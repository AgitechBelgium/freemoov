# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import fields, models,api,_
from odoo.tools.translate import html_translate

class ProductTemplate(models.Model):
	_inherit = "product.template"
	
	pro_description = fields.Text('Description',translate=True)
	delivery_return = fields.Text('Delivery & return',translate=True)
	warranty_support = fields.Text('Warranty & Support',translate=True)
	summary = fields.Html('Résumé',translate=html_translate)
	is_dropship_product = fields.Boolean(string="Dropshipping Product?")

class ProductCategoryTemplate(models.Model):
	_inherit = "product.public.category"
	
	# category_ids = fields.Many2many('product.public.category',string="Categories")
	brand_ids = fields.Many2many('ust.product.brand',string="Brand")
	category_description = fields.Text(string="Category Description")

