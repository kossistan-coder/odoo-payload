# -*- coding: utf-8 -*-
"""Payload-compatible REST API.

Implements the routes documented at https://payloadcms.com/docs/rest-api/overview
on top of Odoo: collections, globals, versions, uploads and auth.
"""
import datetime
import hashlib
import json
import logging
import re

from werkzeug.exceptions import NotFound

from odoo import SUPERUSER_ID, http
from odoo.exceptions import AccessDenied, AccessError, UserError
from odoo.http import Stream, request
from odoo.tools import SQL

from ..models.cms_document import PayloadValidationError, _iso
from ..tools import api_docs, import_export, localization, multitenancy, schema, schema_admin, storage, translate
from ..tools.query import QueryError, parse_bracket_params
from .utils import cors_headers, decode_jwt, encode_jwt, error_response, json_response

_logger = logging.getLogger(__name__)

EDITOR_GROUP = 'payload_cms.group_payload_cms_user'
ADMIN_GROUP = 'payload_cms.group_payload_cms_admin'
MAX_DEPTH = 10


class Forbidden(Exception):
    pass


class Unauthorized(Exception):
    pass


class PayloadRequest:
    """Per-request state: authenticated user, query params, population cache."""

    def __init__(self):
        self.user = None
        self.strategy = None
        self.token_payload = None
        self._authenticate()
        pairs = list(request.httprequest.args.items(multi=True))
        self.query = parse_bracket_params(pairs)
        self.schema_cache = {}
        self.populate_cache = {}
        self.collections = {}

    # ------------------------------------------------------------------
    def _authenticate(self):
        env = request.env
        header = request.httprequest.headers.get('Authorization', '') or ''
        uid = None
        if header[:4] == 'JWT ' or header[:7] == 'Bearer ':
            decoded = decode_jwt(env, header.split(' ', 1)[1].strip())
            if decoded:
                uid, self.token_payload = decoded
                self.strategy = 'local-jwt'
        elif 'API-Key ' in header:
            key = header.split('API-Key ', 1)[1].strip()
            try:
                uid = env['res.users.apikeys'].sudo()._check_credentials(scope='rpc', key=key) or None
            except Exception:  # noqa: BLE001
                uid = None
            self.strategy = 'api-key' if uid else None
        elif request.session.uid:
            uid = request.session.uid
            self.strategy = 'session'
        if uid:
            user = env['res.users'].sudo().browse(uid).exists()
            if user and user.active:
                self.user = user
                if request.env.uid != uid:
                    request.update_env(user=uid)

    @property
    def is_editor(self):
        return bool(self.user) and self.user.has_group(EDITOR_GROUP)

    @property
    def is_admin(self):
        return bool(self.user) and self.user.has_group(ADMIN_GROUP)

    def require_editor(self):
        if not self.user:
            raise Unauthorized()
        if not self.is_editor:
            raise Forbidden()

    def check_csrf(self):
        """Cookie-authenticated writes must come from an allowed origin."""
        if self.strategy != 'session' or request.httprequest.method in ('GET', 'HEAD', 'OPTIONS'):
            return
        origin = request.httprequest.headers.get('Origin') or request.httprequest.headers.get('Referer')
        if not origin:
            return
        host = request.httprequest.host_url.rstrip('/')
        if origin.rstrip('/').startswith(host):
            return
        allowed = [h for h, _v in cors_headers() if h == 'Access-Control-Allow-Credentials']
        if not allowed:
            raise Forbidden()

    # ------------------------------------------------------------------
    @property
    def localization(self):
        if not hasattr(self, '_localization'):
            self._localization = localization.get_settings(request.env)
        return self._localization

    def locale(self):
        """Locale context from ``?locale=`` / ``?fallback-locale=`` (None when disabled)."""
        return localization.make_context(self.localization, self.query.get('locale'),
                                         self.query.get('fallback-locale') or self.query.get('fallbackLocale'))

    def raw_rich_text(self):
        """Rich text is returned as HTML, unless the admin UI or
        ``?richText=lexical`` asks for the editor state."""
        return (self.is_editor and self.flag('_admin')) or self.query.get('richText') in ('lexical', 'json')

    @property
    def multitenancy(self):
        if not hasattr(self, '_multitenancy'):
            self._multitenancy = multitenancy.get_settings(request.env)
        return self._multitenancy

    def tenant_scope(self):
        """Current site: ``{id, allowed}`` (None when multi-tenancy is off).

        The site comes from the ``X-Payload-Tenant`` header / ``?tenant=`` (ID or
        slug; empty or ``all`` = every site) or from the request host.
        ``allowed`` lists the sites of a restricted editor (None = all)."""
        if hasattr(self, '_tenant_scope'):
            return self._tenant_scope
        scope = None
        if self.multitenancy.get('enabled'):
            env = request.env
            value = request.httprequest.headers.get(multitenancy.HEADER)
            if value is None:
                value = self.query.get('tenant')
            tenant = env['cms.document']
            if value not in (None, '', 'all'):
                tenant = multitenancy.find_tenant(env, value)
                if not tenant:
                    self._tenant_scope = None
                    raise NotFound()
            elif value is None and self.multitenancy.get('resolveByHost', True):
                tenant = multitenancy.resolve_host(env, request.httprequest.host)
            allowed = None
            if self.user and self.is_editor and not self.is_admin and self.user.payload_tenant_ids:
                allowed = self.user.payload_tenant_ids.ids
            if tenant:
                if allowed is not None and tenant.id not in allowed:
                    raise Forbidden()
                if not self.is_editor and not multitenancy.is_active(tenant):
                    raise NotFound()
            scope = {'id': tenant.id if tenant else None, 'allowed': allowed}
        self._tenant_scope = scope
        return scope

    @property
    def env(self):
        return request.env(context=dict(request.env.context, payload_schema_cache=self.schema_cache,
                                        payload_admin=self.is_editor and self.flag('_admin'),
                                        payload_editor=self.is_editor,
                                        payload_locale=self.locale(),
                                        payload_raw_richtext=self.raw_rich_text(),
                                        payload_tenant=self.tenant_scope(),
                                        payload_mt_enabled=bool(self.multitenancy.get('enabled'))))

    def flag(self, name, default=False):
        value = self.query.get(name)
        if value is None:
            return default
        return str(value).lower() in ('1', 'true', 'yes')

    def depth(self, default=2):
        try:
            return max(0, min(MAX_DEPTH, int(self.query.get('depth', default))))
        except (TypeError, ValueError):
            return default

    def draft(self):
        """Drafts are only visible to editors asking for them."""
        return self.is_editor and self.flag('draft')

    def collection(self, slug, kind='collection', action='read'):
        key = (slug, kind)
        if key not in self.collections:
            record = request.env['cms.collection'].sudo().search(
                [('slug', '=', slug), ('kind', '=', kind)], limit=1)
            self.collections[key] = record
        record = self.collections[key]
        if not record:
            raise NotFound()
        public = record.public_create if action == 'create' else record.public_read
        if not self.is_editor and not public:
            if not self.user:
                raise Unauthorized()
            raise Forbidden()
        return record

    def body(self):
        """JSON body, or multipart form with `_payload` + `file` (Payload uploads)."""
        httpreq = request.httprequest
        content_type = httpreq.mimetype or ''
        upload = None
        if content_type.startswith('multipart/form-data'):
            form = httpreq.form
            data = {}
            if form.get('_payload'):
                data = json.loads(form['_payload'])
            for key, value in form.items():
                if key != '_payload':
                    data.setdefault(key, value)
            file = httpreq.files.get('file')
            if file and file.filename:
                upload = (file.filename, file.read(), file.mimetype)
            return data, upload
        raw = httpreq.get_data(cache=True, as_text=True)
        if not raw:
            return {}, None
        try:
            data = json.loads(raw)
        except ValueError:
            raise UserError('Invalid JSON body')
        if not isinstance(data, dict):
            raise UserError('Invalid JSON body')
        return data, None

    # ------------------------------------------------------------------
    def populate(self, draft):
        """Return a callback used to populate relationships at a given depth."""
        def _populate(slug, value, depth):
            if isinstance(value, dict):
                value = value.get('id', value.get('value'))
            if not isinstance(value, int):
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    return value
            if depth < 0:
                return value
            key = (slug, value, depth, draft)
            if key in self.populate_cache:
                return self.populate_cache[key]
            try:
                collection = self.collection(slug)
            except (NotFound, Forbidden, Unauthorized):
                return value
            doc = self.env['cms.document'].sudo().browse(value).exists()
            # Missing or unpublished relations are returned as their raw id, like Payload.
            if not doc or doc.collection_id != collection or (not draft and not doc.published_data):
                return value
            self.populate_cache[key] = value  # recursion guard
            result = doc._payload_serialize(draft=draft, depth=depth, populate=_populate)
            self.populate_cache[key] = result
            return result
        return _populate

    def serialize(self, doc, draft, depth):
        """``depth`` = number of relationship levels populated (Payload semantics)."""
        return doc._payload_serialize(draft=draft, depth=depth, populate=self.populate(draft) if depth else None)


