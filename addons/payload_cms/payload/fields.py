# -*- coding: utf-8 -*-
"""Field types of the code-first API, named like Odoo's ``fields``.

Each field turns into a Payload field config (``type``, ``required``,
``localized``, ``admin``...)::

    title = fields.Char("Titre", required=True, translate=True)
    description = fields.RichTextEditor("Description", translate=True)   # Lexical
    category = fields.Many2one("categories", "Catégorie")
    tags = fields.Many2many("categories", "Tags", sidebar=True)
    cover = fields.Image("Couverture")                                    # upload -> media
    kind = fields.Selection([("atelier", "Atelier"), ("expo", "Exposition")], "Type", default="atelier")

Common parameters (all optional):

``string``        label (first positional argument, like Odoo)
``required``      required value
``default``       default value
``help``          description shown under the field
``translate``     one value per locale (alias: ``localized``)
``readonly``      read only in the admin
``unique``        unique value (per site in multisite)
``placeholder``   input placeholder
``private``       hidden from anonymous API clients
``condition``     show the field only when ``{"field": "kind", "equals": "expo"}``

Layout parameters (the admin form):

``tab``           name of the tab the field is shown in
``row``           fields sharing the same ``row`` key are displayed side by side
``width``         width in a row ("50%", "33%"...)
``sidebar``       show the field in the sidebar of the edit view
``hidden``        not shown in the admin
"""
import itertools

_counter = itertools.count()

LAYOUT_KEYS = ('tab', 'row', 'width', 'sidebar')


class Field:
    """Base class. ``type`` is the Payload field type."""
    type = None

    def __init__(self, string=None, required=False, default=None, help=None, translate=False, localized=False,
                 readonly=False, unique=False, placeholder=None, private=False, condition=None,
                 tab=None, row=None, width=None, sidebar=False, hidden=False, name=None, admin=None, **extra):
        self._order = next(_counter)
        self.string = string
        self.required = required
        self.default = default
        self.help = help
        self.localized = bool(translate or localized)
        self.readonly = readonly
        self.unique = unique
        self.placeholder = placeholder
        self.private = private
        self.condition = condition
        self.tab = tab
        self.row = row
        self.width = width
        self.sidebar = sidebar
        self.hidden = hidden
        self.name = name  # API key (defaults to the attribute name)
        self.admin_extra = dict(admin or {})
        self.extra = extra

    # ------------------------------------------------------------------
    def _admin(self):
        admin = dict(self.admin_extra)
        if self.help:
            admin['description'] = self.help
        if self.placeholder:
            admin['placeholder'] = self.placeholder
        if self.readonly:
            admin['readOnly'] = True
        if self.hidden:
            admin['hidden'] = True
        if self.width:
            admin['width'] = self.width
        if self.sidebar:
            admin['position'] = 'sidebar'
        if self.condition:
            admin['condition'] = self.condition
        return admin

    def _type_spec(self):
        """Type specific keys (options, relationTo, fields...)."""
        return {}

    def to_spec(self, name):
        spec = {'name': self.name or name, 'type': self.type}
        if self.string:
            spec['label'] = self.string
        if self.required:
            spec['required'] = True
        if self.localized:
            spec['localized'] = True
        if self.unique:
            spec['unique'] = True
        if self.private:
            spec['private'] = True
        if self.default is not None:
            spec['defaultValue'] = self.default
        spec.update(self._type_spec())
        spec.update(self.extra)
        admin = self._admin()
        if admin:
            spec['admin'] = admin
        return spec


# ----------------------------------------------------------------------
# Scalars
# ----------------------------------------------------------------------
class Char(Field):
    """Single line text."""
    type = 'text'


class Text(Field):
    """Multi line text (textarea)."""
    type = 'textarea'


class Email(Field):
    type = 'email'


class RichTextEditor(Field):
    """Rich text edited with Payload's Lexical editor (returned as HTML by the API).

    ``toolbar=False`` hides the fixed toolbar (inline toolbar only)."""
    type = 'richText'

    def __init__(self, string=None, toolbar=True, **kwargs):
        super().__init__(string, **kwargs)
        if not toolbar:
            self.admin_extra['hideFixedToolbar'] = True


Html = RichTextEditor


class Integer(Field):
    type = 'number'

    def __init__(self, string=None, min=None, max=None, **kwargs):
        super().__init__(string, **kwargs)
        self.min, self.max = min, max

    def _type_spec(self):
        spec = {}
        if self.min is not None:
            spec['min'] = self.min
        if self.max is not None:
            spec['max'] = self.max
        return spec


class Float(Integer):
    pass


Number = Float


class Boolean(Field):
    """Checkbox."""
    type = 'checkbox'


class Date(Field):
    """Date only."""
    type = 'date'
    appearance = 'dayOnly'

    def _admin(self):
        admin = super()._admin()
        admin.setdefault('date', {'pickerAppearance': self.appearance})
        return admin


