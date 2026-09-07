"""Synthetic dry-run on the named staging; all ORM writes are rolled back."""
from unittest.mock import patch

assert env.cr.dbname == 'freemoov-staging-36939736', 'Wrong database'
ICP = env['ir.config_parameter'].sudo()
assert ICP.get_param('freemoov_livechat_ai.api_key'), 'Missing API key'
assert ICP.get_param('freemoov_livechat_ai.dry_run') == 'True', 'Dry run required'
Channel = env['discuss.channel']
channel = Channel.create({
    'name': 'Synthetic AI readiness probe',
    'channel_type': 'livechat',
    'livechat_channel_id': 1,
    'livechat_operator_id': env.ref('freemoov_livechat_ai.partner_ai_bot').id,
})
question = 'Bonjour, quels sont les horaires du magasin de Liège ?'
# Suppress the automatic hook for this synthetic input. The explicit call below
# still runs the real prompt builder, Anthropic client, tools, budget and log.
with patch.object(type(Channel), '_freemoov_ai_trigger_from_message'):
    env['mail.message'].create({
        'model': 'discuss.channel', 'res_id': channel.id,
        'message_type': 'comment', 'body': question, 'author_id': False,
    })
with patch.object(type(Channel), '_freemoov_ai_is_enabled', return_value=True):
    log = channel._freemoov_ai_respond(question)
    print('PROBE_STATUS:', log.status)
    print('PROBE_TOOLS:', log.tools_used)
    print('PROBE_RESPONSE:', log.bot_response)
    # Do not print exception bodies: upstream errors can contain credentials.
    print('PROBE_HAS_ERROR:', bool(log.error_message))
env.cr.rollback()
