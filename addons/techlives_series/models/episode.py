# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Collection, fields


class Episode(Collection):
    """Replays : lien de la vidéo d'un live."""
    _name = 'episodes'
    _sequence = 120
    _label = 'Épisode'
    _label_plural = 'Épisodes'
    _rec_name = 'link'
    _order = '-createdAt'
    _columns = ['event', 'link', 'createdAt']

    event = fields.Many2one('events', "Live", required=True)
    link = fields.Char("Lien de la vidéo", required=True, placeholder="https://www.youtube.com/watch?v=...",
                       pattern=r"https?://\S+", pattern_message="Veuillez saisir un lien valide (https://...).")
