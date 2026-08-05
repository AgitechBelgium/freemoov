from unittest.mock import patch

from odoo.tests import tagged

from ..services import tools
from ..services.tools.verification_tools import MAX_SENDS_PER_HOUR, SEND_WINDOW_MIN
from .common import FreemoovAiCase

REPAIR_PARAM = "freemoov_livechat_ai.repair_tool_enabled"


@tagged("post_install", "-at_install", "freemoov_ai")
class TestSensitiveTools(FreemoovAiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Client Vérifié", "email": "verif@test.be",
        })
        cls.product = cls.env["product.product"].create({"name": "P", "list_price": 5})
        cls.order = cls._confirmed_order(cls.partner)
        cls.Verif = cls.env["freemoov.livechat.verification"]

    @classmethod
    def _confirmed_order(cls, partner):
        order = cls.env["sale.order"].create({
            "partner_id": partner.id,
            "order_line": [(0, 0, {"product_id": cls.product.id})],
        })
        order.action_confirm()
        return order

    # -- helpers ----------------------------------------------------------
    def _verify_channel(self, channel=None, identifier="verif@test.be"):
        channel = channel or self.channel
        with patch.object(type(self.Verif), "_send_code") as send:
            self.Verif._start_verification(channel, identifier)
            code = send.call_args.args[2]  # (partner, method, code)
        self.assertTrue(self.Verif._check_code(channel, code)["verified"])

    def _send_codes(self, count, channel=None, identifier="verif@test.be"):
        channel = channel or self.channel
        with patch.object(type(self.Verif), "_send_code"):
            for _ in range(count):
                tools.run_tool(self.env, channel, "envoyer_code", {"identifiant": identifier})

    def _age_verifications(self, minutes, channel=None):
        """Push this channel's verification records back in time.

        Raw SQL on purpose: `create_date` is the very column the resend cap
        counts, and it is not meant to be written through the ORM.
        """
        channel = channel or self.channel
        self.env.cr.execute(
            "UPDATE freemoov_livechat_verification "
            "SET create_date = create_date - make_interval(mins => %s) WHERE channel_id = %s",
            [minutes, channel.id],
        )
        self.env.invalidate_all()

    def _fsm_project(self):
        values = {"name": "Reparations AI"}
        if "is_fsm" in self.env["project.project"]._fields:
            # project_project_company_id_required_for_fsm_project
            values.update({"is_fsm": True, "company_id": self.env.company.id})
        return self.env["project.project"].create(values)

    def _repair_task(self, project, partner=None, name="Remplacement batterie"):
        return self.env["project.task"].create({
            "name": name,
            "project_id": project.id,
            "partner_id": (partner or self.partner).id,
        })

    def _task_reference(self, task):
        return task.reparation_number if "reparation_number" in task._fields else task.name

    def _enable_repairs(self, value="True"):
        self.env["ir.config_parameter"].sudo().set_param(REPAIR_PARAM, value)

    def _run_as_public(self, name, arguments):
        """Run a tool the way production does: public visitor, cold cache.

        The cache matters as much as the user here — it is shared by every
        environment of the transaction, so a field already read as admin is
        served to the public user without a single ACL check, and the test
        would pass with every `sudo()` stripped out of the tools.
        """
        public_env = self.env(user=self.env.ref("base.public_user"))
        channel = self.channel.with_env(public_env)
        self.env.invalidate_all()
        return tools.run_tool(public_env, channel, name, arguments)

    # -- flux 2FA ---------------------------------------------------------
    def test_envoyer_et_verifier_code_flow(self):
        with patch.object(type(self.Verif), "_send_code") as send:
            res = tools.run_tool(self.env, self.channel, "envoyer_code",
                                 {"identifiant": "verif@test.be"})
            code = send.call_args.args[2]
        self.assertIn("***", res["envoye_vers"])
        self.assertNotIn("verif@test.be", res["envoye_vers"])
        res = tools.run_tool(self.env, self.channel, "verifier_code", {"code": code})
        self.assertTrue(res["verifie"])
        self.assertTrue(self.channel._freemoov_ai_verified_partner())

    def test_verifier_code_reports_remaining_attempts(self):
        self._send_codes(1)
        res = tools.run_tool(self.env, self.channel, "verifier_code", {"code": "000000"})
        self.assertFalse(res["verifie"])
        self.assertEqual(res["essais_restants"], 2)

    def test_resend_cap_per_channel(self):
        """Three codes an hour, and a fresh send does NOT reset the count.

        Without the cap, `_start_verification` hands out a new 3-attempt budget
        on demand — and mails the customer once per request while doing it.
        """
        self._send_codes(MAX_SENDS_PER_HOUR)
        with patch.object(type(self.Verif), "_send_code") as send:
            with self.assertRaisesRegex(tools.ToolError, "trop de codes"):
                tools.run_tool(self.env, self.channel, "envoyer_code",
                               {"identifiant": "verif@test.be"})
            self.assertFalse(send.called, "aucun envoi ne doit partir une fois le plafond atteint")
        # The count is carried by the records themselves: superseded, not deleted.
        self.assertEqual(
            self.Verif.sudo().search_count([("channel_id", "=", self.channel.id)]),
            MAX_SENDS_PER_HOUR,
        )

    def test_resend_cap_does_not_lock_the_channel_forever(self):
        """The cap is a window, not a ban: an hour later the visitor can retry."""
        self._send_codes(MAX_SENDS_PER_HOUR)
        self._age_verifications(SEND_WINDOW_MIN + 1)
        with patch.object(type(self.Verif), "_send_code") as send:
            tools.run_tool(self.env, self.channel, "envoyer_code",
                           {"identifiant": "verif@test.be"})
            code = send.call_args.args[2]
        self.assertTrue(tools.run_tool(self.env, self.channel, "verifier_code",
                                       {"code": code})["verifie"])

    def test_resend_supersedes_the_previous_code(self):
        """Keeping the history must not keep an old code alive."""
        with patch.object(type(self.Verif), "_send_code") as send:
            tools.run_tool(self.env, self.channel, "envoyer_code",
                           {"identifiant": "verif@test.be"})
            first = send.call_args.args[2]
            tools.run_tool(self.env, self.channel, "envoyer_code",
                           {"identifiant": "verif@test.be"})
            second = send.call_args.args[2]
        self.assertFalse(tools.run_tool(self.env, self.channel, "verifier_code",
                                        {"code": first})["verifie"])
        self.assertTrue(tools.run_tool(self.env, self.channel, "verifier_code",
                                       {"code": second})["verifie"])

    # -- commandes --------------------------------------------------------
    def test_statut_commande_blocked_then_ok(self):
        with self.assertRaisesRegex(tools.ToolError, "verification_required"):
            tools.run_tool(self.env, self.channel, "statut_commande", {})
        self._verify_channel()
        res = tools.run_tool(self.env, self.channel, "statut_commande", {})
        self.assertTrue(any(c["reference"] == self.order.name for c in res["commandes"]))

    def test_statut_commande_never_leaks_another_customer(self):
        other = self.env["res.partner"].create({
            "name": "Client Voisin", "email": "voisin@test.be",
        })
        other_order = self._confirmed_order(other)
        self._verify_channel()
        res = tools.run_tool(self.env, self.channel, "statut_commande", {})
        references = {c["reference"] for c in res["commandes"]}
        self.assertIn(self.order.name, references)
        self.assertNotIn(other_order.name, references)

    def test_sensitive_tools_run_as_public_visitor(self):
        """Production reality check: the flow runs as the public user.

        `_freemoov_ai_verified_partner` answers "who" in the caller's own
        environment, so every field read inside a tool has to re-sudo. Run as
        admin, these tools pass whatever they do.
        """
        self._verify_channel()
        res = self._run_as_public("statut_commande", {})
        self.assertTrue(any(c["reference"] == self.order.name for c in res["commandes"]))

    # -- factures ---------------------------------------------------------
    def _posted_invoice(self, order=None):
        invoice = (order or self.order)._create_invoices()
        invoice.action_post()
        return invoice

    def test_renvoyer_facture_no_amount_in_response(self):
        self._verify_channel()
        invoice = self._posted_invoice()
        with patch("odoo.addons.mail.models.mail_template.MailTemplate.send_mail") as sm:
            res = tools.run_tool(self.env, self.channel, "renvoyer_facture",
                                 {"reference_commande": self.order.name})
        self.assertTrue(sm.called)
        self.assertNotIn(str(invoice.amount_total), str(res))
        self.assertIn("***", res["envoye_vers"])
        self.assertNotIn("verif@test.be", res["envoye_vers"])

    def test_renvoyer_facture_as_public_visitor(self):
        self._verify_channel()
        self._posted_invoice()
        with patch("odoo.addons.mail.models.mail_template.MailTemplate.send_mail") as sm:
            res = self._run_as_public("renvoyer_facture",
                                      {"reference_commande": self.order.name})
        self.assertTrue(sm.called)
        self.assertIn("***", res["envoye_vers"])

    def test_renvoyer_facture_refuses_another_customers_order(self):
        other = self.env["res.partner"].create({
            "name": "Client Voisin 2", "email": "voisin2@test.be",
        })
        other_order = self._confirmed_order(other)
        self._posted_invoice(other_order)
        self._verify_channel()
        with patch("odoo.addons.mail.models.mail_template.MailTemplate.send_mail") as sm:
            with self.assertRaisesRegex(tools.ToolError, "introuvable"):
                tools.run_tool(self.env, self.channel, "renvoyer_facture",
                               {"reference_commande": other_order.name})
        self.assertFalse(sm.called)

    def test_renvoyer_facture_wildcard_is_not_a_reference(self):
        """`%` would silently resolve "any of my orders" and mail that invoice."""
        self._verify_channel()
        self._posted_invoice()
        with patch("odoo.addons.mail.models.mail_template.MailTemplate.send_mail") as sm:
            with self.assertRaisesRegex(tools.ToolError, "introuvable"):
                tools.run_tool(self.env, self.channel, "renvoyer_facture",
                               {"reference_commande": self.order.name[:-1] + "%"})
        self.assertFalse(sm.called)

    def test_renvoyer_facture_without_posted_invoice(self):
        self._verify_channel()
        with self.assertRaisesRegex(tools.ToolError, "facture"):
            tools.run_tool(self.env, self.channel, "renvoyer_facture",
                           {"reference_commande": self.order.name})

    # -- réparations ------------------------------------------------------
    def test_statut_reparation_disabled_by_param(self):
        self._verify_channel()
        self._enable_repairs("False")
        with self.assertRaisesRegex(tools.ToolError, "indisponible"):
            tools.run_tool(self.env, self.channel, "statut_reparation", {})

    def test_statut_reparation_blocked_without_verification(self):
        self._enable_repairs()
        with self.assertRaisesRegex(tools.ToolError, "verification_required"):
            tools.run_tool(self.env, self.channel, "statut_reparation", {})

    def test_statut_reparation_returns_fsm_files_only(self):
        """Scoped to Field Service, like the 2FA lookup: an internal task
        carrying a customer is not a repair file."""
        if "is_fsm" not in self.env["project.project"]._fields:
            self.skipTest("industry_fsm absent: pas de cloisonnement FSM")
        self._enable_repairs()
        repair = self._repair_task(self._fsm_project())
        internal = self._repair_task(
            self.env["project.project"].create({"name": "Interne AI"}),
            name="Tache interne AI",
        )
        self._verify_channel()
        res = tools.run_tool(self.env, self.channel, "statut_reparation", {})
        references = {r["reference"] for r in res["reparations"]}
        self.assertIn(self._task_reference(repair), references)
        self.assertNotIn(self._task_reference(internal), references)

    def test_statut_reparation_never_leaks_another_customer(self):
        self._enable_repairs()
        project = self._fsm_project()
        mine = self._repair_task(project)
        other = self._repair_task(
            project,
            partner=self.env["res.partner"].create({"name": "Client Voisin 3"}),
            name="Reparation voisine AI",
        )
        self._verify_channel()
        res = tools.run_tool(self.env, self.channel, "statut_reparation", {})
        references = {r["reference"] for r in res["reparations"]}
        self.assertIn(self._task_reference(mine), references)
        self.assertNotIn(self._task_reference(other), references)

    def test_statut_reparation_tolerates_a_broken_stage_map(self):
        """A typo in a parameter must not raise mid-conversation."""
        self._enable_repairs()
        self.env["ir.config_parameter"].sudo().set_param(
            "freemoov_livechat_ai.repair_stage_map", "not json at all")
        self._repair_task(self._fsm_project())
        self._verify_channel()
        res = tools.run_tool(self.env, self.channel, "statut_reparation", {})
        self.assertTrue(res["reparations"])
