# -*- coding: utf-8 -*-
"""OpenAPI 3 documentation (Swagger UI on ``/api-docs``) of the API written by the modules.

payload_cms does not document its internal ``/api`` (used by the admin only):
the documentation lists the ``@api_doc`` routes and the ``@expose`` methods of
the modules that use payload_cms (see ``payload_cms.payload.apidoc``). The
response schemas are generated from the collections, in the shape returned by
``Model`` (Odoo ``read`` / ``web_read``).
"""
import inspect
import json
import re

from . import schema

PARAM = 'payload_cms.api_docs'
DEFAULTS = {
    'enabled': True,
    'public': False,
    'title': 'API',
    'version': '1.0.0',
    'description': '',
    'servers': [],
    'modules': [],        # empty = every module using payload_cms
    'includeRpc': True,   # generic JSON-RPC endpoint (search_read, web_search_read...)
    'includeAuth': True,  # login (JWT for the routes reserved to the CMS users)
}
PYTHON_TYPES = {int: 'integer', float: 'number', str: 'string', bool: 'boolean', list: 'array', dict: 'object'}
MEDIA_FIELDS = {
    'url': {'type': 'string', 'format': 'uri'},
    'filename': {'type': 'string'},
    'mimeType': {'type': 'string'},
    'filesize': {'type': 'integer'},
    'width': {'type': 'integer'},
    'height': {'type': 'integer'},
    'sizes': {'type': 'object', 'additionalProperties': {'type': 'string', 'format': 'uri'},
              'description': 'URL of each image size (thumbnail, small, medium...).'},
}


def get_settings(env):
    settings = json.loads(json.dumps(DEFAULTS))
    raw = env['ir.config_parameter'].sudo().get_param(PARAM)
    if raw:
        try:
            stored = json.loads(raw)
            stored.pop('collections', None)  # previous versions: documented collections
            settings.update(stored)
        except ValueError:
            pass
    return settings


def set_settings(env, settings):
    env['ir.config_parameter'].sudo().set_param(PARAM, json.dumps(settings))


def _pascal(value):
    return ''.join(w[:1].upper() + w[1:] for w in re.split(r'[^A-Za-z0-9]+', value or '') if w) or 'Doc'


def _param_schema(value):
    """``int`` / ``(int, "help")`` / OpenAPI dict -> (schema, description, required)."""
    help_text, required = None, False
    if isinstance(value, tuple):
        value, help_text = value[0], (value[1] if len(value) > 1 else None)
    if isinstance(value, dict):
        value = dict(value)
        help_text = value.pop('description', help_text)
        required = bool(value.pop('required', False))
        return value, help_text, required
    if isinstance(value, type):
        return {'type': PYTHON_TYPES.get(value, 'string')}, help_text, required
    return {'type': 'string'}, help_text, required


def _object(params):
    props, required = {}, []
    for name, value in (params or {}).items():
        schema_, help_text, req = _param_schema(value)
        if help_text:
            schema_['description'] = help_text
        props[name] = schema_
        if req:
            required.append(name)
    result = {'type': 'object', 'properties': props}
    if required:
        result['required'] = required
    return result


