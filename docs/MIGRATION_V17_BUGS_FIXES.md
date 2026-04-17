# Migration v16 → v17 : bugs rencontrés et corrections

Document de travail pour suivre les divergences v16→v17 détectées pendant
la phase de staging local, et les corrections à déployer en production.

Base de travail : commit `95cd00c` de `origin/production` (prod v16 au
13 avril 2026), restauré dans `freemoov_v17` (DB locale v17).

---

## 1. Structure du repo

### 1.1 `origin/staging` (local) était en retard de 5+ commits sur `origin/staging` (distant)

**Symptôme** : `git status` affichait 184 fichiers modifiés alors qu'on avait
seulement quelques modifs WIP.

**Cause** : HEAD local pointait sur un ancien merge `production→staging`
(`2bd5290`) alors que `origin/staging` distant avait tous les commits
`fix(odoo17)` récents.

**Fix local** : `git reset --mixed origin/staging` (non destructif, WT
intact). Backup préalable dans `.local/backups-wip/<timestamp>/`.

**À faire prod** : aucun. État distant toujours la référence.

---

## 2. Templates et vues

### 2.1 SCSS / views dégradés sur `origin/staging` par rapport à `origin/production`

**Symptôme** : header sans mega-menu, icônes Odoo par défaut, stats-grid
vertical au lieu d'horizontal, pas de TVAC, pas de Payez-en-Nx.

**Cause** : `origin/staging` ne contenait qu'une version simplifiée des SCSS
et des templates — les refontes successives des derniers mois n'ont été
faites QUE sur `origin/production`.

**Fix** : `git checkout origin/production -- <files>` sur :
- `website_freemoov/static/src/scss/` (header.scss, footer.scss,
  product_detail.scss, shop.scss, homepage.scss, common.scss, feather.css,
  search.scss)
- `website_freemoov/views/` (header_freemoov_template_1.xml,
  footer_template.xml, inherited_template.xml, homepage_template.xml,
  header_freemoov_template.xml, inherited_product_template_view.xml)
- `website_freemoov/static/src/img/` (32 PNG)
- `website_freemoov/static/src/fonts/` (feather webfont)

**À faire prod** : rien, tout le port est dans le commit qui va être
poussé vers `origin/staging` puis mergé vers `main`/`production` au deploy.

### 2.2 Image directory `static/src/img/` manquant sur `origin/staging`

**Symptôme** : `<img src="/website_freemoov/static/src/img/user.png"/>` →
404, icônes cart/user/wishlist cassées.

**Cause** : le dossier `img/` n'était pas dans `origin/staging` (simplification
passée). Il existait dans `origin/production`.

**Fix** : restauré via `git checkout origin/production -- website_freemoov/static/src/img`.

---

## 3. Breaking changes Odoo v16 → v17

### 3.1 Template `sale.badge_extra_price` renommé en `website_sale.badge_extra_price`

**Symptôme** : `ValueError: View 'sale.badge_extra_price' in website 1 not found`
lors du rendu de `/shop`.

**Fix fichier** : `sed 's|sale\.badge_extra_price|website_sale.badge_extra_price|g'`
dans `views/inherited_template.xml` (6 occurrences).

### 3.2 `badge_extra_price` v17 exige `combination_info` dans le scope

**Symptôme** : `TypeError: 'NoneType' object is not subscriptable` dans
`website_sale/models/product_template_attribute_value.py::_get_extra_price`.

**Cause** : en v17 le template core utilise `combination_info['currency']`,
alors qu'en v16 il fonctionnait sans. Les appels `<t t-call="...badge_extra_price"/>`
depuis notre inherit `inherit_buttons` (shop listing) ne passent pas de
`combination_info`.

**Fix actuel** : remplacement des 6 `<t t-call="website_sale.badge_extra_price"/>`
par un commentaire `<!-- removed v17: ... -->`.

**Dette technique** : les badges "+5€" sur les attributs de variante (dans
le shop listing) ne s'affichent plus. À reconnecter proprement si besoin en
passant `combination_info` via un wrapper template.

### 3.3 XPath `//li/a/i` ne match plus sur les icônes header

**Symptôme** : `Element '<xpath expr="//li/a/i">' cannot be located in parent view`
pour `inherit_header_cart_link`, `inherit_user_dropdown`,
`inherit_header_wishlist_link`.

**Cause** : en v17 l'icône `<i class="fa fa-shopping-cart">` est wrappée
dans un `<div t-attf-class="#{_icon_wrap_class}">` à l'intérieur du `<a>` —
elle n'est plus fille directe du `<a>`.

**Fix** : `//i[contains(@t-attf-class, 'fa-...') or contains(@class, 'fa-...')]`
(ciblage via attribute au lieu de path strict).

