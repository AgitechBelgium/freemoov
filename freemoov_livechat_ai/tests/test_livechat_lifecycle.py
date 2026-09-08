import json
from unittest.mock import patch

from odoo.tests import tagged
from .common import FreemoovAiCase
from ..services.prompt_builder import build_messages_from_channel
from ..services.anthropic_client import AnthropicClient
from .test_agent_loop import _resp


@tagged('post_install', '-at_install')
class TestLivechatLifecycle(FreemoovAiCase):
    def setUp(self):
        super().setUp()
        self.bot = self.env.ref('freemoov_livechat_ai.partner_ai_bot')
        self.livechat = self.env['im_livechat.channel'].create({'name': 'AI recipe'})
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('freemoov_livechat_ai.enabled', 'True')
        params.set_param('freemoov_livechat_ai.api_key', 'test-key')
        self.portal = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Recipe portal', 'login': 'recipe-portal@example.invalid',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.internal = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Recipe internal visitor', 'login': 'recipe-internal@example.invalid',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })

    def test_offline_ai_is_available_without_finite_script(self):
        self.assertTrue(self.livechat.get_livechat_info()['available'])
        vals = self.livechat._get_livechat_discuss_channel_vals('Visitor')
        self.assertTrue(vals)
        self.assertEqual(vals['livechat_operator_id'], self.bot.id)
        self.assertFalse(vals.get('chatbot_current_step_id'))

    def test_internal_website_visitor_receives_answers_without_verification(self):
        visitor = self.internal
        channel = self.env['discuss.channel'].create(
            self.livechat._get_livechat_discuss_channel_vals('Visitor', user_id=visitor.id))
        self.assertEqual(channel.freemoov_ai_visitor_partner_id, visitor.partner_id)
        with patch.object(AnthropicClient, 'create_message', return_value=_resp('Réponse de recette.')):
            for body in ('Bonjour les horaires ?', 'Et le samedi ?'):
                message = channel.with_user(visitor).message_post(
                    body=body, message_type='comment', subtype_xmlid='mail.mt_comment')
                self.assertTrue(channel._freemoov_ai_is_visitor_message(message),
                                repr((message.author_id.id, channel.freemoov_ai_visitor_partner_id.id,
                                      channel.channel_member_ids.partner_id.ids)))
        self.assertEqual(len(channel.message_ids.filtered(lambda m: m.author_id == self.bot)), 2,
                         repr([(m.author_id.id, m.message_type) for m in channel.message_ids]) +
                         repr(self.env['freemoov.livechat.ai.log'].search([('channel_id', '=', channel.id)]).mapped('status')))
        self.assertFalse(channel._freemoov_ai_verified_partner())
        self.assertEqual(build_messages_from_channel(channel)[0]['role'], 'user')

    def test_internal_visitor_handoff_still_silences_ai(self):
        visitor = self.internal
        channel = self.env['discuss.channel'].create(
            self.livechat._get_livechat_discuss_channel_vals('Visitor', user_id=visitor.id))
        with patch.object(AnthropicClient, 'create_message', return_value=_resp('[ESCALATE]')):
            with patch.object(type(self.livechat), '_get_operator', return_value=self.env['res.users']):
                channel.with_user(visitor).message_post(
                    body='Je veux parler à un conseiller', message_type='comment',
                    subtype_xmlid='mail.mt_comment')
        self.assertTrue(channel.message_ids.filtered(
            lambda m: m.author_id == self.bot and 'Aucun conseiller' in m.body))
        operator = self.portal
        with patch.object(type(self.livechat), '_get_operator', return_value=operator):
            self.assertTrue(channel._freemoov_ai_handoff())
        self.assertTrue(channel._freemoov_ai_human_active(look_back_seconds=0))

    def test_handoff_selection_excludes_the_requesting_visitor(self):
        selector = self.livechat.with_context(freemoov_ai_exclude_partner_id=self.internal.partner_id.id)
        self.assertFalse(selector._get_less_active_operator([], self.internal))
        self.assertEqual(selector._get_less_active_operator([], self.internal | self.portal), self.portal)

    def test_handoff_notifies_the_visitor_of_the_new_operator(self):
        self.channel.write({'livechat_channel_id': self.livechat.id, 'livechat_operator_id': self.bot.id})
        with patch.object(type(self.livechat), '_get_operator', return_value=self.internal):
            self.assertTrue(self.channel._freemoov_ai_handoff())
        payloads = [json.loads(event['message'])['payload'].get('Thread', {})
                    for event in self.env.cr.precommit.data.get('bus.bus.values', [])
                    if self.channel.uuid in json.loads(event['channel'])]
        self.assertTrue(any(payload.get('operator_pid', [False])[0] == self.internal.partner_id.id
                            for payload in payloads))

    def test_portal_is_not_human_operator_and_history_is_user(self):
        self.channel.write({'channel_member_ids': [(0, 0, {'partner_id': self.portal.partner_id.id})]})
        self.channel.with_context(freemoov_ai_bot_post=True).message_post(
            body='Quels horaires ?', author_id=self.portal.partner_id.id,
            message_type='comment', subtype_xmlid='mail.mt_comment')
        self.assertFalse(self.channel._freemoov_ai_human_active())
        self.assertEqual(build_messages_from_channel(self.channel)[-1]['role'], 'user')
        self.assertFalse(self.channel._freemoov_ai_verified_partner())

    def test_handoff_assigns_and_persists_silence(self):
        self.channel.write({'livechat_channel_id': self.livechat.id,
                            'livechat_operator_id': self.bot.id})
        self.channel.add_members(self.bot.ids, post_joined_message=False)
        operator = self.env.ref('base.user_admin')
        with patch.object(type(self.livechat), '_get_operator', return_value=operator):
            self.assertTrue(self.channel._freemoov_ai_handoff())
        self.assertEqual(self.channel.livechat_operator_id, operator.partner_id)
        self.assertIn(operator.partner_id, self.channel.channel_member_ids.partner_id)
        self.assertTrue(self.channel._freemoov_ai_human_active(look_back_seconds=0))

    def test_handoff_offline_does_not_assign(self):
        self.channel.write({'livechat_channel_id': self.livechat.id,
                            'livechat_operator_id': self.bot.id})
        with patch.object(type(self.livechat), '_get_operator', return_value=self.env['res.users']):
            self.assertFalse(self.channel._freemoov_ai_handoff())
        self.assertEqual(self.channel.livechat_operator_id, self.bot)

    def test_portal_two_messages_receive_two_answers(self):
        self.channel.write({'channel_member_ids': [(0, 0, {'partner_id': self.portal.partner_id.id})]})
        with patch.object(AnthropicClient, 'create_message', return_value=_resp('Réponse de recette.')):
            for body in ('Bonjour les horaires ?', 'Et le samedi ?'):
                self.channel.message_post(body=body, author_id=self.portal.partner_id.id,
                                          message_type='comment', subtype_xmlid='mail.mt_comment')
        replies = self.channel.message_ids.filtered(lambda m: m.author_id == self.bot)
        self.assertEqual(len(replies), 2)
        self.assertFalse(self.channel._freemoov_ai_verified_partner())

    def test_disabled_or_dry_run_does_not_advertise_offline_bot(self):
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('freemoov_livechat_ai.enabled', 'False')
        self.assertFalse(self.livechat.get_livechat_info()['available'])
        params.set_param('freemoov_livechat_ai.enabled', 'True')
        params.set_param('freemoov_livechat_ai.dry_run', 'True')
        self.assertFalse(self.livechat.get_livechat_info()['available'])

    def test_offline_handoff_does_not_repeat_model_transfer_promise(self):
        with patch.object(AnthropicClient, 'create_message',
                          return_value=_resp('Je te transfère immédiatement !\n[ESCALATE]')):
            self.channel._freemoov_ai_respond('Un conseiller svp')
        body = str(self.channel.message_ids.filtered(lambda m: m.author_id == self.bot)[0].body)
        self.assertIn('Aucun conseiller', body)
        self.assertNotIn('Je te transfère', body)
