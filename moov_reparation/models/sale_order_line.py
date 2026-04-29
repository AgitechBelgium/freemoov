import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def read_converted(self):
        diag = [
            {
                'id': sl.id,
                'order': sl.order_id.name,
                'product_id': sl.product_id.id,
                'product_name': sl.product_id.display_name,
                'product_type': sl.product_type,
                'detailed_type': sl.product_id.detailed_type,
                'display_type': sl.display_type,
                'qty': sl.product_uom_qty,
                'qty_to_invoice': sl.qty_to_invoice,
            }
            for sl in self
        ]
        results = super().read_converted()
        if self and not results:
            _logger.warning(
                "POS read_converted: input=%s records (%s), output=0 lines. "
                "Per-line state: %s",
                len(self), self.ids, diag,
            )
        elif self and len(results) < len(self):
            _logger.info(
                "POS read_converted: filtered %s/%s lines for %s. "
                "Per-line state: %s",
                len(results), len(self), self.mapped('order_id.name'), diag,
            )
        return results
