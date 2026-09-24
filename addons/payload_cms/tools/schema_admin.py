# -*- coding: utf-8 -*-
"""Conversion between `cms.collection` / `cms.field.definition` records and the
documents edited by the "Configuration" views of the admin (schema builder).

Fields are exposed as Payload `blocks` rows (one block type per field type),
nested through `fields`, `blocks` and `tabs` keys.
"""
import json

from .schema import new_row_id

COLLECTION_KEYS = {
    # doc key: (record field, kind)
    'label': ('label', 'char'),
    'labelSingular': ('label_singular', 'char'),
    'slug': ('slug', 'char'),
    'adminGroup': ('admin_group', 'char'),
    'description': ('description', 'char'),
    'hidden': ('hidden', 'bool'),
    'useAsTitle': ('use_as_title', 'char'),
    'defaultColumns': ('default_columns', 'char'),
    'listSearchableFields': ('list_searchable_fields', 'char'),
    'defaultSort': ('default_sort', 'char'),
    'defaultLimit': ('default_limit', 'int'),
    'versions': ('versions', 'bool'),
    'drafts': ('drafts', 'bool'),
    'autosave': ('autosave', 'bool'),
    'autosaveInterval': ('autosave_interval', 'int'),
    'maxVersions': ('max_versions', 'int'),
    'upload': ('upload', 'bool'),
    'mimeTypes': ('upload_mime_types', 'char'),
    'focalPoint': ('focal_point', 'bool'),
    'crop': ('crop', 'bool'),
    'livePreview': ('live_preview', 'bool'),
    'livePreviewUrl': ('live_preview_url', 'char'),
    'previewUrl': ('preview_url', 'char'),
    'publicRead': ('public_read', 'bool'),
    'publicCreate': ('public_create', 'bool'),
    'multiTenant': ('multi_tenant', 'bool'),
}


def _iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S.000Z') if dt else None


# ----------------------------------------------------------------------
# records -> documents
# ----------------------------------------------------------------------
def field_rows(fields):
    rows = []
    for f in fields:
        row = {
            'id': 'f%023d' % f.id,
            'blockType': f.field_type,
            'name': f.name or '',
            'label': f.label or '',
            'required': f.required,
            'unique': f.unique,
            'localized': f.localized,
            'hasMany': f.has_many,
            'relationTo': f.relation_to_id.slug or None,
            'config': f.config or None,
            'options': [{'id': new_row_id(), **o} for o in f._parse_options()],
            'defaultValue': f.default_value or '',
            'min': f.min_value or None,
            'max': f.max_value or None,
            'minRows': f.min_rows or None,
            'maxRows': f.max_rows or None,
            'useAsSlug': f.slug_source or 'title',
            'position': f.position or 'main',
            'width': f.width or '',
            'description': f.description or '',
            'placeholder': f.placeholder or '',
            'readOnly': f.read_only,
            'hidden': f.hidden,
            'initCollapsed': f.initially_collapsed,
            'badges': [{'id': new_row_id(), 'value': value, 'label': b.get('label') or '', 'color': b.get('color') or 'muted'}
                       for value, b in (((f.config or {}).get('admin') or {}).get('badges') or {}).items()],
        }
        if f.field_type == 'blocks':
            row['blocks'] = [{
                'id': 'f%023d' % b.id,
                'slug': b.name or '',
                'label': b.label or '',
                'fields': field_rows(b.child_ids),
            } for b in f.child_ids]
        elif f.field_type == 'tabs':
            row['tabs'] = [{
                'id': 'f%023d' % tab.id,
                'name': tab.name or '',
                'label': tab.label or '',
                'description': tab.description or '',
                'fields': field_rows(tab.child_ids),
            } for tab in f.child_ids]
        else:
            row['fields'] = field_rows(f.child_ids)
        rows.append(row)
    return rows


def collection_doc(collection):
    doc = {'id': collection.id, 'kind': collection.kind}
    for key, (fname, kind) in COLLECTION_KEYS.items():
        value = collection[fname]
        doc[key] = value if kind != 'char' else (value or '')
    doc['imageSizes'] = [
        {'id': new_row_id(), 'name': s.get('name'), 'width': s.get('width') or None, 'height': s.get('height') or None}
        for s in (collection.image_sizes or [])
    ]
    doc['fields'] = field_rows(collection.field_ids)
    doc['codeModule'] = collection.code_module or ''
    doc['documentCount'] = collection.document_count
    doc['fieldCount'] = collection.field_count
    doc['updatedAt'] = _iso(collection.write_date)
    doc['createdAt'] = _iso(collection.create_date)
    return doc


