# -*- encoding: utf-8 -*-
#######################################################################################
#
#    Copyright (C) 2019 Skyscend Business Solutions (https://www.skyscendbs.com)
#    Copyright (C) 2020 Skyscend Business Solutions  Pvt. Ltd.(<https://skyscendbs.com>)
#
#######################################################################################
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_recaptcha_validation = fields.Boolean(
        string="reCAPTCHA Validation for signup form",
        help="Enable Google reCAPTCHA validation for the signup form"
    )
