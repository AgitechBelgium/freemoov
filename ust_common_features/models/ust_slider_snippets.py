# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
# Developed by Upstackers Technologies

from odoo import api,fields,models

# All In One Slider

class UstAllInOneSlider(models.Model):
    _name = 'all_in.one.slider'
    _description = 'All In One Slider'

    name = fields.Char(string='Title',compute="get_slider_name",store=True)
    slider_name = fields.Char("Slider Name", required=True)
    active = fields.Boolean(string='Active', default=True)
    item_each_slide = fields.Selection([('2', '2'), ('3', '3'), 
                                    ('4', '4'),('5', '5'), ('6', '6')],
                                    string="Item In Each Slide",
                                    default='4', required=True)
    slider_type = fields.Selection([('brand', 'Brand'), ('blog', 'Blog'), 
                                    ('category', 'Category'),('product', 'Product')],
                                    string="Slider Type", required=True)
    speed_of_slider = fields.Integer(string="Slider Sliding Speed", default='5000')
    slider_auto_slide = fields.Boolean(string='Auto Slide', default=True)
    brand_ids = fields.Many2many('ust.product.brand',string="Brand")
    blog_ids = fields.Many2many('blog.post',string="Blog")
    category_ids = fields.Many2many('product.public.category',string="Categories")
    tabs_line_ids = fields.One2many('ust.product.tab.line', 'tabs_line_ids', 'Product Attributes')
    sub_title = fields.Char("Sub Title")

    style_type = fields.Selection([('slider', 'Slider'), 
                                    ('grid', 'Grid')],
                                    string="Style Type",
                                    default='slider', required=True)

    @api.depends('slider_name','slider_type')
    def get_slider_name(self):
        for rec in self:
            rec.name = "%s : %s" % (rec.slider_type ,rec.slider_name)

class UstProductTab(models.Model):
    _name = 'ust.product.tab'
    _description = 'Product Tab'

    name = fields.Char(name="Name",required=True)


class UstProductTabLine(models.Model):
    _name = 'ust.product.tab.line'
    _description = 'Product Tab Line'

    name = fields.Char()
    product_ids = fields.Many2many("product.template", string="Products")
    tab_id = fields.Many2one('ust.product.tab', 'Tab Name')
    tabs_line_ids = fields.Many2one('all_in.one.slider', string='Product Line')
    sub_title_line = fields.Char("Sub Title")
