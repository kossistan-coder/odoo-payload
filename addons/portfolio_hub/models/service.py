# -*- coding: utf-8 -*-
# pyrefly: ignore [missing-import]
from odoo.addons.payload_cms.payload import Collection, fields
from .seo_mixin import SeoMixin


class Service(Collection, SeoMixin):
    """Offres de services : mentorat individuel, audits d'architecture, workshops et B2B."""
    _name = 'services'
    _localized = True
    _sequence = 120
    _label = 'Service'
    _label_plural = 'Services'
    _rec_name = 'name'
    _order = 'sequence, name'
    _columns = ['name', 'service_type', 'price_display', 'sequence', 'is_active', '_status']
    _search = ['name', 'description']
    _drafts = True

    # Contenu
    name = fields.Char("Nom du service", required=True, localized=True, tab="Contenu", placeholder="ex: Audit Architecture & Performance")
    service_type = fields.Selection([
        ('mentorat', 'Mentorat individuel'),
        ('audit', 'Audit de code & architecture'),
        ('workshop', 'Workshop / Atelier technique'),
        ('formation_b2b', 'Formation B2B sur-mesure'),
    ], "Type de service", default='mentorat', required=True, localized=True, row="srv_header", tab="Contenu", badge=True)
    price_display = fields.Char("Prix affiché", localized=True, row="srv_header", tab="Contenu", placeholder="ex: À partir de 500€ / jour")
    description = fields.RichTextEditor("Description détaillée", localized=True, tab="Contenu")

    # Appel à l'action (CTA)
    cta_label = fields.Char("Libellé du CTA", default="Réserver un échange", localized=True, row="cta", tab="CTA")
    cta_url = fields.Char("Lien du CTA", default="/contact", localized=True, row="cta", tab="CTA", placeholder="https://calendly.com/... ou /contact")

    # Barre latérale
    slug = fields.Slug(source='name', sidebar=True)
    product_id = fields.Integer(
        "ID Produit Odoo lié (product.template)",
        localized=True,
        sidebar=True,
        help="ID du template produit Odoo optionnel si facturé ou vendu directement en ligne",
    )
    sequence = fields.Integer("Ordre d'affichage", default=10, localized=True, sidebar=True)
    is_active = fields.Boolean("Actif", default=True, localized=True, sidebar=True, badge=("Actif", "Inactif"))
