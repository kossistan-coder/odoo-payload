# -*- coding: utf-8 -*-
# pyrefly: ignore [missing-import]
from odoo.addons.payload_cms.payload import Collection, fields
from .seo_mixin import SeoMixin


class Project(Collection, SeoMixin):
    """Projets et réalisations du portfolio."""
    _name = 'projects'
    _localized = True
    _sequence = 140
    _label = 'Projet'
    _label_plural = 'Projets'
    _rec_name = 'title'
    _order = '-date_realisation, -createdAt'
    _columns = ['title', 'status', 'date_realisation', 'project_url']
    _search = ['title', 'description']
    _drafts = True

    # Contenu
    title = fields.Char("Titre du projet", required=True, localized=True, tab="Contenu", placeholder="ex: Plateforme LMS & E-commerce Headless")
    description = fields.RichTextEditor("Description détaillée du projet", localized=True, tab="Contenu")
    cover_image = fields.Image("Image principale (Cover)", localized=True, tab="Visuels")

    # Galerie d'images / captures
    gallery = fields.Array("Galerie de captures", singular="Capture", localized=True, tab="Visuels", fields={
        'image': fields.Image("Image", required=True, localized=True, row="img_row"),
        'caption': fields.Char("Légende / Description", localized=True, row="img_row"),
    })

    # Relations
    stack_tags = fields.Many2many('tech-stacks', "Technologies utilisées", localized=True, tab="Contenu")

    # Liens & Métadonnées
    project_url = fields.Char("Lien du projet en ligne", localized=True, tab="Liens", placeholder="https://mon-projet.com")
    github_url = fields.Char("Dépôt GitHub / GitLab", localized=True, tab="Liens", placeholder="https://github.com/...")
    date_realisation = fields.Date("Date de réalisation", localized=True, tab="Liens")

    # Barre latérale
    slug = fields.Slug(source='title', sidebar=True)
    status = fields.Selection([
        ('featured', 'Mis en avant (Top Projet)'),
        ('published', 'Publié standard'),
        ('archived', 'Archivé'),
    ], "Statut d'affichage", default='published', localized=True, sidebar=True, badge=True)
