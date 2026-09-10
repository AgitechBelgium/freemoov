from . import register


@register('chercher_connaissances', 'Rechercher les procédures Freemoov validées : paiement, atelier, livraison, magasins et SAV.',
          {'type': 'object', 'properties': {'question': {'type': 'string', 'maxLength': 500}},
           'required': ['question'], 'additionalProperties': False})
def chercher_connaissances(env, channel, question):
    from ..knowledge_search import search_knowledge
    websites = env['website'].sudo().search([('channel_id', '=', channel.sudo().livechat_channel_id.id)], limit=2) if channel.sudo().livechat_channel_id else env['website']
    # Unique server-side association only. Ambiguous shared channels fail closed.
    return search_knowledge(env, websites.id if len(websites) == 1 else False, question)
