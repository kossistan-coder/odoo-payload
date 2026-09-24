# -*- coding: utf-8 -*-
{
    'name': "Tech Lives Series",

    'summary': "CMS du site Tech Lives Series (lives, épisodes, intervenants, page d'accueil)",

    'description': """
Site https://tech-lives-series.gouv.tg/ géré avec Payload CMS pour Odoo :
lives, épisodes (replays), intervenants, organisateurs, réseaux sociaux, rôles,
participants, messages de contact, suivi des emails et CMS de la page d'accueil.
    """,

    'author': "My Company",
    'website': "https://tech-lives-series.gouv.tg/",

    'category': 'Website/CMS',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',

    # payload_cms : les collections sont déclarées en Python dans models/ (payload_cms.payload)
    'depends': ['base', 'payload_cms'],

    'data': [
        'views/views.xml',
        'views/templates.xml',
        'views/menus.xml',
    ],
    # écrans ajoutés à l'admin OdooPayload (payload_cms/static/src/admin/core/extensions.js)
    'assets': {
        'payload_cms.assets_admin': [
            'techlives_series/static/src/payload/**/*',
        ],
    },
    'demo': [
        'demo/demo.xml',
    ],
    'application': True,
    'installable': True,
}
