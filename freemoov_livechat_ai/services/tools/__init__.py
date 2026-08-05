"""Tool registry for the AI assistant.

Security invariant: authorization lives HERE, server-side. A tool flagged
`requires_verification` never runs unless the channel's verification state,
read from the database, confirms an identified partner. The LLM has no say.
"""
import logging

_logger = logging.getLogger(__name__)

TOOLS = {}


class ToolError(Exception):
    """Raised by tools; the message is safe to relay to the model."""


def register(name, description, input_schema, requires_verification=False):
    def decorator(fn):
        if name in TOOLS:
            raise ValueError("Tool already registered: %s" % name)
        TOOLS[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "requires_verification": requires_verification,
            "fn": fn,
        }
        return fn
    return decorator


def anthropic_tool_specs():
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
        for t in TOOLS.values()
    ]


def verified_partner(channel):
    """The identified customer, elevated for field reads.

    `_freemoov_ai_verified_partner` answers "who" in the *caller's* environment
    — the livechat flow runs as the public visitor, so `partner.id` is all that
    passes without privileges. Every sensitive tool reads fields (name, e-mail,
    commercial parent), so the elevation happens here, once, explicitly.

    The `ToolError` is unreachable through `run_tool`, which refuses first; it
    is there so a direct call cannot turn a missing identity into `False.sudo()`.
    """
    partner = channel._freemoov_ai_verified_partner()
    if not partner:
        raise ToolError("verification_required")
    return partner.sudo()


def run_tool(env, channel, name, arguments):
    tool = TOOLS.get(name)
    if not tool:
        raise ToolError("Outil inconnu : %s" % name)
    if tool["requires_verification"]:
        verified = getattr(channel, "_freemoov_ai_verified_partner", lambda: False)()
        if not verified:
            raise ToolError("verification_required")
    return tool["fn"](env, channel, **(arguments or {}))


# Import tool modules so they self-register (order matters: after registry defs).
from . import store_info  # noqa: E402,F401
from . import catalog  # noqa: E402,F401
from . import verification_tools  # noqa: E402,F401
from . import orders  # noqa: E402,F401
from . import repairs  # noqa: E402,F401
