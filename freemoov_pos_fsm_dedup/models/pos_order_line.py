from odoo import models
from odoo.tools import float_compare, float_is_zero


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    def _freemoov_get_skip_qty_for_picking(self):
        """Return how much of `self.qty` (POS uom) is already shipped to customer
        on the related sale.order.line via another channel (typically FSM).

        Returns 0.0 when:
          - no sale_order_line_id is linked
          - the POS line product differs from the SOL product
          - the line is a refund (negative qty) — refunds get their own picking and
            are not impacted by FSM deliveries
          - nothing has shipped yet
        """
        self.ensure_one()
        sol = self.sale_order_line_id
        if not sol or sol.product_id != self.product_id:
            return 0.0
        if self.qty <= 0:
            return 0.0
        already_in_sol_uom = sol._freemoov_qty_already_to_customer()
        if float_is_zero(already_in_sol_uom, precision_rounding=sol.product_uom.rounding):
            return 0.0
        return sol.product_uom._compute_quantity(
            already_in_sol_uom, self.product_id.uom_id, rounding_method="HALF-UP"
        )

    def _freemoov_filter_lines_for_picking(self):
        """Return self minus lines whose linked SOL has already been fully delivered elsewhere.

        Used to avoid creating empty stock.moves for products the customer has already received.
        Partial coverage is handled at the move-vals layer (see stock.picking._prepare_stock_move_vals).
        """
        if not self:
            return self
        kept = self.env["pos.order.line"]
        for line in self:
            skip_qty = line._freemoov_get_skip_qty_for_picking()
            if skip_qty <= 0:
                kept |= line
                continue
            rounding = line.product_id.uom_id.rounding
            if float_compare(skip_qty, abs(line.qty), precision_rounding=rounding) >= 0:
                continue
            kept |= line
        return kept
