# -*- coding: utf-8 -*-
# pyrefly: ignore [missing-import]
from odoo.addons.payload_cms.payload import Collection, fields


class TechStack(Collection):
    """Technologies, langages, frameworks et outils transverses du portfolio."""
    _name = 'tech-stacks'
    _localized = True
    _sequence = 150
    _label = 'Stack Technique'
    _label_plural = 'Stacks Techniques'
    _rec_name = 'name'
    _order = 'sequence, name'
    _columns = ['name', 'category', 'color', 'sequence', 'active']
    _search = ['name']

    name = fields.Char("Nom de la techno", required=True, localized=True, placeholder="ex: NestJS, Payload 3.0, Angular 18")
    slug = fields.Slug(source='name', sidebar=True)
    logo = fields.Image("Logo / Icône", localized=True)
    category = fields.Selection([
        ('language', 'Langage'),
        ('framework', 'Framework'),
        ('tool', 'Outil'),
        ('database', 'Base de données'),
        ('cloud', 'Cloud / DevOps'),
    ], "Catégorie", default='framework', required=True, localized=True, badge=True)
    color = fields.Char("Couleur (HEX)", localized=True, placeholder="#61DAFB", help="Couleur d'accentuation en hexadécimal")
    sequence = fields.Integer("Ordre d'affichage", default=10, localized=True, sidebar=True)
    active = fields.Boolean("Actif", default=True, localized=True, sidebar=True, badge=("Actif", "Inactif"))
