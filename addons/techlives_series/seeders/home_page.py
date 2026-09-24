# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Seeder

from ..models.blocks import About, CommunityCta, EpisodesList, LiveHero, OrganizersLogos, SpeakersCarousel

ABOUT_TEXT = (
    "<p>Les Tech Lives Series visent à rassembler des professionnels, des apprenants de divers horizons "
    "ainsi que monsieur tout le monde pour discuter des tendances actuelles, des défis et des avancées en "
    "matière de technologie. Chaque session abordera des thématiques spécifiques, avec des interventions de "
    "professionnels et de praticiens qui partageront leurs connaissances et leurs expériences pratiques.</p>"
)


def layout():
    """Blocs de la page d'accueil, remplis avec leurs valeurs par défaut."""
    return [
        LiveHero.row(),
        About.row(text=ABOUT_TEXT),
        EpisodesList.row(),
        SpeakersCarousel.row(),
        OrganizersLogos.row(),
        CommunityCta.row(),
    ]


class HomePage(Seeder):
    """Page « Accueil » (slug home) de la collection Pages.

    - pas de page home : elle est créée avec les blocs du module ;
    - une page home existe : les blocs du module qui lui manquent sont ajoutés à la
      suite de son layout (les blocs existants ne sont ni modifiés ni supprimés).
    """
    _name = 'home_page'
    _description = "Page d'accueil"

    def run(self, env):
        page = self.find(env, 'pages', {'slug': {'equals': 'home'}})
        if page:
            self.add_blocks(page, 'layout', layout())
            return
        self.create(env, 'pages', {
            'title': 'Accueil',
            'slug': 'home',
            'layout': layout(),
            'meta': {'title': 'Tech Lives Series'},
        })
