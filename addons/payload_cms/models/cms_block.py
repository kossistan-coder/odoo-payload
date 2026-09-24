# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .cms_field_definition import NAME_RE, _humanize

BLOCK_SLUG_RE = re.compile(r'^[A-Za-z0-9_-]+$')
# keys of a block row owned by Payload
RESERVED_NAMES = {'id', 'blockType', 'blockName'}

# Button / link sub fields (same shape as the links of the default schema)
BUTTON_APPEARANCES = [
    {'value': 'primary', 'label': 'Primary'},
    {'value': 'secondary', 'label': 'Secondary'},
    {'value': 'outline', 'label': 'Outline'},
    {'value': 'link', 'label': 'Link'},
]


class CmsBlock(models.Model):
    """A reusable layout block built in "Configuration → Blocks".

    A block is an assembly of elementary components (text, rich text, button,
    image, list...) converted to Payload fields. It is added to the ``blocks``
    fields listed in ``targets`` (``'<collection slug>.<blocks field>'``, by
    default the ``layout`` of Pages) like the blocks declared inline, so the
    API, the validation and the admin handle it the same way.

    ``components`` keeps the rows edited in the admin::

        [{'blockType': 'text', 'name': 'title', 'label': 'Title', 'required': True, 'localized': True},
         {'blockType': 'button', 'name': 'cta', 'label': 'Call to action'},
         {'blockType': 'list', 'name': 'cards', 'components': [...]}]
    """
    _name = 'cms.block'
    _description = 'Payload reusable block'
    _order = 'sequence, id'
    _rec_name = 'label'

    sequence = fields.Integer(default=100)
    active = fields.Boolean(default=True)
    slug = fields.Char(required=True, index=True, help="Block type stored in the rows (blockType).")
    label = fields.Char(required=True, translate=True)
    label_plural = fields.Char(translate=True)
    description = fields.Text(translate=True)
    section_header = fields.Boolean(
        default=True, help="Starts the block with a title, a subtitle and a description (SectionBlock).")
    targets = fields.Json(
        default=lambda self: ['pages.layout'],
        help="Blocks fields offering this block: '<collection slug>.<blocks field name>'.")
    components = fields.Json(default=lambda self: [])

    _sql_constraints = [
        ('slug_unique', 'unique(slug)', "The block slug must be unique."),
    ]

    @api.constrains('slug', 'components', 'section_header')
    def _check_components(self):
        for record in self:
            if not BLOCK_SLUG_RE.match(record.slug or ''):
                raise ValidationError(_("Invalid block slug '%s': use letters, digits, '-' and '_'.", record.slug))
            reserved = {'title', 'subtitle', 'description'} if record.section_header else set()
            _check_rows(record.components or [], reserved, record.slug)

    @api.constrains('slug', 'targets')
    def _check_targets(self):
        """A block cannot use the slug of a block declared inline in the same field."""
        Field = self.env['cms.field.definition'].sudo()
        for record in self:
            for slug, name in record._target_pairs():
                inline = Field.search([
                    ('collection_id.slug', '=', slug), ('field_type', '=', 'block'), ('name', '=', record.slug),
                    ('parent_id.field_type', '=', 'blocks'), ('parent_id.name', '=', name)], limit=1)
                if inline:
                    raise ValidationError(_("The field '%(field)s' of '%(collection)s' already has a block '%(slug)s'.",
                                            field=name, collection=slug, slug=record.slug))

    def unlink(self):
        if self.env.context.get('payload_seeder'):
            raise UserError(_("Seeder '%s': deleting CMS data is not allowed (seeders only create or update).",
                              self.env.context['payload_seeder']))
        for record in self:
            count = record._usage_count()
            if count:
                raise UserError(_("The block '%(label)s' is used by %(count)s document(s): remove it from their "
                                  "layout first, or archive it.", label=record.label, count=count))
        return super().unlink()

    def _target_pairs(self):
        self.ensure_one()
        return [tuple(t.split('.', 1)) for t in (self.targets or []) if isinstance(t, str) and '.' in t]

    def _usage_count(self):
        """Documents (current or published data) holding a row of this block."""
        self.ensure_one()
        needle = '%%"blockType": "%s"%%' % self.slug.replace('%', r'\%').replace('_', r'\_')
        self.env['cms.document'].flush_model(['data', 'published_data'])
        self.env.cr.execute(
            "SELECT count(*) FROM cms_document WHERE data::text LIKE %s OR published_data::text LIKE %s",
            (needle, needle))
        return self.env.cr.fetchone()[0]

    # ------------------------------------------------------------------
    # Payload config
    # ------------------------------------------------------------------
    def _fields_config(self):
        self.ensure_one()
        header = []
        if self.section_header:
            header = [
                {'name': 'title', 'type': 'text', 'label': 'Title', 'required': True, 'localized': True, 'admin': {}},
                {'name': 'subtitle', 'type': 'text', 'label': 'Subtitle', 'localized': True, 'admin': {}},
                {'name': 'description', 'type': 'textarea', 'label': 'Description', 'localized': True, 'admin': {}},
            ]
        return header + components_to_fields(self.components or [])

    def _block_config(self):
        self.ensure_one()
        return {
            'slug': self.slug,
            'labels': {'singular': self.label, 'plural': self.label_plural or self.label},
            'admin': {'description': self.description} if self.description else {},
            'fields': self._fields_config(),
            'custom': True,
            'archived': not self.active,
        }

    @api.model
    def _blocks_for(self, collection_slug, field_name):
        """Configs of the reusable blocks offered by the blocks field ``collection_slug.field_name``."""
        key = '%s.%s' % (collection_slug, field_name)
        # archived blocks stay in the config: the rows already written are kept
        blocks = self.sudo().with_context(active_test=False).search([]).filtered(lambda b: key in (b.targets or []))
        return [block._block_config() for block in blocks]