**Warning restant** : Odoo logue
`Error-prone use of @class in view [...] use the hasclass(*classes) function`.
Non-bloquant mais à nettoyer (préférer `hasclass('fa-...')` dès que le xpath
original match en v17, ce qui devient possible car `<i>` a une class
statique `fa-stack` même si `fa-user` passe via `t-attf-class`).

### 3.4 QWeb JS templates : `inherit_id` v16 n'est pas supporté en v17

**Symptôme** : OWL error côté console —
`Missing template: "website_sale_stock.product_availability"`.

**Cause** : notre `<t t-name="website_freemoov.product_availability"
inherit_id="website_sale_stock.product_availability">` dans
`static/src/xml/stock_availability.xml` utilisait la syntaxe v16.
En v17, les QWeb frontend templates n'acceptent plus `inherit_id` — il
faut `t-inherit` + `t-inherit-mode="extension"`.

**Fix** :
```xml
<t t-name="website_sale_stock.product_availability"
   t-inherit="website_sale_stock.product_availability"
   t-inherit-mode="extension">
    <xpath expr="..." position="replace">...</xpath>
</t>
```

### 3.5 `odoo.define(...)` v16 → `@odoo-module` v17

**Symptôme** :
`Uncaught Error: Dependencies should be defined by an array: function(require){'use strict';var publicWidget=...`.
Conséquences : scroll bloqué, menu hover HS, erreurs OWL en cascade.

**Cause** : `website_freemoov/static/src/js/checkout.js` utilisait
`odoo.define('...', function (require) { var publicWidget = require('web.public.widget'); ... })`.
v17 ne supporte plus cette syntaxe legacy — il faut ES modules.

**Fix** : réécriture en `/** @odoo-module **/` avec
`import publicWidget from "@web/legacy/js/public/public_widget";`.

### 3.6 Groupes Odoo v17 : `account.group_show_line_subtotals_tax_*` supprimés

**Symptôme** : COW `website_sale.tax_indication` active en DB (avec l'arch
"TVAC + Payez en 3x") mais non rendu côté site.

**Cause** : l'arch du COW contenait
`groups="account.group_show_line_subtotals_tax_excluded/included"`.
En v17, ces groupes n'existent plus — le contrôle est passé à un field
`website.show_line_subtotals_tax_selection` ('tax_excluded' / 'tax_included').

**Fix** : remplacement dans le post-migrate `17.0.0.9.3` :
```
groups="account.group_show_line_subtotals_tax_excluded"
  → t-if="website.show_line_subtotals_tax_selection == 'tax_excluded'"
groups="account.group_show_line_subtotals_tax_included"
  → t-if="website.show_line_subtotals_tax_selection == 'tax_included'"
```

Le script réécrit tout le arch v17-compliant et gère les 3 langues
(en_US/fr_FR → "Payez en 6x ou 24x", fr_BE → "Payez en 3x ou 24x").

### 3.7 `is_view_active()` ne résout pas vers la COW website

**Symptôme** : `website_sale.tax_indication` a un COW active=true
(`website_id=1`) mais `is_view_active('website_sale.tax_indication')`
retourne False → le t-call n'est pas rendu.

**Cause** : `is_view_active` appelle `viewref(key)` qui retourne la vue
"générique" (non-COW) si elle existe. En v17 cette vue est active=False
par défaut — donc `is_view_active` = False même si la COW est active.

**Fix** : activer la vue générique via post-migrate (force `active=True`
sur `website_sale.tax_indication` non-COW). Le COW prend toujours le
dessus au rendu.

### 3.8 Template core `header_cart_link` / `user_dropdown` / `wishlist_link`
wrappent désormais `<i>` dans un `<div>`

Déjà traité au 3.3. Impact supplémentaire : le CSS `.nav-item > a > i`
ne s'applique plus si utilisé avec sélecteurs fils directs.

### 3.9 Panier : `<table id="cart_products">` → `<div id="cart_products">`

**Symptôme** : 500 Internal Server Error sur `/shop/cart` après upgrade v17.
```
ValueError: xpath "//table[@id='cart_products']" ne peut être localisé
Template: website_sale.cart
```

**Cause** : en v16 `website_sale.cart_lines` rendait un `<table>` avec les
lignes du panier. En v17 c'est un `<div id="cart_products"
class="js_cart_lines d-flex flex-column mb32">` avec des sous-`<div
class="o_cart_product d-flex ...">` — structure flex/card au lieu de table.

**Fix** : post-migrate `17.0.0.9.4` remplace tous les xpath
`//table[@id='cart_products']` par `//div[@id='cart_products']` dans les
COWs concernés (idempotent). En local 1 COW affecté :
`website_sale.suggested_products_list` (accessoires recommandés CMS).

---

## 4. Theme customizer et COWs v16 résiduels

### 4.1 COWs v16 avec arch cassé en v17

**Symptôme** : après restore du dump v16, certains templates affichent
partiellement ou pas du tout.

