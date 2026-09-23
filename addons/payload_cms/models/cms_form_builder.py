# -*- coding: utf-8 -*-
"""Form builder hooks (``form-submissions`` collection).

This is also an example of how to add server-side hooks to a collection
(Payload's ``beforeChange`` / ``afterChange``): inherit ``cms.document`` and
override ``_payload_create`` / ``_payload_update`` for your slug.
"""
import html
import logging
import re

from odoo import api, models

from ..tools import schema
from ..tools.lexical_html import is_lexical, lexical_to_html
from .cms_document import PayloadValidationError

_logger = logging.getLogger(__name__)

SUBMISSIONS = 'form-submissions'
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
VAR_RE = re.compile(r'\{\{\s*([^}\s]+)\s*\}\}')


class CmsDocument(models.Model):
    _inherit = 'cms.document'

    @api.model
    def _payload_create(self, collection, data, draft=False, upload=None):
        if collection.slug != SUBMISSIONS:
            return super()._payload_create(collection, data, draft=draft, upload=upload)
        form = self._form_for_submission(data or {})
        submission = super()._payload_create(collection, data, draft=draft, upload=upload)
        try:
            submission._send_form_emails(form)
        except Exception:  # noqa: BLE001 - never lose a submission because of an email
            _logger.exception("Payload CMS: cannot queue the form emails of submission %s", submission.id)
        return submission

    # ------------------------------------------------------------------
    def _form_data(self, form):
        """Form definition in the current locale (published version for visitors)."""
        data = form.published_data or form.data or {}
        loc = self._locale()
        if loc:
            data = schema.flatten_locale(self._fields_config(form.collection_id), data, loc)
        return data

    @api.model
    def _form_for_submission(self, data):
        """Validate a submission against its form (beforeChange hook)."""
        form_id = data.get('form')
        if isinstance(form_id, dict):
            form_id = form_id.get('id') or form_id.get('value')
        forms = self.env['cms.collection']._get_by_slug('forms')
        form = self.sudo().browse(int(form_id)).exists() if str(form_id or '').isdigit() else self.browse()
        if not form or form.collection_id != forms:
            raise PayloadValidationError([{'path': 'form', 'message': 'This field is required.', 'label': 'Form'}],
                                         SUBMISSIONS)
        definition = self._form_data(form)
        values = {}
        for row in data.get('submissionData') or []:
            if isinstance(row, dict) and row.get('field'):
                values[str(row['field'])] = row.get('value')
        errors = []
        for index, block in enumerate(definition.get('fields') or []):
            if not isinstance(block, dict) or block.get('blockType') == 'message' or not block.get('name'):
                continue
            value = values.get(block['name'])
            empty = value in (None, '', False, 'false')
            label = block.get('label') or block['name']
            if block.get('required') and empty:
                errors.append({'path': 'submissionData.%s' % block['name'], 'label': label,
                               'message': 'This field is required.'})
            elif block.get('blockType') == 'email' and not empty and not EMAIL_RE.match(str(value)):
                errors.append({'path': 'submissionData.%s' % block['name'], 'label': label,
                               'message': 'Please enter a valid email address.'})
        if errors:
            raise PayloadValidationError(errors, SUBMISSIONS)
        # values are always stored as text, like the plugin does
        data['submissionData'] = [{'field': k, 'value': '' if v is None else str(v)} for k, v in values.items()]
        data['form'] = form.id
        return form

    # ------------------------------------------------------------------
    def _send_form_emails(self, form):
        """afterChange hook: queue the emails configured on the form."""
        self.ensure_one()
        definition = self._form_data(form)
        rows = (self.data or {}).get('submissionData') or []
        values = {r['field']: r.get('value') for r in rows if isinstance(r, dict) and r.get('field')}

        def fill(text, as_html=False):
            if not text:
                return text

            def replace(match):
                key = match.group(1)
                if key == '*':
                    return ('<br/>' if as_html else '\n').join(
                        '%s : %s' % (html.escape(k) if as_html else k, html.escape(v or '') if as_html else v or '')
                        for k, v in values.items())
                if key == '*:table':
                    return '<table border="1" cellpadding="4" style="border-collapse:collapse">%s</table>' % ''.join(
                        '<tr><td><b>%s</b></td><td>%s</td></tr>' % (html.escape(k), html.escape(v or ''))
                        for k, v in values.items())
                value = values.get(key, '')
                return html.escape(value or '') if as_html else (value or '')
            return VAR_RE.sub(replace, text)

        Mail = self.env['mail.mail'].sudo()
        default_from = self._form_default_from()
        mails = Mail
        for email in definition.get('emails') or []:
            if not isinstance(email, dict) or not email.get('emailTo'):
                continue
            message = email.get('message')
            body = lexical_to_html(message) if is_lexical(message) else (message or '')
            vals = {
                'email_from': fill(email.get('emailFrom')) or default_from,
                'email_to': fill(email.get('emailTo')),
                'email_cc': fill(email.get('cc')) or False,
                'reply_to': fill(email.get('replyTo')) or False,
                'subject': fill(email.get('subject')) or "You've received a new message.",
                'body_html': fill(body, as_html=True) or fill('{{*:table}}', as_html=True),
                'auto_delete': True,
            }
            bcc = fill(email.get('bcc'))
            if bcc and 'email_bcc' in Mail._fields:
                vals['email_bcc'] = bcc
            mails |= Mail.create(vals)
            if bcc and 'email_bcc' not in Mail._fields:
                # blind copy: a separate email, so recipients never see each other
                mails |= Mail.create(dict(vals, email_to=bcc, email_cc=False))
        return mails

    def _form_default_from(self):
        server = self.env['ir.mail_server'].sudo()
        address = getattr(server, '_get_default_from_address', lambda: None)()
        return address or self.env.company.email_formatted or 'noreply@localhost'
