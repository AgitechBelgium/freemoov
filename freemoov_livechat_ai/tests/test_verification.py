from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from ..services import tools
from .common import FreemoovAiCase


@tagged("post_install", "-at_install", "freemoov_ai")
class TestVerification(FreemoovAiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Client Test", "email": "client@test.be", "phone": "+32470000000",
        })
        cls.Verif = cls.env["freemoov.livechat.verification"]

    def _start(self, identifier="client@test.be"):
        with patch.object(type(self.Verif), "_send_code") as send:
            res = self.Verif.start_verification(self.channel, identifier)
            code = send.call_args.args[2]  # (partner, method, code)
        return res, code

    def _register_sensitive_tool(self):
        @tools.register("t_verif_secret", "Secret", {"type": "object", "properties": {}},
                        requires_verification=True)
        def t_verif_secret(env, channel):
            return {"secret": 42}

        self.addCleanup(tools.TOOLS.pop, "t_verif_secret", None)

    def test_start_masks_target_and_sends(self):
        res, code = self._start()
        self.assertEqual(res["method"], "email")
        self.assertNotIn("client@test.be", res["target_masked"])
        self.assertIn("***", res["target_masked"])
        self.assertEqual(len(code), 6)

    def test_good_code_verifies_channel(self):
        _, code = self._start()
        res = self.Verif.check_code(self.channel, code)
        self.assertTrue(res["verified"])
        self.assertEqual(self.channel._freemoov_ai_verified_partner(), self.partner)

    def test_three_bad_codes_lock(self):
        self._start()
        for _ in range(3):
            res = self.Verif.check_code(self.channel, "000000")
        self.assertFalse(res["verified"])
        self.assertEqual(res["attempts_left"], 0)
        # même le bon code est refusé après verrouillage
        self.assertFalse(self.channel._freemoov_ai_verified_partner())

    def test_unknown_identifier(self):
        from ..services.tools import ToolError
        with self.assertRaises(ToolError):
            self.Verif.start_verification(self.channel, "inconnu@nulpart.be")

    def test_pending_verification_does_not_unlock_tools(self):
        """A code sent but not confirmed is not an identification.

        This is the branch the ``getattr`` fallback in ``run_tool`` stopped
        covering the moment the method landed on ``discuss.channel``: the gate
        now calls a real implementation, and it must still refuse.
        """
        self._register_sensitive_tool()
        self._start()
        self.assertFalse(self.channel._freemoov_ai_verified_partner())
        with self.assertRaisesRegex(tools.ToolError, "verification_required"):
            tools.run_tool(self.env, self.channel, "t_verif_secret", {})

    def test_verified_channel_unlocks_sensitive_tool(self):
        """Counterpart of the test above: the gate opens end to end, so a
        refusal cannot pass for correct behaviour."""
        self._register_sensitive_tool()
        _, code = self._start()
        self.assertTrue(self.Verif.check_code(self.channel, code)["verified"])
        self.assertEqual(
            tools.run_tool(self.env, self.channel, "t_verif_secret", {}),
            {"secret": 42},
        )

    def test_expired_code_is_refused(self):
        _, code = self._start()
        rec = self.Verif.sudo().search([("channel_id", "=", self.channel.id)], limit=1)
        rec.expires_at = fields.Datetime.now() - timedelta(seconds=1)
        res = self.Verif.check_code(self.channel, code)
        self.assertFalse(res["verified"])
        self.assertFalse(self.channel._freemoov_ai_verified_partner())

    def test_sale_order_reference_identifies_partner(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        res, code = self._start(order.name)
        self.assertEqual(res["method"], "email")
        self.assertTrue(self.Verif.check_code(self.channel, code)["verified"])
        self.assertEqual(self.channel._freemoov_ai_verified_partner(), self.partner)

    def test_repair_reference_identifies_partner(self):
        Task = self.env["project.task"]
        if "reparation_number" not in Task._fields:
            self.skipTest("moov_reparation absent: pas de référence de réparation")
        project = self.env["project.project"].create({"name": "Reparations AI"})
        task = Task.create({
            "name": "Remplacement batterie",
            "project_id": project.id,
            "partner_id": self.partner.id,
        })
        self.assertTrue(task.reparation_number, "la séquence de réparation doit être posée")
        _, code = self._start(task.reparation_number)
        self.assertTrue(self.Verif.check_code(self.channel, code)["verified"])
        self.assertEqual(self.channel._freemoov_ai_verified_partner(), self.partner)

    def test_partial_reference_is_not_an_identifier(self):
        """Substring matching on the reference would send a code — and leak a
        masked address — for whichever customer happens to share a fragment."""
        project = self.env["project.project"].create({"name": "Reparations AI"})
        self.env["project.task"].create({
            "name": "RO90001 remplacement batterie",
            "project_id": project.id,
            "partner_id": self.partner.id,
        })
        with self.assertRaises(tools.ToolError):
            self._start("RO9")
        with self.assertRaises(tools.ToolError):
            self._start("remplacement")
