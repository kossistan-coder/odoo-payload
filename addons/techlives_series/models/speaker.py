# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Collection, fields


class Speaker(Collection):
    """Intervenants et modérateurs des lives."""
    _name = 'speakers'
    _sequence = 130
    _label = 'Intervenant'
    _label_plural = 'Intervenants'
    _rec_name = 'full_name'
    _order = 'nom'
    _columns = ['full_name', 'function', 'active', 'hidespeaker']
    _search = ['nom', 'prenom', 'pseudo', 'email']

    nom = fields.Char("Nom", api_name="lastName", required=True, row="identity", placeholder="AGBEWONOU")
    prenom = fields.Char("Prénom", api_name="firstName", required=True, row="identity", placeholder="Darwin")
    full_name = fields.Char("Nom complet", compute="{nom} {prenom}", sidebar=True)
    function = fields.Char("Fonction", api_name="jobTitle", translate=True,
                           placeholder="Consultant et Conseiller en digital et en numérique")
    bio = fields.Text("Biographie", translate=True)
    profile = fields.Image("Photo de profil")
    social_links = fields.Array("Réseaux sociaux", singular="Lien", row_label="url", fields={
        'platform': fields.Many2one('socials', "Plateforme", required=True, row="link", width="33%"),
        'url': fields.Char("URL", required=True, row="link", width="67%",
                           pattern=r"(https?://)?([\w\d-]+\.)+[\w-]{2,}(/.*)?",
                           pattern_message="Veuillez saisir une URL valide."),
    })
    # barre latérale
    email = fields.Email("Email", unique=True, sidebar=True)
    pseudo = fields.Char("Pseudo", api_name="nickname", sidebar=True)
    active = fields.Boolean("Actif", default=True, sidebar=True, badge=("Actif", "Inactif"))
    hidespeaker = fields.Boolean(
        "Masquer sur la page d'accueil", api_name="hiddenOnHome", sidebar=True, badge={True: ("Masqué", "muted"), False: ("Visible", "success")},
        help="Un intervenant peut être modérateur sur d'autres lives : coché, il n'apparaît pas "
             "dans la section « Intervenants » de la page d'accueil.")
    events = fields.Many2many('events', "Lives", sidebar=True,
                              help="Lives auxquels la personne a participé (intervenant ou modérateur).")
