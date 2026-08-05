"""HTTP socle for the voice agent: token, exposure surface, errors, quota.

Every test drives the real WSGI stack (``HttpCase``) rather than calling the
controller in-process: the token check, the status codes and the JSON body are
the contract with a third-party voice platform, and none of them is observable
from a direct method call.
"""
import json
from unittest.mock import patch

import psycopg2

from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from ..controllers.assistant_api import PUBLIC_HTTP_TOOLS
from ..services import tools

TOKEN = "tok-test"


@tagged("post_install", "-at_install", "freemoov_ai")
class TestAssistantApi(HttpCase):
    def setUp(self):
        super().setUp()
        self.ICP = self.env["ir.config_parameter"].sudo()
        self.ICP.set_param("freemoov_livechat_ai.api_token", TOKEN)
        self.Log = self.env["freemoov.assistant.api.log"].sudo()

    def _headers(self, token):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Assistant-Token"] = token
        return headers

    def _call(self, tool, args=None, token=TOKEN, raw=None):
        body = json.dumps({"arguments": args or {}}) if raw is None else raw
        return self.url_open(
            "/api/assistant/v1/call/%s" % tool,
            data=body,
            headers=self._headers(token),
        )

    def _list(self, token=TOKEN):
        return self.url_open("/api/assistant/v1/tools", headers=self._headers(token))

    # --- authentication ---------------------------------------------------

    def test_no_token_403(self):
        self.assertEqual(self._call("infos_magasins", token=None).status_code, 403)
        self.assertEqual(self._call("infos_magasins", token="mauvais").status_code, 403)

    def test_empty_param_disables_api(self):
        """No token configured is 'API off', not 'API open'."""
        self.ICP.set_param("freemoov_livechat_ai.api_token", "")
        self.assertEqual(self._call("infos_magasins").status_code, 403)
        # Not even by sending the empty string the parameter holds.
        self.assertEqual(self._call("infos_magasins", token="").status_code, 403)
        self.assertEqual(self._list().status_code, 403)

    def test_token_comparison_survives_non_ascii(self):
        """A non-ASCII token must compare, not raise: hmac.compare_digest on
        two `str` refuses non-ASCII and a 500 would leak that the token was
        even read."""
        self.ICP.set_param("freemoov_livechat_ai.api_token", "clé-à-façon")
        self.assertEqual(self._call("infos_magasins", token="clé-à-façon").status_code, 200)
        self.assertEqual(self._call("infos_magasins", token="cle-a-facon").status_code, 403)

    def test_rejected_requests_are_never_logged(self):
        """An unauthenticated caller must not be able to write rows: the log
        table is also what the quota counts."""
        before = self.Log.search_count([])
        self._call("infos_magasins", token="tok-canari-secret")
        self._list(token=None)
        self.assertEqual(self.Log.search_count([]), before)

    def test_error_bodies_never_echo_the_credentials(self):
        resp = self._call("infos_magasins", token="tok-canari-secret")
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn("canari", resp.text)
        self.assertNotIn("X-Assistant-Token", resp.text)
        self.assertEqual(resp.json(), {"error": "forbidden"})

    # --- exposure surface -------------------------------------------------

    def test_public_tool_ok(self):
        resp = self._call("infos_magasins", {"ville": "namur"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["magasins"][0]["ville"], "Namur")

    def test_sensitive_tool_not_exposed(self):
        for name in ("statut_commande", "renvoyer_facture", "statut_reparation",
                     "envoyer_code", "verifier_code"):
            self.assertEqual(self._call(name).status_code, 404, name)

    def test_unknown_tool_is_404(self):
        self.assertEqual(self._call("outil_qui_nexiste_pas").status_code, 404)

    def test_tools_endpoint_lists_the_public_tools_only(self):
        resp = self._list()
        self.assertEqual(resp.status_code, 200)
        specs = resp.json()["tools"]
        self.assertEqual({s["name"] for s in specs}, PUBLIC_HTTP_TOOLS)
        for spec in specs:
            self.assertTrue(spec["description"])
            self.assertEqual(spec["input_schema"]["type"], "object")

    def test_public_tools_exist_and_carry_no_identity(self):
        """The exposure list is a hardcoded set: a typo would silently 404 for
        ever, and a tool later flagged `requires_verification` must not stay on
        an unauthenticated-visitor surface."""
        self.assertTrue(PUBLIC_HTTP_TOOLS <= set(tools.TOOLS))
        for name in PUBLIC_HTTP_TOOLS:
            self.assertFalse(tools.TOOLS[name]["requires_verification"], name)

    def test_a_tool_flagged_verified_drops_off_the_api(self):
        """Same invariant, enforced at runtime rather than by the test above:
        the guard is what protects the API the day a tool changes flag."""
        with patch.dict(tools.TOOLS["fiche_produit"], {"requires_verification": True}):
            self.assertEqual(self._call("fiche_produit", {"product_id": 1}).status_code, 404)
            self.assertNotIn(
                "fiche_produit", {s["name"] for s in self._list().json()["tools"]})

    # --- request errors ---------------------------------------------------

    def test_invalid_json_is_400(self):
        resp = self._call("infos_magasins", raw="{not json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json(), {"error": "invalid_json"})

    def test_non_object_payloads_are_400(self):
        for raw in ("[]", '"tout droit"', "3"):
            self.assertEqual(self._call("infos_magasins", raw=raw).status_code, 400, raw)
        # `arguments` itself must be an object, not a list.
        resp = self.url_open(
            "/api/assistant/v1/call/infos_magasins",
            data=json.dumps({"arguments": ["namur"]}),
            headers=self._headers(TOKEN),
        )
        self.assertEqual(resp.status_code, 400)

    def test_missing_body_is_treated_as_no_arguments(self):
        # Straight through the session: url_open turns a falsy body into a GET.
        resp = self.opener.post(
            self.base_url() + "/api/assistant/v1/call/infos_magasins",
            headers=self._headers(TOKEN),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["magasins"]), 3)

    def test_bad_arguments_are_400_and_say_nothing_else(self):
        """Generic message on purpose: the exception text names internals."""
        for args in ({}, {"product_id": "douze"}, {"inconnu": 1, "product_id": 1}):
            resp = self._call("fiche_produit", args)
            self.assertEqual(resp.status_code, 400, args)
            self.assertEqual(resp.json(), {"error": "invalid_arguments"})
            self.assertNotIn("Error", resp.text)
            self.assertNotIn("product_id", resp.text)

    def test_wrongly_typed_arguments_are_refused_up_front(self):
        """The tools were written against the model's tool-use JSON, where the
        types come from the schema. Handed the wrong ones they do not fail
        politely: `marque` and `ville` reach `.lower()` / `.strip()`, i.e. an
        AttributeError — a 500 — and a boolean sent as free text searches the
        catalog for "True". Only `budget_max` fails on its own (a ValueError on
        the float cast), which is precisely why it cannot stand as the sole
        case here."""
        for tool, args in (("chercher_produits", {"marque": 5}),
                           ("chercher_produits", {"recherche": True}),
                           ("chercher_produits", {"budget_max": "cinq cents"}),
                           ("infos_magasins", {"ville": 5})):
            resp = self._call(tool, args)
            self.assertEqual(resp.status_code, 400, args)
            self.assertEqual(resp.json(), {"error": "invalid_arguments"})
        # The healthy call still goes through afterwards.
        self.assertEqual(self._call("chercher_produits", {"budget_max": 500}).status_code, 200)

    @mute_logger("odoo.http", "odoo.sql_db", "odoo.service.model")
    def test_database_errors_are_not_swallowed(self):
        """A dead cursor is not a caller mistake: it must reach the HTTP layer,
        which is what rolls the transaction back and retries it. Reported as a
        400 or a 422 it would be silently lost — and answered as success."""
        with patch.object(tools, "run_tool",
                          side_effect=psycopg2.OperationalError("boom")):
            resp = self._call("infos_magasins")
        self.assertEqual(resp.status_code, 500)

    def test_tool_error_is_422(self):
        tmpl = self.env["product.template"].create({
            "name": "Cache API AI", "list_price": 10.0, "is_published": False,
        })
        resp = self._call("fiche_produit", {"product_id": tmpl.id})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("introuvable", resp.json()["error"])

    # --- quota and audit --------------------------------------------------

    def test_calls_are_logged_with_their_outcome(self):
        self._call("infos_magasins")
        self._call("outil_qui_nexiste_pas")
        self._list()
        logged = self.Log.search([], limit=3, order="id desc").mapped(
            lambda r: (r.tool_name, r.status))
        self.assertEqual(set(logged), {
            ("infos_magasins", "ok"),
            ("outil_qui_nexiste_pas", "unknown_tool"),
            ("__tools__", "ok"),
        })

    def test_logged_tool_name_is_bounded(self):
        """The name comes from the URL: its length is the caller's choice."""
        self._call("x" * 500)
        self.assertLessEqual(
            len(self.Log.search([], limit=1, order="id desc").tool_name), 64)

    def test_quota_refuses_beyond_the_threshold(self):
        self.ICP.set_param("freemoov_livechat_ai.api_rate_per_min", "2")
        self.assertEqual(self._call("infos_magasins").status_code, 200)
        self.assertEqual(self._call("infos_magasins").status_code, 200)
        resp = self._call("infos_magasins")
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.json(), {"error": "rate_limited"})
        self.assertEqual(resp.headers.get("Retry-After"), "60")
        # Refusals do not feed the counter, otherwise the throttle would never
        # release; the discovery endpoint shares the same budget.
        self.assertEqual(self._list().status_code, 429)
        self.assertEqual(
            self.Log.search_count([("status", "=", "rate_limited")]), 2)

    def test_refusals_do_not_feed_the_counter(self):
        self.ICP.set_param("freemoov_livechat_ai.api_rate_per_min", "1")
        self.assertEqual(self._call("infos_magasins").status_code, 200)
        self.assertEqual(self._call("infos_magasins").status_code, 429)
        # Age the accepted call out of the window, leave the refusal inside it:
        # a throttle that counted its own refusals would never release.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE freemoov_assistant_api_log "
            "SET create_date = create_date - interval '5 minutes' WHERE status = 'ok'")
        self.env.invalidate_all()
        self.assertEqual(self._call("infos_magasins").status_code, 200)

    def test_quota_ignores_a_misconfigured_parameter(self):
        """A typo in the parameter must not open the API nor close it."""
        for raw in ("beaucoup", "", "0", "-5", "2.5"):
            self.ICP.set_param("freemoov_livechat_ai.api_rate_per_min", raw)
            self.assertEqual(self._call("infos_magasins").status_code, 200, raw)

    def test_quota_counts_only_the_last_minute(self):
        self.ICP.set_param("freemoov_livechat_ai.api_rate_per_min", "1")
        self.assertEqual(self._call("infos_magasins").status_code, 200)
        self.assertEqual(self._call("infos_magasins").status_code, 429)
        # Same rows, aged past the window: the quota must release.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE freemoov_assistant_api_log "
            "SET create_date = create_date - interval '5 minutes'")
        self.env.invalidate_all()
        self.assertEqual(self._call("infos_magasins").status_code, 200)