class Datetime(Date):
    """Date and time."""
    appearance = 'dayAndTime'


class Selection(Field):
    """Drop-down list. ``selection`` is a list of ``(value, label)`` (or values).

    ``multiple=True`` allows several values, ``widget='radio'`` shows radio buttons."""
    type = 'select'

    def __init__(self, selection=None, string=None, multiple=False, widget=None, **kwargs):
        super().__init__(string, **kwargs)
        self.selection = selection or []
        self.multiple = multiple
        if widget == 'radio':
            self.type = 'radio'

    def _type_spec(self):
        options = [{'value': o[0], 'label': o[1]} if isinstance(o, (tuple, list)) else o for o in self.selection]
        spec = {'options': options}
        if self.multiple:
            spec['hasMany'] = True
        return spec


class Radio(Selection):
    type = 'radio'


class Slug(Field):
    """URL slug generated from another field (``source``, default: the title)."""
    type = 'slug'

    def __init__(self, string='Slug', source='title', **kwargs):
        kwargs.setdefault('sidebar', True)
        super().__init__(string, **kwargs)
        self.source = source

    def _type_spec(self):
        return {'useAsSlug': self.source}


class Json(Field):
    type = 'json'


class Code(Field):
    type = 'code'

    def __init__(self, string=None, language=None, **kwargs):
        super().__init__(string, **kwargs)
        if language:
            self.admin_extra['language'] = language


class Point(Field):
    """Geographic point [longitude, latitude]."""
    type = 'point'


# ----------------------------------------------------------------------
# Relations
# ----------------------------------------------------------------------
class Many2one(Field):
    """Relationship to one document of another collection (slug)."""
    type = 'relationship'
    many = False

    def __init__(self, comodel=None, string=None, **kwargs):
        super().__init__(string, **kwargs)
        self.comodel = comodel

    def _type_spec(self):
        spec = {'relationTo': self.comodel}
        if self.many:
            spec['hasMany'] = True
        return spec


class Many2many(Many2one):
    """Relationship to several documents of another collection."""
    many = True


class Image(Many2one):
    """Upload (image / file) stored in an upload collection (default: ``media``)."""
    type = 'upload'

    def __init__(self, string=None, comodel='media', multiple=False, **kwargs):
        super().__init__(comodel, string, **kwargs)
        self.many = multiple


File = Image


# ----------------------------------------------------------------------
# Structures
# ----------------------------------------------------------------------
class _Container(Field):
    def __init__(self, string=None, fields=None, **kwargs):
        super().__init__(string, **kwargs)
        self.fields = dict(fields or {})

    def _type_spec(self):
        from .collection import build_fields
        return {'fields': build_fields(self.fields.items())}


class Group(_Container):
    """Nested object: ``fields.Group("Lieu", fields={"city": fields.Char("Ville")})``."""
    type = 'group'


class Array(_Container):
    """Repeatable rows: ``fields.Array("Crédits", fields={...}, row_label="name")``."""
    type = 'array'

    def __init__(self, string=None, fields=None, row_label=None, singular=None, min_rows=None, max_rows=None,
                 collapsed=False, **kwargs):
        super().__init__(string, fields, **kwargs)
        self.row_label, self.singular = row_label, singular
        self.min_rows, self.max_rows = min_rows, max_rows
        if collapsed:
            self.admin_extra['initCollapsed'] = True
        if row_label:
            self.admin_extra['rowLabelField'] = row_label

    def _type_spec(self):
        spec = super()._type_spec()
        if self.singular or self.string:
            spec['labels'] = {'singular': self.singular or self.string, 'plural': self.string or self.singular}
        if self.min_rows:
            spec['minRows'] = self.min_rows
        if self.max_rows:
            spec['maxRows'] = self.max_rows
        return spec


One2many = Array


class Block:
    """A block type of a ``Blocks`` field."""

    def __init__(self, slug, string=None, fields=None, plural=None):
        self.slug, self.string, self.plural = slug, string, plural
        self.fields = dict(fields or {})

    def to_spec(self):
        from .collection import build_fields
        label = self.string or self.slug.replace('-', ' ').title()
        return {'slug': self.slug, 'labels': {'singular': label, 'plural': self.plural or label},
                'fields': build_fields(self.fields.items())}


class Blocks(Field):
    """Layout builder: ``fields.Blocks("Layout", blocks=[fields.Block("cta", "Call to action", fields={...})])``."""
    type = 'blocks'

    def __init__(self, string=None, blocks=None, min_rows=None, max_rows=None, **kwargs):
        super().__init__(string, **kwargs)
        self.blocks = list(blocks or [])
        self.min_rows, self.max_rows = min_rows, max_rows

    def _type_spec(self):
        spec = {'blocks': [b.to_spec() for b in self.blocks]}
        if self.min_rows:
            spec['minRows'] = self.min_rows
        if self.max_rows:
            spec['maxRows'] = self.max_rows
        return spec
