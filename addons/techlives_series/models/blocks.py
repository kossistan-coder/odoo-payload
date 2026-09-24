# -*- coding: utf-8 -*-
"""Blocs de mise en page propres au site Tech Lives Series.

Ils s'ajoutent aux blocs natifs (Content, Media, Call to Action, Archive) du champ
``layout`` de la collection Pages : la page d'accueil est une page comme les
autres, composée librement de ces blocs dans l'admin.
"""
from datetime import date

from odoo.addons.payload_cms.payload import Block, Model, fields

MODES = [('auto', 'Automatique'), ('manual', 'Sélection manuelle')]


class LiveHero(Block):
    """Grand visuel du live mis en avant (haut de la page d'accueil)."""
    _name = 'live-hero'
    _label = 'Hero live'
    _inherit = 'pages.layout'
    _sequence = 10

    live = fields.Many2one('events', "Live mis en avant",
                           help="Vide : le prochain live (ou le dernier) est utilisé.")
    badge = fields.Char("Badge", translate=True, placeholder="Episode Spécial",
                        help="Vide : « Episode Spécial » si le live est marqué spécial.")
    image = fields.Image("Visuel", row="images", help="Vide : image hero du live.")
    mobile_image = fields.Image("Visuel mobile", row="images")
    cta_label = fields.Char("Bouton", default="Regarder l'épisode", translate=True, row="cta")
    cta_url = fields.Char("Lien du bouton", row="cta", help="Vide : lien du live.")
    scroll_hint = fields.Char("Invitation à défiler", default="scrollez pour en voir plus...", translate=True)

    @classmethod
    def _delivery_sources(cls, row, env):
        """Sans live choisi : le prochain live, sinon le dernier (API Delivery)."""
        if row.get('live'):
            return []
        upcoming = {'field': 'live', 'collection': 'events', 'limit': 1, 'order': 'date_sortie asc',
                    'domain': [('active', '=', True), ('date_sortie', '>=', date.today().isoformat())]}
        if Model(env, 'events').search(upcoming['domain'], limit=1):
            return [upcoming]
        return [{'field': 'live', 'collection': 'events', 'limit': 1, 'order': 'date_sortie desc',
                 'domain': [('active', '=', True)]}]


class About(Block):
    """Texte de présentation avec une image (« A propos des Tech Lives Series »)."""
    _name = 'about'
    _label = 'A propos'
    _inherit = 'pages.layout'
    _sequence = 20

    title = fields.Char("Titre", default="A propos des Tech Lives Series", translate=True)
    text = fields.RichTextEditor("Texte", translate=True)
    image = fields.Image("Image", row="media")
    image_position = fields.Selection([('left', 'À gauche'), ('right', 'À droite')], "Position de l'image",
                                      default='left', row="media")
    anchor = fields.Char("Ancre", default="about", role="config", help="Lien du menu : #about")


class EpisodesList(Block):
    """Derniers lives (« Episodes précédents »)."""
    _name = 'episodes-list'
    _label = 'Liste des épisodes'
    _inherit = 'pages.layout'
    _sequence = 30

    title = fields.Char("Titre", default="Episodes précédents", translate=True)
    subtitle = fields.Char("Sous-titre", translate=True,
                           default="Revivez les précédents épisodes des Tech Lives Series comme si vous y étiez")
    button_label = fields.Char("Bouton", default="Voir tous les épisodes", translate=True, row="button")
    button_url = fields.Char("Lien du bouton", row="button", placeholder="https://www.youtube.com/@...")
    mode = fields.Selection(MODES, "Lives affichés", default='auto', widget='radio', row="mode")
    limit = fields.Integer("Nombre", default=3, min=1, row="mode", condition={'field': 'mode', 'equals': 'auto'})
    events = fields.Many2many('events', "Lives", condition={'field': 'mode', 'equals': 'manual'})
    anchor = fields.Char("Ancre", default="episodes", role="config")

    @classmethod
    def _delivery_sources(cls, row, env):
        if row.get('mode') == 'manual':
            return []
        return [{'field': 'events', 'collection': 'events', 'domain': [('active', '=', True)],
                 'order': 'date_sortie desc', 'limit': int(row.get('limit') or 3)}]


class SpeakersCarousel(Block):
    """Carrousel des intervenants."""
    _name = 'speakers-carousel'
    _label = 'Carrousel des intervenants'
    _inherit = 'pages.layout'
    _sequence = 40

    title = fields.Char("Titre", default="Intervenants", translate=True)
    subtitle = fields.Char("Sous-titre", translate=True)
    mode = fields.Selection(MODES, "Intervenants affichés", default='auto', widget='radio',
                            help="Automatique : intervenants actifs non masqués (« Masquer sur la page d'accueil »).")
    speakers = fields.Many2many('speakers', "Intervenants", condition={'field': 'mode', 'equals': 'manual'})
    anchor = fields.Char("Ancre", default="speakers", role="config")

    @classmethod
    def _delivery_sources(cls, row, env):
        if row.get('mode') == 'manual':
            return []
        return [{'field': 'speakers', 'collection': 'speakers', 'order': 'nom',
                 'domain': [('active', '=', True), ('hidespeaker', '=', False)]}]


class OrganizersLogos(Block):
    """Logos des organisateurs et partenaires."""
    _name = 'organizers-logos'
    _label = 'Logos des organisateurs'
    _inherit = 'pages.layout'
    _sequence = 50

    title = fields.Char("Titre", default="Organisateurs", translate=True)
    subtitle = fields.Char("Sous-titre", translate=True)
    mode = fields.Selection(MODES, "Logos affichés", default='auto', widget='radio',
                            help="Automatique : organisateurs actifs, dans l'ordre d'affichage.")
    organizers = fields.Many2many('organizers', "Organisateurs", condition={'field': 'mode', 'equals': 'manual'})
    anchor = fields.Char("Ancre", default="organizers", role="config")

    @classmethod
    def _delivery_sources(cls, row, env):
        if row.get('mode') == 'manual':
            return []
        return [{'field': 'organizers', 'collection': 'organizers', 'domain': [('active', '=', True)], 'order': 'sequence'}]


class CommunityCta(Block):
    """Appel à rejoindre la communauté (groupe WhatsApp)."""
    _name = 'community-cta'
    _label = 'Rejoindre la communauté'
    _inherit = 'pages.layout'
    _sequence = 60

    title = fields.Char("Titre", default="REJOIGNEZ LA COMMUNAUTE", translate=True)
    text = fields.Text("Texte", translate=True,
                       default="Restez à l'affût de l'actualité du secteur de la technologie au Togo "
                               "en rejoignant notre groupe WhatsApp.")
    button_label = fields.Char("Bouton", default="Rejoindre maintenant", translate=True, row="button")
    button_url = fields.Char("Lien du groupe", row="button", placeholder="https://chat.whatsapp.com/...")
    image = fields.Image("Illustration")
