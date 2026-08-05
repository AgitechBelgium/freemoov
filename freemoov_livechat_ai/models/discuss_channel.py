import json
import logging
from datetime import timedelta

import psycopg2

from odoo import api, fields, models

from ..services import agent_loop
from ..services.anthropic_client import AnthropicClient, estimate_cost_eur
from ..services.prompt_builder import build_messages_from_channel, build_system_prompt
from ..services.tools.catalog import _serialize, _store_warehouses

_logger = logging.getLogger(__name__)

BOT_PARTNER_XMLID = "freemoov_livechat_ai.partner_ai_bot"
PRODUCT_CARDS_TEMPLATE = "freemoov_livechat_ai.assistant_product_cards"
MAX_PRODUCT_CARDS = 3

# Arguments the audit log must not keep verbatim. The log is readable by every
# internal user (`base.group_user`), and these two values are exactly what a
# customer types to prove who they are: `identifiant` is their e-mail, phone or
# order reference, `code` the one-time code that unlocks their orders and
# invoices. The number is how many leading characters survive — enough to tell
# two calls of the same turn apart, not enough to rebuild the value; 0 drops it
# entirely, which is the only sane amount for a code.
REDACTED_TOOL_ARGS = {"identifiant": 3, "code": 0}


def _redact_tool_calls(tool_calls):
    """The calls as they go to the log: identifying arguments truncated.

    Works on copies. The dicts it is handed carry the arguments that were
    really executed, and a redaction leaking back into them would leave the
    audit trail describing a call nobody made.
    """
    redacted = []
    for tool_call in tool_calls:
        arguments = dict(tool_call.get("arguments") or {})
        for name, keep in REDACTED_TOOL_ARGS.items():
            if name in arguments:
                arguments[name] = "%s…" % str(arguments[name])[:keep]
        redacted.append({**tool_call, "arguments": arguments})
    return redacted


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
            # Ceiling on what one conversation may spend, both directions
            # summed. 0 lifts it.
            "conversation_token_budget": int(
                ICP.get_param("freemoov_livechat_ai.conversation_token_budget") or 50000
            ),
            # Per-call HTTP timeout. It is what bounds the turn: the loop makes
            # up to MAX_TOOL_ITERATIONS + 1 calls, synchronously, inside the
            # visitor's own request, and the worker is killed at
            # `limit_time_real` (120s on Odoo.sh). 15 x 7 = 105s stays under it.
            "client_timeout": int(ICP.get_param("freemoov_livechat_ai.client_timeout") or 15),
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

    def _freemoov_ai_tokens_spent(self):
        """Tokens already billed on this conversation, both directions."""
        Log = self.env["freemoov.livechat.ai.log"].sudo()
        [(spent_in, spent_out)] = Log._read_group(
            [("channel_id", "=", self.id)],
            aggregates=["input_tokens:sum", "output_tokens:sum"],
        )
        return (spent_in or 0) + (spent_out or 0)

    def _freemoov_ai_notify_typing(self, is_typing):
        """Typing indicator, over the bot's own membership (native bus).

        The bot has to be a member for the notification to carry a persona the
        visitor's client can display, so the first turn joins the channel.
        """
        bot = self._freemoov_ai_bot_partner()
        if not bot:
            return
        member = self.channel_member_ids.filtered(lambda m: m.partner_id == bot)
        if not member:
            self.sudo().add_members(partner_ids=bot.ids, post_joined_message=False)
            member = self.channel_member_ids.filtered(lambda m: m.partner_id == bot)
        try:
            member.sudo()._notify_typing(is_typing)
        except Exception:
            # Cosmetic to the last degree: a failed indicator must never cost
            # the visitor the answer that follows it.
            _logger.debug("freemoov_ai: typing notify failed", exc_info=True)

    def _freemoov_ai_post_product_cards(self, product_ids):
        """Post the cards for the products the turn actually talked about.

        Re-checked against the database rather than trusted: the ids travelled
        through the model, and publication can change mid-conversation.
        """
        tmpls = self.env["product.template"].sudo().browse(product_ids).exists()
        tmpls = tmpls.filtered(lambda t: t.is_published and t.active)[:MAX_PRODUCT_CARDS]
        if not tmpls:
            return
        warehouse_map = _store_warehouses(self.env)
        html = self.env["ir.qweb"].sudo()._render(
            PRODUCT_CARDS_TEMPLATE,
            {"products": [_serialize(self.env, tmpl, warehouse_map) for tmpl in tmpls]},
        )
        post_kwargs = {
            "body": html,
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_comment",
        }
        bot = self._freemoov_ai_bot_partner()
        if bot:
            post_kwargs["author_id"] = bot.id
        self.sudo().message_post(**post_kwargs)

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

        # Per-conversation ceiling (spec §8). A turn now runs up to seven API
        # calls carrying the whole history, so a single long conversation can
        # cost more than a day of short ones. Checked before the prompt is even
        # built: the knowledge base is not free either.
        budget = cfg["conversation_token_budget"]
        if budget and self._freemoov_ai_tokens_spent() >= budget:
            return self._freemoov_ai_log("skipped_budget", visitor_message=visitor_message_text)

        try:
            system_prompt = build_system_prompt(self.env)
            messages = build_messages_from_channel(self)
        except Exception as e:
            _logger.exception("freemoov_ai: failed to build prompt")
            return self._freemoov_ai_log("error", visitor_message=visitor_message_text, error_message=str(e))

        client = AnthropicClient(
            api_key=cfg["api_key"],
            model=cfg["model"],
            max_tokens=cfg["max_tokens"],
            timeout=cfg["client_timeout"],
        )
        self._freemoov_ai_notify_typing(True)
        try:
            out = agent_loop.run_agent(self.env, self, client, system_prompt, messages)
        except psycopg2.Error:
            # The cursor is gone: Odoo's retrying layer has to see this one.
            # Nothing else may touch the database on the way out either — a
            # typing notification or an error log written here would raise in
            # turn and bury the failure that caused it.
            raise
        except Exception as e:
            _logger.exception("freemoov_ai: agent loop failed")
            self._freemoov_ai_notify_typing(False)
            return self._freemoov_ai_log("error", visitor_message=visitor_message_text, error_message=str(e))
        self._freemoov_ai_notify_typing(False)

        text, escalate = out["text"], out["escalate"]
        cost = estimate_cost_eur(out["input_tokens"], out["output_tokens"])
        tool_kw = {
            "tools_used": ", ".join(dict.fromkeys(c["name"] for c in out["tool_calls"])),
            "tool_calls_json": json.dumps(
                _redact_tool_calls(out["tool_calls"]), ensure_ascii=False, default=str
            ),
        }

        if self._freemoov_ai_is_dry_run():
            return self._freemoov_ai_log(
                "dry_run",
                visitor_message=visitor_message_text,
                bot_response=text,
                model=cfg["model"],
                input_tokens=out["input_tokens"],
                output_tokens=out["output_tokens"],
                cost_eur=cost,
                latency_ms=out["api_latency_ms"],
                **tool_kw,
            )

        bot_partner = self._freemoov_ai_bot_partner()
        # The loop always fills `text` when it forces an escalation, so this is
        # a last net rather than a live path — but an empty bubble is the one
        # failure a visitor cannot make sense of.
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

        if out["product_ids"] and not escalate:
            # Not under an escalation: the cards would illustrate an answer the
            # bot has just admitted it could not give, and the visitor would
            # read them as the recommendation nobody made.
            try:
                self._freemoov_ai_post_product_cards(out["product_ids"])
            except psycopg2.Error:
                raise
            except Exception:
                # Illustration, posted after the answer the visitor came for.
                # It must not cost the turn its log row: the tokens are spent
                # either way, and the conversation budget is counted from
                # exactly those rows.
                _logger.exception("freemoov_ai: product cards failed")

        return self._freemoov_ai_log(
            "escalated" if escalate else "ok",
            visitor_message=visitor_message_text,
            bot_response=text,
            model=cfg["model"],
            input_tokens=out["input_tokens"],
            output_tokens=out["output_tokens"],
            cost_eur=cost,
            latency_ms=out["api_latency_ms"],
            **tool_kw,
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
                except psycopg2.Error:
                    # Swallowed here, a serialization failure would never reach
                    # Odoo's retrying layer: the visitor's message would look
                    # posted, the cursor would already be dead, and everything
                    # downstream in the same request would 500 in cascade.
                    raise
                except Exception:
                    # Anything else stays swallowed: a bug in the assistant
                    # must not cost the visitor the message they just sent.
                    _logger.exception("freemoov_ai: trigger failed")
        return messages
