from odoo.tests import TransactionCase


class FreemoovAiCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Live mode unless a test says otherwise. The registry refuses every
        # side-effect tool in dry run, and dry run is what an untouched
        # database ships with: pinned here so no suite inherits its answer
        # from whatever the database happens to hold.
        cls.env["ir.config_parameter"].sudo().set_param(
            "freemoov_livechat_ai.dry_run", "False")
        cls.env["ir.config_parameter"].sudo().set_param(
            "freemoov_livechat_ai.knowledge_enabled", "False")
        cls.channel = cls.env["discuss.channel"].create({
            "name": "Test visiteur",
            "channel_type": "livechat",
            "livechat_operator_id": cls.env.ref("base.partner_admin").id,
        })
