# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Collection, expose, fields

TIME_PATTERN = r"\d{2}:\d{2}"


class Event(Collection):
    """Lives (épisodes diffusés) : affiche, date, horaires, intervenants, modérateurs."""
    _name = 'events'
    _sequence = 110
    _label = 'Live'
    _label_plural = 'Lives'
    _rec_name = 'designation'
    _order = '-date_sortie'
    _columns = ['designation', 'date_sortie', 'time', 'episode', 'active', '_status']
    _search = ['designation']
    _drafts = True

    # ------------------------------------------------------------------ Contenu
    designation = fields.Char("Désignation", api_name="title", required=True, translate=True, tab="Contenu",
                              placeholder="Autour de l'IA")
    description = fields.RichTextEditor("Description", translate=True, tab="Contenu")
    date_sortie = fields.Date("Date de sortie", api_name="releaseDate", required=True, tab="Contenu", row="when")
    time = fields.Char("Heure de début", api_name="startTime", required=True, tab="Contenu", row="when", placeholder="11:00",
                       pattern=TIME_PATTERN, pattern_message="L'heure doit être au format HH:mm (ex. 11:00).")
    time_end = fields.Char("Heure de fin", api_name="endTime", tab="Contenu", row="when", placeholder="13:30",
                           pattern=TIME_PATTERN, pattern_message="L'heure doit être au format HH:mm (ex. 13:30).")
    broadcast = fields.Selection([('zoom', 'Zoom'), ('youtube', 'YouTube'), ('facebook', 'Facebook'),
                                  ('linkedin', 'LinkedIn'), ('onsite', 'Présentiel')],
                                 "Diffusion via", multiple=True, tab="Contenu")
    live_url = fields.Char("Lien du live (« Regarder l'épisode »)", tab="Contenu", placeholder="https://")

    # -------------------------------------------------------------------- Médias
    couverture = fields.Image("Couverture", api_name="cover", required=True, tab="Visuels",
                              help="Affiche du live (liste des épisodes).")
    hero_image = fields.Image("Image hero", tab="Visuels", row="hero", help="Grand visuel de la page d'accueil.")
    mobile_image = fields.Image("Image mobile", tab="Visuels", row="hero")

    # --------------------------------------------------------------- Personnes
    speakers = fields.Many2many('speakers', "Intervenants", tab="Intervenants")
    moderators = fields.Many2many('speakers', "Modérateurs", tab="Intervenants")
    roles = fields.Array("Autres rôles", singular="Rôle", tab="Intervenants", collapsed=True,
                         help="Animateur, invité d'honneur... (rôles définis dans « Rôles événement »).",
                         fields={
                             'speaker': fields.Many2one('speakers', "Personne", required=True, row="role"),
                             'role': fields.Many2one('event-roles', "Rôle", required=True, row="role"),
                         })
    participants = fields.Many2many('participants', "Participants", tab="Intervenants")
    organizers = fields.Many2many('organizers', "Organisateurs", tab="Intervenants")

    # ------------------------------------------------------------ Barre latérale
    slug = fields.Slug(source='designation')
    episode = fields.Many2one('episodes', "Épisode (replay)", sidebar=True)
    is_special = fields.Boolean("Épisode spécial", sidebar=True)
    active = fields.Boolean("Actif", default=True, sidebar=True, badge=("Actif", "Inactif"))

    # ------------------------------------------------------------------ API
    # Méthodes appelables en Python (Model(env, 'events').a_venir()) et en
    # JSON-RPC (POST /payload/dataset/call_kw, "model": "events", "method": "a_venir").
    CARD = {
        'designation': {}, 'slug': {}, 'date_sortie': {}, 'time': {}, 'time_end': {}, 'couverture': {},
        'is_special': {}, 'live_url': {},
        'speakers': {'fields': {'nom': {}, 'prenom': {}, 'function': {}, 'profile': {}}},
        'episode': {'fields': {'link': {}}},
    }

    @expose(auth='public', tags=['Lives'], model='events', fields=CARD, many=True)
    def a_venir(self, limit=3):
        """Prochains lives actifs, du plus proche au plus lointain."""
        from datetime import date
        return self.web_search_read([('active', '=', True), ('date_sortie', '>=', date.today().isoformat())],
                                    Event.CARD, order='date_sortie asc', limit=limit)['records']

    @expose(auth='public', tags=['Lives'], model='events', fields=CARD, many=True)
    def replays(self, limit=None):
        """Lives passés qui ont un replay, du plus récent au plus ancien."""
        return self.web_search_read([('active', '=', True), ('episode', '!=', False)],
                                    Event.CARD, order='date_sortie desc', limit=limit)['records']
