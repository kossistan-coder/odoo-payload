# -*- coding: utf-8 -*-
"""Multisite: site URLs on the `tenants` documents and site access of users."""
from odoo import fields, models

from ..tools import multitenancy


class CmsDocument(models.Model):
    _inherit = 'cms.document'

    def _payload_serialize(self, draft=True, depth=0, populate=None):
        doc = super()._payload_serialize(draft=draft, depth=depth, populate=populate)
        if self.collection_slug == multitenancy.TENANTS:
            doc['siteUrls'] = multitenancy.site_urls(self.env, self)
        return doc


class ResUsers(models.Model):
    _inherit = 'res.users'

    payload_tenant_ids = fields.Many2many(
        'cms.document', 'payload_cms_user_tenant_rel', 'user_id', 'tenant_id', string="CMS sites",
        domain=[('collection_slug', '=', 'tenants')],
        help="Multisite: sites this editor can manage (empty = every site). CMS admins manage every site.")
