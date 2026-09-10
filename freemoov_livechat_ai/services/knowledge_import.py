from odoo.exceptions import ValidationError


def import_articles(env, website_id, entries):
    Article = env['freemoov.ai.knowledge.article']
    Article._check_manager()
    allowed = {'key', 'title', 'answer', 'aliases', 'topic', 'lang', 'source_kind',
               'source_ref', 'source_revision', 'public_url', 'effective_from', 'effective_until', 'internal_note'}
    keys = [(item.get('key'), item.get('lang', 'fr')) for item in entries]
    if len(keys) != len(set(keys)) or any(set(item) - allowed for item in entries):
        raise ValidationError('Import contenant des doublons ou des champs inconnus.')
    created = 0
    # Administrative import only: atomic if any entry fails validation.
    with env.cr.savepoint():
        for entry in entries:
            if not entry.get('source_revision'):
                raise ValidationError('Révision de source obligatoire.')
            domain = [('website_id', '=', website_id), ('lang', '=', entry.get('lang', 'fr')),
                      ('key', '=', entry.get('key'))]
            env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                           ['fm-knowledge:%s:%s:%s' % (website_id, entry.get('lang', 'fr'), entry.get('key'))])
            if Article.search_count(domain + [('source_revision', '=', entry['source_revision'])]):
                continue
            latest = Article.search(domain, order='revision desc', limit=1)
            Article.create(dict(entry, website_id=website_id, revision=(latest.revision or 0) + 1))
            created += 1
    return {'created': created, 'unchanged': len(entries) - created}
