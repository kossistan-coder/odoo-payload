# -*- coding: utf-8 -*-
"""Odoo-like access to the Payload collections: domains, ``search_read``, JSON-RPC.

The documents are read and written like Odoo records, with the same shapes::

    from odoo.addons.payload_cms.payload import Model

    Events = Model(request.env, 'events')
    Events.search_read([('active', '=', True)], ['designation', 'date_sortie', 'episode'],
                       order='date_sortie desc', limit=3)
    # [{'id': 68, 'designation': "Épisode 7 ...", 'date_sortie': '2026-10-12', 'episode': [73, 'https://...']}]

    Events.web_search_read([('active', '=', True)], {
        'designation': {},
        'couverture': {},                                    # image -> URL
        'speakers': {'fields': {'nom': {}, 'prenom': {}, 'profile': {}}},
    }, limit=3)
    # {'length': 7, 'records': [{'id': 68, 'designation': ..., 'couverture': '/api/media/file/vignette.jpg',
    #                            'speakers': [{'id': 38, 'nom': 'BATAKA', 'prenom': 'Yao', 'profile': '/api/...'}]}]}

    Events.create({'designation': 'Live', 'date_sortie': '2026-11-02', 'speakers': [(6, 0, [38, 32])]})
    Events.write([68], {'active': False})

Shapes (like ``read`` in Odoo): empty values are ``False``; a relationship is
``[id, display_name]`` (``{'id', 'display_name'}`` in ``web_read``), a "has many"
relationship a list of ids; an image / file is its URL; a rich text is HTML;
a date is ``'YYYY-MM-DD'``, a date and time ``'YYYY-MM-DD HH:MM:SS'`` (UTC).

Access rights follow the collection: anonymous visitors read the published
documents of the collections with *Public read* (private fields hidden); CMS
editors read / write everything. ``Model(...).sudo()`` bypasses the checks,
like ``sudo()`` in Odoo. ``context={'draft': True}`` (editors) reads the drafts,
``context={'lang': 'fr_FR'}`` a locale.

Own API methods are declared on the code-first collection with ``@expose``
and called from Python (``Model(env, 'events').upcoming(3)``) or JSON-RPC::

    class Event(Collection):
        @expose(auth='public')
        def upcoming(self, limit=3):
            return self.search_read([('active', '=', True)], ['designation', 'date_sortie'], limit=limit)
"""
import functools
import re

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import SQL

EDITOR_GROUP = 'payload_cms.group_payload_cms_user'
# Odoo names of the meta columns -> Payload query properties
META = {'id': 'id', 'create_date': 'createdAt', 'write_date': 'updatedAt', 'status': '_status', 'display_name': None}
OPERATORS = {
    '=': 'equals', '!=': 'not_equals', '<>': 'not_equals', 'in': 'in', 'not in': 'not_in',
    'ilike': 'contains', 'like': 'contains', '=like': 'like', '=ilike': 'like',
    'not ilike': 'not_like', 'not like': 'not_like',
    '>': 'greater_than', '>=': 'greater_than_equal', '<': 'less_than', '<=': 'less_than_equal',
}
NEGATIONS = {'=': '!=', '!=': '=', '<>': '=', 'in': 'not in', 'not in': 'in', 'ilike': 'not ilike',
             'like': 'not like', 'not ilike': 'ilike', 'not like': 'like', '>': '<=', '>=': '<', '<': '>=', '<=': '>'}
# methods callable through JSON-RPC (plus the @expose methods of the collection class)
READ_METHODS = {'search', 'search_count', 'search_read', 'read', 'name_search', 'fields_get',
                'web_search_read', 'web_read'}
WRITE_METHODS = {'create', 'write', 'unlink'}
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
DATETIME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$')


def expose(func=None, *, auth='user', **doc):
    """Makes a method of a code-first collection callable through JSON-RPC
    (``POST /payload/dataset/call_kw/<collection>/<method>``).

    ``auth='public'``: anyone (visitors of the site); ``'user'``: CMS editors.
    The other parameters document the method in Swagger, like ``@api_doc``
    (``summary``, ``tags``, ``model``, ``fields``, ``many``...)."""
    if func is None:
        return functools.partial(expose, auth=auth, **doc)
    from .apidoc import DOC_ATTR, DOC_KEYS
    unknown = set(doc) - set(DOC_KEYS)
    if unknown:
        raise TypeError("expose(): unknown parameter(s) %s" % ', '.join(sorted(unknown)))
    func._payload_expose = auth
    setattr(func, DOC_ATTR, doc)
    return func


