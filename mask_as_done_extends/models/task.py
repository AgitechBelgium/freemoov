from odoo import models


class Task(models.Model):
    _inherit = "project.task"

    # v16 _validate_stock override removed — it referenced stock.move.quantity_done
    # which no longer exists in v17 (renamed to stock.move.quantity).
    # industry_fsm_stock._validate_stock() handles serial tracking + service
    # products natively in v17, covering the same cases as the old override.
