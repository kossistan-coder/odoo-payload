# -*- coding: utf-8 -*-
{
    'name': 'Payload CMS',
    'version': '18.0.2.0.0',
    'category': 'Website/Content Management',
    'sequence': 10,
    'summary': 'Headless CMS for Odoo with the Payload CMS admin UI and REST API',
    'description': """
Payload CMS for Odoo
====================
A headless CMS reproducing Payload CMS (https://payloadcms.com):

- Admin panel on /admin with the same UI as Payload (light theme): dashboard,
  list view (search, columns, filters, sort, pagination, bulk actions),
  edit view (fields, sidebar, drafts, autosave, versions, API tab),
  live preview, uploads with focal point, Lexical rich text editor, slug fields...
- Collections, globals and fields declared from Odoo (or code-first with
  Payload-like config dictionaries).
- Payload-compatible REST API on /api: where queries, depth, pagination,
  drafts, versions, uploads, JWT / API key / session authentication, CORS.
    """,
    'author': 'Payload CMS for Odoo',
    'website': 'https://payloadcms.com',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/payload_cms_security.xml',
        'security/ir.model.access.csv',
        'views/cms_collection_views.xml',
        'views/cms_field_definition_views.xml',
        'views/cms_menus.xml',
        'views/cms_document_views.xml',
        'views/admin_templates.xml',
        'data/cms_data.xml',
        'data/form_builder_data.xml',
    ],
    'assets': {
        # Client action embedding the Payload admin inside the Odoo web client
        'web.assets_backend': [
            'payload_cms/static/src/backend/**/*',
        ],
        'payload_cms.assets_admin': [
            # Payload's own SCSS compiled with Tailwind CSS (see static/admin_src)
            'payload_cms/static/dist/admin.css',
            # Runtime: Odoo module loader + OWL
            'web/static/src/module_loader.js',
            'web/static/lib/owl/owl.js',
            'web/static/lib/owl/odoo_module.js',
            'web/static/src/core/template_inheritance.js',
            'web/static/src/core/templates.js',
            # Vanilla Lexical bundle (window.PayloadLexical)
            'payload_cms/static/lib/lexical/lexical.bundle.js',
            # Admin application
            'payload_cms/static/src/admin/**/*.js',
            'payload_cms/static/src/admin/**/*.xml',
        ],
    },
    'installable': True,
    'application': True,
}
