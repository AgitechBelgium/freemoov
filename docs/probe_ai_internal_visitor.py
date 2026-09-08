"""Staging-only real-model probe. Entire test conversation is rolled back."""
from odoo.tools.mail import html2plaintext

assert env.cr.dbname == 'freemoov-staging-36939736'
visitor = env['res.users'].browse(6)
assert visitor.active and not visitor.share
livechat = env['discuss.channel'].browse(2381).livechat_channel_id
assert livechat and livechat._freemoov_ai_available()
try:
    channel = env['discuss.channel'].with_user(visitor).sudo().create(
        livechat._get_livechat_discuss_channel_vals('Internal recipe', user_id=visitor.id))
    assert channel.freemoov_ai_visitor_partner_id == visitor.partner_id
    bot = channel._freemoov_ai_bot_partner()
    for question in ('Quels sont les horaires du magasin de Namur ?', 'Je veux parler à un conseiller'):
        channel.with_user(visitor).message_post(
            body=question, message_type='comment', subtype_xmlid='mail.mt_comment')
        replies = channel.message_ids.filtered(lambda m: m.author_id == bot).sorted('id')
        assert replies
        print('REPLY:', html2plaintext(str(replies[-1].body)))
    assert len(replies) == 2
    logs = env['freemoov.livechat.ai.log'].search([('channel_id', '=', channel.id)], order='id')
    assert logs.mapped('status') == ['ok', 'escalated'], logs.mapped('status')
    assert not channel._freemoov_ai_verified_partner()
    assert channel.livechat_operator_id != visitor.partner_id
    print('PASS: two replies, handoff acknowledged, identity still unverified.')
finally:
    env.cr.rollback()
