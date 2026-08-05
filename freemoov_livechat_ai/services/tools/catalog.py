"""Product search & detail. Availability read from stock per warehouse,
never from the website publication flag (known to be stale)."""
from . import ToolError, register

_SEARCH_LIMIT = 5
_DISPO_NOTE = "Stock indicatif — à confirmer en magasin."


def _brand(tmpl):
    if "x_studio_marque" in tmpl._fields and tmpl.x_studio_marque:
        return str(tmpl.x_studio_marque)
    return ""


def _dispo_by_store(env, tmpl):
    variant = tmpl.product_variant_ids[:1]
    if not variant:
        return {}
    dispo = {}
    for wh in env["stock.warehouse"].sudo().search([]):
        qty = variant.sudo().with_context(warehouse=wh.id).free_qty
        dispo[wh.name] = int(qty)
    return dispo


def _serialize(env, tmpl, with_description=False):
    data = {
        "id": tmpl.id,
        "nom": tmpl.name,
        "prix_tvac": round(tmpl.list_price, 2),
        "marque": _brand(tmpl),
        "url": "https://www.freemoov.com%s" % (tmpl.website_url or ""),
        "dispo": _dispo_by_store(env, tmpl),
    }
    if with_description:
        data["description"] = (tmpl.description_sale or tmpl.name)[:500]
    return data


@register(
    "chercher_produits",
    "Recherche dans le catalogue Freemoov (trottinettes, vélos, gyroroues, pièces, "
    "accessoires) par texte libre, budget maximum, marque ou catégorie. "
    "Retourne au plus 5 produits avec prix TVAC et stock par magasin.",
    {
        "type": "object",
        "properties": {
            "recherche": {"type": "string"},
            "budget_max": {"type": "number"},
            "marque": {"type": "string"},
            "categorie": {"type": "string"},
        },
    },
)
def chercher_produits(env, channel, recherche=None, budget_max=None, marque=None, categorie=None):
    domain = [("is_published", "=", True), ("active", "=", True), ("sale_ok", "=", True)]
    if recherche:
        domain.append(("name", "ilike", recherche))
    if budget_max:
        domain.append(("list_price", "<=", budget_max))
    if categorie:
        domain.append(("public_categ_ids.name", "ilike", categorie))
    tmpls = env["product.template"].sudo().search(domain, limit=40, order="list_price desc")
    if marque:
        tmpls = tmpls.filtered(lambda t: marque.lower() in _brand(t).lower())
    tmpls = tmpls[:_SEARCH_LIMIT]
    return {"produits": [_serialize(env, t) for t in tmpls], "note": _DISPO_NOTE}


@register(
    "fiche_produit",
    "Détail d'un produit (id retourné par chercher_produits) : description, prix, "
    "stock par magasin, lien.",
    {
        "type": "object",
        "properties": {"product_id": {"type": "integer"}},
        "required": ["product_id"],
    },
)
def fiche_produit(env, channel, product_id):
    tmpl = env["product.template"].sudo().browse(int(product_id))
    if not tmpl.exists() or not tmpl.is_published or not tmpl.active:
        raise ToolError("Produit introuvable ou non publié.")
    data = _serialize(env, tmpl, with_description=True)
    data["note"] = _DISPO_NOTE
    return data
