# -*- coding: utf-8 -*-
from odoo import models, fields

class CmsBlock(models.Model):
    """
    Instance de bloc réutilisable dans le contenu d'une page (similaire aux Blocks de Payload CMS).
    Prévu pour être enrichi dans les itérations suivantes avec drag & drop.
    """
    _name = 'cms.block'
    _description = 'Bloc de contenu modulaire'
    _order = 'sequence asc, id asc'

    sequence = fields.Integer(
        string="Ordre",
        default=10
    )
    page_id = fields.Many2one(
        'cms.page',
        string="Page associée",
        ondelete='cascade',
        index=True
    )
    name = fields.Char(
        string="Titre / Repère du bloc",
        help="Libellé optionnel pour repérer facilement le bloc dans la liste."
    )
    block_type = fields.Selection(
        [
            ('hero', 'Bannière d accueil (Hero)'),
            ('features', 'Grille de fonctionnalités (Features)'),
            ('cta', 'Appel à l action (Call To Action)'),
            ('testimonial', 'Témoignages / Avis'),
            ('faq', 'Questions fréquentes (FAQ)'),
            ('custom', 'Bloc structuré libre (Custom JSON)')
        ],
        string="Type de bloc",
        required=True,
        default='custom'
    )
    data = fields.Json(
        string="Données du bloc (JSON)",
        default=lambda self: {},
        help="Propriétés et données sérialisées du bloc au format JSON."
    )
