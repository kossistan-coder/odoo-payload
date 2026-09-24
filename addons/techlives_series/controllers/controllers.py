# -*- coding: utf-8 -*-
"""API du site Tech Lives Series, écrite comme n'importe quel contrôleur Odoo.

Les collections Payload se lisent et s'écrivent avec ``Model`` (domaines,
``search_read``, ``web_search_read``, ``create``) : les réponses ont la forme
des enregistrements Odoo. ``@api_doc`` publie chaque route dans la
documentation Swagger (/api-docs), avec le schéma de sa réponse.
"""
import json

from odoo import http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request

from odoo.addons.payload_cms.payload import Delivery, Model, api_doc

REGISTRATION = ['nom', 'prenom', 'email', 'phone', 'organization', 'profession', 'country', 'city', 'events', 'newsletter']
# paramètres communs des routes de lecture (API Delivery)
DELIVERY_PARAMS = {
    'locale': (str, "Langue : `all` (défaut, toutes les langues), ou un code (`fr`, `en`)"),
    'depth': (int, "Niveaux de relations peuplées avec toutes leurs informations (max 3) ; au-delà : `{id, type, displayName}`"),
}


def _error(message, status=400):
    return request.make_json_response({'error': message}, status=status)


def _delivery(default_depth, locale=None, depth=None, draft=None, **_kw):
    """API Delivery avec les paramètres de la requête (``?locale=fr&depth=1``)."""
    return Delivery(request.env, locale=locale or 'all', depth=int(depth) if str(depth or '').isdigit() else default_depth,
                    draft=str(draft).lower() in ('1', 'true'))


class TechLivesApi(http.Controller):

    @api_doc(tags=['Lives'], delivery=True, depth=1, model='events', paginated=True,
             params=dict(DELIVERY_PARAMS, limit=(int, "Nombre maximum de lives"), offset=(int, "Lives ignorés (pagination)")))
    @http.route('/techlives/api/lives', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def lives(self, limit=None, offset=0, **kw):
        """Lives actifs, du plus récent au plus ancien.

        Les intervenants, modérateurs, organisateurs et le replay sont inclus avec leurs informations.
        """
        return request.make_json_response(_delivery(1, **kw).documents(
            'events', [('active', '=', True)], order='date_sortie desc',
            limit=int(limit) if limit else None, offset=int(offset or 0)))

    @api_doc(tags=['Lives'], delivery=True, depth=2, model='events',
             params=dict(DELIVERY_PARAMS, slug="Slug du live (ex. episode-6-lia-generative-dans-les-metiers-du-quotidien) ou son ID"))
    @http.route('/techlives/api/lives/<string:slug>', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def live(self, slug, **kw):
        """Un live, avec ses intervenants (et leurs réseaux sociaux), modérateurs, organisateurs et replay."""
        result = _delivery(2, **kw).document('events', slug)
        return request.make_json_response(result) if result else _error('Not found', 404)

    @api_doc(tags=['Intervenants'], delivery=True, depth=1, model='speakers', many=True, params=DELIVERY_PARAMS)
    @http.route('/techlives/api/intervenants', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def speakers(self, **kw):
        """Intervenants affichés sur la page d'accueil (actifs et non masqués)."""
        return request.make_json_response(_delivery(1, **kw).documents(
            'speakers', [('active', '=', True), ('hidespeaker', '=', False)], order='nom'))

    # ------------------------------------------------------------------ Pages
    @api_doc(tags=['Pages'], delivery=True, depth=0, model='pages', many=True, params=DELIVERY_PARAMS)
    @http.route('/techlives/api/pages', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def pages(self, **kw):
        """Pages publiées, pour construire la navigation ou le sitemap."""
        return request.make_json_response(_delivery(0, **kw).documents('pages', [], order='title'))

    @api_doc(tags=['Pages'], delivery=True, depth=2, model='pages',
             params=dict(DELIVERY_PARAMS, key="Slug de la page (`home` pour l'accueil) ou son ID",
                         draft=(bool, "Lire le brouillon (utilisateurs du CMS uniquement)")))
    @http.route('/techlives/api/pages/<string:key>', type='http', auth='public', methods=['GET'], cors='*', sitemap=False)
    def page(self, key, **kw):
        """Une page complète, prête à afficher : ses attributs, son SEO et ses blocs, dans l'ordre de l'admin.

        Chaque bloc a un `type`, une `config` (mode, limite, ancre...) et un `content` : textes, images (URL)
        et les lives / intervenants / organisateurs affichés, avec toutes leurs informations (`events`,
        `speakers`, `live`...). En mode automatique, `config.source` décrit la requête (collection, filtre,
        tri, limite). Profondeur par défaut : 2 (ex. les intervenants des lives) ; au-delà, un document lié
        est résumé en `{id, type, displayName}`.
        """
        result = _delivery(2, **kw).document('pages', key)
        return request.make_json_response(result) if result else _error('Not found', 404)

    @api_doc(tags=['Contact'], model='messages',
             params={'name': {'type': 'string', 'required': True, 'description': "Nom et prénom"},
                     'email': {'type': 'string', 'format': 'email', 'required': True},
                     'phone': str,
                     'subject': {'type': 'string', 'required': True},
                     'message': {'type': 'string', 'required': True}},
             response={'type': 'object', 'properties': {'id': {'type': 'integer'}}})
    @http.route('/techlives/api/contact', type='json', auth='public', methods=['POST'], cors='*', csrf=False)
    def contact(self, name=None, email=None, subject=None, message=None, phone=None, **_kw):
        """Envoie un message (formulaire de contact du site).

        Le message arrive dans la collection « Messages » avec le statut « Nouveau ».
        """
        message_id = Model(request.env, 'messages').create({
            'name': name, 'email': email, 'phone': phone, 'subject': subject, 'message': message, 'status': 'new'})
        return {'id': message_id}

    @api_doc(tags=['Participants'], model='participants', body=REGISTRATION,
             response={'type': 'object', 'properties': {'id': {'type': 'integer'}}})
    @http.route('/techlives/api/inscription', type='http', auth='public', methods=['POST'], cors='*', csrf=False)
    def register(self, **_kw):
        """Inscription d'un participant à un ou plusieurs lives (corps JSON)."""
        try:
            data = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except ValueError:
            return _error('Invalid JSON body')
        try:
            participant_id = Model(request.env, 'participants').create({k: v for k, v in data.items() if k in REGISTRATION})
        except (ValidationError, AccessError) as e:
            return _error(e.args[0] if e.args else str(e))
        return request.make_json_response({'id': participant_id}, status=201)
