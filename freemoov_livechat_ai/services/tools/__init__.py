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


def run_tool(env, channel, name, arguments):
    tool = TOOLS.get(name)
    if not tool:
        raise ToolError("Outil inconnu : %s" % name)
    if tool["requires_verification"]:
        verified = getattr(channel, "_freemoov_ai_verified_partner", lambda: False)()
        if not verified:
            raise ToolError("verification_required")
    return tool["fn"](env, channel, **(arguments or {}))
