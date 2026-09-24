# -*- coding: utf-8 -*-
import json

from markupsafe import Markup
from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request


class PayloadAdmin(http.Controller):
    """Serves the Payload-like admin single page application on /admin."""

    @http.route(['/admin', '/admin/<path:path>'], type='http', auth='public', sitemap=False)
    def payload_admin(self, path=None, **_kw):
        # Theme chosen on the Account page (cookie set by core/theme.js); "auto" is resolved client side.
        theme = request.httprequest.cookies.get('payload-theme')
        response = request.render('payload_cms.admin_page', {
            'payload_config': Markup(json.dumps({'adminRoute': '/admin', 'apiRoute': '/api'})),
            'admin_theme': theme if theme in ('light', 'dark') else 'light',
        })
        response.headers['Cache-Control'] = 'no-store'
        return response

    @http.route('/cms/preview/<string:kind>/<string:slug>/<string:doc_id>', type='http', auth='public', sitemap=False)
    def payload_preview(self, kind, slug, doc_id, **_kw):
        """Built-in Live Preview / Preview page.

        It fetches the document through the REST API and re-renders whenever
        the admin posts a `payload-live-preview` message (same protocol as
        `@payloadcms/live-preview`)."""
        if kind not in ('collections', 'globals'):
            raise NotFound()
        collection = request.env['cms.collection'].sudo().search(
            [('slug', '=', slug), ('kind', '=', 'global' if kind == 'globals' else 'collection')], limit=1)
        if not collection:
            raise NotFound()
        return request.render('payload_cms.preview_page', {
            'preview_config': _safe_json({
                'kind': kind,
                'slug': slug,
                'id': doc_id,
                'fields': collection.field_ids._admin_config(),
                'label': collection.label_singular or collection.label,
            }),
            'collection': collection,
        })


def _safe_json(value):
    """JSON safe to embed in an inline <script>."""
    return Markup(json.dumps(value).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026'))
