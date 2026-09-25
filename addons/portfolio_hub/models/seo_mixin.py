# -*- coding: utf-8 -*-
# pyrefly: ignore [missing-import]
from odoo.addons.payload_cms.payload import fields


class SeoMixin:
    """Mixin pour ajouter les balises SEO et Open Graph aux collections Payload CMS."""
    meta_title = fields.Char(
        "Titre SEO",
        tab="SEO",
        localized=True,
        help="Titre personnalisé pour la balise <title> et les moteurs de recherche",
    )
    meta_description = fields.Text(
        "Description SEO",
        tab="SEO",
        localized=True,
        help="Description concise (150-160 caractères) pour les moteurs de recherche",
    )
    og_image = fields.Image(
        "Image Open Graph (OG)",
        tab="SEO",
        localized=True,
        help="Image affichée lors des partages sur les réseaux sociaux (Twitter, LinkedIn...)",
    )
