# -*- coding: utf-8 -*-
"""Port of Payload's official form builder plugin (@payloadcms/plugin-form-builder).

Two collections, with the same shape as the plugin:

* ``forms``: the form definition (fields as blocks, confirmation, emails);
* ``form-submissions``: what visitors submit (``POST /api/form-submissions``
  is public), validated against the form, then notification emails are sent.
"""

_NAME = {'name': 'name', 'type': 'text', 'label': 'Name (lowercase, no special characters)', 'required': True,
         'admin': {'width': '50%'}}
_LABEL = {'name': 'label', 'type': 'text', 'label': 'Label', 'localized': True, 'admin': {'width': '50%'}}
_WIDTH = {'name': 'width', 'type': 'number', 'label': 'Field Width (percentage)', 'admin': {'width': '50%'}}
_REQUIRED = {'name': 'required', 'type': 'checkbox', 'label': 'Required'}


def _block(slug, singular, extra_row=None, extra=None):
    second_row = [_WIDTH] + (extra_row or [])
    return {
        'slug': slug,
        'labels': {'singular': singular, 'plural': singular + ' Fields'},
        'fields': [
            {'type': 'row', 'fields': [_NAME, _LABEL]},
            {'type': 'row', 'fields': second_row},
            *(extra or []),
            _REQUIRED,
        ],
    }


def _default(ftype='text', localized=True):
    return {'name': 'defaultValue', 'type': ftype, 'label': 'Default Value', 'localized': localized,
            'admin': {'width': '50%'}}


FORM_BLOCKS = [
    _block('text', 'Text', [_default()]),
    _block('textarea', 'Text Area', [_default()]),
    _block('select', 'Select', [_default()], extra=[
        {'name': 'placeholder', 'type': 'text', 'label': 'Placeholder'},
        {'name': 'options', 'type': 'array', 'label': 'Select Attribute Options',
         'labels': {'singular': 'Option', 'plural': 'Options'},
         'fields': [{'type': 'row', 'fields': [
             {'name': 'label', 'type': 'text', 'label': 'Label', 'required': True, 'localized': True,
              'admin': {'width': '50%'}},
             {'name': 'value', 'type': 'text', 'label': 'Value', 'required': True, 'admin': {'width': '50%'}},
         ]}]},
    ]),
    _block('email', 'Email'),
    _block('state', 'State'),
    _block('country', 'Country'),
    _block('checkbox', 'Checkbox', [_default('checkbox', localized=False)]),
    _block('number', 'Number', [_default('number', localized=False)]),
    {
        'slug': 'message',
        'labels': {'singular': 'Message', 'plural': 'Message Blocks'},
        'fields': [{'name': 'message', 'type': 'richText', 'label': 'Message', 'localized': True}],
    },
]

FORM_BUILDER_SCHEMA = [
    {
        'slug': 'forms',
        'labels': {'singular': 'Form', 'plural': 'Forms'},
        'admin': {'useAsTitle': 'title', 'defaultColumns': ['title', 'updatedAt'], 'group': 'Form Builder'},
        'versions': {'maxPerDoc': 20},
        'publicRead': True,
        'fields': [
            {'name': 'title', 'type': 'text', 'label': 'Title', 'required': True, 'localized': True},
            {'name': 'fields', 'type': 'blocks', 'label': 'Fields', 'blocks': FORM_BLOCKS},
            {'name': 'submitButtonLabel', 'type': 'text', 'label': 'Submit Button Label', 'localized': True},
            {'name': 'confirmationType', 'type': 'radio', 'label': 'Confirmation Type', 'defaultValue': 'message',
             'options': [{'label': 'Message', 'value': 'message'}, {'label': 'Redirect', 'value': 'redirect'}],
             'admin': {'description': 'Choose whether to display an on-page message or redirect to a different '
                                      'page after they submit the form.', 'layout': 'horizontal'}},
            {'name': 'confirmationMessage', 'type': 'richText', 'label': 'Confirmation Message', 'localized': True,
             'admin': {'condition': {'field': 'confirmationType', 'equals': 'message'}}},
            {'name': 'redirect', 'type': 'group', 'label': 'Redirect',
             'admin': {'condition': {'field': 'confirmationType', 'equals': 'redirect'}},
             'fields': [{'name': 'url', 'type': 'text', 'label': 'URL to redirect to'}]},
            {'name': 'emails', 'type': 'array', 'label': 'Emails', 'private': True,
             'labels': {'singular': 'Email', 'plural': 'Emails'},
             'admin': {'description': "Send custom emails when the form submits. Use comma separated lists to "
                                      "send the same email to multiple recipients. To reference a value from this "
                                      "form, wrap that field's name with double curly brackets, i.e. {{firstName}}. "
                                      "You can use a wildcard {{*}} to output all data and {{*:table}} to format it "
                                      "as an HTML table in the email."},
             'fields': [
                 {'type': 'row', 'fields': [
                     {'name': 'emailTo', 'type': 'text', 'label': 'Email To', 'admin': {'width': '100%', 'placeholder': '"Email Sender" <sender@email.com>'}},
                     {'name': 'cc', 'type': 'text', 'label': 'CC', 'admin': {'width': '50%'}},
                     {'name': 'bcc', 'type': 'text', 'label': 'BCC', 'admin': {'width': '50%'}},
                 ]},
                 {'type': 'row', 'fields': [
                     {'name': 'replyTo', 'type': 'text', 'label': 'Reply To', 'admin': {'width': '50%', 'placeholder': '"Reply To" <reply-to@email.com>'}},
                     {'name': 'emailFrom', 'type': 'text', 'label': 'Email From', 'admin': {'width': '50%', 'placeholder': '"Email From" <email-from@email.com>'}},
                 ]},
                 {'name': 'subject', 'type': 'text', 'label': 'Subject', 'required': True, 'localized': True,
                  'defaultValue': "You've received a new message."},
                 {'name': 'message', 'type': 'richText', 'label': 'Message', 'localized': True,
                  'admin': {'description': 'Enter the message that should be sent in this email.'}},
             ]},
        ],
    },
    {
        'slug': 'form-submissions',
        'labels': {'singular': 'Form Submission', 'plural': 'Form Submissions'},
        'admin': {'useAsTitle': 'id', 'defaultColumns': ['id', 'form', 'createdAt'], 'group': 'Form Builder'},
        'versions': False,
        'publicRead': False,
        'publicCreate': True,
        'fields': [
            {'name': 'form', 'type': 'relationship', 'relationTo': 'forms', 'label': 'Form', 'required': True,
             'admin': {'readOnly': True}},
            {'name': 'submissionData', 'type': 'array', 'label': 'Submission Data',
             'admin': {'readOnly': True},
             'fields': [
                 {'name': 'field', 'type': 'text', 'label': 'Field', 'required': True, 'admin': {'width': '50%'}},
                 {'name': 'value', 'type': 'text', 'label': 'Value', 'required': True, 'admin': {'width': '50%'}},
             ]},
        ],
    },
]
