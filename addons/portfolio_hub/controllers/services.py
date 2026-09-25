# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.payload_cms.payload import api_doc
from .common import DELIVERY_PARAMS, error_response, get_delivery


class ServicesApiController(http.Controller):
    """Endpoints API pour les offres de services (Mentorat 1-on-1, Audit, Workshops B2B)."""

    @api_doc(
        tags=['Services'],
        summary="Liste des services d'architecture et de mentorat",
        description="Retourne les offres de services avec tarif d'appel, description et libellé d'action.",
        delivery=True,
        depth=1,
        model='services',
        many=True,
        params=dict(
            DELIVERY_PARAMS,
            service_type=(str, "Filtrer par type : 'mentorat', 'audit', 'workshop', 'formation_b2b'"),
        ),
    )
    @http.route('/portfolio/api/services', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_services(self, service_type=None, **kw):
        domain = [('is_active', '=', True)]
        if service_type:
            domain.append(('service_type', '=', service_type))

        delivery = get_delivery(default_depth=1, **kw)
        result = delivery.documents('services', domain=domain, order='sequence asc')
        return request.make_json_response(result)

    @api_doc(
        tags=['Services'],
        summary="Détail d'un service",
        description="Retourne la description complète et les modalités d'un service par son slug ou ID.",
        delivery=True,
        depth=1,
        model='services',
        params=dict(DELIVERY_PARAMS, slug="Slug du service (ex: mentorat-1-on-1, audit-technique-securite) ou ID"),
    )
    @http.route('/portfolio/api/services/<string:slug>', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_service_by_slug(self, slug, **kw):
        delivery = get_delivery(default_depth=1, **kw)
        result = delivery.document('services', slug)
        if not result:
            return error_response(f"Service '{slug}' introuvable", status=404)
        return request.make_json_response(result)
