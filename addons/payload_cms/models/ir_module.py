# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def module_uninstall(self):
        """Uninstalling a module removes what it added to the CMS, like Odoo removes
        the tables of its models: its code-first collections (with their documents),
        its layout blocks and the record of its seeders."""
        names = self.mapped('name')
        if names and 'payload_cms' not in names:
            env = self.env(su=True)
            collections = env['cms.collection'].with_context(active_test=False).search([('code_module', 'in', names)])
            for collection in collections:
                _logger.info("Payload CMS: module %s uninstalled, removing %s '%s' (%s documents)",
                             collection.code_module, collection.kind, collection.slug, len(collection.document_ids))
                collection.document_ids._payload_delete()
            collections.unlink()
            blocks = env['cms.field.definition'].search([('field_type', '=', 'block')]).filtered(
                lambda f: (f.config or {}).get('code_module') in names)
            blocks.unlink()
            params = env['ir.config_parameter'].search(
                ['|'] * (len(names) - 1) + [('key', '=like', 'payload_cms.seeder.%s.%%' % name) for name in names])
            params.unlink()
        return super().module_uninstall()
