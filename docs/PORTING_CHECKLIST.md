# Checklist de portage prod v16 → staging v17

Liste actionnable des éléments présents sur `origin/production` (Odoo 16) mais absents de `origin/staging` (Odoo 17), à porter avant bascule.

## Lot 1 — Cleanup staging (risque nul)

- [ ] Supprimer le fichier vide `/staging` à la racine du repo
- [ ] Supprimer le dossier `pixel_meta/` (underscore, module Upstackers v16 périmé) — garder uniquement `pixel-meta/` (tiret, Garazd v17)
- [ ] Vérifier les 3 occurrences `attrs=` résiduelles dans `website_freemoov/static/src/builder/*.xml` (legitimate new v17 builder API ou à migrer ?)

## Lot 2 — Modules Python simples

- [ ] Porter `website_freemoov/models/product_faq.py` depuis prod v16 (22 lignes)
- [ ] Ajouter `from . import product_faq` dans `website_freemoov/models/__init__.py`
- [ ] Porter `website_freemoov/views/performance_hints.xml` (13 lignes, preload hints)
- [ ] Ajouter ces fichiers dans `website_freemoov/__manifest__.py` (`data:`)

## Lot 3 — Module google_merchant_center (complet)

Module présent sur prod v16, absent de staging v17.
- [ ] Copier `google_merchant_center/` depuis prod (29 fichiers)
- [ ] Adapter `__manifest__.py` : `version: 17.0.2.1`
- [ ] Vérifier `models/product_template.py` — hooks sur `product.template` inchangés en v17
- [ ] Vérifier `models/product_public_category.py`
- [ ] Vérifier `models/res_config_settings.py`
- [ ] Vérifier `models/google_merchant_log.py`
- [ ] Vérifier `services/google_merchant_service.py` (API REST, pas de dépendance Odoo)
- [ ] Vérifier `wizards/google_merchant_sync_wizard.py` et sa vue
- [ ] Vérifier `data/ir_cron_data.xml` (cron 15min)
- [ ] Tester installation propre : `odoo -i google_merchant_center --stop-after-init`
- [ ] Tester exécution dry-run du wizard de sync

## Lot 4 — Module SEO (le plus sensible)

Énorme feature v16 (~1500 lignes) à porter avec soin.
- [ ] Copier `website_freemoov/models/seo.py` (812 lignes)
  - [ ] Vérifier `ir.http._serve_fallback()` — 301 redirects produits archivés
  - [ ] Vérifier JSON-LD generators (ProductGroup, AggregateRating, AggregateOffer, Review)
  - [ ] Vérifier override `product.template` `_compute_meta_description` (auto meta)
  - [ ] Vérifier SHIPPING_RATES / HANDLING_DAYS / RETURN_DAYS constantes
- [ ] Copier les 5 vues SEO :
  - [ ] `views/seo_head.xml` (head tags, preloads)
  - [ ] `views/seo_jsonld.xml` (JSON-LD templates)
  - [ ] `views/seo_product_enrichment.xml` (enrichissement fiche produit)
  - [ ] `views/seo_category_content.xml` (contenu bas de catégorie)
  - [ ] `views/seo_backend_form.xml` (onglet SEO backend)
- [ ] Ajouter ces fichiers dans `__manifest__.py` (`data:`)
- [ ] Vérifier que `website_freemoov.subcategory_template` existe toujours en v17 (référence utilisée dans le controller)
- [ ] Tester en local : /shop/, /shop/category/X, /shop/product/Y → voir `<script type="application/ld+json">` dans le head

## Lot 5 — Checkout refonte

Unifier le travail WIP courant (`checkout.scss` V3 "Shopify-level" 1514 lignes) avec la version prod (`cart_checkout_templates.xml` 267 lignes).
- [ ] Comparer le template WIP (`checkout_templates.xml`) vs prod (`cart_checkout_templates.xml`)
- [ ] Décider du template final (garder WIP V3 comme base)
- [ ] Merger les patterns utiles de prod (si présents)
- [ ] Porter `static/src/js/checkout.js` en ES6 module v17 (`/** @odoo-module **/`) — actuellement en `odoo.define`
- [ ] Porter `static/src/scss/checkout.scss` (WIP V3 à finaliser)
- [ ] Porter `static/src/scss/search.scss` (384 lignes, depuis prod)
- [ ] Enregistrer les assets dans `__manifest__.py`
- [ ] Tester tunnel complet : panier → informations → paiement → confirmation

## Lot 6 — Module payment_floa (port v16 → v17)

Module existant dans le repo (`payment_floa/`), version `16.0.1.0.0`. **Ne pas installer** mais porter le code pour compatibilité v17.
- [ ] Adapter `__manifest__.py` : `version: 17.0.1.0.0`
- [ ] Vérifier dépendances : `payment`, `website_sale`, `website_freemoov` (toutes compatibles v17)
- [ ] Vérifier `controllers/` — `http.route` API v17 identique
- [ ] Vérifier `models/` — `payment.provider` modèle v17 renommé (v16 était `payment.acquirer`)
- [ ] Vérifier vues `payment_floa_templates.xml` et `floa_widget_templates.xml` — QWeb v17 compatible
- [ ] Vérifier `data/payment_provider_data.xml` — structure providers v17
- [ ] Vérifier JS `floa_widget.js` — ES6 module si utilise API Odoo
- [ ] Marquer `'installable': True` mais laisser désinstallé par défaut

## Lot 7 — Migrations data v16 à absorber

Les migrations `website_freemoov/migrations/16.0.0.1.0` → `16.0.0.5.2` sur prod corrigent de la data v16. Cette data sera dans le dump migré en v17 → il faut **retranscrire leur logique en pre-migrate v17** si corrections encore nécessaires.
- [ ] Auditer chaque `16.0.0.X.X/post-migrate.py` : la correction est-elle toujours nécessaire après upgrade v17 ?
- [ ] Pour celles qui le sont : créer `website_freemoov/migrations/17.0.X.X/pre-migrate.py`
- [ ] Pour celles déjà appliquées et pérennes : documenter (ne pas retranscrire)

## Validation finale

- [ ] `docker compose up -d` local → Odoo 17 démarre sans erreur
- [ ] Installation fresh de tous les modules custom → pas d'erreur
- [ ] Parcours manuel complet : login back-office, /shop, /pos, /odoo/inventory
- [ ] Suite de tests automatisés : `odoo --test-enable --test-tags=website_freemoov,ust_common_features,moov_reparation,mask_as_done_extends,google_merchant_center,website_cookies_consent,website_google_tag`
- [ ] Réconciliation données v16/v17 → diff nul (cf `MIGRATION_PLAN.md` Phase 3)
- [ ] Push `staging` → test sur Odoo.sh staging avec dump prod frais
- [ ] Bascule prod (cf Phase 5)

## Notes

- Les migrations 17.0.0.X.X déjà présentes dans la branche staging à l'instant T sont partielles. Leur présence est trackée dans `website_freemoov/migrations/` mais leur contenu historique a pu être perdu (voir git log).
- Le `DEVIS_MIGRATION_ODOO_V17.md` dans `.local/` chiffre la prestation pour le client — à ne pas modifier sans l'accord du client.
