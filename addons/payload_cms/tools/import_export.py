# -*- coding: utf-8 -*-
"""Import / export of documents as CSV, Excel (.xlsx) or JSON
(same idea as @payloadcms/plugin-import-export).

Spreadsheet columns are the data paths of the collection:

* groups are flattened with dots (``meta.title``);
* rich text is HTML (HTML is accepted on import);
* relationships / uploads are IDs (``hasMany``: comma separated IDs);
* select ``hasMany``: comma separated values;
* arrays, blocks, json and point fields are JSON.
"""
import csv
import datetime
import io
import json

from . import schema

META_COLUMNS = ('id', '_status', 'createdAt', 'updatedAt')
FORMATS = {
    'csv': ('text/csv; charset=utf-8', 'csv'),
    'xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'),
    'json': ('application/json; charset=utf-8', 'json'),
}
TRUE_VALUES = {'1', 'true', 'yes', 'y', 'x', 'oui', 'vrai', 'on'}
FALSE_VALUES = {'0', 'false', 'no', 'n', 'non', 'faux', 'off', ''}


class ImportFileError(ValueError):
    pass


# ----------------------------------------------------------------------
# Columns
# ----------------------------------------------------------------------
def columns(fields, prefix=''):
    """[(path, field)] of the spreadsheet columns of a collection."""
    result = []
    for field in schema.data_fields(fields):
        path = '%s.%s' % (prefix, field['name']) if prefix else field['name']
        if field['type'] == 'group':
            result += columns(field.get('fields') or [], path)
        elif not field.get('private'):
            result.append((path, field))
    return result


def column_labels(fields):
    """{path: "Group › Label"} used as a hint in the admin."""
    labels = {}

    def walk(fields, prefix, label_prefix):
        for field in schema.data_fields(fields):
            path = '%s.%s' % (prefix, field['name']) if prefix else field['name']
            label = field.get('label') if isinstance(field.get('label'), str) else field['name']
            full = '%s › %s' % (label_prefix, label) if label_prefix else label
            if field['type'] == 'group':
                walk(field.get('fields') or [], path, full)
            else:
                labels[path] = full
    walk(fields, '', '')
    return labels


def meta_columns(collection):
    cols = ['id']
    if collection.drafts:
        cols.append('_status')
    if collection.upload:
        cols += ['filename', 'url', 'mimeType', 'filesize']
    return cols + ['createdAt', 'updatedAt']


def _get(doc, path):
    value = doc
    for key in path.split('.'):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def cell_value(field, value):
    """Value of a spreadsheet cell (export)."""
    if value is None:
        return ''
    ftype = field['type'] if field else None
    if ftype in ('relationship', 'upload'):
        def ident(v):
            return v.get('id', v.get('value')) if isinstance(v, dict) else v
        if isinstance(value, list):
            return ','.join(str(ident(v)) for v in value if ident(v) is not None)
        return ident(value) if ident(value) is not None else ''
    if ftype == 'select' and isinstance(value, list):
        return ','.join(str(v) for v in value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def rows(docs, cols, fields_by_path):
    for doc in docs:
        yield [cell_value(fields_by_path.get(path), _get(doc, path)) for path in cols]


# ----------------------------------------------------------------------
# Writers
# ----------------------------------------------------------------------
def write(fmt, headers, data_rows, sheet_name='Export', docs=None):
    if fmt == 'json':
        return json.dumps(docs or [], ensure_ascii=False, indent=2).encode()
    if fmt == 'csv':
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        for row in data_rows:
            writer.writerow(['true' if v is True else 'false' if v is False else v for v in row])
        # BOM: Excel opens UTF-8 CSV files correctly
        return ('﻿' + buffer.getvalue()).encode('utf-8')
    import xlsxwriter
    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {'in_memory': True, 'strings_to_urls': False, 'strings_to_formulas': False})
    sheet = workbook.add_worksheet(sheet_name[:31] or 'Export')
    bold = workbook.add_format({'bold': True, 'bg_color': '#F3F3F3', 'border': 1})
    widths = [len(h) for h in headers]
    for col, header in enumerate(headers):
        sheet.write(0, col, header, bold)
    count = 0
    for r, row in enumerate(data_rows, start=1):
        count = r
        for col, value in enumerate(row):
            if isinstance(value, bool):
                sheet.write_boolean(r, col, value)
            elif isinstance(value, (int, float)):
                sheet.write_number(r, col, value)
            else:
                text = str(value)
                sheet.write_string(r, col, text[:32767])
                widths[col] = max(widths[col], min(len(text), 60))
    for col, width in enumerate(widths):
        sheet.set_column(col, col, max(10, width + 2))
    sheet.freeze_panes(1, 0)
    if headers:
        sheet.autofilter(0, 0, max(1, count), len(headers) - 1)
    workbook.close()
    return buffer.getvalue()


