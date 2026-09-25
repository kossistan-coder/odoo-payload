# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.payload_cms.payload import api_doc
from .common import DELIVERY_PARAMS, error_response, get_delivery


class FormationsApiController(http.Controller):
    """Endpoints API pour le catalogue de formations et parcours guidés."""

    @api_doc(
        tags=['Formations'],
        summary="Liste des formations",
        description="Retourne le catalogue de formations avec filtres par niveau, mise en avant et pagination.",
        delivery=True,
        depth=1,
        model='formations',
        paginated=True,
        params=dict(
            DELIVERY_PARAMS,
            level=(str, "Niveau : 'beginner', 'intermediate', 'advanced'"),
            featured=(bool, "Filtrer uniquement les formations mises en avant"),
            limit=(int, "Nombre de résultats par page"),
            offset=(int, "Décalage pour pagination"),
        ),
    )
    @http.route('/portfolio/api/formations', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_formations(self, level=None, featured=None, limit=None, offset=0, **kw):
        domain = [('active', '=', True)]
        if level:
            domain.append(('level', '=', level))
        if featured is not None:
            is_feat = str(featured).lower() in ('1', 'true', 'yes')
            domain.append(('is_featured', '=', is_feat))

        delivery = get_delivery(default_depth=1, **kw)
        result = delivery.documents(
            'formations',
            domain=domain,
            order='is_featured desc, create_date desc',
            limit=int(limit) if limit and str(limit).isdigit() else None,
            offset=int(offset) if offset and str(offset).isdigit() else 0,
        )
        return request.make_json_response(result)

    @api_doc(
        tags=['Formations'],
        summary="Formation mise en avant (Track Recommandé)",
        description="Retourne la formation phare affichée sur la Hero section et le haut du catalogue (38h, Fullstack stack).",
        delivery=True,
        depth=2,
        model='formations',
        params=DELIVERY_PARAMS,
    )
    @http.route('/portfolio/api/formations/featured', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_featured_formation(self, **kw):
        delivery = get_delivery(default_depth=2, **kw)
        result = delivery.documents('formations', domain=[('active', '=', True), ('is_featured', '=', True)], limit=1)
        data = (result.get('data') or [])
        if not data:
            # Fallback sur la première formation active
            result = delivery.documents('formations', domain=[('active', '=', True)], limit=1)
            data = (result.get('data') or [])

        if not data:
            return error_response("Aucune formation disponible", status=404)
        return request.make_json_response({'data': data[0], 'meta': result.get('meta')})

    @api_doc(
        tags=['Formations'],
        summary="Détail d'une formation",
        description="Retourne la fiche complète d'une formation par son slug ou ID avec son curriculum détaillé.",
        delivery=True,
        depth=2,
        model='formations',
        params=dict(DELIVERY_PARAMS, slug="Slug de la formation (ex: fullstack-modern-stack-nestjs-payload-angular) ou ID"),
    )
    @http.route('/portfolio/api/formations/<string:slug>', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_formation_by_slug(self, slug, **kw):
        delivery = get_delivery(default_depth=2, **kw)
        result = delivery.document('formations', slug)
        if not result:
            return error_response(f"Formation '{slug}' introuvable", status=404)
        return request.make_json_response(result)

    @api_doc(
        tags=['Formations'],
        summary="Avantages et caractéristiques incluses",
        description="Retourne les points forts inclus dans chaque formation (Dépôts GitHub, Salon Discord, Certificat...).",
        delivery=True,
        depth=0,
        model='formation-features',
        many=True,
        params=DELIVERY_PARAMS,
    )
    @http.route('/portfolio/api/formation-features', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def get_formation_features(self, **kw):
        delivery = get_delivery(default_depth=0, **kw)
        result = delivery.documents('formation-features', domain=[], order='label asc')
        return request.make_json_response(result)
