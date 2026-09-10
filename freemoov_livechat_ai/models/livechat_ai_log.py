from odoo import fields, models


class LivechatAILog(models.Model):
    _name = "freemoov.livechat.ai.log"
    _description = "Livechat AI call log"
    _order = "create_date desc"
    _rec_name = "channel_id"

    channel_id = fields.Many2one("discuss.channel", string="Channel", ondelete="set null")
    visitor_message = fields.Text(string="Visitor message")
    bot_response = fields.Text(string="Bot response")
    system_prompt_sha = fields.Char(string="System prompt SHA", size=12)
    model = fields.Char(string="Model")
    input_tokens = fields.Integer(string="Input tokens")
    output_tokens = fields.Integer(string="Output tokens")
    cost_eur = fields.Float(string="Estimated cost (€)", digits=(10, 5))
    latency_ms = fields.Integer(string="Latency (ms)")
    tools_used = fields.Char(string="Outils utilisés")
    knowledge_sources = fields.Json(string="Révisions documentaires consultées")
    verified_partner_id = fields.Integer(
        string="Client vérifié (id)",
        help="Partner the visitor had proven to be when the turn ran, 0 if "
             "none. Deliberately a plain integer rather than a foreign key: "
             "an audit trail must survive the deletion of what it points at, "
             "and must not make the log a lever to read customer records.",
    )
    tool_calls_json = fields.Text(
        string="Détail des appels d'outils",
        help="Audit trail of the turn: one entry per tool call, with its "
             "arguments, its outcome and its duration. Identifying arguments "
             "are truncated before they are stored.",
    )
    status = fields.Selection(
        [
            ("ok", "OK"),
            ("dry_run", "Dry run"),
            ("skipped_human", "Skipped (human active)"),
            ("skipped_rate", "Skipped (rate limit)"),
            ("skipped_disabled", "Skipped (disabled)"),
            ("skipped_budget", "Skipped (token budget spent)"),
            ("escalated", "Escalated to human"),
            ("error", "Error"),
        ],
        string="Status",
        required=True,
    )
    error_message = fields.Text(string="Error")
