# -*- coding: utf-8 -*-
# pyrefly: ignore [missing-import]
from odoo.addons.payload_cms.payload import Collection, fields


class Category(Collection):
    """Catégories pour le blog et la veille technologique."""
    _name = 'categories'
    _localized = True
    _sequence = 160
    _label = 'Catégorie'
    _label_plural = 'Catégories'
    _rec_name = 'name'
    _columns = ['name', 'slug']
    _search = ['name', 'description']

    name = fields.Char("Nom de la catégorie", required=True, localized=True, placeholder="ex: Architecture Web")
    slug = fields.Slug(source='name', sidebar=True)
    description = fields.Text("Description", localized=True)
    color = fields.Char("Couleur (HEX)", localized=True, placeholder="#3B82F6")


class Tag(Collection):
    """Tags pour le blog, la veille et les projets."""
    _name = 'tags'
    _localized = True
    _sequence = 170
    _label = 'Tag'
    _label_plural = 'Tags'
    _rec_name = 'name'
    _columns = ['name', 'slug']
    _search = ['name']

    name = fields.Char("Nom du tag", required=True, localized=True, placeholder="ex: GraphQL, Microservices")
    slug = fields.Slug(source='name', sidebar=True)
