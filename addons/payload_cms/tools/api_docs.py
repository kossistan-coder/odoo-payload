# -*- coding: utf-8 -*-
"""Automatic OpenAPI 3 documentation (Swagger UI on ``/api-docs``).

The specification is generated on the fly from the collections and globals
schema, so it always matches the REST API (fields, drafts, versions, uploads,
localization, multi-tenancy).
"""
import json
import re

from . import schema

PARAM = 'payload_cms.api_docs'
DEFAULTS = {
    'enabled': True,
    'public': False,
    'title': 'Payload CMS API',
    'version': '1.0.0',
    'description': 'REST API of the Payload CMS for Odoo. Rich text fields are returned as HTML.',
    'servers': [],
    'collections': [],  # empty = every collection & global
    'includeAuth': True,
}


def get_settings(env):
    settings = json.loads(json.dumps(DEFAULTS))
    raw = env['ir.config_parameter'].sudo().get_param(PARAM)
    if raw:
        try:
            settings.update(json.loads(raw))
        except ValueError:
            pass
    return settings


def set_settings(env, settings):
    env['ir.config_parameter'].sudo().set_param(PARAM, json.dumps(settings))


def _pascal(value):
    return ''.join(w[:1].upper() + w[1:] for w in re.split(r'[^A-Za-z0-9]+', value or '') if w) or 'Doc'


def _ref(name):
    return {'$ref': '#/components/schemas/%s' % name}


