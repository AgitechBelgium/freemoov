from odoo import fields, models
from odoo.tools.sql import create_index


class AssistantApiLog(models.Model):
    """One row per authenticated call to /api/assistant/v1.

    Two jobs in one table, deliberately: the usage trail of the voice agent
    (which tool, when, how it ended) and the counter the rate limiter reads.
    Nothing about the caller is stored — the payload can carry a product id or
    a city, never an identity, since identity-bearing tools are not exposed
    over this API.
    """
    _name = "freemoov.assistant.api.log"
    _description = "Assistant HTTP API call log"
    _order = "create_date desc, id desc"
    _rec_name = "tool_name"

    tool_name = fields.Char(string="Outil", required=True)
    status = fields.Selection(
        [
            ("ok", "OK"),
            ("unknown_tool", "Outil non exposé"),
            ("invalid_json", "Corps JSON invalide"),
            ("invalid_args", "Arguments invalides"),
            ("tool_error", "Erreur de l'outil"),
            ("rate_limited", "Quota dépassé"),
        ],
        string="Status",
        required=True,
    )

    def init(self):
        # Every call reads back the last minute of this table, which grows for
        # ever: without this index the quota check degrades into a seq scan
        # that gets slower the more the API is used.
        create_index(
            self._cr,
            "freemoov_assistant_api_log_create_date_idx",
            self._table,
            ["create_date"],
        )
