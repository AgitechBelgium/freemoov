from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import FreemoovAiCase
from ..services import tools


@tagged('post_install', '-at_install', 'freemoov_ai')
class TestKnowledge(FreemoovAiCase):
    def setUp(self):
        super().setUp()
        self.assertIn('freemoov.ai.knowledge.article', self.env.registry.models,
                      'Published knowledge model is not installed')
        self.Article = self.env['freemoov.ai.knowledge.article']
        self.livechat = self.env['im_livechat.channel'].create({'name': 'Knowledge test'})
        self.website = self.env['website'].create({'name': 'Knowledge site', 'channel_id': self.livechat.id})
        self.channel.livechat_channel_id = self.livechat
        self.env['ir.config_parameter'].sudo().set_param('freemoov_livechat_ai.knowledge_enabled', 'True')

    def article(self, **values):
        vals = dict(key='atelier.admission', revision=1, website_id=self.website.id,
                    title='Réparation véhicule acheté ailleurs', aliases='réparation externe; atelier concurrent',
                    answer='Depuis septembre 2026, uniquement les véhicules achetés chez Freemoov.',
                    source_kind='client_decision', source_ref='Validation Enzo 2026-09-10')
        vals.update(values)
        return self.Article.create(vals)

    def search(self, question='réparation achetée ailleurs'):
        return tools.run_tool(self.env, self.channel, 'chercher_connaissances', {'question': question})

    def test_publication_controls_visibility(self):
        row = self.article(internal_note='PRIVATE NOTE')
        self.assertEqual(self.search()['articles'], [])
        row.action_publish()
        result = self.search()['articles']
        self.assertEqual([r['key'] for r in result], ['atelier.admission'])
        self.assertNotIn('PRIVATE NOTE', str(result))
        self.assertNotIn('source_ref', result[0])

    def test_public_cannot_read_or_publish(self):
        row = self.article()
        public = self.env.ref('base.public_user')
        with self.assertRaises(AccessError):
            row.with_user(public).read(['answer'])
        with self.assertRaises(AccessError):
            row.with_user(public).action_publish()

    def test_cannot_forge_publication_or_edit_published(self):
        with self.assertRaises(UserError):
            self.article(state='published')
        row = self.article()
        with self.assertRaises(UserError):
            row.write({'validated_by': self.env.uid})
        row.action_publish()
        with self.assertRaises(UserError):
            row.write({'answer': 'Wrong'})

    def test_revision_replaces_without_stale_search(self):
        first = self.article()
        first.action_publish()
        second = self.article(revision=2, answer='Nouvelle réponse validée.')
        self.assertIn('septembre', self.search()['articles'][0]['answer'])
        second.action_publish()
        self.assertEqual(first.state, 'archived')
        self.assertEqual(self.search()['articles'][0]['answer'], 'Nouvelle réponse validée.')

    def test_date_and_language_filter(self):
        row = self.article(effective_from=fields.Date.today() + timedelta(days=1))
        row.action_publish()
        self.assertEqual(self.search()['articles'], [])
        nl = self.article(key='nl', lang='nl')
        nl.action_publish()
        self.assertEqual(self.search()['articles'], [])

    def test_other_site_and_ambiguous_site_fail_closed(self):
        self.article().action_publish()
        self.env['website'].create({'name': 'Other', 'channel_id': self.livechat.id})
        self.assertEqual(self.search()['status'], 'site_unavailable')

    def test_disabled_and_unrelated(self):
        self.article().action_publish()
        self.assertEqual(self.search('recette de cuisine italienne')['articles'], [])
        self.env['ir.config_parameter'].sudo().set_param('freemoov_livechat_ai.knowledge_enabled', 'False')
        self.assertEqual(self.search()['status'], 'disabled')

    def test_invalid_question(self):
        for text in ['', 'x' * 501, None]:
            with self.assertRaises(tools.ToolError):
                self.search(text)

    def test_older_draft_cannot_replace_newer_publication(self):
        old = self.article()
        self.article(revision=2).action_publish()
        with self.assertRaises(UserError):
            old.action_publish()

    def test_database_enforces_one_published_revision(self):
        from psycopg2 import IntegrityError
        self.article().action_publish()
        second = self.article(revision=2)
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.env.cr.execute("UPDATE freemoov_ai_knowledge_article SET state='published' WHERE id=%s", [second.id])

    def test_expired_article_and_public_tool(self):
        self.article(effective_until=fields.Date.today() - timedelta(days=1)).action_publish()
        self.assertEqual(self.search()['articles'], [])
        self.article(revision=2).action_publish()
        result = tools.run_tool(self.env(user=self.env.ref('base.public_user').id), self.channel,
                                'chercher_connaissances', {'question': 'réparation achetée ailleurs'})
        self.assertEqual(result['articles'][0]['revision'], 2)

    def test_source_url_rejects_untrusted_host(self):
        with self.assertRaises(ValidationError):
            self.article(public_url='https://freemoov.com.evil.test/faq')

    def test_import_preserves_manual_changes(self):
        from ..services.knowledge_import import import_articles
        entries = [dict(key='seed', title='Test', answer='Original', source_kind='client_decision',
                        source_ref='Enzo', source_revision='2026-09-10')]
        import_articles(self.env, self.website.id, entries)
        row = self.Article.search([('website_id', '=', self.website.id), ('key', '=', 'seed')])
        row.answer = 'Correction manuelle'
        self.assertEqual(import_articles(self.env, self.website.id, entries)['created'], 0)
        self.assertEqual(row.answer, 'Correction manuelle')
        self.assertEqual(row.state, 'draft')

    def test_agent_records_sources_and_filters_false_source_links(self):
        from unittest.mock import Mock
        from ..services.agent_loop import run_agent
        from .test_agent_loop import _resp
        self.article(public_url='https://www.freemoov.com/faq').action_publish()
        client = Mock()
        client.create_message.side_effect = [
            _resp(tool_use=('chercher_connaissances', {'question': 'réparation achetée ailleurs'})),
            _resp(text='Consultez [source](https://www.freemoov.com/faq) et [source](https://evil.test/faq).')]
        result = run_agent(self.env, self.channel, client, 'Test', [{'role': 'user', 'content': 'réparation ailleurs'}])
        self.assertEqual(result.get('knowledge_sources'), [{'key': 'atelier.admission', 'revision': 1}])
        self.assertNotIn('evil.test', result['text'])
        self.assertIn('https://www.freemoov.com/faq', result['text'])

    def test_agent_retrieves_even_without_model_tool_request(self):
        from unittest.mock import Mock
        from ..services.agent_loop import run_agent
        from .test_agent_loop import _resp
        self.article().action_publish()
        client = Mock()
        client.create_message.return_value = _resp(text='Réponse courte.')
        result = run_agent(self.env, self.channel, client, 'Test',
                           [{'role': 'user', 'content': 'réparation achetée ailleurs'}])
        self.assertEqual(result['knowledge_sources'], [{'key': 'atelier.admission', 'revision': 1}])

    def test_seed_answers_combined_question_with_feminine_participle(self):
        import json
        from odoo.tools import file_open
        from ..services.knowledge_import import import_articles
        with file_open('freemoov_livechat_ai/data/knowledge_seed.json', 'r') as stream:
            entries = json.load(stream)
        import_articles(self.env, self.website.id, entries)
        self.Article.search([('website_id', '=', self.website.id),
                             ('key', 'not in', ['garantie.portee', 'retour.procedure'])]).action_publish()
        result = self.search('Réparez-vous une trottinette achetée ailleurs ? Et combien de magasins avez-vous ?')
        self.assertIn('atelier.admission', [a['key'] for a in result['articles']])
        self.assertIn('magasins.reseau', [a['key'] for a in result['articles']])
