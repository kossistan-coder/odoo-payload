# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Seeder


class ServicesSeeder(Seeder):
    """Seeder pour les offres de services d'architecture et de mentorat."""
    _name = 'services'
    _description = "Services d'Architecture et Mentorat"
    _sequence = 30

    def run(self, env):
        services = [
            {
                'name': 'Mentorat 1-on-1',
                'slug': 'mentorat-1-on-1',
                'service_type': 'mentorat',
                'price_display': 'Engagement mensuel : 450€ / mois',
                'description': (
                    "<p>Accompagnement individuel sur-mesure pour les fondateurs, directeurs techniques "
                    "et développeurs seniors (Lead/Staff Engineer).</p>"
                    "<ul>"
                    "<li>45 minutes par semaine en visio dédiée</li>"
                    "<li>Revue de code / architecture asynchrone prioritaire</li>"
                    "<li>Accès Slack direct et continu</li>"
                    "<li>Plan de progression de carrière individualisé</li>"
                    "</ul>"
                ),
                'cta_label': 'Candidater',
                'cta_url': '/contact?service=mentorat',
                'sequence': 10,
                'is_active': True,
                'meta_title': 'Mentorat Technique 1-on-1 | Alexandre G.',
                'meta_description': 'Accompagnement individuel pour tech leads et développeurs exigeants.',
            },
            {
                'name': 'Audit Technique & Sécurité',
                'slug': 'audit-technique-securite',
                'service_type': 'audit',
                'price_display': 'Forfait complet : 1,800€ HT',
                'description': (
                    "<p>Diagnostic exhaustif de votre codebase NestJS / Payload CMS / Angular pour identifier "
                    "les goulots d'étranglement et sécuriser votre mise en production.</p>"
                    "<ul>"
                    "<li>Détection des goulots de performance & I/O</li>"
                    "<li>Cartographie des dettes techniques critiques</li>"
                    "<li>Recommandations d'architecture réductive</li>"
                    "<li>Restitution en direct à votre équipe tech</li>"
                    "</ul>"
                ),
                'cta_label': 'Commander',
                'cta_url': '/contact?service=audit',
                'sequence': 20,
                'is_active': True,
                'meta_title': 'Audit Technique & Sécurité Architecture Web',
                'meta_description': 'Audit de performance et revue d architecture logicielle sous 7 jours.',
            },
            {
                'name': 'Workshops & Formations B2B',
                'slug': 'workshops-formations-b2b',
                'service_type': 'formation_b2b',
                'price_display': 'Départ à : 1,200€ / jour',
                'description': (
                    "<p>Montée en compétences collective en immersion sur NestJS & Angular / architectures "
                    "complexes pour aligner vos équipes sur les standards de l'artisanat logiciel.</p>"
                    "<ul>"
                    "<li>Sessions pratiques de pair programming en direct</li>"
                    "<li>Stratégie de migration/architecture sans réécriture</li>"
                    "<li>Modèles de code/refactoring prêts pour vos PRs</li>"
                    "<li>Suivi post-formation pendant 30 jours</li>"
                    "</ul>"
                ),
                'cta_label': 'Devis OPCO',
                'cta_url': '/contact?service=b2b',
                'sequence': 30,
                'is_active': True,
                'meta_title': 'Workshops & Formations Entreprise B2B',
                'meta_description': 'Formations intra-entreprise sur-mesure finançables OPCO.',
            },
        ]

        for item in services:
            self.upsert(env, 'services', {'slug': {'equals': item['slug']}}, item)
