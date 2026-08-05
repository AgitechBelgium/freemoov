from odoo.tests import tagged

from ..services import tools
from .common import FreemoovAiCase


class _VerifiedChannel:
    """Stand-in for a channel whose visitor has been identified (Task 3)."""

    def _freemoov_ai_verified_partner(self):
        return True


@tagged("post_install", "-at_install", "freemoov_ai")
class TestToolsRegistry(FreemoovAiCase):
    def test_register_and_specs(self):
        @tools.register("t_echo", "Echo test", {
            "type": "object",
            "properties": {"txt": {"type": "string"}},
            "required": ["txt"],
        })
        def t_echo(env, channel, txt):
            return {"echo": txt}

        self.addCleanup(tools.TOOLS.pop, "t_echo", None)
        specs = tools.anthropic_tool_specs()
        spec = next(s for s in specs if s["name"] == "t_echo")
        self.assertEqual(set(spec), {"name", "description", "input_schema"})

    def test_run_tool_ok_and_unknown(self):
        @tools.register("t_add", "Add", {"type": "object", "properties": {}})
        def t_add(env, channel):
            return {"ok": True}

        self.addCleanup(tools.TOOLS.pop, "t_add", None)
        self.assertEqual(tools.run_tool(self.env, self.channel, "t_add", {}), {"ok": True})
        with self.assertRaises(tools.ToolError):
            tools.run_tool(self.env, self.channel, "nope", {})

    def test_sensitive_tool_blocked_without_verification(self):
        @tools.register("t_secret", "Secret", {"type": "object", "properties": {}},
                        requires_verification=True)
        def t_secret(env, channel):
            return {"secret": 42}

        self.addCleanup(tools.TOOLS.pop, "t_secret", None)
        with self.assertRaisesRegex(tools.ToolError, "verification_required"):
            tools.run_tool(self.env, self.channel, "t_secret", {})

    def test_sensitive_tool_runs_for_verified_channel(self):
        """The gate must let verified channels through, not refuse everything."""

        @tools.register("t_secret", "Secret", {"type": "object", "properties": {}},
                        requires_verification=True)
        def t_secret(env, channel):
            return {"secret": 42}

        self.addCleanup(tools.TOOLS.pop, "t_secret", None)
        self.assertEqual(
            tools.run_tool(self.env, _VerifiedChannel(), "t_secret", {}),
            {"secret": 42},
        )

    def test_run_tool_passes_env_channel_and_arguments(self):
        """Callables receive (env, channel, **arguments), unchanged."""
        calls = []

        @tools.register("t_echo", "Echo test", {
            "type": "object",
            "properties": {"txt": {"type": "string"}},
            "required": ["txt"],
        })
        def t_echo(env, channel, txt):
            calls.append(1)
            self.assertIs(env, self.env)
            self.assertIs(channel, self.channel)
            return {"echo": txt}

        self.addCleanup(tools.TOOLS.pop, "t_echo", None)
        self.assertEqual(
            tools.run_tool(self.env, self.channel, "t_echo", {"txt": "hi"}),
            {"echo": "hi"},
        )
        self.assertEqual(calls, [1], "the tool callable must have been invoked")

    # -- mode observation -------------------------------------------------
    def _set_dry_run(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            tools.DRY_RUN_PARAM, value)

    def _register_sender(self, calls):
        @tools.register("t_send", "Send", {"type": "object", "properties": {}},
                        side_effects=True)
        def t_send(env, channel):
            calls.append(1)
            return {"sent": True}

        self.addCleanup(tools.TOOLS.pop, "t_send", None)

    def test_a_side_effect_tool_does_not_run_in_dry_run(self):
        """Dry run is what an untouched database ships with, and it is what
        the team turns on to watch the assistant work. A rehearsal that mails
        a customer is not a rehearsal.
        """
        calls = []
        self._register_sender(calls)
        self._set_dry_run("True")
        with self.assertRaisesRegex(tools.ToolError, "observation"):
            tools.run_tool(self.env, self.channel, "t_send", {})
        self.assertEqual(calls, [], "the tool ran anyway")

    def test_a_side_effect_tool_runs_once_dry_run_is_off(self):
        calls = []
        self._register_sender(calls)
        self._set_dry_run("False")
        self.assertEqual(tools.run_tool(self.env, self.channel, "t_send", {}),
                         {"sent": True})
        self.assertEqual(calls, [1])

    def test_reading_tools_still_answer_in_dry_run(self):
        """The point of the mode is to read the journal of a real turn: a bot
        that cannot look anything up has nothing to show.
        """
        self._set_dry_run("True")
        res = tools.run_tool(self.env, self.channel, "infos_magasins", {})
        self.assertTrue(res)

    def test_no_code_is_sent_nor_recorded_in_dry_run(self):
        """Refused before the tool body: `envoyer_code` writes a row on a
        lookup that resolves nobody (it is what meters probing), and a mode
        that is supposed to leave no trace may not leave that one either.
        """
        self._set_dry_run("True")
        Verification = self.env["freemoov.livechat.verification"].sudo()
        before = Verification.search_count([("channel_id", "=", self.channel.id)])
        with self.assertRaisesRegex(tools.ToolError, "observation"):
            tools.run_tool(self.env, self.channel, "envoyer_code",
                           {"identifiant": "visiteur.fictif@example.test"})
        self.assertEqual(
            Verification.search_count([("channel_id", "=", self.channel.id)]), before)

    def test_exactly_the_tools_that_leave_a_trace_are_flagged(self):
        """Pinned as a set rather than one assertion per tool: a tool added to
        the registry lands in this test whichever way it is flagged, and its
        author has to say out loud which side it belongs to.
        """
        flagged = {name for name, tool in tools.TOOLS.items() if tool["side_effects"]}
        self.assertEqual(flagged, {"envoyer_code", "verifier_code", "renvoyer_facture"})

    def test_register_rejects_duplicate_name(self):
        """A re-registration must never silently downgrade a sensitive tool."""

        @tools.register("t_secret", "Secret", {"type": "object", "properties": {}},
                        requires_verification=True)
        def t_secret(env, channel):
            return {"secret": 42}

        self.addCleanup(tools.TOOLS.pop, "t_secret", None)
        with self.assertRaises(ValueError):
            @tools.register("t_secret", "Secret bis", {"type": "object", "properties": {}})
            def t_secret_bis(env, channel):
                return {"secret": "leaked"}

        self.assertTrue(tools.TOOLS["t_secret"]["requires_verification"])
        with self.assertRaisesRegex(tools.ToolError, "verification_required"):
            tools.run_tool(self.env, self.channel, "t_secret", {})
