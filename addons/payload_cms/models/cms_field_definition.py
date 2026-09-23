# -*- coding: utf-8 -*-
import json
import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

FIELD_TYPES = [
    ('text', 'Text'),
    ('textarea', 'Textarea'),
    ('email', 'Email'),
    ('number', 'Number'),
    ('checkbox', 'Checkbox'),
    ('date', 'Date'),
    ('select', 'Select'),
    ('radio', 'Radio group'),
    ('richText', 'Rich text (Lexical)'),
    ('upload', 'Upload'),
    ('relationship', 'Relationship'),
    ('json', 'JSON'),
    ('code', 'Code'),
    ('slug', 'Slug'),
    ('array', 'Array'),
    ('group', 'Group'),
    ('blocks', 'Blocks'),
    ('block', 'Block (definition inside a blocks field)'),
    ('row', 'Row (layout)'),
    ('collapsible', 'Collapsible (layout)'),
    ('tabs', 'Tabs (layout)'),
    ('tab', 'Tab (inside tabs)'),
]

# Types that never store data themselves: their children are stored at the parent level.
PRESENTATIONAL_TYPES = {'row', 'collapsible', 'tabs'}
# Types whose children are stored in a nested object / list.
NESTING_TYPES = {'array', 'group', 'blocks', 'block'}
NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


