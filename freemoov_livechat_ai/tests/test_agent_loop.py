"""Agent loop tests. Mocked at the HTTP boundary: no network, ever.

`create_message` is the only thing stubbed — every tool below really runs,
through `run_tool`, against the test database.
"""
import copy
import json
from unittest.mock import Mock, patch

import psycopg2

from odoo.tests import TransactionCase, tagged

from ..services import agent_loop, tools
from ..services.anthropic_client import AnthropicClient
from .common import FreemoovAiCase

REQUESTS_POST = "odoo.addons.freemoov_livechat_ai.services.anthropic_client.requests.post"


def _resp(text=None, tool_use=None, stop="end_turn"):
    content = []
    if tool_use:
        content.append({"type": "tool_use", "id": "tu_1",
                        "name": tool_use[0], "input": tool_use[1]})
        stop = "tool_use"
    if text:
        content.append({"type": "text", "text": text})
    return {"text": text or "", "content": content, "stop_reason": stop,
            "input_tokens": 10, "output_tokens": 5, "latency_ms": 50}


def _multi_resp(tool_uses):
    """One assistant turn asking for several tools at once.

    The API does this on its own (parallel tool use is the default), and it
    then refuses the next turn unless *every* `tool_use` id comes back with its
    own `tool_result`.
    """
    return {
        "text": "",
        "content": [
            {"type": "tool_use", "id": "tu_%s" % index, "name": name, "input": arguments}
            for index, (name, arguments) in enumerate(tool_uses)
        ],
        "stop_reason": "tool_use",
        "input_tokens": 10, "output_tokens": 5, "latency_ms": 50,
    }


