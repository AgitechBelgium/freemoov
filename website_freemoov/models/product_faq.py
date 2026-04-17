# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.tools.translate import html_translate


class ProductFaq(models.Model):
    _name = 'product.faq'
    _description = 'Product FAQ'
    _order = 'sequence, id'

    product_id = fields.Many2one(
        'product.template', string='Product',
        required=True, ondelete='cascade', index=True,
    )
    question = fields.Char(
        string='Question', required=True, translate=True,
    )
    answer = fields.Html(
        string='Answer', required=True,
        translate=html_translate, sanitize_attributes=False,
    )
    sequence = fields.Integer(string='Sequence', default=10)
