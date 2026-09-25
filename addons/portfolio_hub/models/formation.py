# -*- coding: utf-8 -*-
# pyrefly: ignore [missing-import]
from odoo.addons.payload_cms.payload import Collection, fields
from .seo_mixin import SeoMixin


class FormationFeature(Collection):
    """Caractéristiques et avantages réutilisables pour les formations."""
    _name = 'formation-features'
    _localized = True
    _sequence = 112
    _label = 'Caractéristique'
    _label_plural = 'Caractéristiques de formation'
    _rec_name = 'label'
    _columns = ['label', 'icon']

    label = fields.Char("Libellé", required=True, localized=True, placeholder="ex: Accès à vie aux mises à jour")
    icon = fields.Char("Icône", localized=True, placeholder="ex: lucide-infinity, fa-check")
    description = fields.Char("Description courte", localized=True)


class FormationModule(Collection):
    """Modules / chapitres de cours liés aux formations."""
    _name = 'formation-modules'
    _localized = True
    _sequence = 114
    _label = 'Module de formation'
    _label_plural = 'Modules de formation'
    _rec_name = 'title'
    _order = 'sequence, title'
    _columns = ['title', 'formation', 'sequence']

    formation = fields.Many2one('formations', "Formation", required=True, localized=True)
    title = fields.Char("Titre du module", required=True, localized=True, placeholder="ex: Module 1 : Fondations et Architecture")
    description = fields.RichTextEditor("Description du module", localized=True)
    sequence = fields.Integer("Ordre", default=10, localized=True, sidebar=True)


class Formation(Collection, SeoMixin):
    """Catalogue des formations techniques avec programme et stack."""
    _name = 'formations'
    _localized = True
    _sequence = 110
    _label = 'Formation'
    _label_plural = 'Formations'
    _rec_name = 'name'
    _order = '-is_featured, -createdAt'
    _columns = ['name', 'level', 'duration_hours', 'is_featured', 'active', '_status']
    _search = ['name', 'subtitle']
    _drafts = True

    # Contenu
    name = fields.Char("Titre de la formation", required=True, tab="Contenu", placeholder="ex: Architecture Fullstack Next.js & Payload", localized=True)
    subtitle = fields.Char("Sous-titre", tab="Contenu", placeholder="Devenez autonome sur l'architecture headless moderne", localized=True)
    description = fields.RichTextEditor("Description détaillée", tab="Contenu", localized=True)
    cover_image = fields.Image("Image de couverture", localized=True, tab="Visuels")

    # Détails
    level = fields.Selection([
        ('beginner', 'Débutant'),
        ('intermediate', 'Intermédiaire'),
        ('advanced', 'Avancé'),
    ], "Niveau", default='beginner', required=True, localized=True, row="details", tab="Contenu", badge=True)
    duration_hours = fields.Integer("Durée (heures)", default=10, localized=True, row="details", tab="Contenu")

    # Relations
    stack_tags = fields.Many2many('tech-stacks', "Stack technique", localized=True, tab="Contenu")
    features = fields.Many2many('formation-features', "Points forts & Avantages", localized=True, tab="Contenu")

    # Programme (Modules intégrés éditables en tableau répété)
    modules = fields.Array("Programme détaillé (Modules)", singular="Module", localized=True, tab="Programme", row_label="title", fields={
        'title': fields.Char("Titre du module", required=True, localized=True, row="m_head"),
        'duration': fields.Char("Durée (ex: 2h30)", localized=True, row="m_head", width="30%"),
        'description': fields.Text("Contenu abordé", localized=True),
    })

    # Barre latérale
    slug = fields.Slug(source='name', sidebar=True)
    product_id = fields.Integer(
        "ID Produit Odoo lié (product.template)",
        localized=True,
        sidebar=True,
        help="ID du template produit Odoo correspondant pour l'achat et la facturation",
    )
    is_featured = fields.Boolean("Mis en avant (Hero)", default=False, localized=True, sidebar=True, badge=("Top", "Standard"))
    active = fields.Boolean("Actif", default=True, localized=True, sidebar=True, badge=("Actif", "Inactif"))