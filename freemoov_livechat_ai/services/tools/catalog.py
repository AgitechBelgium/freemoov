"""Product search & detail.

Availability is never read from the website publication flag (known to be
stale). Two questions a visitor actually asks, answered separately — both are
``free_qty``, read at different places:

  * ``dispo`` — **retrait en magasin**: free stock per store, aggregated over
    every variant. ``null`` means the store has no warehouse mapped: stock is
    *not tracked* there, which is not the same as zero.
  * ``commandable`` — **commande en ligne**: what the site accepts, i.e.
    free stock in the website's own warehouse (``website_sale_stock``), or no
    stock condition at all when the product allows out-of-stock ordering, is
    not a storable good, or ships by dropshipping. That last case covers most
    of the catalog, so deriving a rupture from ``dispo`` alone would be wrong
    for the majority of products.

The two can legitimately disagree: stock in the Liège shop but not in the
website warehouse means "orderable? no — but two units waiting in Liège".
Note ``website_freemoov.get_stock_availability`` is only the display badge on
the product page; the gate that refuses a cart line lives in
``website_sale_stock.sale_order._verify_updated_quantity``.
"""
import json
import logging
import unicodedata

from . import ToolError, register

_logger = logging.getLogger(__name__)

_SEARCH_LIMIT = 5
_DISPO_NOTE = (
    "Stock indicatif — à confirmer en magasin. dispo = retrait en magasin, "
    "commandable = commande en ligne : les deux peuvent différer (stock en "
    "magasin mais commande en ligne refusée, ou l'inverse). dispo=null : stock "
    "non suivi dans ce magasin, ce n'est pas une rupture. Ne jamais annoncer un "
    "produit indisponible quand commandable vaut true."
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
        if not isinstance(override, dict):
            # A valid but scalar JSON ("3", "[]") would blow up on `key in`.
            _logger.warning("%s is not a JSON object, ignoring it", _WAREHOUSE_MAP_PARAM)
            override = {}
    warehouses = Warehouse.search([])
    mapping = {}
    for key, store in env["website"]._STORES.items():
        if key in override:
            try:
                warehouse_id = int(override[key]) if override[key] else 0
            except (TypeError, ValueError):
                # A typo in the parameter must not raise mid-conversation:
                # degrade to "untracked" and leave a trace for the admin.
                _logger.warning(
                    "Invalid warehouse id %r for store '%s' in %s",
                    override[key], key, _WAREHOUSE_MAP_PARAM,
                )
                warehouse_id = 0
            mapping[key] = Warehouse.browse(warehouse_id).exists() if warehouse_id else Warehouse
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
            # free_qty, not qty_available: never show a visitor a unit that is
            # already promised to an open order. Same semantics as the sale
            # gate in `_is_commandable`, read per store instead of on the
            # website warehouse.
            # Sum over every variant: a template is routinely out of stock on
            # its first variant while a sibling colour or battery sits on the
            # shelf.
            qty = sum(variants.with_context(warehouse=warehouse.id).mapped("free_qty"))
            dispo[store["locality"]] = int(qty)
    return dispo


def _is_commandable(env, tmpl):
    """Whether the website actually accepts the order.

    The gate is `website_sale_stock`, not the `get_stock_availability` badge:
    `sale_order._verify_updated_quantity` refuses (or trims) the cart line when
    `website._get_product_available_qty` is short, and that helper reads
    `free_qty` **in the website's own warehouse**. Two consequences the badge
    would get wrong: a reserved unit is not sellable, and stock sitting in
    another warehouse does not make a product orderable online.
    """
    website = env["website"].sudo().get_current_website()
    variants = tmpl.product_variant_ids.sudo()
    if sum(website._get_product_available_qty(variant) for variant in variants) > 0:
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
        "commandable": _is_commandable(env, tmpl),
    }
    if with_description:
        data["description"] = (tmpl.description_sale or tmpl.name)[:500]
    return data


@register(
    "chercher_produits",
    "Recherche dans le catalogue Freemoov (trottinettes, vélos, gyroroues, pièces, "
    "accessoires) par texte libre, budget maximum, marque ou catégorie. "
    "Retourne au plus 5 produits avec prix TVAC, dispo (stock disponible pour un "
    "retrait, magasin par magasin) et commandable (true = le site accepte la "
    "commande en ligne). Les deux sont indépendants : un produit peut être en "
    "magasin sans être commandable en ligne, ou commandable sans stock "
    "(précommande, dropshipping). Un magasin à null n'a pas de stock suivi, ce "
    "n'est pas une rupture.",
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
    "dispo (stock disponible pour un retrait, magasin par magasin ; null = stock "
    "non suivi dans ce magasin), commandable (true = le site accepte la commande "
    "en ligne, même sans stock en magasin), lien.",
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
