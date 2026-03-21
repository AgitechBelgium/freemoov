# Google Merchant Center — Odoo 16

Sync automatique des produits Odoo vers Google Merchant Center via le Merchant API.

## Ce que fait le module

- Sync insert/update/delete en quasi temps réel (cron 15 min + hooks write/create/unlink)
- Titres et descriptions optimisés SEO selon le type de produit (trottinettes, vélos, pièces, accessoires)
- Catégories Google (GPC) automatiques par type
- Frais de port calculés par pays (BE/FR/LU/NL) avec seuil gratuit 190€
- Custom labels (gamme de prix, marque, type, GTIN, images)
- Mode dry-run : loggue tout sans envoyer à Google
- Gestion d'erreurs : retry, compteur d'échecs, commit par produit

## Prérequis

### Google Cloud

1. Service Account avec clé JSON — [console.cloud.google.com](https://console.cloud.google.com/iam-admin/serviceaccounts?project=freemoov)
2. Merchant API activée sur le projet GCP
3. Le service account doit être Admin du Merchant Center (5345092695)

### Odoo.sh

`requirements.txt` à la racine du repo :

```
google-auth>=2.0
google-api-core>=2.0
google-shopping-merchant-products>=0.1
```

## Configuration

Paramètres > Google Merchant Center :

- **Merchant Account ID** : 5345092695
- **Data Source ID** : 10624847602
- **Service Account JSON** : uploader la clé
- **Feed** : BE / fr
- **Base URL** : https://freemoov.com
- **Sync Enabled** : oui
- **Dry Run** : oui (à désactiver quand tout est validé)

Puis activer `Export to GMC` sur les catégories e-commerce racines.

## Produits inclus / exclus

**Inclus** : trottinettes, vélos électriques, accessoires, pièces, équipement — tout ce qui est publié et dans une catégorie GMC activée.

**Exclus** : scooters (Coopop), gyroroues, monoroues — politique Google "Vehicles".

## Scripts utilitaires

```bash
# Export CSV (simulation du flux, sans API)
odoo shell -d DB < google_merchant_center/scripts/optimize_gmc_feed.py

# Charger les offer_id existants depuis le mapping GMC
odoo shell -d DB < google_merchant_center/scripts/load_gmc_offer_ids.py

# Recherche GTIN manquants
odoo shell -d DB < google_merchant_center/scripts/gmc_gtin_lookup.py
```

## Architecture

```
google_merchant_center/
├── models/
│   ├── product_template.py      # Champs GMC, hooks write/create, cron, sync
│   ├── product_public_category.py
│   ├── google_merchant_log.py
│   └── res_config_settings.py
├── services/
│   ├── gmc_feed_optimizer.py    # Logique SEO (titres, desc, GPC, shipping)
│   └── google_merchant_service.py # Client API (insert/delete/list)
├── views/
├── wizards/
├── data/ir_cron_data.xml
├── security/ir.model.access.csv
└── scripts/                     # Outils standalone (CSV, audit, GTIN)
```
