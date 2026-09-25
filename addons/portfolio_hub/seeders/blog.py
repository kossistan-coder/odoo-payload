# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Seeder


class BlogSeeder(Seeder):
    """Seeder pour les articles de blog, la veille technique, catégories et tags."""
    _name = 'blog'
    _description = "Blog et Veille Technologique"
    _sequence = 50

    def run(self, env):
        # 1. Catégories
        categories = [
            {'name': 'NestJS', 'slug': 'nestjs', 'description': 'Architecture backend, microservices et patterns Node.js.'},
            {'name': 'Payload CMS', 'slug': 'payload-cms', 'description': 'CMS Headless TypeScript, collections et intégration Next.js.'},
            {'name': 'Angular', 'slug': 'angular', 'description': 'Frontend réactif, Signals, zoneless et performances web.'},
            {'name': 'Architecture & Cloud', 'slug': 'architecture-cloud', 'description': 'Clean Architecture, DDD, Docker et patterns distribués.'},
            {'name': 'Benchmarks', 'slug': 'benchmarks', 'description': 'Tests de charge k6, mesures de latence et analyses comparatives.'},
        ]
        for cat in categories:
            self.upsert(env, 'categories', {'slug': {'equals': cat['slug']}}, cat)

        # 2. Tags
        tags = [
            {'name': 'Signals', 'slug': 'signals'},
            {'name': 'Validé Prod', 'slug': 'valide-prod'},
            {'name': 'Next App', 'slug': 'next-app'},
            {'name': 'Deep Dive', 'slug': 'deep-dive'},
            {'name': 'Performance', 'slug': 'performance'},
            {'name': 'Security', 'slug': 'security'},
            {'name': 'Microservices', 'slug': 'microservices'},
        ]
        for tag in tags:
            self.upsert(env, 'tags', {'slug': {'equals': tag['slug']}}, tag)

        # Récupération des helpers d'IDs
        def get_cat_id(slug):
            d = self.find(env, 'categories', {'slug': {'equals': slug}})
            return d.id if d else None

        def get_tag_id(slug):
            d = self.find(env, 'tags', {'slug': {'equals': slug}})
            return d.id if d else None

        def get_stack_id(slug):
            d = self.find(env, 'tech-stacks', {'slug': {'equals': slug}})
            return d.id if d else None

        cat_nestjs = get_cat_id('nestjs')
        cat_payload = get_cat_id('payload-cms')
        cat_angular = get_cat_id('angular')
        cat_bench = get_cat_id('benchmarks')

        tag_signals = get_tag_id('signals')
        tag_prod = get_tag_id('valide-prod')
        tag_next = get_tag_id('next-app')
        tag_perf = get_tag_id('performance')

        stack_nestjs = get_stack_id('nestjs')
        stack_payload = get_stack_id('payload-cms')
        stack_angular = get_stack_id('angular')

        # 3. Articles (Veille & Insights Tech)
        posts = [
            # Article à la une (Deep Dive)
            {
                'title': 'Payload CMS 3.0 + NestJS : Comment découpler votre CMS tout en partageant vos modèles TypeScript',
                'slug': 'payload-cms-3-nestjs-decoupler-partager-modeles-typescript',
                'excerpt': (
                    "Pourquoi choisir entre l'agilité d'un CMS headless et la rigueur de microservices orientés domaine ? "
                    "Grâce à un monorepo Nx et l'architecture Next-gen de Payload 3.0, découvrez comment synchroniser "
                    "les interfaces DTO et les collections sans redondance cognitive."
                ),
                'content': (
                    "<h2>Le défi du typage unifié dans une architecture découplée</h2>"
                    "<p>Dans un écosystème d'entreprise moderne, maintenir des contrats d'interface distincts entre "
                    "le backend métier (NestJS) et le CMS headless (Payload 3.0) mène inévitablement à une dérive des schémas.</p>"
                    "<p>En exploitant un monorepo basé sur Nx et la génération de types native de Payload 3.0, "
                    "nous pouvons instancier un paquet <code>@contracts</code> partagé qui garantit une compilation sans faille.</p>"
                ),
                'category': cat_payload,
                'tags': [i for i in [get_tag_id('deep-dive'), tag_next] if i],
                'stack_tags': [i for i in [stack_payload, stack_nestjs] if i],
                'is_veille': False,
                'published_date': '2025-03-21 09:00:00',
                'reading_time': 6,
                'author': 'Alexandre G.',
                'meta_title': 'Payload CMS 3.0 + NestJS : Architecture & Contrats TypeScript',
                'meta_description': 'Synchronisez vos modèles DTO et collections sans redondance cognitive.',
            },
            # Article 1
            {
                'title': 'Angular 19 Signals vs RxJS dans des applications d\'entreprise : Le guide pragmatique',
                'slug': 'angular-19-signals-vs-rxjs-applications-entreprise',
                'excerpt': (
                    "Faut-il bannir les Observables ou cohabiter intelligemment ? Analyse fine des gains de performance "
                    "de rendu sans Zone.js et matrice d'arbitrage pour les équipes de dev."
                ),
                'content': (
                    "<p>L'arrivée des Signals dans Angular transforme radicalement la détection de changements. "
                    "Sur notre benchmark de tests, le temps de réconciliation Zone-less affiche un gain mesuré de "
                    "<strong>-44% de cycles CPU</strong>.</p>"
                ),
                'category': cat_angular,
                'tags': [i for i in [tag_signals, tag_perf] if i],
                'stack_tags': [i for i in [stack_angular] if i],
                'is_veille': False,
                'published_date': '2025-03-18 10:30:00',
                'reading_time': 6,
                'author': 'Alexandre G.',
                'meta_title': 'Angular 19 Signals vs RxJS en Production',
                'meta_description': 'Guide pragmatique de migration vers les Signals et le Zoneless.',
            },
            # Article 2
            {
                'title': 'Sécuriser vos microservices NestJS avec Passport & JWT rotation sans état',
                'slug': 'securiser-microservices-nestjs-passport-jwt-rotation-sans-etat',
                'excerpt': (
                    "Implémentation de guards distribués, révocation cryptographique via Redis cluster et gestion "
                    "des refresh tokens avec zéro round-trip vers la base de données principale."
                ),
                'content': (
                    "<p>Le modèle Stateless Auth Pattern (RFC 9068) permet de valider cryptographiquement les tokens "
                    "au niveau des reverse-proxies et des guards NestJS sans interroger la base relationnelle PostgreSQL.</p>"
                ),
                'category': cat_nestjs,
                'tags': [i for i in [tag_prod, get_tag_id('security')] if i],
                'stack_tags': [i for i in [stack_nestjs] if i],
                'is_veille': False,
                'published_date': '2025-03-12 14:00:00',
                'reading_time': 11,
                'author': 'Alexandre G.',
                'meta_title': 'Sécurité Microservices NestJS & JWT Stateless',
                'meta_description': 'Architecture d authentification distribuée avec Redis et NestJS.',
            },
            # Article 3
            {
                'title': 'Migrer de Strapi vers Payload CMS : Bénéfices réels après 6 mois en production',
                'slug': 'migrer-strapi-vers-payload-cms-benefices-reels',
                'excerpt': (
                    "Retour d'expérience chiffré sur une plateforme média recevant 4.2M de requêtes/mois. "
                    "Disparition du boilerplate ORM, compilation native Next.js et typage strict."
                ),
                'content': (
                    "<p>Après 6 mois en production, la consommation mémoire par Pod Kubernetes est passée de "
                    "<strong>410 MB</strong> (Strapi) à seulement <strong>155 MB</strong> (Payload CMS 3.0).</p>"
                ),
                'category': cat_payload,
                'tags': [i for i in [tag_next, tag_perf] if i],
                'stack_tags': [i for i in [stack_payload] if i],
                'is_veille': False,
                'published_date': '2025-03-06 08:00:00',
                'reading_time': 5,
                'author': 'Alexandre G.',
                'meta_title': 'Migration Strapi vers Payload CMS : Bilan de Production',
                'meta_description': 'Retour d expérience chiffré sur 4.2M de requêtes mensuelles.',
            },
            # Article 4 (Veille rapide / Benchmark)
            {
                'title': 'Benchmark : GraphQL vs REST vs tRPC dans un écosystème NestJS',
                'slug': 'benchmark-graphql-vs-rest-vs-trpc-nestjs',
                'excerpt': (
                    "Stress tests conduits avec k6 jusqu'à 25 000 req/sec. Débit utile, saturation CPU du thread "
                    "Event Loop, et overhead des sérialiseurs JSON sous charge extrême."
                ),
                'content': (
                    "<p>Résultat du test de débit max sans throttling : tRPC surpasse GraphQL de +28% avec "
                    "un palier mesuré à <strong>22.8k RPS</strong> sous conteneur standard 2 vCPU.</p>"
                ),
                'category': cat_bench,
                'tags': [i for i in [tag_perf, get_tag_id('microservices')] if i],
                'stack_tags': [i for i in [stack_nestjs] if i],
                'is_veille': True,
                'published_date': '2025-02-24 16:45:00',
                'reading_time': 9,
                'author': 'Alexandre G.',
                'meta_title': 'Benchmark k6 : GraphQL vs REST vs tRPC',
                'meta_description': 'Comparatif de performances sous charge extrême sur Node.js et NestJS.',
            },
        ]

        for item in posts:
            self.upsert(env, 'posts', {'slug': {'equals': item['slug']}}, item)
