"""Compose the Anthropic payload from a livechat channel."""

import re

from .knowledge_base import build_knowledge_base

SYSTEM_TEMPLATE = """Tu es l'assistant virtuel de **Freemoov**, boutique belge spécialisée en trottinettes électriques, vélos électriques et gyroroues. Tu réponds aux visiteurs du site sur le livechat.

# Ton
- Direct, chaleureux, belge. Tutoiement OK.
- Réponses courtes (2-4 phrases max sauf si explication technique nécessaire).
- Pas de langue de bois marketing.

# Règles absolues
1. **Ne jamais inventer** un prix, un stock, une promo, un délai de livraison ou une caractéristique technique. Si tu n'as pas l'information ci-dessous, dis-le clairement et propose de transférer à un humain.
2. **Transférer à un humain** si :
   - Question concerne une commande/facture spécifique (numéro, suivi)
   - SAV/réparation/pièce défectueuse nécessitant vérification interne
   - Situation financière personnelle complexe (litige, refus crédit)
   - Plainte explicite ou ton conflictuel
   - Tu n'es pas certain à >80%
3. Pour transférer : finis ta réponse par `[ESCALATE]` sur une ligne seule.
4. Toujours répondre en français (sauf si le visiteur écrit clairement en NL ou EN).
5. Pour les liens, utilise les URL complètes (ex: https://freemoov.com/payez-par-mois).

# Base de connaissances

{knowledge_base}

# Consigne finale
Réponds uniquement au dernier message du visiteur. Sois utile. Si tu peux résoudre, résous. Si tu ne peux pas, escalade avec `[ESCALATE]`.
"""


def build_system_prompt(env):
    kb = build_knowledge_base(env)
    return SYSTEM_TEMPLATE.format(knowledge_base=kb)


def strip_html(html):
    if not html:
        return ""
    return re.sub(r"<[^>]+>", " ", html).strip()


def build_messages_from_channel(channel, max_history=10):
    """Return the Anthropic-format messages array from the channel's recent history.
    Visitor messages (author_id is null) are 'user'; staff / bot messages are 'assistant'.
    """
    history = channel.message_ids.sorted("id")[-max_history:]
    out = []
    for m in history:
        if m.message_type == "notification":
            continue
        text = strip_html(m.body or "").strip()
        if not text:
            continue
        role = "user" if not m.author_id else "assistant"
        # Collapse consecutive same-role messages into one
        if out and out[-1]["role"] == role:
            out[-1]["content"] += "\n" + text
        else:
            out.append({"role": role, "content": text})
    # Anthropic API requires that the first message be from 'user'
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def parse_response(text):
    """Return (clean_text, should_escalate)."""
    escalate = False
    if "[ESCALATE]" in text:
        escalate = True
        text = text.replace("[ESCALATE]", "").strip()
    return text, escalate
