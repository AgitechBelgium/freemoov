# Référence CSV — Flux Google Merchant Center

Colonnes du fichier `gmc_feed_optimized.csv` généré par `scripts/optimize_gmc_feed.py`.

## Colonnes envoyées à Google

- **id** — offer_id unique (ref interne ou ID Odoo), max 50 car.
- **title** — Titre SEO optimisé par type, max 150 car.
- **description** — Description nettoyée (pas de HTML, pas d'URLs), max 5000 car.
- **link** — URL fiche produit (https://freemoov.com/shop/...)
- **image_link** — Image principale
- **additional_image_link** — Images supplémentaires séparées par `|` (max 10)
- **availability** — in_stock / out_of_stock / preorder / backorder
- **availability_date** — Date dispo estimée (preorder/backorder uniquement)
- **condition** — new / refurbished / used
- **price** — Prix TTC (format "1299.00 EUR")
- **sale_price** — Prix barré si applicable
- **google_product_category** — ID numérique taxonomie Google
- **product_type** — Hiérarchie interne (ex: "Mobilité électrique > Trottinette électrique")
- **brand** — Marque, max 70 car.
- **gtin** — Code-barres EAN si disponible
- **mpn** — Ref fabricant ou code article
- **identifier_exists** — yes/no (GTIN ou MPN+marque présents)
- **product_weight** — Poids en kg (réel ou estimé)
- **shipping(country:XX)** — Frais de port par pays (BE/FR/LU/NL)
- **free_shipping_threshold** — Seuil livraison gratuite (190 EUR)
- **ships_from_country** — BE
- **custom_label_0** — Gamme de prix (Premium, Haut de gamme, etc.)
- **custom_label_1** — Marque
- **custom_label_2** — Type de produit
- **custom_label_3** — Avec/Sans GTIN
- **custom_label_4** — Images multiples / Image unique

## Périmètre

Tous les produits publiés sauf scooters, gyroroues et monoroues.
Trottinettes, vélos électriques, accessoires, pièces, équipement.
