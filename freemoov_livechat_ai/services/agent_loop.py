"""Agentic loop: model <-> tools, capped, with per-call audit trail."""
import json
import logging
import time

import psycopg2

from . import tools
from .prompt_builder import parse_response

_logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 6
_PRODUCT_TOOLS = ("chercher_produits", "fiche_produit")

TOOL_CRASH_MSG = "Erreur interne de l'outil — proposer un transfert."
CAP_REACHED_MSG = (
    "Je n'arrive pas à aboutir sur cette demande, je préfère vous passer un conseiller."
)


def _collect_product_ids(name, result):
    """Ids to draw product cards from (Task 6).

    Two payload shapes: `chercher_produits` nests its records under
    `produits`, `fiche_produit` returns one.
    """
    if name not in _PRODUCT_TOOLS:
        return []
    if "produits" in result:
        return [p["id"] for p in result["produits"]]
    return [result["id"]] if "id" in result else []


def run_agent(env, channel, client, system_prompt, messages):
    """Answer one visitor turn, running whatever tools the model asks for.

    Two invariants hold in the tool block below, and neither is cosmetic:

    * every call goes through `tools.run_tool` — the verification gate is read
      from the database there and nowhere else, so reaching a tool function
      directly would run a sensitive tool for an unverified visitor;
    * no savepoint wraps that call. Failed identity lookups deliberately leave
      a row behind (it is what meters probing, see Task 4), and rolling back
      on `ToolError` would refund the quota it just spent.
    """
    specs = tools.anthropic_tool_specs()
    convo = list(messages)
    tool_calls, product_ids = [], []
    total_in = total_out = total_latency = 0
    escalate_forced = False
    result = None

    for _ in range(MAX_TOOL_ITERATIONS + 1):
        result = client.create_message(system_prompt, convo, tools=specs)
        total_in += result["input_tokens"]
        total_out += result["output_tokens"]
        total_latency += result["latency_ms"]

        if result["stop_reason"] != "tool_use":
            break

        convo.append({"role": "assistant", "content": result["content"]})
        tool_results = []
        for block in result["content"]:
            if block.get("type") != "tool_use":
                continue
            name, args = block["name"], block.get("input") or {}
            t0 = time.monotonic()
            try:
                out = tools.run_tool(env, channel, name, args)
                ok, payload = True, json.dumps(out, ensure_ascii=False, default=str)
                product_ids += _collect_product_ids(name, out)
            except psycopg2.Error:
                # The cursor is gone: Odoo's retrying layer has to see this.
                # Swallowed, it would become a "tool failed" string handed back
                # to the model, the loop would keep querying a dead cursor, and
                # the request would 500 much later with the cause lost.
                raise
            except tools.ToolError as exc:
                # Written to be read by the model — relayed as-is.
                ok, payload = False, json.dumps({"erreur": str(exc)}, ensure_ascii=False)
            except Exception:
                # Expected traffic, not an anomaly: the registry splats the
                # model's arguments into the tool without validating them, so a
                # hallucinated key is a TypeError and a hallucinated id a
                # ValueError. The text of those never leaves the log — it is a
                # stack-trace fragment, and the model would quote it.
                _logger.exception("freemoov_ai: tool %s crashed", name)
                ok, payload = False, json.dumps({"erreur": TOOL_CRASH_MSG}, ensure_ascii=False)
            tool_calls.append({
                "name": name, "arguments": args, "ok": ok,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            })
            tool_results.append({
                "type": "tool_result", "tool_use_id": block["id"],
                "content": payload, "is_error": not ok,
            })
        convo.append({"role": "user", "content": tool_results})
    else:
        # Cap reached: the model is still asking for tools, so its last
        # response carries no answer. Close the turn cleanly instead.
        escalate_forced = True

    text, escalate = parse_response(result["text"] if result else "")
    if escalate_forced and not text:
        text = CAP_REACHED_MSG
    return {
        "text": text,
        "escalate": escalate or escalate_forced,
        "product_ids": list(dict.fromkeys(product_ids)),
        "tool_calls": tool_calls,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "latency_ms": total_latency,
    }
