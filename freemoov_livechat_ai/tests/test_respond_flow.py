"""The channel side of a turn: budget, loop, audit log, cards, typing.

Mocked at the same boundary as the loop tests — `create_message` — so every
tool below really runs against the test database and nothing leaves the box.
"""
import json
from unittest.mock import call, patch

import psycopg2

from odoo.tests import tagged

from ..services import agent_loop, tools
from ..services.anthropic_client import AnthropicClient
from .common import FreemoovAiCase
from .test_agent_loop import _resp


@tagged("post_install", "-at_install", "freemoov_ai")
class TestRespondFlow(FreemoovAiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("freemoov_livechat_ai.enabled", "True")
        ICP.set_param("freemoov_livechat_ai.dry_run", "False")
        ICP.set_param("freemoov_livechat_ai.api_key", "test-key")

    def _log(self):
        return self.env["freemoov.livechat.ai.log"].sudo()

    def _bodies(self):
        return [str(m.body) for m in self.channel.message_ids]

    def _published_product(self, name="Carte Trott", price=999.0):
        return self.env["product.template"].create({
            "name": name, "list_price": price,
            "is_published": True, "sale_ok": True,
        })

    # -- boucle nominale --------------------------------------------------
    def test_respond_logs_tools_and_posts(self):
        responses = [
            _resp(tool_use=("infos_magasins", {})),
            _resp(text="Nos trois magasins sont ouverts du mardi au samedi."),
        ]
        with patch.object(AnthropicClient, "create_message", side_effect=responses):
            log = self.channel._freemoov_ai_respond("vos horaires ?")
        self.assertEqual(log.status, "ok")
        self.assertEqual(log.tools_used, "infos_magasins")
        self.assertIn('"ok": true', log.tool_calls_json)
        self.assertIn("mardi", self._bodies()[0])
        # Usage and timing come from the whole turn, not from the last call.
        self.assertEqual((log.input_tokens, log.output_tokens), (20, 10))
        # The loop renamed this key; reading `latency_ms` would silently log 0.
        self.assertEqual(log.latency_ms, 100)

    def test_repeated_tools_are_listed_once_in_order(self):
        responses = [
            _resp(tool_use=("infos_magasins", {"ville": "namur"})),
            _resp(tool_use=("chercher_produits", {"recherche": "rien"})),
            _resp(tool_use=("infos_magasins", {"ville": "liege"})),
            _resp(text="Voilà."),
        ]
        with patch.object(AnthropicClient, "create_message", side_effect=responses):
            log = self.channel._freemoov_ai_respond("magasins et produits ?")
        self.assertEqual(log.tools_used, "infos_magasins, chercher_produits")
        self.assertEqual(len(json.loads(log.tool_calls_json)), 3)

    def test_empty_answer_still_says_something(self):
        """Last net: the loop is not supposed to return an empty text any more
        (it forces a sentence when it escalates), but an empty bubble would be
        the worst possible failure mode, so the fallback stays.
        """
        blank = {"text": "", "escalate": False, "product_ids": [], "tool_calls": [],
                 "input_tokens": 1, "output_tokens": 1, "api_latency_ms": 1}
        with patch.object(agent_loop, "run_agent", return_value=blank):
            self.channel._freemoov_ai_respond("?")
        self.assertIn("conseiller", self._bodies()[0])

    # -- cartes produit ---------------------------------------------------
    def test_product_cards_posted(self):
        tmpl = self._published_product()
        responses = [
            _resp(tool_use=("fiche_produit", {"product_id": tmpl.id})),
            _resp(text="Voici la fiche."),
        ]
        with patch.object(AnthropicClient, "create_message", side_effect=responses):
            self.channel._freemoov_ai_respond("montre la Carte Trott")
        bodies = self._bodies()
        self.assertTrue(any("fm-assistant-card" in b for b in bodies))
        self.assertTrue(any("Carte Trott" in b and "999" in b for b in bodies))

    def test_no_cards_when_the_turn_escalates(self):
        """Cards under "je vous passe un conseiller" would contradict the
        sentence they sit beneath: the escalation says the turn did not land.
        """
        tmpl = self._published_product(name="Carte Escalade")
        responses = [
            _resp(tool_use=("fiche_produit", {"product_id": tmpl.id})),
            _resp(text="Je préfère vous passer un conseiller. [ESCALATE]"),
        ]
        with patch.object(AnthropicClient, "create_message", side_effect=responses):
            log = self.channel._freemoov_ai_respond("cette trottinette ?")
        self.assertEqual(log.status, "escalated")
        self.assertFalse(any("fm-assistant-card" in b for b in self._bodies()))

    def test_cards_skip_unpublished_products(self):
        """Ids travel through the model, and publication can change mid-turn."""
        tmpl = self._published_product(name="Carte Retiree")
        blank = {"text": "Voici.", "escalate": False, "product_ids": [tmpl.id],
                 "tool_calls": [], "input_tokens": 1, "output_tokens": 1,
                 "api_latency_ms": 1}
        tmpl.is_published = False
        with patch.object(agent_loop, "run_agent", return_value=blank):
            self.channel._freemoov_ai_respond("?")
        self.assertFalse(any("fm-assistant-card" in b for b in self._bodies()))

    def test_failed_cards_do_not_cost_the_turn_its_log(self):
        """The cards are an illustration posted after the answer. The tokens
        are spent either way, and the budget is counted from the log rows.
        """
        tmpl = self._published_product(name="Carte Cassee")
        responses = [
            _resp(tool_use=("fiche_produit", {"product_id": tmpl.id})),
            _resp(text="Voici la fiche."),
        ]
        Channel = type(self.env["discuss.channel"])
        with patch.object(Channel, "_freemoov_ai_post_product_cards",
                          side_effect=RuntimeError("template gone")):
            with patch.object(AnthropicClient, "create_message", side_effect=responses):
                log = self.channel._freemoov_ai_respond("montre la Carte Cassee")
        self.assertEqual(log.status, "ok")
        self.assertIn("Voici la fiche.", self._bodies()[0])

    # -- budget de conversation -------------------------------------------
    def test_budget_stops_the_turn_before_any_api_call(self):
        self._log().create({"channel_id": self.channel.id, "status": "ok",
                            "input_tokens": 40000, "output_tokens": 10001})
        with patch.object(AnthropicClient, "create_message") as create_message:
            log = self.channel._freemoov_ai_respond("encore une question")
        self.assertEqual(log.status, "skipped_budget")
        self.assertFalse(create_message.called)
        self.assertFalse(self._bodies())

    def test_budget_is_per_channel(self):
        other = self.env["discuss.channel"].create({
            "name": "Autre visiteur", "channel_type": "livechat",
            "livechat_operator_id": self.env.ref("base.partner_admin").id,
        })
        self._log().create({"channel_id": other.id, "status": "ok",
                            "input_tokens": 90000, "output_tokens": 0})
        with patch.object(AnthropicClient, "create_message",
                          side_effect=[_resp(text="Bonjour !")]):
            log = self.channel._freemoov_ai_respond("bonjour")
        self.assertEqual(log.status, "ok")

    def test_budget_can_be_raised_by_configuration(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "freemoov_livechat_ai.conversation_token_budget", "200000")
        self._log().create({"channel_id": self.channel.id, "status": "ok",
                            "input_tokens": 60000, "output_tokens": 0})
        with patch.object(AnthropicClient, "create_message",
                          side_effect=[_resp(text="Bonjour !")]):
            log = self.channel._freemoov_ai_respond("bonjour")
        self.assertEqual(log.status, "ok")

    # -- journal d'audit --------------------------------------------------
    def test_identifying_arguments_are_truncated_in_the_audit_log(self):
        """The log is readable by any internal user: what the visitor typed to
        identify themselves is kept as a correlation prefix, not verbatim.
        """
        identifier = "visiteur.fictif@example.be"
        responses = [
            _resp(tool_use=("envoyer_code", {"identifiant": identifier})),
            _resp(text="Je ne retrouve pas ce client."),
        ]
        Verification = self.env["freemoov.livechat.verification"]
        with patch.object(type(Verification), "_send_code"):
            with patch.object(AnthropicClient, "create_message", side_effect=responses):
                log = self.channel._freemoov_ai_respond("mes commandes")
        self.assertNotIn(identifier, log.tool_calls_json)
        self.assertNotIn("example.be", log.tool_calls_json)
        self.assertEqual(json.loads(log.tool_calls_json)[0]["arguments"],
                         {"identifiant": "vis…"})

    def test_the_executed_arguments_are_not_redacted(self):
        """Redaction happens on the way to the log, never on the way to the
        tool — a truncated identifier would resolve to nobody.
        """
        identifier = "visiteur.fictif@example.be"
        responses = [
            _resp(tool_use=("envoyer_code", {"identifiant": identifier})),
            _resp(text="Non trouvé."),
        ]
        Verification = self.env["freemoov.livechat.verification"]
        with patch.object(type(Verification), "_send_code"):
            with patch.object(tools, "run_tool", wraps=tools.run_tool) as run_tool:
                with patch.object(AnthropicClient, "create_message", side_effect=responses):
                    self.channel._freemoov_ai_respond("mes commandes")
        self.assertEqual(run_tool.call_args.args[3], {"identifiant": identifier})

    def test_verification_code_never_reaches_the_log(self):
        responses = [
            _resp(tool_use=("verifier_code", {"code": "123456"})),
            _resp(text="Code invalide."),
        ]
        with patch.object(AnthropicClient, "create_message", side_effect=responses):
            log = self.channel._freemoov_ai_respond("mon code est 123456")
        self.assertNotIn("123456", log.tool_calls_json)

    # -- erreurs ----------------------------------------------------------
    def test_database_errors_reach_the_retrying_layer(self):
        """Swallowed, a `psycopg2.Error` would be written to a log through a
        dead cursor and turn one failed turn into a cascade of 500s.
        """
        before = self._log().search_count([("channel_id", "=", self.channel.id)])
        with patch.object(agent_loop, "run_agent",
                          side_effect=psycopg2.OperationalError("cursor is closed")):
            with patch.object(AnthropicClient, "create_message"):
                with self.assertRaises(psycopg2.OperationalError):
                    self.channel._freemoov_ai_respond("?")
        self.assertEqual(
            self._log().search_count([("channel_id", "=", self.channel.id)]), before)

    def test_other_loop_failures_are_logged_not_raised(self):
        with patch.object(agent_loop, "run_agent", side_effect=RuntimeError("boom")):
            log = self.channel._freemoov_ai_respond("?")
        self.assertEqual(log.status, "error")
        self.assertIn("boom", log.error_message)

    def test_trigger_relays_database_errors(self):
        Channel = type(self.env["discuss.channel"])
        with patch.object(Channel, "_freemoov_ai_trigger_from_message",
                          side_effect=psycopg2.OperationalError("cursor is closed")):
            with self.assertRaises(psycopg2.OperationalError), self.env.cr.savepoint():
                self.channel.message_post(body="coucou", message_type="comment",
                                          subtype_xmlid="mail.mt_comment")

    def test_trigger_swallows_everything_else(self):
        """A bug in the assistant must never cost the visitor their message."""
        Channel = type(self.env["discuss.channel"])
        with patch.object(Channel, "_freemoov_ai_trigger_from_message",
                          side_effect=RuntimeError("boom")):
            message = self.channel.message_post(body="coucou", message_type="comment",
                                                subtype_xmlid="mail.mt_comment")
        self.assertTrue(message.exists())

    # -- frappe -----------------------------------------------------------
    def test_typing_is_notified_around_the_turn(self):
        Member = type(self.env["discuss.channel.member"])
        with patch.object(Member, "_notify_typing") as notify:
            with patch.object(AnthropicClient, "create_message",
                              side_effect=[_resp(text="Bonjour !")]):
                self.channel._freemoov_ai_respond("bonjour")
        self.assertEqual(notify.call_args_list, [call(True), call(False)])
        bot = self.env.ref("freemoov_livechat_ai.partner_ai_bot")
        self.assertIn(bot, self.channel.channel_member_ids.partner_id)

    def test_typing_stops_when_the_turn_fails(self):
        Member = type(self.env["discuss.channel.member"])
        with patch.object(Member, "_notify_typing") as notify:
            with patch.object(agent_loop, "run_agent", side_effect=RuntimeError("boom")):
                self.channel._freemoov_ai_respond("?")
        self.assertEqual(notify.call_args_list, [call(True), call(False)])

    def test_no_typing_notification_on_a_dead_cursor(self):
        """Nothing may touch the database on the way out: a second query would
        raise from the `finally` and bury the original failure.
        """
        Member = type(self.env["discuss.channel.member"])
        with patch.object(Member, "_notify_typing") as notify:
            with patch.object(agent_loop, "run_agent",
                              side_effect=psycopg2.OperationalError("cursor is closed")):
                with self.assertRaises(psycopg2.OperationalError):
                    self.channel._freemoov_ai_respond("?")
        self.assertEqual(notify.call_args_list, [call(True)])

    # -- configuration ----------------------------------------------------
    def test_client_timeout_comes_from_configuration(self):
        """Seven synchronous API calls sit inside the visitor's request, under
        a 120s worker limit: the per-call timeout is what bounds the turn.
        """
        seen = []

        def _capture(client, system_prompt, messages, tools=None):
            seen.append(client.timeout)
            return _resp(text="Bonjour !")

        with patch.object(AnthropicClient, "create_message", autospec=True,
                          side_effect=_capture):
            self.channel._freemoov_ai_respond("bonjour")
            self.env["ir.config_parameter"].sudo().set_param(
                "freemoov_livechat_ai.client_timeout", "8")
            self.channel._freemoov_ai_respond("encore")
        self.assertEqual(seen, [15, 8])

    def test_dry_run_logs_the_audit_without_posting(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "freemoov_livechat_ai.dry_run", "True")
        responses = [
            _resp(tool_use=("infos_magasins", {})),
            _resp(text="Nos trois magasins."),
        ]
        with patch.object(AnthropicClient, "create_message", side_effect=responses):
            log = self.channel._freemoov_ai_respond("vos horaires ?")
        self.assertEqual(log.status, "dry_run")
        self.assertEqual(log.tools_used, "infos_magasins")
        self.assertEqual(log.latency_ms, 100)
        self.assertFalse(self._bodies())
