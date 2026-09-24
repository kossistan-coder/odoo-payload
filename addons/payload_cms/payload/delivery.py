# -*- coding: utf-8 -*-
"""Delivery API: the content of the collections for the frontends (sites, apps).

``Model`` (Odoo shapes, JSON-RPC) is the API of edition; ``Delivery`` is the
read-only format given to the frontends: generic, simple and multilingual::

    from odoo.addons.payload_cms.payload import Delivery

    Delivery(request.env, depth=2).document('pages', 'home')         # the page, relations populated
    Delivery(request.env, depth=1).documents('events', [('active', '=', True)], order='date_sortie desc')

A document::

    {"id": 1, "type": "page",
     "attributes": {"title": {"fr": "Accueil", "en": "Home"}, "slug": {"fr": "home", "en": null}},
     "seo": {"title": {...}, "description": {...}, "image": null},
     "blocks": [{"id": "abc", "type": "episodesList",
                 "config": {"mode": "manual", "limit": 3},
                 "content": {"title": {...}, "image": "https://…/api/media/file/cover.jpg", "events": [{"id": 62, "type": "event", "attributes": {...}}]}}],
     "meta": {"locale": "all", "availableLocales": ["fr", "en"], "status": "published",
              "publishedAt": null, "createdAt": "...", "updatedAt": "..."}}

Rules:

- keys in camelCase (``api_name=`` on a field renames it), types in camelCase
  singular (``pages`` -> ``page``, block ``live-hero`` -> ``liveHero``); ids are numbers, no key is a number;
- a missing value is ``null`` (a list is ``[]``);
- an image / file is its absolute URL;
- relations are populated: the related documents themselves, complete, down to
  ``depth`` levels (max 3); deeper (and with ``depth=0``) a related document is a
  summary ``{id, type, displayName}`` — never a bare id. Relations to collections
  the reader cannot see are not exposed;
- localized fields are always ``{locale: value}``: every available locale with
  ``locale='all'`` (``null`` when not translated), only the requested one (with
  the fallback locale) otherwise;
- a group named ``meta`` / ``seo`` becomes ``seo``, the blocks field of the
  collection ``blocks``, a ``publishedAt`` field goes to ``meta``;
- a block is ``{id, type, config, content}``: select, radio, checkbox and number
  fields are ``config``, the others ``content`` (``role=`` on a field changes it);
  a code-first block can compute the records it shows (automatic mode) with
  ``_delivery_sources`` — see ``payload_cms.payload.Block``.
"""
import re

from ..tools import localization, schema
from .model import Model

META_GROUPS = ('meta', 'seo')
PUBLISHED_FIELDS = ('publishedAt', 'published_at')
CONFIG_TYPES = ('select', 'radio', 'checkbox', 'number')
MAX_DEPTH = 3


def camel(name):
    """``date_sortie`` / ``live-hero`` / ``heroImage`` -> ``dateSortie`` / ``liveHero`` / ``heroImage``."""
    parts = [p for p in re.split(r'[-_\s]+', name or '') if p]
    if not parts:
        return name
    return parts[0][:1].lower() + parts[0][1:] + ''.join(p[:1].upper() + p[1:] for p in parts[1:])


def singular(name):
    if name.endswith('ies') and len(name) > 3:
        return name[:-3] + 'y'
    if name.endswith('sses'):
        return name[:-2]
    if name.endswith('s') and not name.endswith('ss') and len(name) > 1:
        return name[:-1]
    return name


def type_of(slug):
    return camel(singular(slug))


def _day_only(field):
    return ((field.get('admin') or {}).get('date') or {}).get('pickerAppearance') == 'dayOnly'


