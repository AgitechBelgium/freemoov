"""Regressions observed in the live widget: bus ordering and unrelated cards."""
from unittest.mock import patch

from lxml import html
from markupsafe import Markup

from odoo.tests import tagged

from .common import FreemoovAiCase
from .test_agent_loop import _resp
from ..services.agent_loop import run_agent
from ..services.anthropic_client import AnthropicClient
from ..services.prompt_builder import build_messages_from_channel


@tagged('post_install', '-at_install', 'freemoov_ai')
class TestPresentation(FreemoovAiCase):
    def setUp(self):
        super().setUp()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('freemoov_livechat_ai.enabled', 'True')
        params.set_param('freemoov_livechat_ai.api_key', 'test-key')

    def _capture_messages(self, notifications):
        # Spy at the bus transport boundary; keep message_post, formatting,
        # guest identity and the real notification preparation intact.
        self.sent.extend(payload['message'] for _, kind, payload in notifications
                         if kind == 'discuss.channel/new_message')

    def test_bot_does_not_reuse_visitors_temporary_id(self):
        self.sent = []
        with patch.object(type(self.env['bus.bus']), '_sendmany', side_effect=self._capture_messages):
            self.channel.with_context(temporary_id=91.01)._freemoov_ai_post_as_bot('Réponse')
        self.assertEqual(len(self.sent), 1)
        self.assertFalse(self.sent[0].get('temporary_id'))

    def test_markdown_is_formatted_in_persisted_message(self):
        message = self.channel._freemoov_ai_post_as_bot(
            '**Deux choix**\n\n- Premier\n- [Second](https://www.freemoov.com/shop)\n\n'
            'Une ligne\nUne autre ligne')
        doc = html.fromstring(str(message.body))
        self.assertEqual(doc.xpath('//strong/text()'), ['Deux choix'])
        self.assertEqual(len(doc.xpath('//li')), 2)
        self.assertTrue(doc.xpath('//br'))
        self.assertEqual(doc.xpath('//a/@href'), ['https://www.freemoov.com/shop'])

    def test_model_markup_cannot_embed_images_or_active_content(self):
        message = self.channel._freemoov_ai_post_as_bot(
            '<script>alert(1)</script><img src=x onerror=alert(2)>'
            '\n\n![track](https://example.invalid/pixel) '
            '[bad](javascript:alert%281%29) [data](data:text/html,evil) '
            '[relative](//example.invalid/path) '
            '[safe](https://www.freemoov.com/contactus)')
        doc = html.fromstring(str(message.body))
        self.assertFalse(doc.xpath('//script|//img|//iframe|//*[@onerror]'))
        self.assertEqual(doc.xpath('//a/@href'), ['https://www.freemoov.com/contactus'])

    def test_trusted_qweb_cards_are_not_parsed_as_markdown(self):
        message = self.channel._freemoov_ai_post_as_bot(Markup(
            '<div class="fm-assistant-cards"><img src="/web/image/product.template/1/image_128"/></div>'))
        doc = html.fromstring(str(message.body))
        self.assertTrue(doc.xpath('//div[@class="fm-assistant-cards"]/img'))

    def test_history_keeps_links_but_does_not_repeat_card_labels(self):
        self.channel.with_context(freemoov_ai_bot_post=True).message_post(
            body='Un conseil ?', author_id=False, message_type='comment', subtype_xmlid='mail.mt_comment')
        self.channel._freemoov_ai_post_as_bot('[Choix & détails](https://www.freemoov.com/shop/choice-123)')
        self.channel._freemoov_ai_post_as_bot(Markup(
            '<div class="fm-assistant-cards"><a href="https://www.freemoov.com/shop/choice-123">'
            'CARD LABEL SHOULD NOT BE IN PROMPT</a></div>'))
        history = build_messages_from_channel(self.channel)
        self.assertEqual(history[-1]['role'], 'assistant')
        self.assertIn('https://www.freemoov.com/shop/choice-123', history[-1]['content'])
        self.assertIn('Choix & détails', history[-1]['content'])
        self.assertNotIn('CARD LABEL', history[-1]['content'])

    def test_question_notification_precedes_answer(self):
        guest = self.env['mail.guest'].create({'name': 'Recette ordre'})
        self.channel.write({'channel_member_ids': [(0, 0, {'guest_id': guest.id})]})
        channel = self.channel.with_user(self.env.ref('base.public_user')).with_context(
            guest=guest, temporary_id=91.02)
        self.sent = []
        with patch.object(type(self.env['bus.bus']), '_sendmany', side_effect=self._capture_messages):
            with patch.object(AnthropicClient, 'create_message', return_value=_resp('Bonjour !')):
                question = channel.message_post(body='Bonjour', message_type='comment',
                                                subtype_xmlid='mail.mt_comment')
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(self.sent[0]['id'], question.id)
        self.assertEqual(self.sent[0]['temporary_id'], 91.02)
        self.assertFalse(self.sent[1].get('temporary_id'))

    def _product_turn(self, answer):
        products = self.env['product.template'].create([
            {'name': 'RecipeCards %s' % name, 'list_price': price,
             'is_published': True, 'sale_ok': True}
            for name, price in [('Alpha', 500), ('Beta', 400), ('Gamma', 300)]
        ])
        urls = ['https://www.freemoov.com%s' % product.website_url for product in products]
        responses = [_resp(tool_use=('chercher_produits', {'recherche': 'RecipeCards'})),
                     _resp(answer(urls))]
        with patch.object(AnthropicClient, 'create_message', side_effect=responses):
            out = run_agent(self.env, self.channel, AnthropicClient(api_key='test', model='test'),
                            'sys', [{'role': 'user', 'content': 'Deux produits'}])
        return products, out

    def test_only_final_recommendations_in_answer_order_become_cards(self):
        products, out = self._product_turn(lambda urls: 'Voici [Gamma](%s), puis Alpha : %s.' % (urls[2], urls[0]))
        self.assertEqual(out['product_ids'], [products[2].id, products[0].id])

    def test_no_cards_for_results_not_recommended(self):
        _, out = self._product_turn(lambda urls: 'Quel usage prévois-tu ?')
        self.assertEqual(out['product_ids'], [])

    def test_duplicate_links_produce_one_card(self):
        products, out = self._product_turn(lambda urls: '%s?utm_source=chat %s#details' % (urls[1], urls[1]))
        self.assertEqual(out['product_ids'], [products[1].id])

    def test_untrusted_or_unknown_links_never_become_cards(self):
        _, out = self._product_turn(lambda urls: '%s https://www.freemoov.com/shop/unknown-99999999' %
                                   urls[0].replace('www.freemoov.com', 'example.invalid'))
        self.assertEqual(out['product_ids'], [])
