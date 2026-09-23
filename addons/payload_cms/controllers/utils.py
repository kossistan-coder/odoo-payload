# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import time

from odoo.http import request

TOKEN_EXPIRATION = 7200  # seconds, Payload's default `auth.tokenExpiration`


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _unb64(data):
    return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4))


def _secret(env):
    secret = env['ir.config_parameter'].sudo().get_param('database.secret') or ''
    return hashlib.sha256(('payload_cms.jwt:' + secret).encode()).digest()


def encode_jwt(env, user, expiration=None):
    """HS256 JWT compatible with Payload's token payload ({id, collection, email})."""
    expiration = expiration or int(env['ir.config_parameter'].sudo().get_param(
        'payload_cms.token_expiration', TOKEN_EXPIRATION))
    now = int(time.time())
    payload = {
        'id': user.id,
        'collection': 'users',
        'email': user.login,
        'sid': user._compute_session_token('payload-jwt')[:16],
        'iat': now,
        'exp': now + expiration,
    }
    header = _b64(json.dumps({'alg': 'HS256', 'typ': 'JWT'}, separators=(',', ':')).encode())
    body = _b64(json.dumps(payload, separators=(',', ':')).encode())
    signature = hmac.new(_secret(env), ('%s.%s' % (header, body)).encode(), hashlib.sha256).digest()
    return '%s.%s.%s' % (header, body, _b64(signature)), payload['exp']


def decode_jwt(env, token):
    """Return the user id of a valid token, else None."""
    try:
        header, body, signature = token.split('.')
        expected = hmac.new(_secret(env), ('%s.%s' % (header, body)).encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(signature)):
            return None
        payload = json.loads(_unb64(body))
    except (ValueError, TypeError):
        return None
    if payload.get('exp', 0) < time.time():
        return None
    user = env['res.users'].sudo().browse(int(payload.get('id') or 0)).exists()
    if not user or not user.active:
        return None
    # Changing the password invalidates the session token and hence the JWT.
    if payload.get('sid') != user._compute_session_token('payload-jwt')[:16]:
        return None
    return user.id, payload


def cors_headers():
    origin = request.httprequest.headers.get('Origin')
    if not origin:
        return []
    setting = (request.env['ir.config_parameter'].sudo().get_param('payload_cms.cors', '*') or '').strip()
    allowed = [o.strip().rstrip('/') for o in setting.split(',') if o.strip()]
    headers = [
        ('Access-Control-Allow-Methods', 'GET, POST, PATCH, PUT, DELETE, OPTIONS'),
        ('Access-Control-Allow-Headers',
         'Origin, X-Requested-With, Content-Type, Accept, Authorization, Content-Encoding, x-apollo-tracing, '
         'X-Payload-HTTP-Method-Override, X-Payload-Tenant'),
        ('Vary', 'Origin'),
    ]
    if origin.rstrip('/') in allowed:
        headers += [('Access-Control-Allow-Origin', origin), ('Access-Control-Allow-Credentials', 'true')]
    elif '*' in allowed:
        headers.append(('Access-Control-Allow-Origin', '*'))
    elif _is_site_origin(origin):
        # multisite: the frontends of the sites (custom domains / subdomains) may read the API
        headers.append(('Access-Control-Allow-Origin', origin))
    return headers


def _is_site_origin(origin):
    from urllib.parse import urlparse
    from ..tools import multitenancy
    settings = multitenancy.get_settings(request.env)
    if not settings.get('enabled') or not settings.get('corsSites', True):
        return False
    host = urlparse(origin).hostname
    return bool(host and multitenancy.resolve_host(request.env, host))


def json_response(data, status=200, headers=None):
    body = json.dumps(data, default=str, ensure_ascii=False)
    all_headers = [('Content-Type', 'application/json; charset=utf-8'), ('Cache-Control', 'no-store')]
    all_headers += cors_headers() + list(headers or [])
    return request.make_response(body, headers=all_headers, status=status)


def error_response(message, status=400, extra=None):
    error = {'message': message}
    if extra:
        error.update(extra)
    return json_response({'errors': [error]}, status=status)
