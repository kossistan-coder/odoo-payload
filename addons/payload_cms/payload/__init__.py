# -*- coding: utf-8 -*-
"""Code-first API of payload_cms: declare Payload collections like Odoo models.

    from odoo.addons.payload_cms.payload import Collection, Global, fields
"""
from . import fields
from .collection import Collection, Global, build_fields, registered

__all__ = ['Collection', 'Global', 'fields', 'build_fields', 'registered']
