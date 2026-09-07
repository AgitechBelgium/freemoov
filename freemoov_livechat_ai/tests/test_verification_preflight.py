"""A typed OTP must be checked even when the model forgets its tool call."""
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from .common import FreemoovAiCase
from .test_agent_loop import _resp
from ..services.agent_loop import run_agent
from ..services.anthropic_client import AnthropicClient


@tagged('post_install', '-at_install', 'freemoov_ai')
class TestVerificationPreflight(FreemoovAiCase):
    def setUp(self):
        super().setUp()
        self.customer = self.env['res.partner'].create({'name': 'OTP Recipe', 'email': 'otp@example.invalid'})
        Verification = self.env['freemoov.livechat.verification']
        self.verification = Verification.create({
            'channel_id': self.channel.id, 'partner_id': self.customer.id, 'method': 'email',
            'code_hash': Verification._hash('492815', self.channel),
            'expires_at': fields.Datetime.now() + timedelta(minutes=10),
        })

    def _run(self, body):
        with patch.object(AnthropicClient, 'create_message', return_value=_resp('Identité acceptée.')):
            return run_agent(self.env, self.channel, AnthropicClient(api_key='test', model='test'),
                             'sys', [{'role': 'user', 'content': body}])

    def test_valid_typed_code_is_verified_without_model_tool_call(self):
        out = self._run('Voici mon code reçu : 492815. Consulte mes commandes.')
        self.assertEqual(self.channel._freemoov_ai_verified_partner(), self.customer)
        self.assertEqual([c['name'] for c in out['tool_calls']], ['verifier_code'])

    def test_wrong_code_is_rejected_instead_of_model_acceptance(self):
        out = self._run('492816')
        self.assertFalse(self.channel._freemoov_ai_verified_partner())
        self.assertEqual(self.verification.attempts, 1)
        self.assertIn('2 essais', out['text'])
        self.assertNotIn('acceptée', out['text'])

    def test_ambiguous_codes_are_not_guessed(self):
        self._run('492815 ou 492816 ?')
        self.assertEqual(self.verification.attempts, 0)
        self.assertFalse(self.channel._freemoov_ai_verified_partner())

    def test_no_pending_verification_does_not_treat_model_number_as_otp(self):
        self.verification.unlink()
        out = self._run('Le modèle 492815 est disponible ?')
        self.assertEqual(out['tool_calls'], [])

    def test_dry_run_keeps_verification_untouched(self):
        self.env['ir.config_parameter'].sudo().set_param('freemoov_livechat_ai.dry_run', 'True')
        self._run('492815')
        self.assertFalse(self.channel._freemoov_ai_verified_partner())
        self.assertEqual(self.verification.attempts, 0)

    def test_collapsed_history_must_not_replay_an_older_code(self):
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('freemoov_livechat_ai.enabled', 'True')
        params.set_param('freemoov_livechat_ai.api_key', 'test')
        for body in ('492815', 'Je n’ai pas saisi de nouveau code.'):
            self.channel.with_context(freemoov_ai_bot_post=True).message_post(
                body=body, author_id=False, message_type='comment', subtype_xmlid='mail.mt_comment')
        with patch.object(AnthropicClient, 'create_message', return_value=_resp('Je t’écoute.')):
            self.channel._freemoov_ai_respond('Je n’ai pas saisi de nouveau code.')
        self.assertFalse(self.channel._freemoov_ai_verified_partner())
        self.assertEqual(self.verification.attempts, 0)