class CmsFieldDefinition(models.Model):
    """A field of a collection, mirroring Payload's field config.

    Fields are recursive: `array`, `group`, `row`, `collapsible`, `tabs`/`tab`
    contain sub fields, and a `blocks` field contains `block` definitions which
    themselves contain fields.
    """
    _name = 'cms.field.definition'
    _description = 'Payload field'
    _order = 'sequence, id'
    _parent_store = True

    sequence = fields.Integer(default=10)
    collection_id = fields.Many2one(
        'cms.collection', required=True, ondelete='cascade', index=True,
        compute='_compute_collection_id', store=True, readonly=False, precompute=True, recursive=True)
    parent_id = fields.Many2one('cms.field.definition', ondelete='cascade', index=True)
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('cms.field.definition', 'parent_id', string="Sub fields", copy=True)

    name = fields.Char(
        string="Name",
        help="Property name in the stored JSON (camelCase like Payload, e.g. 'heroImage'). "
             "For a block, this is the block slug.")
    label = fields.Char(translate=True)
    field_type = fields.Selection(FIELD_TYPES, string="Type", required=True, default='text')
    required = fields.Boolean()
    unique = fields.Boolean()
    localized = fields.Boolean(help="Store one value per locale (requires localization to be enabled).")
    read_only = fields.Boolean()
    hidden = fields.Boolean(help="Hidden from the admin UI (still stored and returned by the API).")
    position = fields.Selection([('main', 'Main'), ('sidebar', 'Sidebar')], default='main')
    width = fields.Char(help="CSS width inside a row (e.g. 50%).")
    description = fields.Char(translate=True)
    placeholder = fields.Char(translate=True)
    default_value = fields.Char(help="Default value, JSON encoded (e.g. \"draft\", 10, true).")
    has_many = fields.Boolean(string="Has many")
    relation_to_id = fields.Many2one(
        'cms.collection', string="Relation to", domain=[('kind', '=', 'collection')], ondelete='restrict')
    options = fields.Text(
        help="Select / radio options, one per line: 'value' or 'value:Label'.")
    min_value = fields.Float(string="Min")
    max_value = fields.Float(string="Max")
    min_rows = fields.Integer()
    max_rows = fields.Integer()
    slug_source = fields.Char(default='title', help="Field the slug is generated from.")
    initially_collapsed = fields.Boolean()
    config = fields.Json(default=lambda self: {}, help="Extra configuration (free JSON).")

    @api.depends('name', 'label', 'field_type')
    def _compute_display_name(self):
        types = dict(FIELD_TYPES)
        for record in self:
            record.display_name = record.name or record.label or types.get(record.field_type, record.field_type)

    @api.depends('parent_id.collection_id')
    def _compute_collection_id(self):
        for record in self:
            if record.parent_id:
                record.collection_id = record.parent_id.collection_id

    @api.constrains('name', 'field_type')
    def _check_name(self):
        for record in self:
            if record.field_type in PRESENTATIONAL_TYPES:
                continue
            if record.field_type == 'tab' and not record.name:
                continue
            if not record.name:
                raise ValidationError(_("A field of type '%s' requires a name.", record.field_type))
            if record.field_type == 'block':
                if not re.match(r'^[A-Za-z0-9_-]+$', record.name):
                    raise ValidationError(_("Invalid block slug '%s'.", record.name))
            elif not NAME_RE.match(record.name):
                raise ValidationError(_("Invalid field name '%s' (letters, digits and _ only).", record.name))

    @api.constrains('field_type', 'relation_to_id')
    def _check_relation(self):
        for record in self:
            if record.field_type in ('upload', 'relationship') and not record.relation_to_id:
                raise ValidationError(_("Field '%s' needs a 'Relation to' collection.", record.name))
            if record.field_type == 'upload' and not record.relation_to_id.upload:
                raise ValidationError(_("Field '%s' must relate to an upload collection.", record.name))

    @api.constrains('parent_id', 'field_type')
    def _check_parent(self):
        for record in self:
            parent = record.parent_id
            if record.field_type == 'block' and parent.field_type != 'blocks':
                raise ValidationError(_("A block definition must be inside a blocks field."))
            if parent.field_type == 'blocks' and record.field_type != 'block':
                raise ValidationError(_("A blocks field can only contain block definitions."))
            if record.field_type == 'tab' and parent.field_type != 'tabs':
                raise ValidationError(_("A tab must be inside a tabs field."))
            if parent.field_type == 'tabs' and record.field_type != 'tab':
                raise ValidationError(_("A tabs field can only contain tabs."))
            if parent and parent.field_type not in NESTING_TYPES | PRESENTATIONAL_TYPES | {'tab'}:
                raise ValidationError(_("A '%s' field cannot contain sub fields.", parent.field_type))

    @api.constrains('name', 'parent_id', 'collection_id')
    def _check_unique_name(self):
        for record in self:
            if not record.name or record.field_type in PRESENTATIONAL_TYPES:
                continue
            siblings = record._data_siblings()
            if len(siblings.filtered(lambda f: f.name == record.name)) > 1:
                raise ValidationError(_("Duplicate field name '%s'.", record.name))

    def _data_siblings(self):
        """Fields stored in the same JSON object as this field."""
        self.ensure_one()
        container = self.parent_id
        while container and (container.field_type in PRESENTATIONAL_TYPES
                             or (container.field_type == 'tab' and not container.name)):
            container = container.parent_id
        if container:
            roots = container.child_ids
        else:
            roots = self.collection_id.field_ids
        return roots._flatten_data_fields()

    def _flatten_data_fields(self):
        """Return the fields that own a key in the current JSON object
        (row/collapsible/unnamed tabs are transparent)."""
        result = self.browse()
        for field in self:
            if field.field_type in PRESENTATIONAL_TYPES or (field.field_type == 'tab' and not field.name):
                result |= field.child_ids._flatten_data_fields()
            else:
                result |= field
        return result

    def _parse_options(self):
        self.ensure_one()
        opts = []
        for line in (self.options or '').splitlines():
            line = line.strip()
            if not line:
                continue
            value, _sep, label = line.partition(':')
            opts.append({'value': value.strip(), 'label': (label or value).strip()})
        return opts

    def _default(self):
        self.ensure_one()
        if not self.default_value:
            return None
        try:
            return json.loads(self.default_value)
        except ValueError:
            return self.default_value

    def _admin_config(self):
        """Serialize fields to a Payload-like field config list."""
        result = []
        for field in self:
            conf = {
                'type': field.field_type,
                'label': field.label or (field.name and _humanize(field.name)) or '',
                'required': field.required,
                'admin': {
                    'position': field.position if field.position == 'sidebar' else None,
                    'width': field.width or None,
                    'description': field.description or None,
                    'placeholder': field.placeholder or None,
                    'readOnly': field.read_only,
                    'hidden': field.hidden,
                    'initCollapsed': field.initially_collapsed,
                },
            }
            if field.name:
                conf['name'] = field.name
            if field.unique:
                conf['unique'] = True
            if field.localized:
                conf['localized'] = True
            default = field._default()
            if default is not None:
                conf['defaultValue'] = default
            ftype = field.field_type
            if ftype in ('select', 'radio'):
                conf['options'] = field._parse_options()
                conf['hasMany'] = field.has_many if ftype == 'select' else False
            if ftype in ('upload', 'relationship'):
                conf['relationTo'] = field.relation_to_id.slug
                conf['hasMany'] = field.has_many
            if ftype == 'number':
                if field.min_value:
                    conf['min'] = field.min_value
                if field.max_value:
                    conf['max'] = field.max_value
            if ftype in ('array', 'blocks'):
                if field.min_rows:
                    conf['minRows'] = field.min_rows
                if field.max_rows:
                    conf['maxRows'] = field.max_rows
            if ftype == 'slug':
                conf['useAsSlug'] = field.slug_source or 'title'
                conf['unique'] = True
            if ftype == 'blocks':
                conf['blocks'] = [{
                    'slug': block.name,
                    'labels': {'singular': block.label or _humanize(block.name),
                               'plural': block.label or _humanize(block.name)},
                    'fields': block.child_ids._admin_config(),
                } for block in field.child_ids]
            elif ftype == 'tabs':
                conf['tabs'] = [{
                    'name': tab.name or None,
                    'label': tab.label or (tab.name and _humanize(tab.name)) or '',
                    'description': tab.description or None,
                    'fields': tab.child_ids._admin_config(),
                } for tab in field.child_ids]
            elif field.child_ids:
                conf['fields'] = field.child_ids._admin_config()
            if field.config:
                conf.update({k: v for k, v in field.config.items() if k != 'admin'})
                conf['admin'].update(field.config.get('admin') or {})
            conf['admin'] = {k: v for k, v in conf['admin'].items() if v not in (None, False)}
            result.append(conf)
        return result

    # ------------------------------------------------------------------
    # Code-first schema
    # ------------------------------------------------------------------
    @api.model
    def _create_from_spec(self, collection, specs, parent=None):
        Collection = self.env['cms.collection']
        for seq, spec in enumerate(specs, start=1):
            admin = spec.get('admin') or {}
            ftype = spec['type']
            vals = {
                'collection_id': collection.id,
                'parent_id': parent.id if parent else False,
                'sequence': seq * 10,
                'name': spec.get('name') or spec.get('slug') or False,
                'label': spec.get('label') or (spec.get('labels') or {}).get('singular') or False,
                'field_type': ftype,
                'required': bool(spec.get('required')),
                'unique': bool(spec.get('unique')),
                'localized': bool(spec.get('localized')),
                'has_many': bool(spec.get('hasMany')),
                'position': 'sidebar' if admin.get('position') == 'sidebar' else 'main',
                'width': admin.get('width') or False,
                'description': admin.get('description') or spec.get('description') or False,
                'placeholder': admin.get('placeholder') or False,
                'read_only': bool(admin.get('readOnly')),
                'hidden': bool(admin.get('hidden')),
                'initially_collapsed': bool(admin.get('initCollapsed')),
                'min_rows': spec.get('minRows') or 0,
                'max_rows': spec.get('maxRows') or 0,
                'min_value': spec.get('min') or 0,
                'max_value': spec.get('max') or 0,
            }
            # admin options without a dedicated column (condition, rowLabelField...)
            extra_admin = {k: v for k, v in admin.items() if k not in KNOWN_ADMIN_KEYS}
            config = {k: spec[k] for k in EXTRA_KEYS if spec.get(k)}
            if extra_admin:
                config['admin'] = extra_admin
            if config:
                vals['config'] = config
            if 'defaultValue' in spec:
                vals['default_value'] = json.dumps(spec['defaultValue'])
            if spec.get('options'):
                vals['options'] = '\n'.join(
                    o if isinstance(o, str) else '%s:%s' % (o['value'], o.get('label') or o['value'])
                    for o in spec['options'])
            if spec.get('relationTo'):
                related = Collection.with_context(active_test=False).search(
                    [('slug', '=', spec['relationTo']), ('kind', '=', 'collection')], limit=1)
                if not related:
                    raise ValidationError(_("Unknown collection '%s' in relationTo.", spec['relationTo']))
                vals['relation_to_id'] = related.id
            if ftype == 'slug':
                vals['slug_source'] = spec.get('useAsSlug') or 'title'
                vals['position'] = 'sidebar' if admin.get('position', 'sidebar') == 'sidebar' else 'main'
            field = self.create(vals)
            if ftype == 'blocks':
                for bseq, block in enumerate(spec.get('blocks') or [], start=1):
                    labels = block.get('labels') or {}
                    block_field = self.create({
                        'collection_id': collection.id,
                        'parent_id': field.id,
                        'sequence': bseq * 10,
                        'name': block['slug'],
                        'label': labels.get('singular') or False,
                        'field_type': 'block',
                    })
                    self._create_from_spec(collection, block.get('fields') or [], block_field)
            elif ftype == 'tabs':
                for tseq, tab in enumerate(spec.get('tabs') or [], start=1):
                    tab_field = self.create({
                        'collection_id': collection.id,
                        'parent_id': field.id,
                        'sequence': tseq * 10,
                        'name': tab.get('name') or False,
                        'label': tab.get('label') or False,
                        'description': tab.get('description') or False,
                        'field_type': 'tab',
                    })
                    self._create_from_spec(collection, tab.get('fields') or [], tab_field)
            elif spec.get('fields'):
                self._create_from_spec(collection, spec['fields'], field)
        return True


# field options kept as-is in `config`: `private` = hidden from anonymous API clients
EXTRA_KEYS = ('private',)
KNOWN_ADMIN_KEYS = {'position', 'width', 'description', 'placeholder', 'readOnly', 'hidden', 'initCollapsed'}


def _humanize(name):
    """'heroImage' -> 'Hero Image', 'meta_title' -> 'Meta Title' (Payload's toWords)."""
    words = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', name or '').replace('_', ' ').replace('-', ' ')
    return ' '.join(w[:1].upper() + w[1:] for w in words.split())