def field_list(env):
    """Flat list of every field (the "Fields" configuration list)."""
    result = []
    for f in env['cms.field.definition'].sudo().search([]):
        if f.field_type in ('block', 'tab') and not f.name:
            continue
        chain = []
        parent = f.parent_id
        while parent:
            chain.insert(0, parent.name or parent.label or parent.field_type)
            parent = parent.parent_id
        result.append({
            'id': f.id,
            'name': f.name or '',
            'label': f.label or '',
            'type': f.field_type,
            'collection': f.collection_id.label,
            'collectionId': f.collection_id.id,
            'kind': f.collection_id.kind,
            'path': '.'.join(chain + [f.name or f.field_type]),
            'required': f.required,
            'relationTo': f.relation_to_id.slug or None,
            'position': f.position,
            'updatedAt': _iso(f.write_date),
            'createdAt': _iso(f.create_date),
        })
    return result


# ----------------------------------------------------------------------
# documents -> records
# ----------------------------------------------------------------------
def collection_vals(data, kind):
    vals = {}
    for key, (fname, ftype) in COLLECTION_KEYS.items():
        if key not in data:
            continue
        value = data[key]
        if ftype == 'bool':
            value = bool(value)
        elif ftype == 'int':
            try:
                value = int(value or 0)
            except (TypeError, ValueError):
                value = 0
        else:
            value = (value or '').strip() or False
        vals[fname] = value
    if 'imageSizes' in data:
        vals['image_sizes'] = [
            {k: v for k, v in (('name', s.get('name')), ('width', int(s['width']) if s.get('width') else None),
                                ('height', int(s['height']) if s.get('height') else None)) if v}
            for s in data.get('imageSizes') or [] if s.get('name')
        ]
    if kind == 'global':
        vals['upload'] = False
    return vals


def rows_to_spec(rows):
    """Admin block rows -> Payload-like field config used by `_create_from_spec`."""
    specs = []
    for row in rows or []:
        ftype = row.get('blockType')
        if not ftype:
            continue
        spec = {
            'type': ftype,
            'name': (row.get('name') or '').strip() or None,
            'label': (row.get('label') or '').strip() or None,
            'required': bool(row.get('required')),
            'unique': bool(row.get('unique')),
            'localized': bool(row.get('localized')),
            'hasMany': bool(row.get('hasMany')),
            'admin': {
                'position': row.get('position') or 'main',
                'width': row.get('width') or None,
                'description': row.get('description') or None,
                'placeholder': row.get('placeholder') or None,
                'readOnly': bool(row.get('readOnly')),
                'hidden': bool(row.get('hidden')),
                'initCollapsed': bool(row.get('initCollapsed')),
            },
        }
        if isinstance(row.get('config'), dict):
            # extra options defined in code (admin.condition...) survive admin edits
            spec['admin'] = dict((row['config'].get('admin') or {}), **spec['admin'])
            spec.update({k: v for k, v in row['config'].items() if k != 'admin'})
        if 'badges' in row:
            # coloured badges of the list / kanban views (admin.badges)
            badges = {str(b['value']).strip(): {k: v for k, v in (('label', (b.get('label') or '').strip()),
                                                                   ('color', b.get('color') or 'muted')) if v}
                      for b in row.get('badges') or [] if str(b.get('value') or '').strip()}
            if badges and ftype in ('checkbox', 'select', 'radio'):
                spec['admin']['badges'] = badges
            else:
                spec['admin'].pop('badges', None)
        if row.get('relationTo'):
            spec['relationTo'] = row['relationTo']
        if row.get('options'):
            spec['options'] = [{'value': o.get('value'), 'label': o.get('label') or o.get('value')}
                               for o in row['options'] if o.get('value')]
        if row.get('defaultValue') not in (None, ''):
            raw = row['defaultValue']
            try:
                spec['defaultValue'] = json.loads(raw) if isinstance(raw, str) else raw
            except ValueError:
                spec['defaultValue'] = raw
        for key in ('min', 'max', 'minRows', 'maxRows'):
            if row.get(key) not in (None, ''):
                spec[key] = row[key]
        if ftype == 'slug':
            spec['useAsSlug'] = row.get('useAsSlug') or 'title'
            spec['admin']['position'] = row.get('position') or 'sidebar'
        if ftype == 'blocks':
            spec['blocks'] = [{
                'slug': (b.get('slug') or '').strip(),
                'labels': {'singular': b.get('label') or None},
                'fields': rows_to_spec(b.get('fields')),
            } for b in row.get('blocks') or [] if b.get('slug')]
        elif ftype == 'tabs':
            spec['tabs'] = [{
                'name': (tab.get('name') or '').strip() or None,
                'label': tab.get('label') or None,
                'description': tab.get('description') or None,
                'fields': rows_to_spec(tab.get('fields')),
            } for tab in row.get('tabs') or []]
        elif row.get('fields'):
            spec['fields'] = rows_to_spec(row['fields'])
        specs.append(spec)
    return specs


