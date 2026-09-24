# -*- coding: utf-8 -*-
"""Field-config walker shared by the REST API and the models.

Everything works on the Payload-like field configuration produced by
``cms.field.definition._admin_config()`` so that the server and the admin
SPA interpret the schema exactly the same way.
"""
import re
import secrets
import unicodedata
from datetime import datetime

PRESENTATIONAL = ('row', 'collapsible')
EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


def new_row_id():
    """Payload uses 24 hex chars (ObjectID-like) ids for array & block rows."""
    return secrets.token_hex(12)


def slugify(value):
    """Payload's slug formatter (fields/Slug): strips accents, lowercases,
    replaces whitespace by '-' and drops any other non word character."""
    if not value or not isinstance(value, str):
        return ''
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'\s+', '-', value.strip())
    value = re.sub(r'[^\w-]+', '', value)
    value = re.sub(r'-{2,}', '-', value)
    return value.lower().strip('-')


def data_fields(fields):
    """Yield the fields owning a key in the current object.

    ``row``/``collapsible`` and unnamed tabs are transparent, named tabs behave
    like a group.
    """
    for field in fields:
        ftype = field.get('type')
        if ftype in PRESENTATIONAL:
            yield from data_fields(field.get('fields') or [])
        elif ftype == 'tabs':
            for tab in field.get('tabs') or []:
                if tab.get('name'):
                    yield {'type': 'group', 'name': tab['name'], 'label': tab.get('label'),
                           'fields': tab.get('fields') or []}
                else:
                    yield from data_fields(tab.get('fields') or [])
        elif field.get('name'):
            yield field


def find_field(fields, path):
    """Find a field config from a dotted path ('meta.title', 'layout.content.richText')."""
    parts = path.split('.')
    current = list(data_fields(fields))
    field = None
    for part in parts:
        if part.isdigit():
            continue
        field = next((f for f in current if f.get('name') == part), None)
        if field is None:
            return None
        if field['type'] == 'blocks':
            current = [f for b in field.get('blocks') or [] for f in data_fields(b.get('fields') or [])]
        else:
            current = list(data_fields(field.get('fields') or []))
    return field


# ----------------------------------------------------------------------
# Defaults & sanitation
# ----------------------------------------------------------------------
def apply_defaults(fields, data):
    """Fill missing keys with their `defaultValue` (Payload applies them on create)."""
    data = dict(data or {})
    for field in data_fields(fields):
        name = field['name']
        ftype = field['type']
        if ftype == 'group':
            data[name] = apply_defaults(field.get('fields') or [], data.get(name) or {})
        elif ftype in ('array', 'blocks') and isinstance(data.get(name), list):
            # defaults of the rows too (Payload fills them when a row is added)
            blocks = {b['slug']: b for b in field.get('blocks') or []}
            rows = []
            for row in data[name]:
                if isinstance(row, dict):
                    sub = field.get('fields') if ftype == 'array' else (blocks.get(row.get('blockType')) or {}).get('fields')
                    row = apply_defaults(sub or [], row)
                rows.append(row)
            data[name] = rows
        elif name not in data or data[name] is None:
            if 'defaultValue' in field:
                data[name] = field['defaultValue']
            elif ftype == 'checkbox':
                data[name] = False
    return data


def _coerce_number(value):
    if value in (None, ''):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value  # left as is, validation will complain
    return int(number) if number.is_integer() else number


def _coerce_id(value):
    if isinstance(value, dict):
        value = value.get('id', value.get('value'))
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return value


def sanitize(fields, data, previous=None):
    """Keep only the declared keys and coerce values to their JSON type.

    ``previous`` is the currently stored data: keys absent from ``data`` are
    kept (PATCH semantics), like Payload does.
    """
    previous = previous or {}
    data = data if isinstance(data, dict) else {}
    result = {}
    for field in data_fields(fields):
        name = field['name']
        if name not in data:
            if name in previous:
                result[name] = previous[name]
            continue
        result[name] = sanitize_value(field, data[name], previous.get(name))
    return result


