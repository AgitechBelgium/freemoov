from odoo.tests import TransactionCase


class FreemoovAiCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env["discuss.channel"].create({
            "name": "Test visiteur",
            "channel_type": "livechat",
            "livechat_operator_id": cls.env.ref("base.partner_admin").id,
        })
