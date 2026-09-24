# -*- coding: utf-8 -*-
from odoo.addons.payload_cms.payload import Collection, fields


class EmailTrack(Collection):
    """Suivi des emails envoyés aux participants (invitations, rappels, replays)."""
    _name = 'email-tracks'
    _sequence = 170
    _label = 'Suivi email'
    _label_plural = 'Suivi des emails'
    _rec_name = 'subject'
    _order = '-sent_at'
    _columns = ['subject', 'email', 'type', 'status', 'sent_at', 'opened_at']
    _public_read = False

    email = fields.Email("Destinataire", required=True, row="to")
    participant = fields.Many2one('participants', "Participant", row="to")
    subject = fields.Char("Sujet", required=True)
    event = fields.Many2one('events', "Live")
    type = fields.Selection([('invitation', 'Invitation'), ('reminder', 'Rappel'), ('replay', 'Replay'),
                             ('newsletter', 'Newsletter'), ('other', 'Autre')], "Type", default='invitation', row="kind")
    status = fields.Selection([('queued', 'En attente', 'muted'), ('sent', 'Envoyé', 'info'), ('opened', 'Ouvert', 'primary'),
                               ('clicked', 'Cliqué', 'success'), ('bounced', 'Rejeté', 'warning'), ('failed', 'Échec', 'danger')],
                              "Statut", default='queued', row="kind")
    sent_at = fields.Datetime("Envoyé le", row="dates")
    opened_at = fields.Datetime("Ouvert le", row="dates")
    clicked_at = fields.Datetime("Cliqué le", row="dates")
    message_id = fields.Char("Message-ID", readonly=True, sidebar=True)
    error = fields.Text("Erreur", readonly=True, sidebar=True)
