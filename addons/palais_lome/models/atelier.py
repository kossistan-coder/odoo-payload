# -*- coding: utf-8 -*-
"""Ateliers, expositions et programmes du Palais de Lomé.

Collection Payload déclarée comme un modèle Odoo (API ``payload_cms.payload``) :
elle est créée / mise à jour automatiquement à l'installation et à la mise à jour
du module, et disponible dans l'admin (/admin/collections/ateliers) et dans l'API
REST (/api/ateliers).
"""
from odoo.addons.payload_cms.payload import Collection, fields

EVENT_TYPES = [
    ('atelier', 'Atelier'),
    ('exposition', 'Exposition'),
    ('visite', 'Visite'),
    ('conference', 'Conférence'),
    ('spectacle', 'Spectacle'),
    ('projection', 'Projection'),
    ('evenement', 'Événement'),
]
STAGES = [('upcoming', 'À venir'), ('ongoing', 'En cours'), ('finished', 'Terminé'), ('cancelled', 'Annulé')]
LANGUAGES = [('fr', 'Français'), ('en', 'English'), ('de', 'Deutsch'), ('es', 'Español')]
THEMES = [
    ('arts-visuels', 'Arts visuels'),
    ('photographie', 'Photographie'),
    ('histoire-patrimoine', 'Histoire & patrimoine'),
    ('musique', 'Musique'),
    ('danse', 'Danse'),
    ('design', 'Design & artisanat'),
    ('nature', 'Nature & jardins'),
    ('litterature', 'Littérature'),
    ('jeune-public', 'Jeune public'),
    ('famille', 'Famille'),
]


