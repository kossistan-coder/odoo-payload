# -*- coding: utf-8 -*-
{
    'name': "Palais de Lomé",

    'summary': "Site du Palais de Lomé, géré avec Payload CMS pour Odoo",

    'description': """
Collections, globals et contenus du site du Palais de Lomé,
construits sur le module payload_cms (admin Payload, API REST, live preview).
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    'category': 'Website/CMS',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',

    # payload_cms: collections / globals (code-first via cms.collection._sync_schema),
    # REST API /api, admin /admin
    'depends': ['base', 'payload_cms'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'views/menus.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'application': True,
    'installable': True,
}
