# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Collection, fields


class Participant(Collection):
    """Participants inscrits aux lives (les « users » de l'ancienne application).

    Les comptes d'administration, rôles et permissions de l'ancienne application
    sont gérés par Odoo (utilisateurs, groupes, droits d'accès).
    """
    _name = 'participants'
    _sequence = 150
    _label = 'Participant'
    _label_plural = 'Participants'
    _rec_name = 'full_name'
    _order = '-createdAt'
    _columns = ['full_name', 'email', 'phone', 'organization', 'createdAt']
    _search = ['nom', 'prenom', 'email']
    _public_read = False      # données personnelles
    _public_create = True     # inscription depuis le site (POST /api/participants)

    nom = fields.Char("Nom", api_name="lastName", required=True, row="identity")
    prenom = fields.Char("Prénom", api_name="firstName", required=True, row="identity")
    full_name = fields.Char("Nom complet", compute="{nom} {prenom}", sidebar=True)
    email = fields.Email("Email", required=True, unique=True, row="contact")
    phone = fields.Char("Téléphone", row="contact", placeholder="+228 90 00 00 00")
    organization = fields.Char("Structure / entreprise", row="work")
    profession = fields.Char("Profession", row="work")
    country = fields.Char("Pays", default="Togo", row="place")
    city = fields.Char("Ville", row="place")
    events = fields.Many2many('events', "Lives suivis", sidebar=True)
    newsletter = fields.Boolean("Accepte les communications", sidebar=True)
    active = fields.Boolean("Actif", default=True, sidebar=True, badge=("Actif", "Inactif"))
