# -*- coding: utf-8 -*-
# pyrefly: ignore [missing-import]
from odoo.addons.payload_cms.payload import Seeder


class TechStackSeeder(Seeder):
    """Seeder pour les technologies et frameworks clés (Trinité technologique & écosystème)."""
    _name = 'tech_stacks'
    _description = "Technologies et Stacks techniques"
    _sequence = 10

    def run(self, env):
        stacks = [
            {
                'name': 'NestJS 10',
                'slug': 'nestjs',
                'category': 'framework',
                'color': '#E0234E',
                'sequence': 10,
                'active': True,
            },
            {
                'name': 'Payload CMS 3.0',
                'slug': 'payload-cms',
                'category': 'framework',
                'color': '#000000',
                'sequence': 20,
                'active': True,
            },
            {
                'name': 'Angular 18+',
                'slug': 'angular',
                'category': 'framework',
                'color': '#DD0031',
                'sequence': 30,
                'active': True,
            },
            {
                'name': 'TypeScript 5.4',
                'slug': 'typescript',
                'category': 'language',
                'color': '#3178C6',
                'sequence': 40,
                'active': True,
            },
            {
                'name': 'Docker & K8s',
                'slug': 'docker-k8s',
                'category': 'cloud',
                'color': '#2496ED',
                'sequence': 50,
                'active': True,
            },
            {
                'name': 'RabbitMQ & Redis',
                'slug': 'rabbitmq-redis',
                'category': 'tool',
                'color': '#FF6600',
                'sequence': 60,
                'active': True,
            },
            {
                'name': 'GraphQL & tRPC',
                'slug': 'graphql-trpc',
                'category': 'tool',
                'color': '#E10098',
                'sequence': 70,
                'active': True,
            },
            {
                'name': 'PostgreSQL',
                'slug': 'postgresql',
                'category': 'database',
                'color': '#336791',
                'sequence': 80,
                'active': True,
            },
            {
                'name': 'Tailwind CSS v4',
                'slug': 'tailwind-css',
                'category': 'tool',
                'color': '#38BDF8',
                'sequence': 90,
                'active': True,
            },
        ]

        for item in stacks:
            # Idempotent : met à jour si le slug existe déjà, sinon crée le document
            self.upsert(env, 'tech-stacks', {'slug': {'equals': item['slug']}}, item)