# ----------------------------------------------------------------------
# Domains
# ----------------------------------------------------------------------
def _leaf(leaf, title, types):
    if not isinstance(leaf, (list, tuple)) or len(leaf) != 3:
        raise UserError("Invalid domain term %r" % (leaf,))
    name, operator, value = leaf
    operator = operator.lower()
    if name in META:
        name = META[name] or title
    if operator not in OPERATORS:
        raise UserError("Unsupported operator %r" % operator)
    if types.get(name) == 'checkbox' and operator in ('=', '!=') and value in (True, False, None):
        # like an Odoo boolean: False = false or not set
        if (operator == '=') == bool(value):
            return {name: {'equals': True}}
        return {'or': [{name: {'equals': False}}, {name: {'exists': False}}]}
    if value is False or value is None:
        if operator in ('=', '!='):
            return {name: {'exists': operator == '!='}}
    if isinstance(value, tuple):
        value = list(value)
    return {name: {OPERATORS[operator]: value}}


def domain_to_where(domain, title='title', types=None):
    """Odoo domain (prefix notation, implicit AND) -> Payload ``where``.
    ``title``: field searched by ``display_name``; ``types``: {field name: Payload type}."""
    types = types or {}
    domain = list(domain or [])
    if not domain:
        return {}

    def parse(index, negate=False):
        token = domain[index]
        if token in ('&', '|'):
            left, index = parse(index + 1, negate)
            right, index = parse(index, negate)
            op = 'and' if (token == '&') != negate else 'or'
            return {op: [left, right]}, index
        if token == '!':
            return parse(index + 1, not negate)
        if negate:
            name, operator, value = token
            if operator.lower() not in NEGATIONS:
                raise UserError("Operator %r cannot be negated" % operator)
            token = (name, NEGATIONS[operator.lower()], value)
        return _leaf(token, title, types), index + 1

    terms, index = [], 0
    while index < len(domain):
        term, index = parse(index)
        terms.append(term)
    return terms[0] if len(terms) == 1 else {'and': terms}


def order_to_sort(order, title='title'):
    """``'date_sortie desc, nom'`` -> ``'-date_sortie,nom'``."""
    sort = []
    for part in (order or '').split(','):
        words = part.split()
        if not words:
            continue
        name = (META[words[0]] or title) if words[0] in META else words[0]
        sort.append(('-' if len(words) > 1 and words[1].lower() == 'desc' else '') + name)
    return ','.join(sort) or None


