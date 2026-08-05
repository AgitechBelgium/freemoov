from odoo.tests import tagged

from ..services import tools
from .common import FreemoovAiCase


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
