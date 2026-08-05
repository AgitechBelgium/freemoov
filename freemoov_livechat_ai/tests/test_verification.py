import re
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from ..models.verification import TEST_MODE_PARAM, VERIFIED_TTL_MIN
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
            res = self.Verif._start_verification(self.channel, identifier)
            code = send.call_args.args[2]  # (partner, method, code)
        return res, code

    def _register_sensitive_tool(self):
        @tools.register("t_verif_secret", "Secret", {"type": "object", "properties": {}},
                        requires_verification=True)
        def t_verif_secret(env, channel):
            return {"secret": 42}

        self.addCleanup(tools.TOOLS.pop, "t_verif_secret", None)

    def _record(self):
        return self.Verif.sudo().search([("channel_id", "=", self.channel.id)], limit=1)

    def _fsm_project(self):
        values = {"name": "Reparations AI"}
        if "is_fsm" in self.env["project.project"]._fields:
            # project_project_company_id_required_for_fsm_project
            values.update({"is_fsm": True, "company_id": self.env.company.id})
        return self.env["project.project"].create(values)

    def _phone_only_customer(self):
        """Identifiable by order reference only — the SMS branch by construction."""
        partner = self.env["res.partner"].create({
            "name": "Client SMS", "phone": "+32470111111",
        })
        order = self.env["sale.order"].create({"partner_id": partner.id})
        return partner, order

    # -- API de base ------------------------------------------------------
    def test_start_masks_target_and_sends(self):
        res, code = self._start()
        self.assertEqual(res["method"], "email")
        self.assertNotIn("client@test.be", res["target_masked"])
        self.assertIn("***", res["target_masked"])
        # Le domaine est masqué aussi : "@test.be" désigne un client sur un
        # domaine d'entreprise aussi sûrement que l'adresse complète.
        self.assertNotIn("test.be", res["target_masked"])
        self.assertEqual(len(code), 6)

    def test_good_code_verifies_channel(self):
        _, code = self._start()
        res = self.Verif._check_code(self.channel, code)
        self.assertTrue(res["verified"])
        verified = self.channel._freemoov_ai_verified_partner()
        self.assertEqual(verified, self.partner)
        # La barrière répond "qui", elle ne rend pas un enregistrement en sudo
        # dans lequel l'appelant pourrait lire ce qu'il veut.
        self.assertIs(verified.env, self.channel.env)

    def test_three_bad_codes_lock(self):
        _, code = self._start()
        for _ in range(3):
            res = self.Verif._check_code(self.channel, "000000")
        self.assertFalse(res["verified"])
        self.assertEqual(res["attempts_left"], 0)
        # même le bon code est refusé après verrouillage
        self.assertFalse(self.Verif._check_code(self.channel, code)["verified"])
        self.assertFalse(self.channel._freemoov_ai_verified_partner())

    def test_unknown_identifier(self):
        from ..services.tools import ToolError
        with self.assertRaises(ToolError):
            self.Verif._start_verification(self.channel, "inconnu@nulpart.be")

    def test_unknown_identifier_is_still_recorded(self):
        """An unresolved identifier leaves a trace: it consumes the channel's
        quota, otherwise probing sequential references costs nothing.

        Not `assertRaises` here: Odoo's version rolls back to a savepoint when
        the exception fires (`odoo/tests/common.py:446`) and would erase the
        very row under test. The tools layer catches `ToolError` in plain
        Python, so the row survives in production.
        """
        try:
            self.Verif._start_verification(self.channel, "inconnu@nulpart.be")
            self.fail("ToolError attendue")
        except tools.ToolError:
            pass
        rec = self._record()
        self.assertEqual(rec.outcome, "not_found")
        self.assertFalse(rec.partner_id)
        self.assertEqual(self.Verif._requests_since(self.channel, 60), 1)

    def test_a_sent_record_must_be_complete(self):
        """`partner_id` and the code fields are optional for the sake of the
        not-found rows only. A record that claims a code was sent still has to
        carry one."""
        with self.assertRaises(ValidationError):
            self.Verif.sudo().create({"channel_id": self.channel.id, "outcome": "sent"})

    def test_expired_code_is_refused(self):
        _, code = self._start()
        self._record().expires_at = fields.Datetime.now() - timedelta(seconds=1)
        res = self.Verif._check_code(self.channel, code)
        self.assertFalse(res["verified"])
        self.assertFalse(self.channel._freemoov_ai_verified_partner())

    # -- barrière outils --------------------------------------------------
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
        self.assertTrue(self.Verif._check_code(self.channel, code)["verified"])
        self.assertEqual(
            tools.run_tool(self.env, self.channel, "t_verif_secret", {}),
            {"secret": 42},
        )

    def test_verification_expires_after_ttl(self):
        """The livechat cookie lives 24 h; the identification must not.

        Verified once must not mean verified all day on a browser someone else
        can reach.
        """
        self._register_sensitive_tool()
        _, code = self._start()
        self.assertTrue(self.Verif._check_code(self.channel, code)["verified"])
        self._record().verified_at = (
            fields.Datetime.now() - timedelta(minutes=VERIFIED_TTL_MIN + 1)
        )
        self.assertFalse(self.channel._freemoov_ai_verified_partner())
        with self.assertRaisesRegex(tools.ToolError, "verification_required"):
            tools.run_tool(self.env, self.channel, "t_verif_secret", {})

    # -- identifiants acceptés --------------------------------------------
    def test_sale_order_reference_identifies_partner(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        res, code = self._start(order.name)
        self.assertEqual(res["method"], "email")
        self.assertTrue(self.Verif._check_code(self.channel, code)["verified"])
        self.assertEqual(self.channel._freemoov_ai_verified_partner(), self.partner)

    def test_repair_reference_identifies_partner(self):
        Task = self.env["project.task"]
        if "reparation_number" not in Task._fields:
            self.skipTest("moov_reparation absent: pas de référence de réparation")
        task = Task.create({
            "name": "Remplacement batterie",
            "project_id": self._fsm_project().id,
            "partner_id": self.partner.id,
        })
        self.assertTrue(task.reparation_number, "la séquence de réparation doit être posée")
        _, code = self._start(task.reparation_number)
        self.assertTrue(self.Verif._check_code(self.channel, code)["verified"])
        self.assertEqual(self.channel._freemoov_ai_verified_partner(), self.partner)

    def test_task_title_is_not_an_identifier(self):
        """A task title is free text with next to no entropy — and it routinely
        contains the customer's own name. It proves nothing, so only the repair
        reference is accepted."""
        title = "Diagnostic batterie AI"
        self.env["project.task"].create({
            "name": title,
            "project_id": self._fsm_project().id,
            "partner_id": self.partner.id,
        })
        with self.assertRaises(tools.ToolError):
            self._start(title)

    def test_partial_reference_is_not_an_identifier(self):
        """A fragment must not resolve a customer: that would send them a code
        and hand the visitor back their masked address."""
        Task = self.env["project.task"]
        if "reparation_number" not in Task._fields:
            self.skipTest("moov_reparation absent: pas de référence de réparation")
        task = Task.create({
            "name": "Remplacement batterie",
            "project_id": self._fsm_project().id,
            "partner_id": self.partner.id,
        })
        with self.assertRaises(tools.ToolError):
            self._start(task.reparation_number[:-1])

    def test_wildcards_never_widen_the_lookup(self):
        """LIKE metacharacters turn an exact lookup into an enumeration oracle:
        "%@%" resolves a real customer, "RO00%" walks the repair references.

        Two mechanisms, because `_` is legitimate in an e-mail and never in a
        generated reference: the e-mail branch escapes the metacharacters, the
        reference branches refuse the identifier before querying. Either way
        the visitor gets the ordinary not-found answer and learns nothing.
        """
        Task = self.env["project.task"]
        escaped = ["%@%", "client@test.b_", "cl%@test.be", "client@test.be\\"]
        refused = ["%", "_", "\\"]
        if "reparation_number" in Task._fields:
            task = Task.create({
                "name": "Remplacement batterie",
                "project_id": self._fsm_project().id,
                "partner_id": self.partner.id,
            })
            refused.append(task.reparation_number[:4] + "%")
        for probe in escaped + refused:
            with self.subTest(probe=probe), self.assertRaises(tools.ToolError):
                self._start(probe)

    def test_email_with_an_underscore_is_a_valid_identifier(self):
        """169 addresses in this base carry an underscore. Refusing the
        character locked those customers out of the assistant for good, and the
        not-found answer sent them round in circles."""
        partner = self.env["res.partner"].create({
            "name": "Client Underscore", "email": "jean_dupont@test.be",
        })
        res, code = self._start("jean_dupont@test.be")
        self.assertEqual(res["method"], "email")
        self.assertTrue(self.Verif._check_code(self.channel, code)["verified"])
        self.assertEqual(self.channel._freemoov_ai_verified_partner(), partner)

    def test_escaped_underscore_is_not_a_single_char_wildcard(self):
        """The escape has to be a real escape: with `_` still live, this probe
        resolves the neighbouring address and sends that customer a code."""
        self.env["res.partner"].create({
            "name": "Client Voisin", "email": "jeanXdupont@test.be",
        })
        with self.assertRaises(tools.ToolError):
            self._start("jean_dupont@test.be")

    def test_duplicate_email_picks_the_most_active_partner(self):
        """Duplicated e-mails are the norm in this base, so the lookup must not
        depend on row order: the customer who actually orders gets the code."""
        Partner = self.env["res.partner"]
        # "Doublon A" sorts first on res.partner's own order, so a naive
        # search(..., limit=1) would pick the dormant one.
        dormant = Partner.create({"name": "Doublon A", "email": "double@test.be"})
        buyer = Partner.create({"name": "Doublon B", "email": "double@test.be"})
        self.env["sale.order"].create({"partner_id": buyer.id}).write({"state": "sale"})

        _, code = self._start("double@test.be")
        self.assertTrue(self.Verif._check_code(self.channel, code)["verified"])
        verified = self.channel._freemoov_ai_verified_partner()
        self.assertEqual(verified, buyer)
        self.assertNotEqual(verified, dormant)

    # -- envoi du code ----------------------------------------------------
    def test_test_mode_stores_the_code_and_sends_nothing(self):
        """Test mode must never put the code in the logs: this process ships
        its logs to a third party (Sentry). The code lands in a field readable
        by the testers, and nowhere else."""
        self.env["ir.config_parameter"].sudo().set_param(TEST_MODE_PARAM, "True")
        Mail = self.env["mail.mail"].sudo()
        before = Mail.search_count([])

        logger = "odoo.addons.freemoov_livechat_ai.models.verification"
        with self.assertNoLogs(logger, level="DEBUG"):
            self.Verif._start_verification(self.channel, "client@test.be")

        rec = self._record()
        self.assertRegex(rec.test_code_plain or "", r"^\d{6}$")
        self.assertEqual(Mail.search_count([]), before, "aucun mail en mode test")
        self.assertTrue(self.Verif._check_code(self.channel, rec.test_code_plain)["verified"])

    def test_normal_mode_never_stores_the_code_in_clear(self):
        """`_send_code` unmocked: outside test mode the field stays empty.
        Mocking the sender would make this pass whatever the code does."""
        with patch.object(type(self.env["mail.mail"]), "send"):
            self.Verif._start_verification(self.channel, "client@test.be")
        self.assertFalse(self._record().test_code_plain)

    def test_email_delivery_carries_a_working_code(self):
        """Real delivery path, `_send_code` unmocked. `send` is mocked at the
        mail layer only: no SMTP, and the record survives auto_delete so the
        assertions can read it."""
        Mail = self.env["mail.mail"]
        with patch.object(type(Mail), "send") as send:
            res = self.Verif._start_verification(self.channel, "client@test.be")

        self.assertEqual(res["method"], "email")
        self.assertEqual(send.call_count, 1)
        mail = Mail.sudo().search([("email_to", "=", self.partner.email)], order="id desc", limit=1)
        self.assertTrue(mail, "le mail doit être créé")
        self.assertTrue(mail.auto_delete, "le code ne doit pas survivre à l'envoi en base")
        found = re.search(r"\b(\d{6})\b", mail.body_html or "")
        self.assertTrue(found, "le mail légitime doit porter le code")
        self.assertTrue(self.Verif._check_code(self.channel, found.group(1))["verified"])

    def test_sms_delivery_carries_a_working_code(self):
        partner, order = self._phone_only_customer()
        Sms = self.env["sms.sms"]
        with patch.object(type(Sms), "send") as send:
            res = self.Verif._start_verification(self.channel, order.name)

        self.assertEqual(res["method"], "sms")
        self.assertNotIn("470111111", res["target_masked"])
        self.assertEqual(send.call_count, 1)
        sms = Sms.sudo().search([("partner_id", "=", partner.id)], order="id desc", limit=1)
        self.assertTrue(sms, "le SMS doit être créé")
        found = re.search(r"\b(\d{6})\b", sms.body or "")
        self.assertTrue(found, "le SMS légitime doit porter le code")
        self.assertTrue(self.Verif._check_code(self.channel, found.group(1))["verified"])

    def test_sms_branch_is_guarded_when_the_module_is_absent(self):
        """`sms` is a declared dependency now, but an install can still lack it.
        A KeyError in the middle of a visitor conversation is not an option."""
        _, order = self._phone_only_customer()
        with patch.dict(self.env.registry.models):
            self.env.registry.models.pop("sms.sms", None)
            with self.assertRaises(tools.ToolError):
                self.Verif._start_verification(self.channel, order.name)
