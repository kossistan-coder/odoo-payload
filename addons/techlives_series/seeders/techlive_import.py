# -*- coding: utf-8 -*-
"""Import des données de l'ancienne application Tech Lives Series (MongoDB ``techLive``).

Les collections Mongo sont exportées en JSON dans ``data/techlive/`` (et les
images utilisées dans ``data/techlive/upload/``)::

    for c in socials organizers speakers users events episodes messages cms; do
        mongoexport --uri=mongodb://localhost:27017/techLive -c $c --jsonArray -o data/techlive/$c.json
    done

Correspondance :

=================  ====================  =========================================
Mongo              Payload               Relations
=================  ====================  =========================================
socials            socials
organizers         organizers            logo -> media
speakers           speakers              profile -> media, social_links.platform -> socials, events
users              participants          events
events             events                couverture / hero / mobile -> media, speakers,
                                         moderators, participants, episode
episodes           episodes              event
messages           messages
cms                page « home »         blocs live-hero, about, episodes-list,
                                         speakers-carousel, organizers-logos, community-cta
=================  ====================  =========================================

Les comptes d'administration, rôles, permissions et journaux (admins, roles,
permissions, logs) sont gérés par Odoo et ne sont pas importés.

L'import est idempotent : chaque document est retrouvé par une clé naturelle
(email, nom, désignation...) et mis à jour, jamais dupliqué.
"""
import json
import logging
import os

from odoo.addons.payload_cms.payload import Seeder
from odoo.addons.payload_cms.tools.schema import slugify

_logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'techlive')


def _load(name):
    path = os.path.join(DATA_DIR, '%s.json' % name)
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _oid(value):
    """Extended JSON ``{"$oid": "..."}`` -> ``"..."``."""
    return value.get('$oid') if isinstance(value, dict) else value


def _day(value):
    """Extended JSON ``{"$date": "2026-02-23T17:01:28.609Z"}`` -> date of a dayOnly field."""
    value = value.get('$date') if isinstance(value, dict) else value
    return '%sT12:00:00.000Z' % value[:10] if value else None


def _text(value):
    return (value or '').strip()


