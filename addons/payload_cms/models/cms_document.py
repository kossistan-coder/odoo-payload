# -*- coding: utf-8 -*-
import base64
import io
import logging
import mimetypes
import os

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

from ..tools import localization, schema, translate
from ..tools.query import QueryError, WhereBuilder

_logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover
    Image = ImageOps = None


class PayloadValidationError(Exception):
    """Raised with a Payload-like list of field errors."""

    def __init__(self, errors, collection=None, message=None):
        self.errors = errors
        self.collection = collection
        self.message = message or (
            'The following field is invalid: %s' % errors[0]['path'] if len(errors) == 1
            else 'The following fields are invalid: %s' % ', '.join(e['path'] for e in errors))
        super().__init__(self.message)


def _iso(dt):
    if not dt:
        return None
    return dt.strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % (dt.microsecond // 1000)


class CmsDocument(models.Model):
    """A document of a Payload collection (or the single document of a global).

    ``data`` holds the latest saved state (draft or published), while
    ``published_data`` holds what anonymous API consumers see.
    """
    _name = 'cms.document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Payload document'
    _order = 'write_date desc, id desc'
    _rec_name = 'title'

    collection_id = fields.Many2one('cms.collection', required=True, ondelete='cascade', index=True)
    collection_slug = fields.Char(related='collection_id.slug', store=True, index=True)
    kind = fields.Selection(related='collection_id.kind', store=True)
    title = fields.Char(index='trigram', tracking=True)
    data = fields.Json(default=lambda self: {})
    published_data = fields.Json()
    status = fields.Selection([('draft', 'Draft'), ('published', 'Published')], default='draft', required=True, index=True,
                              tracking=True)
    # multisite: site of the document (from data['tenant']) for the native Odoo views (group by, pivot...)
    tenant_id = fields.Many2one('cms.document', string='Site', compute='_compute_tenant_id', store=True, index=True)
    version_ids = fields.One2many('cms.document.version', 'document_id')

    # upload collections
    attachment_id = fields.Many2one('ir.attachment', ondelete='set null')
    filename = fields.Char(index=True)
    mime_type = fields.Char()
    filesize = fields.Integer()
    width = fields.Integer()
    height = fields.Integer()
    focal_x = fields.Float(default=50)
    focal_y = fields.Float(default=50)
    sizes = fields.Json(default=lambda self: {})

    @api.depends('data')
    def _compute_tenant_id(self):
        for record in self:
            tenant = (record.data or {}).get('tenant') if isinstance(record.data, dict) else None
            if isinstance(tenant, dict):
                tenant = tenant.get('id')
            record.tenant_id = int(tenant) if str(tenant or '').isdigit() else False

    def action_open_in_payload(self):
        """Open the document in the Payload admin (client action)."""
        self.ensure_one()
        path = '/globals/%s' % self.collection_slug if self.kind == 'global' else '/collections/%s/%s' % (self.collection_slug, self.id)
        return {'type': 'ir.actions.client', 'tag': 'payload_cms.admin', 'name': self.title or self.collection_id.label,
                'params': {'path': path}}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _fields_config(self, collection):
        cache = self.env.context.get('payload_schema_cache')
        if cache is not None and collection.id in cache:
            return cache[collection.id]
        conf = collection._payload_fields()
        if cache is not None:
            cache[collection.id] = conf
        return conf

    @api.model
    def _locale(self, write=False):
        """Locale context (``payload_locale``) or None when localization is off."""
        loc = self.env.context.get('payload_locale')
        if loc and write:
            # writes always target one locale, without fallback
            loc = dict(loc, locale=loc['default'] if loc['locale'] == 'all' else loc['locale'], fallback=None)
        return loc

    def _default_locale_data(self, collection, data):
        loc = self._locale()
        if not loc:
            return data
        return schema.flatten_locale(self._fields_config(collection), data,
                                     dict(loc, locale=loc['default'], fallback=None))

    def _compute_title(self, collection, data):
        data = self._default_locale_data(collection, data)
        field = collection._title_field()
        if field == 'id':
            return False
        if field == 'filename':
            return self.filename or data.get('filename')
        value = data.get(field)
        if isinstance(value, dict) and 'root' in value:
            return schema.lexical_to_text(value, 200)
        return str(value)[:512] if value not in (None, '') else False

    # ------------------------------------------------------------------
    # Multi-tenancy
    # ------------------------------------------------------------------
    @api.model
    def _tenant_scope(self, collection):
        """Current site context (``payload_tenant``: {id, allowed}) when the
        collection is scoped per site, else None."""
        scope = self.env.context.get('payload_tenant')
        if not scope or not collection._is_tenant_scoped():
            return None
        return scope

    @staticmethod
    def _tenant_id(value):
        if isinstance(value, dict):
            value = value.get('id', value.get('value'))
        try:
            return int(value) if value not in (None, '', False) else None
        except (TypeError, ValueError):
            return None

    def _payload_tenant_visible(self):
        """False when the document belongs to another site than the current one
        (or to a site the user cannot access)."""
        self.ensure_one()
        scope = self._tenant_scope(self.collection_id)
        if not scope:
            return True
        tenant = self._tenant_id((self.data or {}).get('tenant'))
        if scope['id'] and tenant != scope['id']:
            return False
        return scope['allowed'] is None or tenant in scope['allowed']

    @api.model
    def _check_tenant(self, collection, data, scope):
        """Assign the current site to new documents and check the site access."""
        tenant = self._tenant_id(data.get('tenant'))
        if tenant is None and scope['id']:
            data['tenant'] = tenant = scope['id']
        if tenant is None:
            return
        tenants = self.env['cms.collection']._get_by_slug('tenants')
        doc = self.sudo().browse(tenant).exists()
        if not doc or doc.collection_id != tenants:
            raise PayloadValidationError([{'path': 'tenant', 'label': 'Site', 'message': 'This site does not exist.'}], collection.slug)
        if scope['allowed'] is not None and tenant not in scope['allowed']:
            raise PayloadValidationError([{'path': 'tenant', 'label': 'Site', 'message': 'You are not allowed to publish on this site.'}], collection.slug)

    def _check_unique(self, collection, data):
        """Enforce `unique` fields (and slug fields) at the top level."""
        errors = []
        loc = self._locale(write=True)
        for field in schema.data_fields(self._fields_config(collection)):
            if not field.get('unique') or data.get(field['name']) in (None, ''):
                continue
            path = '{%s,%s}' % (field['name'], loc['locale']) if loc and field.get('localized') else '{%s}' % field['name']
            tenant_sql = SQL('')
            if collection._is_tenant_scoped():
                # unique values (slugs...) are unique per site, like in WordPress Multisite
                tenant = self._tenant_id(data.get('tenant'))
                tenant_sql = SQL(" AND data->>'tenant' IS NOT DISTINCT FROM %s", str(tenant) if tenant else None)
            self.env.cr.execute(SQL(
                "SELECT 1 FROM cms_document WHERE collection_id = %s AND id <> %s AND data #>> %s = %s%s LIMIT 1",
                collection.id, self.id or 0, path, str(data[field['name']]), tenant_sql))
            if self.env.cr.fetchone():
                errors.append({'path': field['name'], 'message': 'Value must be unique', 'label': field.get('label')})
        return errors

    def _generate_slugs(self, collection, data):
        for field in schema.collect_slug_fields(self._fields_config(collection)):
            if not data.get(field['name']):
                source = data.get(field.get('useAsSlug') or 'title')
                if isinstance(source, str) and source:
                    data[field['name']] = schema.slugify(source)
        return data

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------
    @api.model
    def _payload_create(self, collection, data, draft=False, upload=None):
        fields_conf = self._fields_config(collection)
        data = dict(data or {})
        scope = self._tenant_scope(collection)
        if scope:
            self._check_tenant(collection, data, scope)
        status = self._target_status(collection, data, draft, current=None)
        clean = schema.apply_defaults(fields_conf, schema.sanitize(fields_conf, data))
        clean = self._generate_slugs(collection, clean)
        doc = self.new({'collection_id': collection.id})
        errors = schema.validate(fields_conf, clean, required=status == 'published')
        if collection.upload and not upload:
            errors.insert(0, {'path': 'file', 'message': 'No files were uploaded.', 'label': 'File'})
        errors += doc._check_unique(collection, clean)
        if errors:
            raise PayloadValidationError(errors, collection.slug)
        loc = self._locale(write=True)
        if loc:
            clean = schema.merge_locale(fields_conf, clean, {}, loc)
        vals = {
            'collection_id': collection.id,
            'data': clean,
            'status': status,
            'published_data': clean if status == 'published' else None,
        }
        record = self.create(vals)
        if upload:
            record._store_upload(collection, upload, data)
        record.title = record._compute_title(collection, clean)
        record._create_version(collection, status, autosave=False)
        return record

    def _target_status(self, collection, data, draft, current):
        if not collection.drafts:
            return 'published'
        if draft:
            return 'draft'
        requested = data.get('_status')
        if requested in ('draft', 'published'):
            return requested
        if current is None:
            return 'draft'
        return current

    def _payload_update(self, data, draft=False, autosave=False, upload=None):
        self.ensure_one()
        collection = self.collection_id
        fields_conf = self._fields_config(collection)
        data = dict(data or {})
        scope = self._tenant_scope(collection)
        if scope:
            if not self._payload_tenant_visible():
                raise PayloadValidationError([{'path': 'tenant', 'label': 'Site', 'message': 'This document belongs to another site.'}], collection.slug)
            if 'tenant' in data:
                self._check_tenant(collection, data, dict(scope, id=None))
        status = self._target_status(collection, data, draft, current=self.status)
        loc = self._locale(write=True)
        stored = self.data or {}
        previous = schema.flatten_locale(fields_conf, stored, loc) if loc else stored
        clean = schema.sanitize(fields_conf, data, previous=previous)
        clean = self._generate_slugs(collection, clean)
        errors = schema.validate(fields_conf, clean, required=status == 'published')
        errors += self._check_unique(collection, clean)
        if errors:
            raise PayloadValidationError(errors, collection.slug)
        if loc:
            clean = schema.merge_locale(fields_conf, clean, stored, loc)
        vals = {'data': clean}
        if status == 'published':
            vals.update(status='published', published_data=clean)
        elif not draft and data.get('_status') == 'draft':
            # explicit `_status: draft` without ?draft=true => unpublish
            vals.update(status='draft', published_data=None)
        else:
            # Saving a draft never touches what is published (Payload semantics):
            # a published document with a newer draft is shown as "Changed".
            vals['status'] = 'draft'
        self.write(vals)
        if upload:
            self._store_upload(collection, upload, data)
        elif collection.upload and data.get('uploadEdits'):
            self._apply_upload_edits(collection, data['uploadEdits'])
        self.title = self._compute_title(collection, clean)
        self._create_version(collection, vals.get('status', self.status), autosave=autosave)
        return self

    def _payload_delete(self):
        attachments = self.mapped('attachment_id')
        for record in self:
            for size in (record.sizes or {}).values():
                if size.get('attachment_id'):
                    attachments |= self.env['ir.attachment'].browse(size['attachment_id'])
        self.unlink()
        attachments.exists().unlink()

    def _payload_duplicate(self):
        self.ensure_one()
        collection = self.collection_id
        data = dict(self.data or {})
        for field in schema.data_fields(self._fields_config(collection)):
            if field.get('unique') or field['type'] == 'slug':
                if data.get(field['name']):
                    data[field['name']] = '%s-copy' % data[field['name']] if field['type'] == 'slug' else None
        title_field = collection._title_field()
        if title_field not in ('id', 'filename') and isinstance(data.get(title_field), str):
            data[title_field] = '%s - Copy' % data[title_field]
        data['_status'] = 'draft'
        upload = None
        if collection.upload and self.attachment_id:
            upload = (self.filename, base64.b64decode(self.attachment_id.datas), self.mime_type)
        return self.with_context(payload_locale=None)._payload_create(collection, data, draft=True, upload=upload)

    # ------------------------------------------------------------------
    # Machine translation
    # ------------------------------------------------------------------
    def _payload_translate(self, source, targets, only_missing=False, translator=None):
        """Translate the localized fields of the latest data from ``source``
        to each locale of ``targets``. Returns the number of translated values."""
        self.ensure_one()
        settings = localization.get_settings(self.env)
        codes = localization.locale_codes(settings)
        if not codes:
            raise UserError(_('Localization is not enabled.'))
        if source not in codes or any(t not in codes for t in targets):
            raise UserError(_('Unknown locale.'))
        translator = translator or self.env.context.get('payload_translator') or translate.get_translator(settings)
        collection = self.collection_id
        fields_conf = self._fields_config(collection)
        data, count = self.data or {}, 0
        for target in targets:
            if target == source:
                continue
            data, done = translate.translate_data(fields_conf, data, codes, source, target, translator, only_missing)
            count += done
            # localized slugs follow the translated source field instead of being copied
            for field in schema.collect_slug_fields(fields_conf):
                value = data.get(field['name'])
                origin = data.get(field.get('useAsSlug') or 'title')
                if not (field.get('localized') and schema.is_locale_dict(value, codes)
                        and schema.is_locale_dict(origin, codes) and isinstance(origin.get(target), str)):
                    continue
                if not value.get(target) or value.get(target) == value.get(source):
                    value[target] = schema.slugify(origin[target])
        if count:
            vals = {'data': data}
            if self.status == 'published':
                vals['published_data'] = data
            self.write(vals)
            self._create_version(collection, self.status, autosave=False)
        return count

    def _payload_auto_translate(self):
        """``autoTranslate`` setting: after a save in the default locale, fill
        (``missing``) or refresh (``always``) the other locales."""
        settings = localization.get_settings(self.env)
        mode = (settings.get('translate') or {}).get('autoTranslate') or 'off'
        loc = self._locale(write=True)
        if mode == 'off' or not loc or loc['locale'] != loc['default']:
            return 0
        if not translate.provider_ready(settings.get('translate') or {}) and not self.env.context.get('payload_translator'):
            return 0
        if not self.env['cms.field.definition'].sudo().search_count(
                [('collection_id', '=', self.collection_id.id), ('localized', '=', True)], limit=1):
            return 0
        targets = [c for c in loc['codes'] if c != loc['default']]
        try:
            with self.env.cr.savepoint():
                return self._payload_translate(loc['default'], targets, only_missing=mode == 'missing')
        except (translate.TranslationError, UserError) as e:
            _logger.warning("Payload CMS: automatic translation failed: %s", e)
            return 0

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------
    def _snapshot(self):
        self.ensure_one()
        return dict(self.data or {}, _status=self.status)

    def _create_version(self, collection, status, autosave=False):
        self.ensure_one()
        if not (collection.versions or collection.drafts):
            return
        Version = self.env['cms.document.version']
        latest = Version.search([('document_id', '=', self.id), ('latest', '=', True)], limit=1)
        if autosave and latest and latest.autosave:
            latest.write({'version': self._snapshot(), 'status': status})
            return latest
        latest.write({'latest': False})
        version = Version.create({
            'document_id': self.id,
            'version': self._snapshot(),
            'status': status,
            'autosave': autosave,
            'latest': True,
        })
        if collection.max_versions:
            old = Version.search([('document_id', '=', self.id)], order='id desc', offset=collection.max_versions)
            old.unlink()
        return version

    def _restore_version(self, version, draft=False):
        self.ensure_one()
        data = dict(version.version or {})
        status = 'draft' if draft else (data.pop('_status', None) or version.status)
        data.pop('_status', None)
        data['_status'] = status
        # restoring replaces the data entirely (all locales at once)
        self.data = {}
        return self.with_context(payload_locale=None)._payload_update(data, draft=draft)

    # ------------------------------------------------------------------
    # Uploads
    # ------------------------------------------------------------------
    def _unique_filename(self, collection, filename):
        stem, ext = os.path.splitext(filename)
        stem = schema.slugify(stem) or 'file'
        ext = ext.lower()
        candidate = stem + ext
        index = 0
        while self.search_count([('collection_id', '=', collection.id), ('filename', '=', candidate), ('id', '!=', self.id)]):
            index += 1
            candidate = '%s-%s%s' % (stem, index, ext)
        return candidate

    def _store_upload(self, collection, upload, data=None):
        """``upload`` is a tuple (filename, bytes, mimetype)."""
        self.ensure_one()
        filename, content, mimetype = upload
        mimetype = mimetype or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        filename = self._unique_filename(collection, filename)
        old = self.attachment_id
        old_sizes = self.sizes or {}
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'raw': content,
            'mimetype': mimetype,
            'res_model': self._name,
            'res_id': self.id,
            'public': True,
        })
        vals = {
            'attachment_id': attachment.id,
            'filename': filename,
            'mime_type': mimetype,
            'filesize': len(content),
            'width': 0,
            'height': 0,
        }
        focal = (data or {}).get('focalX'), (data or {}).get('focalY')
        if focal[0] is not None and focal[1] is not None:
            vals.update(focal_x=float(focal[0]), focal_y=float(focal[1]))
        self.write(vals)
        self._remove_sizes(old_sizes)
        if old:
            old.unlink()
        self._generate_image_sizes(collection, content)
        self.title = self._compute_title(collection, self.data or {})

    def _remove_sizes(self, sizes):
        ids = [s.get('attachment_id') for s in (sizes or {}).values() if s.get('attachment_id')]
        if ids:
            self.env['ir.attachment'].browse(ids).exists().unlink()

    def _generate_image_sizes(self, collection, content):
        self.ensure_one()
        if not Image or not (self.mime_type or '').startswith('image/') or self.mime_type == 'image/svg+xml':
            self.sizes = {}
            return
        try:
            image = Image.open(io.BytesIO(content))
            image = ImageOps.exif_transpose(image)
        except Exception:  # noqa: BLE001 - not a readable image
            _logger.info("Payload CMS: cannot read image %s", self.filename)
            self.sizes = {}
            return
        self.width, self.height = image.size
        stem, ext = os.path.splitext(self.filename)
        fmt = (image.format or Image.registered_extensions().get(ext.lower()) or 'PNG').upper()
        if fmt == 'JPG':
            fmt = 'JPEG'
        sizes = {}
        for size in collection.image_sizes or []:
            width, height = int(size.get('width') or 0), int(size.get('height') or 0)
            if not width and not height:
                continue
            resized = self._resize(image, width, height)
            buffer = io.BytesIO()
            to_save = resized.convert('RGB') if fmt == 'JPEG' and resized.mode not in ('RGB', 'L') else resized
            to_save.save(buffer, format=fmt, quality=85)
            size_name = '%s-%sx%s%s' % (stem, resized.size[0], resized.size[1], ext)
            raw = buffer.getvalue()
            attachment = self.env['ir.attachment'].create({
                'name': size_name,
                'raw': raw,
                'mimetype': self.mime_type,
                'res_model': self._name,
                'res_id': self.id,
                'public': True,
            })
            sizes[size['name']] = {
                'attachment_id': attachment.id,
                'filename': size_name,
                'width': resized.size[0],
                'height': resized.size[1],
                'mimeType': self.mime_type,
                'filesize': len(raw),
            }
        self.sizes = sizes

    def _resize(self, image, width, height):
        """Cover-resize around the focal point (Payload/sharp `position: focal`)."""
        src_w, src_h = image.size
        if not height:
            height = max(1, round(src_h * width / src_w))
        if not width:
            width = max(1, round(src_w * height / src_h))
        if width >= src_w and height >= src_h:
            return image.copy()
        scale = max(width / src_w, height / src_h)
        new_w, new_h = max(width, round(src_w * scale)), max(height, round(src_h * scale))
        resized = image.resize((new_w, new_h), Image.LANCZOS)
        fx = (self.focal_x if self.focal_x is not None else 50) / 100.0
        fy = (self.focal_y if self.focal_y is not None else 50) / 100.0
        left = min(max(0, round(fx * new_w - width / 2)), new_w - width)
        top = min(max(0, round(fy * new_h - height / 2)), new_h - height)
        return resized.crop((left, top, left + width, top + height))

    def _apply_upload_edits(self, collection, edits):
        """Crop / focal point edits sent by the admin's Edit Image drawer."""
        self.ensure_one()
        if not self.attachment_id:
            return
        content = base64.b64decode(self.attachment_id.datas)
        focal = edits.get('focalPoint') or {}
        if focal.get('x') is not None and focal.get('y') is not None:
            self.write({'focal_x': float(focal['x']), 'focal_y': float(focal['y'])})
        crop = edits.get('crop') or {}
        if crop.get('width') and crop.get('height') and Image and (self.mime_type or '').startswith('image/'):
            image = ImageOps.exif_transpose(Image.open(io.BytesIO(content)))
            w, h = image.size
            if crop.get('unit', '%') == '%':
                box = (crop.get('x', 0) * w / 100, crop.get('y', 0) * h / 100,
                       (crop.get('x', 0) + crop['width']) * w / 100, (crop.get('y', 0) + crop['height']) * h / 100)
            else:
                box = (crop.get('x', 0), crop.get('y', 0), crop.get('x', 0) + crop['width'], crop.get('y', 0) + crop['height'])
            box = tuple(int(round(v)) for v in box)
            if box[2] - box[0] >= 1 and box[3] - box[1] >= 1 and box != (0, 0, w, h):
                cropped = image.crop(box)
                buffer = io.BytesIO()
                fmt = image.format or 'PNG'
                cropped.save(buffer, format=fmt if fmt != 'JPG' else 'JPEG', quality=90)
                content = buffer.getvalue()
                self.attachment_id.write({'raw': content})
                self.filesize = len(content)
        self._remove_sizes(self.sizes)
        self._generate_image_sizes(collection, content)

    @api.model
    def _output_rich_text(self, fields_conf, doc):
        """Pure REST output: rich text is rendered to HTML, except for the
        admin UI / ``?richText=lexical`` (context ``payload_raw_richtext``)."""
        if self.env.context.get('payload_raw_richtext'):
            return doc
        loc = self._locale()
        return schema.rich_text_to_html(fields_conf, doc, loc['codes'] if loc else ())

    def _file_url(self, filename):
        return '/api/%s/file/%s' % (self.collection_slug, filename)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def _payload_serialize(self, draft=True, depth=0, populate=None):
        """Return the document as Payload's REST API does."""
        self.ensure_one()
        collection = self.collection_id
        source = (self.data if draft else self.published_data) or {}
        fields_conf = self._fields_config(collection)
        loc = self._locale()
        if loc:
            source = schema.flatten_locale(fields_conf, source, loc)
        doc = schema.order_keys(fields_conf, dict(source, id=self.id))
        if not self.env.context.get('payload_editor'):
            for field in schema.data_fields(fields_conf):
                if field.get('private'):
                    doc.pop(field['name'], None)
        if depth and populate:
            doc = schema.walk_relations(fields_conf, doc, lambda slug, value: populate(slug, value, depth - 1))
        doc = self._output_rich_text(fields_conf, doc)
        if collection.upload:
            base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/') \
                if self.env.context.get('payload_absolute_urls') else ''
            url = base + self._file_url(self.filename) if self.filename else None
            sizes = {}
            for name, size in (self.sizes or {}).items():
                sizes[name] = {
                    'url': base + self._file_url(size['filename']),
                    'width': size.get('width'),
                    'height': size.get('height'),
                    'mimeType': size.get('mimeType'),
                    'filesize': size.get('filesize'),
                    'filename': size.get('filename'),
                }
            for size in collection.image_sizes or []:
                sizes.setdefault(size['name'], {'url': None, 'width': None, 'height': None,
                                                'mimeType': None, 'filesize': None, 'filename': None})
            doc.update({
                'url': url,
                'thumbnailURL': sizes.get('thumbnail', {}).get('url') or (
                    url if (self.mime_type or '').startswith('image/') else None),
                'filename': self.filename,
                'mimeType': self.mime_type,
                'filesize': self.filesize,
                'width': self.width or None,
                'height': self.height or None,
                'focalX': self.focal_x,
                'focalY': self.focal_y,
                'sizes': sizes,
            })
        doc['updatedAt'] = _iso(self.write_date)
        doc['createdAt'] = _iso(self.create_date)
        if collection.drafts:
            doc['_status'] = self.status if draft else 'published'
        if collection.kind == 'global':
            doc.pop('id', None)
            doc['globalType'] = collection.slug
        if self.env.context.get('payload_admin'):
            doc['_hasPublishedVersion'] = bool(self.published_data)
        return doc

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    @api.model
    def _payload_where(self, collection, where=None, draft=True):
        """(where SQL, WhereBuilder) of a query: collection, site, drafts, `where`."""
        fields_conf = self._fields_config(collection)
        builder = WhereBuilder(fields_conf, 'data' if draft else 'published_data', draft=draft, locale=self._locale())
        condition = builder.build(where)
        base = SQL("d.collection_id = %s", collection.id)
        scope = self._tenant_scope(collection)
        if scope and scope['id']:
            base = SQL("%s AND d.data->>'tenant' = %s", base, str(scope['id']))
        elif scope and scope['allowed'] is not None:
            base = SQL("%s AND d.data->>'tenant' = ANY(%s)", base, [str(i) for i in scope['allowed']])
        site_ctx = self.env.context.get('payload_tenant')
        if collection.slug == 'tenants' and site_ctx:
            if site_ctx['allowed'] is not None:
                base = SQL("%s AND d.id = ANY(%s)", base, site_ctx['allowed'])
            if not self.env.context.get('payload_editor'):
                base = SQL("%s AND d.data->>'active' IS DISTINCT FROM 'false'", base)
        if not draft:
            base = SQL("%s AND d.published_data IS NOT NULL", base)
        return SQL("%s AND %s", base, condition), builder

    def _payload_search(self, collection, where=None, sort=None, limit=10, page=1, draft=True, pagination=True):
        where_sql, builder = self._payload_where(collection, where, draft)
        self.env.cr.execute(SQL("SELECT count(*) FROM cms_document d WHERE %s", where_sql))
        total = self.env.cr.fetchone()[0]
        order = builder.order_by(sort or collection.default_sort or '-updatedAt')
        limit = int(limit or 0)
        page = max(1, int(page or 1))
        if not pagination or limit <= 0:
            query = SQL("SELECT d.id FROM cms_document d WHERE %s ORDER BY %s", where_sql, order)
            limit = total
            page = 1
        else:
            query = SQL("SELECT d.id FROM cms_document d WHERE %s ORDER BY %s LIMIT %s OFFSET %s",
                        where_sql, order, limit, (page - 1) * limit)
        self.env.cr.execute(query)
        ids = [row[0] for row in self.env.cr.fetchall()]
        records = self.browse(ids)
        total_pages = max(1, -(-total // limit)) if limit else 1
        meta = {
            'totalDocs': total,
            'limit': limit,
            'totalPages': total_pages,
            'page': page,
            'pagingCounter': (page - 1) * limit + 1 if limit else 1,
            'hasPrevPage': page > 1,
            'hasNextPage': page < total_pages,
            'prevPage': page - 1 if page > 1 else None,
            'nextPage': page + 1 if page < total_pages else None,
        }
        return records, meta


AGGREGATE_INTERVALS = ('day', 'week', 'month', 'quarter', 'year')
AGGREGATE_OPS = ('sum', 'avg', 'min', 'max')


class CmsDocumentAggregate(models.AbstractModel):
    """Read-only aggregation used by the pivot / graph views of the admin."""
    _name = 'cms.document.aggregate'
    _description = 'Payload aggregation'

    @api.model
    def _aggregate(self, collection, group_by, measures, where=None, draft=True, limit=2000):
        """``group_by``: ["_status", "createdAt:month", "category", ...];
        ``measures``: ["count", "sum:price", ...]. Returns rows + labels."""
        Document = self.env['cms.document']
        where_sql, builder = Document._payload_where(collection, where, draft)
        fields_conf = Document._fields_config(collection)
        selects, labels, kinds = [], {}, []
        for spec in group_by:
            path, _sep, interval = spec.partition(':')
            expr, kind = self._group_expr(builder, fields_conf, path, interval, draft)
            selects.append(expr)
            kinds.append((path, kind))
        measure_sql = [SQL('count(*)')]
        measure_keys = ['count']
        for spec in measures:
            op, _sep, path = spec.partition(':')
            if spec == 'count' or op not in AGGREGATE_OPS:
                continue
            field = schema.find_field(fields_conf, path) if path else None
            if not field or field.get('type') != 'number':
                raise QueryError('"%s" is not a number field' % path)
            node, text = builder._nodes(path)
            value = SQL("(CASE WHEN jsonb_typeof(%s) = 'number' THEN (%s)::numeric END)", node, text)
            measure_sql.append(SQL('%s(%s)', SQL(op), value))
            measure_keys.append(spec)
        columns = selects + measure_sql
        group = SQL(', '.join(str(i + 1) for i in range(len(selects)))) if selects else None
        query = SQL('SELECT %s FROM cms_document d WHERE %s', SQL(', ').join(columns), where_sql)
        if group:
            query = SQL('%s GROUP BY %s ORDER BY %s', query, group, group)
        query = SQL('%s LIMIT %s', query, limit)
        self.env.cr.execute(query)
        rows = []
        for record in self.env.cr.fetchall():
            keys = [self._key(v) for v in record[:len(selects)]]
            values = record[len(selects):]
            rows.append({'keys': keys, **{k: (float(v) if v is not None and k != 'count' else v)
                                          for k, v in zip(measure_keys, values)}})
        for index, (path, kind) in enumerate(kinds):
            labels[group_by[index]] = self._labels(collection, fields_conf, path, kind,
                                                   {r['keys'][index] for r in rows})
        return {'groupBy': group_by, 'measures': measure_keys, 'rows': rows, 'labels': labels}

    @staticmethod
    def _key(value):
        if hasattr(value, 'isoformat'):
            return value.isoformat()[:10]
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    def _group_expr(self, builder, fields_conf, path, interval, draft):
        if path == '_status':
            return (SQL('d.status') if draft else SQL("'published'")), 'status'
        if path in ('createdAt', 'updatedAt'):
            column = SQL.identifier('create_date' if path == 'createdAt' else 'write_date')
            interval = interval if interval in AGGREGATE_INTERVALS else 'month'
            return SQL('date_trunc(%s, d.%s)::date', interval, column), 'date'
        field = schema.find_field(fields_conf, path)
        if field is None or field.get('type') in ('array', 'blocks', 'richText', 'json', 'group', 'point'):
            raise QueryError('The following path cannot be grouped: %s' % path)
        _node, text = builder._nodes(path)
        if field['type'] == 'date':
            interval = interval if interval in AGGREGATE_INTERVALS else 'month'
            return SQL("(CASE WHEN %s ~ '^\\d{4}-\\d{2}-\\d{2}' THEN date_trunc(%s, (%s)::timestamptz)::date END)",
                       text, interval, text), 'date'
        return text, field['type']

    def _labels(self, collection, fields_conf, path, kind, keys):
        keys = [k for k in keys if k is not None]
        if kind == 'status':
            return {k: {'draft': 'Draft', 'published': 'Published'}.get(k, k) for k in keys}
        if kind == 'checkbox':
            return {k: 'Yes' if k == 'true' else 'No' for k in keys}
        field = schema.find_field(fields_conf, path) or {}
        if kind in ('select', 'radio'):
            options = {str(o['value'] if isinstance(o, dict) else o): (o.get('label') if isinstance(o, dict) else o)
                       for o in field.get('options') or []}
            return {k: options.get(str(k), k) for k in keys}
        if kind in ('relationship', 'upload'):
            ids = [int(k) for k in keys if str(k).isdigit()]
            docs = self.env['cms.document'].sudo().browse(ids).exists()
            return {str(d.id): d.title or d.filename or '#%s' % d.id for d in docs}
        return {}


class CmsDocumentVersion(models.Model):
    _name = 'cms.document.version'
    _description = 'Payload document version'
    _order = 'id desc'

    document_id = fields.Many2one('cms.document', required=True, ondelete='cascade', index=True)
    collection_id = fields.Many2one(related='document_id.collection_id', store=True, index=True)
    version = fields.Json()
    status = fields.Selection([('draft', 'Draft'), ('published', 'Published')], default='draft')
    autosave = fields.Boolean()
    latest = fields.Boolean(index=True)

    def _payload_serialize(self, depth=0, populate=None):
        self.ensure_one()
        document = self.document_id
        collection = document.collection_id
        version = dict(self.version or {})
        fields_conf = document._fields_config(collection)
        loc = document._locale()
        if loc:
            version = schema.flatten_locale(fields_conf, version, loc)
        if depth and populate:
            version = schema.walk_relations(fields_conf, version,
                                            lambda slug, value: populate(slug, value, depth - 1))
        version = document._output_rich_text(fields_conf, version)
        version.setdefault('_status', self.status)
        version['updatedAt'] = _iso(self.write_date)
        version['createdAt'] = _iso(document.create_date)
        if collection.upload:
            version.update({'filename': document.filename, 'mimeType': document.mime_type,
                            'filesize': document.filesize})
        result = {
            'id': self.id,
            'parent': document.id,
            'version': version,
            'createdAt': _iso(self.create_date),
            'updatedAt': _iso(self.write_date),
            'latest': self.latest,
            'autosave': self.autosave,
            'author': self.create_uid and {'id': self.create_uid.id, 'name': self.create_uid.name,
                                           'email': self.create_uid.login},
        }
        if collection.kind == 'global':
            result.pop('parent')
        return result
