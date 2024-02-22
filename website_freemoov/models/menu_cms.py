# -*- coding: utf-8 -*-
from odoo import fields, models,api,_

class MenuCms(models.Model):
    _name = "menu.cms"
    _description = "Menu CMS"
    _rec_name = 'parent_id'
    
    parent_id = fields.Many2one('product.public.category',string="Parent Category")
    child_category_ids = fields.Many2many('product.public.category', 'child_parent_cat_menu_rel',
        'parent_id', 'child_id', string="Child categories")
    sub_category_ids = fields.Many2many('product.public.category','sub_child_cat_menu_rel',
        'child_id', 'sub_id', string="Sub categories")