# ----------------------------------------------------------------------
# Model
# ----------------------------------------------------------------------
class Model:
    """A Payload collection (or global) seen as an Odoo model."""

    def __init__(self, env, slug, su=False, context=None):
        self.env = env
        self.slug = slug
        self.su = su
        self.context = dict(context or {})
        Collection = env['cms.collection'].sudo()
        self.collection = Collection._get_by_slug(slug) or Collection._get_by_slug(slug, 'global')
        if not self.collection:
            raise UserError("Unknown collection '%s'" % slug)
        self._cache = {}

    def __repr__(self):
        return "Model(%r)" % self.slug

    # -- environment -----------------------------------------------------
    def sudo(self):
        return Model(self.env, self.slug, su=True, context=self.context)

    def with_context(self, **context):
        return Model(self.env, self.slug, su=self.su, context=dict(self.context, **context))

    @property
    def is_editor(self):
        return self.su or self.env.user.has_group(EDITOR_GROUP)

    @property
    def draft(self):
        return bool(self.context.get('draft')) and self.is_editor

    def _check(self, operation):
        if self.is_editor:
            return
        collection = self.collection
        if operation == 'read' and collection.public_read:
            return
        if operation == 'create' and collection.public_create:
            return
        raise AccessError("You are not allowed to %s the documents of '%s'." % (operation, self.slug))

    @property
    def _documents(self):
        """``cms.document`` with the context read by payload_cms (locale, private fields...)."""
        if 'documents' not in self._cache:
            self._cache['documents'] = self._make_documents()
        return self._cache['documents']

    def _make_documents(self):
        from ..tools import localization
        settings = localization.get_settings(self.env)
        lang = self.context.get('lang') or self.env.context.get('lang') or ''
        codes = localization.locale_codes(settings)
        locale = next((c for c in (lang, lang.split('_')[0], lang.replace('_', '-')) if c in codes), None)
        return self.env['cms.document'].sudo().with_context(
            payload_editor=self.is_editor, payload_locale=localization.make_context(settings, locale),
            payload_raw_richtext=False, payload_schema_cache={})

    def _fields(self):
        """Field configs, without the private fields for the visitors."""
        if 'fields' not in self._cache:
            from ..tools.schema import data_fields
            self._cache['fields'] = [f for f in self._documents._fields_config(self.collection)
                                     if self.is_editor or not f.get('private')]
        return self._cache['fields']

    @property
    def _types(self):
        from ..tools.schema import data_fields
        return {f['name']: f['type'] for f in data_fields(self._fields())}

    @property
    def _title(self):
        return self.collection._title_field()

    # -- search ------------------------------------------------------------
    def _search(self, domain=None, offset=0, limit=None, order=None, count=False):
        self._check('read')
        Documents = self._documents
        where_sql, builder = Documents._payload_where(self.collection, domain_to_where(domain, self._title, self._types), self.draft)
        if count:
            self.env.cr.execute(SQL("SELECT count(*) FROM cms_document d WHERE %s", where_sql))
            return self.env.cr.fetchone()[0]
        query = SQL("SELECT d.id FROM cms_document d WHERE %s ORDER BY %s", where_sql,
                    builder.order_by(order_to_sort(order, self._title) or self.collection.default_sort or '-updatedAt'))
        if limit:
            query = SQL("%s LIMIT %s", query, int(limit))
        if offset:
            query = SQL("%s OFFSET %s", query, int(offset))
        self.env.cr.execute(query)
        return [row[0] for row in self.env.cr.fetchall()]

    def search(self, domain=None, offset=0, limit=None, order=None):
        """Ids of the documents matching ``domain``."""
        return self._search(domain, offset, limit, order)

    def search_count(self, domain=None, limit=None):
        return self._search(domain, count=True)

    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        return self.read(self._search(domain, offset, limit, order), fields)

    def read(self, ids=None, fields=None):
        """``fields``: list of names (``None``: every field)."""
        spec = {name: {} for name in fields} if fields else None
        return self._read(self._browse(ids), spec, web=False)

    def web_search_read(self, domain=None, specification=None, offset=0, limit=None, order=None, count_limit=None):
        """Like Odoo 17+: ``specification`` selects the fields, nested for relations
        (``{'speakers': {'fields': {'nom': {}}}}``). Returns ``{'length', 'records'}``."""
        ids = self._search(domain, offset, limit, order)
        length = len(ids) + (offset or 0) if not limit or len(ids) < limit else self.search_count(domain)
        return {'length': length, 'records': self._read(self._browse(ids), specification, web=True)}

    def web_read(self, ids=None, specification=None):
        return self._read(self._browse(ids), specification, web=True)

    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        domain = list(domain or []) + ([('display_name', operator, name)] if name else [])
        docs = self._browse(self._search(domain, limit=limit))
        return [[doc.id, doc.title or str(doc.id)] for doc in docs]

    def _browse(self, ids):
        Documents = self._documents
        if self.collection.kind == 'global':
            docs = Documents.search([('collection_id', '=', self.collection.id)], limit=1)
        else:
            if isinstance(ids, int):
                ids = [ids]
            docs = Documents.browse(ids or []).exists().filtered(lambda d: d.collection_id == self.collection)
        if not self.draft:
            docs = docs.filtered('published_data')
        self._check('read')
        return docs

    # -- read / conversion ------------------------------------------------
    def _read(self, docs, spec, web):
        fields = self._fields()
        from ..tools.schema import data_fields
        by_name = {f['name']: f for f in data_fields(fields)}
        result = []
        for doc in docs:
            data = doc._payload_serialize(draft=self.draft)
            record = {'id': doc.id}
            names = list(spec) if spec is not None else list(by_name) + ['display_name', 'create_date', 'write_date']
            for name in names:
                sub = (spec or {}).get(name) or {}
                if name == 'display_name':
                    record[name] = doc.title or False
                elif name in ('create_date', 'write_date'):
                    value = doc[name]
                    record[name] = value.strftime('%Y-%m-%d %H:%M:%S') if value else False
                elif name == 'status':
                    record[name] = data.get('_status') or 'published'
                elif name in by_name:
                    record[name] = self._value(by_name[name], data.get(name), sub, web)
                elif name in ('url', 'filename', 'mimeType', 'filesize', 'width', 'height', 'sizes', 'alt') and name in data:
                    record[name] = _media_value(name, data[name])
            result.append(record)
        return result

    def _value(self, field, value, sub, web):
        ftype = field['type']
        many = field.get('hasMany')
        if ftype in ('relationship', 'upload'):
            if value in (None, False, []):
                return [] if many else False
            ids = [v.get('id') if isinstance(v, dict) else v for v in (value if isinstance(value, list) else [value])]
            related = self._related(field['relationTo'])
            docs = related._browse(ids) if related else None
            if sub.get('fields') and related:
                rows = related._read(docs, sub['fields'], web)
            elif ftype == 'upload':
                rows = [(doc.id, doc._payload_serialize(draft=related.draft).get('url')) for doc in docs] if docs else []
                rows = [url for _id, url in rows]
            elif many:
                return [d.id for d in docs] if docs is not None else ids
            elif docs:
                rows = [{'id': d.id, 'display_name': d.title or False} if web else [d.id, d.title or False] for d in docs]
            else:
                rows = [{'id': ids[0], 'display_name': False} if web else [ids[0], False]]
            return rows if many else (rows[0] if rows else False)
        if value is None or value == '':
            return [] if many or ftype in ('array', 'blocks') else False
        if ftype == 'date':
            day = ((field.get('admin') or {}).get('date') or {}).get('pickerAppearance') == 'dayOnly'
            return value[:10] if day else value[:19].replace('T', ' ')
        if ftype == 'group':
            return self._rows(field.get('fields') or [], [value], sub, web)[0]
        if ftype == 'array':
            return self._rows(field.get('fields') or [], value, sub, web)
        if ftype == 'blocks':
            blocks = {b['slug']: b.get('fields') or [] for b in field.get('blocks') or []}
            return [dict(self._rows(blocks.get(row.get('blockType')) or [], [row], sub, web)[0], blockType=row.get('blockType'))
                    for row in value if isinstance(row, dict)]
        return value

    def _rows(self, fields, rows, sub, web):
        from ..tools.schema import data_fields
        by_name = {f['name']: f for f in data_fields(fields)}
        spec = sub.get('fields')
        result = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            names = list(spec) if spec else list(by_name)  # every field, False when empty (like Odoo)
            item = {'id': row['id']} if 'id' in row else {}
            for name in names:
                if name in by_name:
                    item[name] = self._value(by_name[name], row.get(name), (spec or {}).get(name) or {}, web)
            result.append(item)
        return result

    def _related(self, slug):
        """Model of a related collection, or None when the user cannot read it."""
        models = self._cache.setdefault('related', {})
        if slug in models:
            return models[slug]
        model = models[slug] = Model(self.env, slug, su=self.su, context=self.context)
        try:
            model._check('read')
        except AccessError:
            models[slug] = None
        return models[slug]

    # -- write ---------------------------------------------------------------
    def _vals(self, vals, docs=None):
        """Odoo values (x2many commands, dates...) -> Payload data."""
        from ..tools.schema import data_fields
        fields = {f['name']: f for f in data_fields(self._fields())}
        data = {}
        for name, value in (vals or {}).items():
            field = fields.get(name)
            if not field:
                raise ValidationError("Invalid field '%s' on '%s'." % (name, self.slug))
            ftype = field['type']
            if ftype in ('relationship', 'upload') and field.get('hasMany'):
                current = (docs[:1].data or {}).get(name) if docs else []
                value = _x2many(value, current or [])
            elif ftype in ('relationship', 'upload'):
                value = value[0] if isinstance(value, (list, tuple)) and value else (value or None)
            elif ftype == 'date' and isinstance(value, str):
                if DATE_RE.match(value):
                    value = '%sT12:00:00.000Z' % value
                elif DATETIME_RE.match(value):
                    value = value.replace(' ', 'T')[:19] + '.000Z'
            elif value is False and ftype != 'checkbox':
                value = None
            data[name] = value
        if self.collection.drafts:
            data['_status'] = 'published'
        return data

    def create(self, vals_list):
        """Creates one document (dict) or several (list of dicts); returns the id(s)."""
        from ..models.cms_document import PayloadValidationError
        self._check('create')
        single = isinstance(vals_list, dict)
        ids = []
        for vals in [vals_list] if single else vals_list:
            try:
                ids.append(self._documents._payload_create(self.collection, self._vals(vals)).id)
            except PayloadValidationError as e:
                raise ValidationError(_errors(e)) from e
        return ids[0] if single else ids

    def write(self, ids, vals):
        from ..models.cms_document import PayloadValidationError
        self._check('write')
        for doc in self._browse_all(ids):
            try:
                doc._payload_update(self._vals(vals, doc))
            except PayloadValidationError as e:
                raise ValidationError(_errors(e)) from e
        return True

    def unlink(self, ids):
        self._check('unlink')
        self._browse_all(ids)._payload_delete()
        return True

    def _browse_all(self, ids):
        if isinstance(ids, int):
            ids = [ids]
        docs = self._documents.browse(ids or []).exists()
        return docs.filtered(lambda d: d.collection_id == self.collection)

    # -- description -----------------------------------------------------
    def fields_get(self, allfields=None, attributes=None):
        from ..tools.schema import data_fields
        result = {}
        for field in data_fields(self._fields()):
            if field.get('private') and not self.is_editor:
                continue
            ftype = field['type']
            info = {
                'type': _odoo_type(field),
                'string': field.get('label') or field['name'],
                'required': bool(field.get('required')),
                'readonly': bool((field.get('admin') or {}).get('readOnly')),
                'help': (field.get('admin') or {}).get('description') or False,
            }
            if ftype in ('relationship', 'upload'):
                info['relation'] = field['relationTo']
            if ftype in ('select', 'radio'):
                info['selection'] = [[o['value'], o.get('label') or o['value']] for o in field.get('options') or []]
            if field.get('localized'):
                info['translate'] = True
            result[field['name']] = info
        result['display_name'] = {'type': 'char', 'string': 'Display Name', 'required': False, 'readonly': True}
        if allfields:
            result = {k: v for k, v in result.items() if k in allfields}
        if attributes:
            result = {k: {a: v[a] for a in attributes if a in v} for k, v in result.items()}
        return result

    # -- methods of the collection class (@expose) ---------------------------
    def _code_class(self):
        from .collection import registered
        return next((c for c in registered() if c._name == self.slug and c._kind == self.collection.kind), None)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        func = getattr(self._code_class(), name, None)
        if not callable(func) or isinstance(func, (classmethod, staticmethod)):
            raise AttributeError("'%s' has no method '%s'" % (self.slug, name))
        return functools.partial(func, self)

    def call(self, method, args=None, kwargs=None):
        """JSON-RPC entry point (``/payload/dataset/call_kw``)."""
        args, kwargs = list(args or []), dict(kwargs or {})
        context = kwargs.pop('context', None) or {}
        model = self.with_context(**context) if context else self
        if method in READ_METHODS | WRITE_METHODS:
            return getattr(model, method)(*args, **kwargs)
        func = getattr(model._code_class(), method, None)
        auth = getattr(func, '_payload_expose', None)
        if not auth:
            raise AccessError("Method '%s' of '%s' is not exposed." % (method, self.slug))
        if auth != 'public' and not model.is_editor:
            raise AccessError("Method '%s' of '%s' is reserved to the CMS editors." % (method, self.slug))
        return func(model, *args, **kwargs)


