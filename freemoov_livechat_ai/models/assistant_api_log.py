import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.tools.sql import create_index

_logger = logging.getLogger(__name__)

# Long enough to answer "what did the voice agent do last quarter", short
# enough that a table nothing ever reads in full does not grow for ever.
GC_RETENTION_DAYS = 90


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

    @api.model
    def _gc_api_logs(self):
        """Daily purge (cron).

        The quota only ever reads the last minute of this table, so the rest
        of it is usage history — and history that nobody trims is a table that
        grows at the rate of the API, for ever.
        """
        threshold = fields.Datetime.now() - timedelta(days=GC_RETENTION_DAYS)
        stale = self.sudo().search([("create_date", "<", threshold)])
        count = len(stale)
        stale.unlink()
        if count:
            _logger.info("freemoov_ai: purged %s assistant API log row(s)", count)
        return count

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
