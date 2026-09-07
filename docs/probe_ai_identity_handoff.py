"""Real model + real ORM recipe, synthetic data only, always rolled back.

Run via odoo-bin shell on the explicitly named staging. Only the outbound OTP
transport is intercepted in memory; the code generator, verifier, tools, agent
loop and operator selection are real. No test_mode flag or real recipient.
"""
import json
import re
import uuid
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.freemoov_livechat_ai.services.tools import run_tool, ToolError

assert env.cr.dbname == 'freemoov-staging-36939736', 'Wrong database'
params = env['ir.config_parameter'].sudo()
assert params.get_param('freemoov_livechat_ai.enabled') == 'True'
assert params.get_param('freemoov_livechat_ai.dry_run') == 'False'
assert params.get_param('freemoov_livechat_ai.verification_test_mode') != 'True'
token = uuid.uuid4().hex[:8]
bot = env.ref('freemoov_livechat_ai.partner_ai_bot')
public = env.ref('base.public_user')
Channel = env['discuss.channel']
Verification = env['freemoov.livechat.verification']
quiet = {'tracking_disable': True, 'mail_create_nosubscribe': True, 'no_reset_password': True}
captured_codes = []


def denied(channel):
    try:
        run_tool(env, channel, 'statut_commande', {})
    except ToolError as exc:
        assert str(exc) == 'verification_required'
    else:
        raise AssertionError('Sensitive tool was not denied')


def new_channel(livechat, partner=None):
    members = [(0, 0, {'partner_id': bot.id})]
    context = {}
    if partner:
        members.append((0, 0, {'partner_id': partner.id}))
    else:
        guest = env['mail.guest'].create({'name': 'Synthetic recipe ' + token})
        members.append((0, 0, {'guest_id': guest.id}))
        context['guest'] = guest
    channel = Channel.create({
        'name': 'Synthetic readiness ' + token, 'channel_type': 'livechat',
        'livechat_channel_id': livechat.id, 'livechat_operator_id': bot.id,
        'livechat_active': True, 'channel_member_ids': members,
    })
    return channel, context


def turn(channel, user, context, body, label):
    question = channel.with_user(user).with_context(**context).message_post(
        body=body, message_type='comment', subtype_xmlid='mail.mt_comment')
    log = env['freemoov.livechat.ai.log'].search([('channel_id', '=', channel.id)], limit=1, order='id desc')
    assert log and log.status in ('ok', 'escalated'), '%s: unexpected AI status %s' % (label, log.status)
    assert channel.message_ids.filtered(lambda m: m.id > question.id and m.author_id == bot), label
    calls = json.loads(log.tool_calls_json or '[]')
    print('TURN', label, log.status, [(call['name'], call.get('ok')) for call in calls])
    print('SYNTHETIC_RESPONSE', re.sub(r'\b\d{6}\b', '[CODE MASQUÉ]', log.bot_response or ''))
    return log


def intercept_code(record, partner, method, code):
    assert partner == customer and method == 'email', 'Unexpected recipient; abort'
    captured_codes.append(code)  # Never printed, persisted or returned to the model.


