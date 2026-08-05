"""Server-to-server tool API (voice agent socle). Public tools only in v1.

The registry already decides what a tool may do; this module decides what the
network may reach, and that is a different question with three answers of its
own:

* **what is exposed** — a hardcoded allow-list, re-checked against the
  registry's own ``requires_verification`` flag. An identity-bearing tool has
  no visitor to identify behind a shared server token, so it must drop off this
  surface the day it is flagged, without anyone remembering to edit the list;
* **what an error says** — a constant string. Never the exception text (it
  names internals), never anything read from the request (the token, the
  headers, the body), so a caller cannot use the API as an echo;
* **what a database error does** — nothing here catches it. ``ToolError`` is
  a 422 and a bad argument is a 400, but a ``psycopg2`` exception travels up
  untouched, which is what lets Odoo roll the transaction back and retry it.

The token is a shared secret in a header: HTTPS is not optional in production,
and the API stays off (403) as long as the parameter is empty.
"""
import hmac
import json
import logging
from datetime import timedelta

from odoo import fields, http
from odoo.http import request

from ..services import tools

_logger = logging.getLogger(__name__)

PUBLIC_HTTP_TOOLS = {"infos_magasins", "chercher_produits", "fiche_produit"}

_TOKEN_PARAM = "freemoov_livechat_ai.api_token"
_RATE_PARAM = "freemoov_livechat_ai.api_rate_per_min"
_DEFAULT_RATE_PER_MIN = 60
_LOG_MODEL = "freemoov.assistant.api.log"
# Sentinel for the discovery endpoint: wrapped in underscores so it can never
# collide with a tool name, which the registry builds from identifiers.
_LIST_TOOLS = "__tools__"
# The name comes from the URL, so its length is the caller's choice.
_MAX_LOGGED_NAME = 64
_JSON_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


def _public_tool(name):
    """The registry entry of a tool this API may serve, or None."""
    if name not in PUBLIC_HTTP_TOOLS:
        return None
    tool = tools.TOOLS.get(name)
    if not tool or tool["requires_verification"]:
        return None
    return tool


def _contradicts_schema(tool, arguments):
    """Cheap type gate in front of the tool signature.

    Not a JSON-Schema validator: it checks only what the tool itself declares.
    The point is not politeness — ``budget_max`` lands in a search domain,
    where a string is a psycopg2 error, i.e. a 500 and a rolled-back
    transaction for what is merely a caller mistake. A missing required
    argument is caught here for the same reason it is caught by the signature:
    to answer 400 rather than let it become anything else.
    """
    schema = tool.get("input_schema") or {}
    properties = schema.get("properties") or {}
    if any(name not in arguments for name in schema.get("required") or []):
        return True
    for name, value in arguments.items():
        expected = _JSON_TYPES.get((properties.get(name) or {}).get("type"))
        if expected is None or value is None:
            # Undeclared argument: the tool signature refuses it on its own,
            # and a null is left to the tool to interpret.
            continue
        if expected is not bool and isinstance(value, bool):
            # JSON true is not a number, whatever Python thinks of it.
            return True
        if not isinstance(value, expected):
            return True
    return False