def _x2many(value, current):
    """Odoo x2many commands (or a plain list of ids) -> list of ids."""
    ids = [v if isinstance(v, int) else (v or {}).get('id') for v in current]
    if not isinstance(value, (list, tuple)):
        return [value] if value else []
    if all(isinstance(v, int) for v in value):
        return list(value)
    for command in value:
        code = command[0]
        if code == 6:
            ids = list(command[2])
        elif code == 4 and command[1] not in ids:
            ids.append(command[1])
        elif code in (2, 3):
            ids = [i for i in ids if i != command[1]]
        elif code == 5:
            ids = []
    return ids


def _odoo_type(field):
    ftype = field['type']
    if ftype in ('relationship', 'upload'):
        if ftype == 'upload':
            return 'image' if not field.get('hasMany') else 'many2many'
        return 'many2many' if field.get('hasMany') else 'many2one'
    if ftype == 'date':
        day = ((field.get('admin') or {}).get('date') or {}).get('pickerAppearance') == 'dayOnly'
        return 'date' if day else 'datetime'
    return {
        'text': 'char', 'email': 'char', 'slug': 'char', 'textarea': 'text', 'code': 'text', 'richText': 'html',
        'number': 'float', 'checkbox': 'boolean', 'select': 'selection', 'radio': 'selection',
    }.get(ftype, 'json')


def _media_value(name, value):
    if name == 'sizes' and isinstance(value, dict):
        return {k: v.get('url') for k, v in value.items() if v.get('url')}
    return value if value is not None else False


def _errors(error):
    return '\n'.join('%s: %s' % (e.get('label') or e.get('path'), e.get('message')) for e in error.errors) or error.message