class _Recorder:
    """`create_message` stand-in that snapshots what it was handed.

    The loop appends to `convo` in place and Mock stores the reference, not a
    copy — `call_args_list` would show every call the *final* conversation, so
    an assertion on "what the second call saw" would be meaningless.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.conversations = []
        self.tool_specs = []

    def __call__(self, system_prompt, messages, tools=None):
        self.conversations.append(copy.deepcopy(messages))
        self.tool_specs.append(tools)
        return self.responses.pop(0)


@tagged("post_install", "-at_install", "freemoov_ai")
class TestAgentLoop(FreemoovAiCase):
    def _client(self):
        return AnthropicClient(api_key="k", model="m")

    def _run(self, responses, question="question"):
        """Run the loop over a canned list of model responses."""
        with patch.object(AnthropicClient, "create_message", side_effect=responses) as cm:
            out = agent_loop.run_agent(self.env, self.channel, self._client(), "sys",
                                       [{"role": "user", "content": question}])
        return out, cm

    # -- boucle nominale --------------------------------------------------
    def test_tool_call_then_answer(self):
        responses = [
            _resp(tool_use=("infos_magasins", {"ville": "namur"})),
            _resp(text="Le magasin de Namur est ouvert du mardi au samedi."),
        ]
        out, _ = self._run(responses, "horaires namur ?")
        self.assertIn("Namur", out["text"])
        self.assertEqual(out["tool_calls"][0]["name"], "infos_magasins")
        self.assertTrue(out["tool_calls"][0]["ok"])
        self.assertFalse(out["escalate"])
        # A tool that returns no product must not feed the cards of Task 6.
        self.assertEqual(out["product_ids"], [])
        # Usage is summed over the whole turn, not just the last call.
        self.assertEqual((out["input_tokens"], out["output_tokens"]), (20, 10))
        self.assertEqual(out["latency_ms"], 100)
        self.assertEqual(
            set(out["tool_calls"][0]), {"name", "arguments", "ok", "duration_ms"})
        self.assertEqual(out["tool_calls"][0]["arguments"], {"ville": "namur"})

    def test_answer_without_any_tool(self):
        out, cm = self._run([_resp(text="Bonjour !")])
        self.assertEqual(out["text"], "Bonjour !")
        self.assertEqual(out["tool_calls"], [])
        self.assertEqual(cm.call_count, 1)

    def test_every_call_routes_through_run_tool(self):
        """`run_tool` is the only place the verification gate lives.

        Reaching `TOOLS[name]["fn"]` directly would run a sensitive tool on an
        unverified visitor, so the loop must never learn that shortcut.
        """
        responses = [
            _resp(tool_use=("infos_magasins", {"ville": "liege"})),
            _resp(text="Voilà."),
        ]
        with patch.object(tools, "run_tool", wraps=tools.run_tool) as run:
            self._run(responses)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[2], "infos_magasins")
        self.assertEqual(run.call_args.args[3], {"ville": "liege"})

    def test_conversation_follows_the_tool_use_protocol(self):
        """The assistant blocks go back verbatim, and every `tool_use` gets a
        `tool_result` carrying its own id — the API rejects the turn otherwise.
        """
        recorder = _Recorder([
            _resp(tool_use=("infos_magasins", {})),
            _resp(text="Trois magasins."),
        ])
        with patch.object(AnthropicClient, "create_message", side_effect=recorder):
            agent_loop.run_agent(self.env, self.channel, self._client(), "sys",
                                 [{"role": "user", "content": "magasins ?"}])
        second = recorder.conversations[1]
        self.assertEqual([m["role"] for m in second], ["user", "assistant", "user"])
        self.assertEqual(second[1]["content"][0]["type"], "tool_use")
        result_block = second[2]["content"][0]
        self.assertEqual(result_block["type"], "tool_result")
        self.assertEqual(result_block["tool_use_id"], "tu_1")
        self.assertFalse(result_block["is_error"])
        self.assertIn("Namur", result_block["content"])
        # The specs travel with every call, including the last one.
        names = {spec["name"] for spec in recorder.tool_specs[0]}
        self.assertEqual(names, set(tools.TOOLS))
        self.assertEqual(recorder.tool_specs[0], recorder.tool_specs[1])

    def test_parallel_tool_use_answers_every_block(self):
        """Several tools in one turn, several results in one message — a loop
        that only served the first block would be rejected on the next call
        ("tool_use ids were found without tool_result blocks").
        """
        recorder = _Recorder([
            _multi_resp([("infos_magasins", {"ville": "namur"}),
                         ("infos_magasins", {"ville": "liege"})]),
            _resp(text="Deux magasins."),
        ])
        with patch.object(AnthropicClient, "create_message", side_effect=recorder):
            out = agent_loop.run_agent(self.env, self.channel, self._client(), "sys",
                                       [{"role": "user", "content": "namur et liege ?"}])
        results = recorder.conversations[1][2]["content"]
        self.assertEqual([block["tool_use_id"] for block in results], ["tu_0", "tu_1"])
        self.assertEqual(len(out["tool_calls"]), 2)
        self.assertIn("Namur", results[0]["content"])
        self.assertIn("Li", results[1]["content"])

    # -- erreurs d'outil --------------------------------------------------
    def test_tool_error_is_relayed_not_fatal(self):
        responses = [
            _resp(tool_use=("statut_commande", {})),  # canal non vérifié -> ToolError
            _resp(text="Je dois d'abord vérifier votre identité. [ESCALATE]"),
        ]
        out, _ = self._run(responses, "ma commande ?")
        self.assertFalse(out["tool_calls"][0]["ok"])
        self.assertTrue(out["escalate"])
        self.assertNotIn("[ESCALATE]", out["text"])

    def test_tool_error_message_reaches_the_model(self):
        """`ToolError` messages are written to be read by the model — relaying
        a generic failure instead would cost it the reason for the refusal."""
        recorder = _Recorder([
            _resp(tool_use=("statut_commande", {})),
            _resp(text="Vérifions votre identité."),
        ])
        with patch.object(AnthropicClient, "create_message", side_effect=recorder):
            agent_loop.run_agent(self.env, self.channel, self._client(), "sys",
                                 [{"role": "user", "content": "ma commande ?"}])
        block = recorder.conversations[1][2]["content"][0]
        self.assertTrue(block["is_error"])
        self.assertEqual(json.loads(block["content"]), {"erreur": "verification_required"})

    def test_hallucinated_arguments_are_relayed_as_errors(self):
        """The registry splats the model's arguments straight into the tool as
        keywords, without validating them: an invented key raises TypeError, a
        non-numeric id raises ValueError. Neither is a bug — both are expected
        traffic from a model, and neither may abort the turn.
        """
        scenarios = [
            ("infos_magasins", {"pays": "Belgique"}),        # TypeError
            ("fiche_produit", {"product_id": "pas-un-id"}),  # ValueError
        ]
        for name, arguments in scenarios:
            with self.subTest(tool=name):
                recorder = _Recorder([
                    _resp(tool_use=(name, arguments)),
                    _resp(text="Je n'ai pas pu récupérer l'information."),
                ])
                with patch.object(AnthropicClient, "create_message", side_effect=recorder):
                    out = agent_loop.run_agent(self.env, self.channel, self._client(), "sys",
                                               [{"role": "user", "content": "?"}])
                self.assertFalse(out["tool_calls"][0]["ok"])
                self.assertTrue(out["text"])
                payload = json.loads(recorder.conversations[1][2]["content"][0]["content"])
                # Generic on purpose: the Python exception text is a stack-trace
                # fragment, and it would end up quoted to a visitor.
                self.assertNotIn(name, payload["erreur"])
                for leak in ("TypeError", "ValueError", "keyword argument", "invalid literal"):
                    self.assertNotIn(leak, payload["erreur"])

    def test_database_errors_are_reraised(self):
        """A psycopg2 error means the cursor is gone: Odoo's retry layer has to
        see it. Swallowed, it would become an "the tool failed" string, the loop
        would keep querying a dead cursor, and the request would 500 later on
        with no trace of the cause.
        """
        responses = [_resp(tool_use=("infos_magasins", {})), _resp(text="jamais atteint")]
        with patch.object(tools, "run_tool",
                          side_effect=psycopg2.OperationalError("cursor is closed")):
            with patch.object(AnthropicClient, "create_message", side_effect=responses) as cm:
                with self.assertRaises(psycopg2.OperationalError):
                    agent_loop.run_agent(self.env, self.channel, self._client(), "sys",
                                         [{"role": "user", "content": "?"}])
        self.assertEqual(cm.call_count, 1, "la boucle ne doit pas continuer sur un curseur mort")

    def test_a_failed_lookup_still_burns_its_quota(self):
        """No savepoint around `run_tool`, ever.

        The anti-probing cap of Task 4 is carried by the `not_found` rows that
        the failed lookups themselves create. A savepoint rolled back on the
        `ToolError` — which is exactly what `assertRaises` does — would erase
        them and hand the model an unmetered existence oracle on sequential
        order references.
        """
        Verification = self.env["freemoov.livechat.verification"]
        domain = [("channel_id", "=", self.channel.id)]
        before = Verification.sudo().search_count(domain)
        responses = [
            _resp(tool_use=("envoyer_code", {"identifiant": "inconnu@nulpart.be"})),
            _resp(text="Je ne retrouve pas ce client."),
        ]
        with patch.object(type(Verification), "_send_code") as send:
            out, _ = self._run(responses, "je veux mes commandes")
        self.assertFalse(send.called, "un identifiant non résolu n'envoie rien")
        self.assertFalse(out["tool_calls"][0]["ok"])
        self.assertEqual(Verification.sudo().search_count(domain), before + 1)

    # -- plafond ----------------------------------------------------------
    def test_iteration_cap(self):
        responses = [_resp(tool_use=("infos_magasins", {}))] * 10
        out, cm = self._run(responses, "boucle")
        self.assertLessEqual(cm.call_count, agent_loop.MAX_TOOL_ITERATIONS + 1)
        self.assertTrue(out["escalate"])

    def test_iteration_cap_answers_something(self):
        """Hitting the cap leaves the last response mid-tool-call, so there is
        no text to show: the visitor still gets a sentence, not an empty bubble.
        """
        out, _ = self._run([_resp(tool_use=("infos_magasins", {}))] * 10, "boucle")
        self.assertTrue(out["text"].strip())
        self.assertEqual(len(out["tool_calls"]), agent_loop.MAX_TOOL_ITERATIONS + 1)

    def test_text_answered_on_the_last_allowed_iteration_is_kept(self):
        """The cap must not throw away an answer the model did produce."""
        responses = [_resp(tool_use=("infos_magasins", {}))] * agent_loop.MAX_TOOL_ITERATIONS
        responses.append(_resp(text="Voici enfin la réponse."))
        out, cm = self._run(responses, "boucle")
        self.assertEqual(cm.call_count, agent_loop.MAX_TOOL_ITERATIONS + 1)
        self.assertEqual(out["text"], "Voici enfin la réponse.")
        self.assertFalse(out["escalate"])

    # -- product_ids ------------------------------------------------------
    def test_product_ids_collected_from_both_product_tools(self):
        """Task 6 draws its cards from these ids, so both payload shapes count:
        `chercher_produits` nests them under `produits`, `fiche_produit` returns
        a single record. The same product seen twice is one card, not two.
        """
        tmpl = self.env["product.template"].create({
            "name": "Trottinette Boucle AI",
            "list_price": 999.0,
            "is_published": True,
            "sale_ok": True,
        })
        responses = [
            _resp(tool_use=("chercher_produits", {"recherche": "Trottinette Boucle AI"})),
            _resp(tool_use=("fiche_produit", {"product_id": tmpl.id})),
            _resp(text="Celle-ci devrait convenir."),
        ]
        out, _ = self._run(responses, "une trottinette ?")
        self.assertEqual(out["product_ids"], [tmpl.id])
        self.assertEqual([c["name"] for c in out["tool_calls"]],
                         ["chercher_produits", "fiche_produit"])
        self.assertTrue(all(c["ok"] for c in out["tool_calls"]))

    def test_failed_product_lookup_collects_nothing(self):
        responses = [
            _resp(tool_use=("fiche_produit", {"product_id": 0})),
            _resp(text="Ce produit n'existe pas."),
        ]
        out, _ = self._run(responses)
        self.assertEqual(out["product_ids"], [])
        self.assertFalse(out["tool_calls"][0]["ok"])


@tagged("post_install", "-at_install", "freemoov_ai")
class TestAnthropicClientToolPayload(TransactionCase):
    """The HTTP boundary itself — `requests.post` is stubbed, nothing leaves.

    The loop tests above all mock `create_message`, so without this class the
    one thing that actually has to reach Anthropic — the tool specs — would be
    covered nowhere.
    """

    def _response(self, body=None, status=200):
        response = Mock()
        response.status_code = status
        response.text = ""
        response.json.return_value = body or {
            "content": [
                {"type": "text", "text": "Je regarde."},
                {"type": "tool_use", "id": "tu_9", "name": "infos_magasins",
                 "input": {"ville": "namur"}},
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 11, "output_tokens": 3},
        }
        return response

    def _call(self, **kwargs):
        client = AnthropicClient(api_key="k", model="m")
        with patch(REQUESTS_POST, return_value=self._response()) as post:
            out = client.create_message("sys", [{"role": "user", "content": "?"}], **kwargs)
        return out, json.loads(post.call_args.kwargs["data"])

    def test_tool_specs_travel_in_the_payload(self):
        specs = tools.anthropic_tool_specs()
        out, payload = self._call(tools=specs)
        self.assertEqual(payload["tools"], specs)
        self.assertEqual(payload["model"], "m")
        # Raw blocks and stop_reason are what the loop runs on.
        self.assertEqual(out["stop_reason"], "tool_use")
        self.assertEqual(out["content"][1]["name"], "infos_magasins")
        self.assertEqual(out["text"], "Je regarde.")

    def test_payload_carries_no_tools_key_without_specs(self):
        """Absent, not empty: `create_message` still serves the plain
        no-tools call (`discuss_channel` uses it today)."""
        out, payload = self._call()
        self.assertNotIn("tools", payload)
        self.assertEqual(out["input_tokens"], 11)

    def test_http_error_is_raised(self):
        client = AnthropicClient(api_key="k", model="m")
        failure = self._response(status=429)
        failure.text = "rate limited"
        with patch(REQUESTS_POST, return_value=failure):
            with self.assertRaisesRegex(RuntimeError, "429"):
                client.create_message("sys", [{"role": "user", "content": "?"}],
                                      tools=tools.anthropic_tool_specs())
