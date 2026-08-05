import hashlib
import logging
import secrets
from datetime import timedelta

from odoo import fields, models

from ..services.tools import ToolError

_logger = logging.getLogger(__name__)

CODE_TTL_MIN = 10
MAX_ATTEMPTS = 3


class LivechatVerification(models.Model):
    _name = "freemoov.livechat.verification"
    _description = "Vérification d'identité livechat (2FA)"
    _order = "id desc"

    channel_id = fields.Many2one("discuss.channel", required=True, index=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", required=True)
    code_hash = fields.Char(required=True)
    method = fields.Selection([("email", "E-mail"), ("sms", "SMS")], required=True)
    expires_at = fields.Datetime(required=True)
    attempts = fields.Integer(default=0)
    verified_at = fields.Datetime()

    # -- lookup -----------------------------------------------------------
    def _find_partner(self, identifier):
        ident = (identifier or "").strip()
        if not ident:
            return self.env["res.partner"]
        if "@" in ident:
            return self.env["res.partner"].sudo().search([("email", "=ilike", ident)], limit=1)
        order = self.env["sale.order"].sudo().search([("name", "=ilike", ident)], limit=1)
        if order:
            return order.partner_id
        task = self._find_task(ident)
        return task.partner_id if task else self.env["res.partner"]

    def _find_task(self, ident):
        """FSM lookup on the reference the customer actually holds.

        `moov_reparation` puts the repair sequence (RO00042) in
        `reparation_number`, not in `name` — the task name is free text. The
        field is only queried when that module is installed, since it is not a
        dependency here. Matching is exact-but-case-insensitive on purpose: a
        substring match would resolve a fragment like "RO9" to whichever
        customer happens to share it, send them a code, and hand the visitor
        back their masked address.
        """
        Task = self.env["project.task"].sudo()
        domain = [("name", "=ilike", ident)]
        if "reparation_number" in Task._fields:
            domain = ["|", ("reparation_number", "=ilike", ident)] + domain
        return Task.search(domain, limit=1)

    @staticmethod
    def _mask(value):
        if "@" in (value or ""):
            local, _, dom = value.partition("@")
            return "%s***@%s" % (local[:1], dom)
        return "***%s" % (value or "")[-4:]

    def _hash(self, code, channel):
        return hashlib.sha256((code + str(channel.id)).encode()).hexdigest()

    # -- API --------------------------------------------------------------
    def start_verification(self, channel, identifier):
        partner = self._find_partner(identifier)
        if not partner or not (partner.email or partner.phone):
            raise ToolError(
                "Je ne retrouve pas ce client. Vérifie l'e-mail ou la référence, "
                "ou propose un transfert vers un conseiller."
            )
        method = "email" if partner.email else "sms"
        code = "%06d" % secrets.randbelow(1_000_000)
        self.sudo().search([("channel_id", "=", channel.id), ("verified_at", "=", False)]).unlink()
        self.sudo().create({
            "channel_id": channel.id,
            "partner_id": partner.id,
            "code_hash": self._hash(code, channel),
            "method": method,
            "expires_at": fields.Datetime.now() + timedelta(minutes=CODE_TTL_MIN),
        })
        self._send_code(partner, method, code)
        target = partner.email if method == "email" else partner.phone
        return {"target_masked": self._mask(target), "method": method}

    def check_code(self, channel, code):
        rec = self.sudo().search([
            ("channel_id", "=", channel.id), ("verified_at", "=", False),
        ], limit=1)
        if not rec or rec.expires_at < fields.Datetime.now() or rec.attempts >= MAX_ATTEMPTS:
            return {"verified": False, "attempts_left": 0}
        if rec.code_hash != self._hash((code or "").strip(), channel):
            rec.attempts += 1
            return {"verified": False, "attempts_left": MAX_ATTEMPTS - rec.attempts}
        rec.verified_at = fields.Datetime.now()
        return {"verified": True, "attempts_left": MAX_ATTEMPTS - rec.attempts}

    # -- envoi ------------------------------------------------------------
    def _send_code(self, partner, method, code):
        ICP = self.env["ir.config_parameter"].sudo()
        if ICP.get_param("freemoov_livechat_ai.verification_test_mode") == "True":
            _logger.warning("freemoov_ai 2FA TEST MODE — code pour %s : %s", partner.name, code)
            return
        if method == "email":
            self.env["mail.mail"].sudo().create({
                "email_to": partner.email,
                "subject": "Votre code de vérification Freemoov",
                "body_html": "<p>Votre code de vérification : <b>%s</b> "
                             "(valable %s minutes).</p>" % (code, CODE_TTL_MIN),
            }).send()
        else:
            self.env["sms.sms"].sudo().create({
                "partner_id": partner.id,
                "number": partner.phone,
                "body": "Freemoov — code de vérification : %s" % code,
            }).send()


class DiscussChannelVerification(models.Model):
    _inherit = "discuss.channel"

    def _freemoov_ai_verified_partner(self):
        """Server-side authority consumed by tools.run_tool. DB read, no cache."""
        self.ensure_one()
        rec = self.env["freemoov.livechat.verification"].sudo().search([
            ("channel_id", "=", self.id), ("verified_at", "!=", False),
        ], limit=1, order="verified_at desc")
        return rec.partner_id if rec else False
