# -*- coding: utf-8 -*-
{
    'name': 'Payload CMS',
    'version': '18.0.1.0.0',
    'category': 'Website/Content Management',
    'sequence': 10,
    'summary': 'Gestion de contenu déclarative inspirée de Payload CMS avec éditeur Lexical',
    'description': """
Payload CMS pour Odoo
=====================
Ce module intègre l'expérience de gestion de contenu de Payload CMS directement dans le backend Odoo :
- Concept de Collections typées (pages, posts, etc.)
- Champs déclaratifs (text, richText, relationship, array, blocks, upload, select)
- Éditeur de texte riche basé sur Lexical (vanilla) via un widget OWL dédié
- Stockage JSON au format compatible avec l'arbre sérialisé Lexical / Payload CMS
- Mise en page à deux colonnes avec sidebar pour les statuts et métadonnées
    """,
    'author': 'Antigravity / Payload CMS for Odoo',
    'website': 'https://payloadcms.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
    ],
    'data': [
        'security/payload_cms_security.xml',
        'security/ir.model.access.csv',
        'views/cms_page_views.xml',
        'views/cms_collection_views.xml',
        'views/cms_field_definition_views.xml',
        'views/cms_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Librairie Lexical standalone (vanilla)
            'payload_cms/static/lib/lexical/lexical.bundle.js',
            # Feuilles de styles
            'payload_cms/static/src/scss/payload_cms.scss',
            'payload_cms/static/src/scss/lexical_editor.scss',
            # Logique de l'éditeur Lexical
            'payload_cms/static/src/js/lexical_editor/lexical_theme.js',
            'payload_cms/static/src/js/lexical_editor/lexical_helper.js',
            'payload_cms/static/src/js/lexical_editor/lexical_features.js',
            'payload_cms/static/src/js/lexical_editor/lexical_renderer.js',
            # Widgets OWL pour champs Odoo
            'payload_cms/static/src/js/widgets/lexical_field.js',
            'payload_cms/static/src/js/widgets/payload_media_card.js',
            'payload_cms/static/src/js/widgets/payload_live_preview.js',
            # Templates QWeb OWL
            'payload_cms/static/src/xml/lexical_field.xml',
            'payload_cms/static/src/xml/payload_media_card.xml',
            'payload_cms/static/src/xml/payload_live_preview.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': True,
}
