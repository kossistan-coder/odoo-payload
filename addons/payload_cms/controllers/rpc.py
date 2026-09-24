# -*- coding: utf-8 -*-
"""JSON-RPC access to the collections, like Odoo's ``/web/dataset/call_kw``::

    POST /payload/dataset/call_kw
    {"jsonrpc": "2.0", "method": "call", "params": {
        "model": "events", "method": "search_read",
        "args": [[["active", "=", true]]],
        "kwargs": {"fields": ["designation", "date_sortie"], "order": "date_sortie desc", "limit": 3}}}

Anonymous calls read the public collections. Authentication: the Odoo session
cookie, or ``Authorization: Bearer <Odoo API key | Payload JWT>``.
"""
import re

from odoo import http
from odoo.exceptions import AccessDenied
from odoo.http import request

from ..payload.model import Model
from .utils import decode_jwt


def _authenticate():
    header = request.httprequest.headers.get('Authorization') or ''
    match = re.match(r'^(?:bearer|jwt)\s+(.+)$', header, re.IGNORECASE)
    if not match:
        return
    token = match.group(1).strip()
    decoded = decode_jwt(request.env, token)
    uid = decoded[0] if decoded else request.env['res.users.apikeys'].sudo()._check_credentials(scope='rpc', key=token)
    if not uid:
        raise AccessDenied("Invalid API key or token")
    request.update_env(user=uid)


class PayloadRpc(http.Controller):

    @http.route(['/payload/dataset/call_kw', '/payload/dataset/call_kw/<path:path>'], type='json', auth='public',
                csrf=False, cors='*', sitemap=False)
    def call_kw(self, model=None, method=None, args=None, kwargs=None, path=None, **params):
        """``/payload/dataset/call_kw/<collection>/<method>``: the model and the
        method come from the URL, and the other JSON-RPC params are the keyword
        arguments of the method (``{"params": {"limit": 3}}``)."""
        _authenticate()
        if path and (not model or not method):
            parts = [p for p in path.split('/') if p]
            if len(parts) >= 2:
                model, method = model or parts[0], method or parts[1]
                if kwargs is None:
                    kwargs = params
        return Model(request.env, model).call(method, args, kwargs)
