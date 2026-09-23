# -*- coding: utf-8 -*-
"""Lexical JSON <-> HTML conversion (server side).

* ``lexical_to_html`` produces the same markup as
  ``@payloadcms/richtext-lexical/html`` (convertLexicalToHTML): it is used to
  expose rich text as plain HTML in the REST API.
* ``html_to_lexical`` parses HTML back into a Payload-compatible Lexical state,
  so REST clients (and machine translation) can write HTML.
"""
import re
import secrets
from html import escape
from html.parser import HTMLParser

FORMAT_BOLD, FORMAT_ITALIC, FORMAT_STRIKE, FORMAT_UNDERLINE = 1, 2, 4, 8
FORMAT_CODE, FORMAT_SUB, FORMAT_SUP = 16, 32, 64


def _attr(value):
    return escape(str(value), quote=True)


# ----------------------------------------------------------------------
# Lexical -> HTML
# ----------------------------------------------------------------------
def _style(node):
    styles = []
    fmt = node.get('format')
    if isinstance(fmt, str) and fmt in ('left', 'center', 'right', 'justify', 'start', 'end'):
        styles.append('text-align: %s;' % fmt)
    indent = node.get('indent') or 0
    if indent:
        styles.append('padding-inline-start: %spx;' % (int(indent) * 40))
    return ' style="%s"' % ' '.join(styles) if styles else ''


def _text(node):
    html = escape(node.get('text', ''), quote=False)
    fmt = node.get('format') or 0
    if fmt & FORMAT_BOLD:
        html = '<strong>%s</strong>' % html
    if fmt & FORMAT_ITALIC:
        html = '<em>%s</em>' % html
    if fmt & FORMAT_STRIKE:
        html = '<span style="text-decoration: line-through;">%s</span>' % html
    if fmt & FORMAT_UNDERLINE:
        html = '<span style="text-decoration: underline;">%s</span>' % html
    if fmt & FORMAT_CODE:
        html = '<code>%s</code>' % html
    if fmt & FORMAT_SUB:
        html = '<sub>%s</sub>' % html
    if fmt & FORMAT_SUP:
        html = '<sup>%s</sup>' % html
    return html


def _doc_url(doc):
    if isinstance(doc, dict):
        return doc.get('url') or ('/%s' % doc['slug'] if doc.get('slug') else None)
    return None


def _children(node, ctx):
    return ''.join(_node(child, ctx) for child in node.get('children') or [])


