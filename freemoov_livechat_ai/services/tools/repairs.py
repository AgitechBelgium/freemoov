"""Repair follow-up — verified identity only, and off by default.

The stage names of the FSM projects are internal wording; until the technicians
have agreed on what the customer should read, the tool stays behind
`repair_tool_enabled` and the mapping lives in a parameter.
"""
import json
import logging

from . import ToolError, register, verified_partner
from .verification_tools import VERIFICATION_HINT

_logger = logging.getLogger(__name__)

_DEFAULT_STAGE_MAP = {}  # rempli via param JSON après l'atelier techniciens
ENABLED_PARAM = "freemoov_livechat_ai.repair_tool_enabled"
STAGE_MAP_PARAM = "freemoov_livechat_ai.repair_stage_map"
DISABLED_MSG = (
    "Le suivi de réparation est indisponible dans l'assistant pour le moment — "
    "proposer un transfert vers un conseiller."
)


def _stage_map(ICP):
    raw = ICP.get_param(STAGE_MAP_PARAM)
    if not raw:
        return _DEFAULT_STAGE_MAP
    try:
        mapping = json.loads(raw)
    except ValueError:
        # A typo in a parameter must not raise mid-conversation.
        _logger.warning("Invalid JSON in %s, falling back to raw stage names", STAGE_MAP_PARAM)
        return _DEFAULT_STAGE_MAP
    if not isinstance(mapping, dict):
        _logger.warning("%s is not a JSON object, ignoring it", STAGE_MAP_PARAM)
        return _DEFAULT_STAGE_MAP
    return mapping


@register(
    "statut_reparation",
    "Dossiers de réparation récents (5 au plus) du client vérifié : référence, magasin, "
    "état, date d'ouverture. Nécessite une identité vérifiée. " + VERIFICATION_HINT,
    {"type": "object", "properties": {}},
    requires_verification=True,
)
def statut_reparation(env, channel):
    ICP = env["ir.config_parameter"].sudo()
    if ICP.get_param(ENABLED_PARAM) != "True":
        raise ToolError(DISABLED_MSG)
    partner = verified_partner(channel)
    domain = [("partner_id", "child_of", partner.commercial_partner_id.id)]
    Task = env["project.task"].sudo()
    # Same fencing as the 2FA lookup: only Field Service projects are repair
    # files. An internal task that happens to carry a customer is not one, and
    # its title is internal wording. `is_fsm` only exists with `industry_fsm`,
    # which is not a declared dependency.
    if "is_fsm" in env["project.project"]._fields:
        domain.append(("project_id.is_fsm", "=", True))
    tasks = Task.search(domain, limit=5, order="create_date desc")
    if not tasks:
        raise ToolError("Aucun dossier de réparation trouvé pour ce client.")
    stage_map = _stage_map(ICP)
    # `reparation_number` (moov_reparation) is the reference the customer holds;
    # `name` is free internal text. Fall back only where the module is absent.
    has_reference = "reparation_number" in Task._fields
    return {"reparations": [{
        "reference": (t.reparation_number or t.name) if has_reference else t.name,
        "magasin": t.project_id.name or "",
        "etat": stage_map.get(t.stage_id.name, t.stage_id.name),
        "ouvert_le": str(t.create_date.date()),
    } for t in tasks]}