**Cause** : les COWs (vues website-specific créées par le website builder)
conservent l'arch du moment où l'user a cliqué. Si cet arch utilise des
xpath ou des attributs v16 incompatibles v17, les parties concernées
échouent silencieusement (Odoo ignore les xpath qui ne matchent plus).

**Stratégie** :
- Pour les COWs qu'on contrôle (header/footer/inherit_* du module) : les
  supprimer via le post-migrate `17.0.0.9.0` (déjà existant) pour que le
  code du disque soit utilisé.
- Pour les COWs qui contiennent des edits CMS (produits, category pages,
  snippets custom) : les garder et patcher localement l'arch (c'est ce
  qu'on fait pour `tax_indication` dans 17.0.0.9.3).

### 4.2 Mode Grille forcé (list switcher désactivé)

**Symptôme** : sur v17 après restore, le switcher grid/list apparaît sur
les pages catégorie. Prod v16 ne l'affichait pas — mode grid uniquement.

**Cause** : `website_sale.add_grid_or_list_option` est active=True par
défaut en v17. Prod l'avait désactivée (probablement via theme customizer
shop > options).

**Fix** : post-migrate `17.0.0.9.3` force
`website_sale.add_grid_or_list_option.active = False`.

---

## 5. Erreurs console encore présentes (non bloquantes)

### 5.1 `Uncaught ReferenceError: gtag is not defined`
Google Tag Manager non chargé sur staging (normal, tag GTM ne s'injecte
qu'en prod). Aucune action.

### 5.2 `Hotjar only works over HTTPS`
Idem — staging sans HTTPS, Hotjar ignore. Aucune action.

### 5.3 `Missing template: "web.OverlayContainer"` / `web_editor.UploadProgressToast`
Erreurs OWL core Odoo qu'on observe même sur des installations propres
en mode public (templates lazy-loaded jamais importés). Non bloquant.

---

## 6. Checklist de déploiement production

À la mise en prod (merge `staging` → `main` → deploy Odoo.sh prod) :

- [ ] Bump version manifest `17.0.0.9.3` → (next version) si des fixes
      DB post-deploy sont requis
- [ ] Vérifier que le dump de prod v16 a bien été converti via Odoo
      Upgrade Service (schéma v17)
- [ ] Lancer `-u website_freemoov,google_merchant_center` après restore
      → déclenche les post-migrate 17.0.0.9.* qui nettoient les COWs,
      réactivent les icônes, fixent le TVAC, désactivent le grid switcher
- [ ] Checker manuellement sur la prod déployée :
  - [ ] Mega-menu desktop hover + mobile click
  - [ ] Icônes header (cart/user/wishlist custom PNG)
  - [ ] TVAC + "Payez en 3x ou 24x" (fr_BE) à côté du prix
  - [ ] Mode grid uniquement sur toutes les catégories
  - [ ] Disponibilité stock rendue correctement (variant.js)
  - [ ] Page produit : stats-grid horizontal, accordion specs, sticky image
  - [ ] Fonts `feather.css` chargées (icônes du footer)
  - [ ] Scroll fonctionne (pas de blocage lié à un JS v16 cassé)
  - [ ] Language fr_BE par défaut, prix en EUR
- [ ] Re-désactiver Floa (`payment_floa/__manifest__.py` → `installable: False`)
- [ ] Vérifier qu'aucun COW v16 obsolète ne reste actif via :
      ```sql
      SELECT key, COUNT(*) FROM ir_ui_view
      WHERE website_id IS NOT NULL
        AND arch_db::text LIKE '%group_show_line_subtotals_tax%'
      GROUP BY key;
      ```
- [ ] Smoke test full flow : browse → add to cart → checkout → payment
      (Mollie/Stripe selon prod) → confirmation

---

## 7. Dette technique post-migration

Points à corriger proprement dans un itération future :

1. **Inherits d'icônes** (section 3.3) : passer à `hasclass('fa-*')` quand
   possible pour éviter les warnings Odoo `Error-prone use of @class`.
2. **Badges extra price** (section 3.2) : reconnecter les `+5€` sur
   variantes dans le shop listing via un wrapper qui set `combination_info`.
3. **`tax_indication` COW** : à terme, faire un vrai inherit dans le code
   source au lieu de patcher un COW. Nécessite de purger le COW existant
   sur prod au deploy puis de pousser notre override.
4. **Theme customizer** : documenter quelles options doivent être
   activées/désactivées post-deploy (shop > list switcher OFF, footer
   option, etc.) — ou coder ces choix dans le module au lieu de s'appuyer
   sur le clic admin.
5. **`variant.js`** : l'appel manuel à `fetch('/web/dataset/call_kw/...')`
   pourrait passer par `rpc` du nouveau framework v17
   (`@web/core/network/rpc_service`) pour consistance. Fonctionnel en l'état.
