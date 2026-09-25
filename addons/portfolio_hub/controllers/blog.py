# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.payload_cms.payload import Model, api_doc
from .common import DELIVERY_PARAMS, error_response, get_delivery


class BlogApiController(http.Controller):
    """Endpoints API pour le blog technique, les analyses de terrain et la veille."""

    @api_doc(
        tags=['Blog & Veille'],
        summary="Articles de blog et veille technique",
        description="Retourne les articles publiés avec filtres par catégorie, tag, format veille et recherche.",
        delivery=True,
        depth=1,
        model='posts',
        paginated=True,
        params=dict(
            DELIVERY_PARAMS,
            category=(str, "Slug de la catégorie (ex: nestjs, payload-cms, angular)"),
            tag=(str, "Slug du tag (ex: signals, valide-prod, deep-dive)"),
            is_veille=(bool, "True pour n'afficher que les veilles rapides, False pour analyses de fond"),
            search=(str, "Terme de recherche dans le titre ou l'extrait"),
            limit=(int, "Nombre d'articles par page"),
            offset=(int, "Pagination offset"),
            order=(str, "Tri : 'published_date desc' (défaut), 'reading_time asc', etc."),
        ),
    )
    @http.route('/portfolio/api/posts', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_posts(self, category=None, tag=None, is_veille=None, search=None, limit=None, offset=0, order=None, **kw):
        domain = []

        # Filtre catégorie
        if category:
            cat_doc = Model(request.env, 'categories').search([('slug', '=', category)], limit=1)
            if cat_doc:
                domain.append(('category', '=', cat_doc[0]))
            else:
                return request.make_json_response({'data': [], 'meta': {'total': 0}})

        # Filtre tag
        if tag:
            tag_doc = Model(request.env, 'tags').search([('slug', '=', tag)], limit=1)
            if tag_doc:
                domain.append(('tags', 'in', [tag_doc[0]]))
            else:
                return request.make_json_response({'data': [], 'meta': {'total': 0}})

        # Filtre type veille vs analyse
        if is_veille is not None:
            domain.append(('is_veille', '=', str(is_veille).lower() in ('1', 'true', 'yes')))

        # Recherche textuelle
        if search:
            domain.append('|')
            domain.append(('title', 'ilike', search))
            domain.append(('excerpt', 'ilike', search))

        delivery = get_delivery(default_depth=1, **kw)
        result = delivery.documents(
            'posts',
            domain=domain,
            order=order or 'published_date desc',
            limit=int(limit) if limit and str(limit).isdigit() else None,
            offset=int(offset) if offset and str(offset).isdigit() else 0,
        )
        return request.make_json_response(result)

    @api_doc(
        tags=['Blog & Veille'],
        summary="Article à la une (Deep Dive)",
        description="Retourne le grand article mis en avant pour la section Hero du blog (Payload 3.0 + NestJS).",
        delivery=True,
        depth=2,
        model='posts',
        params=DELIVERY_PARAMS,
    )
    @http.route('/portfolio/api/posts/featured', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_featured_post(self, **kw):
        delivery = get_delivery(default_depth=2, **kw)
        # Priorité à l'article deep-dive
        tag_docs = Model(request.env, 'tags').search([('slug', '=', 'deep-dive')], limit=1)
        domain = [('tags', 'in', [tag_docs[0]])] if tag_docs else [('is_veille', '=', False)]
        result = delivery.documents('posts', domain=domain, limit=1)
        data = (result.get('data') or [])
        if not data:
            result = delivery.documents('posts', domain=[('is_veille', '=', False)], order='published_date desc', limit=1)
            data = (result.get('data') or [])

        if not data:
            return error_response("Aucun article disponible", status=404)
        return request.make_json_response({'data': data[0], 'meta': result.get('meta')})

    @api_doc(
        tags=['Blog & Veille'],
        summary="Détail d'un article",
        description="Retourne le contenu complet HTML/Lexical, métadonnées, auteur et technologies liées d'un article.",
        delivery=True,
        depth=2,
        model='posts',
        params=dict(DELIVERY_PARAMS, slug="Slug de l'article ou son ID"),
    )
    @http.route('/portfolio/api/posts/<string:slug>', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_post_by_slug(self, slug, **kw):
        delivery = get_delivery(default_depth=2, **kw)
        result = delivery.document('posts', slug)
        if not result:
            return error_response(f"Article '{slug}' introuvable", status=404)
        return request.make_json_response(result)

    @api_doc(
        tags=['Blog & Veille'],
        summary="Liste des catégories avec comptage",
        description="Retourne toutes les catégories disponibles avec le nombre d'articles associés.",
        delivery=True,
        depth=0,
        model='categories',
        many=True,
    )
    @http.route('/portfolio/api/categories', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_categories(self, **kw):
        delivery = get_delivery(default_depth=0, **kw)
        result = delivery.documents('categories', domain=[], order='name asc')

        # Comptage dynamique des articles par catégorie
        PostModel = Model(request.env, 'posts')
        for cat in result.get('data') or []:
            cat_id = cat.get('id')
            cat['articleCount'] = PostModel.search_count([('category', '=', cat_id)]) if cat_id else 0

        return request.make_json_response(result)

    @api_doc(
        tags=['Blog & Veille'],
        summary="Liste des tags",
        description="Retourne la liste des tags thématiques (Signals, Validé Prod, Next App...).",
        delivery=True,
        depth=0,
        model='tags',
        many=True,
    )
    @http.route('/portfolio/api/tags', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_tags(self, **kw):
        delivery = get_delivery(default_depth=0, **kw)
        result = delivery.documents('tags', domain=[], order='name asc')
        return request.make_json_response(result)

    @api_doc(
        tags=['Blog & Veille'],
        summary="Métriques du radar de veille",
        description="Retourne les indicateurs de tête de la page Veille (articles indexés, snippets, status).",
        response={
            'type': 'object',
            'properties': {
                'indexedArticles': {'type': 'integer', 'example': 148},
                'codeSnippets': {'type': 'string', 'example': '390+'},
                'systemStatus': {'type': 'string', 'example': 'LIVE REPO'},
                'totalCategories': {'type': 'integer', 'example': 5},
            },
        },
    )
    @http.route('/portfolio/api/insights/metrics', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_insights_metrics(self, **_kw):
        posts_count = Model(request.env, 'posts').search_count([])
        categories_count = Model(request.env, 'categories').search_count([])
        metrics = {
            'indexedArticles': max(148, posts_count),
            'codeSnippets': '390+',
            'systemStatus': 'LIVE REPO',
            'totalCategories': categories_count,
            'latestEdition': '#42',
        }
        return request.make_json_response(metrics)
