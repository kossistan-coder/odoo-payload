# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Seeder


class FormationsSeeder(Seeder):
    """Seeder pour les formations complètes et le catalogue à l'unité."""
    _name = 'formations'
    _description = "Formations et Catalogue de cours"
    _sequence = 40

    def run(self, env):
        # Récupération des IDs des technos créées par tech_stacks
        def get_stack_id(slug):
            doc = self.find(env, 'tech-stacks', {'slug': {'equals': slug}})
            return doc.id if doc else None

        # Récupération des IDs des caractéristiques
        features_docs = env['cms.document'].sudo().search([('collection_id.slug', '=', 'formation-features')])
        feature_ids = [f.id for f in features_docs]

        nestjs_id = get_stack_id('nestjs')
        payload_id = get_stack_id('payload-cms')
        angular_id = get_stack_id('angular')
        ts_id = get_stack_id('typescript')
        docker_id = get_stack_id('docker-k8s')

        formations = [
            # 1. Le grand Track Recommandé (Hero)
            {
                'name': 'Fullstack Modern Stack : NestJS + Payload CMS 3.0 + Angular',
                'slug': 'fullstack-modern-stack-nestjs-payload-angular',
                'subtitle': 'La roadmap complète de zéro jusqu\'aux microservices distribués et frontends zoneless ultra-performants.',
                'description': (
                    "<p><strong>38 heures d'apprentissage chirurgical.</strong> Oubliez les tutos superficiels : "
                    "concevez, codez et déployez 4 projets de production avec architecture événementielle, "
                    "signals réactifs et back-office headless scalable.</p>"
                ),
                'level': 'advanced',
                'duration_hours': 38,
                'is_featured': True,
                'active': True,
                'stack_tags': [i for i in [nestjs_id, payload_id, angular_id, ts_id, docker_id] if i],
                'features': feature_ids,
                'modules': [
                    {
                        'title': '01. NestJS Core & Patterns',
                        'duration': '7h 40m',
                        'description': 'Inversion de contrôle avancée, validateurs DTO typés, transactions Prisma ORM & architecture en couches d\'entreprise.',
                    },
                    {
                        'title': '02. Payload CMS 3.0 Deep Architecture',
                        'duration': '10h 15m',
                        'description': 'Intégration Next.js Server Components, collections modulaires, lifecycles hooks synchronisés et gestion fine du RBAC.',
                    },
                    {
                        'title': '03. Angular 18 Zoneless & Signals Mastery',
                        'duration': '11h 25m',
                        'description': 'Paradigme Signal-first sans zone.js, routing différé (deferral), standalone components et Tailwind CSS v4.',
                    },
                    {
                        'title': '04. Déploiement CI/CD & Infrastructure',
                        'duration': '8h 40m',
                        'description': 'Conteneurisation multi-étapes, cluster Redis distribué, terminaison SSL/TLS automatique et pipeline GitHub Actions.',
                    },
                ],
                'meta_title': 'Formation Fullstack NestJS, Payload CMS 3.0 & Angular 18',
                'meta_description': 'Devenez ingénieur fullstack d élite sur l écosystème TypeScript moderne.',
            },
            # 2. Formations Spécialisées à l'unité
            {
                'name': 'NestJS Architecture & Microservices',
                'slug': 'nestjs-architecture-microservices',
                'subtitle': 'Dominez la complexité d\'un backend distribué : patterns CQRS, queues de messages asynchrones et résilience.',
                'description': (
                    "<p>Apprenez à structurer des applications NestJS modulaires prêtes pour l'échelle d'entreprise. "
                    "Inclus un projet complet de <em>Plateforme d'enchères temps réel</em>.</p>"
                ),
                'level': 'intermediate',
                'duration_hours': 14,
                'is_featured': False,
                'active': True,
                'stack_tags': [i for i in [nestjs_id, ts_id] if i],
                'features': feature_ids[:3],
                'modules': [
                    {'title': 'Architecture Hexagonale & Inversion de dépendances', 'duration': '3h 30m', 'description': 'Découpler la logique métier du framework.'},
                    {'title': 'Microservices & Queues RabbitMQ', 'duration': '5h 15m', 'description': 'Communication asynchrone et résilience face aux pannes.'},
                    {'title': 'CQRS & Event Sourcing', 'duration': '3h 15m', 'description': 'Séparer lectures et écritures pour maximiser le débit.'},
                    {'title': 'Tests E2E & Conteneurisation', 'duration': '2h 00m', 'description': 'Tests d intégration automatisés sous Jest et Docker.'},
                ],
                'meta_title': 'Formation NestJS Architecture & Microservices',
                'meta_description': 'Maîtrisez les microservices et le Clean Architecture en NestJS.',
            },
            {
                'name': 'Payload CMS 3.0 : De l\'Installation au Headless',
                'slug': 'payload-cms-3-installation-au-headless',
                'subtitle': 'Créez un CMS headless ultra-véloce avec la dernière version native Next.js et extensions personnalisées.',
                'description': (
                    "<p>Découvrez la puissance du CMS headless 100% TypeScript. "
                    "Inclus un projet de <em>Portail SaaS multi-tenant 100% typé</em>.</p>"
                ),
                'level': 'beginner',
                'duration_hours': 10,
                'is_featured': False,
                'active': True,
                'stack_tags': [i for i in [payload_id, ts_id] if i],
                'features': feature_ids[:3],
                'modules': [
                    {'title': 'Prise en main et installation dans Next.js App Router', 'duration': '2h 30m', 'description': 'Configuration du payload.config.ts et initialisation.'},
                    {'title': 'Collections, Globals et Blocs complexes', 'duration': '3h 45m', 'description': 'Concevoir un schéma de contenu modulaire et maintenable.'},
                    {'title': 'Hooks, RBAC et Sécurité', 'duration': '2h 15m', 'description': 'Contrôle d accès granulaire et automatisation des workflows.'},
                    {'title': 'API REST, GraphQL et Delivery Frontend', 'duration': '1h 30m', 'description': 'Consommer le contenu dans n importe quel client web ou mobile.'},
                ],
                'meta_title': 'Formation Payload CMS 3.0 Headless',
                'meta_description': 'Apprenez à maîtriser Payload CMS 3.0 avec Next.js et TypeScript.',
            },
            {
                'name': 'Angular 18+ Moderne & Patterns',
                'slug': 'angular-18-moderne-patterns',
                'subtitle': 'Repensez votre façon de construire des applications Web avec Signals primitifs, Zoneless et SignalStore.',
                'description': (
                    "<p>L'ère moderne d'Angular : adieu zone.js, bienvenue aux performances brutes. "
                    "Inclus un projet de <em>Dashboard analytique ultra-réactif</em>.</p>"
                ),
                'level': 'intermediate',
                'duration_hours': 12,
                'is_featured': False,
                'active': True,
                'stack_tags': [i for i in [angular_id, ts_id] if i],
                'features': feature_ids[:3],
                'modules': [
                    {'title': 'Signals Primitifs & Computed', 'duration': '3h 00m', 'description': 'La réactivité granulaire au cœur des composants.'},
                    {'title': 'Architecture Zoneless & SSR', 'duration': '3h 30m', 'description': 'Performances web maximales sans overhead.'},
                    {'title': 'Gestion d État avec NGRX SignalStore', 'duration': '3h 30m', 'description': 'Organiser l état métier sans boilerplate.'},
                    {'title': 'Optimisations & Defer Loading', 'duration': '2h 00m', 'description': 'Chargement à la demande ultra-fluide.'},
                ],
                'meta_title': 'Formation Angular 18+ Moderne & Zoneless',
                'meta_description': 'Apprenez Angular 18 avec Signals et Zoneless change detection.',
            },
        ]

        for item in formations:
            self.upsert(env, 'formations', {'slug': {'equals': item['slug']}}, item)
