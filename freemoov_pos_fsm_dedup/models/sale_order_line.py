from odoo import api, fields, models
from odoo.tools import float_round


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    delivered_via_fsm = fields.Boolean(
        string="Delivered via FSM",
        compute="_compute_delivered_via_fsm",
        store=True,
        index=True,
        help="True when a stock_move done has shipped this line's product to a customer location, "
             "either through a FSM picking or through any other channel that linked stock.move.sale_line_id.",
    )

    @api.depends("move_ids.state", "move_ids.location_dest_id", "move_ids.quantity")
    def _compute_delivered_via_fsm(self):
        for line in self:
            line.delivered_via_fsm = any(
                m.state == "done" and m.location_dest_id.usage == "customer"
                for m in line.move_ids
            )

    def _freemoov_qty_already_to_customer(self):
        """Quantity already shipped to a customer location for this SOL, expressed in `self.product_uom`.

        Aggregates two channels because POS pickings do not link their stock.move to sale_line_id:
          1. stock.move.sale_line_id == self  (FSM, manual delivery, picking confirmation)
          2. stock.move.picking_id.pos_order_id IN self.pos_order_line_ids.order_id  (POS encashment)

        UoM-safe: each move's quantity is converted into the SOL UoM before summing.
        Cancelled moves are ignored.
        """
        self.ensure_one()
        rounding = self.product_uom.rounding
        qty = 0.0
        seen_move_ids = set()

        for move in self.move_ids:
            if move.state != "done":
                continue
            if move.location_dest_id.usage != "customer":
                continue
            qty += move.product_uom._compute_quantity(move.quantity, self.product_uom, rounding_method="HALF-UP")
            seen_move_ids.add(move.id)

        for pol in self.pos_order_line_ids:
            for picking in pol.order_id.picking_ids:
                for move in picking.move_ids:
                    if move.id in seen_move_ids:
                        continue
                    if move.state != "done":
                        continue
                    if move.product_id != self.product_id:
                        continue
                    if move.location_dest_id.usage != "customer":
                        continue
                    qty += move.product_uom._compute_quantity(move.quantity, self.product_uom, rounding_method="HALF-UP")
                    seen_move_ids.add(move.id)

        return float_round(qty, precision_rounding=rounding) if rounding else qty
