import logging
from datetime import datetime, timedelta

from odoo import api, fields, models

from ..services.anthropic_client import AnthropicClient, estimate_cost_eur
from ..services.prompt_builder import (
    build_messages_from_channel,
    build_system_prompt,
    parse_response,
)

_logger = logging.getLogger(__name__)

BOT_PARTNER_XMLID = "freemoov_livechat_ai.partner_ai_bot"


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _freemoov_ai_is_enabled(self):
        ICP = self.env["ir.config_parameter"].sudo()
        return ICP.get_param("freemoov_livechat_ai.enabled") == "True"

    def _freemoov_ai_is_dry_run(self):
        ICP = self.env["ir.config_parameter"].sudo()
        return ICP.get_param("freemoov_livechat_ai.dry_run", "True") == "True"

    def _freemoov_ai_config(self):
        ICP = self.env["ir.config_parameter"].sudo()
        return {
            "api_key": ICP.get_param("freemoov_livechat_ai.api_key") or "",
            "model": ICP.get_param("freemoov_livechat_ai.model") or "claude-haiku-4-5-20251001",
            "max_tokens": int(ICP.get_param("freemoov_livechat_ai.max_tokens") or 400),
            "delay_seconds": int(ICP.get_param("freemoov_livechat_ai.delay_seconds") or 30),
            "rate_limit_per_min": int(ICP.get_param("freemoov_livechat_ai.rate_limit_per_min") or 20),
        }

    def _freemoov_ai_check_rate_limit(self, limit_per_min):
        Log = self.env["freemoov.livechat.ai.log"].sudo()
        window = fields.Datetime.now() - timedelta(minutes=1)
        count = Log.search_count([("create_date", ">=", window), ("status", "in", ("ok", "dry_run", "escalated"))])
        return count < limit_per_min

    def _freemoov_ai_log(self, status, **kw):
        return self.env["freemoov.livechat.ai.log"].sudo().create({
            "channel_id": self.id,
            "status": status,
            **kw,
        })

    def _freemoov_ai_human_active(self, look_back_seconds=120):
        """A human (non-bot, non-visitor) has posted in the last N seconds."""
        bot = self._freemoov_ai_bot_partner()
        threshold = fields.Datetime.now() - timedelta(seconds=look_back_seconds)
        recent = self.message_ids.filtered(
            lambda m: m.create_date >= threshold
            and m.author_id
            and (not bot or m.author_id.id != bot.id)
            and m.message_type != "notification"
        )
        return bool(recent)

    def _freemoov_ai_bot_partner(self):
        try:
            return self.env.ref(BOT_PARTNER_XMLID, raise_if_not_found=False)
        except Exception:
            return False

    def _freemoov_ai_respond(self, visitor_message_text):
        """Run the AI flow for this channel and post the response.
        Returns the log record.
        """
        self.ensure_one()
        cfg = self._freemoov_ai_config()

        if not self._freemoov_ai_is_enabled():
            return self._freemoov_ai_log("skipped_disabled", visitor_message=visitor_message_text)

        if not self._freemoov_ai_check_rate_limit(cfg["rate_limit_per_min"]):
            return self._freemoov_ai_log("skipped_rate", visitor_message=visitor_message_text)

        if self._freemoov_ai_human_active():
            return self._freemoov_ai_log("skipped_human", visitor_message=visitor_message_text)

        try:
            system_prompt = build_system_prompt(self.env)
            messages = build_messages_from_channel(self)
        except Exception as e:
            _logger.exception("freemoov_ai: failed to build prompt")
            return self._freemoov_ai_log("error", visitor_message=visitor_message_text, error_message=str(e))

        client = AnthropicClient(api_key=cfg["api_key"], model=cfg["model"], max_tokens=cfg["max_tokens"])
        try:
            result = client.create_message(system_prompt, messages)
        except Exception as e:
            _logger.exception("freemoov_ai: Anthropic call failed")
            return self._freemoov_ai_log("error", visitor_message=visitor_message_text, error_message=str(e))

        text, escalate = parse_response(result["text"])
        cost = estimate_cost_eur(result["input_tokens"], result["output_tokens"])

        if self._freemoov_ai_is_dry_run():
            return self._freemoov_ai_log(
                "dry_run",
                visitor_message=visitor_message_text,
                bot_response=text,
                model=cfg["model"],
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
                cost_eur=cost,
                latency_ms=result["latency_ms"],
            )

        bot_partner = self._freemoov_ai_bot_partner()
        body = text if text else "Je n'ai pas pu formuler de réponse, je transfère à un conseiller."
        if escalate:
            body += "\n\n_💬 Un conseiller humain va prendre le relais sous peu._"

        post_kwargs = {
            "body": body,
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_comment",
        }
        if bot_partner:
            post_kwargs["author_id"] = bot_partner.id
        self.sudo().message_post(**post_kwargs)

        return self._freemoov_ai_log(
            "escalated" if escalate else "ok",
            visitor_message=visitor_message_text,
            bot_response=text,
            model=cfg["model"],
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            cost_eur=cost,
            latency_ms=result["latency_ms"],
        )

    @api.model_create_multi
    def _freemoov_ai_trigger_from_message(self, message):
        """Called after a visitor message is posted. Triggers AI if conditions met."""
        channel = self.browse(message.res_id) if message.model == "discuss.channel" else self
        if not channel or channel.channel_type != "livechat":
            return
        # Only react to visitor messages (no author_id = public website visitor)
        if message.author_id:
            return
        if message.message_type == "notification":
            return
        # Strip HTML for logging
        from ..services.prompt_builder import strip_html
        text = strip_html(message.body or "")
        if not text or len(text) < 2:
            return
        channel._freemoov_ai_respond(text)


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        for m in messages:
            if m.model == "discuss.channel" and m.res_id:
                try:
                    self.env["discuss.channel"]._freemoov_ai_trigger_from_message(m)
                except Exception:
                    _logger.exception("freemoov_ai: trigger failed")
        return messages