class SpecBuilder:
    def __init__(self, env, settings, server_url):
        self.env = env
        self.settings = settings
        self.server_url = server_url
        self.operation_ids = set()

    # ------------------------------------------------------------------
    # Schemas of the records (Odoo shapes)
    # ------------------------------------------------------------------
    def fields_of(self, slug, public):
        from ..payload.model import Model
        try:
            model = Model(self.env, slug).sudo()
        except Exception:  # noqa: BLE001 - unknown collection
            return None, []
        fields = model._fields()
        if public:
            fields = [f for f in fields if not f.get('private')]
        return model, fields

    def record_schema(self, slug, spec, web, public, depth=0):
        """Schema of a record of ``slug`` read with ``spec`` (list, dict or None = every field)."""
        model, fields = self.fields_of(slug, public)
        if model is None:
            return {'type': 'object'}
        by_name = {f['name']: f for f in schema.data_fields(fields)}
        if isinstance(spec, (list, tuple)):
            spec = {name: {} for name in spec}
        names = list(spec) if spec else list(by_name) + ['display_name', 'create_date', 'write_date']
        props = {'id': {'type': 'integer'}}
        for name in names:
            sub = (spec or {}).get(name) or {}
            if name == 'display_name':
                props[name] = {'type': 'string'}
            elif name in ('create_date', 'write_date'):
                props[name] = {'type': 'string', 'format': 'date-time', 'example': '2026-10-12 18:00:00'}
            elif name == 'status':
                props[name] = {'type': 'string', 'enum': ['draft', 'published']}
            elif name in by_name:
                props[name] = self.value_schema(by_name[name], sub, web, public, depth)
            elif name in MEDIA_FIELDS and model.collection.upload:
                props[name] = dict(MEDIA_FIELDS[name])
            elif name == 'alt':
                props[name] = {'type': 'string'}
        title = model.collection.label_singular or model.collection.label
        return {'type': 'object', 'title': title, 'properties': props}

    def value_schema(self, field, sub, web, public, depth):
        ftype = field['type']
        many = field.get('hasMany')
        nested = sub.get('fields') if isinstance(sub, dict) else None
        if ftype in ('relationship', 'upload'):
            target = field.get('relationTo')
            if nested and depth < 6:
                item = self.record_schema(target, nested, web, public, depth + 1)
            elif ftype == 'upload':
                item = {'type': 'string', 'format': 'uri', 'description': 'URL of the file'}
            elif many:
                item = {'type': 'integer', 'description': 'ID of a `%s` record' % target}
            elif web:
                item = {'type': 'object', 'properties': {'id': {'type': 'integer'}, 'display_name': {'type': 'string'}}}
            else:
                item = {'type': 'array', 'minItems': 2, 'maxItems': 2, 'items': {'oneOf': [{'type': 'integer'}, {'type': 'string'}]},
                        'description': '`[id, display_name]`', 'example': [1, 'Name']}
            result = {'type': 'array', 'items': item} if many else item
        elif ftype == 'group':
            result = self.rows_schema(field.get('fields') or [], sub, web, public, depth)
        elif ftype == 'array':
            item = self.rows_schema(field.get('fields') or [], sub, web, public, depth)
            item['properties'] = dict({'id': {'type': 'string'}}, **item['properties'])
            result = {'type': 'array', 'items': item}
        elif ftype == 'blocks':
            variants = []
            for block in field.get('blocks') or []:
                item = self.rows_schema(block.get('fields') or [], sub, web, public, depth)
                item['properties'] = dict({'id': {'type': 'string'}, 'blockType': {'type': 'string', 'enum': [block['slug']]}},
                                          **item['properties'])
                item['title'] = (block.get('labels') or {}).get('singular') or block['slug']
                variants.append(item)
            result = {'type': 'array', 'items': {'oneOf': variants} if variants else {'type': 'object'}}
        else:
            result = self.scalar_schema(field)
            if many and ftype in ('select', 'number', 'text'):
                result = {'type': 'array', 'items': result}
        label = field.get('label') if isinstance(field.get('label'), str) else ''
        help_text = (field.get('admin') or {}).get('description') or ''
        text = ' — '.join(p for p in (label, help_text, result.pop('description', '')) if p)
        if text:
            result['description'] = text
        return result

    def scalar_schema(self, field):
        ftype = field['type']
        if ftype == 'email':
            return {'type': 'string', 'format': 'email'}
        if ftype == 'richText':
            return {'type': 'string', 'format': 'html', 'description': 'HTML'}
        if ftype == 'number':
            return {'type': 'number'}
        if ftype == 'checkbox':
            return {'type': 'boolean'}
        if ftype == 'date':
            day = ((field.get('admin') or {}).get('date') or {}).get('pickerAppearance') == 'dayOnly'
            return {'type': 'string', 'format': 'date' if day else 'date-time',
                    'example': '2026-10-12' if day else '2026-10-12 18:00:00'}
        if ftype in ('select', 'radio'):
            values = [o['value'] if isinstance(o, dict) else o for o in field.get('options') or []]
            return {'type': 'string', 'enum': values} if values else {'type': 'string'}
        if ftype in ('json', 'point'):
            return {}
        return {'type': 'string'}

    def rows_schema(self, fields, sub, web, public, depth):
        by_name = {f['name']: f for f in schema.data_fields(fields)}
        spec = sub.get('fields') if isinstance(sub, dict) else None
        names = list(spec) if spec else list(by_name)
        props = {n: self.value_schema(by_name[n], (spec or {}).get(n) or {}, web, public, depth) for n in names if n in by_name}
        return {'type': 'object', 'properties': props}

    def input_schema(self, slug, names, public):
        """Schema of the values sent to ``create`` / ``write`` (or a route body)."""
        model, fields = self.fields_of(slug, public)
        by_name = {f['name']: f for f in schema.data_fields(fields)}
        props, required = {}, []
        for name in names or list(by_name):
            field = by_name.get(name)
            if not field:
                continue
            ftype = field['type']
            if ftype in ('relationship', 'upload'):
                item = {'type': 'integer', 'description': 'ID of a `%s` record' % field['relationTo']}
                props[name] = {'type': 'array', 'items': item,
                               'description': 'IDs, or x2many commands `[[6, 0, ids]]`, `[[4, id]]`, `[[3, id]]`'} \
                    if field.get('hasMany') else item
            elif ftype in ('group', 'array', 'blocks', 'json', 'point'):
                props[name] = {'description': 'JSON value'}
            else:
                props[name] = self.scalar_schema(field)
            if field.get('label'):
                props[name]['description'] = ' — '.join(p for p in (field['label'], props[name].get('description')) if p)
            if field.get('required'):
                required.append(name)
        result = {'type': 'object', 'properties': props}
        if required:
            result['required'] = required
        return result

    # ------------------------------------------------------------------
    # Delivery format (payload_cms.payload.Delivery)
    # ------------------------------------------------------------------
    def delivery_value(self, field, codes, public, level, depth):
        ftype = field['type']
        if ftype == 'upload':
            url = {'type': 'string', 'format': 'uri', 'nullable': True, 'description': 'URL of the file'}
            result = {'type': 'array', 'items': url} if field.get('hasMany') else url
        elif ftype == 'relationship':
            from ..payload.delivery import type_of
            if level < depth:
                item = self.delivery_document(field['relationTo'], public, top=False, level=level + 1, depth=depth)
            else:
                item = {'type': 'object', 'description': 'Summary of a `%s` (beyond `depth`)' % type_of(field['relationTo']),
                        'properties': {'id': {'type': 'integer'}, 'type': {'type': 'string', 'enum': [type_of(field['relationTo'])]},
                                       'displayName': {'type': 'string', 'nullable': True}}}
            result = {'type': 'array', 'items': item} if field.get('hasMany') else dict(item, nullable=True)
        elif ftype == 'group':
            result = self.delivery_object(field.get('fields') or [], codes, public, level, depth)
        elif ftype == 'array':
            item = self.delivery_object(field.get('fields') or [], codes, public, level, depth)
            item['properties'] = dict({'id': {'type': 'string'}}, **item['properties'])
            result = {'type': 'array', 'items': item}
        elif ftype == 'blocks':
            result = self.delivery_blocks(field, codes, public, level, depth)
        else:
            result = dict(self.scalar_schema(field), nullable=True)
            if field['type'] == 'date':
                day = ((field.get('admin') or {}).get('date') or {}).get('pickerAppearance') == 'dayOnly'
                result.update(example='2026-10-12' if day else '2026-10-12T18:00:00Z')
            if field.get('hasMany') and ftype in ('select', 'number', 'text'):
                result = {'type': 'array', 'items': result}
        if field.get('localized') and codes:
            result = {'type': 'object', 'description': 'Localized: one value per locale (`null` when not translated)',
                      'properties': {code: result for code in codes}}
        label = field.get('label') if isinstance(field.get('label'), str) else ''
        if label:
            result = dict(result, description=' — '.join(p for p in (label, result.get('description')) if p))
        return result

    def _readable(self, field, public):
        if public and field['type'] in ('relationship', 'upload'):
            return bool(self.env['cms.collection'].sudo()._get_by_slug(field['relationTo']).public_read)
        return not (public and field.get('private'))

    def delivery_object(self, fields, codes, public, level, depth):
        from ..payload.delivery import Delivery
        props = {}
        for field in schema.data_fields(fields):
            if self._readable(field, public):
                props[Delivery._key(None, field)] = self.delivery_value(field, codes, public, level, depth)
        return {'type': 'object', 'properties': props}

    def delivery_blocks(self, field, codes, public, level, depth):
        from ..payload.delivery import CONFIG_TYPES, Delivery, camel
        variants = []
        for block in field.get('blocks') or []:
            config, content = {}, {}
            for sub in schema.data_fields(block.get('fields') or []):
                if not self._readable(sub, public):
                    continue
                role = sub.get('role') or ('config' if sub['type'] in CONFIG_TYPES else 'content')
                (config if role == 'config' else content)[Delivery._key(None, sub)] = \
                    self.delivery_value(sub, codes, public, level, depth)
            config['source'] = {'type': 'object', 'nullable': True, 'description': 'Automatic mode: query of the records put in `content`',
                                'properties': {'collection': {'type': 'string'}, 'filter': {'type': 'array', 'items': {}},
                                               'sort': {'type': 'string'}, 'limit': {'type': 'integer', 'nullable': True}}}
            variants.append({'type': 'object', 'title': (block.get('labels') or {}).get('singular') or block['slug'], 'properties': {
                'id': {'type': 'string'}, 'type': {'type': 'string', 'enum': [camel(block['slug'])]},
                'config': {'type': 'object', 'properties': config}, 'content': {'type': 'object', 'properties': content}}})
        return {'type': 'array', 'items': {'oneOf': variants} if variants else {'type': 'object'}}

    def delivery_document(self, slug, public, top=True, level=0, depth=0):
        from ..payload.delivery import META_GROUPS, PUBLISHED_FIELDS, type_of
        from . import localization
        model, fields = self.fields_of(slug, public)
        if model is None:
            return {'type': 'object'}
        codes = localization.locale_codes(localization.get_settings(self.env))
        data_fields = list(schema.data_fields(fields))
        blocks = [f for f in data_fields if f['type'] == 'blocks']
        attributes = [f for f in data_fields if not (f['type'] == 'group' and f['name'] in META_GROUPS)
                      and not (f['type'] == 'blocks' and len(blocks) == 1) and f['name'] not in PUBLISHED_FIELDS]
        attrs = self.delivery_object(attributes, codes, public, level, depth)
        if model.collection.upload:
            attrs['properties']['url'] = {'type': 'string', 'format': 'uri'}
        props = {'id': {'type': 'integer'}, 'type': {'type': 'string', 'enum': [type_of(slug)]}, 'attributes': attrs}
        seo = next((f for f in data_fields if f['type'] == 'group' and f['name'] in META_GROUPS), None)
        if seo:
            props['seo'] = self.delivery_object(seo.get('fields') or [], codes, public, level, depth)
        if len(blocks) == 1:
            props['blocks'] = self.delivery_blocks(blocks[0], codes, public, level, depth)
        if top:
            meta = {'locale': {'type': 'string'}, 'availableLocales': {'type': 'array', 'items': {'type': 'string'}},
                    'createdAt': {'type': 'string', 'format': 'date-time'}, 'updatedAt': {'type': 'string', 'format': 'date-time'}}
            if model.collection.drafts:
                meta['status'] = {'type': 'string', 'enum': ['draft', 'published']}
            if any(f['name'] in PUBLISHED_FIELDS for f in data_fields):
                meta['publishedAt'] = {'type': 'string', 'nullable': True}
            props['meta'] = {'type': 'object', 'properties': meta}
        return {'type': 'object', 'title': model.collection.label_singular or model.collection.label, 'properties': props}

    def delivery_schema(self, doc, public):
        depth = int(doc.get('depth') or 0)
        document = self.delivery_document(doc['model'], public, depth=depth)
        many = doc.get('many') or doc.get('paginated')
        meta = {'locale': {'type': 'string', 'description': '`all` or the locale code'},
                'availableLocales': {'type': 'array', 'items': {'type': 'string'}},
                'defaultLocale': {'type': 'string'}, 'depth': {'type': 'integer'}}
        if many:
            meta.update(total={'type': 'integer'}, limit={'type': 'integer', 'nullable': True}, offset={'type': 'integer'})
        return {'type': 'object', 'properties': {
            'data': {'type': 'array', 'items': document} if many else document,
            'meta': {'type': 'object', 'properties': meta},
        }}

    def response_schema(self, doc, public):
        if doc.get('response') is not None:
            return doc['response']
        if doc.get('delivery') and doc.get('model'):
            return self.delivery_schema(doc, public)
        if not doc.get('model'):
            return {}
        fields = doc.get('fields')
        web = isinstance(fields, dict)
        record = self.record_schema(doc['model'], fields, web, public)
        if doc.get('paginated'):
            return {'type': 'object', 'properties': {'length': {'type': 'integer', 'description': 'Total number of records'},
                                                     'records': {'type': 'array', 'items': record}}}
        return {'type': 'array', 'items': record} if doc.get('many') else record

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------
    def operation_id(self, base):
        name = re.sub(r'[^A-Za-z0-9]+', '_', base).strip('_') or 'operation'
        candidate, index = name, 1
        while candidate in self.operation_ids:
            index += 1
            candidate = '%s_%s' % (name, index)
        self.operation_ids.add(candidate)
        return candidate

    def security(self, auth):
        auth_schemes = [{'bearerAuth': []}, {'cookieAuth': []}]
        return ([{}] + auth_schemes) if auth in ('public', 'none') else auth_schemes

    def tags_of(self, doc, default):
        if doc.get('tags'):
            return list(doc['tags'])
        if doc.get('model'):
            model, _fields = self.fields_of(doc['model'], True)
            if model:
                return [model.collection.label]
        return [default]

    @staticmethod
    def jsonrpc_body(params_schema, example=None):
        params = dict(params_schema)
        if example is not None:
            params['example'] = example
        return {'required': True, 'content': {'application/json': {'schema': {
            'type': 'object', 'required': ['params'],
            'properties': {'jsonrpc': {'type': 'string', 'enum': ['2.0'], 'default': '2.0'},
                           'method': {'type': 'string', 'enum': ['call'], 'default': 'call'},
                           'params': params}}}}}

    @staticmethod
    def jsonrpc_response(result):
        return {'200': {'description': 'JSON-RPC response (`error` instead of `result` on failure)',
                        'content': {'application/json': {'schema': {'type': 'object', 'properties': {
                            'jsonrpc': {'type': 'string'}, 'id': {}, 'result': result,
                            'error': {'$ref': '#/components/schemas/JsonRpcError'}}}}}}}

    def route_operations(self, route, paths, tags):
        doc = route['doc']
        public = route['auth'] in ('public', 'none')
        summary, description = split(route['func'])
        summary = doc.get('summary') or summary or route['func'].__name__.replace('_', ' ').capitalize()
        description = doc.get('description') or description
        op_tags = self.tags_of(doc, route['module'])
        tags.update(op_tags)
        result = self.response_schema(doc, public)
        path_params = [{'name': name, 'in': 'path', 'required': True, 'schema': {'type': t}}
                       for name, t in route['url_params'].items()]
        for p in path_params:
            extra = (doc.get('params') or {}).get(p['name'])
            if extra is not None:
                _schema, help_text, _req = _param_schema(extra)
                if help_text:
                    p['description'] = help_text
        for method in route['methods']:
            operation = {
                'tags': op_tags,
                'summary': summary,
                'operationId': self.operation_id('%s_%s_%s' % (route['module'], route['func'].__name__, method.lower())),
                'security': self.security(route['auth']),
            }
            if description:
                operation['description'] = description
            if doc.get('deprecated'):
                operation['deprecated'] = True
            other = {k: v for k, v in (doc.get('params') or {}).items() if k not in route['url_params']}
            if route['type'] == 'json':
                operation['parameters'] = path_params
                operation['requestBody'] = self.jsonrpc_body(_object(other))
                operation['responses'] = self.jsonrpc_response(result)
            else:
                params = list(path_params)
                for name, value in other.items():
                    schema_, help_text, required = _param_schema(value)
                    item = {'name': name, 'in': 'query', 'schema': schema_, 'required': required}
                    if help_text:
                        item['description'] = help_text
                    params.append(item)
                operation['parameters'] = params
                if method in ('POST', 'PUT', 'PATCH') and doc.get('body') is not None:
                    body = doc['body']
                    body_schema = self.input_schema(doc['model'], body, public) \
                        if isinstance(body, (list, tuple)) and doc.get('model') else _object(body)
                    operation['requestBody'] = {'required': True, 'content': {'application/json': {'schema': body_schema}}}
                operation['responses'] = {'200': {'description': 'OK', 'content': {'application/json': {'schema': result}}}}
                if not public:
                    operation['responses']['401'] = {'description': 'Not authenticated'}
            paths.setdefault(route['path'], {})[method.lower()] = operation

    def exposed_operation(self, item, paths, tags):
        doc = item['doc']
        func = item['func']
        public = item['auth'] == 'public'
        summary, description = split(func)
        op_tags = self.tags_of(dict(doc, model=doc.get('model') or item['model']), item['model'])
        tags.update(op_tags)
        # keyword arguments of the method, from its signature (or `params`)
        params = dict(doc.get('params') or {})
        for name, parameter in list(inspect.signature(func).parameters.items())[1:]:
            if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD) or name in params:
                continue
            default = parameter.default
            schema_ = {'type': PYTHON_TYPES.get(type(default), 'string')} if default not in (inspect.Parameter.empty, None) else {}
            if default is not inspect.Parameter.empty and default is not None:
                schema_['default'] = default
            params[name] = dict(schema_, required=default is inspect.Parameter.empty)
        operation = {
            'tags': op_tags,
            'summary': doc.get('summary') or summary or '%s.%s' % (item['model'], item['method']),
            'operationId': self.operation_id('%s_%s' % (item['model'], item['method'])),
            'security': self.security(item['auth']),
            'description': (doc.get('description') or description or '') +
                           '\n\nJSON-RPC: the `params` are the keyword arguments of the method `%s` of `%s`.' % (item['method'], item['model']),
            'requestBody': self.jsonrpc_body(_object(params)),
            'responses': self.jsonrpc_response(self.response_schema(doc, public)),
        }
        paths['/payload/dataset/call_kw/%s/%s' % (item['model'], item['method'])] = {'post': operation}

    def rpc_operation(self, paths):
        example = {'model': 'events', 'method': 'search_read', 'args': [[['active', '=', True]]],
                   'kwargs': {'fields': ['display_name'], 'order': 'create_date desc', 'limit': 5}}
        paths['/payload/dataset/call_kw'] = {'post': {
            'tags': ['JSON-RPC'],
            'summary': 'Call a method of a collection (like /web/dataset/call_kw)',
            'operationId': self.operation_id('call_kw'),
            'security': self.security('public'),
            'description': (
                'Methods: `search`, `search_count`, `search_read`, `read`, `web_search_read`, `web_read`, '
                '`name_search`, `fields_get`, `create`, `write`, `unlink`, and the `@expose` methods.\n\n'
                'Domains use the Odoo syntax (`[["active", "=", true], "|", ["a", "ilike", "x"], ["b", ">", 3]]`); '
                '`web_search_read` takes a specification selecting the fields, nested for the relations '
                '(`{"speakers": {"fields": {"nom": {}}}}`). Anonymous calls read the public collections; '
                'writes are reserved to the CMS users. `kwargs.context`: `{"lang": "fr_FR"}`, `{"draft": true}`.'),
            'requestBody': self.jsonrpc_body({'type': 'object', 'required': ['model', 'method'], 'properties': {
                'model': {'type': 'string', 'description': 'Collection slug'},
                'method': {'type': 'string'},
                'args': {'type': 'array', 'items': {}},
                'kwargs': {'type': 'object'}}}, example),
            'responses': self.jsonrpc_response({}),
        }}

    def auth_operations(self, paths):
        tag = 'Authentication'
        paths['/api/users/login'] = {'post': {
            'tags': [tag], 'summary': 'Login', 'operationId': self.operation_id('login'), 'security': [{}],
            'description': 'Returns a JWT to send as `Authorization: Bearer <token>`. An Odoo API key works as well.',
            'requestBody': {'required': True, 'content': {'application/json': {'schema': {
                'type': 'object', 'required': ['email', 'password'],
                'properties': {'email': {'type': 'string'}, 'password': {'type': 'string', 'format': 'password'}}}}}},
            'responses': {'200': {'description': 'Logged in', 'content': {'application/json': {'schema': {
                'type': 'object', 'properties': {'token': {'type': 'string'}, 'exp': {'type': 'integer'},
                                                 'user': {'type': 'object'}}}}}},
                          '401': {'description': 'Invalid credentials'}},
        }}

    # ------------------------------------------------------------------
    def build(self):
        from ..payload.apidoc import documented_routes, exposed_methods, payload_modules
        modules = self.settings.get('modules') or payload_modules(self.env)
        paths, tags = {}, set()
        for route in documented_routes(self.env, modules):
            self.route_operations(route, paths, tags)
        for item in exposed_methods(self.env, modules):
            self.exposed_operation(item, paths, tags)
        tag_list = [{'name': t} for t in sorted(tags)]
        if self.settings.get('includeRpc', True):
            self.rpc_operation(paths)
            tag_list.append({'name': 'JSON-RPC', 'description': 'Generic access to the collections.'})
        if self.settings.get('includeAuth', True):
            self.auth_operations(paths)
            tag_list.append({'name': 'Authentication', 'description': 'JWT or Odoo API key for the routes reserved to the CMS users.'})
        description = (self.settings.get('description') or '').strip()
        description += ('\n\n' if description else '') + (
            '**Delivery routes** (content for the frontends): `{data, meta}`, camelCase keys, `null` for missing values, '
            'images as URLs, relations as the related documents themselves (populated down to `?depth=N`, then summaries '
            '`{id, type, displayName}`), '
            'localized fields as `{locale: value}` (`?locale=all|<code>`), blocks as `{type, config, content}`.\n\n'
            '**JSON-RPC / Model routes** (edition): values in the shape of Odoo records (`false` when empty, relation `[id, name]`).')
        servers = [s for s in self.settings.get('servers') or [] if s.get('url')] or [{'url': self.server_url}]
        return {
            'openapi': '3.0.3',
            'info': {'title': self.settings.get('title') or 'API', 'version': self.settings.get('version') or '1.0.0',
                     'description': description},
            'servers': [{'url': s['url'], **({'description': s['description']} if s.get('description') else {})} for s in servers],
            'tags': tag_list,
            'paths': dict(sorted(paths.items())),
            'components': {
                'schemas': {'JsonRpcError': {'type': 'object', 'nullable': True, 'properties': {
                    'code': {'type': 'integer'}, 'message': {'type': 'string'},
                    'data': {'type': 'object', 'properties': {'name': {'type': 'string'}, 'message': {'type': 'string'}}}}}},
                'securitySchemes': {
                    'bearerAuth': {'type': 'http', 'scheme': 'bearer',
                                   'description': 'Odoo API key, or the JWT returned by POST /api/users/login.'},
                    'cookieAuth': {'type': 'apiKey', 'in': 'cookie', 'name': 'session_id',
                                   'description': 'Odoo session (automatic in this page when you are logged in).'},
                },
            },
        }


def split(func):
    from ..payload.apidoc import split_docstring
    return split_docstring(func)


def build_spec(env, settings, server_url):
    return SpecBuilder(env, settings, server_url).build()


def admin_routes(env, model=None):
    """Documented routes and exposed methods (API tab of the admin), optionally for one collection."""
    from ..payload.apidoc import documented_routes, exposed_methods
    result = []
    for route in documented_routes(env):
        if model and route['doc'].get('model') != model:
            continue
        summary = route['doc'].get('summary') or split(route['func'])[0] or route['func'].__name__
        result.append({'methods': route['methods'], 'path': route['path'], 'type': route['type'], 'auth': route['auth'],
                       'module': route['module'], 'summary': summary, 'model': route['doc'].get('model') or None})
    for item in exposed_methods(env):
        if model and item['model'] != model:
            continue
        summary = item['doc'].get('summary') or split(item['func'])[0] or item['method']
        result.append({'methods': ['POST'], 'path': '/payload/dataset/call_kw/%s/%s' % (item['model'], item['method']),
                       'type': 'json', 'auth': item['auth'], 'module': item['module'], 'summary': summary, 'model': item['model']})
    return result
