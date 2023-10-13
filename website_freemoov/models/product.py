# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import fields, models,api,_

class ProductTemplate(models.Model):
	_inherit = "product.template"
	
	pro_description = fields.Char('Description')
	delivery_return = fields.Char('Delivery & return')
	warranty_support = fields.Char('Warranty & Support')

class ProductCategoryTemplate(models.Model):
	_inherit = "product.public.category"
	
	# category_ids = fields.Many2many('product.public.category',string="Categories")
	brand_ids = fields.Many2many('ust.product.brand',string="Brand")