def save_collection(env, collection, data, kind):
    """Create (collection empty) or update a collection / global from an admin doc."""
    Collection = env['cms.collection'].sudo()
    vals = collection_vals(data, kind)
    if collection and collection.code_module:
        # fields defined by a Python class (payload_cms.payload): the code is the source of truth
        data = {k: v for k, v in data.items() if k != 'fields'}
    old_fields = collection.field_ids._admin_config() if collection else None
    if collection:
        collection.write(vals)
    else:
        vals['kind'] = kind
        vals.setdefault('label', data.get('label') or data.get('slug'))
        collection = Collection.create(vals)
    if 'fields' in data:
        collection.all_field_ids.unlink()
        env['cms.field.definition'].sudo()._create_from_spec(collection, rows_to_spec(data['fields']))
        if old_fields is not None:
            collection._migrate_localized(old_fields)
    return collection


# ----------------------------------------------------------------------
# reusable blocks (Configuration → Blocks)
# ----------------------------------------------------------------------
def _with_ids(rows):
    """Component rows edited as Payload block rows need an id."""
    result = []
    for row in rows or []:
        row = dict(row, id=row.get('id') or new_row_id())
        if row.get('options'):
            row['options'] = [dict(o, id=o.get('id') or new_row_id()) for o in row['options']]
        if row.get('blockType') == 'list':
            row['components'] = _with_ids(row.get('components'))
        result.append(row)
    return result


def _count_components(rows):
    return sum(1 + _count_components(r.get('components')) for r in rows or [])


def block_doc(block):
    return {
        'id': block.id,
        'label': block.label or '',
        'labelPlural': block.label_plural or '',
        'slug': block.slug or '',
        'description': block.description or '',
        'sectionHeader': block.section_header,
        'targets': block.targets or [],
        'components': _with_ids(block.components),
        'componentCount': _count_components(block.components),
        'usageCount': block._usage_count(),
        'active': block.active,
        'updatedAt': _iso(block.write_date),
        'createdAt': _iso(block.create_date),
    }


def _clean_components(rows):
    result = []
    for row in rows or []:
        if not row.get('blockType'):
            continue
        row = {k: v for k, v in row.items() if v not in (None, '', [])}
        row['name'] = (row.get('name') or '').strip()
        if row['blockType'] == 'list':
            row['components'] = _clean_components(row.get('components'))
        result.append(row)
    return result


def save_block(env, block, data):
    """Create (block empty) or update a reusable block from an admin doc."""
    vals = {}
    for key, fname in (('label', 'label'), ('labelPlural', 'label_plural'), ('slug', 'slug'), ('description', 'description')):
        if key in data:
            vals[fname] = (data[key] or '').strip() or False
    for key, fname in (('sectionHeader', 'section_header'), ('active', 'active')):
        if key in data:
            vals[fname] = bool(data[key])
    if 'targets' in data:
        vals['targets'] = [t for t in data['targets'] or [] if isinstance(t, str) and '.' in t]
    if 'components' in data:
        vals['components'] = _clean_components(data['components'])
    if block:
        block.write(vals)
        return block
    return env['cms.block'].sudo().create(vals)
