import logging

from odoo import models
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class Task(models.Model):
    _inherit = "project.task"

    def _validate_stock(self):
        """Cancel pending FSM stock_moves for SOL whose product was already delivered via POS.

        Symmetrical guard for the rare case where the customer pays at the counter BEFORE
        the technician validates the FSM task. Without this guard, native
        industry_fsm_stock._validate_stock would force-validate the FSM picking and
        add a second stock move done customer for the same product.

        Native code (industry_fsm_stock/models/project_task.py:35-110) sets
        sol.qty_delivered = sol.product_uom_qty unconditionally for FSM lines, then
        button_validates the pending pickings. We cancel pending moves on lines already
        fully delivered so neither side-effect happens.
        """
        for task in self:
            if not task.sale_order_id:
                continue
            for sol in task.sale_order_id.order_line:
                if not (sol.task_id and sol.task_id.id == task.id):
                    continue
                if sol.product_id.type not in ("product", "consu"):
                    continue
                already = sol._freemoov_qty_already_to_customer()
                rounding = sol.product_uom.rounding
                if float_compare(already, sol.product_uom_qty, precision_rounding=rounding) < 0:
                    continue
                pending = sol.move_ids.filtered(lambda m: m.state not in ("done", "cancel"))
                if not pending:
                    continue
                _logger.info(
                    "freemoov_pos_fsm_dedup: cancelling %d pending FSM move(s) for SOL %s "
                    "(already delivered via another channel: %.4f / %.4f)",
                    len(pending), sol.id, already, sol.product_uom_qty,
                )
                pending._action_cancel()
        return super()._validate_stock()