class Atelier(Collection):
    _name = 'ateliers'
    _label = 'Atelier'
    _label_plural = 'Ateliers'
    _description = "Ateliers, expositions et programmes du Palais de Lomé."
    _rec_name = 'title'
    _order = '-date_begin'
    _columns = ['title', 'event_type', 'date_begin', 'date_end', 'stage', '_status']
    _search = ['title', 'subtitle', 'slug']
    _drafts = True
    _autosave = True

    # ------------------------------------------------------------------ Contenu
    title = fields.Char("Titre", required=True, translate=True, tab="Contenu",
                        placeholder="Lomé : portraits d’une ville")
    subtitle = fields.Char("Sous-titre", translate=True, tab="Contenu")
    description_short = fields.Text("Résumé", translate=True, tab="Contenu",
                                    help="Texte court affiché dans les listes et les cartes du programme.")
    description = fields.RichTextEditor("Description", translate=True, tab="Contenu")
    credits = fields.Array("Crédits", singular="Crédit", tab="Contenu", row_label="name",
                           help="Ex. « Commissariat d’exposition — Hervé Pana », « Scénographie — Aissa Dione ».",
                           fields={
                               'role': fields.Char("Rôle", required=True, translate=True, row="credit",
                                                   placeholder="Commissariat d’exposition"),
                               'name': fields.Char("Nom", required=True, row="credit", placeholder="Hervé Pana"),
                           })
    artists = fields.Array("Artistes / intervenants", singular="Artiste", tab="Contenu", row_label="name",
                           collapsed=True, fields={
                               'name': fields.Char("Nom", required=True, row="identity"),
                               'role': fields.Char("Rôle", translate=True, row="identity",
                                                   placeholder="Photographe, commissaire..."),
                               'photo': fields.Image("Photo"),
                               'bio': fields.Text("Biographie", translate=True),
                           })

    # -------------------------------------------------------------- Dates & lieu
    date_begin = fields.Datetime("Début", required=True, tab="Dates & lieu", row="dates")
    date_end = fields.Datetime("Fin", tab="Dates & lieu", row="dates")
    date_tz = fields.Char("Fuseau horaire", default="GMT", help="Lomé : GMT (UTC+0).", tab="Dates & lieu", row="tz")
    lang = fields.Selection(LANGUAGES, "Langue de l’événement", tab="Dates & lieu", row="tz")
    schedule_info = fields.Text("Horaires", translate=True, tab="Dates & lieu", placeholder="De 10h00 à 17h00")
    access_info = fields.Text("Informations d’accès", translate=True, tab="Dates & lieu")
    note_info = fields.Text("Informations complémentaires", translate=True, tab="Dates & lieu")
    venue = fields.Group("Lieu", tab="Dates & lieu", fields={
        'name': fields.Char("Nom du lieu", default="PALAIS DE LOMÉ"),
        'street': fields.Char("Rue", row="street"),
        'street2': fields.Char("Complément", row="street"),
        'zip': fields.Char("Code postal", row="city"),
        'city': fields.Char("Ville", default="Lomé", row="city"),
        'state': fields.Char("Région", row="city"),
        'country': fields.Char("Pays", default="Togo", row="city"),
        'phone': fields.Char("Téléphone", row="contact"),
        'website': fields.Char("Site web", row="contact"),
        'latitude': fields.Float("Latitude", row="gps"),
        'longitude': fields.Float("Longitude", row="gps"),
    })
    organizer = fields.Group("Organisateur", tab="Dates & lieu", fields={
        'name': fields.Char("Nom", default="PALAIS DE LOMÉ", row="org"),
        'email': fields.Email("Email", row="org"),
        'phone': fields.Char("Téléphone", row="contact"),
        'website': fields.Char("Site web", row="contact"),
    })

    # -------------------------------------------------------------------- Médias
    cover_image = fields.Image("Image de couverture", tab="Médias", row="images")
    banner_image = fields.Image("Bannière", tab="Médias", row="images")
    cover = fields.Group("Affichage de la couverture", tab="Médias", fields={
        'opacity': fields.Float("Opacité du voile", default=0.4, min=0, max=1, help="De 0 à 1.", row="display"),
        'height': fields.Selection([('full', 'Plein écran'), ('half', 'Moitié d’écran'), ('third', 'Tiers d’écran'),
                                    ('auto', 'Automatique')], "Hauteur", default='half', row="display"),
        'text_align': fields.Selection([('left', 'Gauche'), ('center', 'Centre'), ('right', 'Droite')],
                                       "Alignement du texte", row="display"),
        'background_color': fields.Char("Couleur de fond", placeholder="#1a1a1a"),
    })
    gallery = fields.Array("Galerie (Aperçu de l’exposition)", singular="Image", tab="Médias", fields={
        'image': fields.Image("Image", required=True),
        'reference': fields.Char("Légende / référence", translate=True),
    })
    video_url = fields.Char("Vidéo (URL)", tab="Médias", placeholder="https://www.youtube.com/watch?v=...")

    # --------------------------------------------------------------- Billetterie
    seats_limited = fields.Boolean("Places limitées", tab="Billetterie", row="seats")
    seats_max = fields.Integer("Nombre de places", min=0, tab="Billetterie", row="seats",
                               condition={'field': 'seats_limited', 'equals': True})
    register_url = fields.Char("Lien d’inscription / réservation", tab="Billetterie", row="links")
    website_url = fields.Char("Site web de l’événement", tab="Billetterie", row="links")
    ticket_instructions = fields.RichTextEditor("Instructions billetterie", translate=True, tab="Billetterie")
    tickets = fields.Array("Billets / tarifs", singular="Billet", tab="Billetterie", row_label="name", fields={
        'name': fields.Char("Nom", required=True, translate=True, row="ticket", width="50%", placeholder="Plein tarif"),
        'price': fields.Float("Prix", min=0, row="ticket", width="25%"),
        'currency': fields.Selection(['XOF', 'EUR', 'USD'], "Devise", default='XOF', row="ticket", width="25%"),
        'description': fields.Text("Description", translate=True),
        'seats_max': fields.Integer("Places", min=0, row="sale"),
        'sale_start': fields.Date("Début des ventes", row="sale"),
        'sale_end': fields.Date("Fin des ventes", row="sale"),
    })

    # ----------------------------------------------------------------------- SEO
    seo = fields.Group("SEO", tab="SEO", fields={
        'title': fields.Char("Meta title", translate=True),
        'description': fields.Text("Meta description", translate=True),
        'keywords': fields.Char("Mots-clés", translate=True),
        'og_image': fields.Image("Image de partage (Open Graph)"),
    })

    # ------------------------------------------------------------ Barre latérale
    slug = fields.Slug("Slug", source='title', translate=True)
    event_type = fields.Selection(EVENT_TYPES, "Type", required=True, default='atelier', sidebar=True)
    stage = fields.Selection(STAGES, "Étape", default='upcoming', sidebar=True)
    website_visibility = fields.Selection([('public', 'Public'), ('link', 'Via le lien uniquement'),
                                           ('members', 'Membres connectés')], "Visibilité", default='public', sidebar=True)
    tags = fields.Selection(THEMES, "Thématiques", multiple=True, sidebar=True)
    parent_event = fields.Many2one('ateliers', "Programme parent", sidebar=True,
                                   help="Ex. l’exposition à laquelle cet atelier est rattaché.")
    related_exposition = fields.Many2one('ateliers', "Exposition liée", sidebar=True)
    workshops = fields.Many2many('ateliers', "Ateliers associés", sidebar=True)
    sequence = fields.Integer("Ordre d’affichage", default=10, sidebar=True)
    page_sections = fields.Group("Sections de la page", sidebar=True, fields={
        'introduction': fields.Boolean("Introduction"),
        'location': fields.Boolean("Lieu"),
        'register': fields.Boolean("Inscription", default=True),
        'community': fields.Boolean("Communauté"),
    })
    note = fields.Text("Note interne", sidebar=True, help="Non affichée sur le site.")
