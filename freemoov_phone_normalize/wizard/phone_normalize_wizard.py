import base64
import csv
import io
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

BATCH_SIZE = 200


class PhoneNormalizeWizard(models.TransientModel):
    _name = "freemoov.phone.normalize.wizard"
    _description = "Bulk phone normalization wizard (curative pass)"

    mode = fields.Selection(
        [("dry_run", "Dry run (report only)"), ("apply", "Apply changes")],
        default="dry_run",
        required=True,
    )
    scope = fields.Selection(
        [
            ("all", "All active partners with a phone or mobile"),
            ("missing_country", "Active partners without country_id"),
            ("invalid", "Partners already flagged as invalid"),
        ],
        default="all",
        required=True,
    )

    processed_count = fields.Integer(readonly=True)
    valid_count = fields.Integer(readonly=True)
    invalid_count = fields.Integer(readonly=True)
    repaired_count = fields.Integer(readonly=True)
    inferred_country_count = fields.Integer(readonly=True)
    set_country_count = fields.Integer(readonly=True)

    report_file = fields.Binary(readonly=True, attachment=False)
    report_filename = fields.Char(readonly=True)

    def _build_domain(self):
        domain = [("active", "=", True)]
        if self.scope == "missing_country":
            domain += ["|", ("phone", "!=", False), ("mobile", "!=", False), ("country_id", "=", False)]
        elif self.scope == "invalid":
            domain += ["|", ("phone_invalid", "=", True), ("mobile_invalid", "=", True)]
        else:
            domain += ["|", ("phone", "!=", False), ("mobile", "!=", False)]
        return domain

    def action_run(self):
        self.ensure_one()
        Partner = self.env["res.partner"]
        Normalizer = self.env["freemoov.phone.normalizer"]

        domain = self._build_domain()
        partners = Partner.with_context(active_test=False).search(domain)
        _logger.info("Phone normalize wizard (%s) on %d partners", self.mode, len(partners))

        rows = []
        stats = {
            "processed": 0,
            "valid": 0,
            "invalid": 0,
            "repaired": 0,
            "inferred": 0,
            "set_country": 0,
        }

        for chunk_start in range(0, len(partners), BATCH_SIZE):
            chunk = partners[chunk_start:chunk_start + BATCH_SIZE]
            for partner in chunk:
                stats["processed"] += 1
                update = {}
                signals = partner._freemoov_collect_partner_signals()
                inferred_for_record = False
                for fname in ("phone", "mobile"):
                    raw = partner[fname]
                    if not raw:
                        continue
                    res = Normalizer.normalize(raw, signals)
                    changed = res["valid"] and res["value"] != raw
                    if res["valid"]:
                        stats["valid"] += 1
                        if changed:
                            stats["repaired"] += 1
                            update[fname] = res["value"]
                        if partner[f"{fname}_invalid"]:
                            update[f"{fname}_invalid"] = False
                            update[f"{fname}_invalid_reason"] = False
                        if res["country"] and not partner.country_id and "country_id" not in update:
                            country = self.env["res.country"].search([("code", "=", res["country"])], limit=1)
                            if country:
                                update["country_id"] = country.id
                                signals["country_code"] = country.code
                                stats["set_country"] += 1
                    else:
                        stats["invalid"] += 1
                        if not partner[f"{fname}_invalid"] or partner[f"{fname}_invalid_reason"] != res["reason"]:
                            update[f"{fname}_invalid"] = True
                            update[f"{fname}_invalid_reason"] = res["reason"] or "unknown"
                    if res["country_inferred"]:
                        inferred_for_record = True
                    rows.append({
                        "partner_id": partner.id,
                        "name": partner.name or "",
                        "field": fname,
                        "raw": raw,
                        "normalized": res["value"] if res["valid"] else "",
                        "valid": res["valid"],
                        "country": res["country"] or "",
                        "country_inferred": res["country_inferred"],
                        "reason": res["reason"] or "",
                    })
                if inferred_for_record:
                    stats["inferred"] += 1
                    if not partner.phone_country_inferred:
                        update["phone_country_inferred"] = True
                if self.mode == "apply" and update:
                    super(type(partner), partner).write(update)
            if self.mode == "apply":
                self.env.cr.commit()

        report_bytes = self._build_csv(rows)
        self.write({
            "processed_count": stats["processed"],
            "valid_count": stats["valid"],
            "invalid_count": stats["invalid"],
            "repaired_count": stats["repaired"],
            "inferred_country_count": stats["inferred"],
            "set_country_count": stats["set_country"],
            "report_file": base64.b64encode(report_bytes),
            "report_filename": "freemoov_phone_normalize_%s_%s.csv" % (self.mode, self.scope),
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
            fieldnames=["partner_id", "name", "field", "raw", "normalized", "valid", "country", "country_inferred", "reason"],
        )
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")
