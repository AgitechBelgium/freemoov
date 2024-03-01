# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import fields, models,api,_
from odoo.tools.translate import html_translate

class ProductTemplate(models.Model):
	_inherit = "product.template"
	
	pro_description = fields.Html('Description ',translate=html_translate)
	delivery_return = fields.Html('Delivery & return',translate=html_translate)
	warranty_support = fields.Html('Warranty & Support',translate=html_translate)
	summary = fields.Html('Résumé',translate=html_translate)
	is_dropship_product = fields.Boolean(string="Dropshipping Product?")
	tab_ids = fields.One2many('ust.product.tabs', 'product_id',string="Tab")

	def dropship_product(self) :
		dropship_route = self.env.ref('stock_dropshipping.route_drop_shipping')
		is_dropship = dropship_route.id in self.route_ids.ids
		return is_dropship

	def get_stock_availability(self,website=None):
		if self.detailed_type == 'product' and not self.allow_out_of_stock_order:
			product_variant_ids = self.product_variant_ids.ids
			if website and website.warehouse_id :
				warehouse_location_id = website.warehouse_id.lot_stock_id
				stock_quant_ids = self.env['stock.quant'].sudo().search([('product_id','in',product_variant_ids),('location_id','=',warehouse_location_id.id),('on_hand','=',True)])
				qty_avail = sum(quant.quantity for quant in stock_quant_ids)
		else :
			qty_avail = 1
		
		dropship_route = self.env.ref('stock_dropshipping.route_drop_shipping')
		is_dropship = dropship_route.id in product_variant_id.route_ids.ids

		return {'qty_avail':qty_avail, 'is_dropship' : is_dropship}

class ProductCategoryTemplate(models.Model):
	_inherit = "product.public.category"
	
	# category_ids = fields.Many2many('product.public.category',string="Categories")
	brand_ids = fields.Many2many('ust.product.brand',string="Brand")
	category_description = fields.Text(string="Category Description ")
