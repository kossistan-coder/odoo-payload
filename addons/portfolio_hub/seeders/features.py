# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Seeder


class FormationFeaturesSeeder(Seeder):
    """Seeder pour les avantages inclus dans les formations."""
    _name = 'formation_features'
    _description = "Caractéristiques et avantages inclus"
    _sequence = 20

    def run(self, env):
        features = [
            {
                'label': 'Dépôts GitHub Privés',
                'icon': 'lucide-github',
                'description': 'Commits précis étape par étape, branches dédiées par chapitre et configuration CI/CD GitHub Actions prête pour la prod.',
            },
            {
                'label': 'Salon Discord Privé',
                'icon': 'lucide-message-square',
                'description': 'Échangez directement avec Alexandre et une communauté sélective de seniors. Réponses garanties en moins de 4 heures aux blocages.',
            },
            {
                'label': 'Certificat Vérifiable',
                'icon': 'lucide-award',
                'description': 'Validation par revue de code de vos pull requests finales et certificat cryptographique partageable sur votre profil LinkedIn.',
            },
            {
                'label': 'Mises à Jour Majeures',
                'icon': 'lucide-refresh-cw',
                'description': "Accès garanti à l'ensemble des modules révisés à chaque nouvelle version de NestJS, Payload ou Angular. Zéro frais caché.",
            },
            {
                'label': 'Accès à Vie',
                'icon': 'lucide-infinity',
                'description': 'Consultez les vidéos HD/4K et les dépôts de code sans limite de temps.',
            },
        ]

        for item in features:
            self.upsert(env, 'formation-features', {'label': {'equals': item['label']}}, item)
