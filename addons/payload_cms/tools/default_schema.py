# -*- coding: utf-8 -*-
"""Default collections & globals, modeled after Payload's website template.

The structure is the same as a Payload config (``CollectionConfig`` /
``GlobalConfig``) so it can be edited like a ``payload.config.ts``.
"""

LINK_FIELDS = [
    {'type': 'row', 'fields': [
        {'name': 'label', 'type': 'text', 'required': True, 'admin': {'width': '50%'}},
        {'name': 'url', 'type': 'text', 'label': 'URL', 'required': True, 'admin': {'width': '50%'}},
    ]},
    {'name': 'newTab', 'type': 'checkbox', 'label': 'Open in new tab'},
]

DEFAULT_SCHEMA = [
    {
        'slug': 'media',
        'sequence': 30,
        'labels': {'singular': 'Media', 'plural': 'Media'},
        'admin': {'useAsTitle': 'filename', 'defaultColumns': ['filename', 'alt', 'updatedAt']},
        'upload': {'mimeTypes': ['image/*', 'application/pdf', 'video/*'],
                   'imageSizes': [
                       {'name': 'thumbnail', 'width': 300},
                       {'name': 'square', 'width': 500, 'height': 500},
                       {'name': 'small', 'width': 600},
                       {'name': 'medium', 'width': 900},
                       {'name': 'large', 'width': 1400},
                       {'name': 'og', 'width': 1200, 'height': 630},
                   ]},
        'fields': [
            {'name': 'alt', 'type': 'text', 'label': 'Alt'},
            {'name': 'caption', 'type': 'richText'},
        ],
    },
    {
        'slug': 'categories',
        'sequence': 40,
        'labels': {'singular': 'Category', 'plural': 'Categories'},
        'admin': {'useAsTitle': 'title', 'defaultColumns': ['title', 'slug', 'updatedAt']},
        'fields': [
            {'name': 'title', 'type': 'text', 'required': True},
            {'name': 'slug', 'type': 'slug', 'useAsSlug': 'title', 'admin': {'position': 'sidebar'}},
        ],
    },
    {
        'slug': 'pages',
        'sequence': 10,
        'labels': {'singular': 'Page', 'plural': 'Pages'},
        'admin': {
            'useAsTitle': 'title',
            'defaultColumns': ['title', 'slug', 'updatedAt', '_status'],
            'livePreview': {'url': ''},
        },
        'versions': {'drafts': {'autosave': True}},
        'fields': [
            {'name': 'title', 'type': 'text', 'required': True},
            {'type': 'tabs', 'tabs': [
                {'label': 'Hero', 'fields': [
                    {'name': 'hero', 'type': 'group', 'label': False, 'fields': [
                        {'name': 'type', 'type': 'select', 'defaultValue': 'lowImpact', 'required': True,
                         'options': [{'value': 'none', 'label': 'None'},
                                     {'value': 'highImpact', 'label': 'High Impact'},
                                     {'value': 'mediumImpact', 'label': 'Medium Impact'},
                                     {'value': 'lowImpact', 'label': 'Low Impact'}]},
                        {'name': 'richText', 'type': 'richText', 'label': 'Rich Text'},
                        {'name': 'links', 'type': 'array', 'maxRows': 2, 'fields': LINK_FIELDS},
                        {'name': 'media', 'type': 'upload', 'relationTo': 'media'},
                    ]},
                ]},
                {'label': 'Content', 'fields': [
                    {'name': 'layout', 'type': 'blocks', 'required': True, 'blocks': [
                        {'slug': 'content', 'labels': {'singular': 'Content'}, 'fields': [
                            {'name': 'richText', 'type': 'richText', 'label': 'Rich Text'},
                        ]},
                        {'slug': 'mediaBlock', 'labels': {'singular': 'Media Block'}, 'fields': [
                            {'name': 'media', 'type': 'upload', 'relationTo': 'media', 'required': True},
                        ]},
                        {'slug': 'cta', 'labels': {'singular': 'Call to Action'}, 'fields': [
                            {'name': 'richText', 'type': 'richText', 'label': 'Rich Text'},
                            {'name': 'links', 'type': 'array', 'maxRows': 2, 'fields': LINK_FIELDS},
                        ]},
                        {'slug': 'archive', 'labels': {'singular': 'Archive'}, 'fields': [
                            {'name': 'introContent', 'type': 'richText', 'label': 'Intro Content'},
                            {'name': 'categories', 'type': 'relationship', 'relationTo': 'categories', 'hasMany': True},
                            {'name': 'limit', 'type': 'number', 'defaultValue': 10},
                        ]},
                    ]},
                ]},
                {'name': 'meta', 'label': 'SEO', 'fields': [
                    {'name': 'title', 'type': 'text'},
                    {'name': 'image', 'type': 'upload', 'relationTo': 'media'},
                    {'name': 'description', 'type': 'textarea'},
                ]},
            ]},
            {'name': 'publishedAt', 'type': 'date', 'label': 'Published At', 'admin': {'position': 'sidebar'}},
            {'name': 'slug', 'type': 'slug', 'useAsSlug': 'title', 'admin': {'position': 'sidebar'}},
        ],
    },
    {
        'slug': 'posts',
        'sequence': 20,
        'labels': {'singular': 'Post', 'plural': 'Posts'},
        'admin': {
            'useAsTitle': 'title',
            'defaultColumns': ['title', 'slug', 'updatedAt', '_status'],
            'livePreview': {'url': ''},
        },
        'versions': {'drafts': {'autosave': True}},
        'fields': [
            {'name': 'title', 'type': 'text', 'required': True},
            {'type': 'tabs', 'tabs': [
                {'label': 'Content', 'fields': [
                    {'name': 'heroImage', 'type': 'upload', 'relationTo': 'media'},
                    {'name': 'content', 'type': 'richText', 'required': True},
                ]},
                {'label': 'Meta', 'fields': [
                    {'name': 'relatedPosts', 'type': 'relationship', 'relationTo': 'posts', 'hasMany': True,
                     'admin': {'position': 'sidebar'}},
                    {'name': 'categories', 'type': 'relationship', 'relationTo': 'categories', 'hasMany': True,
                     'admin': {'position': 'sidebar'}},
                ]},
                {'name': 'meta', 'label': 'SEO', 'fields': [
                    {'name': 'title', 'type': 'text'},
                    {'name': 'image', 'type': 'upload', 'relationTo': 'media'},
                    {'name': 'description', 'type': 'textarea'},
                ]},
            ]},
            {'name': 'publishedAt', 'type': 'date', 'label': 'Published At', 'admin': {'position': 'sidebar'}},
            {'name': 'slug', 'type': 'slug', 'useAsSlug': 'title', 'admin': {'position': 'sidebar'}},
        ],
    },
    {
        'kind': 'global',
        'slug': 'header',
        'label': 'Header',
        'sequence': 10,
        'fields': [
            {'name': 'navItems', 'type': 'array', 'label': 'Nav Items', 'maxRows': 6, 'fields': LINK_FIELDS},
        ],
    },
    {
        'kind': 'global',
        'slug': 'footer',
        'label': 'Footer',
        'sequence': 20,
        'fields': [
            {'name': 'navItems', 'type': 'array', 'label': 'Nav Items', 'maxRows': 6, 'fields': LINK_FIELDS},
            {'name': 'copyright', 'type': 'text'},
        ],
    },
]