def _node(node, ctx):
    if not isinstance(node, dict):
        return ''
    ntype = node.get('type')
    if ntype == 'text':
        return _text(node)
    if ntype == 'linebreak':
        return '<br>'
    if ntype == 'tab':
        return '\t'
    if ntype == 'paragraph':
        inner = _children(node, ctx)
        return '<p%s>%s</p>' % (_style(node), inner or '<br>')
    if ntype == 'heading':
        tag = node.get('tag') if node.get('tag') in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6') else 'h2'
        return '<%s%s>%s</%s>' % (tag, _style(node), _children(node, ctx), tag)
    if ntype == 'quote':
        return '<blockquote%s>%s</blockquote>' % (_style(node), _children(node, ctx))
    if ntype == 'list':
        tag = 'ol' if node.get('listType') == 'number' else 'ul'
        cls = ' class="list-check"' if node.get('listType') == 'check' else ' class="list-%s"' % ('number' if tag == 'ol' else 'bullet')
        start = ' start="%s"' % node['start'] if tag == 'ol' and node.get('start') not in (None, 1) else ''
        return '<%s%s%s>%s</%s>' % (tag, cls, start, _children(node, ctx), tag)
    if ntype == 'listitem':
        has_sublist = any(isinstance(c, dict) and c.get('type') == 'list' for c in node.get('children') or [])
        if 'checked' in node:
            checked = bool(node.get('checked'))
            return ('<li aria-checked="%s" class="list-item-checkbox list-item-checkbox-%s" role="checkbox" tabindex="-1" value="%s">%s</li>'
                    % ('true' if checked else 'false', 'checked' if checked else 'unchecked', node.get('value') or 1, _children(node, ctx)))
        cls = ' class="nestedListItem"' if has_sublist else ''
        return '<li%s value="%s">%s</li>' % (cls, node.get('value') or 1, _children(node, ctx))
    if ntype in ('link', 'autolink'):
        fields = node.get('fields') or {}
        href = fields.get('url') or ''
        if fields.get('linkType') == 'internal':
            doc = (fields.get('doc') or {}).get('value')
            href = _doc_url(doc) or ctx.get('internal_link', lambda d: '#')(fields.get('doc'))
        target = ' target="_blank" rel="noopener noreferrer"' if fields.get('newTab') else ''
        return '<a href="%s"%s>%s</a>' % (_attr(href or '#'), target, _children(node, ctx))
    if ntype == 'horizontalrule':
        return '<hr>'
    if ntype == 'upload':
        value = node.get('value')
        if not isinstance(value, dict):
            return '<img data-lexical-upload-id="%s" data-lexical-upload-relation-to="%s">' % (
                _attr(value), _attr(node.get('relationTo', '')))
        url = value.get('url') or ''
        mime = value.get('mimeType') or ''
        if mime.startswith('image/'):
            size = ''
            if value.get('width') and value.get('height'):
                size = ' width="%s" height="%s"' % (value['width'], value['height'])
            return '<img alt="%s" src="%s"%s>' % (_attr(value.get('alt') or value.get('filename') or ''), _attr(url), size)
        if mime.startswith('video/'):
            return '<video controls src="%s"></video>' % _attr(url)
        return '<a href="%s" rel="noopener noreferrer">%s</a>' % (_attr(url), escape(value.get('filename') or url))
    if ntype == 'relationship':
        value = node.get('value')
        if isinstance(value, dict):
            title = value.get('title') or value.get('name') or value.get('filename') or value.get('id')
            return '<div data-lexical-relationship-relation-to="%s" data-lexical-relationship-id="%s">%s</div>' % (
                _attr(node.get('relationTo', '')), _attr(value.get('id', '')), escape(str(title)))
        return '<div data-lexical-relationship-relation-to="%s" data-lexical-relationship-id="%s"></div>' % (
            _attr(node.get('relationTo', '')), _attr(value))
    if ntype == 'block':
        fields = node.get('fields') or {}
        return '<div data-block-type="%s"></div>' % _attr(fields.get('blockType', ''))
    return _children(node, ctx)


def lexical_to_html(state, **ctx):
    """Convert a serialized Lexical editor state to HTML."""
    if not isinstance(state, dict):
        return state if isinstance(state, str) else ''
    root = state.get('root') or {}
    return ''.join(_node(child, ctx) for child in root.get('children') or [])


def is_lexical(value):
    return isinstance(value, dict) and isinstance(value.get('root'), dict)


# ----------------------------------------------------------------------
# HTML -> Lexical
# ----------------------------------------------------------------------
FORMAT_TAGS = {'strong': FORMAT_BOLD, 'b': FORMAT_BOLD, 'em': FORMAT_ITALIC, 'i': FORMAT_ITALIC,
               's': FORMAT_STRIKE, 'strike': FORMAT_STRIKE, 'del': FORMAT_STRIKE, 'u': FORMAT_UNDERLINE,
               'ins': FORMAT_UNDERLINE, 'code': FORMAT_CODE, 'sub': FORMAT_SUB, 'sup': FORMAT_SUP}
VOID_TAGS = {'br', 'hr', 'img', 'input', 'meta', 'link', 'source', 'wbr'}


def _element(etype, **extra):
    node = {'children': [], 'direction': None, 'format': '', 'indent': 0, 'type': etype, 'version': 1}
    node.update(extra)
    return node


def _paragraph():
    return _element('paragraph', textFormat=0, textStyle='')