def _tenant_ids_of(values):
    ids = []
    for value in values or []:
        if isinstance(value, dict):
            value = value.get('id', value.get('value'))
        if str(value).isdigit():
            ids.append(int(value))
    tenants = request.env['cms.collection']._get_by_slug(multitenancy.TENANTS)
    return request.env['cms.document'].sudo().search([('id', 'in', ids), ('collection_id', '=', tenants.id)]).ids if tenants else []


def _user_doc(user):
    return {
        'id': user.id,
        'email': user.login,
        'name': user.name,
        'roles': ['admin'] if user.has_group(ADMIN_GROUP) else ['editor'],
        'tenants': user.payload_tenant_ids.ids,
        'updatedAt': _iso(user.write_date),
        'createdAt': _iso(user.create_date),
        'collection': 'users',
    }


class PayloadApi(http.Controller):

    @staticmethod
    def _tenant_ids(values):
        return _tenant_ids_of(values)

    @http.route(['/api', '/api/<path:path>'], type='http', auth='public', csrf=False, save_session=True,
                methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE', 'OPTIONS'])
    def payload_api(self, path='', **_kw):
        method = request.httprequest.method
        if method == 'OPTIONS':
            return request.make_response('', headers=cors_headers(), status=204)
        override = request.httprequest.headers.get('X-Payload-HTTP-Method-Override')
        if method == 'POST' and override in ('GET', 'PATCH', 'DELETE'):
            method = override
        try:
            req = PayloadRequest()
            req.check_csrf()
            segments = [s for s in path.split('/') if s]
            return self._route(req, method, segments)
        except PayloadValidationError as e:
            request.env.cr.rollback()
            return json_response({'errors': [{
                'name': 'ValidationError',
                'message': e.message,
                'data': {'collection': e.collection, 'errors': e.errors},
            }]}, status=400)
        except QueryError as e:
            request.env.cr.rollback()
            return error_response(str(e), 400)
        except Unauthorized:
            request.env.cr.rollback()
            return error_response('You are not allowed to perform this action.', 401)
        except (Forbidden, AccessError):
            request.env.cr.rollback()
            return error_response('You are not allowed to perform this action.', 403)
        except NotFound:
            request.env.cr.rollback()
            return error_response('Not Found', 404)
        except UserError as e:
            request.env.cr.rollback()
            return error_response(str(e), 400)
        except Exception as e:  # noqa: BLE001
            _logger.exception("Payload API error on %s /api/%s", method, path)
            request.env.cr.rollback()
            return error_response('Something went wrong.', 500, {'detail': str(e)})

    # ------------------------------------------------------------------
    def _route(self, req, method, seg):
        if not seg:
            return json_response({'message': 'Payload CMS for Odoo', 'docs': 'https://payloadcms.com/docs/rest-api/overview'})
        head = seg[0]
        if head == '_admin':
            return self._admin(req, method, seg[1:])
        if head == 'access' and method == 'GET':
            return self._access(req)
        if head == 'users':
            return self._users(req, method, seg[1:])
        rest = seg[1:]
        # /api is the internal API of the admin: the public API of a site is written
        # by its module (routes / JSON-RPC, see payload_cms.payload.Model). Only the
        # files of the upload collections stay public (images of the site).
        if not req.is_editor and not (len(rest) == 2 and rest[0] == 'file' and method in ('GET', 'HEAD')):
            raise Forbidden() if req.user else Unauthorized()
        if head == 'globals' and len(seg) >= 2:
            return self._global(req, method, seg[1], seg[2:])
        public_create = not rest and method == 'POST' and not request.httprequest.headers.get('X-Payload-HTTP-Method-Override')
        collection = req.collection(head, action='create' if public_create else 'read')
        if not rest:
            if method == 'GET':
                return self._find(req, collection)
            if method == 'POST':
                return self._create(req, collection)
            if method in ('PATCH', 'PUT'):
                return self._bulk_update(req, collection)
            if method == 'DELETE':
                return self._bulk_delete(req, collection)
        elif rest[0] == 'count' and method == 'GET':
            return self._count(req, collection)
        elif rest == ['aggregate'] and method == 'GET':
            return self._aggregate(req, collection)
        elif rest == ['export'] and method == 'GET':
            return self._export(req, collection)
        elif rest == ['import'] and method == 'POST':
            return self._import(req, collection)
        elif rest == ['import', 'template'] and method == 'GET':
            return self._import_template(req, collection)
        elif rest[0] == 'versions':
            return self._versions(req, method, collection, rest[1:])
        elif rest[0] == 'file' and len(rest) == 2 and method == 'GET':
            return self._file(req, collection, rest[1])
        elif rest[0].isdigit():
            doc = self._get_doc(req, collection, int(rest[0]))
            if len(rest) == 1:
                if method == 'GET':
                    return self._find_by_id(req, collection, doc)
                if method in ('PATCH', 'PUT'):
                    return self._update(req, collection, doc)
                if method == 'DELETE':
                    return self._delete(req, collection, doc)
            elif rest[1] == 'translate' and method == 'POST':
                return self._translate(req, collection, doc)
            elif rest[1] == 'duplicate' and method == 'POST':
                req.require_editor()
                copy = doc._payload_duplicate()
                return json_response({'doc': req.serialize(copy, True, 0), 'message': 'Successfully duplicated.'}, 201)
        raise NotFound()

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------
    def _get_doc(self, req, collection, doc_id):
        doc = req.env['cms.document'].sudo().browse(doc_id).exists()
        if not doc or doc.collection_id != collection or not doc._payload_tenant_visible():
            raise NotFound()
        return doc

    def _find(self, req, collection):
        draft = req.draft()
        docs, meta = req.env['cms.document'].sudo()._payload_search(
            collection,
            where=req.query.get('where'),
            sort=req.query.get('sort'),
            limit=req.query.get('limit', collection.default_limit or 10),
            page=req.query.get('page', 1),
            draft=draft,
            pagination=req.query.get('pagination', 'true') != 'false',
        )
        depth = req.depth()
        result = {'docs': [req.serialize(doc, draft, depth) for doc in docs]}
        result.update(meta)
        return json_response(result)

    def _count(self, req, collection):
        _docs, meta = req.env['cms.document'].sudo()._payload_search(
            collection, where=req.query.get('where'), limit=1, draft=req.draft())
        return json_response({'totalDocs': meta['totalDocs']})

    def _find_by_id(self, req, collection, doc):
        merged = self._live_preview_merge(req, collection, doc)
        if merged is not None:
            return json_response(merged)
        draft = req.draft()
        if not draft and not doc.published_data:
            raise NotFound()
        return json_response(req.serialize(doc, draft, req.depth()))

    def _live_preview_merge(self, req, collection, doc):
        """`@payloadcms/live-preview` mergeData request: POST + `X-Payload-HTTP-Method-Override: GET`
        with `{data, depth}` in the body. Returns the given data populated like a findByID."""
        if request.httprequest.method != 'POST':
            return None
        body, _upload = req.body()
        if not isinstance(body.get('data'), dict):
            return None
        if doc and not req.is_editor and not doc.published_data:
            raise NotFound()
        try:
            depth = max(0, min(MAX_DEPTH, int(body.get('depth', 2))))
        except (TypeError, ValueError):
            depth = 2
        fields_conf = req.env['cms.document']._fields_config(collection)
        data = dict(body['data'])
        base = doc._payload_serialize(draft=True) if doc else {}
        for key in ('id', 'createdAt', 'updatedAt', '_status', 'url', 'thumbnailURL', 'filename', 'mimeType',
                    'filesize', 'width', 'height', 'focalX', 'focalY', 'sizes', 'globalType'):
            if key in base and key not in data:
                data[key] = base[key]
        if depth:
            # anonymous clients only get published related documents
            populate = req.populate(req.is_editor)
            data = schema.walk_relations(fields_conf, data, lambda slug, value: populate(slug, value, depth - 1))
        return req.env['cms.document']._output_rich_text(fields_conf, data)

    def _create(self, req, collection):
        if not collection.public_create:
            req.require_editor()
        data, upload = req.body()
        draft = req.flag('draft') and req.is_editor
        doc = req.env['cms.document'].sudo()._payload_create(collection, data, draft=draft, upload=upload)
        doc._payload_auto_translate()
        label = collection.label_singular or collection.label
        return json_response({
            'doc': req.serialize(doc, True, req.depth(0)),
            'message': '%s successfully created.' % label,
        }, 201)

    def _update(self, req, collection, doc):
        req.require_editor()
        data, upload = req.body()
        doc._payload_update(data, draft=req.flag('draft'), autosave=req.flag('autosave'), upload=upload)
        if not req.flag('autosave'):
            doc._payload_auto_translate()
        label = collection.label_singular or collection.label
        return json_response({
            'doc': req.serialize(doc, True, req.depth(0)),
            'message': 'Updated successfully.' if not req.flag('autosave') else 'Autosaved.',
            'label': label,
        })

    # ------------------------------------------------------------------
    # Import / export (CSV, Excel, JSON)
    # ------------------------------------------------------------------
    def _file_response(self, content, fmt, filename):
        mimetype, ext = import_export.FORMATS[fmt]
        headers = [('Content-Type', mimetype), ('Content-Length', str(len(content))),
                   ('Content-Disposition', 'attachment; filename="%s.%s"' % (filename, ext)), ('Cache-Control', 'no-store')]
        return request.make_response(content, headers=headers + cors_headers())

    def _export_columns(self, req, collection):
        fields = collection._payload_fields()
        cols = import_export.columns(fields)
        return fields, dict(cols), [p for p, _f in cols]

    def _export(self, req, collection):
        """GET /api/{slug}/export?format=csv|xlsx|json&where=…&ids=1,2&fields=a,b&sort=…&locale=…&draft=true"""
        req.require_editor()
        fmt = req.query.get('format') or 'csv'
        if fmt not in import_export.FORMATS:
            raise UserError('Unknown format "%s" (csv, xlsx or json).' % fmt)
        draft = req.draft()
        where = req.query.get('where')
        ids = [int(i) for i in str(req.query.get('ids') or '').split(',') if i.strip().isdigit()]
        if ids:
            where = {'id': {'in': ids}}
        docs, _meta = req.env['cms.document'].sudo()._payload_search(
            collection, where=where, sort=req.query.get('sort'), limit=0, pagination=False, draft=draft)
        depth = req.depth(0) if fmt == 'json' else 0
        serialized = [req.serialize(doc, draft, depth) for doc in docs]
        fields, by_path, all_cols = self._export_columns(req, collection)
        wanted = [c for c in str(req.query.get('fields') or '').split(',') if c]
        cols = (import_export.meta_columns(collection) if not wanted else []) + [c for c in (wanted or all_cols)]
        if wanted and 'id' not in cols:
            cols.insert(0, 'id')
        if fmt == 'json' and wanted:
            keep = {c.split('.')[0] for c in cols}
            serialized = [{k: v for k, v in d.items() if k in keep} for d in serialized]
        headers = cols
        if req.query.get('headers') == 'labels':
            labels = import_export.column_labels(fields)
            headers = [labels.get(c, c) for c in cols]
        content = import_export.write(fmt, headers, list(import_export.rows(serialized, cols, by_path)),
                                      sheet_name=collection.label or collection.slug, docs=serialized)
        stamp = datetime.datetime.now().strftime('%Y-%m-%d')
        return self._file_response(content, fmt, '%s-%s' % (collection.slug, stamp))

    def _aggregate(self, req, collection):
        """GET /api/{slug}/aggregate?groupBy=_status,createdAt:month&measures=count,sum:price&where=…
        Grouped counts / sums used by the pivot and graph views."""
        req.require_editor()
        group_by = [g for g in str(req.query.get('groupBy') or '').split(',') if g][:3]
        measures = [m for m in str(req.query.get('measures') or 'count').split(',') if m][:6]
        result = req.env['cms.document.aggregate'].sudo()._aggregate(
            collection, group_by, measures, where=req.query.get('where'), draft=req.draft())
        return json_response(result)

    def _import_template(self, req, collection):
        req.require_editor()
        fmt = req.query.get('format') or 'xlsx'
        if fmt not in ('csv', 'xlsx'):
            raise UserError('The import template is available as csv or xlsx.')
        _fields, _by_path, cols = self._export_columns(req, collection)
        headers = ['id'] + (['_status'] if collection.drafts else []) + cols
        content = import_export.write(fmt, headers, [], sheet_name=collection.label or collection.slug)
        return self._file_response(content, fmt, '%s-import-template' % collection.slug)

    def _import(self, req, collection):
        """POST /api/{slug}/import (multipart: `file` + `_payload` JSON options):
        mode create | update | upsert, matchField, draft, dryRun, mapping {column: path}."""
        req.require_editor()
        if collection.upload:
            raise UserError('Upload collections cannot be imported from a file.')
        options, upload = req.body()
        if not upload:
            raise UserError('Select a CSV, Excel (.xlsx) or JSON file.')
        filename, content, _mimetype = upload
        try:
            headers, rows, is_json = import_export.read(filename, content)
        except import_export.ImportFileError as e:
            raise UserError(str(e))
        fields, by_path, _cols = self._export_columns(req, collection)
        labels = import_export.column_labels(fields)
        mapping = options.get('mapping') if isinstance(options.get('mapping'), dict) else None
        if not is_json:
            mapping = mapping or import_export.auto_mapping(headers, fields, labels)
        mode = options.get('mode') if options.get('mode') in ('create', 'update', 'upsert') else 'create'
        match = options.get('matchField') or 'id'
        draft = bool(options.get('draft')) and bool(collection.drafts)
        dry_run = bool(options.get('dryRun'))
        top_level = {f['name'] for f in schema.data_fields(fields)}
        required_cols = [(p, f) for p, f in import_export.columns(fields)
                         if f.get('required') and f['type'] not in ('slug', 'checkbox') and f.get('defaultValue') is None]
        Document = req.env['cms.document'].sudo()
        results, created, updated = [], [], 0

        class DryRun(Exception):
            pass

        def find_existing(data, meta):
            key = meta.get('id') if match == 'id' else import_export._get(data, match)
            if key in (None, ''):
                return Document
            where = {'id': {'equals': key}} if match == 'id' else {match: {'equals': key}}
            docs, _m = Document._payload_search(collection, where=where, limit=1, draft=True)
            return docs[:1]

        try:
            with req.env.cr.savepoint():
                for line, row in enumerate(rows, start=2):
                    if is_json:
                        data = {k: v for k, v in row.items() if k in top_level}
                        meta = {k: row[k] for k in ('id', '_status') if row.get(k) not in (None, '')}
                        errors = []
                    else:
                        data, meta, errors = import_export.row_to_data(row, mapping, by_path)
                    if errors:
                        results.append({'row': line, 'status': 'error', 'errors': errors})
                        continue
                    existing = find_existing(data, meta) if mode in ('update', 'upsert') else Document
                    if mode == 'update' and not existing:
                        results.append({'row': line, 'status': 'error', 'errors': [
                            {'path': match, 'message': 'No document matches %s = %s' % (match, meta.get('id') if match == 'id' else import_export._get(data, match))}]})
                        continue
                    if collection.drafts and meta.get('_status') in ('draft', 'published') and not draft:
                        data['_status'] = meta['_status']
                    if not existing:
                        # an import never creates documents without their required values (even as drafts)
                        missing = [{'path': path, 'message': 'This field is required.'} for path, field in required_cols
                                   if import_export._get(data, path) in (None, '', [])]
                        if missing:
                            results.append({'row': line, 'status': 'error', 'errors': missing})
                            continue
                    try:
                        with req.env.cr.savepoint():
                            if existing:
                                existing._payload_update(data, draft=draft)
                                updated += 1
                                results.append({'row': line, 'status': 'updated', 'id': existing.id})
                            else:
                                doc = Document._payload_create(collection, data, draft=draft)
                                created.append(doc)
                                results.append({'row': line, 'status': 'created', 'id': doc.id})
                    except PayloadValidationError as e:
                        results.append({'row': line, 'status': 'error', 'errors': e.errors})
                if dry_run:
                    raise DryRun()
        except DryRun:
            req.env.invalidate_all()
        if not dry_run:
            for doc in created:
                doc._payload_auto_translate()
        failed = sum(1 for r in results if r['status'] == 'error')
        verb = 'can be imported' if dry_run else 'imported'
        return json_response({
            'dryRun': dry_run,
            'total': len(rows),
            'created': len(created),
            'updated': updated,
            'failed': failed,
            'headers': headers,
            'mapping': mapping or {h: h for h in headers},
            'results': [r for r in results if r['status'] == 'error'][:200] + ([r for r in results if r['status'] != 'error'][:50] if dry_run else []),
            'message': '%s row(s) %s: %s created, %s updated, %s error(s).' % (
                len(rows) - failed, verb, len(created), updated, failed),
        }, status=200)

    def _translate(self, req, collection, doc):
        """Machine translation: ``POST /api/{slug}/{id}/translate`` (or
        ``/api/globals/{slug}/translate``) with ``{from, to, overwrite}``.
        ``to`` is a locale code, a list of codes or ``"all"``."""
        req.require_editor()
        body, _upload = req.body()
        params = dict(req.query, **body)
        settings = req.localization
        codes = localization.locale_codes(settings)
        if not codes:
            raise UserError('Localization is not enabled.')
        source = params.get('from') or settings['defaultLocale']
        targets = params.get('to') or 'all'
        if targets == 'all':
            targets = [c for c in codes if c != source]
        elif isinstance(targets, str):
            targets = [t for t in targets.split(',') if t]
        overwrite = str(params.get('overwrite', 'true')).lower() in ('1', 'true', 'yes')
        try:
            count = doc._payload_translate(source, targets, only_missing=not overwrite)
        except translate.TranslationError as e:
            raise UserError(str(e))
        locale = targets[0] if len(targets) == 1 else source
        result = doc.with_context(payload_locale=localization.make_context(settings, locale, 'none')) \
            ._payload_serialize(draft=True)
        return json_response({
            'doc': result,
            'translated': count,
            'locales': targets,
            'message': 'Translated %s value(s) from %s to %s.' % (count, source, ', '.join(targets)),
        })

    def _delete(self, req, collection, doc):
        req.require_editor()
        result = req.serialize(doc, True, 0)
        doc._payload_delete()
        label = collection.label_singular or collection.label
        return json_response({'doc': result, 'message': '%s "%s" successfully deleted.' % (label, doc.title or doc.id)})

    def _bulk_docs(self, req, collection):
        where = req.query.get('where')
        if not where:
            raise UserError('Missing \'where\' query of documents to update or delete.')
        docs, _meta = req.env['cms.document'].sudo()._payload_search(
            collection, where=where, limit=0, pagination=False, draft=True)
        return docs

    def _bulk_update(self, req, collection):
        req.require_editor()
        data, _upload = req.body()
        docs = self._bulk_docs(req, collection)
        result, errors = [], []
        for doc in docs:
            try:
                with req.env.cr.savepoint():
                    doc._payload_update(dict(data), draft=req.flag('draft'))
                result.append(req.serialize(doc, True, 0))
            except PayloadValidationError as e:
                errors.append({'id': doc.id, 'message': e.message})
        return json_response({'docs': result, 'errors': errors,
                              'message': 'Updated %s %s successfully.' % (len(result), collection.label)},
                             status=200 if not errors else 400)

    def _bulk_delete(self, req, collection):
        req.require_editor()
        docs = self._bulk_docs(req, collection)
        result = [req.serialize(doc, True, 0) for doc in docs]
        docs._payload_delete()
        return json_response({'docs': result, 'errors': [],
                              'message': 'Deleted %s %s successfully.' % (len(result), collection.label)})

    def _file(self, req, collection, filename):
        if not collection.upload:
            raise NotFound()
        env = req.env
        env.cr.execute(SQL("""
            SELECT id FROM cms_document
             WHERE collection_id = %s
               AND (filename = %s OR EXISTS (
                    SELECT 1 FROM jsonb_each(COALESCE(sizes, '{}'::jsonb)) s WHERE s.value->>'filename' = %s))
             LIMIT 1""", collection.id, filename, filename))
        row = env.cr.fetchone()
        if not row:
            raise NotFound()
        doc = env['cms.document'].sudo().browse(row[0])
        if not req.is_editor and collection.drafts and not doc.published_data:
            raise NotFound()
        size = None if doc.filename == filename else \
            next(s for s in (doc.sizes or {}).values() if s.get('filename') == filename)
        key = doc._file_key(size)
        if not key:
            raise NotFound()
        if doc.storage == 's3':
            public_url = doc._public_file_url(key)
            if public_url:
                stream = Stream(type='url', url=public_url, max_age=3600)
            else:
                try:
                    content = doc._storage_backend().get(key)
                except storage.StorageError as e:
                    _logger.warning("Payload CMS: %s", e)
                    raise NotFound()
                # object keys are never reused: the key identifies the content
                stream = Stream(type='data', data=content, size=len(content), download_name=filename,
                                mimetype=(size or {}).get('mimeType') if size else doc.mime_type,
                                etag=hashlib.sha1(key.encode()).hexdigest(), last_modified=doc.write_date, max_age=3600)
        else:
            attachment = env['ir.attachment'].sudo().browse(int(key)).exists()
            if not attachment:
                raise NotFound()
            stream = env['ir.binary']._get_stream_from(attachment)
            stream.download_name = filename
        response = stream.get_response(max_age=3600, content_security_policy="default-src 'none'")
        for header, value in cors_headers():
            response.headers[header] = value
        return response

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------
    def _versions(self, req, method, collection, rest, document=None):
        req.require_editor()
        Version = req.env['cms.document.version'].sudo()
        depth = req.depth(1)
        if not rest and method == 'GET':
            domain = [('collection_id', '=', collection.id)]
            where = req.query.get('where') or {}
            parent = (where.get('parent') or {}).get('equals') if isinstance(where, dict) else None
            if document:
                domain.append(('document_id', '=', document.id))
            elif parent:
                domain.append(('document_id', '=', int(parent)))
            if isinstance(where, dict) and (where.get('latest') or {}).get('equals') in ('true', True):
                domain.append(('latest', '=', True))
            if isinstance(where, dict) and (where.get('autosave') or {}).get('equals') in ('false', False):
                domain.append(('autosave', '=', False))
            if isinstance(where, dict):
                status = (where.get('version._status') or {}).get('equals')
                if status:
                    domain.append(('status', '=', status))
            limit = int(req.query.get('limit', 10) or 10)
            page = max(1, int(req.query.get('page', 1) or 1))
            sort = req.query.get('sort') or '-updatedAt'
            order = 'id desc' if sort.startswith('-') else 'id asc'
            total = Version.search_count(domain)
            versions = Version.search(domain, order=order, limit=limit, offset=(page - 1) * limit)
            total_pages = max(1, -(-total // limit))
            return json_response({
                'docs': [v._payload_serialize() for v in versions],
                'totalDocs': total, 'limit': limit, 'totalPages': total_pages, 'page': page,
                'pagingCounter': (page - 1) * limit + 1, 'hasPrevPage': page > 1,
                'hasNextPage': page < total_pages, 'prevPage': page - 1 if page > 1 else None,
                'nextPage': page + 1 if page < total_pages else None,
            })
        if rest and rest[0].isdigit():
            version = Version.browse(int(rest[0])).exists()
            if not version or version.collection_id != collection:
                raise NotFound()
            if method == 'GET':
                return json_response(version._payload_serialize(depth=depth, populate=req.populate(True)))
            if method == 'POST':
                doc = version.document_id._restore_version(version, draft=req.flag('draft'))
                return json_response({'doc': req.serialize(doc, True, 0),
                                      'message': 'Restored version successfully.'})
        raise NotFound()

    # ------------------------------------------------------------------
    # Globals
    # ------------------------------------------------------------------
    def _global_doc(self, req, collection, write=False):
        """The document of a global. Globals scoped per site have one document
        per site; reads fall back to the shared document (no site)."""
        Document = req.env['cms.document'].sudo()
        scope = Document._tenant_scope(collection)
        if not scope:
            return Document.search([('collection_id', '=', collection.id)], limit=1, order='id')
        req.env.cr.execute(SQL(
            "SELECT id FROM cms_document WHERE collection_id = %s AND data->>'tenant' IS NOT DISTINCT FROM %s ORDER BY id LIMIT 1",
            collection.id, str(scope['id']) if scope['id'] else None))
        row = req.env.cr.fetchone()
        if not row and not write and scope['id']:
            req.env.cr.execute(SQL(
                "SELECT id FROM cms_document WHERE collection_id = %s AND data->>'tenant' IS NULL ORDER BY id LIMIT 1",
                collection.id))
            row = req.env.cr.fetchone()
        return Document.browse(row[0]) if row else Document

    def _global(self, req, method, slug, rest):
        collection = req.collection(slug, kind='global')
        doc = self._global_doc(req, collection)
        if rest and rest[0] == 'versions':
            if not doc:
                if method == 'GET' and not rest[1:]:
                    return json_response({'docs': [], 'totalDocs': 0, 'limit': 10, 'totalPages': 1, 'page': 1,
                                          'pagingCounter': 1, 'hasPrevPage': False, 'hasNextPage': False,
                                          'prevPage': None, 'nextPage': None})
                raise NotFound()
            return self._versions(req, method, collection, rest[1:], document=doc)
        if rest == ['translate'] and method == 'POST':
            if not doc:
                raise NotFound()
            return self._translate(req, collection, doc)
        if rest:
            raise NotFound()
        if method == 'GET':
            merged = self._live_preview_merge(req, collection, doc)
            if merged is not None:
                return json_response(merged)
            draft = req.draft()
            if not doc or (not draft and not doc.published_data):
                empty = {'globalType': collection.slug, 'createdAt': None, 'updatedAt': None}
                return json_response(empty)
            return json_response(req.serialize(doc, draft, req.depth()))
        if method in ('POST', 'PATCH'):
            req.require_editor()
            data, _upload = req.body()
            doc = self._global_doc(req, collection, write=True)
            if doc:
                doc._payload_update(data, draft=req.flag('draft'), autosave=req.flag('autosave'))
            else:
                doc = req.env['cms.document'].sudo()._payload_create(collection, data, draft=req.flag('draft'))
            if not req.flag('autosave'):
                doc._payload_auto_translate()
            return json_response({'result': req.serialize(doc, True, req.depth(0)),
                                  'message': 'Updated successfully.'})
        raise NotFound()

    # ------------------------------------------------------------------
    # Users & auth
    # ------------------------------------------------------------------
    def _users(self, req, method, rest):
        env = request.env
        action = rest[0] if rest else None
        if action == 'login' and method == 'POST':
            data, _u = req.body()
            email, password = data.get('email') or data.get('username'), data.get('password')
            if not email or not password:
                return error_response('The email or password provided is incorrect.', 401)
            try:
                auth = request.session.authenticate(request.db, {'login': email, 'password': password, 'type': 'password'})
            except AccessDenied:
                return error_response('The email or password provided is incorrect.', 401)
            user = env['res.users'].sudo().browse(auth['uid'])
            if not user.has_group(EDITOR_GROUP):
                request.session.logout(keep_db=True)
                return error_response('You are not allowed to perform this action.', 403)
            token, exp = encode_jwt(env, user)
            return json_response({'message': 'Auth Passed', 'user': _user_doc(user), 'token': token, 'exp': exp})
        if action == 'logout' and method == 'POST':
            if req.strategy == 'session':
                request.session.logout(keep_db=True)
            return json_response({'message': 'You have been logged out successfully.'})
        if action == 'me' and method == 'GET':
            if not req.user or not req.is_editor:
                return json_response({'user': None})
            result = {'user': _user_doc(req.user), 'collection': 'users', 'strategy': req.strategy}
            if req.token_payload:
                result['exp'] = req.token_payload['exp']
                result['token'] = request.httprequest.headers.get('Authorization', '').split(' ', 1)[1]
            return json_response(result)
        if action == 'refresh-token' and method == 'POST':
            req.require_editor()
            token, exp = encode_jwt(env, req.user)
            return json_response({'message': 'Token refresh successful', 'refreshedToken': token, 'exp': exp,
                                  'user': _user_doc(req.user)})
        # users "collection"
        req.require_editor()
        Users = env['res.users'].sudo()
        group = env.ref(EDITOR_GROUP)
        domain = [('groups_id', 'in', group.ids), ('share', '=', False), ('id', '!=', SUPERUSER_ID)]
        if action is None and method == 'GET':
            limit = int(req.query.get('limit', 10) or 10)
            page = max(1, int(req.query.get('page', 1) or 1))
            search = None
            where = req.query.get('where')
            if isinstance(where, dict):
                flat = json.dumps(where)
                match = re.search(r'"(?:like|contains|equals)": "([^"]*)"', flat)
                search = match and match.group(1)
            if search:
                domain += ['|', ('name', 'ilike', search), ('login', 'ilike', search)]
            sort = req.query.get('sort') or 'email'
            field = {'email': 'login', 'name': 'name', 'createdAt': 'create_date', 'updatedAt': 'write_date'}.get(sort.lstrip('-'), 'login')
            order = '%s %s' % (field, 'desc' if sort.startswith('-') else 'asc')
            total = Users.search_count(domain)
            users = Users.search(domain, limit=limit, offset=(page - 1) * limit, order=order)
            total_pages = max(1, -(-total // limit))
            return json_response({
                'docs': [_user_doc(u) for u in users], 'totalDocs': total, 'limit': limit,
                'totalPages': total_pages, 'page': page, 'pagingCounter': (page - 1) * limit + 1,
                'hasPrevPage': page > 1, 'hasNextPage': page < total_pages,
                'prevPage': page - 1 if page > 1 else None, 'nextPage': page + 1 if page < total_pages else None,
            })
        if action is None and method == 'POST':
            if not req.is_admin:
                raise Forbidden()
            data, _u = req.body()
            if not data.get('email'):
                raise PayloadValidationError([{'path': 'email', 'message': 'This field is required.'}], 'users')
            user = Users.create({
                'name': data.get('name') or data['email'],
                'login': data['email'],
                'email': data['email'],
                'password': data.get('password') or False,
                'groups_id': [(4, env.ref(EDITOR_GROUP).id)],
                'payload_tenant_ids': [(6, 0, self._tenant_ids(data.get('tenants')))],
            })
            return json_response({'doc': _user_doc(user), 'message': 'User successfully created.'}, 201)
        if action and action.isdigit():
            user = Users.search(domain + [('id', '=', int(action))], limit=1)
            if not user:
                raise NotFound()
            if method == 'GET':
                return json_response(_user_doc(user))
            if method in ('PATCH', 'PUT'):
                if user != req.user and not req.is_admin:
                    raise Forbidden()
                data, _u = req.body()
                vals = {}
                if data.get('name'):
                    vals['name'] = data['name']
                if data.get('email'):
                    vals.update(login=data['email'], email=data['email'])
                if data.get('password'):
                    vals['password'] = data['password']
                if 'tenants' in data and req.is_admin:
                    vals['payload_tenant_ids'] = [(6, 0, self._tenant_ids(data['tenants']))]
                user.write(vals)
                return json_response({'doc': _user_doc(user), 'message': 'Updated successfully.'})
            if method == 'DELETE':
                if not req.is_admin or user == req.user:
                    raise Forbidden()
                result = _user_doc(user)
                user.write({'groups_id': [(3, env.ref(EDITOR_GROUP).id), (3, env.ref(ADMIN_GROUP).id)]})
                return json_response({'doc': result, 'message': 'User removed from the CMS.'})
        raise NotFound()

    # ------------------------------------------------------------------
    # Admin helpers
    # ------------------------------------------------------------------
    def _access(self, req):
        collections = request.env['cms.collection'].sudo().search([])
        result = {'canAccessAdmin': req.is_editor, 'collections': {}, 'globals': {}}
        for c in collections:
            perms = {'read': req.is_editor or c.public_read, 'create': req.is_editor,
                     'update': req.is_editor, 'delete': req.is_editor}
            if c.kind == 'global':
                result['globals'][c.slug] = {'read': perms['read'], 'update': perms['update']}
            else:
                result['collections'][c.slug] = perms
        return json_response(result)

    # ------------------------------------------------------------------
    # Schema builder (Configuration views of the admin): collections, globals, fields
    # ------------------------------------------------------------------
    def _paginate(self, req, rows, search_keys):
        where = req.query.get('where')
        search = None
        if isinstance(where, dict):
            match = re.search(r'"(?:like|contains|equals)": "([^"]*)"', json.dumps(where))
            search = match and match.group(1).lower()
        if search:
            rows = [r for r in rows if any(search in str(r.get(k) or '').lower() for k in search_keys)]
        sort = req.query.get('sort') or ''
        key = sort.lstrip('-')
        if key:
            rows = sorted(rows, key=lambda r: (r.get(key) is None, str(r.get(key) or '').lower()), reverse=sort.startswith('-'))
        limit = int(req.query.get('limit', 10) or 10)
        page = max(1, int(req.query.get('page', 1) or 1))
        total = len(rows)
        total_pages = max(1, -(-total // limit))
        return {
            'docs': rows[(page - 1) * limit:page * limit], 'totalDocs': total, 'limit': limit,
            'totalPages': total_pages, 'page': page, 'pagingCounter': (page - 1) * limit + 1,
            'hasPrevPage': page > 1, 'hasNextPage': page < total_pages,
            'prevPage': page - 1 if page > 1 else None, 'nextPage': page + 1 if page < total_pages else None,
        }

    def _schema(self, req, method, rest):
        if not req.is_admin:
            raise Forbidden()
        from odoo.exceptions import ValidationError
        env = request.env
        section = rest[0] if rest else None
        if section == 'localization':
            return self._localization_settings(req, method)
        if section == 'multitenancy':
            return self._multitenancy_settings(req, method)
        if section == 'api-docs':
            return self._api_docs_settings(req, method)
        if section == 'storage':
            return self._storage_settings(req, method)
        if section == 'fields' and method == 'GET':
            return json_response(self._paginate(req, schema_admin.field_list(env), ['name', 'label', 'type', 'collection', 'path']))
        if section == 'blocks':
            return self._schema_blocks(req, method, rest)
        if section not in ('collections', 'globals'):
            raise NotFound()
        kind = 'global' if section == 'globals' else 'collection'
        Collection = env['cms.collection'].sudo()
        label = 'Global' if kind == 'global' else 'Collection'
        try:
            if len(rest) == 1:
                if method == 'GET':
                    docs = [schema_admin.collection_doc(c) for c in Collection.search([('kind', '=', kind)])]
                    return json_response(self._paginate(req, docs, ['label', 'slug', 'adminGroup']))
                if method == 'POST':
                    data, _u = req.body()
                    record = schema_admin.save_collection(env, Collection.browse(), data, kind)
                    return json_response({'doc': schema_admin.collection_doc(record), 'message': '%s successfully created.' % label}, 201)
                if method == 'DELETE':
                    where = req.query.get('where') or {}
                    ids = str(((where.get('id') or {}).get('in')) or '').split(',') if isinstance(where, dict) else []
                    records = Collection.browse([int(i) for i in ids if i.isdigit()]).exists()
                    count = len(records)
                    records.unlink()
                    return json_response({'docs': [], 'errors': [], 'message': 'Deleted %s %s successfully.' % (count, label.lower() + 's')})
            elif rest[1].isdigit():
                record = Collection.search([('id', '=', int(rest[1])), ('kind', '=', kind)])
                if not record:
                    raise NotFound()
                if method == 'GET':
                    return json_response(schema_admin.collection_doc(record))
                if method in ('PATCH', 'PUT', 'POST'):
                    data, _u = req.body()
                    schema_admin.save_collection(env, record, data, kind)
                    return json_response({'doc': schema_admin.collection_doc(record), 'message': 'Updated successfully.'})
                if method == 'DELETE':
                    doc = schema_admin.collection_doc(record)
                    record.unlink()
                    return json_response({'doc': doc, 'message': '%s "%s" successfully deleted.' % (label, doc['label'])})
        except ValidationError as e:
            request.env.cr.rollback()
            raise PayloadValidationError([{'path': 'fields', 'message': str(e.args[0] if e.args else e)}], section,
                                         message=str(e.args[0] if e.args else e))
        raise NotFound()

    def _schema_blocks(self, req, method, rest):
        """Reusable blocks (Configuration → Blocks), virtual collection `_config_blocks`."""
        from odoo.exceptions import UserError, ValidationError
        env = request.env
        Block = env['cms.block'].sudo().with_context(active_test=False)
        try:
            if len(rest) == 1:
                if method == 'GET':
                    docs = [schema_admin.block_doc(b) for b in Block.search([])]
                    return json_response(self._paginate(req, docs, ['label', 'slug']))
                if method == 'POST':
                    data, _u = req.body()
                    record = schema_admin.save_block(env, Block.browse(), data)
                    return json_response({'doc': schema_admin.block_doc(record), 'message': 'Block successfully created.'}, 201)
                if method == 'DELETE':
                    where = req.query.get('where') or {}
                    ids = str(((where.get('id') or {}).get('in')) or '').split(',') if isinstance(where, dict) else []
                    records = Block.browse([int(i) for i in ids if i.isdigit()]).exists()
                    count = len(records)
                    records.unlink()
                    return json_response({'docs': [], 'errors': [], 'message': 'Deleted %s blocks successfully.' % count})
            elif rest[1].isdigit():
                record = Block.browse(int(rest[1])).exists()
                if not record:
                    raise NotFound()
                if method == 'GET':
                    return json_response(schema_admin.block_doc(record))
                if method in ('PATCH', 'PUT', 'POST'):
                    data, _u = req.body()
                    schema_admin.save_block(env, record, data)
                    return json_response({'doc': schema_admin.block_doc(record), 'message': 'Updated successfully.'})
                if method == 'DELETE':
                    doc = schema_admin.block_doc(record)
                    record.unlink()
                    return json_response({'doc': doc, 'message': 'Block "%s" successfully deleted.' % doc['label']})
        except (UserError, ValidationError) as e:
            request.env.cr.rollback()
            message = str(e.args[0] if e.args else e)
            raise PayloadValidationError([{'path': 'components', 'message': message}], 'blocks', message=message)
        raise NotFound()

    def _multitenancy_settings(self, req, method):
        """Settings of the virtual global `_config_multitenancy`."""
        env = request.env
        settings = multitenancy.get_settings(env)
        Collection = env['cms.collection'].sudo()
        if method in ('POST', 'PATCH'):
            data, _u = req.body()
            for key in ('enabled', 'resolveByHost', 'corsSites'):
                if key in data:
                    settings[key] = bool(data[key])
            multitenancy.set_settings(env, settings)
            if settings['enabled']:
                Collection._install_multitenancy()
            if isinstance(data.get('scopedCollections'), list):
                wanted = set(data['scopedCollections'])
                for collection in Collection.search([]):
                    if collection.slug in (multitenancy.TENANTS, multitenancy.NETWORKS):
                        continue
                    scoped = self._localizable_key(collection) in wanted
                    if collection.multi_tenant != scoped:
                        collection.multi_tenant = scoped
        tenants = Collection._get_by_slug(multitenancy.TENANTS)
        networks = Collection._get_by_slug(multitenancy.NETWORKS)
        doc = {
            'enabled': bool(settings['enabled']),
            'resolveByHost': bool(settings.get('resolveByHost', True)),
            'corsSites': bool(settings.get('corsSites', True)),
            'scopedCollections': [self._localizable_key(c) for c in Collection.search([('multi_tenant', '=', True)])],
            'siteCount': len(tenants.document_ids) if tenants else 0,
            'networkCount': len(networks.document_ids) if networks else 0,
            'globalType': '_config_multitenancy',
        }
        if method in ('POST', 'PATCH'):
            return json_response({'result': doc, 'message': 'Updated successfully.'})
        return json_response(doc)

    def _api_docs_settings(self, req, method):
        """Settings of the virtual global `_config_api_docs`."""
        env = request.env
        settings = api_docs.get_settings(env)
        if method in ('POST', 'PATCH'):
            data, _u = req.body()
            for key in ('enabled', 'public', 'includeAuth', 'includeRpc'):
                if key in data:
                    settings[key] = bool(data[key])
            for key in ('title', 'version', 'description'):
                if key in data:
                    settings[key] = (data[key] or '').strip()
            if isinstance(data.get('servers'), list):
                settings['servers'] = [{'url': s['url'].strip(), 'description': (s.get('description') or '').strip()}
                                       for s in data['servers'] if isinstance(s, dict) and (s.get('url') or '').strip()]
            if isinstance(data.get('modules'), list):
                settings['modules'] = [m for m in data['modules'] if isinstance(m, str)]
            api_docs.set_settings(env, settings)
        doc = dict(settings, servers=[dict(s, id='server-%s' % i) for i, s in enumerate(settings.get('servers') or [])],
                   docsUrl=request.httprequest.host_url.rstrip('/') + '/api-docs',
                   specUrl=request.httprequest.host_url.rstrip('/') + '/api-docs/openapi.json',
                   globalType='_config_api_docs')
        if method in ('POST', 'PATCH'):
            return json_response({'result': doc, 'message': 'Updated successfully.'})
        return json_response(doc)

    def _storage_settings(self, req, method):
        """Settings of the virtual global `_config_storage` (file storage of the uploads)."""
        env = request.env
        stored = storage.stored_settings(env)
        locked = storage.env_overrides()
        message = 'Updated successfully.'
        if method in ('POST', 'PATCH'):
            data, _u = req.body()
            for key in ('backend', 'endpoint', 'region', 'bucket', 'accessKey', 'prefix', 'addressing', 'publicUrl', 'delivery'):
                if key in data and key not in locked:
                    stored[key] = (data[key] or '').strip() if isinstance(data[key], str) else data[key]
            if data.get('secretKey') and 'secretKey' not in locked:
                stored['secretKey'] = data['secretKey'].strip()
            if data.get('clearSecretKey') and 'secretKey' not in locked:
                stored['secretKey'] = ''
            settings = storage._normalize(dict(stored, **locked))
            if settings['backend'] == 's3' and settings['delivery'] == 'public' and not settings['publicUrl']:
                raise PayloadValidationError([{'path': 'publicUrl', 'label': 'Public base URL',
                                               'message': 'Required to serve the files from the bucket.'}], '_config_storage')
            if settings['backend'] == 's3' or data.get('testConnection'):
                try:
                    message = storage.S3Backend(settings).test(create_bucket=bool(data.get('createBucket')))
                except storage.StorageError as e:
                    raise PayloadValidationError([{'path': 'bucket', 'label': 'Bucket', 'message': str(e)}],
                                                 '_config_storage', message=str(e))
            storage.set_settings(env, stored)
            if data.get('migrateExisting'):
                moved, errors = env['cms.document'].sudo()._payload_migrate_storage(settings['backend'])
                message = '%s %s file(s) moved to the %s storage.' % (message, moved, settings['backend'])
                if errors:
                    message += ' %s error(s): %s' % (len(errors), '; '.join(errors[:3]))
        settings = storage.get_settings(env)
        Document = env['cms.document'].sudo()
        counts = {name: Document.search_count([('collection_id.upload', '=', True), ('filename', '!=', False),
                                               ('storage', '=', name)]) for name in storage.BACKENDS}
        doc = {k: v for k, v in settings.items() if k != 'secretKey'}
        doc.update({
            'secretKey': '',
            'secretKeySet': bool(settings.get('secretKey')),
            'clearSecretKey': False,
            'testConnection': False,
            'createBucket': False,
            'migrateExisting': False,
            'nativeCount': counts['native'],
            's3Count': counts['s3'],
            'envVariables': ', '.join('%s (%s)' % (storage.ENV_VARS[k], k) for k in sorted(locked)) or 'None',
            'globalType': '_config_storage',
        })
        if method in ('POST', 'PATCH'):
            return json_response({'result': doc, 'message': message})
        return json_response(doc)

    @staticmethod
    def _localizable_key(collection):
        return 'globals/%s' % collection.slug if collection.kind == 'global' else collection.slug

    def _localization_settings(self, req, method):
        """Settings of the virtual global `_config_localization`."""
        env = request.env
        settings = localization.get_settings(env)
        if method in ('POST', 'PATCH'):
            data, _u = req.body()
            locales = []
            for row in data.get('locales') or settings['locales']:
                code = str(row.get('code') or '').strip()
                if code and code not in [l['code'] for l in locales]:
                    locales.append({'code': code, 'label': (row.get('label') or code).strip(), 'rtl': bool(row.get('rtl'))})
            if not locales:
                raise PayloadValidationError([{'path': 'locales', 'message': 'Add at least one locale.', 'label': 'Locales'}], '_config_localization')
            codes = [l['code'] for l in locales]
            default = data.get('defaultLocale', settings['defaultLocale'])
            if default not in codes:
                raise PayloadValidationError([{'path': 'defaultLocale', 'label': 'Default Locale',
                                               'message': 'The default locale must be one of the locales.'}], '_config_localization')
            translate_conf = dict(settings['translate'])
            if 'autoTranslate' in data:
                translate_conf['autoTranslate'] = data['autoTranslate'] if data['autoTranslate'] in ('off', 'missing', 'always') else 'off'
            if data.get('apiKey'):
                translate_conf['apiKey'] = data['apiKey'].strip()
            if data.get('clearApiKey'):
                translate_conf['apiKey'] = ''
            if data.get('provider') in ('google', 'mymemory', 'libretranslate'):
                translate_conf['provider'] = data['provider']
            for key in ('url', 'email'):
                if key in data:
                    translate_conf[key] = (data[key] or '').strip()
            settings.update({
                'enabled': bool(data.get('enabled', settings['enabled'])),
                'locales': locales,
                'defaultLocale': default,
                'fallback': bool(data.get('fallback', settings['fallback'])),
                'translate': translate_conf,
            })
            localization.set_settings(env, settings)
            if isinstance(data.get('localizedCollections'), list):
                wanted = set(data['localizedCollections'])
                Collection = env['cms.collection'].sudo()
                for collection in Collection.search([]):
                    has = bool(collection.all_field_ids.filtered('localized'))
                    key = self._localizable_key(collection)
                    if key in wanted and not has:
                        collection._set_localized(True)
                    elif key not in wanted and has:
                        collection._set_localized(False)
        localized_keys = [self._localizable_key(c) for c in env['cms.collection'].sudo().search([])
                          if c.all_field_ids.filtered('localized')]
        doc = {
            'enabled': settings['enabled'],
            'locales': [dict(l, id='locale-%s' % l['code']) for l in settings['locales']],
            'defaultLocale': settings['defaultLocale'],
            'fallback': settings['fallback'],
            'provider': settings['translate'].get('provider') or 'google',
            'url': settings['translate'].get('url') or '',
            'email': settings['translate'].get('email') or '',
            'autoTranslate': settings['translate'].get('autoTranslate') or 'off',
            'apiKey': '',
            'apiKeySet': bool(settings['translate'].get('apiKey')),
            'localizedCollections': localized_keys,
            'translateExisting': False,
            'globalType': '_config_localization',
        }
        if method in ('POST', 'PATCH'):
            message = 'Updated successfully.'
            if data.get('translateExisting') and settings['enabled']:
                message = self._translate_existing(env, settings)
            return json_response({'result': doc, 'message': message})
        return json_response(doc)

    def _translate_existing(self, env, settings):
        """Fill the missing translations of every document of the localized collections."""
        codes = localization.locale_codes(settings)
        default = settings['defaultLocale']
        targets = [c for c in codes if c != default]
        collections = env['cms.collection'].sudo().search([]).filtered(lambda c: c.all_field_ids.filtered('localized'))
        done = values = 0
        for doc in env['cms.document'].sudo().search([('collection_id', 'in', collections.ids)]):
            try:
                with env.cr.savepoint():
                    count = doc._payload_translate(default, targets, only_missing=True)
            except (translate.TranslationError, UserError) as e:
                return 'Translation stopped after %s document(s): %s' % (done, e)
            done += 1 if count else 0
            values += count
        return 'Translated %s value(s) in %s document(s).' % (values, done)

    @staticmethod
    def _api_modules():
        from ..payload.apidoc import payload_modules
        names = payload_modules(request.env)
        modules = request.env['ir.module.module'].sudo().search([('name', 'in', names)])
        return [{'value': m.name, 'label': m.shortdesc or m.name} for m in modules]

    def _admin(self, req, method, rest):
        req.require_editor()
        if rest[:1] == ['schema']:
            return self._schema(req, method, rest[1:])
        if rest == ['config'] and method == 'GET':
            collections = request.env['cms.collection'].sudo().search([('hidden', 'in', (True, False))])
            return json_response({
                'serverURL': request.httprequest.host_url.rstrip('/'),
                'routes': {'admin': '/admin', 'api': '/api'},
                'collections': [c._admin_config() for c in collections if c.kind == 'collection'],
                'globals': [c._admin_config() for c in collections if c.kind == 'global'],
                'user': _user_doc(req.user),
                'isAdmin': req.is_admin,
                'localization': localization.public_settings(req.localization),
                'multitenancy': {'enabled': bool(req.multitenancy.get('enabled')), 'header': multitenancy.HEADER,
                                 'userTenants': req.user.payload_tenant_ids.ids if not req.is_admin else None},
                'storage': storage.public_settings(storage.get_settings(request.env)) if req.is_admin else None,
                'apiDocs': {'enabled': bool(api_docs.get_settings(request.env).get('enabled')), 'url': '/api-docs',
                            'modules': self._api_modules()},
                'odooURL': '/odoo',
            })
        if rest == ['routes'] and method == 'GET':
            # documented API routes (API tab of the edit view)
            return json_response({'routes': api_docs.admin_routes(request.env, req.query.get('model') or None)})
        if rest[:1] == ['relation-labels'] and method == 'GET':
            # {collection: [ids]} -> titles, used by relationship fields & list cells
            spec = req.query.get('ids') or {}
            spec = json.loads(spec) if isinstance(spec, str) else spec
            result = {}
            for slug, ids in (spec or {}).items():
                ids = [int(i) for i in (ids if isinstance(ids, list) else str(ids).split(',')) if str(i).isdigit()]
                collection = req.collection(slug)
                docs = req.env['cms.document'].sudo().search([('collection_id', '=', collection.id), ('id', 'in', ids)])
                result[slug] = {d.id: req.serialize(d, True, 0) for d in docs}
            return json_response(result)
        raise NotFound()
