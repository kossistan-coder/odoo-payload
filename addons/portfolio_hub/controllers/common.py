# -*- coding: utf-8 -*-
from odoo.http import request
from odoo.addons.payload_cms.payload import Delivery

DELIVERY_PARAMS = {
    'locale': (str, "Langue : 'all' (défaut, toutes les langues) ou code ('fr', 'en')"),
    'depth': (int, "Niveau de relations peuplées de 0 à 3 (défaut : 1)"),
    'draft': (bool, "Afficher les brouillons (utilisateurs CMS uniquement)"),
}


def error_response(message, status=400):
    """Retourne une réponse JSON d'erreur formatée."""
    return request.make_json_response({'error': message, 'status': status}, status=status)


def get_delivery(default_depth=1, locale=None, depth=None, draft=None, **_kw):
    """Initialise l'API Delivery de Payload CMS avec les options de requête."""
    try:
        depth_val = int(depth) if depth is not None and str(depth).isdigit() else default_depth
    except (ValueError, TypeError):
        depth_val = default_depth

    return Delivery(
        request.env,
        locale=locale or 'all',
        depth=depth_val,
        draft=str(draft).lower() in ('1', 'true', 'yes'),
    )
