# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Collection, fields


class Social(Collection):
    """Réseaux sociaux (LinkedIn, X, Facebook...) utilisés par les liens des intervenants."""
    _name = 'socials'
    _sequence = 180
    _label = 'Réseau social'
    _label_plural = 'Réseaux sociaux'
    _rec_name = 'name'
    _order = 'sequence'
    _columns = ['name', 'base_url', 'active']

    name = fields.Char("Nom", required=True, unique=True, placeholder="LinkedIn")
    icon = fields.Image("Icône")
    base_url = fields.Char("URL de base", placeholder="https://www.linkedin.com/in/")
    sequence = fields.Integer("Ordre", default=10, sidebar=True)
    active = fields.Boolean("Actif", default=True, sidebar=True, badge=("Actif", "Inactif"))
