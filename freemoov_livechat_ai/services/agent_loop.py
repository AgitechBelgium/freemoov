"""Agentic loop: model <-> tools, capped, with per-call audit trail."""
import json
import logging
import re
import time
from urllib.parse import urlsplit

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
TRUNCATED_MSG = (
    "Ma réponse a été coupée avant la fin, je préfère vous passer un conseiller "
    "plutôt que de vous laisser une information incomplète."
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


def _recommended_product_ids(text, product_urls):
    """Only links in the final answer, allowlisted by successful tool results.

    No name guessing or arbitrary id extraction: an unlinked result must not
    look like a recommendation. Ignore query/fragment tracking, keep host and
    full path checks, deduplicate in the order the visitor reads the answer.
    """
    def key(url):
        parts = urlsplit(url)
        return parts.scheme, parts.netloc, parts.path

    allowed = {key(url): product_id for url, product_id in product_urls.items()}
    ids = []
    for url in re.findall(r'https?://[^\s<>"\[\]]+', text):
        try:
            product_id = allowed.get(key(url.rstrip(').,;!?:')))
        except ValueError:
            continue
        if product_id and product_id not in ids:
            ids.append(product_id)
    return ids


def _pending_typed_code(env, channel, messages, visitor_message_text=None):
    """Only a unique six-digit value from THIS visitor turn may be checked.

    Do not interpret a product reference as a code outside a pending flow, or
    guess which of two pasted values the visitor intended. Dry run never grants
    an identity or consumes attempts.
    """
    if tools.is_dry_run(env) or not messages or messages[-1].get('role') != 'user':
        return None
    content = visitor_message_text if visitor_message_text is not None else messages[-1].get('content')
    if not isinstance(content, str):
        return None
    codes = re.findall(r'(?<!\w)[0-9]{6}(?!\w)', content)
    if len(codes) != 1:
        return None
    pending = env['freemoov.livechat.verification'].sudo().search_count([
        ('channel_id', '=', channel.id), ('outcome', '=', 'sent'),
        ('verified_at', '=', False), ('superseded', '=', False),
    ])
    return codes[0] if pending else None


def run_agent(env, channel, client, system_prompt, messages, visitor_message_text=None):
    """Answer one visitor turn, running whatever tools the model asks for.

    Four invariants hold below, none of them cosmetic:

    * every call goes through `tools.run_tool` — the verification gate is read
      from the database there and nowhere else, so reaching a tool function
      directly would run a sensitive tool for an unverified visitor;
    * no savepoint wraps that call. Failed identity lookups deliberately leave
      a row behind (it is what meters probing, see Task 4), and rolling back
      on `ToolError` would refund the quota it just spent;
    * nothing runs on the iteration past the budget. Its results could not be
      sent back to the model anyway, and several tools have real side effects
      (`envoyer_code` mails a code, `renvoyer_facture` mails an invoice and
      has no per-channel cap of its own);
    * a `max_tokens` stop is a truncation, not an answer: the cut lands
      mid-block, so any `tool_use` in it carries arguments the model never
      finished writing, and the text is half a sentence.

    `api_latency_ms` is the API time alone. Wall time for the turn is that plus
    `sum(call["duration_ms"] for call in tool_calls)`.
    """
    specs = tools.anthropic_tool_specs()
    convo = list(messages)
    tool_calls, product_urls = [], {}
    total_in = total_out = total_latency = 0
    # Set when the turn has to end on a canned sentence: whatever the model
    # said last is then unusable, and saying it anyway would mislead.
    forced_text = None
    result = None

    code = _pending_typed_code(env, channel, messages, visitor_message_text)
    if code:
        # Validation belongs to the server, not to the model's willingness to
        # call a tool. Keep the SAME registry gate, attempt limits and audit.
        started = time.monotonic()
        verification = tools.run_tool(env, channel, 'verifier_code', {'code': code})
        tool_calls.append({'name': 'verifier_code', 'arguments': {'code': code}, 'ok': True,
                           'duration_ms': int((time.monotonic() - started) * 1000)})
        if not verification['verifie']:
            remaining = verification['essais_restants']
            text = ('Ce code est incorrect. Il reste %s essais.' % remaining if remaining else
                    'Ce code n’est plus valable. Demande un nouveau code de vérification.')
            return {'text': text, 'escalate': False, 'product_ids': [], 'tool_calls': tool_calls,
                    'input_tokens': 0, 'output_tokens': 0, 'api_latency_ms': 0}
        # Resume the real pending request with the verified result in the
        # protocol, as if the model had correctly requested the validation.
        convo.extend([
            {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 'verification_preflight',
                                             'name': 'verifier_code', 'input': {'code': code}}]},
            {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'verification_preflight',
                                        'content': json.dumps(verification), 'is_error': False}]},
        ])
        system_prompt += ('\nLe code du dernier message vient d’être validé par le serveur. '
                          'Ne le vérifie pas une seconde fois ; poursuis la demande du visiteur '
                          'avec l’outil de commande ou de réparation approprié.')

    for iteration in range(MAX_TOOL_ITERATIONS + 1):
        result = client.create_message(system_prompt, convo, tools=specs)
        total_in += result["input_tokens"]
        total_out += result["output_tokens"]
        total_latency += result["latency_ms"]

        if result["stop_reason"] == "max_tokens":
            # Ahead of the generic break below, which would otherwise take this
            # for an ordinary end of turn. A truncated response is not an
            # answer: the cut lands mid-block, so the text is half a sentence
            # (the cut can fall inside a price or a URL) and a `tool_use` in it
            # carries arguments the model never finished writing.
            forced_text = TRUNCATED_MSG
            break

        if result["stop_reason"] != "tool_use":
            break

        if iteration == MAX_TOOL_ITERATIONS:
            # Budget spent. Stop *before* executing: these results can no
            # longer be reported to the model, and the sends they trigger are
            # real ones the visitor would never hear about.
            forced_text = CAP_REACHED_MSG
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
            else:
                ok, payload = True, json.dumps(out, ensure_ascii=False, default=str)
                # Out of the `except` reach on purpose: a bug in our own
                # collection code must not be reported to the model as a failed
                # lookup on a lookup that succeeded.
                found_ids = _collect_product_ids(name, out)
                if found_ids:
                    for product in out.get('produits', [out]):
                        if product.get('id') in found_ids and product.get('url'):
                            product_urls[product['url']] = product['id']
            tool_calls.append({
                "name": name, "arguments": args, "ok": ok,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            })
            tool_results.append({
                "type": "tool_result", "tool_use_id": block["id"],
                "content": payload, "is_error": not ok,
            })
        if not tool_results:
            # `tool_use` announced, no block to run. An empty `content` array
            # is a 400, and looping would re-send a dangling assistant turn the
            # API refuses too, so the turn ends here.
            _logger.warning("freemoov_ai: tool_use stop reason with no tool_use block")
            forced_text = CAP_REACHED_MSG
            break
        convo.append({"role": "user", "content": tool_results})

    text, escalate = parse_response(result["text"] if result else "")
    if forced_text:
        text = forced_text
    return {
        "text": text,
        "escalate": escalate or bool(forced_text),
        "product_ids": [] if escalate or forced_text else _recommended_product_ids(text, product_urls),
        "tool_calls": tool_calls,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "api_latency_ms": total_latency,
    }
