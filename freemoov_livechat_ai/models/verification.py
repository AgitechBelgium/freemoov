import hashlib
import logging
import secrets
from datetime import timedelta

from odoo import fields, models

from ..services.tools import ToolError

_logger = logging.getLogger(__name__)

CODE_TTL_MIN = 10
VERIFIED_TTL_MIN = 30
MAX_ATTEMPTS = 3
TEST_MODE_PARAM = "freemoov_livechat_ai.verification_test_mode"

# `%` and `_` are LIKE wildcards, `\` escapes them: any of the three turns an
# exact lookup into a pattern search, i.e. an enumeration oracle handed to an
# anonymous visitor ("%@%" resolves a real customer on the first try).
LIKE_METACHARS = ("%", "_", "\\")

NOT_FOUND_MSG = (
    "Je ne retrouve pas ce client. Vérifie l'e-mail ou la référence, "
    "ou propose un transfert vers un conseiller."
)
NO_SMS_MSG = (
    "Je ne peux pas envoyer le code par SMS pour le moment. "
    "Propose un transfert vers un conseiller."
)


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
    test_code_plain = fields.Char(
        string="Code (mode test)",
        groups="base.group_system",
        help="Rempli uniquement quand le mode test est actif, pour que les "
             "testeurs lisent le code sans envoi réel. Jamais rempli en production.",
    )

    # -- lookup -----------------------------------------------------------
    def _find_partner(self, identifier):
        ident = (identifier or "").strip()
        if not ident or any(char in ident for char in LIKE_METACHARS):
            # Refused before any query, and with the ordinary "not found"
            # answer: a dedicated message would tell the probe it was spotted.
            return self.env["res.partner"]
        if "@" in ident:
            return self._pick_partner(
                self.env["res.partner"].sudo().search([("email", "=ilike", ident)])
            )
        order = self.env["sale.order"].sudo().search([("name", "=ilike", ident)], limit=1)
        if order:
            return order.partner_id
        return self._find_task(ident).partner_id

    def _find_task(self, ident):
        """FSM lookup on the reference the customer actually holds.

        `moov_reparation` puts the repair sequence (RO00042) in
        `reparation_number`, not in `name` — the task name is free text with
        next to no entropy, often containing the customer's own name, and is
        not scoped to any project. It is therefore never accepted as proof of
        identity; only the reference is, and only on a Field Service project.

        `reparation_number` is only queried when `moov_reparation` is
        installed, and `is_fsm` when `industry_fsm` is: neither is a dependency
        of this module.
        """
        Task = self.env["project.task"].sudo()
        if "reparation_number" not in Task._fields:
            return Task
        domain = [("reparation_number", "=ilike", ident)]
        if "is_fsm" in self.env["project.project"]._fields:
            domain.append(("project_id.is_fsm", "=", True))
        return Task.search(domain, limit=1)

    def _pick_partner(self, partners):
        """Duplicated e-mails are the norm in this base, so `limit=1` would
        make the choice depend on row order. Pick the most recently active
        record instead: the one the customer is really using."""
        if len(partners) < 2:
            return partners
        _logger.warning(
            "freemoov_ai 2FA: identifier matches %s partners (ids=%s), "
            "picking the most recently active",
            len(partners), partners.ids,
        )
        return max(partners, key=self._activity_key)

    def _activity_key(self, partner):
        order = self.env["sale.order"].sudo().search(
            [("partner_id", "=", partner.id), ("state", "in", ("sale", "done"))],
            order="date_order desc", limit=1,
        )
        if order:
            return (2, order.date_order, partner.id)
        task = self.env["project.task"].sudo().search(
            [("partner_id", "=", partner.id)], order="write_date desc", limit=1,
        )
        if task:
            return (1, task.write_date, partner.id)
        return (0, partner.write_date, partner.id)

    @staticmethod
    def _mask(value):
        if "@" in (value or ""):
            local, _, dom = value.partition("@")
            return "%s***@%s…" % (local[:1], dom[:1])
        return "***%s" % (value or "")[-4:]

    def _hash(self, code, channel):
        return hashlib.sha256((code + str(channel.id)).encode()).hexdigest()

    # -- API --------------------------------------------------------------
    # Underscore-prefixed on purpose: `call_kw` refuses to dispatch to private
    # methods, and these two run privileged searches on behalf of an anonymous
    # visitor. They are called from the tools layer, never from the client.
    def _start_verification(self, channel, identifier):
        partner = self._find_partner(identifier)
        if not partner or not (partner.email or partner.phone):
            raise ToolError(NOT_FOUND_MSG)
        method = "email" if partner.email else "sms"
        code = "%06d" % secrets.randbelow(1_000_000)
        self.sudo().search([("channel_id", "=", channel.id), ("verified_at", "=", False)]).unlink()
        verification = self.sudo().create({
            "channel_id": channel.id,
            "partner_id": partner.id,
            "code_hash": self._hash(code, channel),
            "method": method,
            "expires_at": fields.Datetime.now() + timedelta(minutes=CODE_TTL_MIN),
        })
        verification._send_code(partner, method, code)
        target = partner.email if method == "email" else partner.phone
        return {"target_masked": self._mask(target), "method": method}

    def _check_code(self, channel, code):
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
        """Deliver the code out of band.

        The code is never logged, at any level: this process ships its logs to
        a third-party collector, and a code in a WARNING is a code in someone
        else's database. In test mode it goes to `test_code_plain`, readable
        by system users in the backend and nowhere else.
        """
        self.ensure_one()
        if self.env["ir.config_parameter"].sudo().get_param(TEST_MODE_PARAM) == "True":
            self.sudo().write({"test_code_plain": code})
            return
        if method == "email":
            self.env["mail.mail"].sudo().create({
                "email_to": partner.email,
                "subject": "Votre code de vérification Freemoov",
                "body_html": "<p>Votre code de vérification : <b>%s</b> "
                             "(valable %s minutes).</p>" % (code, CODE_TTL_MIN),
                # The mail queue would keep the body forever otherwise: the
                # code would outlive its 10 minutes as clear text in the base.
                "auto_delete": True,
            }).send()
            return
        if "sms.sms" not in self.env:
            _logger.error(
                "freemoov_ai 2FA: sms.sms unavailable, cannot deliver the code (partner id=%s)",
                partner.id,
            )
            raise ToolError(NO_SMS_MSG)
        self.env["sms.sms"].sudo().create({
            "partner_id": partner.id,
            "number": partner.phone,
            "body": "Freemoov — code de vérification : %s" % code,
        }).send()


class DiscussChannelVerification(models.Model):
    _inherit = "discuss.channel"

    def _freemoov_ai_verified_partner(self):
        """Server-side authority consumed by tools.run_tool. DB read, no cache.

        The identification expires after `VERIFIED_TTL_MIN`. The livechat
        cookie outlives it by a day, so "verified once" must not mean
        "verified all day" on a browser someone else can reach.
        """
        self.ensure_one()
        fresh_since = fields.Datetime.now() - timedelta(minutes=VERIFIED_TTL_MIN)
        rec = self.env["freemoov.livechat.verification"].sudo().search([
            ("channel_id", "=", self.id),
            ("verified_at", "!=", False),
            ("verified_at", ">=", fresh_since),
        ], limit=1, order="verified_at desc")
        # Handed back in the caller's environment: the gate answers "who", it
        # does not lend out a sudo-flavoured record to read fields with.
        return rec.partner_id.with_env(self.env) if rec else False
