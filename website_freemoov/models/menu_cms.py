# -*- coding: utf-8 -*-
from odoo import fields, models,api,_

class ChildMenu(models.Model):
    _name = 'child.menu'
    _description = "Child Menu"

    name = fields.Char('Name')
    url = fields.Char('URL')
    slider_type = fields.Selection([('main_menu', 'Main Menu'), ('sub_menu', 'Sub menu')],
                                    string="Slider Type")
    menu_id = fields.Many2one('menu.cms',string="Parent Menu")
    child_id = fields.Many2one('child.menu',string="Child Menu")
    slider_type = fields.Selection([('main_menu', 'Main Menu'), ('sub_menu', 'Sub menu')],
                                    string="Slider Type")
    child_menu_ids = fields.One2many('child.menu','child_id',string="Child menus")

class MenuCms(models.Model):
    _name = "menu.cms"
    _description = "Menu CMS"
    _rec_name = 'name'
    
    parent_id = fields.Many2one('product.public.category',string="Parent Category")
    child_category_ids = fields.Many2many('product.public.category', 'child_parent_cat_menu_rel',
        'parent_id', 'child_id', string="Child categories")
    sub_category_ids = fields.Many2many('product.public.category','sub_child_cat_menu_rel',
        'child_id', 'sub_id', string="Sub categories")
    
    design_type = fields.Selection([('1', '1'), ('2', '2'),('3', '3')],string="Design Type")
    slider_type = fields.Selection([('main_menu', 'Main Menu'), ('sub_menu', 'Sub menu')],
                                    string="Slider Type")
    
    name = fields.Char('Main menu')
    url = fields.Char('URL')
    child_menu_ids = fields.One2many('child.menu','menu_id',string="Child menus")
    
    def menu_details(self):
        lines = []
        for line in self.child_menu_ids:
            lines.append(line)
        final_data = []
        design_type = self.design_type and int(self.design_type) or 0
        if design_type and lines:
            # temp = 0
            while lines:
                x = []
                for i in range(design_type):
                    if lines:
                        x.append(lines[0])
                        lines = lines[1:]
                final_data.append(x)
        return final_data    