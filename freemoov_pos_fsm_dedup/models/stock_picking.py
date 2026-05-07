import logging

from odoo import api, models
from odoo.tools import float_compare, float_is_zero

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.model
    def _create_picking_from_pos_order_lines(self, location_dest_id, lines, picking_type, partner=False):
        """Strip POS lines whose product was already delivered through another channel
        (typically FSM) before letting native code build the picking.

        Native flow (see point_of_sale/models/stock_picking.py:30):
          - filter stockable + non-zero qty
          - split positive vs negative
          - create one picking per side, then call _create_move_from_pos_order_lines

        We pre-filter `lines` so that fully-delivered ones never reach the picking creation.
        Partial deliveries are not stripped here — they fall through and are adjusted in
        _prepare_stock_move_vals so the picking ships only the missing delta.
        """
        kept = lines._freemoov_filter_lines_for_picking()
        if kept != lines:
            removed = lines - kept
            _logger.info(
                "freemoov_pos_fsm_dedup: skipping %d POS line(s) already delivered via FSM (pos.order=%s, removed=%s)",
                len(removed), removed.mapped("order_id.name"), removed.ids,
            )
        if not kept:
            return self.env["stock.picking"]
        return super()._create_picking_from_pos_order_lines(location_dest_id, kept, picking_type, partner=partner)

    def _prepare_stock_move_vals(self, first_line, order_lines):
        """Adjust product_uom_qty when the SOL behind these POS lines was already partly delivered.

        Called once per (picking, product) group. We subtract the qty already shipped to
        customer through any other channel so that the move only ships the missing delta.

        Example: SO of 2 trotinettes, 1 already delivered via FSM, customer pays the remaining
        2 at the counter (he kept 1 already, takes 1 more) → POS line qty = 2, FSM has shipped 1,
        the move adjusts to 1 instead of 2.
        """
        vals = super()._prepare_stock_move_vals(first_line, order_lines)
        if not order_lines:
            return vals
        rounding = first_line.product_id.uom_id.rounding
        skip_qty = sum(line._freemoov_get_skip_qty_for_picking() for line in order_lines)
        if float_is_zero(skip_qty, precision_rounding=rounding):
            return vals
        original_qty = vals.get("product_uom_qty", 0.0)
        adjusted_qty = max(0.0, original_qty - skip_qty)
        if float_compare(adjusted_qty, original_qty, precision_rounding=rounding) == 0:
            return vals
        _logger.info(
            "freemoov_pos_fsm_dedup: adjusting move qty for product %s on picking %s "
            "(pos lines=%s, original=%.4f, already_via_fsm=%.4f, adjusted=%.4f)",
            first_line.product_id.display_name, self.name, order_lines.ids,
            original_qty, skip_qty, adjusted_qty,
        )
        vals["product_uom_qty"] = adjusted_qty
        return vals
