import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

PHONE_FIELDS = ("phone", "mobile")


class ResPartner(models.Model):
    _inherit = "res.partner"

    phone_invalid = fields.Boolean(
        string="Phone Invalid",
        index=True,
        copy=False,
        help="True when the saved phone number could not be normalized to E.164. The raw value is preserved for manual review.",
    )
    mobile_invalid = fields.Boolean(
        string="Mobile Invalid",
        index=True,
        copy=False,
    )
    phone_country_inferred = fields.Boolean(
        string="Phone Country Inferred",
        index=True,
        copy=False,
        help="True when the country used to format phone/mobile fell back to the company default (no signal on the partner).",
    )
    phone_invalid_reason = fields.Char(string="Phone Invalid Reason", copy=False)
    mobile_invalid_reason = fields.Char(string="Mobile Invalid Reason", copy=False)

    def _freemoov_collect_partner_signals(self, vals=None):
        """Snapshot the inference signals (country, vat, lang, zip) merged with incoming vals."""
        self.ensure_one() if self else None
        merged = {
            "country_code": (self.country_id.code if self else None) or None,
            "vat": self.vat if self else None,
            "lang": self.lang if self else None,
            "zip": self.zip if self else None,
        }
        if vals:
            if "country_id" in vals:
                country = self.env["res.country"].browse(vals["country_id"]) if vals["country_id"] else None
                merged["country_code"] = country.code if country else None
            for key in ("vat", "lang", "zip"):
                if key in vals:
                    merged[key] = vals[key]
        return merged

    @api.model
    def _freemoov_apply_normalization(self, vals, partner=None):
        """Mutate `vals` in place : normalize phone/mobile + populate flags + maybe set country_id.

        Returns the updated vals dict (same instance).
        """
        normalizer = self.env["freemoov.phone.normalizer"]
        signals = (partner or self.browse())._freemoov_collect_partner_signals(vals)
        any_inferred = False

        for fname in PHONE_FIELDS:
            if fname not in vals:
                continue
            raw = vals.get(fname)
            if raw is False or raw is None or raw == "":
                vals[f"{fname}_invalid"] = False
                vals[f"{fname}_invalid_reason"] = False
                continue
            res = normalizer.normalize(raw, signals)
            vals[fname] = res["value"] if res["valid"] else raw
            vals[f"{fname}_invalid"] = not res["valid"]
            vals[f"{fname}_invalid_reason"] = res["reason"] or False
            if res["country_inferred"]:
                any_inferred = True
            if res["valid"] and res["country"] and not signals.get("country_code") and "country_id" not in vals:
                country = self.env["res.country"].search([("code", "=", res["country"])], limit=1)
                if country:
                    vals["country_id"] = country.id
                    signals["country_code"] = country.code

        if any(f"{f}_invalid" in vals for f in PHONE_FIELDS):
            vals.setdefault("phone_country_inferred", any_inferred)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if any(f in vals for f in PHONE_FIELDS):
                self._freemoov_apply_normalization(vals)
        return super().create(vals_list)

    def write(self, vals):
        if not any(f in vals for f in PHONE_FIELDS):
            return super().write(vals)
        for partner in self:
            partner_vals = dict(vals)
            self._freemoov_apply_normalization(partner_vals, partner=partner)
            super(ResPartner, partner).write(partner_vals)
        return True

    def action_freemoov_normalize_phones(self):
        """Manual button : re-run normalization on the current recordset."""
        normalizer = self.env["freemoov.phone.normalizer"]
        for partner in self:
            update = {}
            signals = partner._freemoov_collect_partner_signals()
            inferred = False
            for fname in PHONE_FIELDS:
                raw = partner[fname]
                if not raw:
                    if partner[f"{fname}_invalid"] or partner[f"{fname}_invalid_reason"]:
                        update[f"{fname}_invalid"] = False
                        update[f"{fname}_invalid_reason"] = False
                    continue
                res = normalizer.normalize(raw, signals)
                if res["valid"]:
                    if res["value"] != raw:
                        update[fname] = res["value"]
                    if partner[f"{fname}_invalid"]:
                        update[f"{fname}_invalid"] = False
                        update[f"{fname}_invalid_reason"] = False
                    if res["country"] and not partner.country_id:
                        country = self.env["res.country"].search([("code", "=", res["country"])], limit=1)
                        if country:
                            update["country_id"] = country.id
                            signals["country_code"] = country.code
                else:
                    update[f"{fname}_invalid"] = True
                    update[f"{fname}_invalid_reason"] = res["reason"] or "unknown"
                if res["country_inferred"]:
                    inferred = True
            if inferred and not partner.phone_country_inferred:
                update["phone_country_inferred"] = True
            if update:
                super(ResPartner, partner).write(update)
        return True
