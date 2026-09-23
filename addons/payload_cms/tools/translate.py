# -*- coding: utf-8 -*-
"""Machine translation of localized fields.

Providers: Google Cloud Translation API v2 (API key), LibreTranslate (open
source, URL + optional key) and MyMemory (free, no key).

Only localized fields are translated: text / textarea values as plain text,
rich text as HTML (Lexical -> HTML -> Google -> Lexical, so formatting,
links and uploads are preserved). Localized groups, arrays and blocks are
translated leaf by leaf.
"""
import copy
import logging
import re

import requests

from .lexical_html import html_to_lexical, is_lexical, lexical_to_html
from .schema import data_fields, is_locale_dict

_logger = logging.getLogger(__name__)

GOOGLE_URL = 'https://translation.googleapis.com/language/translate/v2'
MYMEMORY_URL = 'https://api.mymemory.translated.net/get'
MYMEMORY_MAX_BYTES = 480  # MyMemory accepts up to 500 bytes per query
# values never sent to the translator (URLs, emails, anchors, paths)
UNTRANSLATABLE_RE = re.compile(r'^\s*(https?://|mailto:|tel:|/|#|www\.)\S*\s*$|^\s*[^@\s]+@[^@\s]+\.[^@\s]+\s*$', re.I)
UNTRANSLATABLE_NAMES = {'url', 'href', 'link', 'email', 'path', 'domain', 'code', 'anchor'}
MAX_SEGMENTS = 100
MAX_CHARS = 25000


class TranslationError(Exception):
    pass


def google_translator(api_key, timeout=20):
    """Return ``translate(texts, source, target, fmt) -> [texts]``."""
    def translate(texts, source, target, fmt='text'):
        results = []
        batch, size = [], 0
        batches = []
        for text in texts:
            if batch and (len(batch) >= MAX_SEGMENTS or size + len(text) > MAX_CHARS):
                batches.append(batch)
                batch, size = [], 0
            batch.append(text)
            size += len(text)
        if batch:
            batches.append(batch)
        for chunk in batches:
            try:
                response = requests.post(GOOGLE_URL, params={'key': api_key}, json={
                    'q': chunk, 'source': source, 'target': target, 'format': fmt,
                }, timeout=timeout)
            except requests.RequestException as e:
                raise TranslationError('Google Translate is unreachable: %s' % e)
            if response.status_code != 200:
                try:
                    message = response.json()['error']['message']
                except Exception:  # noqa: BLE001
                    message = response.text[:200]
                raise TranslationError('Google Translate error (%s): %s' % (response.status_code, message))
            results += [t['translatedText'] for t in response.json()['data']['translations']]
        return results
    return translate


