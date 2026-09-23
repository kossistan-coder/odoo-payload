# -*- coding: utf-8 -*-
"""Multi-tenancy ("multisite"), inspired by @payloadcms/plugin-multi-tenant and
WordPress Multisite.

* ``networks``: a network has a base domain (``example.com``);
* ``tenants`` (sites): a site belongs to a network and is served on
  ``{slug}.{network domain}``, plus optional custom domains (domain mapping);
* collections / globals flagged ``multi_tenant`` get a ``tenant`` relationship
  field and are filtered by the current site.

The current site of a request comes from the ``X-Payload-Tenant`` header (ID or
slug), the ``?tenant=`` parameter or, when ``resolveByHost`` is on, from the
request host.
"""
import json

from odoo.tools import SQL

PARAM = 'payload_cms.multitenancy'
HEADER = 'X-Payload-Tenant'
TENANTS = 'tenants'
NETWORKS = 'networks'
DEFAULTS = {
    'enabled': False,
    'resolveByHost': True,
    'corsSites': True,
}

NETWORK_SCHEMA = [
    {
        'slug': NETWORKS,
        'labels': {'singular': 'Network', 'plural': 'Networks'},
        'admin': {'useAsTitle': 'name', 'defaultColumns': ['name', 'domain', 'updatedAt'], 'group': 'Multisite',
                  'description': 'A network groups sites under a base domain: its sites are served on {site}.{domain}.'},
        'publicRead': True,
        'fields': [
            {'name': 'name', 'type': 'text', 'label': 'Name', 'required': True},
            {'name': 'domain', 'type': 'text', 'label': 'Base domain', 'required': True, 'unique': True,
             'admin': {'placeholder': 'example.com',
                       'description': 'Point a wildcard DNS record (*.example.com) to this Odoo server.'}},
            {'name': 'description', 'type': 'textarea', 'label': 'Description'},
        ],
    },
    {
        'slug': TENANTS,
        'labels': {'singular': 'Site', 'plural': 'Sites'},
        'admin': {'useAsTitle': 'name', 'defaultColumns': ['name', 'slug', 'network', 'active', 'updatedAt'],
                  'group': 'Multisite',
                  'description': 'Sites (tenants) of the multisite network. Their content is isolated in the collections marked "Scoped per site".'},
        'publicRead': True,
        'fields': [
            {'type': 'row', 'fields': [
                {'name': 'name', 'type': 'text', 'label': 'Site name', 'required': True,
                 'admin': {'width': '50%', 'placeholder': 'My blog',
                           'description': 'Shown in the site selector of the navigation.'}},
                {'name': 'slug', 'type': 'slug', 'useAsSlug': 'name', 'label': 'Slug', 'required': True,
                 'admin': {'width': '50%', 'position': 'main', 'placeholder': 'my-blog',
                           'description': 'Subdomain ({slug}.{network domain}) and value of X-Payload-Tenant / ?tenant=.'}},
            ]},
            {'name': 'network', 'type': 'relationship', 'relationTo': NETWORKS, 'label': 'Network',
             'admin': {'description': 'The site is served on {slug}.{network domain}.'}},
            {'name': 'domains', 'type': 'array', 'label': 'Custom domains',
             'labels': {'singular': 'Domain', 'plural': 'Domains'},
             'admin': {'description': 'Domain mapping: other host names serving this site (e.g. www.my-shop.com).',
                       'rowLabelField': 'domain'},
             'fields': [{'name': 'domain', 'type': 'text', 'label': 'Domain', 'required': True,
                         'admin': {'placeholder': 'www.my-shop.com'}}]},
            {'name': 'description', 'type': 'textarea', 'label': 'Description'},
            {'name': 'active', 'type': 'checkbox', 'label': 'Active', 'defaultValue': True,
             'admin': {'position': 'sidebar', 'description': 'Inactive sites are hidden from anonymous clients.'}},
        ],
    },
]


def get_settings(env):
    settings = dict(DEFAULTS)
    raw = env['ir.config_parameter'].sudo().get_param(PARAM)
    if raw:
        try:
            settings.update(json.loads(raw))
        except ValueError:
            pass
    return settings


def set_settings(env, settings):
    env['ir.config_parameter'].sudo().set_param(PARAM, json.dumps(settings))


def tenant_field(kind='collection'):
    field = {'name': 'tenant', 'type': 'relationship', 'relationTo': TENANTS, 'label': 'Site',
             'required': kind == 'collection', 'index': True,
             'admin': {'position': 'sidebar', 'description': 'Site owning this document.'}}
    if kind == 'global':
        field['required'] = False
        field['admin'] = {'hidden': True}
    return field


def _tenants(env):
    return env['cms.collection']._get_by_slug(TENANTS)


def find_tenant(env, value):
    """Tenant document from an ID or a slug."""
    collection = _tenants(env)
    if not collection or value in (None, ''):
        return env['cms.document']
    Document = env['cms.document'].sudo()
    value = str(value).strip()
    if value.isdigit():
        doc = Document.browse(int(value)).exists()
        return doc if doc and doc.collection_id == collection else Document
    env.cr.execute(SQL("SELECT id FROM cms_document WHERE collection_id = %s AND data->>'slug' = %s ORDER BY id LIMIT 1",
                       collection.id, value))
    row = env.cr.fetchone()
    return Document.browse(row[0]) if row else Document


def resolve_host(env, host):
    """Tenant served on ``host`` (custom domain or {slug}.{network domain})."""
    host = (host or '').split(':')[0].strip().lower().rstrip('.')
    tenants = _tenants(env)
    if not host or not tenants:
        return env['cms.document']
    cr = env.cr
    cr.execute(SQL("""
        SELECT id FROM cms_document
         WHERE collection_id = %s
           AND EXISTS (SELECT 1 FROM jsonb_array_elements(CASE WHEN jsonb_typeof(data->'domains') = 'array'
                                                          THEN data->'domains' ELSE '[]'::jsonb END) d
                        WHERE lower(d->>'domain') = %s)
         ORDER BY id LIMIT 1""", tenants.id, host))
    row = cr.fetchone()
    if not row and '.' in host:
        sub, base = host.split('.', 1)
        networks = env['cms.collection']._get_by_slug(NETWORKS)
        if networks:
            cr.execute(SQL("""
                SELECT t.id FROM cms_document t
                  JOIN cms_document n ON n.collection_id = %s AND lower(n.data->>'domain') = %s
                 WHERE t.collection_id = %s AND lower(t.data->>'slug') = %s AND t.data->>'network' = n.id::text
                 ORDER BY t.id LIMIT 1""", networks.id, base, tenants.id, sub))
            row = cr.fetchone()
    return env['cms.document'].sudo().browse(row[0]) if row else env['cms.document']


def is_active(tenant):
    return (tenant.data or {}).get('active') is not False


def site_urls(env, tenant, scheme='https'):
    data = tenant.data or {}
    urls = []
    network = data.get('network')
    if network and data.get('slug'):
        doc = env['cms.document'].sudo().browse(int(network)).exists()
        domain = doc and (doc.data or {}).get('domain')
        if domain:
            urls.append('%s://%s.%s' % (scheme, data['slug'], domain))
    for row in data.get('domains') or []:
        if isinstance(row, dict) and row.get('domain'):
            urls.append('%s://%s' % (scheme, row['domain']))
    return urls
