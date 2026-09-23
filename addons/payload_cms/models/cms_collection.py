# -*- coding: utf-8 -*-
import logging
import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from ..tools import multitenancy, schema

_logger = logging.getLogger(__name__)

SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9_-]*$')

# Payload's default image size generated for every upload collection.
DEFAULT_IMAGE_SIZES = [{'name': 'thumbnail', 'width': 400, 'height': 300}]

# Default live preview breakpoints (same as the Payload website template).
DEFAULT_BREAKPOINTS = [
    {'name': 'mobile', 'label': 'Mobile', 'width': 375, 'height': 667},
    {'name': 'tablet', 'label': 'Tablet', 'width': 768, 'height': 1024},
    {'name': 'desktop', 'label': 'Desktop', 'width': 1440, 'height': 900},
]

RESERVED_SLUGS = {'users', 'globals', 'access', 'payload-preferences', 'payload-locked-documents', '_admin'}


class CmsCollection(models.Model):
    """A Payload *Collection* or *Global* declared from the Odoo backend.

    The configuration mirrors Payload's `CollectionConfig` / `GlobalConfig`
    (slug, labels, admin.useAsTitle, versions.drafts, upload, livePreview...)
    and is exposed to the admin SPA through `/api/_admin/config`.
    """
    _name = 'cms.collection'
    _description = 'Payload Collection / Global'
    _inherit = ['mail.thread']
    _order = 'kind, sequence, id'
    _rec_name = 'label'

    sequence = fields.Integer(default=100, help="Order in the navigation (default collections: 10-30, Users: 35).")
    # code-first collections (payload_cms.payload.Collection classes)
    code_module = fields.Char(readonly=True, help="Module whose Python class defines this collection.")
    code_hash = fields.Char(readonly=True, copy=False)
    kind = fields.Selection(
        [('collection', 'Collection'), ('global', 'Global')],
        required=True, default='collection', tracking=True)
    slug = fields.Char(
        required=True, index=True, tracking=True,
        help="URL-safe identifier used by the REST API (e.g. 'pages' -> /api/pages).")
    label = fields.Char(string="Label (plural)", required=True, translate=True, tracking=True)
    label_singular = fields.Char(string="Label (singular)", translate=True)
    description = fields.Text(translate=True, help="Shown under the title of the list view.")
    active = fields.Boolean(default=True)
    hidden = fields.Boolean(help="Hide from the admin navigation (still reachable through the API).")
    admin_group = fields.Char(
        string="Navigation group",
        help="Group label in the admin navigation. Defaults to 'Collections' / 'Globals'.")

    # --- admin ------------------------------------------------------------
    use_as_title = fields.Char(
        string="Use as title", default='title',
        help="Field used as document title in the admin (admin.useAsTitle).")
    default_columns = fields.Char(
        help="Comma separated list of columns shown by default in the list view (admin.defaultColumns).")
    list_searchable_fields = fields.Char(
        help="Comma separated list of fields searched by the list view search bar.")
    default_sort = fields.Char(default='-updatedAt', help="Default sort, Payload syntax (e.g. -createdAt).")
    default_limit = fields.Integer(default=10)
    preview_url = fields.Char(
        help="URL of the 'Preview' button. Placeholders: {slug}, {id}, {collection}, {locale}. "
             "Leave empty to use the built-in preview page.")
    live_preview = fields.Boolean(default=False)
    live_preview_url = fields.Char(
        help="URL loaded in the Live Preview iframe. Placeholders: {slug}, {id}, {collection}. "
             "Leave empty to use the built-in preview page.")
    live_preview_breakpoints = fields.Json(default=lambda self: DEFAULT_BREAKPOINTS)

    # --- versions / drafts -----------------------------------------------
    versions = fields.Boolean(default=True, help="Keep a history of every save (versions).")
    drafts = fields.Boolean(default=False, help="Enable draft / published workflow (versions.drafts).")
    autosave = fields.Boolean(default=False, help="Autosave drafts while editing (versions.drafts.autosave).")
    autosave_interval = fields.Integer(default=2000, help="Autosave interval in milliseconds.")
    max_versions = fields.Integer(default=100, help="Maximum number of versions kept per document (0 = unlimited).")

    # --- upload -----------------------------------------------------------
    upload = fields.Boolean(help="Documents of this collection are files (upload collection).")
    upload_mime_types = fields.Char(default='image/*', help="Comma separated accepted mime types (e.g. image/*,application/pdf).")
    image_sizes = fields.Json(default=lambda self: DEFAULT_IMAGE_SIZES)
    focal_point = fields.Boolean(default=True)
    crop = fields.Boolean(default=True)

    # --- access -----------------------------------------------------------
    public_read = fields.Boolean(
        default=True,
        help="Anonymous API clients can read published documents.")
    multi_tenant = fields.Boolean(
        string="Scoped per site",
        help="Multisite: each document belongs to a site (tenant) and the API filters by the current site.")
    public_create = fields.Boolean(
        help="Anonymous API clients can create documents (e.g. form submissions).")

    field_ids = fields.One2many(
        'cms.field.definition', 'collection_id', string="Fields",
        domain=[('parent_id', '=', False)], copy=True)
    all_field_ids = fields.One2many('cms.field.definition', 'collection_id', string="All fields")
    document_ids = fields.One2many('cms.document', 'collection_id')
    document_count = fields.Integer(compute='_compute_document_count')
    field_count = fields.Integer(compute='_compute_field_count')

    _sql_constraints = [
        ('slug_unique', 'unique(slug, kind)', "The slug must be unique."),
    ]

    @api.depends('all_field_ids')
    def _compute_field_count(self):
        for record in self:
            record.field_count = len(record.all_field_ids)

    def _compute_document_count(self):
        groups = self.env['cms.document']._read_group(
            [('collection_id', 'in', self.ids)], ['collection_id'], ['__count'])
        counts = {collection.id: count for collection, count in groups}
        for record in self:
            record.document_count = counts.get(record.id, 0)

    @api.constrains('slug')
    def _check_slug(self):
        for record in self:
            if not SLUG_RE.match(record.slug or ''):
                raise ValidationError(_("Invalid slug '%s': use lowercase letters, digits, '-' and '_'.", record.slug))
            if record.kind == 'collection' and record.slug in RESERVED_SLUGS:
                raise ValidationError(_("The slug '%s' is reserved.", record.slug))

    @api.constrains('kind', 'upload')
    def _check_global_upload(self):
        for record in self:
            if record.kind == 'global' and record.upload:
                raise ValidationError(_("A global cannot be an upload collection."))

    def action_open_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'payload_cms.admin',
            'name': self.label,
            'params': {'path': '/%s/%s' % ('globals' if self.kind == 'global' else 'collections', self.slug)},
        }

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------
    def _get_by_slug(self, slug, kind='collection'):
        return self.sudo().search([('slug', '=', slug), ('kind', '=', kind)], limit=1)

    def _title_field(self):
        self.ensure_one()
        names = {f.name for f in self.field_ids._flatten_data_fields()}
        if self.use_as_title and (self.use_as_title in names or self.use_as_title in ('id', 'filename')):
            return self.use_as_title
        if self.upload:
            return 'filename'
        return 'id'

    def _is_tenant_scoped(self):
        """True when multi-tenancy is enabled and this collection is scoped per site."""
        self.ensure_one()
        if not self.multi_tenant or self.slug in (multitenancy.TENANTS, multitenancy.NETWORKS):
            return False
        cache = self.env.context.get('payload_mt_enabled')
        if cache is None:
            cache = multitenancy.get_settings(self.env)['enabled']
        return bool(cache)

    def _payload_fields(self):
        """Field config used by the API and the admin: the stored fields, plus the
        `tenant` relationship of the collections scoped per site."""
        self.ensure_one()
        fields_conf = self.field_ids._admin_config()
        if self._is_tenant_scoped() and not any(f.get('name') == 'tenant' for f in fields_conf):
            fields_conf.append(multitenancy.tenant_field(self.kind))
        return fields_conf

    def _admin_config(self):
        """Serialize the collection the way Payload's client config does."""
        self.ensure_one()
        singular = self.label_singular or self.label
        config = {
            'slug': self.slug,
            'labels': {'singular': singular, 'plural': self.label},
            'label': self.label,
            'fields': self._payload_fields(),
            'multiTenant': self._is_tenant_scoped(),
            'sequence': self.sequence,
            'codeModule': self.code_module or False,
            'admin': {
                'useAsTitle': self._title_field(),
                'defaultColumns': [c.strip() for c in (self.default_columns or '').split(',') if c.strip()],
                'listSearchableFields': [c.strip() for c in (self.list_searchable_fields or '').split(',') if c.strip()],
                'group': self.admin_group or False,
                'hidden': self.hidden,
                'description': self.description or '',
                'preview': bool(self.preview_url) or self.live_preview,
                'livePreview': {
                    'enabled': self.live_preview,
                    'url': self.live_preview_url or '',
                    'breakpoints': self.live_preview_breakpoints or DEFAULT_BREAKPOINTS,
                } if self.live_preview else False,
                'previewURL': self.preview_url or '',
            },
            'defaultSort': self.default_sort or '-updatedAt',
            'defaultLimit': self.default_limit or 10,
            'versions': {
                'enabled': self.versions or self.drafts,
                'drafts': {
                    'autosave': {'interval': self.autosave_interval or 2000} if self.autosave else False,
                } if self.drafts else False,
                'maxPerDoc': self.max_versions,
            },
            'timestamps': True,
        }
        if self.kind == 'collection':
            config['upload'] = {
                'mimeTypes': [m.strip() for m in (self.upload_mime_types or '').split(',') if m.strip()],
                'imageSizes': self.image_sizes or [],
                'focalPoint': self.focal_point,
                'crop': self.crop,
            } if self.upload else False
        return config

    # ------------------------------------------------------------------
    # Code-first schema (Payload-like config dictionaries)
    # ------------------------------------------------------------------
    @api.model
    def _sync_schema(self, specs):
        """Create or update collections from Payload-like config dicts.

        Example::

            env['cms.collection']._sync_schema([{
                'slug': 'posts', 'labels': {'singular': 'Post', 'plural': 'Posts'},
                'admin': {'useAsTitle': 'title', 'defaultColumns': ['title', 'slug', '_status']},
                'versions': {'drafts': {'autosave': True}},
                'fields': [{'name': 'title', 'type': 'text', 'required': True}, ...],
            }])
        """
        Field = self.env['cms.field.definition']
        for spec in specs:
            kind = spec.get('kind', 'collection')
            labels = spec.get('labels') or {}
            admin = spec.get('admin') or {}
            versions = spec.get('versions') or {}
            drafts = versions.get('drafts') if isinstance(versions, dict) else False
            upload = spec.get('upload')
            live_preview = admin.get('livePreview')
            vals = {
                'kind': kind,
                'slug': spec['slug'],
                'label': labels.get('plural') or spec.get('label') or spec['slug'].replace('-', ' ').title(),
                'label_singular': labels.get('singular') or spec.get('label') or False,
                'description': admin.get('description') or False,
                'admin_group': admin.get('group') or False,
                'hidden': bool(admin.get('hidden')),
                'use_as_title': admin.get('useAsTitle') or 'title',
                'default_columns': ','.join(admin.get('defaultColumns') or []) or False,
                'list_searchable_fields': ','.join(admin.get('listSearchableFields') or []) or False,
                'default_sort': spec.get('defaultSort') or '-updatedAt',
                'versions': bool(versions) or bool(drafts),
                'drafts': bool(drafts),
                'autosave': bool(isinstance(drafts, dict) and drafts.get('autosave')),
                'upload': bool(upload),
                'live_preview': bool(live_preview),
                'live_preview_url': (live_preview or {}).get('url') if isinstance(live_preview, dict) else False,
                'preview_url': admin.get('previewURL') or False,
                'public_read': spec.get('publicRead', True),
                'public_create': bool(spec.get('publicCreate')),
                'multi_tenant': bool(spec.get('multiTenant')),
                'sequence': spec.get('sequence', 100),
            }
            if isinstance(upload, dict):
                if upload.get('mimeTypes'):
                    vals['upload_mime_types'] = ','.join(upload['mimeTypes'])
                if 'imageSizes' in upload:
                    vals['image_sizes'] = upload['imageSizes']
            collection = self.with_context(active_test=False).search(
                [('slug', '=', spec['slug']), ('kind', '=', kind)], limit=1)
            if collection:
                old_fields = collection.field_ids._admin_config()
                collection.write(vals)
                collection.all_field_ids.unlink()
                Field._create_from_spec(collection, spec.get('fields') or [])
                collection._migrate_localized(old_fields)
            else:
                collection = self.create(vals)
                Field._create_from_spec(collection, spec.get('fields') or [])
        return True

    def _migrate_localized(self, old_fields):
        """After a schema change, collapse the values of fields that are no
        longer localized to their default locale value."""
        from ..tools import localization
        settings = localization.get_settings(self.env)
        codes = [l['code'] for l in settings.get('locales') or [] if l.get('code')]
        if not codes:
            return
        for collection in self:
            new_fields = collection.field_ids._admin_config()
            docs = self.env['cms.document'].sudo().search([('collection_id', '=', collection.id)])
            for doc in docs:
                vals = {}
                for column in ('data', 'published_data'):
                    migrated, changed = schema.delocalize(old_fields, new_fields, doc[column], codes, settings['defaultLocale'])
                    if changed:
                        vals[column] = migrated
                if vals:
                    doc.write(vals)
            versions = self.env['cms.document.version'].sudo().search([('collection_id', '=', collection.id)])
            for version in versions:
                migrated, changed = schema.delocalize(old_fields, new_fields, version.version, codes, settings['defaultLocale'])
                if changed:
                    version.version = migrated

    # text-like fields localized by the "Localized collections" setting
    LOCALIZABLE_TYPES = ('text', 'textarea', 'richText', 'slug')

    def _set_localized(self, localized):
        """Localize (text, textarea, rich text, slug fields) or un-localize (all
        fields) the collections of ``self``."""
        for collection in self:
            old_fields = collection.field_ids._admin_config()
            if localized:
                from ..tools.translate import UNTRANSLATABLE_NAMES
                fields = collection.all_field_ids.filtered(
                    lambda f: f.field_type in self.LOCALIZABLE_TYPES and not f.localized
                    and (f.name or '').lower() not in UNTRANSLATABLE_NAMES)
                fields.write({'localized': True})
            else:
                collection.all_field_ids.filtered('localized').write({'localized': False})
                collection._migrate_localized(old_fields)

    # ------------------------------------------------------------------
    # Code-first collections (odoo.addons.payload_cms.payload.Collection)
    # ------------------------------------------------------------------
    def _register_hook(self):
        super()._register_hook()
        try:
            with self.env.cr.savepoint():
                self._payload_sync_code()
        except Exception:  # noqa: BLE001 - never prevent the server from starting
            _logger.exception("Payload CMS: cannot synchronise the code-first collections")

    @api.model
    def _payload_sync_code(self, force=False):
        """Create / update the collections declared as Python classes by the
        installed modules (only when their definition changed)."""
        from ..payload import registered
        classes = registered()
        if not classes:
            return
        modules = {cls._module for cls in classes}
        installed = set(self.env['ir.module.module'].sudo().search(
            [('name', 'in', list(modules)), ('state', 'in', ('installed', 'to upgrade', 'to install'))]).mapped('name'))
        classes = sorted((c for c in classes if c._module in installed), key=lambda c: (c._kind, c._sequence, c._name))
        Collection = self.sudo().with_context(active_test=False)
        # 1. create the missing collections first (relations between them)
        for cls in classes:
            if not Collection.search([('slug', '=', cls._name), ('kind', '=', cls._kind)], limit=1):
                spec = dict(cls._spec(), fields=[])
                Collection._sync_schema([spec])
        # 2. schema of the changed classes
        for cls in classes:
            record = Collection.search([('slug', '=', cls._name), ('kind', '=', cls._kind)], limit=1)
            digest = cls._hash()
            if not force and record.code_hash == digest and record.code_module == cls._module:
                continue
            _logger.info("Payload CMS: synchronising %s '%s' from module %s", cls._kind, cls._name, cls._module)
            Collection._sync_schema([cls._spec()])
            record.write({'code_module': cls._module, 'code_hash': digest})

    @api.model
    def _payload_default_sequences(self):
        """Navigation order: Pages, Posts, Media, Users, then the other
        collections (code-first modules, builder)."""
        defaults = {'pages': 10, 'posts': 20, 'media': 30}
        for record in self.sudo().with_context(active_test=False).search([('kind', '=', 'collection')]):
            if record.slug in defaults:
                if record.sequence != defaults[record.slug]:
                    record.sequence = defaults[record.slug]
            elif record.sequence <= 40 and not record.code_module:
                record.sequence = 100
        return True

    @api.model
    def _install_multitenancy(self):
        """Multisite: `networks` + `tenants` collections."""
        existing = set(self.with_context(active_test=False).search([('kind', '=', 'collection')]).mapped('slug'))
        self._sync_schema([s for s in multitenancy.NETWORK_SCHEMA if s['slug'] not in existing])
        return True

    @api.model
    def _install_form_builder(self):
        """Payload's form builder plugin: `forms` + `form-submissions` collections."""
        from ..tools.form_builder import FORM_BUILDER_SCHEMA
        existing = set(self.with_context(active_test=False).search([('kind', '=', 'collection')]).mapped('slug'))
        self._sync_schema([s for s in FORM_BUILDER_SCHEMA if s['slug'] not in existing])
        # the notification emails (recipients...) are never exposed to anonymous clients
        emails = self.env['cms.field.definition'].search([
            ('collection_id.slug', '=', 'forms'), ('parent_id', '=', False), ('name', '=', 'emails')])
        for field in emails.filtered(lambda f: not (f.config or {}).get('private')):
            field.config = dict(field.config or {}, private=True)
        return True

    @api.model
    def _install_default_schema(self):
        from ..tools.default_schema import DEFAULT_SCHEMA
        existing = set(self.with_context(active_test=False).search([]).mapped('slug'))
        self._sync_schema([s for s in DEFAULT_SCHEMA if s['slug'] not in existing])
        return True