def sanitize_value(field, value, previous=None):
    ftype = field['type']
    if value is None:
        return None
    if ftype == 'slug':
        # API clients may send "My Blog": always store a URL-safe slug
        return slugify(value if isinstance(value, str) else str(value)) or None
    if ftype in ('text', 'textarea', 'email', 'code'):
        return value if isinstance(value, str) else str(value)
    if ftype == 'number':
        if field.get('hasMany') and isinstance(value, list):
            return [_coerce_number(v) for v in value]
        return _coerce_number(value)
    if ftype == 'checkbox':
        if isinstance(value, str):
            return value.lower() in ('1', 'true', 'on', 'yes')
        return bool(value)
    if ftype == 'date':
        if value == '':
            return None
        return value
    if ftype in ('select', 'radio'):
        if field.get('hasMany'):
            return [v for v in (value if isinstance(value, list) else [value]) if v not in (None, '')]
        return value if value != '' else None
    if ftype in ('relationship', 'upload'):
        if field.get('hasMany'):
            values = value if isinstance(value, list) else [value]
            return [_coerce_id(v) for v in values if v not in (None, '', False)]
        return _coerce_id(value) if value not in ('', False) else None
    if ftype == 'group':
        return sanitize(field.get('fields') or [], value, previous if isinstance(previous, dict) else {})
    if ftype == 'array':
        rows = []
        for row in value if isinstance(value, list) else []:
            if not isinstance(row, dict):
                continue
            clean = sanitize(field.get('fields') or [], row)
            clean['id'] = row.get('id') or new_row_id()
            rows.append(clean)
        return rows
    if ftype == 'blocks':
        blocks = {b['slug']: b for b in field.get('blocks') or []}
        rows = []
        for row in value if isinstance(value, list) else []:
            if not isinstance(row, dict) or row.get('blockType') not in blocks:
                continue
            clean = sanitize(blocks[row['blockType']].get('fields') or [], row)
            clean['id'] = row.get('id') or new_row_id()
            clean['blockType'] = row['blockType']
            if row.get('blockName'):
                clean['blockName'] = row['blockName']
            rows.append(clean)
        return rows
    if ftype == 'richText' and isinstance(value, str):
        # REST clients may send HTML: store it as a Lexical state
        from .lexical_html import html_to_lexical
        return html_to_lexical(value)
    # richText, json: stored as given
    return value


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------
def is_empty(field, value):
    if value is None or value == '' or value == []:
        return True
    if field['type'] == 'richText':
        return not _lexical_has_content(value)
    return False


def _lexical_has_content(value):
    if not isinstance(value, dict):
        return bool(value)
    root = value.get('root') or {}

    def walk(node):
        if node.get('type') in ('upload', 'relationship', 'block', 'inlineBlock', 'horizontalrule'):
            return True
        if node.get('text', '').strip():
            return True
        return any(walk(child) for child in node.get('children') or [])
    return walk(root)


def validate(fields, data, path='', required=True):
    """Return a list of ``{'path', 'message'}`` errors (Payload error format)."""
    errors = []
    data = data or {}
    for field in data_fields(fields):
        name = field['name']
        fpath = '%s.%s' % (path, name) if path else name
        value = data.get(name)
        ftype = field['type']
        if required and field.get('required') and is_empty(field, value):
            errors.append({'path': fpath, 'message': 'This field is required.', 'label': field.get('label')})
            continue
        if value in (None, ''):
            continue
        if field.get('pattern') and isinstance(value, str) and not re.fullmatch(field['pattern'], value):
            errors.append({'path': fpath, 'label': field.get('label'),
                           'message': field.get('patternMessage') or '"%s" does not match the expected format.' % value})
            continue
        if ftype == 'email' and not EMAIL_RE.match(value):
            errors.append({'path': fpath, 'message': 'Please enter a valid email address.', 'label': field.get('label')})
        elif ftype == 'number':
            numbers = value if isinstance(value, list) else [value]
            for number in numbers:
                if not isinstance(number, (int, float)):
                    errors.append({'path': fpath, 'message': '"%s" is not a valid number.' % number, 'label': field.get('label')})
                elif field.get('min') is not None and number < field['min']:
                    errors.append({'path': fpath, 'message': '"%s" is less than the min allowed value of %s.' % (number, field['min']), 'label': field.get('label')})
                elif field.get('max') is not None and number > field['max']:
                    errors.append({'path': fpath, 'message': '"%s" is greater than the max allowed value of %s.' % (number, field['max']), 'label': field.get('label')})
        elif ftype == 'date':
            try:
                datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            except ValueError:
                errors.append({'path': fpath, 'message': '"%s" is not a valid date.' % value, 'label': field.get('label')})
        elif ftype in ('select', 'radio'):
            allowed = {o['value'] for o in field.get('options') or []}
            for v in value if isinstance(value, list) else [value]:
                if v not in allowed:
                    errors.append({'path': fpath, 'message': 'This field has an invalid selection', 'label': field.get('label')})
                    break
        elif ftype == 'slug':
            if value != slugify(value):
                errors.append({'path': fpath, 'message': 'Slug may only contain lowercase letters, digits and dashes.', 'label': field.get('label')})
        elif ftype == 'group':
            errors += validate(field.get('fields') or [], value, fpath, required)
        elif ftype in ('array', 'blocks'):
            rows = value if isinstance(value, list) else []
            if required and field.get('minRows') and len(rows) < field['minRows']:
                errors.append({'path': fpath, 'message': 'This field requires at least %s row(s).' % field['minRows'], 'label': field.get('label')})
            if field.get('maxRows') and len(rows) > field['maxRows']:
                errors.append({'path': fpath, 'message': 'This field requires no more than %s row(s).' % field['maxRows'], 'label': field.get('label')})
            blocks = {b['slug']: b for b in field.get('blocks') or []}
            for index, row in enumerate(rows):
                sub = field.get('fields') if ftype == 'array' else (blocks.get(row.get('blockType')) or {}).get('fields')
                errors += validate(sub or [], row, '%s.%s' % (fpath, index), required)
    return errors


