"""Live catalog/model consistency checks on staging; no persistent records."""
from odoo.addons.freemoov_livechat_ai.services.agent_loop import run_agent
from odoo.addons.freemoov_livechat_ai.services.anthropic_client import AnthropicClient
from odoo.addons.freemoov_livechat_ai.services.prompt_builder import build_system_prompt
from odoo.addons.freemoov_livechat_ai.services.tools.catalog import _serialize, _store_warehouses

assert env.cr.dbname == 'freemoov-staging-36939736'
channel = env['discuss.channel'].create({
    'name': 'Synthetic catalog consistency', 'channel_type': 'livechat',
    'livechat_operator_id': env.ref('freemoov_livechat_ai.partner_ai_bot').id,
})
cfg = channel._freemoov_ai_config()
client = AnthropicClient(api_key=cfg['api_key'], model=cfg['model'],
                         max_tokens=cfg['max_tokens'], timeout=cfg['client_timeout'])
system = build_system_prompt(env)
try:
    for question in [
        'Est-ce que la Segway Ninebot F2 PLUS E est commandable en ligne et en stock dans vos magasins ?',
        'Je cherche deux trottinettes électriques à moins de 600 euros. Propose deux modèles avec leurs liens.',
        'Propose-moi deux trottinettes à moins de 600 euros disponibles pour acheter maintenant.',
    ]:
        out = run_agent(env, channel, client, system, [{'role': 'user', 'content': question}])
        print('QUESTION', question)
        print('RESPONSE', out['text'])
        print('PRODUCT_IDS', out['product_ids'], 'ESCALATE', out['escalate'])
        assert not out['escalate']
        if question.startswith(('Je cherche', 'Propose-moi')):
            assert len(out['product_ids']) == 2, 'Expected exactly two recommendations'
            for product in env['product.template'].browse(out['product_ids']):
                facts = _serialize(env, product, _store_warehouses(env))
                assert facts['prix_tvac'] <= 600
                assert facts['commandable'] or any((qty or 0) > 0 for qty in facts['dispo'].values()), facts['nom']
    print('PASS catalog-selection-budget-and-orderability; inspect response wording above')
finally:
    env.cr.rollback()
