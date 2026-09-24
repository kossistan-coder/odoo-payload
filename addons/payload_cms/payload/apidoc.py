# -*- coding: utf-8 -*-
"""Documentation (Swagger / OpenAPI) of the API routes written by the modules.

payload_cms documents every route of the controllers of the modules that use
it (any ``controllers/*.py`` imported by the module): the path, methods, URL
parameters and authentication come from ``@http.route``, the description from
the docstring. ``@api_doc`` completes it (parameters, body, response schema
generated from the collection) or hides a route (``hidden=True``)::

    from odoo.addons.payload_cms.payload import Model, api_doc

    class TechLivesApi(http.Controller):

        @api_doc(tags=['Lives'], params={'limit': (int, "Nombre maximum")},
                 model='events', fields=CARD, many=True)
        @http.route('/techlives/api/lives', type='http', auth='public', methods=['GET'])
        def lives(self, limit=None):
            \"\"\"Lives actifs, du plus récent au plus ancien.\"\"\"
            ...

Parameters of ``@api_doc`` (all optional):

``summary``     one line (default: first line of the docstring)
``description`` markdown (default: rest of the docstring)
``tags``        groups of the documentation (default: the collection label)
``params``      query parameters (``type='http'``) or JSON-RPC params (``type='json'``):
                ``{'limit': int}``, ``{'limit': (int, "help")}`` or an OpenAPI schema dict
                (``'required': True`` to make it mandatory). URL parameters (``<int:id>``)
                are documented automatically.
``body``        JSON body of an ``http`` POST / PUT route: same format as ``params``,
                or a list of fields of ``model`` (``['name', 'email']``)
``model``       collection returned (or received) by the route
``fields``      returned fields: list (``search_read`` / ``read`` shape) or
                ``web_search_read`` specification (nested relations); default: every field
``many``        a list of records; ``paginated``: ``{'length', 'records'}``
``delivery``    the route returns the Delivery format (``payload_cms.payload.Delivery``) of ``model``:
                ``{data, meta}`` (``many`` / ``paginated``: a list in ``data``); ``depth``: the
                relations populated by default (0 = ids)
``hidden``      not in the documentation
``response``    OpenAPI schema of the response (instead of ``model`` / ``fields``)
``deprecated``  shown as deprecated

The same parameters are accepted by ``@expose`` for the methods of the
collections (``POST /payload/dataset/call_kw/<collection>/<method>``).
"""
import inspect
import re

DOC_ATTR = '_payload_api_doc'
DOC_KEYS = ('summary', 'description', 'tags', 'params', 'body', 'model', 'fields', 'many', 'paginated',
            'response', 'deprecated', 'delivery', 'depth', 'hidden')


def api_doc(summary=None, **doc):
    """Marks an ``@http.route`` for the API documentation (see the module docstring).
    Works above or below ``@http.route``."""
    unknown = set(doc) - set(DOC_KEYS)
    if unknown:
        raise TypeError("api_doc(): unknown parameter(s) %s" % ', '.join(sorted(unknown)))
    doc['summary'] = summary

    def decorator(func):
        setattr(func, DOC_ATTR, doc)
        original = getattr(func, 'original_endpoint', None)
        if original is not None:
            setattr(original, DOC_ATTR, doc)
        return func
    return decorator


def split_docstring(func):
    """(summary, description) from the docstring of a function."""
    text = inspect.cleandoc(getattr(func, '__doc__', None) or '')
    if not text:
        return None, None
    first, _sep, rest = text.partition('\n\n')
    return ' '.join(first.split()), rest.strip() or None


def payload_modules(env):
    """Installed modules depending (directly or not) on payload_cms."""
    Module = env['ir.module.module'].sudo()
    installed = Module.search([('state', '=', 'installed')])
    deps = {m.name: set(m.dependencies_id.mapped('name')) for m in installed}
    result, changed = {'payload_cms'}, True
    while changed:
        changed = False
        for name, requires in deps.items():
            if name not in result and requires & result:
                result.add(name)
                changed = True
    result.discard('payload_cms')
    return sorted(result)


def documented_routes(env, modules=None):
    """Routes of the controllers of the modules using payload_cms (except ``@api_doc(hidden=True)``).

    Returns dicts ``{path, methods, type, auth, module, func, doc}`` (``path``
    in OpenAPI syntax, ``params``: URL parameters with their type)."""
    from odoo import http
    modules = payload_modules(env) if modules is None else modules
    routes = []
    for url, endpoint in http._generate_routing_rules(modules, nodb_only=False):
        doc = getattr(endpoint, DOC_ATTR, None) or {}
        if doc.get('hidden'):
            continue
        func = getattr(endpoint, 'original_endpoint', None) or endpoint
        module = (getattr(func, '__module__', '') or '').split('.')
        routing = endpoint.routing
        path, url_params = openapi_path(url)
        routes.append({
            'path': path,
            'url_params': url_params,
            'methods': [m.upper() for m in routing.get('methods') or []] or (['POST'] if routing.get('type') == 'json' else ['GET']),
            'type': routing.get('type', 'http'),
            'auth': routing.get('auth', 'user'),
            'module': module[2] if module[:2] == ['odoo', 'addons'] else module[0],
            'func': func,
            'doc': doc,
        })
    return sorted(routes, key=lambda r: (r['module'], r['path']))


CONVERTERS = {'int': 'integer', 'float': 'number', 'string': 'string', 'path': 'string', 'model': 'integer'}


def openapi_path(url):
    """``/lives/<int:live_id>`` -> (``/lives/{live_id}``, {'live_id': 'integer'})."""
    params = {}

    def replace(match):
        converter, name = match.group(1), match.group(2)
        converter = (converter or 'string').split('(')[0]
        params[name] = CONVERTERS.get(converter, 'string')
        return '{%s}' % name
    return re.sub(r'<(?:([^:<>]+):)?([A-Za-z_][A-Za-z0-9_]*)>', replace, url), params


def exposed_methods(env, modules=None):
    """``@expose`` methods of the code-first collections of the modules using payload_cms."""
    from .collection import registered
    modules = set(payload_modules(env) if modules is None else modules)
    result = []
    for cls in registered():
        if cls._module not in modules:
            continue
        for name, func in sorted(vars(cls).items()):
            auth = getattr(func, '_payload_expose', None)
            if auth:
                result.append({'model': cls._name, 'kind': cls._kind, 'method': name, 'auth': auth,
                               'module': cls._module, 'func': func, 'doc': getattr(func, DOC_ATTR, {}) or {}})
    return result
