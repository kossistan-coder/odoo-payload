# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re

class CmsFieldDefinition(models.Model):
    """
    Modèle déclarant les champs typés d'une collection façon Payload CMS.
    Types supportés : text, richtext, relationship, array, blocks, upload, select.
    """
    _name = 'cms.field.definition'
    _description = 'Définition de champ CMS'
    _order = 'sequence asc, id asc'

    sequence = fields.Integer(
        string="Ordre",
        default=10
    )
    collection_id = fields.Many2one(
        'cms.collection',
        string="Collection",
        required=True,
        ondelete='cascade',
        index=True
    )
    name = fields.Char(
        string="Nom technique du champ",
        required=True,
        help="Nom de la propriété en snake_case (ex: 'header_title', 'featured_image')."
    )
    label = fields.Char(
        string="Libellé affiché",
        required=True,
        help="Libellé du champ affiché dans l'interface d'édition."
    )
    field_type = fields.Selection(
        [
            ('text', 'Texte court (text)'),
            ('richtext', 'Texte riche Lexical (richText)'),
            ('relationship', 'Relation / Référence (relationship)'),
            ('array', 'Tableau d éléments (array)'),
            ('blocks', 'Blocs dynamiques (blocks)'),
            ('upload', 'Fichier / Média (upload)'),
            ('select', 'Menu déroulant / Choix (select)')
        ],
        string="Type de champ",
        required=True,
        default='text'
    )
    required = fields.Boolean(
        string="Obligatoire",
        default=False
    )
    localized = fields.Boolean(
        string="Traductible (i18n)",
        default=False
    )
    config = fields.Json(
        string="Configuration spécifique (JSON)",
        default=lambda self: {},
        help="Options avancées au format JSON (ex: relationModel, selectOptions, maxDepth...)."
    )

    _sql_constraints = [
        (
            'collection_field_unique',
            'unique(collection_id, name)',
            "Le nom technique du champ doit être unique pour chaque collection !"
        )
    ]

    @api.constrains('name')
    def _check_name_format(self):
        for record in self:
            if record.name and not re.match(r'^[a-z0-9_]+$', record.name):
                raise ValidationError(
                    _("Le nom de champ '%s' doit être en minuscules avec des caractères alphanumériques ou des tirets bas (_).") % record.name
                )
