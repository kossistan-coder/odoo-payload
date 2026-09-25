# -*- coding: utf-8 -*-
# pyrefly: ignore [missing-import]
from odoo.addons.payload_cms.payload import Collection, fields
from .seo_mixin import SeoMixin


class Post(Collection, SeoMixin):
    """Articles de blog et fiches de veille technologique."""
    _name = 'posts'
    _localized = True
    _sequence = 130
    _label = 'Article'
    _label_plural = 'Articles'
    _rec_name = 'title'
    _order = '-published_date'
    _columns = ['title', 'category', 'is_veille', 'published_date', 'reading_time', '_status']
    _search = ['title', 'excerpt']
    _drafts = True

    # Contenu
    title = fields.Char("Titre de l'article", required=True, localized=True, tab="Contenu", placeholder="ex: Pourquoi migrer vers Payload 3.0")
    excerpt = fields.Text("Extrait / Chapeau", localized=True, tab="Contenu", placeholder="Résumé accrocheur affiché dans les cartes et aperçus...")
    content = fields.RichTextEditor("Contenu complet", localized=True, tab="Contenu")
    cover_image = fields.Image("Image de couverture", localized=True, tab="Visuels")

    # Catégorisation et technologies
    category = fields.Many2one('categories', "Catégorie", localized=True, tab="Contenu")
    tags = fields.Many2many('tags', "Tags thématiques", localized=True, tab="Contenu")
    stack_tags = fields.Many2many('tech-stacks', "Technologies abordées", localized=True, tab="Contenu")

    # Barre latérale
    slug = fields.Slug(source='title', sidebar=True)
    is_veille = fields.Boolean(
        "Format Veille rapide",
        default=False,
        localized=True,
        sidebar=True,
        badge={True: ("Veille", "info"), False: ("Analyse", "primary")},
        help="Coché pour un condensé de veille technologique rapide, non coché pour une analyse de fond.",
    )
    published_date = fields.Datetime("Date de publication", localized=True, sidebar=True)
    reading_time = fields.Integer("Temps de lecture (minutes)", default=5, localized=True, sidebar=True)
    author = fields.Char("Auteur", default="Stan", localized=True, sidebar=True)
