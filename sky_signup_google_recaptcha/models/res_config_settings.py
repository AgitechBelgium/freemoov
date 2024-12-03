# -*- encoding: utf-8 -*-
#######################################################################################
#
#    Copyright (C) 2019 Skyscend Business Solutions (https://www.skyscendbs.com)
#    Copyright (C) 2020 Skyscend Business Solutions  Pvt. Ltd.(<https://skyscendbs.com>)
#
#######################################################################################
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_recaptcha_validation = fields.Boolean(
        string="Enable reCAPTCHA for Signup Form", readonly=False,
        related='company_id.enable_recaptcha_validation',
        help="Enable Google reCAPTCHA validation for the signup form"
    )