def _text_node(text, fmt):
    return {'detail': 0, 'format': fmt, 'mode': 'normal', 'style': '', 'text': text, 'type': 'text', 'version': 1}


class _Builder(HTMLParser):
    """Small tolerant HTML -> Lexical tree builder."""

    INLINE_PARENTS = ('paragraph', 'heading', 'quote', 'listitem', 'link')

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _element('root')
        self.stack = [(self.root, None)]   # (lexical element, html tag or None when implicit)
        self.formats = []                  # [(tag, bits)]
        self.pre = 0

    @property
    def current(self):
        return self.stack[-1][0]

    def _format(self):
        fmt = 0
        for _tag, bits in self.formats:
            fmt |= bits
        return fmt

    def _pop_to(self, types):
        while len(self.stack) > 1 and self.current['type'] not in types:
            self.stack.pop()

    def _inline_parent(self):
        node = self.current
        if node['type'] in self.INLINE_PARENTS:
            return node
        if node['type'] == 'list':
            item = _element('listitem', value=len(node['children']) + 1)
            node['children'].append(item)
            self.stack.append((item, None))
            return item
        para = _paragraph()
        node['children'].append(para)
        self.stack.append((para, None))
        return para

    def _open_block(self, node, tag):
        """Open a paragraph / heading / quote (only allowed at root level)."""
        if self.current['type'] in ('listitem',) or (self.current['type'] == 'quote' and node['type'] != 'quote'):
            return False
        self._pop_to(('root',))
        self.root['children'].append(node)
        self.stack.append((node, tag))
        return True

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        style = attrs.get('style') or ''
        node = None
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            node = _element('heading', tag=tag)
        elif tag in ('p', 'div', 'section', 'article', 'figure', 'header', 'footer', 'td', 'th', 'pre'):
            if attrs.get('data-lexical-relationship-id'):
                rel_id = attrs['data-lexical-relationship-id']
                self._pop_to(('root',))
                self.root['children'].append({'format': '', 'type': 'relationship', 'version': 2,
                                              'relationTo': attrs.get('data-lexical-relationship-relation-to') or '',
                                              'value': int(rel_id) if rel_id.isdigit() else rel_id})
                self.formats.append((tag, 0))
                self._skip = getattr(self, '_skip', 0) + 1
                return
            node = _paragraph()
            if tag == 'pre':
                self.pre += 1
                self.formats.append(('pre', FORMAT_CODE))
        elif tag == 'blockquote':
            node = _element('quote')
        if node is not None:
            align = re.search(r'text-align:\s*(left|center|right|justify)', style)
            if align:
                node['format'] = align.group(1)
            indent = re.search(r'padding-inline-start:\s*(\d+)px', style)
            if indent:
                node['indent'] = int(indent.group(1)) // 40
            self._open_block(node, tag)
            return
        if tag in ('ul', 'ol'):
            ltype = 'number' if tag == 'ol' else ('check' if 'list-check' in (attrs.get('class') or '') else 'bullet')
            lst = _element('list', listType=ltype, start=int(attrs.get('start') or 1) if str(attrs.get('start') or '1').isdigit() else 1,
                           tag='ol' if tag == 'ol' else 'ul')
            if self.current['type'] == 'listitem':
                self.current['children'].append(lst)
            else:
                self._pop_to(('root',))
                self.root['children'].append(lst)
            self.stack.append((lst, tag))
        elif tag == 'li':
            self._pop_to(('list', 'root'))
            if self.current['type'] != 'list':
                lst = _element('list', listType='bullet', start=1, tag='ul')
                self.root['children'].append(lst)
                self.stack.append((lst, None))
            lst = self.current
            extra = {'value': len(lst['children']) + 1}
            if lst.get('listType') == 'check':
                extra['checked'] = attrs.get('aria-checked') == 'true'
            item = _element('listitem', **extra)
            lst['children'].append(item)
            self.stack.append((item, tag))
        elif tag == 'a':
            link = _element('link', fields={'url': attrs.get('href') or '', 'newTab': attrs.get('target') == '_blank',
                                            'linkType': 'custom'}, id=secrets.token_hex(12))
            link['version'] = 3
            self._inline_parent()['children'].append(link)
            self.stack.append((link, tag))
        elif tag == 'br':
            self._inline_parent()['children'].append({'type': 'linebreak', 'version': 1})
        elif tag == 'hr':
            self._pop_to(('root',))
            self.root['children'].append({'type': 'horizontalrule', 'version': 1})
        elif tag == 'img':
            upload_id = attrs.get('data-lexical-upload-id')
            if upload_id:
                self._pop_to(('root',))
                self.root['children'].append({'format': '', 'type': 'upload', 'version': 3, 'id': secrets.token_hex(12),
                                              'fields': None, 'relationTo': attrs.get('data-lexical-upload-relation-to') or 'media',
                                              'value': int(upload_id) if upload_id.isdigit() else upload_id})
        elif tag in FORMAT_TAGS:
            self.formats.append((tag, FORMAT_TAGS[tag]))
        elif tag == 'span':
            bits = 0
            if 'line-through' in style:
                bits |= FORMAT_STRIKE
            if 'underline' in style:
                bits |= FORMAT_UNDERLINE
            if 'bold' in style or '700' in style:
                bits |= FORMAT_BOLD
            if 'italic' in style:
                bits |= FORMAT_ITALIC
            self.formats.append((tag, bits))

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if getattr(self, '_skip', 0) and tag in ('div', 'p') and self.formats and self.formats[-1][0] == tag:
            self._skip -= 1
            self.formats.pop()
            return
        if tag in FORMAT_TAGS or tag == 'span':
            for index in range(len(self.formats) - 1, -1, -1):
                if self.formats[index][0] == tag:
                    del self.formats[index]
                    break
            return
        if tag == 'pre':
            self.pre = max(0, self.pre - 1)
            for index in range(len(self.formats) - 1, -1, -1):
                if self.formats[index][0] == 'pre':
                    del self.formats[index]
                    break
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index][1] == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        if getattr(self, '_skip', 0):
            return
        if not self.pre:
            data = re.sub(r'\s+', ' ', data)
            if not data.strip() and self.current['type'] in ('root', 'list'):
                return
        if data:
            self._inline_parent()['children'].append(_text_node(data, self._format()))


