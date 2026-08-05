from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    freemoov_ai_enabled = fields.Boolean(
        string="Enable AI livechat assistant",
        config_parameter="freemoov_livechat_ai.enabled",
    )
    freemoov_ai_dry_run = fields.Boolean(
        string="Dry run (log only, do not post responses)",
        config_parameter="freemoov_livechat_ai.dry_run",
        default=True,
    )
    freemoov_ai_api_key = fields.Char(
        string="Anthropic API key",
        config_parameter="freemoov_livechat_ai.api_key",
    )
    freemoov_ai_model = fields.Char(
        string="Model",
        config_parameter="freemoov_livechat_ai.model",
        default="claude-haiku-4-5-20251001",
    )
    freemoov_ai_delay_seconds = fields.Integer(
        string="Wait before bot replies (seconds)",
        config_parameter="freemoov_livechat_ai.delay_seconds",
        default=30,
        help="Let human operators grab the conversation first.",
    )
    freemoov_ai_max_tokens = fields.Integer(
        string="Max response tokens",
        config_parameter="freemoov_livechat_ai.max_tokens",
        default=400,
    )
    freemoov_ai_rate_limit_per_min = fields.Integer(
        string="Max calls per minute (global)",
        config_parameter="freemoov_livechat_ai.rate_limit_per_min",
        default=20,
    )
