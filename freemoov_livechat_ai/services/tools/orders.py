"""Order status and invoice resend — verified identity only.

Everything here reads customer data on behalf of an anonymous website visitor,
so two rules hold throughout: the recordsets are explicitly `sudo()` (the
livechat runs as the public user, and `verified_partner` only elevates the
partner), and every domain is anchored on that verified partner.
"""
from . import ToolError, register, verified_partner
from .verification_tools import VERIFICATION_HINT

_STATE_FR = {
    "draft": "devis en attente", "sent": "devis envoyé",
    "sale": "confirmée", "done": "terminée", "cancel": "annulée",
}
_PICKING_FR = {
    "draft": "en préparation", "waiting": "en attente de stock",
    "confirmed": "en préparation", "assigned": "prête à expédier",
    "done": "expédiée", "cancel": "annulée",
}
INVOICE_TEMPLATE_XMLID = "account.email_template_edi_invoice"


def _partner_domain(partner):
    return [("partner_id", "child_of", partner.commercial_partner_id.id)]


def _mask_email(env, email):
    """Same masking as the verification model — domain included.

    `c***@test.be` still designates a customer on a company domain as surely as
    the full address does, which is why the model masks the domain too.
    """
    return env["freemoov.livechat.verification"]._mask(email)


@register(
    "statut_commande",
    "Commandes récentes du client vérifié : état, expédition, numéro de suivi. "
    "Nécessite une identité vérifiée (envoyer_code puis verifier_code). " + VERIFICATION_HINT,
    {"type": "object", "properties": {}},
    requires_verification=True,
)
def statut_commande(env, channel):
    partner = verified_partner(channel)
    orders = env["sale.order"].sudo().search(
        _partner_domain(partner) + [("state", "in", ("sale", "done"))],
        limit=5, order="date_order desc")
    out = []
    for o in orders:
        pickings = o.picking_ids.filtered(lambda p: p.state != "cancel")
        last = pickings.sorted("id")[-1:] if pickings else None
        # carrier_id/carrier_tracking_ref come from `delivery`, which is not a
        # declared dependency: absent it, the tool answers without the tracking
        # rather than raising in the middle of a conversation.
        carrier = last.carrier_id if last and "carrier_id" in last._fields else None
        out.append({
            "reference": o.name,
            "date": str(o.date_order.date()),
            "etat": _STATE_FR.get(o.state, o.state),
            "livraison": _PICKING_FR.get(last.state, "") if last else "",
            "transporteur": carrier.name if carrier else "",
            "numero_suivi": (last.carrier_tracking_ref or "") if carrier else "",
        })
    if not out:
        raise ToolError("Aucune commande confirmée trouvée pour ce client.")
    return {"commandes": out}


@register(
    "renvoyer_facture",
    "Renvoie la facture d'une commande à l'adresse e-mail ENREGISTRÉE du client vérifié. "
    "Ne jamais afficher le contenu de la facture ni les montants dans le chat. "
    "Nécessite une identité vérifiée. " + VERIFICATION_HINT,
    {
        "type": "object",
        "properties": {"reference_commande": {"type": "string"}},
        "required": ["reference_commande"],
    },
    requires_verification=True,
)
def renvoyer_facture(env, channel, reference_commande):
    partner = verified_partner(channel)
    Verification = env["freemoov.livechat.verification"]
    # The domain is already anchored on the verified partner, so a wildcard
    # could only reach this customer's own orders — but it would reach an
    # arbitrary one, and mail its invoice, on a reference nobody typed.
    reference = Verification._escape_like((reference_commande or "").strip())
    order = env["sale.order"].sudo().search(
        _partner_domain(partner) + [("name", "=ilike", reference)], limit=1)
    if not order:
        raise ToolError("Commande introuvable pour ce client.")
    invoice = order.invoice_ids.filtered(lambda m: m.state == "posted")[:1]
    if not invoice:
        raise ToolError("Aucune facture validée sur cette commande — proposer un transfert.")
    template = env.ref(INVOICE_TEMPLATE_XMLID, raise_if_not_found=False)
    if not template:
        raise ToolError("Envoi de facture indisponible — proposer un transfert.")
    template.sudo().send_mail(invoice.id, email_layout_xmlid="mail.mail_notification_light")
    # No amount, no line, no PDF: the answer says where it went, nothing else.
    return {"envoye_vers": _mask_email(env, partner.email)}