# ----------------------------------------------------------------------
# components -> Payload fields
# ----------------------------------------------------------------------
def _check_rows(rows, reserved, block):
    seen = set(reserved)
    for row in rows:
        name = (row.get('name') or '').strip()
        if not NAME_RE.match(name):
            raise ValidationError(_("Block '%(block)s': invalid component name '%(name)s' (letters, digits and _ only).",
                                    block=block, name=name))
        if name in RESERVED_NAMES or name in seen:
            raise ValidationError(_("Block '%(block)s': the name '%(name)s' is already used.", block=block, name=name))
        seen.add(name)
        if row.get('blockType') in ('image', 'relationship') and not row.get('relationTo'):
            raise ValidationError(_("Block '%(block)s': the component '%(name)s' needs a collection.", block=block, name=name))
        if row.get('blockType') == 'list':
            _check_rows(row.get('components') or [], set(), block)


def _admin(row, **extra):
    admin = {'description': row.get('description') or None, 'placeholder': row.get('placeholder') or None,
             'width': row.get('width') or None, **extra}
    return {k: v for k, v in admin.items() if v}


def _default(row, cast):
    raw = row.get('defaultValue')
    if raw in (None, ''):
        return {}
    try:
        return {'defaultValue': cast(raw)}
    except (TypeError, ValueError):
        return {}


def _bool(value):
    return value if isinstance(value, bool) else str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def components_to_fields(rows):
    """Admin component rows -> Payload field configs."""
    result = []
    for row in rows or []:
        ctype = row.get('blockType')
        name = (row.get('name') or '').strip()
        if not ctype or not name:
            continue
        label = row.get('label') or _humanize(name)
        base = {'name': name, 'label': label, 'required': bool(row.get('required'))}
        localized = {'localized': True} if row.get('localized') else {}
        if ctype in ('text', 'textarea', 'email'):
            field = dict(base, type=ctype, admin=_admin(row), **localized, **_default(row, str))
        elif ctype == 'richText':
            field = dict(base, type='richText', admin=_admin(row), **localized)
        elif ctype == 'number':
            field = dict(base, type='number', admin=_admin(row), **_default(row, float))
            for key in ('min', 'max'):
                if row.get(key) not in (None, ''):
                    field[key] = row[key]
        elif ctype == 'checkbox':
            field = dict(base, type='checkbox', admin=_admin(row), **_default(row, _bool))
        elif ctype == 'date':
            field = dict(base, type='date', admin=_admin(row))
        elif ctype == 'select':
            options = [{'value': o.get('value'), 'label': o.get('label') or o.get('value')}
                       for o in row.get('options') or [] if o.get('value')]
            field = dict(base, type='select', options=options, hasMany=bool(row.get('hasMany')), admin=_admin(row),
                         **_default(row, str))
        elif ctype == 'image':
            field = dict(base, type='upload', relationTo=row.get('relationTo') or 'media', admin=_admin(row))
        elif ctype == 'relationship':
            field = dict(base, type='relationship', relationTo=row.get('relationTo'),
                         hasMany=bool(row.get('hasMany')), admin=_admin(row))
        elif ctype == 'button':
            required = base['required']
            field = {
                'name': name, 'type': 'group', 'label': label, 'admin': _admin(row),
                'fields': [
                    {'type': 'row', 'fields': [
                        {'name': 'label', 'type': 'text', 'label': 'Text', 'required': required,
                         'admin': _admin({'width': '50%', 'placeholder': row.get('placeholder')}), **localized},
                        {'name': 'url', 'type': 'text', 'label': 'Link', 'required': required,
                         'admin': {'width': '50%', 'placeholder': 'https://… or /page'}},
                    ]},
                    {'type': 'row', 'fields': [
                        {'name': 'appearance', 'type': 'select', 'label': 'Appearance', 'options': BUTTON_APPEARANCES,
                         'defaultValue': row.get('appearance') or 'primary', 'admin': {'width': '50%', 'isClearable': False}},
                        {'name': 'newTab', 'type': 'checkbox', 'label': 'Open in new tab', 'admin': {'width': '50%'}},
                    ]},
                ],
            }
        elif ctype == 'list':
            field = dict(base, type='array', fields=components_to_fields(row.get('components')),
                         admin=_admin(row, initCollapsed=bool(row.get('initCollapsed'))))
            if row.get('singular'):
                field['labels'] = {'singular': row['singular'], 'plural': label}
            for key in ('minRows', 'maxRows'):
                if row.get(key):
                    field[key] = int(row[key])
        else:
            continue
        result.append(field)
    return result
