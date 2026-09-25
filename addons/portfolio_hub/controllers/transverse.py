# -*- coding: utf-8 -*-
import json
import logging
import re
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)
from odoo.addons.payload_cms.payload import Model, api_doc
from .common import DELIVERY_PARAMS, error_response, get_delivery

EMAIL_RE = re.compile(r"^[\w\.\+\-]+@[\w\.\-]+\.[a-zA-Z]{2,}$")


class TransverseApiController(http.Controller):
    """Endpoints API transverses : Stats, Stacks techniques, Projets, Pages et formulaires."""

    # ==================================================================
    # Statistiques Homepage
    # ==================================================================
    @api_doc(
        tags=['Stats & Stacks'],
        summary="Statistiques clés de la Homepage",
        description="Retourne les 4 indicateurs du hero (12,000+ Développeurs, 99.4% Satisfaction, etc.).",
        delivery=True,
        depth=0,
        model='homepage-stats',
        many=True,
    )
    @http.route('/portfolio/api/stats', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_homepage_stats(self, **kw):
        delivery = get_delivery(default_depth=0, **kw)
        result = delivery.documents('homepage-stats', domain=[('active', '=', True)], order='sequence asc')
        return request.make_json_response(result)

    # ==================================================================
    # Technologies & Stacks
    # ==================================================================
    @api_doc(
        tags=['Stats & Stacks'],
        summary="Technologies et Stacks",
        description="Retourne la liste des frameworks, langages et outils avec code couleur et catégorie.",
        delivery=True,
        depth=0,
        model='tech-stacks',
        many=True,
        params=dict(DELIVERY_PARAMS, category=(str, "Filtrer par catégorie : 'framework', 'language', 'tool', 'cloud'")),
    )
    @http.route('/portfolio/api/tech-stacks', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_tech_stacks(self, category=None, **kw):
        domain = [('active', '=', True)]
        if category:
            domain.append(('category', '=', category))

        delivery = get_delivery(default_depth=0, **kw)
        result = delivery.documents('tech-stacks', domain=domain, order='sequence asc')
        return request.make_json_response(result)

    @api_doc(
        tags=['Stats & Stacks'],
        summary="Les 3 Piliers Technologiques (Trinité)",
        description="Retourne la sélection des 3 piliers phares (NestJS 10, Payload CMS 3.0, Angular 18+).",
        delivery=True,
        depth=0,
        model='tech-stacks',
        many=True,
    )
    @http.route('/portfolio/api/tech-stacks/pillars', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_pillars(self, **kw):
        delivery = get_delivery(default_depth=0, **kw)
        pillars_slugs = ['nestjs', 'payload-cms', 'angular']
        result = delivery.documents('tech-stacks', domain=[('slug', 'in', pillars_slugs)], order='sequence asc')
        return request.make_json_response(result)

    # ==================================================================
    # Projets / Réalisations
    # ==================================================================
    @api_doc(
        tags=['Projets'],
        summary="Projets du portfolio",
        description="Retourne les réalisations et cas d'études d'architecture avec leurs technologies.",
        delivery=True,
        depth=1,
        model='projects',
        many=True,
        params=dict(DELIVERY_PARAMS, status=(str, "Filtrer par statut : 'featured' ou 'published'")),
    )
    @http.route('/portfolio/api/projects', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_projects(self, status=None, **kw):
        domain = []
        if status:
            domain.append(('status', '=', status))
        else:
            domain.append(('status', 'in', ('featured', 'published')))

        delivery = get_delivery(default_depth=1, **kw)
        result = delivery.documents('projects', domain=domain, order='status asc, date_realisation desc')
        return request.make_json_response(result)

    @api_doc(
        tags=['Projets'],
        summary="Détail d'un projet",
        description="Retourne la description complète, les captures d'écran et les liens démo/GitHub.",
        delivery=True,
        depth=2,
        model='projects',
        params=dict(DELIVERY_PARAMS, slug="Slug du projet ou ID"),
    )
    @http.route('/portfolio/api/projects/<string:slug>', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_project_by_slug(self, slug, **kw):
        delivery = get_delivery(default_depth=2, **kw)
        result = delivery.document('projects', slug)
        if not result:
            return error_response(f"Projet '{slug}' introuvable", status=404)
        return request.make_json_response(result)

    # ==================================================================
    # Pages CMS (Accueil, Formations, Veille...)
    # ==================================================================
    @api_doc(
        tags=['Pages'],
        summary="Rendu d'une page complète",
        description="Retourne la structure complète d'une page (Accueil, Formations, Veille) avec ses blocs de contenu et métadonnées SEO.",
        delivery=True,
        depth=2,
        model='pages',
        params=dict(DELIVERY_PARAMS, slug="Slug de la page : 'home', 'formations', 'veille-insights'"),
    )
    @http.route('/portfolio/api/pages/<string:slug>', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_page_by_slug(self, slug, **kw):
        delivery = get_delivery(default_depth=2, **kw)
        result = delivery.document('pages', slug)
        if not result:
            return error_response(f"Page '{slug}' introuvable", status=404)
        return request.make_json_response(result)

    # ==================================================================
    # Formulaires : Inscription Newsletter & Contact / Devis
    # ==================================================================
    @api_doc(
        tags=['Formulaires'],
        summary="Inscription à la newsletter (La Veille du Dimanche)",
        description="Enregistre un nouvel abonné avec validation d'email et source d'acquisition.",
        body={'email': {'type': 'string', 'format': 'email', 'required': True}, 'source': str},
        response={'type': 'object', 'properties': {'success': {'type': 'boolean'}, 'message': {'type': 'string'}}},
    )
    @http.route('/portfolio/api/newsletter/subscribe', type='http', auth='public', methods=['POST'], cors='*', csrf=False)
    def subscribe_newsletter(self, **_kw):
        try:
            data = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except ValueError:
            return error_response("Corps JSON invalide")

        email = (data.get('email') or '').strip().lower()
        if not email or not EMAIL_RE.match(email):
            return error_response("Adresse email invalide", status=422)

        source = data.get('source') or 'homepage'
        SubModel = Model(request.env, 'newsletter-subscribers').sudo()

        # Idempotent : si déjà inscrit, on met à jour la source
        existing = SubModel.search([('email', '=', email)], limit=1)
        if existing:
            SubModel.write(existing, {'source': source, 'active': True})
            return request.make_json_response({'success': True, 'message': 'Inscription confirmée ! Vous êtes déjà abonné à la veille.'})

        SubModel.create({
            'email': email,
            'source': source,
            'active': True,
        })
        return request.make_json_response({'success': True, 'message': 'Bienvenue dans la Veille du Dimanche !'}, status=201)

    @api_doc(
        tags=['Formulaires'],
        summary="Demande de contact, devis audit ou convention OPCO",
        description="Réceptionne les demandes des boutons d'actions (Commander un audit, Candidature mentorat, Financement OPCO).",
        body={'name': {'type': 'string', 'required': True},
              'email': {'type': 'string', 'format': 'email', 'required': True},
              'type': {'type': 'string', 'description': "Type : 'audit', 'mentorat', 'opco', 'general'"},
              'message': str},
        response={'type': 'object', 'properties': {'success': {'type': 'boolean'}, 'message': {'type': 'string'}}},
    )
    @http.route('/portfolio/api/contact', type='http', auth='public', methods=['POST'], cors='*', csrf=False)
    def contact_request(self, **_kw):
        try:
            data = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except ValueError:
            return error_response("Corps JSON invalide")

        email = (data.get('email') or '').strip().lower()
        name = (data.get('name') or '').strip()
        req_type = data.get('type') or 'general'
        msg = data.get('message') or ''

        if not email or not EMAIL_RE.match(email):
            return error_response("Adresse email invalide", status=422)
        if not name:
            return error_response("Le nom est obligatoire", status=422)

        # Enregistrement de l'activité sur le partenaire admin
        try:
            admin_partner = request.env.ref('base.partner_admin', raise_if_not_found=False) or request.env.ref('base.user_admin').partner_id
            partner_model = request.env['ir.model'].sudo().search([('model', '=', 'res.partner')], limit=1)
            act_type = request.env['mail.activity.type'].sudo().search([], limit=1)
            if partner_model and admin_partner and act_type:
                request.env['mail.activity'].sudo().create({
                    'res_model_id': partner_model.id,
                    'res_id': admin_partner.id,
                    'summary': f"Demande contact [{req_type.upper()}] de {name} ({email})",
                    'note': f"<p><strong>Nom :</strong> {name}</p><p><strong>Email :</strong> {email}</p><p><strong>Type :</strong> {req_type}</p><p><strong>Message :</strong> {msg}</p>",
                    'activity_type_id': act_type.id,
                })
        except Exception as e:
            _logger.warning("Impossible de créer l'activité mail pour la demande de contact : %s", e)

        return request.make_json_response({
            'success': True,
            'message': f"Merci {name}, votre demande ({req_type}) a été prise en compte. Réponse garantie sous 48h.",
        }, status=201)
