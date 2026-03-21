# -*- coding: utf-8 -*-
from odoo import api, fields, models


class GoogleMerchantLog(models.Model):
    _name = 'google.merchant.log'
    _description = 'Google Merchant Center Sync Log'
    _order = 'create_date desc'

    product_id = fields.Many2one(
        'product.template',
        string='Product',
        ondelete='set null',
    )
    operation = fields.Selection(
        [
            ('insert', 'Insert / Update'),
            ('delete', 'Delete'),
        ],
        string='Operation',
        required=True,
    )
    status = fields.Selection(
        [
            ('success', 'Success'),
            ('error', 'Error'),
        ],
        string='Status',
        required=True,
    )
    error_message = fields.Text(string='Error Message')
    gmc_product_id = fields.Char(string='GMC Product ID')
    request_data = fields.Text(string='Request Data (debug)')
    create_date = fields.Datetime(string='Date', readonly=True)
