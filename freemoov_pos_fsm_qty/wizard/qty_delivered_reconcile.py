import base64
import csv
import io
import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)

BATCH_SIZE = 200


class QtyDeliveredReconcileWizard(models.TransientModel):
    _name = "freemoov.qty.delivered.reconcile.wizard"
    _description = "Recompute qty_delivered for SO lines double-counted by pos_sale"

    mode = fields.Selection(
        [("dry_run", "Dry run (report only)"), ("apply", "Apply: invalidate cache and force recompute")],
        default="dry_run",
        required=True,
    )

    affected_count = fields.Integer(readonly=True)
    fixed_count = fields.Integer(readonly=True)
    skipped_count = fields.Integer(readonly=True)
    report_file = fields.Binary(readonly=True, attachment=False)
    report_filename = fields.Char(readonly=True)

    def _candidate_lines(self):
        domain = [
            ("order_id.state", "in", ["sale", "done"]),
            ("product_uom_qty", ">", 0),
            ("qty_delivered", ">", 0),
            ("pos_order_line_ids", "!=", False),
        ]
        return self.env["sale.order.line"].search(domain)

    def action_run(self):
        self.ensure_one()
        SaleOrderLine = self.env["sale.order.line"]
        candidates = self._candidate_lines()
        rows = []
        affected, fixed, skipped = 0, 0, 0
        wizard_id = self.id

        for chunk_start in range(0, len(candidates), BATCH_SIZE):
            chunk = candidates[chunk_start:chunk_start + BATCH_SIZE]
            for line in chunk:
                qty_before = line.qty_delivered
                if qty_before <= line.product_uom_qty:
                    continue
                line.invalidate_recordset(fnames=["qty_delivered"])
                line._compute_qty_delivered()
                qty_after = line.qty_delivered
                changed = qty_after != qty_before
                if changed:
                    fixed += 1
                else:
                    skipped += 1
                affected += 1
                rows.append({
                    "sol_id": line.id,
                    "order": line.order_id.name,
                    "product": (line.product_id.display_name or "")[:60],
                    "product_uom_qty": line.product_uom_qty,
                    "qty_before": qty_before,
                    "qty_after": qty_after,
                    "delta": qty_after - qty_before,
                    "fsm_done": bool(line.task_id and line.task_id.fsm_done),
                    "pos_orders": ", ".join(line.pos_order_line_ids.mapped("order_id.name")),
                })
                if self.mode == "dry_run":
                    line.qty_delivered = qty_before
            if self.mode == "apply":
                self.env.flush_all()
                self.env.cr.commit()

        report_bytes = self._build_csv(rows)
        self.write({
            "affected_count": affected,
            "fixed_count": fixed,
            "skipped_count": skipped,
            "report_file": base64.b64encode(report_bytes),
            "report_filename": "freemoov_qty_delivered_%s.csv" % self.mode,
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @staticmethod
    def _build_csv(rows):
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "sol_id", "order", "product", "product_uom_qty",
                "qty_before", "qty_after", "delta", "fsm_done", "pos_orders",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")
