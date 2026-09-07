"""Format untrusted assistant text; QWeb cards use a separate trusted path."""
from urllib.parse import urlsplit

import markdown
from lxml import html
from markupsafe import Markup, escape

from odoo.tools.mail import html_sanitize

_TAGS = {'p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'code', 'pre', 'a', 'blockquote'}


def format_assistant_text(text):
    # Escape raw HTML BEFORE Markdown parses it; then use Odoo's sanitizer and
    # a strict presentation allowlist. Markdown images must not become tracking
    # requests to model-supplied URLs, even though a normal sanitizer allows img.
    rendered = markdown.markdown(str(escape(text or '')), extensions=['nl2br'])
    safe = html_sanitize(rendered, sanitize_attributes=True, strip_style=True, strip_classes=True)
    doc = html.fragment_fromstring(str(safe), create_parent='div')
    for node in list(doc.iterdescendants()):
        if node.tag == 'img':
            node.drop_tree()
            continue
        if node.tag not in _TAGS:
            node.drop_tag()
            continue
        href = node.get('href') if node.tag == 'a' else None
        node.attrib.clear()
        if href:
            try:
                parsed = urlsplit(href)
                allowed = (parsed.scheme in ('https', 'http') and parsed.hostname
                           and not parsed.username and not parsed.password
                           and not any(ord(c) < 33 for c in href))
            except ValueError:
                allowed = False
            if allowed:
                node.set('href', href)
                node.set('target', '_blank')
                node.set('rel', 'noopener noreferrer')
    return Markup(html.tostring(doc, encoding='unicode'))
