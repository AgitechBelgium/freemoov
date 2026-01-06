from odoo import models, api, fields, _


class Task(models.Model):
	_inherit = "project.task"

	def _validate_stock(self):
		self.ensure_one()
		all_fsm_sn_moves = self.env['stock.move']
		ml_to_create = []
		for so_line in self.sale_order_id.order_line:
			if not (so_line.task_id.is_fsm or so_line.project_id.is_fsm or so_line.fsm_lot_id):
				continue
			qty = so_line.product_uom_qty - so_line.qty_delivered
			fsm_sn_moves = self.env['stock.move']
			if not qty:
				continue
			for last_move in so_line.move_ids.filtered(
					lambda p: p.state not in ['done', 'cancel'] and p.quantity_done < qty):
				move = last_move
				fsm_sn_moves |= last_move
				while move.move_orig_ids.filtered(lambda m: m.quantity_done < qty):
					move = move.move_orig_ids
					fsm_sn_moves |= move
			for fsm_sn_move in fsm_sn_moves:
				ml_vals = fsm_sn_move._prepare_move_line_vals(quantity=0)
				task = fsm_sn_move.sale_line_id.task_id
				# if the move_line of the delivery is linked to the current task or is a taskless product, set his qty_done accordinlgy
				if not task or task == self:
					ml_vals['qty_done'] = qty - fsm_sn_move.quantity_done
				ml_vals['lot_id'] = so_line.fsm_lot_id.id
				if fsm_sn_move.product_id.tracking == "serial":
					quants = self.env['stock.quant']._gather(fsm_sn_move.product_id, fsm_sn_move.location_id,
					                                         lot_id=so_line.fsm_lot_id)
					quant = quants.filtered(lambda q: q.quantity == 1.0)[:1]
					ml_vals['location_id'] = quant.location_id.id or fsm_sn_move.location_id.id
				ml_to_create.append(ml_vals)
			all_fsm_sn_moves |= fsm_sn_moves
			# set the quantity delivered of the sol to the quantity ordered. This will be done for the service sol and the products linked to the task
			if so_line.task_id == self:
				if self._context.get('is_fsm_picking') and so_line.product_id.detailed_type == 'service':
					so_line.qty_delivered = so_line.product_uom_qty
		self.env['stock.move.line'].create(ml_to_create)
