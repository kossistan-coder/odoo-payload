# -*- coding: utf-8 -*-
"""Translate Payload ``where`` / ``sort`` query parameters to SQL on the
``cms_document`` table (documents are stored in a JSONB column)."""
import json
import re

from odoo.tools import SQL

from . import schema

# Payload property -> real column of cms_document
COLUMN_FIELDS = {
    'id': ('id', 'number'),
    'createdAt': ('create_date', 'date'),
    'updatedAt': ('write_date', 'date'),
    '_status': ('status', 'text'),
    'filename': ('filename', 'text'),
    'mimeType': ('mime_type', 'text'),
    'filesize': ('filesize', 'number'),
    'width': ('width', 'number'),
    'height': ('height', 'number'),
    'focalX': ('focal_x', 'number'),
    'focalY': ('focal_y', 'number'),
}

OPERATORS = {
    'equals', 'not_equals', 'in', 'not_in', 'all', 'like', 'not_like', 'contains', 'exists',
    'greater_than', 'greater_than_equal', 'less_than', 'less_than_equal',
}
PATH_RE = re.compile(r'^[A-Za-z0-9_.]+$')


class QueryError(ValueError):
    pass


def parse_bracket_params(pairs):
    """Parse ``qs``-style keys (``where[or][0][title][like]=x``,
    ``where[id][in][]=1``) into nested dicts/lists, like Payload's REST API.

    ``pairs`` is an iterable of (key, value) (repeated keys allowed)."""
    root = {}
    for key, value in pairs:
        if '[' not in key:
            root[key] = value
            continue
        head, rest = key.split('[', 1)
        parts = [head] + re.findall(r'\[([^\[\]]*)\]', '[' + rest)
        node = root
        for index, part in enumerate(parts):
            last = index == len(parts) - 1
            if part == '':
                # "a[]" -> append; represented as a dict with increasing numeric keys
                part = str(len(node))
            if last:
                node[part] = value
            else:
                nxt = node.get(part)
                if not isinstance(nxt, dict):
                    nxt = {}
                    node[part] = nxt
                node = nxt
    return _lists(root)


def _lists(node):
    """Convert dicts whose keys are all digits into lists (qs arrays)."""
    if isinstance(node, dict):
        node = {k: _lists(v) for k, v in node.items()}
        if node and all(k.isdigit() for k in node):
            return [node[k] for k in sorted(node, key=int)]
    return node


def _json_path(path):
    return '{%s}' % ','.join(path.split('.'))


def _values(value):
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [v for v in value.split(',')]
    return [json.dumps(value) if isinstance(value, bool) else str(value)]


