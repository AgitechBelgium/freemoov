# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import logging
from odoo import fields, models, api, _
from odoo.tools.translate import html_translate

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
	_inherit = "product.template"
	
	pro_description = fields.Html('Description ', translate=html_translate)
	delivery_return = fields.Html('Delivery & return', translate=html_translate)
	warranty_support = fields.Html('Warranty & Support', translate=html_translate)
	summary = fields.Html('Résumé', translate=html_translate)
	is_dropship_product = fields.Boolean(string="Dropshipping Product?")
	tab_ids = fields.One2many('ust.product.tabs', 'product_id', string="Tab")

	def dropship_product(self):
		dropship_route_id = self.env['website'].sudo()._freemoov_get_dropship_route_id()
		# sudo: public visitors have no ACL on stock.route; only a boolean leaves here
		return bool(dropship_route_id and dropship_route_id in self.sudo().route_ids.ids)

	def get_stock_availability(self, website=None):
		qty_avail = 0
		if self.detailed_type == 'product' and not self.allow_out_of_stock_order:
			product_variant_ids = self.product_variant_ids.ids
			# sudo: les visiteurs publics n'ont pas d'ACL sur stock.warehouse ;
			# seul l'id de l'emplacement sert au domaine du search sudoé. Le
			# sudo doit couvrir le test lui-même, qui lit déjà le champ.
			website_sudo = website.sudo() if website else website
			if website_sudo and website_sudo.warehouse_id:
				warehouse_location_id = website_sudo.warehouse_id.lot_stock_id
				stock_quant_ids = self.env['stock.quant'].sudo().search([
					('product_id', 'in', product_variant_ids),
					('location_id', '=', warehouse_location_id.id),
					('on_hand', '=', True)
				])
				qty_avail = sum(quant.quantity for quant in stock_quant_ids)
		else:
			qty_avail = 1

		dropship_route_id = self.env['website'].sudo()._freemoov_get_dropship_route_id()
		is_dropship = bool(dropship_route_id and dropship_route_id in self.sudo().route_ids.ids)

		return {'qty_avail': qty_avail, 'is_dropship': is_dropship}

	def _get_sales_prices(self, pricelist, fiscal_position):
		"""Force Belgian fiscal position (21% VAT) for all website visitors.

		Reuses the website-level ormcache (Website._freemoov_get_belgian_fp_id)
		to avoid running the BE fpos search() once per product on the catalog
		grid. See website.py for invalidation semantics.
		"""
		fp_id = self.env['website'].sudo()._freemoov_get_belgian_fp_id()
		if fp_id:
			fiscal_position = self.env['account.fiscal.position'].sudo().browse(fp_id)
		return super()._get_sales_prices(pricelist, fiscal_position)


class ProductCategoryTemplate(models.Model):
	_inherit = "product.public.category"
	
	brand_ids = fields.Many2many('ust.product.brand', string="Brand")
	category_description = fields.Text(string="Category Text Description")
	seo_noindex = fields.Boolean(
		string="Noindex",
		default=False,
		help="Exclure cette catégorie des indexations web si activé",
	)
	# Mêmes flags de sanitisation que website_sale.website_description :
	# indispensable pour que l'éditeur web puisse sauvegarder les snippets
	# (styles inline, grilles, formulaires) sans les tronquer.
	category_bottom_content = fields.Html(
		string="Contenu sous les produits",
		translate=html_translate,
		sanitize_overridable=True,
		sanitize_attributes=False,
		sanitize_form=False,
		help="Contenu HTML affiché en dessous de la liste des produits pour cette catégorie"
	)
