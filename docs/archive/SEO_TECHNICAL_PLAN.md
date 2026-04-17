# Plan Technique de Refonte SEO — Freemoov.com

**Date :** 2026-03-21
**Version Odoo :** 16 (Odoo.sh)
**Domaine :** https://www.freemoov.com
**Document compagnon :** `docs/SEO_AUDIT_PLAN.md` (audit complet + données SE Ranking)

---

## Table des matieres

1. [Vue d'ensemble et priorites](#1-vue-densemble)
2. [Phase 0 — Urgences techniques](#2-phase-0)
3. [Phase 1 — Structured Data (JSON-LD)](#3-phase-1)
4. [Phase 2 — Contenu duplique et URLs](#4-phase-2)
5. [Phase 3 — Performance et Core Web Vitals](#5-phase-3)
6. [Phase 4 — SEO Local Belgique](#6-phase-4)
7. [Phase 5 — Contenu et mots-cles](#7-phase-5)
8. [Phase 6 — Link building et autorite](#8-phase-6)
9. [Phase 7 — AI Search et avenir](#9-phase-7)
10. [Architecture des fichiers](#10-architecture)
11. [Calendrier de deploiement](#11-calendrier)
12. [KPIs et suivi](#12-kpis)

---

## 1. Vue d'ensemble {#1-vue-densemble}

### Situation actuelle (mars 2026)
- **Position 2** pour "trottinette electrique" en Belgique (18 100 vol/mois)
- **247 mots-cles** en organique BE, **734** en FR
- **97% du trafic BE** concentre sur la homepage — les categories ne rankent pas
- Score audit SE Ranking : **79/100** (83 erreurs, 860 warnings)
- **Zero JSON-LD** / rich snippets sur tout le site
- **Zero visibilite IA** (ChatGPT, Perplexity, Gemini)
- Page categorie principale **TIMEOUT a 20s** (3 MB de HTML)

### Objectifs
1. **Position 1** sur "trottinette electrique" BE (+100% trafic estime)
2. **Rich snippets** sur toutes les fiches produit (CTR 1.3% → 5-8%)
3. **Pages categories qui rankent** individuellement (debloquer 97% du potentiel)
4. **Local pack** pour Liege et Namur (+ Bruxelles sans magasin)
5. **Temps de chargement** < 3s sur toutes les pages
6. **Visibilite IA** — apparaitre dans les reponses ChatGPT/Perplexity

### Priorites strategiques

| Priorite | Impact | Effort | Description |
|----------|--------|--------|-------------|
| **P0** | CRITIQUE | 1-2 sem | Timeout page categorie, H1 manquants, 77 titres generiques |
| **P1** | HAUT | 2-3 sem | JSON-LD Product/Breadcrumb/LocalBusiness, sitemap, robots.txt |
| **P2** | HAUT | 2-4 sem | Contenu duplique, URLs, canonical, performance |
| **P3** | MOYEN | ongoing | Landing pages locales, blog, link building |
| **P4** | MOYEN | ongoing | AI Search optimization, visibilite IA |

---

## 2. Phase 0 — Urgences techniques {#2-phase-0}

> **Objectif :** Debloquer l'indexation et la performance des pages les plus importantes.
> **Delai :** Semaine 1-2

### 2.1 FIX: Page categorie trottinette TIMEOUT (20s)

**Probleme :** La page `/shop/category/trottinette-electrique-1` charge 74 produits sur une seule page, generant 3 MB de HTML. Le crawler SE Ranking et Googlebot timeout.

**Causes racines (3 problemes combines) :**

**A) Trop de produits par page** — `shop_ppg` probablement a 0 ou tres eleve.
**B) Attributs variantes rendus 2 FOIS par carte produit :**
- Lignes 232-337 : `<ul class="js_add_cart_variants">` visible (specs badges) — boucle sur `attribute_line_ids` avec selects/radios/pills complets
- Lignes 341-448 : `<ul class="d-none js_add_cart_variants">` hidden — MEME rendu complet pour le JS add-to-cart
- Pour un produit avec 10 attributs = 200-400 lignes HTML × 74 produits = **15 000-30 000 lignes inutiles**

**C) N+1 queries base de donnees :**
- `get_stock_availability()` fait 74 `search` sur `stock.quant` (1 par produit)
- `_get_first_possible_variant_id()` par carte
- `_get_attribute_exclusions()` par carte dans le bloc hidden

**Solution en 3 etapes :**

**Etape 1 (5 min — IMMEDIAT) : Limiter a 24 produits/page**
Website > Configuration > Settings > Shop > "Number of products in grid" → **24**
Ou en Python :
```python
# website_freemoov/models/website.py
class Website(models.Model):
    _inherit = 'website'
    shop_ppg = fields.Integer(default=24)
```

**Etape 2 (2h) : Supprimer le bloc hidden variantes des cartes produit**
```xml
<!-- inherited_template.xml — dans inherit_buttons -->
<!-- SUPPRIMER les lignes 341-448 (ul.d-none.js_add_cart_variants) -->
<!-- Ce bloc est inutile sur le listing — il sert au add-to-cart
     qui redirige de toute facon vers la fiche produit -->
```

**Etape 3 (1h) : Simplifier les badges variantes visibles**
Remplacer les selects/radios complets (lignes 232-337) par de simples `<span>` :
```xml
<div class="product-specs">
    <t t-set="count" t-value="0"/>
    <t t-foreach="product.attribute_line_ids" t-as="ptal">
        <t t-if="count &lt; 4">
            <t t-set="count" t-value="count + 1"/>
            <span class="spec-badge">
                <small t-esc="ptal.attribute_id.name"/>:
                <strong t-esc="ptal.product_template_value_ids[:1].name"/>
            </span>
        </t>
    </t>
</div>
```

**Etape 4 (3h) : Batch stock queries**
```python
# Remplacer 74 queries individuelles par 1 seule
quants = self.env['stock.quant'].sudo().read_group(
    [('product_id', 'in', all_variant_ids),
     ('location_id', '=', warehouse.lot_stock_id.id)],
    ['product_id', 'quantity'], ['product_id'])
```

**Impact combine :**
- Etape 1 : 3 MB → ~1 MB (-67%)
- Etape 2 : ~1 MB → ~400 KB (-60% du HTML restant)
- Etape 3 : ~400 KB → ~300 KB
- Etape 4 : 20s → 2-3s de temps serveur

**Test :** `curl -o /dev/null -s -w '%{time_total}' http://localhost:8071/shop/category/trottinette-electrique-1`

> **NOTE :** Le trust block (H6 "ACHETEZ EN TOUTE CONFIANCE") n'est PAS dans la boucle produit.
> Il est dans `product_details_inherited` (lignes 1068-1160) = page detail produit uniquement.
> Les H2 dupliques vus sur la page production viennent probablement du contenu CMS `oe_structure`.

### 2.2 FIX: H1 manquant sur 58 pages (categories utilisent H3)

**Probleme :** Le template `inherit_pager` dans `inherited_template.xml` (ligne 86) utilise `<h3>` pour le titre de categorie au lieu de `<h1>`.

**Solution :**
```xml
<!-- Dans inherited_template.xml, modifier le template inherit_pager -->
<!-- AVANT (ligne 86): -->
<h3 class="fw-bold text-uppercase"><t t-esc="category.name"/></h3>

<!-- APRES: -->
<h1 class="fw-bold text-uppercase fm-category-title"><t t-esc="category.name"/></h1>
```

Idem pour la page `/shop` (ligne 111) :
```xml
<!-- AVANT: -->
<h3 class="fw-bold text-uppercase">SHOP</h3>

<!-- APRES: -->
<h1 class="fw-bold text-uppercase fm-category-title">Nos produits</h1>
```

**Impact :** 58 pages passent de "H1 manquant" a un H1 semantiquement correct
**Fichier :** `website_freemoov/views/inherited_template.xml` lignes 86 et 111

### 2.3 FIX: 77 pages categories avec titre generique

**Probleme :** 77 pages categories affichent toutes le titre "Boutique | Freemoov, l'expert en trottinette electrique, Velo electrique et Gyroroue". C'est le fallback Odoo quand `website_meta_title` n'est pas renseigne sur `product.public.category`.

**Solution en 2 etapes :**

**Etape 1 : Auto-generation du titre si vide**
```python
# website_freemoov/models/product.py
class ProductPublicCategory(models.Model):
    _inherit = 'product.public.category'

    def _default_website_meta(self):
        res = super()._default_website_meta()
        if not self.website_meta_title:
            # Auto-generer un titre unique depuis le nom de categorie
            res['default_opengraph']['og:title'] = f"{self.name} | Freemoov"
            res['default_meta_description'] = (
                self.category_description[:160]
                if self.category_description
                else f"Decouvrez notre selection de {self.name.lower()} chez Freemoov. "
                     f"Livraison gratuite en Belgique, SAV expert, paiement en plusieurs fois."
            )
        return res
```

**Etape 2 : Script SQL pour remplir les titres des 77 categories**
```sql
-- Remplir website_meta_title pour les categories sans titre custom
UPDATE product_public_category
SET website_meta_title = name || ' | Freemoov - Expert Mobilite Electrique'
WHERE website_meta_title IS NULL OR website_meta_title = '';
```

**Impact :** 77 titres uniques au lieu d'un titre generique identique
**Script :** A inclure dans le migration script `post-migrate.py`

### 2.4 FIX: 98 pages sans meta description

**Solution :** Meme approche — auto-generer depuis `category_description` ou un template par defaut.

### 2.5 FIX: Canonical homepage / vs /home

**Probleme :** `/` dans le sitemap mais canonical pointe vers `/home`.

**Solution :** Redirection 301 de `/home` vers `/` dans le controller website :
```python
# website_freemoov/controllers/main.py
from odoo import http
from odoo.http import request

class WebsiteHome(http.Controller):
    @http.route('/home', type='http', auth='public', website=True)
    def redirect_home(self, **kwargs):
        return request.redirect('/', code=301)
```

---

## 3. Phase 1 — Structured Data (JSON-LD) {#3-phase-1}

> **Objectif :** Rich snippets dans les SERP pour tous les types de pages.
> **Delai :** Semaine 2-4

### 3.1 Approche technique Odoo 16

**Methode recommandee :** Generer le JSON-LD en Python via `Markup(json.dumps(...))` et l'injecter dans QWeb via `t-out`. Cela evite tous les problemes d'echappement HTML dans les `<script>` tags.

```python
# models/seo_mixin.py
import json
from markupsafe import Markup
from odoo import models, fields, api
from datetime import timedelta

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _get_jsonld_product(self):
        """Build JSON-LD Product structured data."""
        self.ensure_one()
        base_url = self.env['website'].get_current_website().get_base_url()
        pricelist = self.env['website'].get_current_website().get_current_pricelist()

        data = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": self.name,
            "description": self.description_sale or self.name,
            "url": base_url + self.website_url,
            "image": [base_url + self.env['website'].image_url(self, 'image_1920')],
            "sku": self.default_code or "",
            "brand": {"@type": "Brand", "name": self._get_brand_name()},
            "offers": {
                "@type": "Offer",
                "url": base_url + self.website_url,
                "priceCurrency": pricelist.currency_id.name,
                "price": "%.2f" % self.list_price,
                "priceValidUntil": (fields.Date.today() + timedelta(days=90)).isoformat(),
                "availability": self._get_schema_availability(),
                "itemCondition": "https://schema.org/NewCondition",
                "seller": {"@type": "Organization", "name": "Freemoov"},
                "shippingDetails": self._get_shipping_details(base_url),
                "hasMerchantReturnPolicy": self._get_return_policy(base_url),
            },
        }
        if self.barcode:
            data["gtin13"] = self.barcode
        return Markup(json.dumps(data, ensure_ascii=False, indent=2))
```

```xml
<!-- views/seo_jsonld.xml -->
<template id="product_jsonld" inherit_id="website_sale.product" name="Product JSON-LD">
    <xpath expr="//div[@id='wrap']" position="before">
        <script type="application/ld+json" t-out="product._get_jsonld_product()"/>
    </xpath>
</template>
```

### 3.2 Schemas JSON-LD par type de page

#### Product (fiche produit)
Proprietes requises : `name`, `offers` (avec `price` > 0, `priceCurrency`), `image`
Proprietes recommandees : `brand`, `sku`, `gtin13`, `description`, `availability`, `itemCondition`, `shippingDetails`, `hasMerchantReturnPolicy`

**AggregateRating :** NE PAS inclure tant qu'il n'y a pas de vrais avis utilisateurs. Google penalise les notes fabricees. Implementer d'abord Trustpilot/Avis Verifies, puis ajouter le schema.

Le JSON-LD Product complet inclut :
- Shipping BE (gratuit), FR (19.90 EUR), LU (14.90 EUR) avec `OfferShippingDetails`
- Return policy 14 jours (UE) avec `MerchantReturnPolicy`
- `additionalProperty` pour specs techniques (autonomie, vitesse, puissance, batterie)
- `weight` en KGM

#### BreadcrumbList (toutes les pages)
```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {"@type": "ListItem", "position": 1, "name": "Accueil", "item": "https://www.freemoov.com/"},
    {"@type": "ListItem", "position": 2, "name": "Trottinette electrique", "item": "https://www.freemoov.com/shop/category/trottinette-electrique-1"},
    {"@type": "ListItem", "position": 3, "name": "Dualtron Togo Limited"}
  ]
}
```
Position commence a 1. Dernier element sans `item` (URL de la page courante implicite). Doit correspondre au breadcrumb HTML visible.

#### LocalBusiness (pages magasins — x2)
Type : `ElectronicsStore` (plus specifique que `Store` ou `LocalBusiness`)
- NAP exact = Google Business Profile
- `openingHoursSpecification` complet
- `geo` avec lat/long
- `parentOrganization` pointant vers `Organization` principale
- `hasMap` avec Google Maps CID

#### Organization (homepage uniquement)
Type : `OnlineStore` (subtype de `Organization` pour e-commerce)
- `subOrganization` referençant les 2 magasins
- `hasMerchantReturnPolicy` au niveau org (s'applique a tous les produits)
- `sameAs` avec tous les profils sociaux
- `vatID` pour confiance europeenne
- Depuis nov 2025 : `hasShippingService` au niveau org

#### CollectionPage + ItemList (pages categories)
```json
{
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "Trottinettes electriques",
  "url": "https://www.freemoov.com/shop/category/trottinette-electrique-1",
  "mainEntity": {
    "@type": "ItemList",
    "numberOfItems": 36,
    "itemListElement": [
      {"@type": "ListItem", "position": 1, "item": {
        "@type": "Product", "name": "...", "url": "...", "image": "...",
        "offers": {"@type": "Offer", "price": 1899, "priceCurrency": "EUR", "availability": "..."}
      }}
    ]
  }
}
```
Inclure uniquement les produits visibles sur la page courante (pas les pages suivantes).

#### FAQPage (pages categorie + blog)
**Attention :** Depuis aout 2023, Google n'affiche plus les rich results FAQ pour les sites non-gouvernementaux. Mais le schema reste utile pour :
- Comprehension du contenu par Google
- AI Overviews / reponses IA
- Autres moteurs (Bing, DuckDuckGo)

#### WebSite + SearchAction (homepage)
Le sitelinks searchbox est **deprecie depuis nov 2024**. Mais `WebSite` reste utile pour l'affichage du nom du site dans les SERP.

#### ProductGroup (variantes produit)
Odoo utilise une page unique avec selecteur de variantes. Utiliser `ProductGroup` avec `hasVariant` nested. Chaque variante = un `Product` avec `sku`/`gtin` unique et URL `?variant=PRODUCT_PRODUCT_ID`.
`variesBy` : utiliser `https://schema.org/color`, `https://schema.org/size` (pour batterie/capacite).

#### VideoObject (homepage Vimeo)
Requis : `name`, `thumbnailUrl`, `uploadDate`. Heberger le thumbnail sur freemoov.com (pas Vimeo) pour fiabilite.

### 3.3 Strategie par page

| Page | Schemas |
|------|---------|
| Homepage | `OnlineStore` + `WebSite` + `VideoObject` |
| Categorie/Shop | `CollectionPage` + `ItemList` + `BreadcrumbList` |
| Fiche produit | `Product`/`ProductGroup` + `BreadcrumbList` + `Offer` + shipping/return |
| Pages magasins | `ElectronicsStore` + `BreadcrumbList` |
| FAQ | `FAQPage` + `BreadcrumbList` |
| Blog | `Article` + `BreadcrumbList` |

### 3.4 Implementation Odoo 16

**Fichiers a creer :**
- `models/seo_mixin.py` : methodes `_get_jsonld_product()`, `_get_jsonld_breadcrumb()`, `_get_jsonld_organization()`, `_get_jsonld_category()`
- `views/seo_jsonld.xml` : templates QWeb injectant les `<script type="application/ld+json">` via `t-out`
- `views/seo_head.xml` : hreflang fr-BE, canonical fixes

**Technique cle :** `Markup(json.dumps(data))` pour eviter l'echappement HTML dans les `<script>` tags. NE PAS utiliser `t-esc` directement dans le JSON.

### 3.5 Fix og:image domaine

**Cause :** `request.httprequest.url_root` retourne `https://freemoov.odoo.com/` sur Odoo.sh au lieu de `https://www.freemoov.com/`.

**Fix :** Override `get_website_meta()` dans `website.seo.metadata` pour remplacer le domaine interne par `website.domain` :
```python
class SeoMetadata(models.AbstractModel):
    _inherit = 'website.seo.metadata'

    def get_website_meta(self):
        meta = super().get_website_meta()
        website = request.website
        if website.domain:
            domain = website.domain.rstrip('/')
            if not domain.startswith('http'):
                domain = 'https://' + domain
            for key in ['og:image', 'og:url']:
                if key in meta.get('opengraph_meta', {}):
                    from urllib.parse import urlparse
                    url = meta['opengraph_meta'][key]
                    if url.startswith('http'):
                        parsed = urlparse(url)
                        meta['opengraph_meta'][key] = domain + parsed.path
                        if parsed.query:
                            meta['opengraph_meta'][key] += '?' + parsed.query
        return meta
```

**Aussi :** Verifier `web.base.url` dans Settings > Technical > System Parameters = `https://www.freemoov.com`

### 3.6 Validation

- **Google Rich Results Test** : https://search.google.com/test/rich-results
- **Schema.org Validator** : https://validator.schema.org/
- **Google Search Console** : Enhancements > Rich results
- Tester CHAQUE type de page apres deploiement

---

## 4. Phase 2 — Contenu duplique et URLs {#4-phase-2}

> **Objectif :** Eliminer le contenu duplique et optimiser la structure des URLs.
> **Delai :** Semaine 3-5

### 4.1 Produits dupliques via `?category=` (94 groupes de titres dupliques)

**Cause :** Le `QueryURL` du controller shop preserve `category` dans tous les liens produit. Chaque produit est accessible via `/shop/product-123?category=106`, `?category=1`, etc.

**Bonne nouvelle :** Le canonical strip deja le `?category=` automatiquement (Odoo re-match la route sans params). Mais le crawl budget est gaspille.

**Fix (template XML) :**
```xml
<template id="products_item_clean_url" inherit_id="website_sale.products_item" priority="99">
    <xpath expr="//t[@t-set='product_href']" position="replace">
        <t t-set="product_href" t-value="product.website_url"/>
    </xpath>
</template>
```
Tous les liens produit dans la grille pointent vers l'URL clean sans `?category=`.
**Effort :** 15 min | **Impact :** Elimine 94 groupes de contenu duplique

### 4.2 URLs sort/filter indexees (pages 3 MB)

**Cause :** `/shop?order=name+asc&category=80` genere des pages completes. Le canonical est correct mais Googlebot crawle quand meme.

**Fix 3 couches :**

**Couche 1 — robots.txt :**
```xml
<template id="custom_robots" inherit_id="website.robots">
    <xpath expr="." position="replace">
        <t t-name="website.robots">
User-agent: *
Disallow: /my/
Disallow: /web/
Disallow: /shop/cart
Disallow: /shop/checkout
Disallow: /shop/payment
Disallow: /shop/confirm_order
Disallow: /livechat/
Disallow: /helpdesk/
Disallow: /website/info
Disallow: /slider_s/
Disallow: /*?order=
Disallow: /*?search=
Disallow: /*?min_price=
Disallow: /*?max_price=
Disallow: /*?ppg=
Disallow: /*?attrib=

Allow: /shop/
Allow: /shop/category/
Allow: /blog/

Sitemap: <t t-esc="url_root"/>sitemap.xml
        </t>
    </xpath>
</template>
```

**Couche 2 — noindex sur pages parametrees :**
```xml
<template id="shop_noindex_params" inherit_id="website.layout" priority="99">
    <xpath expr="//head/link[@rel='canonical']" position="after">
        <t t-if="request and request.httprequest.args and (
            request.httprequest.args.get('order') or
            request.httprequest.args.get('attrib') or
            request.httprequest.args.get('min_price') or
            request.httprequest.args.get('max_price'))">
            <meta name="robots" content="noindex, follow"/>
        </t>
    </xpath>
</template>
```
**Effort :** 1h | **Impact :** Elimine indexation des pages filtrees/triees

### 4.3 URLs categories trop longues (>130 chars)

**Cause :** `slug()` utilise `display_name` qui inclut le chemin parent complet quand `seo_name` n'est pas renseigne. Aucune des 97 categories n'a de `seo_name`.

Exemple : `trottinette-electrique-nos-marques-de-trottinette-electrique-trottinette-electrique-dualtron-106`

**Fix (SQL) — setter `seo_name` = nom de la categorie (sans parents) :**
```sql
UPDATE product_public_category
SET seo_name = jsonb_build_object(
    'en_US', name->>'en_US',
    'fr_BE', COALESCE(name->>'fr_BE', name->>'en_US')
)
WHERE seo_name IS NULL OR seo_name::text IN ('{}', 'null', 'false');
```

Resultat pour cat 106 : `/shop/category/trottinette-electrique-dualtron-106` (au lieu de 135 chars)

**Redirections 301 automatiques :** Odoo 16 redirige automatiquement quand l'ID est correct mais le slug a change. Aucune config manuelle necessaire.

**Effort :** 30 min | **Impact :** URLs propres, crawl budget ameliore

### 4.4 Canonical homepage `/` vs `/home`

**Cause :** `homepage_url = '/home'` dans les settings website. Le controller reroute `/` vers `/home`, le canonical pointe vers `/home`.

**Fix :**
```sql
-- Changer le homepage_url
UPDATE website SET homepage_url = '' WHERE id = 1;
```
Puis ajouter un redirect 301 `/home` → `/` via Website > Configuration > Redirects.

**Effort :** 10 min | **Impact :** Canonical coherent, sitemap correct

### 4.5 URLs `/fr_BE/` generant des 303

**Cause :** Les liens internes ou CMS contiennent `/fr_BE/magasin` etc. Odoo redirige 303 vers `/magasin` car `fr_BE` est la langue par defaut.

**Fix :** Nettoyer les liens dans la DB :
```sql
-- Trouver les menus avec /fr_BE/
SELECT id, name, url FROM website_menu WHERE url LIKE '/fr_BE/%';
-- Les corriger
UPDATE website_menu SET url = REPLACE(url, '/fr_BE/', '/') WHERE url LIKE '/fr_BE/%';

-- Trouver les vues CMS
SELECT id, key FROM ir_ui_view WHERE arch_db::text LIKE '%/fr_BE/%';
```
**Effort :** 1h | **Impact :** Elimine 10 redirections 303

### 4.6 77 titres generiques — fix template

**Cause :** Le template `website_sale.products` set `additional_title = "Shop"` (traduit "Boutique") AVANT que le nom de categorie soit utilise. Les 77 categories sans `website_meta_title` heritent du titre generique.

**Fix (template, recommande) :**
```xml
<template id="products_title_fix" inherit_id="website_sale.products" priority="99">
    <xpath expr="//t[@t-set='additional_title'][1]" position="replace">
        <t t-if="category" t-set="additional_title" t-value="category.name"/>
        <t t-else="" t-set="additional_title">Boutique</t>
    </xpath>
</template>
```
Resultat : "Trottinette electrique Dualtron | Freemoov..." au lieu de "Boutique | Freemoov..."

**En complement (SQL) :** Pour les categories importantes, setter un titre SEO custom :
```sql
UPDATE product_public_category
SET website_meta_title = jsonb_build_object(
    'fr_BE', (name->>'fr_BE') || ' | Freemoov - Expert Mobilite Electrique'
)
WHERE website_meta_title IS NULL OR website_meta_title::text IN ('{}', 'null');
```
**Effort :** 30 min (template) + 15 min (SQL) | **Impact :** 77 titres uniques

### 4.7 Sitemap — exclure URLs techniques

**Fix (Python) :**
```python
# models/website.py
class Website(models.Model):
    _inherit = 'website'

    SITEMAP_EXCLUDE = [
        '/livechat', '/helpdesk', '/slider_s', '/website/info',
        '/my/', '/web/login', '/web/signup',
    ]

    def _enumerate_pages(self, query_string=None, force=False):
        for page in super()._enumerate_pages(query_string=query_string, force=force):
            if not any(p in page.get('loc', '') for p in self.SITEMAP_EXCLUDE):
                yield page
```
Puis vider le cache sitemap : `DELETE FROM ir_attachment WHERE url LIKE '/sitemap-%';`

**Effort :** 1h | **Impact :** Sitemap propre, crawl budget optimise

### 4.8 Pagination `rel=next/prev`

**Aucune action requise.** Google a deprecie `rel=next/prev` en mars 2019. Le pager Odoo genere deja des liens `<a>` vers les pages suivantes/precedentes, ce qui suffit. Les pages paginees ont un canonical self-referencing correct. NE PAS ajouter `noindex` aux pages 2+ (cacherait les produits).

---

## 5. Phase 3 — Performance et Core Web Vitals {#5-phase-3}

> **Objectif :** Toutes les pages < 3s, LCP < 2.5s, CLS < 0.1
> **Delai :** Semaine 3-6

### 5.1 Actions par priorite

| # | Action | Impact | Effort | Priorite |
|---|--------|--------|--------|----------|
| 1 | `shop_ppg = 24` (settings) | Page -67%, fix timeout | 5 min | **P0** |
| 2 | Supprimer hidden variant block des cartes | HTML -50-60%/carte | 2h | **P0** |
| 3 | Simplifier variant display → text badges | HTML -20%/carte | 1h | **P0** |
| 4 | Batch `get_stock_availability` (1 query vs 74) | Serveur -2-5s | 3h | **P1** |
| 5 | `loading="lazy"` sur images grille (sauf 1ere ligne) | Transfer -5-10 MB | 1h | **P1** |
| 6 | Remplacer feather.css (325 icones → 3 utilisees) | CSS -19 KB | 30min | **P1** |
| 7 | Cloudflare Polish/WebP + Brotli + page rules | Images -25-35% | 30min | **P1** |
| 8 | Minifier Owl Carousel ou remplacer par Bootstrap natif | JS -42-90 KB | 2-4h | **P2** |
| 9 | Preload image LCP sur page produit | LCP -200-500ms | 30min | **P2** |
| 10 | Audit SCSS dead rules | CSS -5-10 KB | 2h | **P3** |

**Objectif combine :** Page categorie 3 MB/20s → <500 KB/<3s. Homepage 5.4s → <3s.

### 5.2 Details techniques

#### Images et WebP
- Odoo 16 ne supporte PAS WebP cote serveur (JPEG/PNG uniquement)
- **Cloudflare Polish** (plan Pro) : conversion automatique WebP au CDN edge → zero code
- Images statiques homepage : deja en WebP (`<picture><source type="image/webp">`)
- JPEG qualite Odoo = 95 (tres haute, quasi-lossless)

#### Lazy loading
- Template `website_sale.products_item` n'a PAS `loading="lazy"` par defaut
- Ajouter via override QWeb ou JS post-render :
```javascript
document.querySelectorAll('.oe_product_image img').forEach((img, i) => {
    if (i > 5) img.loading = 'lazy';  // 1ere ligne = eager (LCP)
});
```

#### CSS/JS bundles Odoo
- CSS total : **967 KB** (dont ~850 KB Odoo core, ~120 KB custom)
- JS total : **577 KB** (dont Owl Carousel 90 KB non-minifie)
- Odoo 16 N'A PAS de `web.assets_frontend_minimal` (concept v17+)
- Impossible de splitter le bundle sans modifier le framework
- Verifier que `dev_mode` est OFF en production

#### Feather icons
- 325 classes definies, **3 utilisees** : `icon-heart`, `icon-circle-plus`, `icon-shopping-cart`
- Remplacer par FontAwesome (`fa-heart`, `fa-plus-circle`, `fa-shopping-cart`) → eliminer 19.5 KB CSS + ~15-30 KB font

#### Cloudflare page rules
```
/web/assets/*  → Cache Everything, Edge TTL 1 mois
/web/image/*   → Cache Everything, Edge TTL 1 semaine
/website_freemoov/static/*  → Cache Everything, Edge TTL 1 mois
```
Activer : Brotli, HTTP/2, Auto-Minify CSS/JS

#### Odoo.sh limites
- Workers geres par la plateforme (2-4 selon plan)
- `limit-time-real=120` (2 min) — le timeout 20s n'est pas une limite plateforme, c'est le code Python
- Le fix PPG + batch queries resout le probleme serveur

---

## 6. Phase 4 — SEO Local Belgique {#6-phase-4}

> **Objectif :** Local pack pour Liege, Namur et Bruxelles.
> **Delai :** Semaine 2-8

### 6.1 Google Business Profile

Optimiser les 2 profils GBP existants :
- **Categorie principale :** "Electric motor scooter dealer"
- **Secondaires :** "Electric bicycle store", "Bicycle repair shop", "Electric vehicle dealer"
- Posts 1-2x/semaine, photos geotaggees 5+/mois
- Q&A pre-rempli (ecocheques, assurance, reparation, age minimum)
- Attributs : ecocheques acceptes, Bancontact, parking

### 6.2 Landing pages locales

| Page | Mot-cle cible | Vol BE | Diff |
|------|--------------|--------|------|
| `/trottinette-electrique-liege` | trottinette electrique liege | 210 | 7 |
| `/trottinette-electrique-namur` | trottinette electrique namur | 110 | 6 |
| `/trottinette-electrique-bruxelles` | trottinette electrique bruxelles | 480 | 5 |
| `/magasin-trottinette-electrique-belgique` | magasin trottinette electrique belgique | 140 | 4 |

Chaque page : 1 200-1 800 mots, contenu unique (pas de city swap), Google Maps embed, schema LocalBusiness, photos du magasin, FAQ locale, produits populaires.

**Bruxelles (pas de magasin physique) :** Focus livraison gratuite + proximite Namur/Liege + invitation test-ride. NE PAS pretendre avoir un magasin.

### 6.3 Hreflang

```html
<link rel="alternate" hreflang="fr-BE" href="https://www.freemoov.com/..." />
<link rel="alternate" hreflang="x-default" href="https://www.freemoov.com/..." />
```

### 6.4 Annuaires belges (20+ citations)

**Tier 1 :** Google Business, Facebook, LinkedIn, Apple Business, Bing Places, Trustpilot.be, Waze
**Tier 2 :** Pagesdor.be, Kompass.be, Infobel.com, Pages Blanches, Yelp Belgium
**Tier 3 :** Opendi.be, Tuugo.be, Brownbook.net, EnrollBusiness.be

### 6.5 NAP Consistency

Format standardise pour chaque emplacement :
```
Freemoov Liege
[Adresse exacte]
4000 Liege, Belgium
+32 [numero]
```
Audit NAP sur tous les profils (Google, social, annuaires).

### 6.6 Strategie avis Google

- QR code en magasin + email post-achat (J+7) + SMS post-reparation
- Objectif : 50+ avis par magasin
- Repondre a CHAQUE avis sous 24-48h
- Profil Trustpilot gratuit

---

## 7. Phase 5 — Contenu et mots-cles {#7-phase-5}

> **Objectif :** Capter le trafic informationnel et construire l'autorite thematique.
> **Delai :** Ongoing (1 article/semaine)

### 7.1 Calendrier blog (12 articles)

#### Q2 2026 (avril-juin — pic saison)
| # | Titre | Mot-cle cible | Vol | Diff |
|---|-------|--------------|-----|------|
| 1 | Assurance trottinette electrique en Belgique : guide 2026 | assurance trottinette electrique | 140 | 9 |
| 2 | Acheter une trottinette avec vos ecocheques | trottinette electrique ecocheque | 70 | 8 |
| 3 | Top 5 trottinettes electriques pour la ville en 2026 | meilleure trottinette electrique | 210 | 10 |
| 4 | Entretien trottinette electrique : le guide complet | entretien trottinette electrique | 70 | 6 |

#### Q3 2026 (juillet-sept)
| 5 | Trottinette vs velo electrique : que choisir ? | trottinette ou velo electrique | ~200 | - |
| 6 | Comment choisir sa trottinette : guide d'achat 2026 | choisir trottinette electrique | ~300 | - |
| 7 | Accessoires indispensables pour trottinette | accessoire trottinette electrique | ~150 | - |
| 8 | Trottinette electrique sous la pluie | trottinette electrique pluie | ~100 | - |

#### Q4 2026 (oct-dec)
| 9 | Idees cadeaux mobilite electrique Noel 2026 | cadeau trottinette electrique | ~200 | - |
| 10 | Hivernage trottinette : proteger votre batterie | hivernage trottinette electrique | ~50 | - |
| 11 | Trottinette longue autonomie : notre selection | trottinette electrique autonomie | 480 | 10 |
| 12 | Financer sa trottinette en Belgique | budget mobilite belgique | ~100 | - |

### 7.2 Mise a jour article existant

**"/blog/trottinette-electrique-1/loi-trottinette-electrique-en-belgique-3"**
- Ajouter : casque obligatoire 2026, age minimum 16 ans, assurance RC auto >25kg, zones stationnement
- Lier vers : article assurance, produits, ecocheques, pages magasins

### 7.3 Pages marques a optimiser

| Marque | Vol FR | Diff | Action |
|--------|--------|------|--------|
| Teverun | 480 | 5 | Optimiser titre + meta desc + contenu unique |
| Inmotion | 140 | 5 | Idem |
| Vsett | 90 | 4 | Idem |
| Dualtron | 120 | 14 | Idem |

### 7.4 Maillage interne

Chaque article de blog doit lier vers :
- 2-3 fiches produit specifiques
- La categorie pertinente
- La page reparation/service
- Les pages magasins
- D'autres articles lies

Creer une page hub `/guide-trottinette-electrique` reliant tous les articles (pillar content).

---

## 8. Phase 6 — Link building et autorite {#8-phase-6}

### 8.1 Desaveu des backlinks spam

Creer un fichier `disavow.txt` pour Google Search Console avec ~30 domaines spam :
```
domain:optimizeflow.top
domain:analyticshaven.top
domain:dailymusings.top
domain:metamagic.top
domain:creativeposts.top
domain:blinks.sbs
domain:takes.sbs
domain:knows.sbs
domain:wants.cfd
domain:takes.homes
domain:seol.store
domain:seo-high-ranking.shop
domain:rankvanceauthority.info
domain:rankvanceboost.info
domain:rankvancelinks.info
domain:atomizelink.icu
domain:1stcallglasscare.com
domain:enteratyourownrisk.org
```

### 8.2 Strategie link building belge

| Strategie | Difficulte | Autorite | Delai |
|-----------|-----------|----------|-------|
| Annuaires business (CCI, UCM, 1890.be) | Facile | Moyenne | 1-2 sem |
| Reseau Entreprendre (laureat) | Facile | Moyenne-Haute | 1-2 sem |
| Citations annuaires belges | Facile | Faible-Moyenne | 1-2 sem |
| L'Avenir / Sud Info (presse locale) | Moyen | Haute | 1-2 mois |
| Pro Velo / GRACQ (partenariat) | Moyen | Moyenne | 2-3 mois |
| RTBF / Le Soir / La Libre | Difficile | Tres haute | 3-6 mois |
| Infographie reglementation | Moyen | Haute | 2-4 mois |

### 8.3 Angles presse

1. "Freemoov, la startup liegeoise qui democratise la micromobilite"
2. Expert commentary : nouvelles regles casque obligatoire 2026
3. Data story : "Les ventes de trottinettes explosent en Wallonie"
4. Partenariat Pro Velo : mobilite multimodale

---

## 9. Phase 7 — AI Search et avenir {#9-phase-7}

### 9.1 Optimisation pour les moteurs IA

Actuellement **zero presence** dans ChatGPT, Perplexity, Gemini.

**Actions :**
- Contenu structuré et factuel (les IA privilegient les reponses claires)
- FAQ riches avec des reponses directes (pas de marketing fluff)
- Schema FAQPage pour structurer les donnees
- Presence sur des sources citees par les IA (Wikipedia, forums specialises)
- Articles informationnels de qualite (guides, comparatifs objectifs)

### 9.2 Google SGE / AI Overviews

- Les AI Overviews privilegient le contenu qui repond directement aux questions
- Structure : question en H2, reponse directe en premier paragraphe, details ensuite
- Les listes numerotees et tableaux comparatifs sont favorises

---

## 10. Architecture des fichiers {#10-architecture}

```
website_freemoov/
├── models/
│   ├── product.py          # Enrichir: brand, sku, gtin → JSON-LD
│   ├── website.py          # Override: sitemap, robots.txt, ppg
│   └── seo_mixin.py        # NEW: Auto meta title/desc, JSON-LD generation
├── controllers/
│   ├── main.py             # Existant + redirect /home → /
│   └── sitemap.py          # NEW: Custom sitemap excludes
├── views/
│   ├── inherited_template.xml  # FIX: H3→H1, meta tags
│   ├── seo_jsonld.xml          # NEW: JSON-LD templates
│   ├── seo_head.xml            # NEW: hreflang, canonical fixes
│   └── local_pages.xml         # NEW: Landing pages locales
├── data/
│   └── seo_data.xml            # NEW: Default meta descriptions
└── static/
    └── src/
        └── scss/
            └── seo_local.scss  # NEW: Styles landing pages
```

---

## 11. Calendrier de deploiement {#11-calendrier}

### Semaine 1-2 : Urgences (Phase 0)
- [ ] Fix pagination (ppg=36) → debloquer timeout
- [ ] H3 → H1 sur categories
- [ ] Script SQL meta titles 77 categories
- [ ] Script SQL meta descriptions 98 pages
- [ ] Redirect 301 /home → /
- [ ] Deployer + relancer audit SE Ranking

### Semaine 2-4 : Structured Data (Phase 1)
- [ ] JSON-LD Product sur toutes les fiches
- [ ] JSON-LD BreadcrumbList global
- [ ] JSON-LD LocalBusiness (Liege + Namur)
- [ ] JSON-LD Organization
- [ ] Fix og:image domaine
- [ ] Valider avec Schema Markup Validator

### Semaine 3-5 : Contenu duplique (Phase 2)
- [ ] Canonical sans ?category= param
- [ ] Nettoyer sitemap (exclure techniques)
- [ ] Optimiser robots.txt (Disallow sort/filter)
- [ ] Hreflang fr-BE
- [ ] Raccourcir seo_name des categories

### Semaine 3-6 : Performance (Phase 3)
- [ ] Lazy loading optimise
- [ ] Images : compression + alt texts
- [ ] Reduire poids CSS si possible
- [ ] Defer scripts non-essentiels

### Semaine 2-8 : SEO Local (Phase 4)
- [ ] Optimiser 2 profils GBP
- [ ] 3 landing pages locales
- [ ] Soumettre 20+ annuaires belges
- [ ] Setup collecte avis Google

### Ongoing : Contenu (Phase 5)
- [ ] 1 article blog / semaine
- [ ] Optimiser pages marques
- [ ] Hub page guide trottinette

### Ongoing : Link building (Phase 6)
- [ ] Desaveu spam backlinks
- [ ] CCI, UCM, Reseau Entreprendre
- [ ] Presse locale (L'Avenir, Sud Info)

---

## 12. KPIs et suivi {#12-kpis}

| KPI | Baseline (mars 2026) | Objectif 3 mois | Objectif 6 mois |
|-----|---------------------|-----------------|-----------------|
| Position "trottinette electrique" BE | 2 | **1** | 1 |
| Mots-cles top 5 (BE) | 55 | 80 | 120 |
| Trafic organique BE | 990/mois | 2 000/mois | 4 000/mois |
| CTR moyen (GSC) | ~1.3% | 3% | 5% |
| Rich results (GSC) | 0 | 50+ pages | 200+ pages |
| Score audit SE Ranking | 79/100 | 90/100 | 95/100 |
| Backlinks dofollow | 16 legitimes | 30 | 50 |
| Avis Google (total) | ? | 30/magasin | 50/magasin |
| Load time categorie | TIMEOUT | < 3s | < 2s |
| Pages avec H1 unique | ~60% | 100% | 100% |
| Pages avec meta desc | ~80% | 100% | 100% |

### Outils de suivi
- **Google Search Console** : positions, CTR, couverture, Core Web Vitals
- **SE Ranking** : audit automatise, rank tracking local (IDs: Liege 2081, Namur 2084, Bruxelles 1439)
- **Schema Markup Validator** : validation structured data
- **PostHog** : comportement utilisateur, conversions
- **PageSpeed Insights** : Core Web Vitals

---

> **NOTE :** Les sections 3, 4 et 5 seront completees avec les resultats detailles des agents de recherche (JSON-LD complets, fixes Odoo, optimisations performance).
