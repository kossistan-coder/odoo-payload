# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
import unicodedata

def _default_lexical_content(self=None):
    """
    Arbre JSON d'état initial de l'éditeur Lexical compatible avec Payload CMS.
    Comprend un nœud racine 'root' avec un paragraphe enfant vide.
    """
    return {
        "root": {
            "children": [
                {
                    "children": [],
                    "direction": "ltr",
                    "format": "",
                    "indent": 0,
                    "type": "paragraph",
                    "version": 1
                }
            ],
            "direction": "ltr",
            "format": "",
            "indent": 0,
            "type": "root",
            "version": 1
        }
    }

class CmsPage(models.Model):
    """
    Modèle de base représentant la collection 'pages' dans Payload CMS.
    Gère le contenu rédactionnel riche (Lexical JSON), les blocs, le cycle de vie et le SEO.
    """
    _name = 'cms.page'
    _description = 'Page CMS'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'write_date desc, id desc'

    title = fields.Char(
        string="Titre de la page",
        required=True,
        tracking=True,
        help="Titre principal de la page."
    )
    slug = fields.Char(
        string="Slug URL",
        required=True,
        index=True,
        tracking=True,
        help="Chemin URL unique pour cette page (ex: 'a-propos', 'tarifs')."
    )
    status = fields.Selection(
        [
            ('draft', 'Brouillon'),
            ('published', 'Publié'),
            ('archived', 'Archivé')
        ],
        string="Statut de publication",
        default='draft',
        required=True,
        tracking=True,
        index=True
    )
    content = fields.Json(
        string="Contenu principal (Lexical JSON)",
        default=_default_lexical_content,
        help="Arbre de nœuds sérialisés généré par l'éditeur Lexical compatible Payload CMS."
    )
    block_ids = fields.One2many(
        'cms.block',
        'page_id',
        string="Blocs modulaires",
        copy=True,
        help="Composants et sections structurées rattachés à la page."
    )
    author_id = fields.Many2one(
        'res.users',
        string="Auteur",
        default=lambda self: self.env.user,
        tracking=True
    )
    published_at = fields.Datetime(
        string="Date de publication",
        tracking=True
    )
    featured_image = fields.Binary(
        string="Image principale (Upload)",
        attachment=True,
        help="Image d'illustration principale de la page."
    )
    featured_image_filename = fields.Char(
        string="Nom de l'image"
    )
    meta_title = fields.Char(
        string="Méta-titre SEO",
        help="Titre pour les moteurs de recherche (laisser vide pour utiliser le titre de la page)."
    )
    meta_description = fields.Text(
        string="Méta-description SEO",
        help="Court résumé pour le référencement naturel et les réseaux sociaux."
    )

    _sql_constraints = [
        ('slug_unique', 'unique(slug)', "Le slug URL de la page doit être unique !")
    ]

    @api.onchange('title')
    def _onchange_title_generate_slug(self):
        """
        Génère automatiquement un slug lisible à partir du titre si aucun slug n'est défini.
        """
        if self.title and not self.slug:
            self.slug = self._slugify(self.title)

    @api.constrains('slug')
    def _check_slug_format(self):
        for record in self:
            if record.slug and not re.match(r'^[a-z0-9\-_]+$', record.slug):
                raise ValidationError(
                    _("Le slug '%s' n'est pas valide. Utilisez uniquement des minuscules, des chiffres et des tirets.") % record.slug
                )

    def action_publish(self):
        """Bascule le statut en publié et renseigne la date si elle est vide."""
        for record in self:
            vals = {'status': 'published'}
            if not record.published_at:
                vals['published_at'] = fields.Datetime.now()
            record.write(vals)

    def action_set_to_draft(self):
        """Bascule le statut en brouillon."""
        self.write({'status': 'draft'})

    def action_archive(self):
        """Bascule le statut en archivé."""
        self.write({'status': 'archived'})

    @staticmethod
    def _slugify(text):
        """Nettoie et transforme un texte en slug URL sécurisé."""
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
        text = re.sub(r'[^\w\s-]', '', text).strip().lower()
        return re.sub(r'[-\s]+', '-', text)