# ----------------------------------------------------------------------
# Relations
# ----------------------------------------------------------------------
def collect_slug_fields(fields):
    return [f for f in data_fields(fields) if f['type'] == 'slug']


def walk_relations(fields, data, callback):
    """Call ``callback(field, value)`` for every relationship/upload value and
    replace it by the callback result. Also walks Lexical upload/relationship
    nodes of rich text fields. Returns a new data dict."""
    if not isinstance(data, dict):
        return data
    result = dict(data)
    for field in data_fields(fields):
        name = field['name']
        if name not in result or result[name] is None:
            continue
        value = result[name]
        ftype = field['type']
        if ftype in ('relationship', 'upload'):
            if isinstance(value, list):
                result[name] = [v for v in (callback(field['relationTo'], item) for item in value) if v is not None]
            else:
                result[name] = callback(field['relationTo'], value)
        elif ftype == 'group':
            result[name] = walk_relations(field.get('fields') or [], value, callback)
        elif ftype == 'array' and isinstance(value, list):
            result[name] = [walk_relations(field.get('fields') or [], row, callback) for row in value]
        elif ftype == 'blocks' and isinstance(value, list):
            blocks = {b['slug']: b for b in field.get('blocks') or []}
            result[name] = [
                walk_relations((blocks.get(row.get('blockType')) or {}).get('fields') or [], row, callback)
                for row in value if isinstance(row, dict)
            ]
        elif ftype == 'richText' and isinstance(value, dict):
            result[name] = _walk_lexical(value, callback)
    return result


def _walk_lexical(state, callback):
    def walk(node):
        if not isinstance(node, dict):
            return node
        node = dict(node)
        if node.get('type') in ('upload', 'relationship') and node.get('relationTo') and node.get('value') is not None:
            populated = callback(node['relationTo'], node['value'])
            if populated is not None:
                node['value'] = populated
        if node.get('type') == 'link' and isinstance(node.get('fields'), dict):
            doc = node['fields'].get('doc')
            if isinstance(doc, dict) and doc.get('relationTo') and doc.get('value') is not None:
                populated = callback(doc['relationTo'], doc['value'])
                if populated is not None:
                    node['fields'] = dict(node['fields'], doc=dict(doc, value=populated))
        if isinstance(node.get('children'), list):
            node['children'] = [walk(child) for child in node['children']]
        return node
    state = dict(state)
    if isinstance(state.get('root'), dict):
        state['root'] = walk(state['root'])
    return state


def lexical_to_text(state, limit=None):
    """Plain text extraction (used for titles / search)."""
    parts = []

    def walk(node):
        if not isinstance(node, dict):
            return
        if node.get('type') == 'text':
            parts.append(node.get('text', ''))
        for child in node.get('children') or []:
            walk(child)
        if node.get('type') in ('paragraph', 'heading', 'quote', 'listitem'):
            parts.append('\n')
    if isinstance(state, dict):
        walk(state.get('root') or {})
    text = ''.join(parts).strip()
    return text[:limit] if limit else text


