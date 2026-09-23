# -*- coding: utf-8 -*-
"""Automatic API documentation: Swagger UI on /api-docs, OpenAPI 3 on /api-docs/openapi.json."""
import json

from markupsafe import Markup, escape

from odoo import http
from odoo.http import request

from ..tools import api_docs, localization, multitenancy
from .api import PayloadRequest
from .utils import json_response

SWAGGER_PAGE = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>%(title)s</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&family=Roboto+Mono:ital,wght@0,100..700;1,100..700&display=swap"/>
<link rel="stylesheet" href="/payload_cms/static/lib/swagger-ui/swagger-ui.css"/>
<style>
  body { margin: 0; background: #fff; }
  :root { --font-body: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; --font-mono: "Roboto Mono", "SF Mono", Menlo, Consolas, Monaco, monospace; }
  body, .swagger-ui, .swagger-ui .info .title, .swagger-ui .opblock-tag, .swagger-ui .btn, .swagger-ui input, .swagger-ui select, .swagger-ui textarea, .swagger-ui table, .swagger-ui .opblock .opblock-summary-description, .swagger-ui .opblock-description-wrapper p, .swagger-ui .response-col_status, .swagger-ui .parameter__name, .swagger-ui .model-title, .swagger-ui section.models h4 { font-family: var(--font-body); }
  .swagger-ui code, .swagger-ui pre, .swagger-ui .microlight, .swagger-ui .opblock .opblock-summary-path, .swagger-ui .opblock .opblock-summary-method, .swagger-ui .model, .swagger-ui .prop-type, .swagger-ui .parameter__type, .swagger-ui .parameter__in, .swagger-ui textarea.curl { font-family: var(--font-mono); }
  .swagger-ui .info { margin: 32px 0 24px; }
  .swagger-ui .scheme-container { box-shadow: none; border-top: 1px solid #ebebeb; border-bottom: 1px solid #ebebeb; }
  .swagger-ui .btn.authorize { border-color: #222; color: #222; }
  .swagger-ui .btn.authorize svg { fill: #222; }
  .payload-docs-bar { display: flex; align-items: center; justify-content: space-between; padding: 12px 20px; border-bottom: 1px solid #ebebeb; font: 14px var(--font-body); }
  .payload-docs-bar a { color: #222; }
  .embed .payload-docs-bar { display: none; }
  .payload-docs-back { display: inline-flex; width: 24px; height: 24px; align-items: center; justify-content: center; margin-right: 8px; border: 1px solid #ddd; border-radius: 3px; text-decoration: none; }
</style>
</head>
<body class="%(body_class)s">
<div class="payload-docs-bar"><span><a class="payload-docs-back" href="/admin/api-docs" title="Back" onclick="if (history.length > 1) { history.back(); return false; }">&#8592;</a> <strong>%(title)s</strong></span><span><a href="/api-docs/openapi.json" download="openapi.json">openapi.json</a> · <a href="/admin">Admin</a></span></div>
<div id="swagger-ui"></div>
<script src="/payload_cms/static/lib/swagger-ui/swagger-ui-bundle.js"></script>
<script>
  window.ui = SwaggerUIBundle({
    url: "/api-docs/openapi.json",
    dom_id: "#swagger-ui",
    deepLinking: true,
    persistAuthorization: true,
    displayRequestDuration: true,
    tryItOutEnabled: true,
    filter: true,
    docExpansion: "list",
    defaultModelsExpandDepth: 0,
    requestInterceptor: (req) => { req.credentials = "same-origin"; return req; },
  });
</script>
</body>
</html>"""


class PayloadApiDocs(http.Controller):

    def _check_access(self, settings):
        """Returns None when allowed, else a response (404 disabled / 401 / login redirect)."""
        if not settings.get('enabled'):
            return request.not_found()
        if settings.get('public'):
            return None
        req = PayloadRequest()
        if req.is_editor:
            return None
        return req

    @http.route('/api-docs', type='http', auth='public', sitemap=False)
    def payload_api_docs(self, embed=None, **_kw):
        settings = api_docs.get_settings(request.env)
        denied = self._check_access(settings)
        if denied is not None:
            if isinstance(denied, PayloadRequest):
                return request.redirect('/web/login?redirect=/api-docs')
            return denied
        html = SWAGGER_PAGE % {
            'title': escape(settings.get('title') or 'Payload CMS API'),
            'body_class': 'embed' if embed else '',
        }
        return request.make_response(Markup(html), headers=[('Content-Type', 'text/html; charset=utf-8')])

    @http.route('/api-docs/openapi.json', type='http', auth='public', csrf=False, sitemap=False)
    def payload_openapi(self, **_kw):
        env = request.env
        settings = api_docs.get_settings(env)
        denied = self._check_access(settings)
        if denied is not None:
            if isinstance(denied, PayloadRequest):
                return json_response({'errors': [{'message': 'You are not allowed to perform this action.'}]}, status=401)
            return denied
        loc = localization.get_settings(env)
        mt = multitenancy.get_settings(env)
        spec = api_docs.build_spec(
            env, settings, request.httprequest.host_url.rstrip('/'),
            localization=localization.public_settings(loc) if loc.get('enabled') else None,
            multitenancy=mt if mt.get('enabled') else None)
        return request.make_response(json.dumps(spec, ensure_ascii=False, indent=1),
                                     headers=[('Content-Type', 'application/json; charset=utf-8'),
                                              ('Content-Disposition', 'inline; filename="openapi.json"')])
