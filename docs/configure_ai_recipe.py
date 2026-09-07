"""Run through odoo-bin shell ONLY on the named neutralized staging.

Creates an idempotent native welcome script so the widget can be tested
without an online human operator. Does not enable AI or change credentials.
"""
assert env.cr.dbname == 'freemoov-staging-36939736', 'Wrong database'
channel = env['im_livechat.channel'].browse(1).exists()
assert channel, 'Expected livechat channel is missing'
rule = env['im_livechat.channel.rule'].browse(1).exists()
assert rule and rule.channel_id == channel, 'Unexpected rule/channel'
Script = env['chatbot.script'].with_context(lang='en_US')
script = Script.search([('title', '=', 'Freemoov AI — recette')], limit=1)
assert not rule.chatbot_script_id or rule.chatbot_script_id == script, 'Existing bot must be preserved'
if not script:
    script = Script.create({
        'title': 'Freemoov AI — recette',
        'script_step_ids': [(0, 0, {
            'sequence': 1,
            'step_type': 'free_input_multi',
            'message': "Bienvenue sur la recette de l’assistant Freemoov. "
                       "La configuration des réponses IA est en cours. "
                       "N’utilisez pas de données personnelles pour ces essais.",
        })],
    })
script.operator_partner_id = env.ref('freemoov_livechat_ai.partner_ai_bot')
rule.write({'chatbot_script_id': script.id, 'chatbot_only_if_no_operator': False})
assert not script.first_step_warning, script.first_step_warning
assert channel.get_livechat_info()['available']
env.cr.commit()
print('RECIPE_CONFIGURED script=%s rule=%s' % (script.id, rule.id))
