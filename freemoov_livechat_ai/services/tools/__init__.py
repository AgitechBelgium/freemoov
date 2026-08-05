"""Tool registry for the AI assistant.

Security invariant: authorization lives HERE, server-side. A tool flagged
`requires_verification` never runs unless the channel's verification state,
read from the database, confirms an identified partner. The LLM has no say.

Same rule for `side_effects`: a tool that sends a code, an invoice or grants
an identity does not run while the assistant is in dry run. Observation mode
has to be observable — a turn that mails a real customer is not a rehearsal.
"""
import logging

_logger = logging.getLogger(__name__)

TOOLS = {}

DRY_RUN_PARAM = "freemoov_livechat_ai.dry_run"

# Written to be read by the model: it explains the refusal and closes the
# retry loop it would otherwise start (the tool would refuse again, and again).
DRY_RUN_MSG = (
    "Mode observation : l'assistant ne peut ni envoyer de code, ni valider "
    "une identité, ni envoyer de facture pour le moment. N'insiste pas et "
    "propose un transfert vers un conseiller."
)


class ToolError(Exception):
    """Raised by tools; the message is safe to relay to the model."""


def is_dry_run(env):
    """Observation mode, read from the database on every call.

    An absent parameter means dry run, and that default is the safe direction:
    a database where nobody has decided yet must not mail a customer.
    """
    return env["ir.config_parameter"].sudo().get_param(DRY_RUN_PARAM, "True") == "True"


def register(name, description, input_schema, requires_verification=False,
             side_effects=False):
    def decorator(fn):
        if name in TOOLS:
            raise ValueError("Tool already registered: %s" % name)
        TOOLS[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "requires_verification": requires_verification,
            # Leaves a trace outside the database: a mail, an SMS, or an
            # identity the rest of the toolbox will trust for 30 minutes.
            "side_effects": side_effects,
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
    if tool["side_effects"] and is_dry_run(env):
        # Ahead of the verification gate: this refusal is about the mode the
        # server is in, it tells the visitor nothing about themselves, and it
        # spares a privileged lookup whose answer would be thrown away.
        raise ToolError(DRY_RUN_MSG)
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