def order_keys(fields, data):
    """JSONB does not keep key order: restore the schema order (like Payload)."""
    if not isinstance(data, dict):
        return data
    result = {}
    if 'id' in data:
        result['id'] = data['id']
    for field in data_fields(fields):
        name = field['name']
        if name not in data:
            continue
        value = data[name]
        ftype = field['type']
        if ftype == 'group' and isinstance(value, dict):
            value = order_keys(field.get('fields') or [], value)
        elif ftype == 'array' and isinstance(value, list):
            value = [_row(order_keys(field.get('fields') or [], row)) for row in value]
        elif ftype == 'blocks' and isinstance(value, list):
            blocks = {b['slug']: b for b in field.get('blocks') or []}
            value = [_row(order_keys((blocks.get(row.get('blockType')) or {}).get('fields') or [], row), True)
                     if isinstance(row, dict) else row for row in value]
        result[name] = value
    for key, value in data.items():
        result.setdefault(key, value)
    return result


def _row(row, block=False):
    """Array rows / blocks end with id (and blockName, blockType), like Payload."""
    if not isinstance(row, dict):
        return row
    row = dict(row)
    tail = [(k, row.pop(k)) for k in ('id', 'blockName', 'blockType') if k in row]
    row.update(tail)
    return row


# ----------------------------------------------------------------------
# Localization (values stored as {"en": ..., "fr": ...})
# ----------------------------------------------------------------------
def is_locale_dict(value, codes):
    return isinstance(value, dict) and bool(value) and set(value) <= set(codes)


def _pick(value, loc):
    """Value of a localized field for the given locale context."""
    codes = loc['codes']
    if not is_locale_dict(value, codes):
        return value  # value written before the field was localized
    if loc['locale'] == 'all':
        return value
    picked = value.get(loc['locale'])
    if (picked is None or picked == '' or picked == []) and loc.get('fallback'):
        picked = value.get(loc['fallback'])
    return picked


def flatten_locale(fields, data, loc):
    """Replace localized values by their value in ``loc['locale']`` (recursive)."""
    if not loc or loc['locale'] == 'all' or not isinstance(data, dict):
        return data
    result = dict(data)
    for field in data_fields(fields):
        name = field['name']
        if name not in result:
            continue
        value = result[name]
        if field.get('localized'):
            value = _pick(value, loc)
        ftype = field['type']
        if ftype == 'group' and isinstance(value, dict):
            value = flatten_locale(field.get('fields') or [], value, loc)
        elif ftype == 'array' and isinstance(value, list):
            value = [flatten_locale(field.get('fields') or [], row, loc) for row in value]
        elif ftype == 'blocks' and isinstance(value, list):
            blocks = {b['slug']: b for b in field.get('blocks') or []}
            value = [flatten_locale((blocks.get(row.get('blockType')) or {}).get('fields') or [], row, loc)
                     if isinstance(row, dict) else row for row in value]
        result[name] = value
    return result


def merge_locale(fields, flat, stored, loc):
    """Write the flat values of ``loc['locale']`` into the stored (localized) data."""
    if not loc or loc['locale'] == 'all' or not isinstance(flat, dict):
        return flat
    stored = stored if isinstance(stored, dict) else {}
    result = dict(flat)
    codes, locale, default = loc['codes'], loc['locale'], loc['default']
    for field in data_fields(fields):
        name = field['name']
        if name not in flat:
            continue
        value = flat[name]
        previous = stored.get(name)
        ftype = field['type']
        if field.get('localized'):
            base = dict(previous) if is_locale_dict(previous, codes) else (
                {default: previous} if previous not in (None, '', []) else {})
            base[locale] = value
            result[name] = base
            continue
        if ftype == 'group' and isinstance(value, dict):
            result[name] = merge_locale(field.get('fields') or [], value, previous if isinstance(previous, dict) else {}, loc)
        elif ftype in ('array', 'blocks') and isinstance(value, list):
            old_rows = {r.get('id'): r for r in previous or [] if isinstance(r, dict)} if isinstance(previous, list) else {}
            blocks = {b['slug']: b for b in field.get('blocks') or []}
            rows = []
            for row in value:
                if not isinstance(row, dict):
                    continue
                sub = field.get('fields') if ftype == 'array' else (blocks.get(row.get('blockType')) or {}).get('fields')
                rows.append(merge_locale(sub or [], row, old_rows.get(row.get('id')) or {}, loc))
            result[name] = rows
    return result