class AssistantApiController(http.Controller):

    # --- plumbing ---------------------------------------------------------

    def _authenticated(self):
        expected = (request.env["ir.config_parameter"].sudo()
                    .get_param(_TOKEN_PARAM) or "").strip()
        if not expected:
            return False  # no token configured means API off, not API open
        provided = (request.httprequest.headers.get("X-Assistant-Token") or "").strip()
        # Bytes on both sides: compare_digest refuses two `str` as soon as one
        # holds a non-ASCII character, and that TypeError would turn a wrong
        # key into a 500.
        return hmac.compare_digest(expected.encode(), provided.encode())

    def _rate_per_min(self):
        raw = request.env["ir.config_parameter"].sudo().get_param(_RATE_PARAM)
        try:
            limit = int(raw)
        except (TypeError, ValueError):
            limit = 0
        if limit <= 0:
            if raw:
                _logger.warning(
                    "Invalid %s (%r), falling back to %s calls/min",
                    _RATE_PARAM, raw, _DEFAULT_RATE_PER_MIN,
                )
            # Deliberately no "unlimited" and no "zero" value: the supported
            # way to close the API is to empty the token.
            return _DEFAULT_RATE_PER_MIN
        return limit

    def _quota_reached(self):
        """Guard-rail, not a strict limiter.

        Rows land at the end of their own transaction, so two simultaneous
        calls can both pass — acceptable for a server-to-server token, and the
        alternative (a lock, or a counter committed up front) would serialize
        the API to protect it against its only legitimate caller. Refusals are
        excluded from the count: counting them would keep the throttle closed
        for as long as the caller keeps knocking.
        """
        window = fields.Datetime.now() - timedelta(minutes=1)
        count = request.env[_LOG_MODEL].sudo().search_count([
            ("create_date", ">=", window),
            ("status", "!=", "rate_limited"),
        ])
        return count >= self._rate_per_min()

    def _log(self, tool_name, status):
        request.env[_LOG_MODEL].sudo().create({
            "tool_name": (tool_name or "?")[:_MAX_LOGGED_NAME],
            "status": status,
        })

    def _reply(self, payload, status=200, headers=None):
        headers = list(headers or []) + [("Cache-Control", "no-store")]
        return request.make_json_response(payload, headers=headers, status=status)

    def _refuse(self, status, error, headers=None):
        return self._reply({"error": error}, status=status, headers=headers)

    def _forbidden(self):
        # Nothing is written to the database on this path: an unauthenticated
        # caller must not be able to make the server store rows, let alone
        # rows the quota counts. Logged at INFO because scanners hitting a
        # public URL are noise, not an incident.
        _logger.info(
            "Rejected assistant API call from %s", request.httprequest.remote_addr)
        return self._refuse(403, "forbidden")

    def _too_many(self, tool_name):
        self._log(tool_name, "rate_limited")
        return self._refuse(429, "rate_limited", headers=[("Retry-After", "60")])

    # --- routes -----------------------------------------------------------

    @http.route("/api/assistant/v1/tools", type="http", auth="public",
                methods=["GET"], csrf=False)
    def list_tools(self, **kwargs):
        if not self._authenticated():
            return self._forbidden()
        if self._quota_reached():
            return self._too_many(_LIST_TOOLS)
        self._log(_LIST_TOOLS, "ok")
        specs = [s for s in tools.anthropic_tool_specs() if _public_tool(s["name"])]
        return self._reply({"tools": specs})

    @http.route("/api/assistant/v1/call/<string:tool_name>", type="http",
                auth="public", methods=["POST"], csrf=False)
    def call_tool(self, tool_name, **kwargs):
        if not self._authenticated():
            return self._forbidden()
        if self._quota_reached():
            return self._too_many(tool_name)
        tool = _public_tool(tool_name)
        if not tool:
            self._log(tool_name, "unknown_tool")
            return self._refuse(404, "unknown_tool")

        try:
            body = json.loads(request.httprequest.get_data() or b"{}")
        except ValueError:
            self._log(tool_name, "invalid_json")
            return self._refuse(400, "invalid_json")
        if not isinstance(body, dict):
            self._log(tool_name, "invalid_json")
            return self._refuse(400, "invalid_json")

        arguments = body.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict) or _contradicts_schema(tool, arguments):
            self._log(tool_name, "invalid_args")
            return self._refuse(400, "invalid_arguments")

        try:
            # channel=None: the tools reachable here never read it (the
            # registry's `getattr(channel, ...)` default is what makes that
            # safe), and those that would are refused above.
            result = tools.run_tool(request.env, None, tool_name, arguments)
        except tools.ToolError as exc:
            self._log(tool_name, "tool_error")
            # Registry contract: a ToolError message is written to be relayed.
            return self._refuse(422, str(exc))
        except (TypeError, ValueError):
            # An argument shape the type gate above could not see. The
            # exception text names internals, so it stays in the server log.
            _logger.info("Invalid arguments for tool %s", tool_name, exc_info=True)
            self._log(tool_name, "invalid_args")
            return self._refuse(400, "invalid_arguments")

        # Serialization stays out of the try: a payload Odoo cannot encode is a
        # bug on our side, not a caller mistake to report as a 400.
        self._log(tool_name, "ok")
        return self._reply(result)
