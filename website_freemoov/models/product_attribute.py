# -*- coding: utf-8 -*-
from odoo import fields, models,api,_

class ProductTemplateAttributeLineInherit(models.Model):
    _inherit = "product.template.attribute.line"

    attribute_default_val = fields.Many2one('product.attribute.value',string="Default Attribute value")

class ProductAttribute(models.Model):
    _name = "product.attribute"
    _inherit = [
        'product.attribute',
        'image.mixin',
    ]
    