# ----------------------------------------------------------------------
# REST output: rich text as HTML
# ----------------------------------------------------------------------
def rich_text_to_html(fields, data, codes=()):
    """Convert every richText value (also inside groups, arrays, blocks and
    locale dictionaries) to an HTML string."""
    from .lexical_html import is_lexical, lexical_to_html
    if not isinstance(data, dict):
        return data
    result = dict(data)

    def convert(value):
        if is_lexical(value):
            return lexical_to_html(value)
        if is_locale_dict(value, codes):
            return {k: convert(v) for k, v in value.items()}
        return value

    def rows(value, fn):
        if is_locale_dict(value, codes):
            return {k: rows(v, fn) for k, v in value.items()}
        return [fn(row) for row in value] if isinstance(value, list) else value

    for field in data_fields(fields):
        name = field['name']
        if name not in result or result[name] is None:
            continue
        ftype = field['type']
        if ftype == 'richText':
            result[name] = convert(result[name])
        elif ftype == 'group':
            result[name] = rich_text_to_html(field.get('fields') or [], result[name], codes)
        elif ftype == 'array':
            result[name] = rows(result[name], lambda row: rich_text_to_html(field.get('fields') or [], row, codes))
        elif ftype == 'blocks':
            blocks = {b['slug']: b for b in field.get('blocks') or []}
            result[name] = rows(result[name], lambda row: rich_text_to_html(
                (blocks.get(row.get('blockType')) or {}).get('fields') or [], row, codes) if isinstance(row, dict) else row)
    return result


def localized_paths(fields, prefix=''):
    """Dotted paths of the localized fields (top level and inside groups)."""
    paths = []
    for field in data_fields(fields):
        path = '%s.%s' % (prefix, field['name']) if prefix else field['name']
        if field.get('localized'):
            paths.append((path, field))
        elif field['type'] == 'group':
            paths += localized_paths(field.get('fields') or [], path)
    return paths


def delocalize(old_fields, new_fields, data, codes, default):
    """Schema migration: values of fields that are no longer localized
    ({"en": ..., "fr": ...}) are replaced by their default locale value."""
    if not isinstance(data, dict):
        return data, False
    old_by_name = {f['name']: f for f in data_fields(old_fields)}
    changed = False
    result = dict(data)
    for field in data_fields(new_fields):
        name = field['name']
        old = old_by_name.get(name)
        if name not in result or not old:
            continue
        value = result[name]
        if old.get('localized') and not field.get('localized') and is_locale_dict(value, codes):
            value = value.get(default)
            if value is None:
                value = next((v for v in result[name].values() if v not in (None, '', [])), None)
            result[name], changed = value, True
            continue
        if field.get('localized'):
            continue
        ftype = field['type']
        if ftype == 'group' and isinstance(value, dict):
            result[name], sub = delocalize(old.get('fields') or [], field.get('fields') or [], value, codes, default)
            changed |= sub
        elif ftype in ('array', 'blocks') and isinstance(value, list):
            old_blocks = {b['slug']: b for b in old.get('blocks') or []}
            new_blocks = {b['slug']: b for b in field.get('blocks') or []}
            rows = []
            for row in value:
                if isinstance(row, dict):
                    if ftype == 'array':
                        o, n = old.get('fields') or [], field.get('fields') or []
                    else:
                        o = (old_blocks.get(row.get('blockType')) or {}).get('fields') or []
                        n = (new_blocks.get(row.get('blockType')) or {}).get('fields') or []
                    row, sub = delocalize(o, n, row, codes, default)
                    changed |= sub
                rows.append(row)
            result[name] = rows
    return result, changed


class _Blank(dict):
    def __missing__(self, key):
        return ''


def apply_computed(fields, data):
    """Fields with a ``compute`` template (``"{nom} {prenom}"``) get their value
    from the other top-level fields of the document."""
    if not isinstance(data, dict):
        return data
    for field in data_fields(fields):
        template = field.get('compute')
        if not template:
            continue
        values = _Blank({k: ('' if v is None else v) for k, v in data.items() if not isinstance(v, (dict, list))})
        try:
            data[field['name']] = ' '.join(template.format_map(values).split()) or None
        except (ValueError, KeyError, IndexError):
            continue
    return data