def _trim(node):
    """Strip leading/trailing spaces of blocks and drop empty text nodes."""
    children = node.get('children')
    if not isinstance(children, list):
        return
    for child in children:
        _trim(child)
    if children and node.get('type') in ('paragraph', 'heading', 'quote', 'listitem'):
        # only the outermost children touch the block edges
        if children[0].get('type') == 'text':
            children[0]['text'] = children[0]['text'].lstrip()
        if children[-1].get('type') == 'text':
            children[-1]['text'] = children[-1]['text'].rstrip()
    node['children'] = [c for c in children if c.get('type') != 'text' or c.get('text')]
    if node.get('type') == 'paragraph':
        first = next((c for c in node['children'] if c.get('type') == 'text'), None)
        node['textFormat'] = first['format'] if first else 0


def html_to_lexical(html):
    """Convert an HTML string to a Payload-compatible Lexical editor state."""
    builder = _Builder()
    builder.feed(html or '')
    builder.close()
    root = builder.root
    _trim(root)
    # wrap stray inline nodes of the root into paragraphs
    if not root['children']:
        root['children'].append(_paragraph())
    return {'root': root}


def lexical_texts(state):
    """Collect the text nodes of a Lexical state (used for translation)."""
    nodes = []

    def walk(node):
        if isinstance(node, dict):
            if node.get('type') == 'text' and node.get('text', '').strip():
                nodes.append(node)
            for child in node.get('children') or []:
                walk(child)
    if isinstance(state, dict):
        walk(state.get('root'))
    return nodes
