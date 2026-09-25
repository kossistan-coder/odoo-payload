# -*- coding: utf-8 -*-
# pyrefly: ignore [missing-import]
from odoo.addons.payload_cms.payload import Seeder


class PagesSeeder(Seeder):
    """Seeder pour les trois pages principales de l'interface (Accueil, Formations, Veille).

    Alimente la collection native 'pages' de payload_cms.
    """
    _name = 'pages'
    _description = "Pages principales (Accueil, Formations, Veille & Insights)"
    _sequence = 70

    def run(self, env):
        pages = [
            # 1. Page d'accueil (Hero, Trinité technologique, Services, Pack formation, Veille)
            {
                'title': {'fr': 'Accueil', 'en': 'Home'},
                'slug': 'home',
                'publishedAt': '2025-01-01',
                'layout': [
                    {
                        'blockType': 'content',
                        'richText': {
                            'fr': (
                                "<div class=\"hero-badge\">CONSEILS POUR BOOSTER L'ÉQUIPE ARCHITECTURE</div>"
                                "<h1>Architecte Fullstack NestJS, Payload 3.0 &amp; Angular 18.</h1>"
                                "<p class=\"lead\">Tech Lead en journée, runneur de formations d'ingénierie logicielle "
                                "avancée et mentor pour développeurs exigeants. Découplez vos architectures et repoussez "
                                "les limites du Web moderne grâce aux designs résilients.</p>"
                            ),
                            'en': (
                                "<div class=\"hero-badge\">TIPS FOR BOOSTING THE ARCHITECTURE TEAM</div>"
                                "<h1>Fullstack Architect NestJS, Payload 3.0 &amp; Angular 18.</h1>"
                                "<p class=\"lead\">Tech Lead by day, instructor of advanced software engineering courses, "
                                "and mentor to ambitious developers. Decouple your architectures and push the boundaries "
                                "of the modern web with resilient designs.</p>"
                            ),
                        },
                    },
                    {
                        'blockType': 'content',
                        'richText': {
                            'fr': (
                                "<h2>Une trinité technologique taillée pour l'échelle</h2>"
                                "<p>Inversion de contrôle poussée, modules hexagonaux, typage strict de bout en bout "
                                "et réactivité zoneless sans compromis.</p>"
                            ),
                            'en': (
                                "<h2>A technology trinity built for scale</h2>"
                                "<p>Advanced inversion of control, hexagonal modules, strict end-to-end typing, "
                                "and uncompromising zoneless reactivity.</p>"
                            ),
                        },
                    },
                    {
                        'blockType': 'cta',
                        'richText': {
                            'fr': (
                                "<p><strong>La Veille du Dimanche — 100% ingénierie, 0 spam.</strong> "
                                "Rejoignez plus de 6 400 développeurs et recevez chaque dimanche notre décryptage d'architecture logicielle.</p>"
                            ),
                            'en': (
                                "<p><strong>Sunday Tech Watch — 100% engineering, 0 spam.</strong> "
                                "Join over 6,400 developers and receive our software architecture breakdown every Sunday.</p>"
                            ),
                        },
                        'links': [
                            {'label': {'fr': 'Explorer les formations', 'en': 'Explore courses'}, 'url': '/formations', 'newTab': False},
                            {'label': {'fr': "Réserver un Audit d'Architecture", 'en': 'Book an Architecture Audit'}, 'url': '/services#audit', 'newTab': False},
                        ],
                    },
                ],
                'meta': {
                    'title': {
                        'fr': 'Alexandre G. // Architecte Fullstack NestJS, Payload 3.0 & Angular 18',
                        'en': 'Alexandre G. // Fullstack Architect NestJS, Payload 3.0 & Angular 18',
                    },
                    'description': {
                        'fr': "Formations d'ingénierie logicielle avancée, mentorat privé et audits d'architecture web moderne.",
                        'en': 'Advanced software engineering courses, 1-on-1 mentorship and modern web architecture audits.',
                    },
                },
            },
            # 2. Page Formations & Parcours Guidés
            {
                'title': {'fr': 'Formations & Parcours Guidés', 'en': 'Guided Courses & Paths'},
                'slug': 'formations',
                'publishedAt': '2025-01-01',
                'layout': [
                    {
                        'blockType': 'content',
                        'richText': {
                            'fr': (
                                "<div class=\"curriculum-badge\">CURRICULUM ARCHITECTURE 2025</div>"
                                "<h1>Formations &amp; Parcours Guidés</h1>"
                                "<p class=\"lead\">Des programmes pragmatiques, axés sur des architectures réelles sans superflu "
                                "pour devenir un ingénieur fullstack d'élite.</p>"
                                "<div class=\"metrics-bar\">"
                                "<span>100% CODE RÉEL</span> &bull; <span>38+ H SYLLABUS 2025</span> &bull; <span>4.96/5 ARCHITECT SCORE</span>"
                                "</div>"
                            ),
                            'en': (
                                "<div class=\"curriculum-badge\">2025 ARCHITECTURE CURRICULUM</div>"
                                "<h1>Guided Courses &amp; Learning Paths</h1>"
                                "<p class=\"lead\">Pragmatic programs focused on production-grade architectures without fluff "
                                "to become an elite fullstack engineer.</p>"
                                "<div class=\"metrics-bar\">"
                                "<span>100% REAL CODE</span> &bull; <span>38+ H 2025 SYLLABUS</span> &bull; <span>4.96/5 ARCHITECT SCORE</span>"
                                "</div>"
                            ),
                        },
                    },
                    {
                        'blockType': 'cta',
                        'richText': {
                            'fr': (
                                "<p><strong>Besoin d'un financement entreprise (OPCO / Entreprise) ?</strong> "
                                "Les programmes sont finançables sous convention de formation professionnelle en France et en Europe.</p>"
                            ),
                            'en': (
                                "<p><strong>Need corporate funding (OPCO / Company sponsorship)?</strong> "
                                "Programs are eligible for professional training funding in France and throughout Europe.</p>"
                            ),
                        },
                        'links': [
                            {'label': {'fr': 'Demander une convention', 'en': 'Request an agreement'}, 'url': '/contact?type=opco', 'newTab': False},
                        ],
                    },
                ],
                'meta': {
                    'title': {
                        'fr': 'Formations & Parcours Guidés | Architecte Fullstack',
                        'en': 'Guided Courses & Paths | Fullstack Architect',
                    },
                    'description': {
                        'fr': 'Roadmap complète de zéro jusqu aux microservices distribués et frontends zoneless ultra-performants.',
                        'en': 'Complete roadmap from zero to distributed microservices and ultra-fast zoneless frontends.',
                    },
                },
            },
            # 3. Page Veille & Insights Tech
            {
                'title': {'fr': 'Veille & Insights Tech', 'en': 'Tech Insights & Radar'},
                'slug': 'veille-insights',
                'publishedAt': '2025-01-01',
                'layout': [
                    {
                        'blockType': 'content',
                        'richText': {
                            'fr': (
                                "<div class=\"radar-badge\">RADAR // FLUX ACTIF : ÉDITION #42</div>"
                                "<h1>Veille &amp; Insights Tech</h1>"
                                "<p class=\"lead\">Analyses approfondies, retours d'expérience et benchmarks de production "
                                "sur l'écosystème NestJS, Payload CMS 3.0 et Angular.</p>"
                                "<div class=\"metrics-bar\">"
                                "<span>148 ARTICLES INDEXÉS</span> &bull; <span>390+ CODE SNIPPETS</span> &bull; <span>LIVE REPO</span>"
                                "</div>"
                            ),
                            'en': (
                                "<div class=\"radar-badge\">RADAR // ACTIVE FEED : EDITION #42</div>"
                                "<h1>Tech Insights &amp; Radar</h1>"
                                "<p class=\"lead\">In-depth analyses, field feedback and production benchmarks "
                                "across NestJS, Payload CMS 3.0 and Angular ecosystems.</p>"
                                "<div class=\"metrics-bar\">"
                                "<span>148 INDEXED ARTICLES</span> &bull; <span>390+ CODE SNIPPETS</span> &bull; <span>LIVE REPO</span>"
                                "</div>"
                            ),
                        },
                    },
                    {
                        'blockType': 'cta',
                        'richText': {
                            'fr': (
                                "<p><em>« Dupliquer un type vaut mieux que créer une dépendance logicielle prématurée. "
                                "Le découpage commence au niveau du contrat d'interface. »</em> — Alexandre G., Clean Architecture Handbook</p>"
                            ),
                            'en': (
                                "<p><em>« Duplicating a type is better than creating premature software coupling. "
                                "Decoupling starts at the interface contract level. »</em> — Alexandre G., Clean Architecture Handbook</p>"
                            ),
                        },
                        'links': [
                            {'label': {'fr': "S'abonner à la veille du dimanche", 'en': 'Subscribe to Sunday watch'}, 'url': '#newsletter', 'newTab': False},
                        ],
                    },
                ],
                'meta': {
                    'title': {
                        'fr': 'Veille & Insights Tech | Analyses & Benchmarks',
                        'en': 'Tech Insights & Radar | Analyses & Benchmarks',
                    },
                    'description': {
                        'fr': 'Analyses de code, retours de production et benchmarks k6 sur NestJS, Payload et Angular.',
                        'en': 'Code deep-dives, production feedback and k6 benchmarks on NestJS, Payload and Angular.',
                    },
                },
            },
        ]

        for item in pages:
            # Idempotent : met à jour par le slug s'il existe déjà, sinon crée
            self.upsert(env, 'pages', {'slug': {'equals': item['slug']}}, item)
