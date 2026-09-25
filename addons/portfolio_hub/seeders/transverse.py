# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Seeder


class TransverseSeeder(Seeder):
    """Seeder pour les statistiques homepage, abonnés newsletter et projets du portfolio."""
    _name = 'transverse'
    _description = "Stats Homepage, Projets et Transverse"
    _sequence = 60

    def run(self, env):
        # 1. Chiffres clés / Stats Hero
        stats = [
            {'value': '12,000+', 'label': 'Développeurs formés', 'sequence': 10, 'active': True},
            {'value': '99.4%', 'label': 'Satisfaction apprenants', 'sequence': 20, 'active': True},
            {'value': '15+', 'label': 'Projets d\'envergure en prod', 'sequence': 30, 'active': True},
            {'value': '8 ans', 'label': 'D\'expérience Tech Lead', 'sequence': 40, 'active': True},
        ]
        for item in stats:
            self.upsert(env, 'homepage-stats', {'label': {'equals': item['label']}}, item)

        # 2. Projets du portfolio
        def get_stack_id(slug):
            d = self.find(env, 'tech-stacks', {'slug': {'equals': slug}})
            return d.id if d else None

        projects = [
            {
                'title': 'Portail SaaS Multi-tenant 100% Typé',
                'slug': 'portail-saas-multi-tenant',
                'description': (
                    "<p>Architecture multi-tenant avec isolation logique par schéma et synchronisation "
                    "des rôles d'utilisateurs RBAC via Payload CMS 3.0 et Next.js App Router.</p>"
                ),
                'stack_tags': [i for i in [get_stack_id('payload-cms'), get_stack_id('typescript'), get_stack_id('postgresql')] if i],
                'project_url': 'https://saas-demo.architect-lab.com',
                'github_url': 'https://github.com/alexandre/saas-multi-tenant-template',
                'date_realisation': '2025-01-15',
                'status': 'featured',
                'meta_title': 'Étude de cas : Portail SaaS Multi-tenant',
                'meta_description': 'Conception d un SaaS scalable avec Payload CMS 3.0.',
            },
            {
                'title': 'Plateforme d\'Enchères Temps Réel CQRS',
                'slug': 'plateforme-encheres-temps-reel-cqrs',
                'description': (
                    "<p>Backend distribué NestJS capable d'encaisser 25 000 enchères simultanées par seconde. "
                    "Architecture événementielle RabbitMQ, Event Sourcing et synchronisation Redis PubSub.</p>"
                ),
                'stack_tags': [i for i in [get_stack_id('nestjs'), get_stack_id('rabbitmq-redis'), get_stack_id('docker-k8s')] if i],
                'project_url': 'https://auction-cqrs.architect-lab.com',
                'github_url': 'https://github.com/alexandre/nestjs-cqrs-auction-engine',
                'date_realisation': '2024-11-20',
                'status': 'featured',
                'meta_title': 'Étude de cas : Plateforme d Enchères Temps Réel CQRS',
                'meta_description': 'Système haute performance à base de NestJS et RabbitMQ.',
            },
            {
                'title': 'Dashboard Analytique Ultra-Réactif Zoneless',
                'slug': 'dashboard-analytique-zoneless',
                'description': (
                    "<p>Application web d'analyse de données financières sous Angular 18+ Zoneless. "
                    "Affichage en temps réel de flux de données sans aucun lag d'interface grâce aux Signals.</p>"
                ),
                'stack_tags': [i for i in [get_stack_id('angular'), get_stack_id('typescript'), get_stack_id('tailwind-css')] if i],
                'project_url': 'https://analytics.architect-lab.com',
                'github_url': 'https://github.com/alexandre/angular-zoneless-dashboard',
                'date_realisation': '2025-02-10',
                'status': 'published',
                'meta_title': 'Étude de cas : Dashboard Analytique Angular Zoneless',
                'meta_description': 'Interface ultra-rapide basée sur les Signals et SignalStore.',
            },
        ]
        for proj in projects:
            self.upsert(env, 'projects', {'slug': {'equals': proj['slug']}}, proj)

        # 3. Premier abonné Newsletter de démonstration
        subscriber = {
            'email': 'lead.dev@societe.com',
            'subscribed_date': '2025-03-01 10:00:00',
            'source': 'homepage',
            'active': True,
        }
        self.upsert(env, 'newsletter-subscribers', {'email': {'equals': subscriber['email']}}, subscriber)
