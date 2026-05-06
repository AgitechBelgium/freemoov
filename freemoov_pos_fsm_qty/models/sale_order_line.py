import logging

from odoo import api, models
from odoo.tools import float_compare, float_is_zero

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.depends(
        "task_id.fsm_done",
        "move_ids.state",
        "move_ids.product_uom_qty",
        "move_ids.location_dest_id",
    )
    def _compute_qty_delivered(self):
        """Override pos_sale's `+=` so qty_delivered is not double-counted.

        Native pos_sale (Odoo Enterprise 17, pos_sale/models/sale_order.py:60-64) does:
            super()._compute_qty_delivered()         # stock_move-based value
            for sale_line in self:
                if all pos picking done:
                    sale_line.qty_delivered += pos_qty

        When the SO was fulfilled via FSM (`industry_fsm_stock`), the stock_move
        already contributes to qty_delivered. Adding pos_qty on top double counts
        the same physical delivery.

        We detect this case after super() runs and subtract pos_qty when the FSM
        path already covered the line.
        """
        super()._compute_qty_delivered()
        for line in self:
            if not line.pos_order_line_ids:
                continue
            if line.product_id.type == "service":
                continue
            pickings = line.pos_order_line_ids.order_id.picking_ids
            if not pickings or any(p.state != "done" for p in pickings):
                continue
            if not line._freemoov_fsm_already_delivered():
                continue
            pos_qty = sum(
                line._convert_qty(line, pol.qty, "p2s") for pol in line.pos_order_line_ids
            )
            if float_is_zero(pos_qty, precision_rounding=line.product_uom.rounding):
                continue
            adjusted = line.qty_delivered - pos_qty
            if float_compare(adjusted, 0.0, precision_rounding=line.product_uom.rounding) < 0:
                _logger.warning(
                    "SO line %s: pos_qty (%s) > qty_delivered (%s); leaving native value untouched",
                    line.id, pos_qty, line.qty_delivered,
                )
                continue
            line.qty_delivered = adjusted

    def _freemoov_fsm_already_delivered(self):
        """True if a done stock_move on this line already shipped >= product_uom_qty to customer."""
        self.ensure_one()
        if not self.task_id or not self.task_id.fsm_done:
            return False
        rounding = self.product_uom.rounding
        delivered_phys = 0.0
        for move in self.move_ids:
            if move.state != "done":
                continue
            if move.location_dest_id.usage != "customer":
                continue
            delivered_phys += move.product_uom._compute_quantity(move.quantity, self.product_uom)
        return float_compare(delivered_phys, self.product_uom_qty, precision_rounding=rounding) >= 0
