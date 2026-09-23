# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re

class CmsCollection(models.Model):
    """
    Méta-modèle représentant une Collection de type Payload CMS.
    Permet de déclarer et configurer les types de contenu et leurs attributs.
    """
    _name = 'cms.collection'
    _description = 'Collection Payload CMS'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(
        string="Identifiant technique (slug)",
        required=True,
        index=True,
        tracking=True,
        help="Nom technique unique en minuscules (ex: 'pages', 'articles', 'produits')."
    )
    label = fields.Char(
        string="Nom affiché (Label)",
        required=True,
        tracking=True,
        help="Libellé lisible affiché dans l'interface et les menus."
    )
    icon = fields.Char(
        string="Icône FontAwesome",
        default="fa-folder-open",
        help="Classe d'icône FontAwesome pour la collection (ex: fa-file-text-o, fa-newspaper-o)."
    )
    description = fields.Text(
        string="Description",
        help="Description fonctionnelle du contenu stocké dans cette collection."
    )
    active = fields.Boolean(
        string="Actif",
        default=True,
        help="Désactiver une collection sans supprimer ses données."
    )
    field_ids = fields.One2many(
        'cms.field.definition',
        'collection_id',
        string="Champs déclarés",
        copy=True
    )
    field_count = fields.Integer(
        string="Nombre de champs",
        compute="_compute_field_count",
        store=True
    )

    _sql_constraints = [
        ('name_unique', 'unique(name)', "L'identifiant technique de la collection doit être unique !")
    ]

    @api.depends('field_ids')
    def _compute_field_count(self):
        for record in self:
            record.field_count = len(record.field_ids)

    @api.constrains('name')
    def _check_name_format(self):
        for record in self:
            if record.name and not re.match(r'^[a-z0-9_]+$', record.name):
                raise ValidationError(
                    _("Le nom technique de la collection '%s' doit être composé uniquement de lettres minuscules, chiffres et tirets du bas (_).") % record.name
                )
