# -*- coding: utf-8 -*-
# pyrefly: ignore [missing-import]
from odoo import models, fields


class ProductTemplate(models.Model):
    """Extension du produit Odoo natif pour lier les formations et services Payload CMS."""
    _inherit = 'product.template'

    formation_document_id = fields.Many2one(
        'cms.document',
        string="Formation CMS liée",
        domain="[('collection_id.slug', '=', 'formations')]",
        help="Document de la collection Formations associé à ce produit vendable",
    )
    service_document_id = fields.Many2one(
        'cms.document',
        string="Service CMS lié",
        domain="[('collection_id.slug', '=', 'services')]",
        help="Document de la collection Services associé à ce produit vendable",
    )
