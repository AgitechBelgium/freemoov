from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    website_cookies_consent_manager = fields.Selection(
        related='website_id.cookies_consent_manager',
        readonly=False,
    )