class TechLiveImport(Seeder):
    """Données de la base MongoDB ``techLive`` (ancienne application Node.js)."""
    _name = 'techlive_import'
    _description = "Import de l'ancienne base Tech Lives Series (MongoDB)"
    _sequence = 200  # après la page d'accueil (HomePage), dont il remplit les blocs

    def run(self, env):
        self.env = env
        self.ids = {}        # Mongo ObjectId -> id du document Payload
        self.media = {}      # nom de fichier -> id du média
        self._socials()
        self._organizers()
        self._speakers()
        self._participants()
        self._events()
        self._episodes()
        self._relations()
        self._messages()
        self._home_page()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ids(self, values):
        return [self.ids[_oid(v)] for v in values or [] if _oid(v) in self.ids]

    def _save(self, slug, key, where, data):
        doc = self.upsert(self.env, slug, where, data)
        self.ids[key] = doc.id
        return doc

    def _media(self, filename, alt=None):
        """Média (collection upload ``media``) créé une seule fois par fichier."""
        if not filename:
            return None
        if filename in self.media:
            return self.media[filename]
        path = os.path.join(DATA_DIR, 'upload', filename)
        if not os.path.exists(path):
            _logger.warning("Tech Lives import: missing file %s", filename)
            return None
        Document = self.env['cms.document'].sudo()
        collection = self.collection(self.env, 'media')
        # nom normalisé par payload_cms à l'upload (« DT Agbagla.png » -> « dt-agbagla.png »)
        stem, ext = os.path.splitext(filename)
        stored = (slugify(stem) or 'file') + ext.lower()
        existing = Document.search([('collection_id', '=', collection.id), ('filename', '=', stored)], limit=1)
        if not existing:
            with open(path, 'rb') as f:
                existing = Document._payload_create(collection, {'alt': alt or os.path.splitext(filename)[0]},
                                                    upload=(filename, f.read(), None))
        self.media[filename] = existing.id
        return existing.id

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------
    def _socials(self):
        Document = self.env['cms.document'].sudo()
        collection = self.collection(self.env, 'socials')
        existing = {(d.data or {}).get('name', '').lower(): d for d in Document.search([('collection_id', '=', collection.id)])}
        for index, row in enumerate(_load('socials'), start=1):
            name = _text(row.get('designation'))
            data = {'name': name, 'active': row.get('active', True)}
            doc = existing.get(name.lower())
            if doc:
                # réseau déjà saisi (ex. « Linkedin ») : on garde son nom et son icône
                doc._payload_update({'active': data['active']})
            else:
                doc = self.create(self.env, 'socials', dict(data, sequence=index * 10))
            self.ids[_oid(row['_id'])] = doc.id

    def _organizers(self):
        for index, row in enumerate(_load('organizers'), start=1):
            name = _text(row.get('designation'))
            self._save('organizers', _oid(row['_id']), {'name': {'equals': name}}, {
                'name': name,
                'logo': self._media(row.get('image'), name),
                'website': row.get('url') or None,
                'type': 'organizer',
                'sequence': index * 10,
                'active': row.get('active', True),
            })

    def _speakers(self):
        for row in _load('speakers'):
            email = _text(row.get('email')).lower()
            links = [{'platform': self.ids[_oid(link.get('platform'))], 'url': link['url']}
                     for link in row.get('socialLinks') or [] if _oid(link.get('platform')) in self.ids and link.get('url')]
            self._save('speakers', _oid(row['_id']), {'email': {'equals': email}}, {
                'nom': _text(row.get('nom')),
                'prenom': _text(row.get('prenom')),
                'function': row.get('function') or None,
                'bio': row.get('bio') or None,
                'email': email,
                'pseudo': row.get('pseudo') or None,
                'profile': self._media(row.get('profile'), '%s %s' % (row.get('prenom') or '', row.get('nom') or '')),
                'social_links': links,
                'active': row.get('active', True),
                'hidespeaker': bool(row.get('hidespeaker')),
            })

    def _participants(self):
        for row in _load('users'):
            email = _text(row.get('email')).lower()
            if not email:
                continue
            self._save('participants', _oid(row['_id']), {'email': {'equals': email}}, {
                'nom': _text(row.get('nom')),
                'prenom': _text(row.get('prenom')),
                'email': email,
            })

    def _events(self):
        for row in _load('events'):
            designation = _text(row.get('designation'))
            description = _text(row.get('description'))
            self._save('events', _oid(row['_id']), {'designation': {'equals': designation}}, {
                'designation': designation,
                'description': '<p>%s</p>' % description if description else None,
                'date_sortie': _day(row.get('date_sortie')),
                'time': row.get('time'),
                'couverture': self._media(row.get('couverture'), designation),
                'hero_image': self._media(row.get('heroImage'), designation),
                'mobile_image': self._media(row.get('mobileImage'), designation),
                'speakers': self._ids(row.get('speakers')),
                'moderators': self._ids(row.get('moderators')),
                'participants': self._ids(row.get('participants')),
                'active': row.get('active', True),
            })

    def _episodes(self):
        for row in _load('episodes'):
            event = self.ids.get(_oid(row.get('event')))
            if not event:
                continue
            self._save('episodes', _oid(row['_id']), {'event': {'equals': event}}, {
                'event': event,
                'link': row.get('link'),
            })

    def _relations(self):
        """Relations croisées, une fois tous les documents créés."""
        Document = self.env['cms.document'].sudo()
        for row in _load('events'):
            doc = Document.browse(self.ids.get(_oid(row['_id'])))
            episode = self.ids.get(_oid(row.get('episode')))
            if doc and episode:
                doc._payload_update({'episode': episode, '_status': 'published'})
        for name in ('speakers', 'users'):
            for row in _load(name):
                doc = Document.browse(self.ids.get(_oid(row['_id'])))
                if doc and row.get('events'):
                    doc._payload_update({'events': self._ids(row['events'])})

    def _messages(self):
        for row in _load('messages'):
            email = _text(row.get('email')).lower()
            subject = _text(row.get('objet'))
            if self.exists(self.env, 'messages', {'and': [{'email': {'equals': email}}, {'subject': {'equals': subject}}]}):
                continue
            self.create(self.env, 'messages', {
                'name': ('%s %s' % (_text(row.get('prenom')), _text(row.get('nom')))).strip(),
                'email': email,
                'subject': subject,
                'message': row.get('message'),
                'status': 'answered' if row.get('answered') else 'new',
            })

    # ------------------------------------------------------------------
    # Page d'accueil (collection Mongo « cms »)
    # ------------------------------------------------------------------
    def _home_page(self):
        cms = (_load('cms') or [None])[0]
        page = self.find(self.env, 'pages', {'slug': {'equals': 'home'}})
        if not cms or not page:
            return
        about = cms.get('proposBanner') or {}
        episodes = cms.get('episodeTextBanner') or {}
        speakers = cms.get('speakerTextBanner') or {}
        organizers = cms.get('organizerTextBanner') or {}
        community = cms.get('communityTextBanner') or {}
        values = {
            'live-hero': {'live': self.ids.get(_oid(cms.get('banner')))},
            'about': {
                'title': (about.get('text') or {}).get('title'),
                'text': '<p>%s</p>' % (about.get('text') or {}).get('description') if (about.get('text') or {}).get('description') else None,
                'image': self._media(about.get('image'), (about.get('text') or {}).get('title')),
            },
            'episodes-list': {'title': episodes.get('title'), 'subtitle': episodes.get('description'),
                              'mode': 'manual', 'events': self._ids(cms.get('recentsEvent'))},
            'speakers-carousel': {'title': speakers.get('title'), 'subtitle': speakers.get('description'),
                                  'mode': 'manual', 'speakers': self._ids(cms.get('speakers'))},
            'organizers-logos': {'title': organizers.get('title'), 'subtitle': organizers.get('description')},
            'community-cta': {'title': community.get('title'), 'text': community.get('description')},
        }
        layout = []
        for row in (page.data or {}).get('layout') or []:
            update = {k: v for k, v in (values.get(row.get('blockType')) or {}).items() if v not in (None, [], '')}
            layout.append(dict(row, **update))
        page._payload_update({'layout': layout, '_status': 'published'})
