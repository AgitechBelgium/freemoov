"""Product search & detail.

Availability is never read from the website publication flag (known to be
stale). Two orthogonal facts are exposed, and the model needs both:

  * ``dispo`` — free stock per store, aggregated over every variant.
    ``null`` means the store has no warehouse mapped: stock is *not tracked*
    there, which is not the same as zero.
  * ``commandable`` — whether the site actually accepts an order. A product
    with no stock anywhere is still orderable when it allows out-of-stock
    ordering, is not a storable good, or ships by dropshipping. Mirrors
    ``website_freemoov.product_template.get_stock_availability``; most of the
    catalog falls in that case, so deriving a rupture from ``dispo`` alone
    would be wrong for the majority of products.
"""
import json
import logging
import unicodedata

from . import ToolError, register

_logger = logging.getLogger(__name__)

_SEARCH_LIMIT = 5
_DISPO_NOTE = (
    "Stock indicatif — à confirmer en magasin. dispo=null : stock non suivi dans "
    "ce magasin, ce n'est pas une rupture. Ne jamais annoncer un produit "
    "indisponible quand commandable vaut true."
)
_WAREHOUSE_MAP_PARAM = "freemoov_livechat_ai.store_warehouse_map"


def _normalize(value):
    """Lowercase and strip accents, so 'Liege' matches 'Freemoov Liège'."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _brand(tmpl):
    if "x_studio_marque" in tmpl._fields and tmpl.x_studio_marque:
        return str(tmpl.x_studio_marque)
    return ""


def _store_warehouses(env):
    """Map each store key of ``website._STORES`` to a warehouse recordset.

    Resolution order: the JSON override in ``_WAREHOUSE_MAP_PARAM``
    (``{"liege": 3, "charleroi": null}``) wins, a null value declaring a store
    with no warehouse; otherwise the warehouse whose name contains the store
    locality. Deliberately not a bare ``search([])``: logistics or supplier
    warehouses must never surface to a visitor as a shop counter.
    """
    Warehouse = env["stock.warehouse"].sudo()
    override = {}
    raw = env["ir.config_parameter"].sudo().get_param(_WAREHOUSE_MAP_PARAM)
    if raw:
        try:
            override = json.loads(raw)
        except ValueError:
            _logger.warning(
                "Invalid JSON in %s, falling back to name matching", _WAREHOUSE_MAP_PARAM
            )
    warehouses = Warehouse.search([])
    mapping = {}
    for key, store in env["website"]._STORES.items():
        if key in override:
            warehouse_id = override[key]
            mapping[key] = Warehouse.browse(int(warehouse_id)).exists() if warehouse_id else Warehouse
            continue
        locality = _normalize(store["locality"])
        mapping[key] = next(
            (w for w in warehouses if locality in _normalize(w.name)), Warehouse
        )
    return mapping


def _dispo_by_store(env, tmpl, warehouse_map):
    variants = tmpl.product_variant_ids.sudo()
    dispo = {}
    for key, store in env["website"]._STORES.items():
        warehouse = warehouse_map.get(key)
        if not warehouse:
            dispo[store["locality"]] = None
        elif not variants:
            dispo[store["locality"]] = 0
        else:
            # Sum over every variant: a template is routinely out of stock on
            # its first variant while a sibling colour or battery sits on the
            # shelf.
            qty = sum(variants.with_context(warehouse=warehouse.id).mapped("free_qty"))
            dispo[store["locality"]] = int(qty)
    return dispo


def _is_commandable(tmpl, dispo):
    """Whether the website lets a visitor order the product right now."""
    if any((qty or 0) > 0 for qty in dispo.values()):
        return True
    if tmpl.allow_out_of_stock_order or tmpl.detailed_type != "product":
        return True
    return bool(tmpl.dropship_product())


def _serialize(env, tmpl, warehouse_map, with_description=False):
    dispo = _dispo_by_store(env, tmpl, warehouse_map)
    data = {
        "id": tmpl.id,
        "nom": tmpl.name,
        "prix_tvac": round(tmpl.list_price, 2),
        "marque": _brand(tmpl),
        "url": "https://www.freemoov.com%s" % (tmpl.website_url or ""),
        "dispo": dispo,
        "commandable": _is_commandable(tmpl, dispo),
    }
    if with_description:
        data["description"] = (tmpl.description_sale or tmpl.name)[:500]
    return data


@register(
    "chercher_produits",
    "Recherche dans le catalogue Freemoov (trottinettes, vélos, gyroroues, pièces, "
    "accessoires) par texte libre, budget maximum, marque ou catégorie. "
    "Retourne au plus 5 produits avec prix TVAC, le stock par magasin (dispo) et "
    "commandable. Un stock à 0 ne signifie pas indisponible : si commandable vaut "
    "true, le produit se commande en ligne (précommande, dropshipping). Un magasin "
    "à null n'a pas de stock suivi, ne pas l'annoncer en rupture.",
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
    warehouse_map = _store_warehouses(env)
    return {
        "produits": [_serialize(env, t, warehouse_map) for t in tmpls],
        "note": _DISPO_NOTE,
    }


@register(
    "fiche_produit",
    "Détail d'un produit (id retourné par chercher_produits) : description, prix, "
    "stock par magasin (dispo, null = stock non suivi dans ce magasin), commandable "
    "(true = commande possible en ligne même sans stock), lien.",
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
    data = _serialize(env, tmpl, _store_warehouses(env), with_description=True)
    data["note"] = _DISPO_NOTE
    return data
