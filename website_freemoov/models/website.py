# -*- coding: utf-8 -*-
from odoo import fields, models,api,_

class Website(models.Model):
	_inherit = 'website'


	def get_ust_cat_data(self):
		category_ids = self.env['product.public.category'].search([('website_id', 'in', [False, self.id]), ('parent_id', '=', False)])
		return category_ids

