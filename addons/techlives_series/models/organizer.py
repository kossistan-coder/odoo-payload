# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Collection, fields


class Organizer(Collection):
    """Organisateurs et partenaires (section « Organisateurs » de la page d'accueil)."""
    _name = 'organizers'
    _sequence = 140
    _label = 'Organisateur'
    _label_plural = 'Organisateurs'
    _rec_name = 'name'
    _order = 'sequence'
    _columns = ['name', 'type', 'website', 'active']

    name = fields.Char("Nom", required=True, placeholder="Agence Togo Digital")
    logo = fields.Image("Logo", required=True)
    website = fields.Char("Site web", placeholder="https://")
    description = fields.Text("Description", translate=True)
    type = fields.Selection([('organizer', 'Organisateur', 'primary'), ('co_organizer', 'Co-organisateur', 'info'),
                             ('partner', 'Partenaire', 'success'), ('sponsor', 'Sponsor', 'warning')],
                            "Type", default='organizer', sidebar=True)
    sequence = fields.Integer("Ordre d'affichage", default=10, sidebar=True)
    active = fields.Boolean("Actif", default=True, sidebar=True, badge=("Actif", "Inactif"))
