# -*- coding: utf-8 -*-
"""Base of the default layout block: a title, an optional subtitle and a description.

Front-end type::

    type SectionBlock = {
      title: LocalizedString
      subtitle?: LocalizedString
      description: LocalizedString
    }

A block inheriting from ``SectionBlock`` gets these three fields first, then
its own fields::

    class EpisodesList(SectionBlock):
        _name = 'episodes-list'
        limit = fields.Integer("Nombre", default=3)
"""
from . import fields
from .collection import Block


class SectionBlock(Block):
    """Title (required), subtitle, description (required), all translatable."""
    title = fields.Char("Title", required=True, translate=True)
    subtitle = fields.Char("Subtitle", translate=True)
    description = fields.Text("Description", required=True, translate=True)