class SpecBuilder:
    def __init__(self, env, settings, server_url, localization=None, multitenancy=None):
        self.env = env
        self.settings = settings
        self.server_url = server_url
        self.localization = localization  # public localization settings (enabled only)
        self.multitenancy = multitenancy  # multitenancy settings (enabled only)
        self.schemas = {}
        self.names = {}

    # ------------------------------------------------------------------
    # Schemas
    # ------------------------------------------------------------------
    def schema_name(self, collection):
        key = (collection.kind, collection.slug)
        if key not in self.names:
            base = _pascal(collection.slug)
            name = ('Global' + base) if collection.kind == 'global' else base
            while name in self.names.values():
                name += '_'
            self.names[key] = name
        return self.names[key]

    def field_schema(self, field):
        ftype = field.get('type')
        result = {}
        if ftype in ('text', 'textarea', 'code', 'slug', 'password'):
            result = {'type': 'string'}
        elif ftype == 'email':
            result = {'type': 'string', 'format': 'email'}
        elif ftype == 'number':
            result = {'type': 'number'}
        elif ftype == 'checkbox':
            result = {'type': 'boolean'}
        elif ftype == 'date':
            result = {'type': 'string', 'format': 'date-time'}
        elif ftype in ('select', 'radio'):
            values = [o['value'] if isinstance(o, dict) else o for o in field.get('options') or []]
            result = {'type': 'string', 'enum': values} if values else {'type': 'string'}
        elif ftype == 'richText':
            result = {'type': 'string', 'format': 'html',
                      'description': 'HTML. Send HTML or a Lexical state; `?richText=lexical` returns the Lexical JSON.'}
        elif ftype == 'json':
            result = {'description': 'Any JSON value.'}
        elif ftype == 'point':
            result = {'type': 'array', 'items': {'type': 'number'}, 'minItems': 2, 'maxItems': 2}
        elif ftype in ('upload', 'relationship'):
            target = self.env['cms.collection']._get_by_slug(field.get('relationTo') or '')
            one = {'oneOf': [{'type': 'integer', 'description': 'ID (depth=0)'}]}
            if target:
                one['oneOf'].append(_ref(self.schema_name(target)))
            one['description'] = 'Related %s: its ID, or the populated document when depth > 0.' % (field.get('relationTo') or '')
            result = one
        elif ftype == 'group':
            result = self.object_schema(field.get('fields') or [])
        elif ftype == 'array':
            item = self.object_schema(field.get('fields') or [])
            item['properties'] = dict({'id': {'type': 'string'}}, **item['properties'])
            result = {'type': 'array', 'items': item}
        elif ftype == 'blocks':
            variants = []
            for block in field.get('blocks') or []:
                item = self.object_schema(block.get('fields') or [])
                item['properties'] = dict({
                    'id': {'type': 'string'},
                    'blockType': {'type': 'string', 'enum': [block['slug']]},
                    'blockName': {'type': 'string', 'nullable': True},
                }, **item['properties'])
                item['title'] = (block.get('labels') or {}).get('singular') or block['slug']
                item.setdefault('required', []).append('blockType')
                variants.append(item)
            result = {'type': 'array', 'items': {'oneOf': variants} if variants else {'type': 'object'}}
        else:
            result = {}
        if field.get('hasMany') and ftype in ('select', 'number', 'upload', 'relationship', 'text'):
            result = {'type': 'array', 'items': result}
        parts = [field.get('label') if isinstance(field.get('label'), str) else '',
                 (field.get('admin') or {}).get('description') or '', result.pop('description', '')]
        if field.get('localized') and self.localization:
            parts.append('Localized: one value per locale (`?locale=`; `?locale=all` returns `{code: value}`).')
        if any(parts):
            result['description'] = ' — '.join(p for p in parts if p)
        if field.get('defaultValue') is not None and not isinstance(field.get('defaultValue'), (dict, list)):
            result['default'] = field['defaultValue']
        if (field.get('admin') or {}).get('readOnly'):
            result['readOnly'] = True
        return result

    def object_schema(self, fields):
        properties, required = {}, []
        for field in schema.data_fields(fields):
            if field.get('private'):
                continue
            properties[field['name']] = self.field_schema(field)
            if field.get('required'):
                required.append(field['name'])
        result = {'type': 'object', 'properties': properties}
        if required:
            result['required'] = required
        return result

    def document_schema(self, collection):
        fields = collection._payload_fields()
        doc = self.object_schema(fields)
        required = doc.pop('required', [])
        props = {}
        if collection.kind == 'collection':
            props['id'] = {'type': 'integer', 'readOnly': True}
        props.update(doc['properties'])
        if collection.upload:
            props.update({
                'url': {'type': 'string', 'readOnly': True},
                'thumbnailURL': {'type': 'string', 'nullable': True, 'readOnly': True},
                'filename': {'type': 'string', 'readOnly': True},
                'mimeType': {'type': 'string', 'readOnly': True},
                'filesize': {'type': 'integer', 'readOnly': True},
                'width': {'type': 'integer', 'nullable': True, 'readOnly': True},
                'height': {'type': 'integer', 'nullable': True, 'readOnly': True},
                'focalX': {'type': 'number'},
                'focalY': {'type': 'number'},
                'sizes': {'type': 'object', 'readOnly': True, 'additionalProperties': {
                    'type': 'object', 'properties': {k: {'type': 'string' if k in ('url', 'mimeType', 'filename') else 'integer', 'nullable': True}
                                                     for k in ('url', 'width', 'height', 'mimeType', 'filesize', 'filename')}}},
            })
        if collection.drafts:
            props['_status'] = {'type': 'string', 'enum': ['draft', 'published']}
        props['updatedAt'] = {'type': 'string', 'format': 'date-time', 'readOnly': True}
        props['createdAt'] = {'type': 'string', 'format': 'date-time', 'readOnly': True}
        if collection.kind == 'global':
            props['globalType'] = {'type': 'string', 'enum': [collection.slug], 'readOnly': True}
        name = self.schema_name(collection)
        self.schemas[name] = {'type': 'object', 'title': collection.label_singular or collection.label,
                              'properties': props}
        body = {'type': 'object', 'properties': {k: v for k, v in props.items() if not v.get('readOnly')}}
        if required:
            body['required'] = required
        self.schemas[name + 'Input'] = body
        return name

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    def params(self, *names):
        return [{'$ref': '#/components/parameters/%s' % n} for n in names]

    def security(self, public):
        auth = [{'bearerAuth': []}, {'apiKeyAuth': []}, {'cookieAuth': []}]
        return ([{}] + auth) if public else auth

    def doc_response(self, ref, wrap=None, description='OK'):
        content = _ref(ref) if not wrap else {'type': 'object', 'properties': {
            wrap: _ref(ref), 'message': {'type': 'string'}}}
        return {'description': description, 'content': {'application/json': {'schema': content}}}

    def errors(self, *codes):
        return {str(c): {'$ref': '#/components/responses/Error%s' % c} for c in codes}

    def collection_paths(self, collection, paths):
        name = self.document_schema(collection)
        tag = collection.label
        slug = collection.slug
        read_params = ['depth', 'draft', 'richText'] + (['locale', 'fallbackLocale'] if self.localization else []) \
            + (['tenant'] if self.multitenancy and collection.multi_tenant else [])
        write_params = ['depth'] + (['draft'] if collection.drafts else []) + (['locale'] if self.localization else []) \
            + (['tenant'] if self.multitenancy and collection.multi_tenant else [])
        if collection.upload:
            body = {'required': True, 'content': {'multipart/form-data': {'schema': {
                'type': 'object', 'properties': {
                    'file': {'type': 'string', 'format': 'binary'},
                    '_payload': {'type': 'string', 'description': 'JSON of the other fields (%sInput)' % name},
                }}}, 'application/json': {'schema': _ref(name + 'Input')}}}
        else:
            body = {'required': True, 'content': {'application/json': {'schema': _ref(name + 'Input')}}}
        public_read = bool(collection.public_read)
        public_create = bool(collection.public_create)
        paths['/api/%s' % slug] = {
            'get': {
                'tags': [tag], 'summary': 'Find %s' % collection.label, 'operationId': 'find%s' % name,
                'parameters': self.params('where', 'sort', 'limit', 'page', 'pagination', *read_params),
                'security': self.security(public_read),
                'responses': dict({'200': {'description': 'Paginated documents', 'content': {'application/json': {'schema': {
                    'allOf': [_ref('PaginatedDocs'), {'type': 'object', 'properties': {'docs': {'type': 'array', 'items': _ref(name)}}}]}}}}},
                    **self.errors(400, 401, 403)),
            },
            'post': {
                'tags': [tag], 'summary': 'Create %s' % (collection.label_singular or collection.label),
                'operationId': 'create%s' % name, 'parameters': self.params(*write_params), 'requestBody': body,
                'security': self.security(public_create),
                'responses': dict({'201': self.doc_response(name, 'doc', 'Created')}, **self.errors(400, 401, 403)),
            },
            'patch': {
                'tags': [tag], 'summary': 'Update many (where)', 'operationId': 'updateMany%s' % name,
                'parameters': self.params('whereRequired', *write_params),
                'requestBody': {'required': True, 'content': {'application/json': {'schema': _ref(name + 'Input')}}},
                'security': self.security(False),
                'responses': dict({'200': {'description': 'Updated documents'}}, **self.errors(400, 401, 403)),
            },
            'delete': {
                'tags': [tag], 'summary': 'Delete many (where)', 'operationId': 'deleteMany%s' % name,
                'parameters': self.params('whereRequired'), 'security': self.security(False),
                'responses': dict({'200': {'description': 'Deleted documents'}}, **self.errors(400, 401, 403)),
            },
        }
        paths['/api/%s/count' % slug] = {'get': {
            'tags': [tag], 'summary': 'Count %s' % collection.label, 'operationId': 'count%s' % name,
            'parameters': self.params('where', 'draft', *(['tenant'] if self.multitenancy and collection.multi_tenant else [])),
            'security': self.security(public_read),
            'responses': {'200': {'description': 'Count', 'content': {'application/json': {'schema': {
                'type': 'object', 'properties': {'totalDocs': {'type': 'integer'}}}}}}},
        }}
        paths['/api/%s/{id}' % slug] = {
            'parameters': self.params('id'),
            'get': {
                'tags': [tag], 'summary': 'Find by ID', 'operationId': 'findById%s' % name,
                'parameters': self.params(*read_params), 'security': self.security(public_read),
                'responses': dict({'200': self.doc_response(name)}, **self.errors(401, 403, 404)),
            },
            'patch': {
                'tags': [tag], 'summary': 'Update by ID', 'operationId': 'update%s' % name,
                'parameters': self.params(*(write_params + (['autosave'] if collection.autosave else []))),
                'requestBody': body, 'security': self.security(False),
                'responses': dict({'200': self.doc_response(name, 'doc')}, **self.errors(400, 401, 403, 404)),
            },
            'delete': {
                'tags': [tag], 'summary': 'Delete by ID', 'operationId': 'delete%s' % name,
                'security': self.security(False),
                'responses': dict({'200': self.doc_response(name, 'doc')}, **self.errors(401, 403, 404)),
            },
        }
        paths['/api/%s/{id}/duplicate' % slug] = {'post': {
            'tags': [tag], 'summary': 'Duplicate', 'operationId': 'duplicate%s' % name, 'parameters': self.params('id'),
            'security': self.security(False), 'responses': dict({'201': self.doc_response(name, 'doc', 'Created')}, **self.errors(401, 403, 404)),
        }}
        if self.localization:
            paths['/api/%s/{id}/translate' % slug] = {'post': self.translate_operation(tag, name, with_id=True)}
        if collection.versions or collection.drafts:
            self.version_paths(paths, '/api/%s/versions' % slug, tag, name)
        if collection.upload:
            paths['/api/%s/file/{filename}' % slug] = {'get': {
                'tags': [tag], 'summary': 'Download a file (or an image size)', 'operationId': 'file%s' % name,
                'parameters': [{'name': 'filename', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}],
                'security': self.security(public_read),
                'responses': {'200': {'description': 'File', 'content': {'*/*': {'schema': {'type': 'string', 'format': 'binary'}}}}, '404': {'$ref': '#/components/responses/Error404'}},
            }}

    def translate_operation(self, tag, name, with_id):
        return {
            'tags': [tag], 'summary': 'Machine translation (Google Translate)', 'operationId': 'translate%s' % name,
            'parameters': self.params('id') if with_id else [],
            'requestBody': {'content': {'application/json': {'schema': {'type': 'object', 'properties': {
                'from': {'type': 'string', 'description': 'Source locale (default locale by default)'},
                'to': {'oneOf': [{'type': 'string'}, {'type': 'array', 'items': {'type': 'string'}}],
                       'description': 'Target locale(s), or "all"'},
                'overwrite': {'type': 'boolean', 'default': True, 'description': 'false = only fill empty values'},
            }}}}},
            'security': self.security(False),
            'responses': dict({'200': {'description': 'Translated document'}}, **self.errors(400, 401, 403, 404)),
        }

    def version_paths(self, paths, base, tag, name):
        paths[base] = {'get': {
            'tags': [tag], 'summary': 'Find versions', 'operationId': 'versions%s' % name,
            'parameters': self.params('where', 'sort', 'limit', 'page'), 'security': self.security(False),
            'responses': dict({'200': {'description': 'Paginated versions'}}, **self.errors(401, 403)),
        }}
        paths[base + '/{id}'] = {
            'parameters': self.params('id'),
            'get': {'tags': [tag], 'summary': 'Find version by ID', 'operationId': 'version%s' % name,
                    'parameters': self.params('depth'), 'security': self.security(False),
                    'responses': dict({'200': {'description': 'Version', 'content': {'application/json': {'schema': {
                        'type': 'object', 'properties': {'id': {'type': 'integer'}, 'parent': {'type': 'integer'},
                                                         'version': _ref(name), 'latest': {'type': 'boolean'},
                                                         'autosave': {'type': 'boolean'}}}}}}}, **self.errors(401, 403, 404))},
            'post': {'tags': [tag], 'summary': 'Restore version', 'operationId': 'restoreVersion%s' % name,
                     'parameters': self.params('draft'), 'security': self.security(False),
                     'responses': dict({'200': self.doc_response(name, 'doc')}, **self.errors(401, 403, 404))},
        }

    def global_paths(self, collection, paths):
        name = self.document_schema(collection)
        tag = 'Globals'
        base = '/api/globals/%s' % collection.slug
        read_params = ['depth', 'draft', 'richText'] + (['locale', 'fallbackLocale'] if self.localization else []) \
            + (['tenant'] if self.multitenancy and collection.multi_tenant else [])
        paths[base] = {
            'get': {'tags': [tag], 'summary': 'Get %s' % collection.label, 'operationId': 'get%s' % name,
                    'parameters': self.params(*read_params), 'security': self.security(bool(collection.public_read)),
                    'responses': dict({'200': self.doc_response(name)}, **self.errors(401, 403))},
            'post': {'tags': [tag], 'summary': 'Update %s' % collection.label, 'operationId': 'update%s' % name,
                     'parameters': self.params('depth', *(['draft'] if collection.drafts else []),
                                               *(['locale'] if self.localization else []),
                                               *(['tenant'] if self.multitenancy and collection.multi_tenant else [])),
                     'requestBody': {'required': True, 'content': {'application/json': {'schema': _ref(name + 'Input')}}},
                     'security': self.security(False),
                     'responses': dict({'200': self.doc_response(name, 'result')}, **self.errors(400, 401, 403))},
        }
        if self.localization:
            paths[base + '/translate'] = {'post': self.translate_operation(tag, name, with_id=False)}
        if collection.versions or collection.drafts:
            self.version_paths(paths, base + '/versions', tag, name)

    def auth_paths(self, paths):
        tag = 'Authentication'
        user = {'type': 'object', 'properties': {
            'id': {'type': 'integer'}, 'email': {'type': 'string'}, 'name': {'type': 'string'},
            'roles': {'type': 'array', 'items': {'type': 'string'}}}}
        self.schemas['User'] = user
        paths['/api/users/login'] = {'post': {
            'tags': [tag], 'summary': 'Login', 'operationId': 'login', 'security': [{}],
            'description': 'Returns a JWT: send it as `Authorization: Bearer <token>` (or `JWT <token>`). Also sets the Odoo session cookie.',
            'requestBody': {'required': True, 'content': {'application/json': {'schema': {
                'type': 'object', 'required': ['email', 'password'],
                'properties': {'email': {'type': 'string'}, 'password': {'type': 'string', 'format': 'password'}}}}}},
            'responses': {'200': {'description': 'Logged in', 'content': {'application/json': {'schema': {
                'type': 'object', 'properties': {'user': _ref('User'), 'token': {'type': 'string'},
                                                 'exp': {'type': 'integer'}, 'message': {'type': 'string'}}}}}},
                          '401': {'$ref': '#/components/responses/Error401'}},
        }}
        paths['/api/users/logout'] = {'post': {'tags': [tag], 'summary': 'Logout', 'operationId': 'logout',
                                               'security': self.security(True), 'responses': {'200': {'description': 'Logged out'}}}}
        paths['/api/users/me'] = {'get': {
            'tags': [tag], 'summary': 'Current user', 'operationId': 'me', 'security': self.security(True),
            'responses': {'200': {'description': 'Current user (null when anonymous)', 'content': {'application/json': {'schema': {
                'type': 'object', 'properties': {'user': _ref('User'), 'exp': {'type': 'integer'}, 'token': {'type': 'string'}}}}}}},
        }}
        paths['/api/users/refresh-token'] = {'post': {
            'tags': [tag], 'summary': 'Refresh the JWT', 'operationId': 'refreshToken', 'security': self.security(False),
            'responses': dict({'200': {'description': 'New token'}}, **self.errors(401))}}

    # ------------------------------------------------------------------
    def build(self):
        Collection = self.env['cms.collection'].sudo()
        wanted = set(self.settings.get('collections') or [])
        records = Collection.search([], order='kind, sequence, id')
        paths = {}
        tags = []
        if self.settings.get('includeAuth', True):
            self.auth_paths(paths)
            tags.append({'name': 'Authentication', 'description': 'JWT, API key (`Authorization: users API-Key <key>`) or Odoo session.'})
        for collection in records:
            # every schema exists, so relationships to undocumented collections still resolve
            self.document_schema(collection)
        has_globals = False
        for collection in records:
            key = collection.slug if collection.kind == 'collection' else 'globals/%s' % collection.slug
            if wanted and key not in wanted:
                continue
            if collection.kind == 'global':
                has_globals = True
                self.global_paths(collection, paths)
            else:
                tags.append({'name': collection.label, 'description': collection.description or 'Collection `%s`' % collection.slug})
                self.collection_paths(collection, paths)
        if has_globals:
            tags.append({'name': 'Globals', 'description': 'Single documents (header, footer, settings…).'})
        description = self.settings.get('description') or ''
        if self.localization:
            description += '\n\n**Localization**: locales %s (default `%s`).' % (
                ', '.join('`%s`' % l['code'] for l in self.localization.get('locales') or []), self.localization.get('defaultLocale'))
        if self.multitenancy:
            description += ('\n\n**Multi-tenant**: the site is resolved from the `X-Payload-Tenant` header '
                            '(ID or slug), the `?tenant=` parameter or the request host (site domain / subdomain).')
        servers = [s for s in self.settings.get('servers') or [] if s.get('url')] or [{'url': self.server_url}]
        return {
            'openapi': '3.0.3',
            'info': {'title': self.settings.get('title') or 'Payload CMS API',
                     'version': self.settings.get('version') or '1.0.0', 'description': description.strip()},
            'servers': [{'url': s['url'], **({'description': s['description']} if s.get('description') else {})} for s in servers],
            'tags': tags,
            'paths': paths,
            'components': {
                'schemas': dict(self.schemas, **self.common_schemas()),
                'parameters': self.common_parameters(),
                'responses': {('Error%s' % c): {'description': d, 'content': {'application/json': {'schema': _ref('Errors')}}}
                              for c, d in ((400, 'Bad request / validation error'), (401, 'Unauthorized'),
                                           (403, 'Forbidden'), (404, 'Not found'))},
                'securitySchemes': {
                    'bearerAuth': {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT',
                                   'description': 'Token returned by POST /api/users/login.'},
                    'apiKeyAuth': {'type': 'apiKey', 'in': 'header', 'name': 'Authorization',
                                   'description': 'Odoo API key: `users API-Key <key>`.'},
                    'cookieAuth': {'type': 'apiKey', 'in': 'cookie', 'name': 'session_id',
                                   'description': 'Odoo session (automatic in this page when you are logged in).'},
                },
            },
        }

    def common_schemas(self):
        return {
            'PaginatedDocs': {'type': 'object', 'properties': {
                'docs': {'type': 'array', 'items': {}}, 'totalDocs': {'type': 'integer'}, 'limit': {'type': 'integer'},
                'totalPages': {'type': 'integer'}, 'page': {'type': 'integer'}, 'pagingCounter': {'type': 'integer'},
                'hasPrevPage': {'type': 'boolean'}, 'hasNextPage': {'type': 'boolean'},
                'prevPage': {'type': 'integer', 'nullable': True}, 'nextPage': {'type': 'integer', 'nullable': True}}},
            'Errors': {'type': 'object', 'properties': {'errors': {'type': 'array', 'items': {'type': 'object', 'properties': {
                'name': {'type': 'string'}, 'message': {'type': 'string'},
                'data': {'type': 'object', 'properties': {'collection': {'type': 'string'}, 'errors': {'type': 'array', 'items': {
                    'type': 'object', 'properties': {'path': {'type': 'string'}, 'message': {'type': 'string'}}}}}}}}}}},
        }

    def common_parameters(self):
        where_desc = ('Payload query as JSON, e.g. `{"title":{"like":"hello"}}`, or with the qs syntax '
                      '`where[title][like]=hello`. Operators: equals, not_equals, in, not_in, all, like, not_like, '
                      'contains, exists, greater_than(_equal), less_than(_equal), combined with and / or.')
        params = {
            'id': {'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}},
            'where': {'name': 'where', 'in': 'query', 'schema': {'type': 'string'}, 'description': where_desc},
            'whereRequired': {'name': 'where', 'in': 'query', 'required': True, 'schema': {'type': 'string'}, 'description': where_desc},
            'sort': {'name': 'sort', 'in': 'query', 'schema': {'type': 'string'}, 'description': 'Field name, `-` prefix = descending (e.g. `-createdAt`).'},
            'limit': {'name': 'limit', 'in': 'query', 'schema': {'type': 'integer', 'default': 10}},
            'page': {'name': 'page', 'in': 'query', 'schema': {'type': 'integer', 'default': 1}},
            'pagination': {'name': 'pagination', 'in': 'query', 'schema': {'type': 'boolean', 'default': True}},
            'depth': {'name': 'depth', 'in': 'query', 'schema': {'type': 'integer', 'default': 2, 'minimum': 0, 'maximum': 10},
                      'description': 'Relationship population depth.'},
            'draft': {'name': 'draft', 'in': 'query', 'schema': {'type': 'boolean'},
                      'description': 'Read: return the latest draft (editors only). Write: save as a draft.'},
            'autosave': {'name': 'autosave', 'in': 'query', 'schema': {'type': 'boolean'}},
            'richText': {'name': 'richText', 'in': 'query', 'schema': {'type': 'string', 'enum': ['html', 'lexical']},
                         'description': 'Rich text output format (HTML by default).'},
        }
        if self.localization:
            codes = [l['code'] for l in self.localization.get('locales') or []]
            params['locale'] = {'name': 'locale', 'in': 'query', 'schema': {'type': 'string', 'enum': codes + ['all']},
                                'description': 'Locale (default `%s`); `all` returns every locale.' % self.localization.get('defaultLocale')}
            params['fallbackLocale'] = {'name': 'fallback-locale', 'in': 'query', 'schema': {'type': 'string', 'enum': codes + ['none']},
                                        'description': 'Locale used for empty values, `none` to disable the fallback.'}
        if self.multitenancy:
            params['tenant'] = {'name': 'X-Payload-Tenant', 'in': 'header', 'schema': {'type': 'string'},
                                'description': 'Site (tenant) ID or slug. Optional when the request host is a site domain.'}
        return params


def build_spec(env, settings, server_url, localization=None, multitenancy=None):
    return SpecBuilder(env, settings, server_url, localization, multitenancy).build()
