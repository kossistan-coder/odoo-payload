# -*- coding: utf-8 -*-
"""Code-first API of payload_cms: declare Payload collections like Odoo models.

    from odoo.addons.payload_cms.payload import Block, Collection, Global, Seeder, fields

Odoo-like data access (domains, search_read, JSON-RPC on /payload/dataset/call_kw):

    from odoo.addons.payload_cms.payload import Model, api_doc, expose

Delivery API (read-only format for the frontends: normalized, multilingual):

    from odoo.addons.payload_cms.payload import Delivery
"""
from . import fields
from .apidoc import api_doc
from .delivery import Delivery
from .model import Model, domain_to_where, expose
from .collection import Block, Collection, Global, build_fields, registered, registered_blocks
from .seeder import Seeder, registered_seeders
from .section import SectionBlock

__all__ = ['api_doc', 'Block', 'Delivery', 'Collection', 'Global', 'Model', 'Seeder', 'SectionBlock', 'domain_to_where', 'expose', 'fields', 'build_fields', 'registered', 'registered_blocks',
           'registered_seeders']