# ----------------------------------------------------------------------
# Readers
# ----------------------------------------------------------------------
def read(filename, content):
    """Return (headers, [row dicts]) or [docs] for JSON."""
    name = (filename or '').lower()
    if name.endswith('.json'):
        try:
            data = json.loads(content.decode('utf-8-sig'))
        except ValueError as e:
            raise ImportFileError('Invalid JSON file: %s' % e)
        docs = data.get('docs') if isinstance(data, dict) else data
        if not isinstance(docs, list):
            raise ImportFileError('The JSON file must contain an array of documents (or {"docs": [...]}).')
        headers = sorted({k for d in docs if isinstance(d, dict) for k in d})
        return headers, [d for d in docs if isinstance(d, dict)], True
    if name.endswith('.xlsx') or content[:2] == b'PK':
        import openpyxl
        try:
            workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as e:  # noqa: BLE001
            raise ImportFileError('Invalid Excel file: %s' % e)
        sheet = workbook.worksheets[0]
        values = list(sheet.iter_rows(values_only=True))
        if not values:
            return [], [], False
        headers = [str(h).strip() if h is not None else '' for h in values[0]]
        result = []
        for line in values[1:]:
            if line is None or all(v in (None, '') for v in line):
                continue
            result.append({h: _xlsx_value(v) for h, v in zip(headers, line) if h})
        return headers, result, False
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('latin-1')
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    lines = [line for line in reader]
    if not lines:
        return [], [], False
    headers = [h.strip() for h in lines[0]]
    result = []
    for line in lines[1:]:
        if not any((v or '').strip() for v in line):
            continue
        result.append({h: v for h, v in zip(headers, line) if h})
    return headers, result, False


def _xlsx_value(value):
    if isinstance(value, datetime.datetime):
        return value.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    if isinstance(value, datetime.date):
        return value.isoformat()
    return value


# ----------------------------------------------------------------------
# Row -> document data
# ----------------------------------------------------------------------
def parse_cell(field, value):
    """Spreadsheet cell -> JSON value of the field (raises ValueError)."""
    ftype = field['type']
    if isinstance(value, str):
        value = value.strip()
    if value in (None, ''):
        return None
    if ftype == 'number':
        if field.get('hasMany'):
            return [float(v) if '.' in str(v) else int(v) for v in str(value).replace(';', ',').split(',') if str(v).strip()]
        if isinstance(value, (int, float)):
            return value
        number = float(str(value).replace(',', '.'))
        return int(number) if number.is_integer() else number
    if ftype == 'checkbox':
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in TRUE_VALUES:
            return True
        if text in FALSE_VALUES:
            return False
        raise ValueError('"%s" is not a boolean (true / false)' % value)
    if ftype in ('relationship', 'upload'):
        ids = [v.strip() for v in str(value).replace(';', ',').split(',') if v.strip()]
        for v in ids:
            if not v.lstrip('-').isdigit():
                raise ValueError('"%s" is not a document ID' % v)
        ids = [int(float(v)) for v in ids]
        return ids if field.get('hasMany') else (ids[0] if ids else None)
    if ftype == 'select' and field.get('hasMany'):
        return [v.strip() for v in str(value).split(',') if v.strip()]
    if ftype in ('array', 'blocks', 'json', 'point'):
        if isinstance(value, (list, dict)):
            return value
        try:
            return json.loads(value)
        except ValueError:
            if ftype == 'point':
                return [float(v) for v in str(value).split(',')]
            raise ValueError('invalid JSON')
    if ftype == 'richText' and isinstance(value, (dict, list)):
        return value
    return str(value) if not isinstance(value, str) else value


def row_to_data(row, mapping, fields_by_path):
    """Returns (data, meta, errors): data nested by path, meta {id, _status}."""
    data, meta, errors = {}, {}, []
    for column, value in row.items():
        path = mapping.get(column, column) if mapping else column
        if not path:
            continue
        if path in META_COLUMNS or path in ('filename', 'url', 'mimeType', 'filesize'):
            if path in ('id', '_status') and value not in (None, ''):
                meta[path] = value
            continue
        field = fields_by_path.get(path)
        if field is None:
            continue
        try:
            parsed = parse_cell(field, value)
        except (TypeError, ValueError) as e:
            errors.append({'path': path, 'message': str(e)})
            continue
        if parsed is None:
            continue
        target = data
        keys = path.split('.')
        for key in keys[:-1]:
            target = target.setdefault(key, {})
        target[keys[-1]] = parsed
    return data, meta, errors


def auto_mapping(headers, fields, labels):
    """Column header -> path (by path, name or label, case insensitive)."""
    by_key = {}
    for path, _field in columns(fields):
        by_key[path.lower()] = path
        by_key.setdefault(path.split('.')[-1].lower(), path)
        label = labels.get(path)
        if label:
            by_key.setdefault(label.lower(), path)
            by_key.setdefault(label.split(' › ')[-1].lower(), path)
    for meta in META_COLUMNS:
        by_key[meta.lower()] = meta
    return {h: by_key.get((h or '').strip().lower()) for h in headers}