def _chunks(text, limit):
    """Split a text in pieces of at most ``limit`` UTF-8 bytes, on sentence/word boundaries."""
    import re
    pieces, current = [], ''
    for part in re.split(r'(?<=[.!?\n])\s+|(?<=,)\s+', text):
        candidate = (current + ' ' + part) if current else part
        if len(candidate.encode()) <= limit:
            current = candidate
            continue
        if current:
            pieces.append(current)
        while len(part.encode()) > limit:
            cut = part[:limit // 2].rsplit(' ', 1)[0] or part[:limit // 2]
            pieces.append(cut)
            part = part[len(cut):].lstrip()
        current = part
    if current:
        pieces.append(current)
    return pieces


def mymemory_translator(email=None, timeout=20):
    """MyMemory (free, no key; an email raises the daily quota). Plain text only."""
    def translate_one(text, source, target, fmt='text'):
        if fmt == 'html':
            # one block of rich text (inline tags are kept by MyMemory), caller keeps it short
            return request(text, source, target)
        core = text.strip()
        if not core:
            return text
        lead, trail = text[:len(text) - len(text.lstrip())], text[len(text.rstrip()):]
        out = [html_unescape(request(chunk, source, target)) for chunk in _chunks(core, MYMEMORY_MAX_BYTES)]
        return lead + ' '.join(out) + trail

    def request(text, source, target):
        params = {'q': text, 'langpair': '%s|%s' % (source, target)}
        if email:
            params['de'] = email
        try:
            response = requests.get(MYMEMORY_URL, params=params, timeout=timeout)
            payload = response.json()
        except (requests.RequestException, ValueError) as e:
            raise TranslationError('MyMemory is unreachable: %s' % e)
        status = int(payload.get('responseStatus') or response.status_code or 0)
        translated = (payload.get('responseData') or {}).get('translatedText')
        if status != 200 or not translated or payload.get('quotaFinished'):
            raise TranslationError('MyMemory error (%s): %s' % (status, translated or payload.get('responseDetails') or 'quota reached'))
        return translated

    def translate(texts, source, target, fmt='text'):
        return [translate_one(t, source, target, fmt) for t in texts]
    # rich text is sent block by block (max_html_bytes), not as a whole document
    translate.supports_html = False
    translate.max_html_bytes = MYMEMORY_MAX_BYTES
    return translate


def libretranslate_translator(url, api_key=None, timeout=30):
    """LibreTranslate (open source, self-hostable): text and HTML."""
    endpoint = url.rstrip('/') + '/translate'

    def translate(texts, source, target, fmt='text'):
        body = {'q': list(texts), 'source': source, 'target': target, 'format': 'html' if fmt == 'html' else 'text'}
        if api_key:
            body['api_key'] = api_key
        try:
            response = requests.post(endpoint, json=body, timeout=timeout)
            payload = response.json()
        except (requests.RequestException, ValueError) as e:
            raise TranslationError('LibreTranslate is unreachable: %s' % e)
        if response.status_code != 200:
            raise TranslationError('LibreTranslate error (%s): %s' % (response.status_code, payload.get('error')))
        result = payload.get('translatedText')
        return result if isinstance(result, list) else [result]
    return translate


def html_unescape(text):
    import html
    return html.unescape(text)


def provider_ready(conf):
    """True when the configured provider can translate."""
    provider = (conf or {}).get('provider') or 'google'
    if provider == 'mymemory':
        return True
    if provider == 'libretranslate':
        return bool(conf.get('url'))
    return bool(conf.get('apiKey'))


def get_translator(settings):
    conf = settings.get('translate') or {}
    provider = conf.get('provider') or 'google'
    if provider == 'mymemory':
        return mymemory_translator(conf.get('email'))
    if provider == 'libretranslate':
        if not conf.get('url'):
            raise TranslationError('Machine translation is not configured (missing LibreTranslate URL).')
        return libretranslate_translator(conf['url'], conf.get('apiKey'))
    if not conf.get('apiKey'):
        raise TranslationError('Machine translation is not configured (missing Google API key).')
    return google_translator(conf['apiKey'])


def _empty(value):
    return value in (None, '', [], {})


def translate_data(fields, data, codes, source, target, translator, only_missing=False):
    """Return a copy of the stored (all-locales) ``data`` where the ``target``
    locale of every localized field is translated from ``source``."""
    result = copy.deepcopy(data or {})
    jobs = []  # (container, key, 'text' | 'rich')

    def leaves(field, container, key):
        value = container.get(key)
        ftype = field['type']
        if ftype in ('text', 'textarea') and isinstance(value, str) and value.strip():
            if field.get('name') not in UNTRANSLATABLE_NAMES and not UNTRANSLATABLE_RE.match(value):
                jobs.append((container, key, 'text'))
        elif ftype == 'richText' and is_lexical(value):
            jobs.append((container, key, 'rich'))
        elif ftype == 'group' and isinstance(value, dict):
            for sub in data_fields(field.get('fields') or []):
                leaves(sub, value, sub['name'])
        elif ftype in ('array', 'blocks') and isinstance(value, list):
            blocks = {b['slug']: b for b in field.get('blocks') or []}
            for row in value:
                if isinstance(row, dict):
                    sub_fields = field.get('fields') if ftype == 'array' else (blocks.get(row.get('blockType')) or {}).get('fields')
                    for sub in data_fields(sub_fields or []):
                        leaves(sub, row, sub['name'])

    def visit(fields, obj):
        for field in data_fields(fields):
            name = field['name']
            if name not in obj:
                continue
            value = obj[name]
            ftype = field['type']
            if field.get('localized'):
                if not is_locale_dict(value, codes):
                    value = {source: value} if not _empty(value) else {}
                    obj[name] = value
                if _empty(value.get(source)) or (only_missing and not _empty(value.get(target))):
                    continue
                value[target] = copy.deepcopy(value[source])
                leaves(field, value, target)
            elif ftype == 'group' and isinstance(value, dict):
                visit(field.get('fields') or [], value)
            elif ftype in ('array', 'blocks') and isinstance(value, list):
                blocks = {b['slug']: b for b in field.get('blocks') or []}
                for row in value:
                    if isinstance(row, dict):
                        sub_fields = field.get('fields') if ftype == 'array' else (blocks.get(row.get('blockType')) or {}).get('fields')
                        visit(sub_fields or [], row)

    visit(fields, result)
    texts = [(c, k) for c, k, kind in jobs if kind == 'text']
    rich = [(c, k) for c, k, kind in jobs if kind == 'rich']
    if texts:
        translated = translator([c[k] for c, k in texts], source, target, 'text')
        for (container, key), value in zip(texts, translated):
            container[key] = value
    if rich and getattr(translator, 'supports_html', True):
        translated = translator([lexical_to_html(c[k]) for c, k in rich], source, target, 'html')
        for (container, key), value in zip(rich, translated):
            container[key] = html_to_lexical(value)
    elif rich:
        for container, key in rich:
            container[key] = _translate_blocks(container[key], translator, source, target)
    return result, len(jobs)


def _text_nodes(node, out):
    if not isinstance(node, dict):
        return
    if node.get('type') == 'text' and isinstance(node.get('text'), str) and node['text'].strip():
        out.append(node)
    for child in node.get('children') or []:
        _text_nodes(child, out)


INLINE_TYPES = {'text', 'link', 'autolink', 'linebreak', 'tab'}


def _inline_html(children):
    """HTML of inline nodes (the content of one paragraph / heading / list item)."""
    html = lexical_to_html({'root': {'type': 'root', 'format': '', 'indent': 0, 'version': 1, 'direction': None,
                                     'children': [{'type': 'paragraph', 'format': '', 'indent': 0, 'version': 1,
                                                   'direction': None, 'children': children}]}})
    match = re.match(r'^<p[^>]*>(.*)</p>$', html, re.S)
    return match.group(1) if match else html


def _inline_blocks(node, blocks, fallback):
    """Blocks whose children are all inline (translated with their formatting);
    other text nodes go to ``fallback``."""
    if node.get('type') in ('list', 'root'):
        for child in node.get('children') or []:
            _inline_blocks(child, blocks, fallback)
        return
    children = node.get('children') or []
    if children and all(isinstance(c, dict) and c.get('type') in INLINE_TYPES for c in children):
        if _text_nodes_list(node):
            blocks.append(node)
    else:
        for child in children:
            if isinstance(child, dict) and child.get('children') is not None and child.get('type') not in INLINE_TYPES:
                _inline_blocks(child, blocks, fallback)
            elif isinstance(child, dict):
                fallback += _text_nodes_list(child)


def _translate_blocks(state, translator, source, target):
    """Rich text for providers limited to short texts: the content of each
    block (paragraph, heading, list item...) is translated as inline HTML, so the
    sentence keeps its context and its formatting while the block itself
    (heading level, list type...) is untouched. Blocks that are too long fall
    back to a translation of their text nodes."""
    state = copy.deepcopy(state)
    limit = getattr(translator, 'max_html_bytes', None)
    blocks, fallback = [], []
    _inline_blocks(state.get('root') or {}, blocks, fallback)
    short = []
    for node in blocks:
        html = _inline_html(node['children'])
        if limit and len(html.encode()) > limit:
            fallback += _text_nodes_list(node)
        else:
            short.append((node, html))
    if short:
        translated = translator([h for _n, h in short], source, target, 'html')
        for (node, _html), value in zip(short, translated):
            parsed = html_to_lexical('<p>%s</p>' % value)['root']['children']
            if parsed and parsed[0].get('children'):
                node['children'] = parsed[0]['children']
    if fallback:
        translated = translator([n['text'] for n in fallback], source, target, 'text')
        for node, value in zip(fallback, translated):
            node['text'] = value
    return state


def _text_nodes_list(node):
    out = []
    _text_nodes(node, out)
    return out
