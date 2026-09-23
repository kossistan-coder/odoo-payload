# -*- coding: utf-8 -*-
"""Code-first collections, written like Odoo models::

    from odoo.addons.payload_cms.payload import Collection, fields

    class Atelier(Collection):
        _name = 'ateliers'                  # slug: /api/ateliers
        _description = "Ateliers et expositions"
        _label = 'Atelier'                  # singular label (plural: _label_plural)
        _rec_name = 'title'                 # admin.useAsTitle
        _order = '-date_begin'              # default sort
        _drafts = True                      # draft / published + versions

        title = fields.Char("Titre", required=True, translate=True)
        description = fields.RichTextEditor("Description", translate=True, tab="Contenu")

Every class of an installed module is synchronised with ``cms.collection`` when
the registry is loaded (module install / update / server start), only when its
definition changed.
"""
import hashlib
import json

from .fields import Field

# slug/kind -> class, filled when the modules are imported
_registry = {}


def registered():
    return list(_registry.values())


def _fields_of(cls):
    items = {}
    for klass in reversed(cls.__mro__):
        for name, value in vars(klass).items():
            if isinstance(value, Field):
                items[name] = value
    return sorted(items.items(), key=lambda item: item[1]._order)


def build_fields(items):
    """Ordered (name, Field) -> Payload field configs, with tabs, rows and sidebar.

    Fields without ``tab`` come first, then the tabs (in the order they first
    appear), then the sidebar fields. Consecutive fields sharing a ``row`` key
    are wrapped in a row (equal widths unless ``width`` is given)."""
    items = list(items)
    main = [(n, f) for n, f in items if not f.sidebar]
    sidebar = [(n, f) for n, f in items if f.sidebar]
    untabbed = [(n, f) for n, f in main if not f.tab]
    tabs = {}
    for name, field in main:
        if field.tab:
            tabs.setdefault(field.tab, []).append((name, field))
    result = _rows(untabbed)
    if tabs:
        result.append({'type': 'tabs', 'tabs': [{'label': label, 'fields': _rows(fields)} for label, fields in tabs.items()]})
    return result + _rows(sidebar)


def _rows(items):
    result, index = [], 0
    while index < len(items):
        name, field = items[index]
        if not field.row:
            result.append(field.to_spec(name))
            index += 1
            continue
        group = []
        while index < len(items) and items[index][1].row == field.row:
            group.append(items[index])
            index += 1
        if len(group) == 1:
            result.append(group[0][1].to_spec(group[0][0]))
            continue
        width = '%d%%' % (100 // len(group))
        specs = []
        for n, f in group:
            spec = f.to_spec(n)
            admin = spec.setdefault('admin', {})
            admin.setdefault('width', width)
            specs.append(spec)
        result.append({'type': 'row', 'fields': specs})
    return result


class _Base:
    _kind = 'collection'
    _name = None               # slug (required)
    _description = None        # admin description
    _label = None              # singular label
    _label_plural = None       # plural label (collections)
    _group = None              # navigation group (default: Collections / Globals)
    _sequence = 100            # order in the navigation (default collections: 10-30, Users: 35)
    _hidden = False            # hidden from the navigation
    _drafts = False            # draft / published workflow
    _autosave = False          # autosave drafts
    _versions = True           # keep versions
    _max_versions = None
    _public_read = True        # anonymous API clients can read published documents
    _live_preview_url = None   # e.g. 'https://www.site.com/{slug}?locale={locale}'
    _preview_url = None
    _multi_tenant = False      # multisite: scoped per site

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__dict__.get('_name'):
            module = cls.__module__.split('.')[2] if cls.__module__.startswith('odoo.addons.') else cls.__module__
            cls._module = module
            _registry[(cls._kind, cls._name)] = cls

    @classmethod
    def _fields(cls):
        return _fields_of(cls)

    @classmethod
    def _spec(cls):
        admin = {}
        if cls._description:
            admin['description'] = cls._description
        if cls._group:
            admin['group'] = cls._group
        if cls._hidden:
            admin['hidden'] = True
        if cls._live_preview_url is not None:
            admin['livePreview'] = {'url': cls._live_preview_url}
        if cls._preview_url:
            admin['previewURL'] = cls._preview_url
        versions = False
        if cls._drafts:
            versions = {'drafts': {'autosave': True} if cls._autosave else True}
        elif cls._versions:
            versions = {'maxPerDoc': cls._max_versions or 100}
        return {
            'kind': cls._kind,
            'slug': cls._name,
            'labels': {'singular': cls._label or cls._name.replace('-', ' ').title(),
                       'plural': cls._label_plural or cls._label or cls._name.replace('-', ' ').title()},
            'admin': admin,
            'versions': versions,
            'publicRead': cls._public_read,
            'multiTenant': cls._multi_tenant,
            'sequence': cls._sequence,
            'fields': build_fields(cls._fields()),
        }

    @classmethod
    def _hash(cls):
        return hashlib.sha1(json.dumps(cls._spec(), sort_keys=True, default=str).encode()).hexdigest()


class Collection(_Base):
    """A Payload collection (many documents): ``/api/{_name}``."""
    _kind = 'collection'
    _rec_name = 'title'        # admin.useAsTitle
    _order = None              # default sort, e.g. '-date_begin'
    _columns = None            # default list columns
    _search = None             # fields searched by the list search bar
    _upload = False            # upload collection (files / images)
    _public_create = False     # anonymous API clients can create (form submissions...)

    @classmethod
    def _spec(cls):
        spec = super()._spec()
        admin = spec['admin']
        admin['useAsTitle'] = cls._rec_name
        if cls._columns:
            admin['defaultColumns'] = list(cls._columns)
        if cls._search:
            admin['listSearchableFields'] = list(cls._search)
        if cls._order:
            spec['defaultSort'] = cls._order
        if cls._upload:
            spec['upload'] = cls._upload if isinstance(cls._upload, dict) else True
        spec['publicCreate'] = cls._public_create
        return spec


class Global(_Base):
    """A Payload global (single document: header, footer, settings): ``/api/globals/{_name}``."""
    _kind = 'global'

    @classmethod
    def _spec(cls):
        spec = super()._spec()
        spec['label'] = cls._label or cls._name.replace('-', ' ').title()
        return spec
