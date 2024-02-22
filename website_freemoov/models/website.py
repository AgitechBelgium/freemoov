
# -*- coding: utf-8 -*-
from odoo import fields, models,api,_

class Website(models.Model):
	_inherit = 'website'


	def check_stock_availability(self,product_variant) :
		qty_avail = 0
		product_variant_id = self.env['product.product'].sudo().browse(product_variant)
		website = self.get_current_website()
		if website.warehouse_id :
			warehouse_location_id = website.warehouse_id.lot_stock_id
			stock_quant_ids = self.env['stock.quant'].sudo().search([('product_id','=',product_variant_id.id),('location_id','=',warehouse_location_id.id),('on_hand','=',True)])
			qty_avail = sum(quant.quantity for quant in stock_quant_ids)
		return qty_avail

		# def check_tmpl_stock_availability(self,product_tmpl_id) :
		# qty_avail = 0
		# for rec in self :
		# 	if rec.warehouse_id :
		# 		warehouse_location_id = rec.warehouse_id.lot_stock_id
		# 		stock_quant_ids = self.env['stock.quant'].sudo().search([('product_id','=',product_variant.id),('location_id','=',warehouse_location_id.id),('on_hand','=',True)])
		# 		qty_avail = sum(quant.quantity for quant in stock_quant_ids)
		# return qty_avail

	def get_ust_cat_data(self):
		category_ids = self.env['product.public.category'].search([('website_id', 'in', [False, self.id]), ('parent_id', '=', False)])
		return category_ids

	def get_child_category(self,category):
		return self.env['product.category'].search([('parent_id','=',category.id)])

	def category_levels(self):
		category_vals = {}
		category_ids = self.env['product.category'].search([])
		first_level_category_ids = self.env['product.category'].search([('parent_id','=',False)])
		count = 1
		if first_level_category_ids:
			category_vals.update({count:[first_level_category_ids]})
			count += 1
		left_category_ids = self.env['product.category'].search([('id','not in',first_level_category_ids.ids)])

		main_category_vals = {}
		for category in first_level_category_ids:
			child_category_ids = left_category_ids.filtered(lambda x:x.parent_id.id == category.id)

			for child_category in child_category_ids:
				category_count = 1
				no_parent_found = 0
				comp_category = child_category
				categories = []
				while no_parent_found != 1:
					if comp_category.parent_id:
						category_count += 1
						comp_category = comp_category.parent_id
						categories.append(comp_category.id)
					else:
						no_parent_found = 1
				
				if category_count not in list(category_vals.keys()):
					category_vals.update({category_count:[child_category]})

				elif category_count in list(category_vals.keys()):
					category_value = category_vals[category_count]
					category_value.append(child_category)
					category_vals[category_count] = category_value

			main_category_vals.update({category:category_vals})
		# print('\n====main_category_vals===',main_category_vals)
		return category_vals


		

		# if left_category_ids:
			# for category in left_category_ids:
			# 	category_count = 1
			# 	no_parent_found = 0
			# 	comp_category = category
			# 	categories = []
			# 	while no_parent_found != 1:
			# 		if comp_category.parent_id:
			# 			category_count += 1
			# 			comp_category = comp_category.parent_id
			# 			categories.append(comp_category.id)
			# 		else:
			# 			no_parent_found = 1
			# 	if category_count not in list(category_vals.keys()):
			# 		category_vals.update({category_count:[category]})
			# 	elif category_count in list(category_vals.keys()):
			# 		category_value = category_vals[category_count]
			# 		category_value.append(category)
			# 		category_vals[category_count] = category_value
		

