# -*- coding: utf-8 -*-
"""Default block of the Pages layout (``blockType: 'section'``)::

    { blockType: 'section', title: LocalizedString, subtitle?: LocalizedString, description: LocalizedString }
"""
from ..payload import SectionBlock


class Section(SectionBlock):
    _name = 'section'
    _label = 'Section'
    _inherit = 'pages.layout'
    _sequence = 1
