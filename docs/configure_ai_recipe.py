"""Run through odoo-bin shell ONLY on the named neutralized staging.

Enables live AI on staging only. Preserves credentials and removes only the
temporary recipe script from the website rule; native flows elsewhere remain.
"""
assert env.cr.dbname == 'freemoov-staging-36939736', 'Wrong database'
channel = env['im_livechat.channel'].browse(1).exists()
assert channel, 'Expected livechat channel is missing'
rule = env['im_livechat.channel.rule'].browse(1).exists()
assert rule and rule.channel_id == channel, 'Unexpected rule/channel'
Script = env['chatbot.script'].with_context(lang='en_US')
script = Script.search([('title', '=', 'Freemoov AI — recette')], limit=1)
assert not rule.chatbot_script_id or rule.chatbot_script_id == script, 'Existing bot must be preserved'
params = env['ir.config_parameter'].sudo()
assert params.get_param('freemoov_livechat_ai.api_key'), 'Configure the API key first'
params.set_param('freemoov_livechat_ai.enabled', 'True')
params.set_param('freemoov_livechat_ai.dry_run', 'False')
rule.write({'chatbot_script_id': False})
channel.default_message = 'Bonjour ! Je suis l’assistant IA Freemoov. Comment puis-je vous aider ?'
assert channel.get_livechat_info()['available']
env.cr.commit()
print('RECIPE_CONFIGURED continuous live AI, rule=%s' % rule.id)
