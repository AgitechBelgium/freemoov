# -*- coding: utf-8 -*-
from odoo import fields, models,api,_

class BetteryDetails(models.Model):
	_name = "bettery.details"
	_description = "Bettery Details"

	name = fields.Char(string="Name")
	power = fields.Float(string="Power")
	uom_id = fields.Many2one('uom.uom', string="Unit")
	product_tmplt_id = fields.Many2one('product.template',string="Product")

class EngineDetails(models.Model):
	_name = "engine.details"
	_description = "Engine Details"

	name = fields.Char(string="Name")
	power = fields.Float(string="Power")
	uom_id = fields.Many2one('uom.uom', string="Unit")
	product_tmplt_id = fields.Many2one('product.template',string="Product")

class ModelDetails(models.Model):
	_name = "model.details"
	_description = "Model Details"

	name = fields.Char(string="Name")
	model_size = fields.Char(string="Model Size")
	uom_id = fields.Many2one('uom.uom', string="Unit")
	product_tmplt_id = fields.Many2one('product.template',string="Product")

class WaterProofingDetails(models.Model):
	_name = "waterproofing.details"
	_description = "WaterProofing Details"

	name = fields.Char(string="Name")
	water_surface_tension = fields.Float(string="Size")

	product_tmplt_id = fields.Many2one('product.template',string="Product")

class FrameDetails(models.Model):
	_name = "frame.details"
	_description = "Frame Details"

	name = fields.Char(string="Name")
	size = fields.Char(string="Size")
	uom_id = fields.Many2one('uom.uom', string="Unit")
	product_tmplt_id = fields.Many2one('product.template',string="Product")

class UnderCarriageDetails(models.Model):
	_name = "undercarriage.details"
	_description = "UnderCarriage Details"

	name = fields.Char(string="Name")
	size = fields.Char(string="Size")

	product_tmplt_id = fields.Many2one('product.template',string="Product")

class BrakingDetails(models.Model):
	_name = "braking.details"
	_description = "Braking Details"

	name = fields.Char(string="Name")
	brake_type = fields.Char(string="Type")

	product_tmplt_id = fields.Many2one('product.template',string="Product")

class LightingDetails(models.Model):
	_name = "lighting.details"
	_description = "Lighting Details"

	name = fields.Char(string="Name")
	visibility = fields.Selection([('strong','Strongly Visibility'),('average','Average Visibility'),('none','None')],default="strong")
	product_tmplt_id = fields.Many2one('product.template',string="Product")

class OptionDetails(models.Model):
	_name = "option.details"
	_description = "Option Details"

	name = fields.Char(string="Name")
	is_option = fields.Boolean(string="Is Option")
	product_tmplt_id = fields.Many2one('product.template',string="Product")
