# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Collection, fields


class EventRole(Collection):
    """Rôles d'une personne dans un live (intervenant, modérateur, animateur, invité...)."""
    _name = 'event-roles'
    _sequence = 190
    _label = 'Rôle'
    _label_plural = 'Rôles événement'
    _rec_name = 'name'
    _columns = ['name', 'slug']

    name = fields.Char("Nom", required=True, translate=True, placeholder="Modérateur")
    description = fields.Text("Description", translate=True)
    slug = fields.Slug(source='name')
