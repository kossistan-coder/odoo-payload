# -*- coding: utf-8 -*-
"""Localization (Payload `localization` config) + machine translation settings.

Settings are stored as JSON in the `payload_cms.localization` system parameter::

    {
        "enabled": true,
        "locales": [{"code": "en", "label": "English"}, {"code": "fr", "label": "Français"}],
        "defaultLocale": "en",
        "fallback": true,
        "translate": {"provider": "google", "apiKey": "...", "autoTranslate": "missing"}
    }

Localized field values are stored like Payload does: ``{"en": ..., "fr": ...}``.
"""
import json

from .translate import provider_ready

PARAM = 'payload_cms.localization'
DEFAULTS = {
    'enabled': False,
    'locales': [{'code': 'en', 'label': 'English'}, {'code': 'fr', 'label': 'Français'}],
    'defaultLocale': 'en',
    'fallback': True,
    'translate': {'provider': 'google', 'apiKey': '', 'autoTranslate': 'off'},
}


def get_settings(env):
    raw = env['ir.config_parameter'].sudo().get_param(PARAM)
    settings = json.loads(json.dumps(DEFAULTS))
    if raw:
        try:
            stored = json.loads(raw)
            settings.update({k: v for k, v in stored.items() if k != 'translate'})
            settings['translate'].update(stored.get('translate') or {})
        except ValueError:
            pass
    codes = [l['code'] for l in settings['locales'] if l.get('code')]
    if settings['defaultLocale'] not in codes and codes:
        settings['defaultLocale'] = codes[0]
    return settings


def set_settings(env, settings):
    env['ir.config_parameter'].sudo().set_param(PARAM, json.dumps(settings))


def locale_codes(settings):
    return [l['code'] for l in settings.get('locales') or [] if l.get('code')] if settings.get('enabled') else []


def public_settings(settings):
    """Settings exposed to the admin (API key hidden)."""
    return {
        'enabled': bool(settings.get('enabled')),
        'locales': settings.get('locales') or [],
        'defaultLocale': settings.get('defaultLocale'),
        'fallback': bool(settings.get('fallback')),
        'translate': {
            'enabled': provider_ready(settings.get('translate') or {}),
            'provider': (settings.get('translate') or {}).get('provider') or 'google',
            'autoTranslate': (settings.get('translate') or {}).get('autoTranslate') or 'off',
        },
    }


def make_context(settings, locale=None, fallback_locale=None):
    """Locale context passed to the models (``payload_locale`` context key)."""
    codes = locale_codes(settings)
    if not codes:
        return None
    default = settings['defaultLocale']
    if locale == 'all':
        loc = 'all'
    else:
        loc = locale if locale in codes else default
    if fallback_locale in ('none', 'null', 'false'):
        fallback = None
    elif fallback_locale in codes:
        fallback = fallback_locale
    else:
        fallback = default if settings.get('fallback', True) else None
    return {'locale': loc, 'fallback': fallback, 'codes': codes, 'default': default}
