# -*- coding: utf-8 -*-
"""API documentation of the modules using payload_cms: Swagger UI on /api-docs,
OpenAPI 3 on /api-docs/openapi.json (see ``payload_cms.payload.apidoc``)."""
import json

from markupsafe import Markup, escape

from odoo import http
from odoo.http import request

from ..tools import api_docs
from .api import PayloadRequest
from .utils import json_response

SWAGGER_PAGE = """<!DOCTYPE html>
<html lang="en" data-theme="%(theme)s" class="%(theme_class)s">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="color-scheme" content="light dark"/>
<script>
  /* Same theme as the admin (see static/src/admin/core/theme.js): ?theme=, else the
     `payload-theme` preference (localStorage / cookie), else the OS; kept in sync live. */
  (function () {
    var forced = new URLSearchParams(location.search).get("theme");
    var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    function apply() {
      var pref = forced;
      if (pref !== "light" && pref !== "dark") {
        try { pref = localStorage.getItem("payload-theme"); } catch (e) { pref = null; }
        if (!pref) { var m = document.cookie.match(/(?:^|;\\s*)payload-theme=([^;]*)/); pref = m && m[1]; }
      }
      var dark = pref === "dark" || (pref !== "light" && media && media.matches);
      document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
      document.documentElement.classList.toggle("dark-mode", Boolean(dark));
    }
    apply();
    if (media && media.addEventListener) { media.addEventListener("change", apply); }
    window.addEventListener("storage", function (ev) { if (ev.key === "payload-theme" || ev.key === null) { apply(); } });
  })();
</script>
<title>%(title)s</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&family=Roboto+Mono:ital,wght@0,100..700;1,100..700&display=swap"/>
<link rel="stylesheet" href="/payload_cms/static/lib/swagger-ui/swagger-ui.css"/>
<style>
  :root { --docs-bg: #fff; --docs-border: #ebebeb; --docs-link: #222; }
  html[data-theme="dark"] { --docs-bg: rgb(20, 20, 20); --docs-border: rgb(60, 60, 60); --docs-link: rgb(235, 235, 235); color-scheme: dark; }
  body { margin: 0; background: var(--docs-bg); }
  :root { --font-body: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; --font-mono: "Roboto Mono", "SF Mono", Menlo, Consolas, Monaco, monospace; }
  body, .swagger-ui, .swagger-ui .info .title, .swagger-ui .opblock-tag, .swagger-ui .btn, .swagger-ui input, .swagger-ui select, .swagger-ui textarea, .swagger-ui table, .swagger-ui .opblock .opblock-summary-description, .swagger-ui .opblock-description-wrapper p, .swagger-ui .response-col_status, .swagger-ui .parameter__name, .swagger-ui .model-title, .swagger-ui section.models h4 { font-family: var(--font-body); }
  .swagger-ui code, .swagger-ui pre, .swagger-ui .microlight, .swagger-ui .opblock .opblock-summary-path, .swagger-ui .opblock .opblock-summary-method, .swagger-ui .model, .swagger-ui .prop-type, .swagger-ui .parameter__type, .swagger-ui .parameter__in, .swagger-ui textarea.curl { font-family: var(--font-mono); }
  .swagger-ui .info { margin: 32px 0 24px; }
  .swagger-ui .scheme-container { box-shadow: none; border-top: 1px solid var(--docs-border); border-bottom: 1px solid var(--docs-border); }
  .swagger-ui .btn.authorize { border-color: var(--docs-link); color: var(--docs-link); }
  .swagger-ui .btn.authorize svg { fill: var(--docs-link); }
  .payload-docs-bar { display: flex; align-items: center; justify-content: space-between; padding: 12px 20px; border-bottom: 1px solid var(--docs-border); font: 14px var(--font-body); color: var(--docs-link); }
  .payload-docs-bar a { color: var(--docs-link); }
  .embed .payload-docs-bar { display: none; }
  /* Dark theme: Swagger UI's own `html.dark-mode` theme, on Payload's dark background */
  html.dark-mode, html.dark-mode .swagger-ui, html.dark-mode .swagger-ui .scheme-container { background: var(--docs-bg); }
  html.dark-mode .swagger-ui .scheme-container { box-shadow: none; }
  html.dark-mode .swagger-ui .scheme-container .btn.authorize { border-color: var(--docs-link); color: var(--docs-link); }
  html.dark-mode .swagger-ui .scheme-container .btn.authorize svg { color: var(--docs-link); fill: var(--docs-link); }
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
        # Theme of the admin (cookie set by static/src/admin/core/theme.js); "auto" is resolved client side.
        theme = _kw.get('theme') or request.httprequest.cookies.get('payload-theme')
        html = SWAGGER_PAGE % {
            'theme': theme if theme in ('light', 'dark') else 'light',
            'theme_class': 'dark-mode' if theme == 'dark' else '',
            'title': escape(settings.get('title') or 'API'),
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
        spec = api_docs.build_spec(env, settings, request.httprequest.host_url.rstrip('/'))
        return request.make_response(json.dumps(spec, ensure_ascii=False, indent=1),
                                     headers=[('Content-Type', 'application/json; charset=utf-8'),
                                              ('Content-Disposition', 'inline; filename="openapi.json"')])
