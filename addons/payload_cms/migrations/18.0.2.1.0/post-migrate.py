# -*- coding: utf-8 -*-
"""Pages: the "Hero" section (tab + group ``hero``) is removed, the layout blocks cover it."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    pages = env['cms.collection'].with_context(active_test=False).search([('slug', '=', 'pages'), ('kind', '=', 'collection')])
    if not pages:
        return
    Field = env['cms.field.definition']
    hero = Field.search([('collection_id', '=', pages.id), ('name', '=', 'hero'), ('field_type', '=', 'group')])
    tabs = hero.mapped('parent_id').filtered(lambda f: f.field_type == 'tab' and not f.name)
    # the unnamed "Hero" tab only holds the hero group: remove the whole tab
    (tabs.filtered(lambda t: t.child_ids <= hero) | hero).unlink()
    docs = env['cms.document'].search([('collection_id', '=', pages.id)])
    for doc in docs:
        vals = {}
        for column in ('data', 'published_data'):
            if isinstance(doc[column], dict) and 'hero' in doc[column]:
                vals[column] = {k: v for k, v in doc[column].items() if k != 'hero'}
        if vals:
            doc.write(vals)
    _logger.info("Payload CMS: Hero section removed from Pages (%s documents cleaned)", len(docs))
