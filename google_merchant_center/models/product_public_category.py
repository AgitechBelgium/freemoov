# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductPublicCategory(models.Model):
    _inherit = 'product.public.category'

    gmc_enabled = fields.Boolean(
        string='Export to Google Merchant Center',
        default=False,
        help='If checked, products in this category (and subcategories) can be synced to GMC.',
    )
    gmc_google_category = fields.Char(
        string='Google Product Category',
        help='Google taxonomy category, e.g. "Vehicles & Parts > Vehicle Parts & Accessories > Motor Vehicle Electronics"',
    )
