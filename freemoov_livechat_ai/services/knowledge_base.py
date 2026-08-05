"""Build a compact knowledge base to feed the AI model as context.

Two sources: Odoo product catalog (live) + static FAQ (hardcoded below,
to be edited by the Freemoov team as their policies evolve).
"""

STATIC_FAQ = """
## Freemoov — faits essentiels (faits vrais, à citer uniquement si certains)

### Paiement
- **3x sans frais** jusqu'à 2.000€ via nos partenaires (Bancontact, VISA, MasterCard, PayPal…). Sans dossier.
- **24x avec financement** via Cetelem pour les montants plus élevés. Dossier avec justificatifs, acceptation soumise à conditions du partenaire financier.
- Page dédiée : https://freemoov.com/payez-par-mois
- Situations CPAS/chômage : le financement 24x n'est pas garanti (c'est Cetelem qui décide). Le 3x sans frais reste toujours accessible.

### Livraison
- Livraison gratuite dès 190€ d'achat.
- Délai standard : 1 à 5 jours ouvrés en Belgique.
- Retour gratuit sous 30 jours.

### Magasins
- Liège
- Namur
- Bruxelles (si applicable, à confirmer)
- Prise de rendez-vous possible pour essai ou SAV.

### Garantie et SAV
- Garantie 2 ans incluse sur toutes les trottinettes neuves.
- Services premium Freemoov inclus.
- Pour un SAV / réparation / pièce défectueuse : demander le numéro de commande et la description du problème, puis escalader à un conseiller humain.

### Législation belge (trottinettes électriques)
- Vitesse max autorisée sur voie publique : 25 km/h.
- Âge minimum : 16 ans sur voie publique.
- Casque recommandé, obligatoire pour les <16 ans sur certaines voies.
- Pas de plaque d'immatriculation ni permis pour les modèles limités 25 km/h.
- Les modèles débridés (>25 km/h) sont réservés à un usage privé (terrain privé).

### Hors périmètre
- Si la question concerne une commande spécifique, un remboursement, une plainte, une situation personnelle financière complexe ou un SAV : répondre brièvement puis transférer à un conseiller humain.
- Si la question n'est pas sûre : répondre "Je ne suis pas certain, je transfère à un conseiller" plutôt que d'inventer.
"""


def build_catalog_summary(env, max_products=40):
    """Return a compact markdown summary of top products (active, published, with price)."""
    Product = env["product.template"].sudo()
    products = Product.search(
        [
            ("is_published", "=", True),
            ("active", "=", True),
            ("sale_ok", "=", True),
        ],
        limit=max_products,
        order="list_price desc",
    )
    lines = ["## Catalogue produits (résumé, extraits)"]
    for p in products:
        stock = ""
        if hasattr(p, "qty_available"):
            try:
                qty = int(p.qty_available)
                stock = f", stock: {qty}" if qty > 0 else ", rupture"
            except Exception:
                pass
        brand = p.x_studio_marque if "x_studio_marque" in p._fields and p.x_studio_marque else ""
        brand_part = f" [{brand}]" if brand else ""
        lines.append(f"- {p.name}{brand_part} — {p.list_price:.0f}€ TVAC{stock}")
    lines.append(f"\n(Total produits publiés : ~{Product.search_count([('is_published','=',True),('active','=',True)])})")
    return "\n".join(lines)


def build_knowledge_base(env):
    return STATIC_FAQ + "\n\n" + build_catalog_summary(env)
