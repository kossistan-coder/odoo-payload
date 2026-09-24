# -*- coding: utf-8 -*-
"""Seeders: starter content of a module, kept apart from its models.

A module puts its seeders in a ``seeders/`` package (imported by its
``__init__.py``)::

    # mon_module/seeders/home_page.py
    from odoo.addons.payload_cms.payload import Seeder

    class HomePage(Seeder):
        _name = 'home_page'
        _description = "Page d'accueil"

        def run(self, env):
            if self.exists(env, 'pages', {'slug': {'equals': 'home'}}):
                return
            self.create(env, 'pages', {'title': 'Accueil', 'slug': 'home', ...})

Seeders only CREATE or UPDATE: while a seeder runs, deleting CMS data
(documents, versions, collections, fields) raises an error and the seeder is
rolled back, so a seeder can never empty or break the database.

Each seeder runs once per database, after the code-first collections are
synchronised (module install / update / server start). The execution is
recorded in the ``payload_cms.seeder.<module>.<name>`` system parameter; run
them again with ``env['cms.collection']._payload_run_seeders(force=True)``.
"""

_seeders = {}


def registered_seeders():
    return list(_seeders.values())


class Seeder:
    _name = None
    _description = None
    _sequence = 100  # execution order

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__dict__.get('_name'):
            cls._module = cls.__module__.split('.')[2] if cls.__module__.startswith('odoo.addons.') else cls.__module__
            _seeders[(cls._module, cls._name)] = cls

    @classmethod
    def _key(cls):
        return 'payload_cms.seeder.%s.%s' % (cls._module, cls._name)

    def run(self, env):
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def collection(env, slug, kind='collection'):
        return env['cms.collection'].sudo()._get_by_slug(slug, kind)

    def find(self, env, slug, where):
        """First document of ``slug`` matching the Payload ``where`` query
        (localized values are matched in every locale), or an empty recordset."""
        Document = env['cms.document'].sudo()
        collection = self.collection(env, slug)
        if not collection:
            return Document
        docs, _meta = Document._payload_search(collection, where=where, limit=1, draft=True)
        if docs:
            return docs[:1]
        # localized fields store {"en": ..., "fr": ...}: compare every locale
        for field, condition in (where or {}).items():
            expected = (condition or {}).get('equals') if isinstance(condition, dict) else condition
            for doc in Document.search([('collection_id', '=', collection.id)]):
                value = (doc.data or {}).get(field)
                if value == expected or (isinstance(value, dict) and expected in value.values()):
                    return doc
        return Document

    def exists(self, env, slug, where):
        return bool(self.find(env, slug, where))

    def add_blocks(self, doc, field, rows, skip_existing=True):
        """Append block rows to the ``field`` (blocks) of a document, keeping
        its existing rows untouched. ``skip_existing``: a block type already
        present is not added again. Returns the number of rows added."""
        from ..tools import schema
        collection = doc.collection_id
        blocks_field = schema.find_field(doc._fields_config(collection), field)
        definitions = {b['slug']: b for b in (blocks_field or {}).get('blocks') or []}
        data = dict(doc.data or {})
        existing = list(data.get(field) or [])
        present = {r.get('blockType') for r in existing if isinstance(r, dict)}
        added = []
        for row in rows:
            block_type = row.get('blockType')
            if block_type not in definitions or (skip_existing and block_type in present):
                continue
            clean = schema.sanitize(definitions[block_type].get('fields') or [], row)
            clean = schema.apply_defaults(definitions[block_type].get('fields') or [], clean)
            added.append(dict(clean, id=schema.new_row_id(), blockType=block_type))
            present.add(block_type)
        if not added:
            return 0
        data[field] = existing + added
        vals = {'data': data}
        if doc.status == 'published':
            vals['published_data'] = data
        doc.write(vals)
        doc._create_version(collection, doc.status, autosave=False)
        return len(added)

    def create(self, env, slug, data, publish=True):
        """Create a document (``publish=False``: draft)."""
        collection = self.collection(env, slug)
        data = dict(data, _status='published' if publish else 'draft')
        return env['cms.document'].sudo()._payload_create(collection, data, draft=not publish)

    def upsert(self, env, slug, where, data, publish=True):
        """Update the first document matching ``where`` (a Payload query), or
        create it. Existing documents are only updated, never deleted."""
        collection = self.collection(env, slug)
        docs, _meta = env['cms.document'].sudo()._payload_search(collection, where=where, limit=1, draft=True)
        if docs:
            payload = dict(data, _status='published' if publish else 'draft')
            return docs[0]._payload_update(payload, draft=not publish)
        return self.create(env, slug, data, publish=publish)

    def update_global(self, env, slug, data, publish=True):
        """Write the document of a global."""
        collection = self.collection(env, slug, kind='global')
        Document = env['cms.document'].sudo()
        doc = Document.search([('collection_id', '=', collection.id)], limit=1)
        data = dict(data, _status='published' if publish else 'draft')
        if doc:
            return doc._payload_update(data, draft=not publish)
        return Document._payload_create(collection, data, draft=not publish)