def _scalar(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if value is None:
        return None
    return str(value)


def _is_number(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


class WhereBuilder:
    def __init__(self, fields, json_column, draft=True, locale=None):
        self.fields = fields
        self.json_column = json_column  # 'data' or 'published_data'
        self.draft = draft
        # locale context (see tools/localization.make_context) or None
        self.locale = locale if locale and locale.get('locale') != 'all' else None
        self.localized = [p for p, _f in schema.localized_paths(fields)] if self.locale else []

    def _nodes(self, path):
        """(jsonb node, text) SQL expressions for a data path, resolving
        localized fields to the requested locale (with fallback)."""
        column = SQL.identifier(self.json_column)
        for prefix in self.localized:
            if path == prefix or path.startswith(prefix + '.'):
                rest = path[len(prefix):]
                locales = [self.locale['locale']]
                if self.locale.get('fallback') and self.locale['fallback'] not in locales:
                    locales.append(self.locale['fallback'])
                paths = [_json_path(prefix + '.' + code + rest) for code in locales]
                legacy = _json_path(path)
                prefix_path = _json_path(prefix)
                not_dict = SQL("jsonb_typeof(d.%s #> %s) <> 'object'", column, prefix_path)
                node = SQL('COALESCE(%s, CASE WHEN %s THEN d.%s #> %s END)', SQL.join(SQL(', '), [
                    SQL('d.%s #> %s', column, p) for p in paths]), not_dict, column, legacy)
                text = SQL('COALESCE(%s, CASE WHEN %s THEN d.%s #>> %s END)', SQL.join(SQL(', '), [
                    SQL('d.%s #>> %s', column, p) for p in paths]), not_dict, column, legacy)
                return SQL('(%s)', node), SQL('(%s)', text)
        jpath = _json_path(path)
        return SQL('(d.%s #> %s)', column, jpath), SQL('(d.%s #>> %s)', column, jpath)

    def build(self, where):
        if not where:
            return SQL('TRUE')
        if isinstance(where, str):
            try:
                where = json.loads(where)
            except ValueError:
                raise QueryError('Invalid where clause')
        if not isinstance(where, dict):
            raise QueryError('Invalid where clause')
        clauses = []
        for key, value in where.items():
            if key in ('and', 'or'):
                items = value if isinstance(value, list) else list(value.values()) if isinstance(value, dict) else []
                subs = [self.build(item) for item in items if item]
                if subs:
                    joiner = SQL(' AND ') if key == 'and' else SQL(' OR ')
                    clauses.append(SQL('(%s)', SQL.join(joiner, subs)))
                continue
            if not isinstance(value, dict):
                # shorthand: where[title]=foo -> equals
                value = {'equals': value}
            for operator, operand in value.items():
                clauses.append(self._condition(key, operator, operand))
        if not clauses:
            return SQL('TRUE')
        return SQL('(%s)', SQL.join(SQL(' AND '), clauses))

    # ------------------------------------------------------------------
    def _condition(self, path, operator, value):
        if operator not in OPERATORS:
            raise QueryError('Unsupported operator "%s"' % operator)
        if not PATH_RE.match(path):
            raise QueryError('Invalid path "%s"' % path)
        if path in COLUMN_FIELDS:
            column, kind = COLUMN_FIELDS[path]
            if path == '_status' and not self.draft:
                text = SQL("'published'")
            else:
                text = SQL('d.%s::text', SQL.identifier(column))
            return self._column_condition(SQL('d.%s', SQL.identifier(column)), text, kind, operator, value)
        field = schema.find_field(self.fields, path)
        if field is None and path.endswith('.relationTo'):
            field = {'type': 'text'}
        if field is None:
            raise QueryError('The following path cannot be queried: %s' % path)
        node, text = self._nodes(path)
        return self._json_condition(node, text, field, operator, value)

    def _column_condition(self, column, text, kind, operator, value):
        if operator == 'exists':
            truthy = _scalar(value) in ('true', '1')
            return SQL('%s IS NOT NULL', column) if truthy else SQL('%s IS NULL', column)
        if operator in ('equals', 'not_equals'):
            if value in (None, 'null'):
                return SQL('%s IS NULL', column) if operator == 'equals' else SQL('%s IS NOT NULL', column)
            if operator == 'equals':
                return SQL('%s = %s', text, _scalar(value))
            return SQL('%s IS DISTINCT FROM %s', text, _scalar(value))
        if operator in ('in', 'not_in', 'all'):
            values = _values(value)
            if not values:
                return SQL('FALSE') if operator != 'not_in' else SQL('TRUE')
            cond = SQL('%s = ANY(%s)', text, values)
            return SQL('NOT (%s)', cond) if operator == 'not_in' else cond
        if operator in ('like', 'contains', 'not_like'):
            words = str(value).split() if operator != 'contains' else [str(value)]
            conds = [SQL('%s ILIKE %s', text, '%%%s%%' % w) for w in words] or [SQL('TRUE')]
            cond = SQL('(%s)', SQL.join(SQL(' AND '), conds))
            return SQL('NOT %s', cond) if operator == 'not_like' else cond
        op = {'greater_than': '>', 'greater_than_equal': '>=', 'less_than': '<', 'less_than_equal': '<='}[operator]
        if kind == 'number':
            if not _is_number(value):
                raise QueryError('Invalid number "%s"' % value)
            return SQL('%s ' + op + ' %s', column, float(value))
        return SQL('%s ' + op + ' %s', column, str(value))

    def _json_condition(self, node, text, field, operator, value):
        # Arrays (hasMany relationship/select, numbers...) match if any element matches.
        elements = SQL(
            "(CASE WHEN jsonb_typeof(%s) = 'array' THEN %s ELSE '[]'::jsonb END)", node, node)
        any_element = lambda cond_sql: SQL(
            'EXISTS (SELECT 1 FROM jsonb_array_elements_text(%s) AS e(v) WHERE %s)', elements, cond_sql)

        if operator == 'exists':
            truthy = _scalar(value) in ('true', '1')
            present = SQL("(%s IS NOT NULL AND %s <> 'null'::jsonb AND %s <> '\"\"'::jsonb)", node, node, node)
            return present if truthy else SQL('NOT %s', present)

        if operator in ('equals', 'not_equals'):
            if value in (None, 'null'):
                cond = SQL("(%s IS NULL OR %s = 'null'::jsonb)", node, node)
            else:
                scalar = _scalar(value)
                cond = SQL('(%s = %s OR %s)', text, scalar, any_element(SQL('e.v = %s', scalar)))
            return cond if operator == 'equals' else SQL('NOT COALESCE(%s, FALSE)', cond)

        if operator in ('in', 'not_in', 'all'):
            values = _values(value)
            if not values:
                return SQL('FALSE') if operator != 'not_in' else SQL('TRUE')
            if operator == 'all':
                return SQL('(%s)', SQL.join(SQL(' AND '), [
                    SQL('(%s = %s OR %s)', text, v, any_element(SQL('e.v = %s', v))) for v in values]))
            cond = SQL('(%s = ANY(%s) OR %s)', text, values, any_element(SQL('e.v = ANY(%s)', values)))
            return cond if operator == 'in' else SQL('NOT COALESCE(%s, FALSE)', cond)

        if operator in ('like', 'not_like', 'contains'):
            words = str(value).split() if operator != 'contains' else [str(value)]
            conds = [SQL('%s ILIKE %s', text, '%%%s%%' % w) for w in words] or [SQL('TRUE')]
            cond = SQL('(%s)', SQL.join(SQL(' AND '), conds))
            return cond if operator != 'not_like' else SQL('NOT COALESCE(%s, FALSE)', cond)

        op = {'greater_than': '>', 'greater_than_equal': '>=', 'less_than': '<', 'less_than_equal': '<='}[operator]
        if field.get('type') == 'number' or (field.get('type') not in ('date', 'text', 'slug') and _is_number(value)):
            if not _is_number(value):
                raise QueryError('Invalid number "%s"' % value)
            numeric = SQL("(CASE WHEN jsonb_typeof(%s) = 'number' THEN (%s)::numeric END)", node, text)
            return SQL('%s ' + op + ' %s', numeric, float(value))
        return SQL('%s ' + op + ' %s', text, str(value))

    # ------------------------------------------------------------------
    def order_by(self, sort):
        """``sort=-title,createdAt`` -> ORDER BY clause."""
        terms = []
        for item in (sort or '').split(','):
            item = item.strip()
            if not item:
                continue
            desc = item.startswith('-')
            path = item.lstrip('-+')
            if not PATH_RE.match(path):
                raise QueryError('Invalid sort "%s"' % item)
            direction = SQL('DESC NULLS LAST') if desc else SQL('ASC NULLS LAST')
            if path in COLUMN_FIELDS:
                terms.append(SQL('d.%s %s', SQL.identifier(COLUMN_FIELDS[path][0]), direction))
                continue
            node, text = self._nodes(path)
            terms.append(SQL("(CASE WHEN jsonb_typeof(%s) = 'number' THEN (%s)::numeric END) %s", node, text, direction))
            terms.append(SQL('lower(%s) %s', text, direction))
        terms.append(SQL('d.id DESC'))
        return SQL.join(SQL(', '), terms)
