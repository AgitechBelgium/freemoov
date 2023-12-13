# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import fields, models,api,_

class ProductTemplate(models.Model):
	_inherit = "product.template"
	
	pro_description = fields.Text('Description')
	delivery_return = fields.Text('Delivery & return')
	warranty_support = fields.Text('Warranty & Support')
	is_dropship_product = fields.Boolean(string="Dropshipping Product?")

class ProductCategoryTemplate(models.Model):
	_inherit = "product.public.category"
	
	# category_ids = fields.Many2many('product.public.category',string="Categories")
	brand_ids = fields.Many2many('ust.product.brand',string="Brand")
	category_description = fields.Text(string="Category Description")

