# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Collection, fields


class Message(Collection):
    """Messages du formulaire de contact du site."""
    _name = 'messages'
    _sequence = 160
    _label = 'Message'
    _label_plural = 'Messages'
    _rec_name = 'subject'
    _order = '-createdAt'
    _columns = ['subject', 'name', 'email', 'status', 'createdAt']
    _search = ['subject', 'name', 'email']
    _public_read = False
    _public_create = True     # formulaire de contact (POST /api/messages)

    name = fields.Char("Nom", required=True, row="from")
    email = fields.Email("Email", required=True, row="from")
    phone = fields.Char("Téléphone")
    subject = fields.Char("Sujet", required=True)
    message = fields.Text("Message", required=True)
    status = fields.Selection([('new', 'Nouveau', 'info'), ('read', 'Lu', 'warning'), ('answered', 'Répondu', 'success'),
                               ('archived', 'Archivé', 'muted')],
                              "Statut", default='new', sidebar=True)
    event = fields.Many2one('events', "Live concerné", sidebar=True)