try:
    livechat = env['im_livechat.channel'].create({'name': 'Synthetic recipe ' + token, 'user_ids': [(5, 0, 0)]})
    customer, other = env['res.partner'].with_context(**quiet).create([
        {'name': 'Synthetic Client ' + token, 'email': 'recipe-' + token + '@example.invalid'},
        {'name': 'Synthetic Other ' + token, 'email': 'other-' + token + '@example.invalid'},
    ])
    own_order, other_order = env['sale.order'].with_context(**quiet).create([
        {'name': 'RECIPE-OWN-' + token, 'partner_id': customer.id, 'state': 'sale'},
        {'name': 'RECIPE-OTHER-' + token, 'partner_id': other.id, 'state': 'sale'},
    ])
    channel, context = new_channel(livechat)
    denied(channel)
    with patch.object(type(Verification), '_send_code', intercept_code):
        turn(channel, public, context, 'Je veux le statut de mes commandes. Mon e-mail est ' + customer.email,
             'identity-request')
        assert len(captured_codes) == 1
        wrong_code = captured_codes[0][:-1] + str((int(captured_codes[0][-1]) + 1) % 10)
        log = turn(channel, public, context, 'Voici le code reçu par e-mail : ' + wrong_code +
                   '. Vérifie-le.', 'wrong-code')
        denied(channel)
        verification = Verification.search([('channel_id', '=', channel.id)], limit=1, order='id desc')
        assert verification.attempts == 1, 'Wrong code must actually reach the verifier'
        assert own_order.name not in log.bot_response
        log = turn(channel, public, context, 'Voici le bon code reçu : ' + captured_codes[0] +
                   '. Peux-tu maintenant consulter le statut de mes commandes ?', 'valid-code-and-order')
        assert channel._freemoov_ai_verified_partner() == customer
        assert own_order.name in log.bot_response and other_order.name not in log.bot_response
        assert captured_codes[0] not in (log.tool_calls_json or '')
    channel2, _ = new_channel(livechat)
    denied(channel2)
    assert [o['reference'] for o in run_tool(env, channel, 'statut_commande', {})['commandes']] == [own_order.name]
    try:
        run_tool(env, channel, 'renvoyer_facture', {'reference_commande': other_order.name})
    except ToolError as exc:
        assert 'introuvable' in str(exc)
    else:
        raise AssertionError('Cross-customer invoice access')
    print('PASS identity-isolation, cross-customer denial, code redacted in tool log')
    Verification.search([('channel_id', '=', channel.id), ('verified_at', '!=', False)]).write({
        'verified_at': fields.Datetime.now() - timedelta(minutes=31)})
    denied(channel)
    print('PASS expired-identity-denied')

    portal = env['res.users'].with_context(**quiet).create({
        'name': 'Synthetic Portal ' + token, 'login': 'portal-' + token + '@example.invalid',
        'groups_id': [(6, 0, [env.ref('base.group_portal').id])],
    })
    portal_channel, portal_context = new_channel(livechat, portal.partner_id)
    turn(portal_channel, portal, portal_context, 'Quels sont les horaires du magasin de Liège ?', 'portal-first')
    turn(portal_channel, portal, portal_context, 'Et le samedi à Namur ?', 'portal-follow-up')
    assert not portal_channel._freemoov_ai_human_active()
    denied(portal_channel)
    print('PASS portal-replies-without-identity-bypass')

    offline, offline_context = new_channel(livechat)
    log = turn(offline, public, offline_context, 'Je veux parler à un conseiller humain.', 'offline-handoff')
    assert log.status == 'escalated'
    assert 'Aucun conseiller' in str(offline.message_ids.sorted('id')[-1].body)
    assert offline.livechat_operator_id == bot

    operator = env['res.users'].with_context(**quiet).create({
        'name': 'Synthetic Operator ' + token, 'login': 'operator-' + token + '@example.invalid',
        'groups_id': [(6, 0, [env.ref('base.group_user').id, env.ref('im_livechat.im_livechat_group_user').id])],
    })
    env['bus.presence'].create({'user_id': operator.id, 'status': 'online'})
    livechat.write({'user_ids': [(6, 0, operator.ids)]})
    assert livechat._get_operator() == operator
    online, online_context = new_channel(livechat)
    log = turn(online, public, online_context, 'Je veux parler à un conseiller humain.', 'online-handoff')
    assert log.status == 'escalated'
    assert online.livechat_operator_id == operator.partner_id
    assert operator.partner_id in online.channel_member_ids.partner_id
    assert online._freemoov_ai_human_active(look_back_seconds=0)
    count = len(online.message_ids.filtered(lambda m: m.author_id == bot))
    online.with_user(operator).message_post(body='Bonjour, le conseiller reprend.',
                                           message_type='comment', subtype_xmlid='mail.mt_comment')
    online.with_user(public).with_context(**online_context).message_post(
        body='Merci, ma question est pour le conseiller.', message_type='comment', subtype_xmlid='mail.mt_comment')
    assert len(online.message_ids.filtered(lambda m: m.author_id == bot)) == count
    print('PASS online-handoff-real-selector-and-persistent-bot-silence')
    print('RECIPE_SUCCESS: no real recipient, no persistent test data, no test-mode change')
finally:
    env.cr.rollback()
