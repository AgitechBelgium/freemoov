# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
# Developed by Upstackers Technologies

from odoo import api, fields, models
from odoo.http import request
import base64
from odoo.addons.website_sale.controllers import main
from odoo.addons.http_routing.models.ir_http import slug


class UstProductBrand(models.Model):
    _name = 'ust.product.brand'
    _description = 'Product Brand'

    name = fields.Char("Brand name")
    description = fields.Char("Description")
    active = fields.Boolean("Active",default=True)
    brand_image = fields.Binary("Brand Image")
    brand_image_filename = fields.Char('Image FileName')


class ProductTemplate(models.Model):
    _inherit = "product.template"

    brand_id = fields.Many2one("ust.product.brand", string="Brand Name")
    prod_label_id = fields.Many2one('ust.product_label',string="Label")
    is_available_trial = fields.Boolean(string="Is available for trial?")

    @api.model
    def get_ust_product_timer(self):
        partner_id = self.env.user.partner_id
        price_list_id = partner_id.property_product_pricelist.id
        price_list_data = partner_id.property_product_pricelist
        price_rule = price_list_data._compute_price_rule(self, 1)
        
        message = ""
        prod_dict = {}
        for price_list_data in price_list_data:
            for line in price_list_data.sudo().item_ids.ids:
                item_id = self.env['product.pricelist.item'].sudo().browse(line)
                if item_id.date_start != False and item_id.before_start_datetime!= False:
                    if item_id.before_start_datetime <= fields.Datetime.now() and item_id.date_start > fields.Datetime.now():
                        is_find = True
                        message = item_id.before_start_msg
                        prod_dict.update({
                            item_id.product_tmpl_id : message,
                        })
            if self.id and price_rule.get(self.id)[1]:
                price_rule_id = price_rule.get(self.id)[1]
                if price_rule_id:
                    prod_item_ids = self.env['product.pricelist.item'].sudo().browse(price_rule_id)
                    before_data = 'false'
                    if prod_item_ids and prod_item_ids.date_end:
                        return {'prod_item_ids': prod_item_ids, 'date_end': prod_item_ids.date_end.strftime("%Y-%m-%d") + ' 00:00:00','is_show':False}
                    else:
                        prod_dict_data = ({
                            'is_show' : True,
                            'prod_dict' : prod_dict,
                        })
                        return prod_dict_data
        return False

class UstProductTabs(models.Model):
    _name = 'ust.product.tabs'
    _description = 'Product Tabs'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=1)
    name = fields.Char(string='Tab Name', translate=True, required=True)
    tab_description = fields.Html(string='Tab Description')
    product_id = fields.Many2one('product.template', string='Product Template')
    website_ids = fields.Many2many('website')

    def get_count_data(self, current_website, tab_data):
        if len(tab_data) == 0 or current_website in tab_data:
            return True
        else:
            return False

    
class UstProductTabConfigure(models.Model):
    _name = 'ust.product.tab.configure'
    _description = 'Product Tab Configure'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=1)
    name = fields.Char(string='Tab Name', translate=True, required=True)
    tab_description = fields.Html(string='Tab Description')
    product_id = fields.Many2one('product.template', string='Product Template')
    website_ids = fields.Many2many('website')

    def ust_get_tab_data(self, current_website, tab_data):
        if len(tab_data) == 0 or current_website in tab_data:
            return True
        else:
            return False


class UstProductLabel (models.Model):
    _name = 'ust.product_label'
    _description = 'Product Label'

    name = fields.Char(string="Name")
    font_color_of_label = fields.Char(string="Label Font Color", default="#ffffff")
    bg_color_of_label = fields.Char(string="Label Background Color",default="#242424")
    label_type = fields.Selection([
                    ('fill', 'Fill'),
                    ('outlinesquare', 'Outline Square'),
                    ('outlineround', 'Outline Rounded'),
                    ('rounded', 'Rounded'),
                    ('flat', 'Flat'),
                    ('fillrounded', 'Fill Rounded')
                    ],string='Label Style', default='rounded')