class Delivery:
    """Reads published documents in the Delivery format (see the module docstring)."""

    def __init__(self, env, locale='all', depth=0, draft=False):
        self.env = env
        self.draft = bool(draft)
        self.depth = max(0, min(MAX_DEPTH, int(depth or 0)))
        settings = localization.get_settings(env)
        self.codes = localization.locale_codes(settings)
        self.default = settings.get('defaultLocale') if self.codes else None
        self.fallback = settings.get('fallback', True)
        self.locale = locale if locale in self.codes else ('all' if self.codes else None)
        self.base_url = (env['ir.config_parameter'].sudo().get_param('web.base.url') or '').rstrip('/')
        self.models = {}
        self.cache = {}      # (slug, id, level) -> converted document
        self.urls = {}       # media id -> URL

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def document(self, slug, key, domain=None):
        """``{data, meta}`` of one document: ``key`` = id, or value of the ``slug``
        field (``domain`` replaces the lookup), or None when not found."""
        model = self._model(slug)
        if model is None:
            return None
        if domain is None:
            domain = [('id', '=', int(key))] if str(key).isdigit() else [('slug', '=', key)]
        docs = model._browse(model.search(domain, limit=1))
        if not docs:
            return None
        return {'data': self._convert(model, docs[0], top=True), 'meta': self._meta()}

    def documents(self, slug, domain=None, order=None, limit=None, offset=0):
        """``{data: [...], meta: {total, limit, offset...}}``."""
        model = self._model(slug)
        if model is None:
            return {'data': [], 'meta': dict(self._meta(), total=0, limit=limit, offset=offset or 0)}
        ids = model.search(domain or [], offset=offset, limit=limit, order=order)
        total = model.search_count(domain or []) if limit else len(ids) + (offset or 0)
        data = [self._convert(model, doc, top=True) for doc in model._browse(ids)]
        return {'data': data, 'meta': dict(self._meta(), total=total, limit=limit, offset=offset or 0)}

    # ------------------------------------------------------------------
    def _model(self, slug):
        if slug not in self.models:
            try:
                model = Model(self.env, slug).with_context(draft=self.draft)
                model._check('read')
            except Exception:  # noqa: BLE001 - unknown or not readable: never exposed
                model = None
            self.models[slug] = model
        return self.models[slug]

    def _meta(self):
        return {'locale': self.locale, 'availableLocales': list(self.codes), 'defaultLocale': self.default,
                'depth': self.depth}

    @staticmethod
    def _iso(value):
        return value.strftime('%Y-%m-%dT%H:%M:%SZ') if value else None

    def _url(self, url):
        return (self.base_url + url) if url and url.startswith('/') else url

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------
    def _convert(self, model, doc, top=False, level=0):
        key = (model.slug, doc.id, level)
        if key in self.cache:
            return self.cache[key]
        collection = model.collection
        fields = model._fields()
        source = (doc.data if self.draft else doc.published_data) or {}
        result = {'id': doc.id, 'type': type_of(model.slug), 'attributes': {}}
        blocks_fields = [f for f in schema.data_fields(fields) if f['type'] == 'blocks']
        meta = {}
        for field in schema.data_fields(fields):
            name = field['name']
            value = source.get(name)
            if field['type'] == 'group' and name in META_GROUPS:
                result['seo'] = self._object(field.get('fields') or [], value if isinstance(value, dict) else {}, level)
            elif field['type'] == 'blocks' and len(blocks_fields) == 1:
                result['blocks'] = self._blocks(field, value, level)
            elif name in PUBLISHED_FIELDS:
                meta['publishedAt'] = self._scalar(field, value)
            else:
                entry, converted = self._entry(field, value, level)
                if entry:
                    result['attributes'][entry] = converted
        if collection.upload:
            result['attributes']['url'] = self._url(doc._payload_serialize(draft=self.draft).get('url'))
        if top:
            if collection.drafts:
                meta['status'] = 'published' if not self.draft else (doc.status or 'draft')
            meta.update(createdAt=self._iso(doc.create_date), updatedAt=self._iso(doc.write_date))
            meta = dict({'locale': self.locale, 'availableLocales': list(self.codes)}, **meta)
        if meta:
            result['meta'] = meta
        self.cache[key] = result
        return result

    def _object(self, fields, data, level):
        result = {}
        for field in schema.data_fields(fields):
            entry, value = self._entry(field, (data or {}).get(field['name']), level)
            if entry:
                result[entry] = value
        return result

    def _key(self, field, populated=True):
        return field.get('apiName') or camel(field['name'])

    def _entry(self, field, value, level):
        """(key, value) of a field, or (None, None) when it is not exposed."""
        if field['type'] in ('relationship', 'upload') and self._model(field['relationTo']) is None:
            return None, None  # relation to a collection the reader cannot see (e.g. participants)
        key = self._key(field)
        if field.get('localized') and self.codes:
            return key, self._localized(field, value, level)
        return key, self._value(field, value, level)

    def _localized(self, field, value, level):
        stored = value if schema.is_locale_dict(value, self.codes) else ({self.default: value} if value not in (None, '') else {})
        codes = self.codes if self.locale == 'all' else [self.locale]
        result = {}
        for code in codes:
            item = stored.get(code)
            if self.locale != 'all' and item in (None, '', []) and self.fallback:
                item = stored.get(self.default)
            result[code] = self._value(field, item, level)
        return result

    @staticmethod
    def _ids(value):
        values = value if isinstance(value, list) else ([] if value in (None, '', False) else [value])
        ids = []
        for v in values:
            v = v.get('id') if isinstance(v, dict) else v
            if str(v).isdigit():
                ids.append(int(v))
        return ids

    def _related(self, slug, ids, level):
        """Documents of ``ids`` (published and readable, in this order): complete when
        ``level`` <= ``depth``, else a summary ``{id, type, displayName}`` (no loops)."""
        model = self._model(slug)
        if model is None or not ids:
            return []
        docs = model._browse(ids)
        if level > self.depth:
            return [{'id': doc.id, 'type': type_of(slug), 'displayName': doc.title or None} for doc in docs]
        return [self._convert(model, doc, level=level) for doc in docs]

    def _media_urls(self, slug, ids):
        model = self._model(slug)
        if model is None:
            return []
        missing = [i for i in ids if i not in self.urls]
        for doc in model._browse(missing):
            self.urls[doc.id] = self._url(doc._payload_serialize(draft=self.draft).get('url'))
        return [self.urls[i] for i in ids if self.urls.get(i)]

    def _value(self, field, value, level):
        ftype = field['type']
        many = field.get('hasMany')
        if ftype == 'upload':
            urls = self._media_urls(field['relationTo'], self._ids(value))
            return urls if many else (urls[0] if urls else None)
        if ftype == 'relationship':
            docs = self._related(field['relationTo'], self._ids(value), level + 1)
            return docs if many else (docs[0] if docs else None)
        if ftype == 'group':
            return self._object(field.get('fields') or [], value if isinstance(value, dict) else {}, level)
        if ftype == 'array':
            rows = []
            for row in value if isinstance(value, list) else []:
                if isinstance(row, dict):
                    rows.append(dict({'id': row.get('id')}, **self._object(field.get('fields') or [], row, level)))
            return rows
        if ftype == 'blocks':
            return self._blocks(field, value, level)
        if value is None or value == '' or (value == [] and not many):
            return [] if many else None
        if ftype == 'richText':
            from ..tools.lexical_html import is_lexical, lexical_to_html
            return lexical_to_html(value) if is_lexical(value) else value
        return self._scalar(field, value)

    def _scalar(self, field, value):
        if value in (None, ''):
            return None
        if field['type'] == 'date' and isinstance(value, str):
            return value[:10] if _day_only(field) else value[:19] + 'Z'
        if field['type'] == 'checkbox':
            return bool(value)
        return value

    # ------------------------------------------------------------------
    # Blocks
    # ------------------------------------------------------------------
    def _blocks(self, field, rows, level):
        definitions = {b['slug']: b for b in field.get('blocks') or []}
        result = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict) or row.get('blockType') not in definitions:
                continue
            block_type = row['blockType']
            config, content = {}, {}
            fields = definitions[block_type].get('fields') or []
            for sub in schema.data_fields(fields):
                key, value = self._entry(sub, row.get(sub['name']), level)
                if not key:
                    continue
                role = sub.get('role') or ('config' if sub['type'] in CONFIG_TYPES else 'content')
                (config if role == 'config' else content)[key] = value
            self._apply_sources(block_type, row, fields, config, content, level)
            result.append({'id': row.get('id'), 'type': camel(block_type), 'config': config, 'content': content})
        return result

    def _apply_sources(self, block_type, row, fields, config, content, level):
        """Records computed by the block (automatic mode): ``Block._delivery_sources``."""
        from .collection import registered_blocks
        cls = next((b for b in registered_blocks() if b._name == block_type), None)
        if cls is None or not hasattr(cls, '_delivery_sources'):
            return
        by_name = {f['name']: f for f in schema.data_fields(fields)}
        for source in cls._delivery_sources(row, self.env) or []:
            field = by_name.get(source['field'])
            model = self._model(source['collection'])
            if not field or model is None:
                continue
            if 'ids' in source:
                ids = [int(i) for i in source['ids']]
            else:
                ids = model.search(source.get('domain') or [], order=source.get('order'), limit=source.get('limit'))
            ids = [d.id for d in model._browse(ids)]  # published and readable only
            key, value = self._entry(field, ids if field.get('hasMany') else (ids[0] if ids else None), level)
            content[key] = value
            if 'ids' not in source:
                config['source'] = {
                    'collection': type_of(source['collection']),
                    'filter': self._api_domain(model, source.get('domain') or []),
                    'sort': self._api_order(model, source.get('order')),
                    'limit': source.get('limit'),
                }

    def _api_names(self, model):
        return {f['name']: f.get('apiName') or camel(f['name']) for f in schema.data_fields(model._fields())}

    def _api_domain(self, model, domain):
        names = self._api_names(model)
        return [[names.get(t[0], camel(t[0])), t[1], t[2]] if isinstance(t, (list, tuple)) else t for t in domain]

    def _api_order(self, model, order):
        names = self._api_names(model)
        parts = []
        for part in (order or '').split(','):
            words = part.split()
            if words:
                parts.append(' '.join([names.get(words[0], camel(words[0]))] + words[1:]))
        return ', '.join(parts) or None
