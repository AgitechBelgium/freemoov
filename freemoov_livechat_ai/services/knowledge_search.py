import re
import unicodedata

from .tools import ToolError

STOP = set('le la les un une des du de d a au aux en et est ce c cette que qui quoi pour je tu il nous vous mon ma mes son sa ses sur chez comment quel quelle quels quelles puis peux peut sont se ne pas'.split())
FORMS = {'achetee': 'achete', 'acheter': 'achete', 'achat': 'achete',
         'reparez': 'reparation', 'reparer': 'reparation', 'repare': 'reparation',
         'reparee': 'reparation'}


def tokens(text):
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    words = {word.rstrip('s') for word in re.findall(r'[a-z0-9]+', normalized) if len(word) > 2 and word not in STOP}
    return {FORMS.get(word, word) for word in words}


def search_knowledge(env, website_id, question, lang='fr'):
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        raise ToolError('La question doit contenir entre 1 et 500 caractères.')
    if env['ir.config_parameter'].sudo().get_param('freemoov_livechat_ai.knowledge_enabled') != 'True':
        return {'status': 'disabled', 'articles': []}
    if not website_id:
        return {'status': 'site_unavailable', 'articles': []}
    query = tokens(question)
    ranked = []
    for row in env['freemoov.ai.knowledge.article'].sudo()._published_for(website_id, lang):
        headline = tokens(row.title + ' ' + (row.aliases or ''))
        body = tokens(row.answer)
        matched = query & (headline | body)
        exact_alias = question.strip().casefold() in [v.strip().casefold() for v in (row.aliases or '').split(';') if v.strip()]
        # A multi-part question may contain an entire intent without being
        # identical to its alias. Keep that intent ahead of broad body matches.
        alias_match = any(len(part) >= 2 and part <= query for part in
                          (tokens(alias) for alias in (row.aliases or '').split(';')))
        if len(matched) < 2 and not exact_alias:
            continue
        score = len(query & headline) * 4 + len(query & body) + (12 if exact_alias or alias_match else 0)
        ranked.append((score, row))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].key))
    return {'status': 'ok' if ranked else 'no_match', 'articles': [
        {'key': row.key, 'revision': row.revision, 'title': row.title, 'answer': row.answer,
         'public_url': row.public_url or False} for _, row in ranked[:5]]}
