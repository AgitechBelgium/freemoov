from odoo import models, api, fields, _


class StockMove(models.Model):
	_inherit = "stock.move"

	# def _get_new_picking_values(self):
	# 	picking_values = super(StockMove, self)._get_new_picking_values()
	# 	if self._context.get('fsm_mode'):
	# 		picking_values.update({'state': 'draft'})
	# 	return picking_values

	def write(self, vals):
		res = super(StockMove, self).write(vals)
		for move in self:
			if move._context.get('is_fsm_picking') and move.state == 'done':
				move.state = 'draft'
		return res
