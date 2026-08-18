
# -*- coding: utf-8 -*-
from odoo import fields, models, api, tools, _

class Website(models.Model):
	_inherit = 'website'

	@api.model
	@tools.ormcache()
	def _freemoov_get_belgian_fp_id(self):
		"""Cached lookup of the auto-apply Belgian fiscal position id.

		ormcache invalidation: the cache is keyed at the registry level (no
		args). It survives the lifetime of the worker. If an admin modifies
		`auto_apply` or the country on the BE fiscal position, restart the
		service or clear the registry cache via Settings → Technical.
		Returns the id (not a recordset) — never store recordsets in ormcache.
		"""
		fp = self.env['account.fiscal.position'].sudo().search([
			('country_id.code', '=', 'BE'),
			('auto_apply', '=', True),
		], limit=1)
		return fp.id

	@api.model
	@tools.ormcache()
	def _freemoov_get_dropship_route_id(self):
		"""Cached lookup of the stock_dropshipping route id.

		Returns False if the module is not installed. Same invalidation
		semantics as _freemoov_get_belgian_fp_id (registry-level cache,
		stable for the worker lifetime).
		"""
		route = self.env.ref(
			'stock_dropshipping.route_drop_shipping',
			raise_if_not_found=False,
		)
		return route.id if route else False

	def _get_current_fiscal_position(self):
		"""Force the Belgian fiscal position for every website visitor.

		Freemoov sells exclusively to Belgium, with prices stored HTVA in the
		catalog and a 21% VAT mapped through the auto-apply BE fiscal position.
		The native implementation resolves the fpos from GeoIP, which can fail
		on the very first hit of the product page (no geoip context yet) while
		the subsequent JS get_combination_info call resolves correctly. The
		result was a visible flash of the HTVA price (e.g. 825,62 EUR) that
		jumped to the TVAC price (999 EUR) once the variant JS booted.

		Forcing the BE fpos on every request matches the catalog behaviour
		already enforced by ProductTemplate._get_sales_prices and removes the
		FOUC. Drop this override the day Freemoov starts shipping outside BE.
		"""
		fp_id = self._freemoov_get_belgian_fp_id()
		if fp_id:
			return self.env['account.fiscal.position'].sudo().browse(fp_id)
		return super()._get_current_fiscal_position()

	def check_stock_availability(self,product_variant) :
		qty_avail = 0
		product_variant_id = self.env['product.product'].sudo().browse(product_variant)
		website = self.get_current_website()
		# sudo: pas d'ACL stock.warehouse pour le public ; seul l'id de
		# l'emplacement sert au domaine du search sudoé. Le sudo doit couvrir
		# le test lui-même, qui lit déjà le champ.
		website_sudo = website.sudo()
		if website_sudo.warehouse_id :
			warehouse_location_id = website_sudo.warehouse_id.lot_stock_id
			stock_quant_ids = self.env['stock.quant'].sudo().search([('product_id','=',product_variant_id.id),('location_id','=',warehouse_location_id.id),('on_hand','=',True)])
			qty_avail = sum(quant.quantity for quant in stock_quant_ids)

		dropship_route_id = self.sudo()._freemoov_get_dropship_route_id()
		is_dropship = bool(dropship_route_id and dropship_route_id in product_variant_id.route_ids.ids)


		return {'qty_avail' : qty_avail,'is_dropship':is_dropship}

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


	def get_website_menu_data(self):
		menu_cms_records = self.env['menu.cms'].search([])
		vals = []
		for menu_cms in menu_cms_records : 
			vals.append({
				'menu' : menu_cms,
				'slider_type' : menu_cms.slider_type,
				'line_data' : menu_cms.menu_details(),
			})

		return vals
