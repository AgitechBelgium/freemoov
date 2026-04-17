# Audit SEO & Plan de Refonte — Freemoov.com

**Date :** 2026-03-21
**Site :** https://www.freemoov.com (Odoo 16 / Odoo.sh)
**Domaine secondaire :** freemoov.be → 301 vers freemoov.com (OK)

---

## PARTIE 1 : AUDIT SEO TECHNIQUE

### 1.1 Problemes CRITIQUES (Impact immediat sur le ranking)

#### A. Pages monstrueusement lourdes
- **Page categorie "Trottinette electrique" : 2 942 KB (3 MB)**
- 74 produits affiches sur UNE seule page, sans pagination effective
- Cause : le footer complet (trust block, FAQ, "Qui sommes-nous") est **repete a l'interieur de chaque carte produit**

#### B. 263 balises H2 sur la page categorie (desastre semantique)
| Balise H2 | Repetitions |
|-----------|-------------|
| "Vos avantages Freemoov" | x51 |
| "Qui sommes-nous ?" | x51 |
| "ACHETEZ EN TOUTE CONFIANCE" | x50 |
| "Besoin de conseils ?" | x50 |
| "Paiement en ligne securise" | x50 |

> **Diagnostic :** Le bloc trust/footer est imbrique dans le template de chaque carte produit, multipliant le HTML inutile et detruisant la hierarchie des titres.

#### C. Zero JSON-LD / Structured Data enrichie
- **Aucun JSON-LD** sur aucune page (homepage, categorie, produit)
- Seul le microdata Odoo natif (schema.org/Product + Offer) est present sur les fiches produit
- Microdata incomplet : manque `aggregateRating`, `review`, `brand`, `sku`, `gtin`, `availability`, `itemCondition`
- **Aucun BreadcrumbList** schema
- **Aucun LocalBusiness** schema (2 magasins physiques : Liege + Namur)
- **Aucun Organization** schema
- **Aucun FAQPage** schema (malgre du contenu FAQ present)

#### D. og:image pointe vers le mauvais domaine
```
og:image: https://freemoov.odoo.com/web/image/16889-253d2c4d/...
```
- Devrait pointer vers `https://www.freemoov.com/web/image/...`
- Impacte le partage social et les rich results

#### E. Homepage : 2 balises H1
- Le H1 est duplique (meme contenu, 2 occurrences)
- Canonical pointe vers `/home` au lieu de `/`

### 1.2 Problemes MAJEURS

#### F. Sitemap polluee (559 URLs)
URLs inutiles indexees :
- `/slider_s/all_in_one_data` (endpoint technique du module carousel)
- `/website/info` (page technique Odoo)
- `/livechat`, `/livechat/channel/www-freemoov-com-1`
- `/helpdesk/*` (3 canaux + 3 knowledgebases)

#### G. URLs de categories excessivement longues
Exemples (>130 caracteres) :
```
/shop/category/trottinette-electrique-nos-marques-de-trottinette-electrique-trottinette-electrique-dualtron-106
/shop/category/trottinette-electrique-nos-categories-de-trottinette-electrique-trottinette-electrique-ultra-performante-5
```
- Repetition du mot-cle "trottinette-electrique" 3 fois dans l'URL
- Google penalise les URLs trop longues et sur-optimisees

#### H. Absence de hreflang
- Le site cible la Belgique francophone mais n'a aucun tag hreflang
- Risque de confusion Google entre marches FR, BE, CH

#### I. robots.txt minimaliste
```
User-agent: *
Sitemap: https://www.freemoov.com/sitemap.xml
User-agent: *
Allow: /social_instagram/
```
- Pas de Disallow pour les pages techniques
- Directive "User-agent: *" dupliquee

#### J. Produits indisponibles dans le listing
- 24 produits "Pas disponible a la vente" affiches sur 74 (32%)
- Dilue la pertinence de la page et degradel'UX

#### K. Absence de rel=next/prev pour la pagination
- Pas de `<link rel="next">` ni `<link rel="prev">`
- Google ne peut pas comprendre la structure paginee

#### L. 53 images sans attribut alt + 12 avec alt vide
- Sur 149 images de la page categorie
- = 44% des images non accessibles / non indexables

### 1.3 Problemes MODEREES

#### M. Title tag avec double espace
```
Acheter la Meilleure Trottinette Electrique ?  C'est ici !
```
(double espace avant "C'est")

#### N. Pas de meta robots explicite
- Pas de `<meta name="robots" content="index, follow">` — fonctionne par defaut mais mieux vaut etre explicite

#### O. Microdata produit incomplete
Present : `name`, `image`, `description`, `offers`, `price`, `priceCurrency`, `url`, `listPrice`
Manquant : `brand`, `sku`, `gtin13/ean`, `availability`, `itemCondition`, `aggregateRating`, `review`, `category`

#### P. Google Merchant Center disconnected du site
- Le module `google_merchant_center` existe avec des categorisations riches (GPC_MAP, PRODUCT_TYPE_MAP)
- Mais aucune de ces donnees ne se retrouve cote SEO on-page

---

## PARTIE 2 : PLAN DE REFONTE SEO

### Phase 1 : Corrections critiques (Semaine 1-2)

#### 1.1 Corriger la duplication H2/footer dans les cartes produit
**Fichier :** Template QWeb carte produit (inherit de `website_sale.products_item`)
**Action :** Le bloc trust/footer est probablement herite via un `oe_structure` ou un snippet insere dans le template produit. Il faut l'isoler pour qu'il n'apparaisse qu'une seule fois en dehors de la boucle produit.
**Impact :** -90% du poids de page, semantique HTML corrigee
**Effort :** Moyen (2-4h)

#### 1.2 Ajouter JSON-LD Product enrichi sur les fiches produit
**Fichier :** Nouveau template QWeb dans `website_freemoov/views/`
**Action :** Creer un template heritant de `website_sale.product` qui injecte un bloc `<script type="application/ld+json">` avec :
```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "...",
  "image": ["..."],
  "description": "...",
  "brand": { "@type": "Brand", "name": "..." },
  "sku": "...",
  "gtin13": "...",
  "offers": {
    "@type": "Offer",
    "url": "...",
    "priceCurrency": "EUR",
    "price": "...",
    "priceValidUntil": "...",
    "availability": "https://schema.org/InStock",
    "itemCondition": "https://schema.org/NewCondition",
    "seller": {
      "@type": "Organization",
      "name": "Freemoov"
    }
  }
}
```
**Donnees disponibles :** Le module GMC a deja le mapping categorie, le SKU, le prix. Il suffit de reutiliser ces donnees cote template.
**Impact :** Rich snippets produit dans Google (prix, dispo, avis)
**Effort :** Moyen (3-5h)

#### 1.3 Ajouter JSON-LD BreadcrumbList
**Action :** Template QWeb global injectant le breadcrumb structure sur toutes les pages shop :
```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Accueil", "item": "https://www.freemoov.com/" },
    { "@type": "ListItem", "position": 2, "name": "Trottinette electrique", "item": "https://www.freemoov.com/shop/category/trottinette-electrique-1" },
    { "@type": "ListItem", "position": 3, "name": "Dualtron Togo Limited", "item": "https://www.freemoov.com/shop/trottinette-electrique-dualtron-togo-limited-1190" }
  ]
}
```
**Impact :** Breadcrumbs rich dans les SERP
**Effort :** Faible (1-2h)

#### 1.4 Ajouter JSON-LD LocalBusiness (x2)
**Action :** Template global ou page dediee `/magasin` avec :
```json
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "Freemoov Liege",
  "address": { ... },
  "geo": { "latitude": ..., "longitude": ... },
  "openingHoursSpecification": [...],
  "telephone": "...",
  "url": "https://www.freemoov.com/magasin",
  "image": "...",
  "priceRange": "$$"
}
```
**Impact :** SEO local, Google Maps, Knowledge Panel
**Effort :** Faible (1-2h)

#### 1.5 Corriger og:image domaine
**Fichier :** Python model ou template QWeb qui genere les meta OG
**Action :** Remplacer `freemoov.odoo.com` par `www.freemoov.com` dans la generation des og:image
**Impact :** Partage social correct
**Effort :** Faible (30min)

### Phase 2 : Optimisations structurelles (Semaine 2-3)

#### 2.1 Nettoyer le sitemap.xml
**Methode Odoo :** Override du controller `/sitemap.xml` ou utilisation de `website.page` avec `is_seo_optimized`
**Action :**
- Exclure : `/slider_s/*`, `/website/info`, `/livechat/*`, `/helpdesk/*`
- Ajouter `<lastmod>` et `<priority>` pour chaque URL
- Segmenter en sous-sitemaps si > 500 URLs (sitemap index)
**Effort :** Moyen (2-3h)

#### 2.2 Optimiser robots.txt
```
User-agent: *
Disallow: /web/
Disallow: /website/info
Disallow: /slider_s/
Disallow: /livechat/
Disallow: /helpdesk/
Disallow: /my/
Disallow: /shop/cart
Disallow: /shop/checkout
Disallow: /shop/payment
Disallow: /shop/confirmation
Disallow: /*?order=
Disallow: /*?attrib=
Disallow: /*?page=

Sitemap: https://www.freemoov.com/sitemap.xml
```
**Effort :** Faible (30min) — Odoo Website > Configuration > robots.txt

#### 2.3 Raccourcir les URLs de categories
**Action :** Modifier les `seo_name` des categories dans Odoo :
| Avant | Apres |
|-------|-------|
| `trottinette-electrique-nos-marques-de-trottinette-electrique-trottinette-electrique-dualtron-106` | `trottinette-electrique/marque/dualtron-106` |
| `trottinette-electrique-nos-categories-de-trottinette-electrique-trottinette-electrique-ultra-performante-5` | `trottinette-electrique/categorie/ultra-performante-5` |

> **Attention :** Odoo genere l'URL de categorie en concatenant parent + enfant. Il faudra soit modifier le `seo_name` de chaque sous-categorie pour supprimer la repetition, soit overrider la methode `_compute_website_url` dans `product.public.category`.

**Attention 301 :** Mettre en place des redirections 301 pour les anciennes URLs.
**Effort :** Moyen (3-4h + redirections)

#### 2.4 Corriger le H1 homepage
**Action :** Supprimer un des 2 H1 dupliques, garder un seul H1 semantique riche en mots-cles
**Effort :** Faible (15min via website builder ou template)

#### 2.5 Canonical homepage / → /home
**Action :** S'assurer que `/` et `/home` ont le meme canonical (`https://www.freemoov.com/`) ou que `/home` redirige 301 vers `/`
**Effort :** Faible (30min)

#### 2.6 Ajouter hreflang
```html
<link rel="alternate" hreflang="fr-BE" href="https://www.freemoov.com/..." />
<link rel="alternate" hreflang="x-default" href="https://www.freemoov.com/..." />
```
**Action :** Template QWeb global dans `<head>`. Meme si le site est monolingue, cela clarifie le ciblage geo.
**Effort :** Faible (1h)

### Phase 3 : Enrichissement SEO on-page (Semaine 3-4)

#### 3.1 Schema FAQPage sur les pages categorie
**Action :** Structurer le contenu existant ("Besoin de conseils ?", "Paiement securise", etc.) en JSON-LD FAQPage
**Impact :** Rich snippet FAQ dans les SERP — gain de place significatif
**Effort :** Faible (1-2h)

#### 3.2 Schema Organization global
```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Freemoov",
  "url": "https://www.freemoov.com",
  "logo": "https://www.freemoov.com/web/image/website/1/logo/...",
  "sameAs": [
    "https://www.facebook.com/freemoov",
    "https://www.instagram.com/freemoov"
  ],
  "contactPoint": {
    "@type": "ContactPoint",
    "telephone": "+32-...",
    "contactType": "customer service",
    "availableLanguage": "French"
  }
}
```
**Effort :** Faible (30min)

#### 3.3 Completer les alt texts d'images
**Action :**
- Images produit : utiliser `product.name` + `product.brand` comme alt
- Images CMS : audit manuel des 53 images sans alt
- Template QWeb : forcer un alt dynamique sur les images produit :
  ```xml
  <img t-att-alt="'%s - %s' % (product.name, product.brand_name or 'Freemoov')" .../>
  ```
**Effort :** Moyen (2-3h)

#### 3.4 Enrichir le microdata produit existant
Ajouter les attributs manquants au template produit :
- `itemprop="brand"` → depuis le champ brand du produit
- `itemprop="sku"` → default_code
- `itemprop="gtin13"` → barcode
- `itemprop="availability"` → stock status
- `itemprop="itemCondition"` → NewCondition
**Effort :** Moyen (2-3h)

#### 3.5 Masquer/deplacer les produits indisponibles
**Options :**
a) Les placer en fin de listing (tri "disponible d'abord")
b) Les masquer completement du listing (garder la fiche accessible pour le SEO)
c) Ajouter `data-nosnippet` ou low-priority signals
**Effort :** Moyen (2h)

### Phase 4 : SEO Local & Contenu (Semaine 4-6)

#### 4.1 Google Business Profile
- Verifier/optimiser les fiches GBP pour Liege et Namur
- Lier les fiches au site avec le schema LocalBusiness
- Photos, horaires, categories correctes

#### 4.2 Pages de contenu SEO par categorie
Chaque page categorie devrait avoir un bloc de contenu unique (pas juste la liste produits) :
- Introduction descriptive (200-400 mots)
- Guide d'achat contextuel
- FAQ specifique a la categorie
- Le champ `category_description` et `category_bottom_content` existent deja dans le modele — les exploiter !

#### 4.3 Blog SEO
Actuellement 16 articles dans le sitemap. Objectif :
- 1 article/semaine cible sur des mots-cles longue traine
- Exemples de sujets :
  - "Meilleure trottinette electrique 2026 Belgique"
  - "Trottinette electrique pluie etanche : laquelle choisir ?"
  - "Comparatif Dualtron vs Vsett vs Teverun"
  - "Reglementation trottinette electrique Belgique 2026"
  - "Entretien trottinette electrique : guide complet"

#### 4.4 Maillage interne
- Lier les articles de blog vers les pages categories/produits
- Ajouter des liens contextuels entre categories liees
- "Vous pourriez aussi aimer" enrichi avec liens semantiques

### Phase 5 : Performance & Technique (Ongoing)

#### 5.1 Reduire le poids des pages
- **Objectif categorie :** < 500 KB (actuellement 3 MB)
- Lazy load agressif des images sous le fold
- Pagination server-side (24-36 produits/page max)
- Supprimer le HTML duplique (trust block dans chaque carte)

#### 5.2 Core Web Vitals
- Mesurer LCP, FID, CLS via PageSpeed Insights
- Optimiser le critical CSS path
- Defer les scripts non-essentiels (Hotjar, GTM, Meta Pixel)
- Preconnect deja en place pour fonts.googleapis.com (OK)

#### 5.3 HTTPS/Security headers
- Verifier le HSTS header
- Content-Security-Policy
- X-Content-Type-Options (present via Cloudflare)

---

## PARTIE 3 : IMPLEMENTATION ODOO

### Architecture technique proposee

```
website_freemoov/
  views/
    seo_structured_data.xml     # JSON-LD templates (Product, BreadcrumbList, Organization, LocalBusiness, FAQ)
    seo_meta_overrides.xml      # Corrections meta (og:image, canonical, hreflang)
  models/
    product.py                  # Enrichir avec brand, sku, gtin, availability pour le JSON-LD
    website.py                  # Override sitemap generation, robots.txt
  controllers/
    sitemap.py                  # Custom sitemap controller (exclure URLs techniques)
```

### Template JSON-LD Product (exemple)

```xml
<template id="product_jsonld" inherit_id="website_sale.product" name="Product JSON-LD">
    <xpath expr="//div[@id='product_detail']" position="before">
        <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "<t t-esc="product.name"/>",
                "image": ["<t t-esc="request.website.image_url(product, 'image_1920')"/>"],
                "description": "<t t-esc="product.description_sale or product.name"/>",
                "brand": {
                    "@type": "Brand",
                    "name": "<t t-esc="product.brand_name or 'Freemoov'"/>"
                },
                "sku": "<t t-esc="product.default_code or ''"/>",
                <t t-if="product.barcode">
                "gtin13": "<t t-esc="product.barcode"/>",
                </t>
                "offers": {
                    "@type": "Offer",
                    "url": "<t t-esc="request.httprequest.url"/>",
                    "priceCurrency": "EUR",
                    "price": "<t t-esc="product.list_price"/>",
                    "availability": "<t t-if="product.qty_available > 0">https://schema.org/InStock</t><t t-else="">https://schema.org/OutOfStock</t>",
                    "itemCondition": "https://schema.org/NewCondition"
                }
            }
        </script>
    </xpath>
</template>
```

> **Note :** Le JSON-LD sera mieux genere via un Python controller ou un computed field pour eviter les problemes d'echappement XML dans les templates QWeb. Alternative : generer le JSON en Python et l'injecter via `t-raw`.

### Priorites de deploiement

| # | Action | Impact SEO | Effort | Priorite |
|---|--------|-----------|--------|----------|
| 1 | Fix H2 duplication / trust block | CRITIQUE | 2-4h | P0 |
| 2 | JSON-LD Product | HAUT | 3-5h | P0 |
| 3 | JSON-LD BreadcrumbList | HAUT | 1-2h | P0 |
| 4 | Fix og:image domain | MOYEN | 30min | P0 |
| 5 | Nettoyer sitemap | HAUT | 2-3h | P1 |
| 6 | Optimiser robots.txt | MOYEN | 30min | P1 |
| 7 | JSON-LD LocalBusiness | HAUT (local) | 1-2h | P1 |
| 8 | Raccourcir URLs categories | HAUT | 3-4h | P1 |
| 9 | Fix H1 homepage | MOYEN | 15min | P1 |
| 10 | Canonical homepage | MOYEN | 30min | P1 |
| 11 | Ajouter hreflang | MOYEN | 1h | P2 |
| 12 | Schema FAQPage | MOYEN | 1-2h | P2 |
| 13 | Schema Organization | FAIBLE | 30min | P2 |
| 14 | Alt texts images | MOYEN | 2-3h | P2 |
| 15 | Enrichir microdata produit | MOYEN | 2-3h | P2 |
| 16 | Masquer produits indisponibles | MOYEN | 2h | P2 |
| 17 | Contenu SEO categories | HAUT | ongoing | P3 |
| 18 | Blog SEO | HAUT | ongoing | P3 |
| 19 | Reduire poids pages | HAUT (perf) | 4-6h | P1 |
| 20 | Core Web Vitals | MOYEN (perf) | ongoing | P3 |

---

## PARTIE 4 : SE RANKING — DONNEES EXTRAITES

### Connexion API
- **Token :** `f809474e-d040-ab65-24d6-109d507af20a` (Data API)
- **Subscription :** Active (expire 2026-04-02), 97 330 credits restants
- **2 APIs distinctes :**
  - Data API : `https://api.seranking.com/v1/` — SEO data (OK, fonctionnel)
  - Project API : `https://api4.seranking.com/` — rank tracking (necessite token different)

### Visibilite organique freemoov.com (mars 2026)

**ATTENTION :** Les donnees initiales trackaient freemoov.be (ancien domaine, 301 → .com). Les vraies donnees sont sur freemoov.com.

#### Marche Belgique (principal)
- **247 mots-cles** en organique
- **55 en top 1-5**, 23 en top 6-10, 48 en top 11-20
- Trafic estime : **990/mois**
- **"trottinette electrique" : Position 2** (vol. 18 100/mois BE) — excellente position !
- **"trottinette electrique belgique" : Position 1** (vol. 210/mois)
- **"trottinettes electriques" : Position 2** (vol. 500/mois)

#### Marche France (secondaire)
- **734 mots-cles** en organique
- **59 en top 1-5**, 44 en top 6-10
- Trafic estime : 395/mois
- "marque trottinette electrique fiable" : Position 1 (vol. 70/mois)
- "marques de trottinettes electriques" : Position 3 (vol. 480/mois)

#### Google Search Console (28 derniers jours, donne par le client)
- ~1 000+ clics/mois, 60k+ impressions
- "freemoov" : 462 clics / 2 422 impressions
- "trottinette electrique" : 347 clics / 26 983 impressions (CTR ~1.3%)
- 1 000 requetes positionnees

#### Mondial
- **1 216 mots-cles** worldwide
- Trafic estime mondial : 1 392/mois

#### Repartition du trafic par page (PROBLEME MAJEUR)
| Page | Trafic BE | % du total |
|------|-----------|-----------|
| **Homepage (/)** | **964** | **97.4%** |
| /shop/category/gyroroue-47 | ~10 | 1% |
| Tout le reste | ~16 | 1.6% |

> **CONSTAT CRITIQUE :** La homepage capte quasi tout le trafic organique. Les pages categories (trottinette, velo, pieces) ne rankent quasiment pas individuellement. C'est directement lie aux problemes techniques (timeout, titres generiques, pas de H1, pas de meta desc).

#### Positions en mouvement (BE)
| Mot-cle | Avant | Maintenant | Changement |
|---------|-------|------------|-----------|
| trottinette electrique belgique | 5 | **1** | +4 |
| roue electrique | 28 | **2** | +26 |
| gyroroue | (new) | **2** | NEW |
| trottinette electrique | 3 | **2** | +1 |

#### Croissance historique
- Avril 2024 : **11 mots-cles**
- Mars 2026 : **247 mots-cles** (x22 en 2 ans)
- Pic trafic : 1 112/mois (nov 2025), actuellement 990/mois

#### Marche FR — tendance
- Pic : 2 049 mots-cles (jan 2025)
- Creux : 674 (dec 2025) — probablement lie aux redirections 301 .be → .com
- Recovery en cours : 734 (mars 2026)

#### Concurrents identifies

**Belgique :**
| Concurrent | Relevance | Observation |
|-----------|-----------|-------------|
| biketrottstore.com | 41% | Concurrent direct |
| m365shop.be | 41% | Specialise Xiaomi/accessoires |
| trottibike.be | 22% | E-commerce belge |
| streetride.be | 12% | Micro-mobilite |

**France :**
| Concurrent | Relevance | Trafic estime |
|-----------|-----------|---------------|
| timy-mobility.fr | 20% | 2 604/mois |
| biketrottstore.com | 8.6% | - |
| m365shop.be | 8.6% | - |

### Audit technique SE Ranking (freemoov.com) — DETAIL COMPLET
- **Score global : 79/100** (audit_id: 5128, 500 pages crawlees le 2026-03-21)
- **83 erreurs, 860 avertissements, 1 179 notices**
- **442 pages OK (200)**, 45 redirections (301), 10 redirections (303), **2 TIMEOUT**, 1 erreur 404

#### Pages en TIMEOUT (status 0 = CRITIQUE)
| URL | Load time | Inlinks | Impact |
|-----|-----------|---------|--------|
| `/shop/category/trottinette-electrique-1` | **20 001ms** | **973** | Page commerciale #1 |
| `/shop/category/.../trottinette-electrique-95` (marques) | **20 001ms** | - | Page marques parent |

> **La page la plus importante du site est inaccessible aux crawlers Google.** 973 liens internes pointent vers elle.

#### Pages les plus lentes (>5s)
| URL | Load time | Taille HTML |
|-----|-----------|-------------|
| `/shop?order=...&category=80` (toutes categories) | 10 898ms | 2.89 MB |
| `/shop/...dualtron-106` | 19 065ms | 1.37 MB |
| `/helpdesk/demande-de-suivi-1` | 9 346ms | 108 KB |
| `/home` | **9 249ms** | 121 KB |
| `/services-atelier` | 9 074ms | 133 KB |
| `/shop/category/gyroroue-47` | 5 150ms | 1.62 MB |
| `/magasin` | 5 389ms | 135 KB |

#### Pages les plus lourdes (HTML)
| URL | Taille | Images |
|-----|--------|--------|
| `/shop?...category=80` (5 variantes tri) | **2.89–3.02 MB** | 72-76 |
| `/shop/category/...-pas-cher-63` | 1.84 MB | - |
| `/shop/category/gyroroue-47` | 1.62 MB | 81 |
| Blog Brekr | 1.65 MB | 18 |

#### 66 pages categories avec le MEME titre generique
`"Boutique | Freemoov, l'expert en trottinette electrique, Velo electrique et Gyroroue"`
→ Toutes les sous-categories sans `website_meta_title` renseigne heritent du titre par defaut Odoo.

#### 98 pages sans meta description
Inclut : `/shop`, toutes les pieces detachees (30+), accessoires, velos, `/return`, `/delivery`, `/garantie`, `/privacy-policy`, `/faq`, `/payez-par-mois`, `/about-us`, `/jobs`, blog indexes, et la majorite des fiches produit.

#### 56 pages sans H1
Inclut : `/shop` (page principale!), `/return`, `/about-us`, `/blog`, `/cookies`, `/payez-par-mois`, blog categories, `/jobs`, toutes les pieces-detachees, toutes les sous-categories velo-electrique (brekr, lombardo, phatfour, super-73, knaap), punk-139, rovoron-173.

#### Contenu duplique via ?category= params
Les URLs produit avec `?category=XX` generent des pages identiques avec des URLs differentes :
- "Dualtron Togo Limited" → 9 URLs differentes (1 par categorie parente)
- "PUNK Rider Pro" → 6 URLs
- **94 groupes de titres dupliques** au total

#### Problemes recurrents sur TOUTES les pages
| Probleme | Detail |
|----------|--------|
| CSS trop lourd | `web.assets_frontend.min.css` = **967 KB** |
| JS non minifie | `web.assets_frontend_minimal.min.js` = **577 KB** |
| Images sans alt | Header icons (user.png, cart.png, wishlist.png), trust badges footer, pixel FB |
| Liens internes 301/303 | Social links, wishlist, login, change_pricelist — sur chaque page via header/footer |
| Lien externe cetelem.be | Retourne 301 — present sur chaque page |

#### Homepage specifique
| Probleme | Detail |
|----------|--------|
| Canonical mismatch | URL `/` mais canonical pointe vers `/home` → erreur sitemap |
| Speed Index | **5.4s** (Lighthouse) |
| Images sans alt | 23 images |
| 2 balises H1 | Dupliquees |
| CSS 967KB | Bundle Odoo complet |

#### Page /magasin (SEO local)
- H1 : "MAGASINS DE TROTTINETTE, VELO ET GYROROUE" (OK)
- Load time : 5 389ms (lent)
- **41 images sans alt** (logos marques, photos magasin)
- **2 images surdimensionnees** (photos magasin non optimisees)
- 4 liens Google Maps raccourcis (302 attendu)

#### Redirections 301 (45 pages)
Pattern : `/shop/product/slug-123` → `/shop/slug-123` (ancien format URL Odoo). Correct et attendu.
Aussi : 3 anciennes URLs categorie redirigees (par-categorie-pas-cher-63, par-categorie-puissante-5, etc.)

#### Redirections 303 (10 pages) — a convertir en 301 si permanentes
- `/fr_BE/contactus`, `/fr_BE/services-atelier`, `/fr_BE/about-us`, `/fr_BE/magasin`
- `/shop/wishlist`, `/my/home` (auth required)
- `/website/social/instagram`, `/facebook`, `/linkedin`, `/youtube`

#### Liens internes vers redirections (121 pages)
Sur chaque page via header/footer : social links, wishlist, `/shop/change_pricelist/1`, `/shop/change_pricelist/4`. A corriger dans les templates pour pointer vers les URLs finales.

#### Liens externes vers redirections (15 pages)
- **cetelem.be** retourne 301 — present dans header/footer de chaque page
- **maps.app.goo.gl** (x4) — raccourcis Google Maps, 302 attendu
- **floapay.be** — lien externe sans ancre

#### Pages avec 1 seul lien interne (orphelines)
- `/home` (paradoxalement, seul `/` y pointe via canonical)
- `/helpdesk/demande-generale-2`, `/helpdesk/demande-de-suivi-1`
- `/freemoov-charleroi`, `/formulaire-de-garantie`
- 3 offres d'emploi (`/jobs/detail/...`)

#### Resume des codes d'erreur SE Ranking (reference)
| Code | Severite | Nombre | Description |
|------|----------|--------|-------------|
| title_duplicate | ERROR | 77 | Titre identique sur 77 pages |
| timeout | ERROR | 2 | Pages en timeout (trottinette-1, marques-95) |
| sitemap_pages_timed_out | ERROR | 2 | Memes pages dans le sitemap |
| sitemap_non_canonical | ERROR | 1 | `/` dans sitemap mais canonical = `/home` |
| http4xx | ERROR | 1 | `/cdn-cgi/l/email-protection` (Cloudflare) |
| image_no_alt | WARNING | 442 | Quasi toutes les pages |
| links3xx | WARNING | 121 | Liens internes vers redirections |
| description_missing | WARNING | 97 | Meta desc manquante |
| loading_speed | WARNING | 67 | Temps de chargement > 3s |
| h1_missing | WARNING | 58 | H1 absent |
| redirect3xx | WARNING | 55 | Pages 301 crawlees |
| redirect_temporary | WARNING | 10 | Pages 302/303 |
| image_big | WARNING | 8 | Images surdimensionnees |
| h1_empty | WARNING | 1 | `/about-us` |
| js_not_min | NOTICE | 442 | JS Odoo non minifie (chaque page) |
| css_big | NOTICE | 442 | CSS 967KB (chaque page) |
| links_no_anchor | NOTICE | 121 | Liens sans texte d'ancre |
| title_long | NOTICE | 103 | Titre > 60 chars |
| h1_multiple | NOTICE | 18 | Plusieurs H1 |
| extlinks3xx | NOTICE | 15 | Liens externes vers 301 |
| description_long | NOTICE | 12 | Meta desc > 160 chars |
| less_inlink | NOTICE | 8 | 1 seul lien interne |
| extlinks_no_anchor | NOTICE | 7 | Liens externes sans ancre |
| h1_duplicate | NOTICE | 5 | H1 identique sur plusieurs pages |
| same_title_h1 | NOTICE | 4 | Title = H1 |
| description_duplicate | NOTICE | 2 | Meta desc identique |

### Profil de backlinks (freemoov.com) — COMPLET

| Metrique | Valeur |
|----------|--------|
| Total backlinks | **66** (35 dofollow / 31 nofollow) |
| Domaines referents | **52** (21 dofollow) |
| Domain InLink Rank | **20/100** |
| Page InLink Rank | **3/100** (tres faible) |
| Ancres uniques | 20 |

#### Backlinks de valeur (a proteger)
| Source | DIR | Type | Cible | Ancre |
|--------|-----|------|-------|-------|
| **notebookcheck.net** | 87 | dofollow | Navee S60 | "Freemoov in France..." |
| **sudinfo.be** (x3) | 87 | dofollow | Homepage + categories | "des gyroroues", prix |
| **reseau-entreprendre.org/wallonie** | 85 | dofollow | Homepage | "Freemoov" |
| **namurinvest.be** | 40 | dofollow | Homepage | (image) |
| **gyroriderz.com** (x3) | 11 | dofollow | Accessoires | "FREEMOOV" |
| notebookcheck (8 TLDs) | 45-87 | dofollow | Navee S60 | multilingue |

> 18 backlinks Notebookcheck proviennent d'un SEUL article sur la Navee S60 syndique en 8 langues.

#### Backlinks SPAM a desavouer (~30 domaines)
- **Reseau finlandais IP 195.20.19.178** (20 domaines): optimizeflow.top, analyticshaven.top, dailymusings.top, metamagic.top, creativeposts.top, urls-shortener.eu, sites.jake.eu, screenshots.wiki, anchorurl.cloud, buzzshrink.website, quero.party, bye.fyi, drjack.world, shortenurls.eu, byteshort.xyz, etc.
- **SEO spam** (.sbs/.cfd/.homes): blinks.sbs, takes.sbs, knows.sbs, wants.cfd, takes.homes, seol.store, seo-high-ranking.shop
- **Rankvance link spam**: rankvanceauthority.info, rankvanceboost.info, rankvancelinks.info
- **39% des backlinks viennent de 2 IPs spam finlandaises**

#### Faiblesses du profil
- Seulement **~16 backlinks dofollow legitimes** sur 66
- **0 lien .edu ou .gov**
- **Categories quasi-nues** : 1 seul backlink chacune (trottinette + gyroroue, les 2 de sudinfo.be)
- **Pas de liens presse belge** au-dela de sudinfo.be — RTBF, La Libre, DH, L'Avenir absents
- **Pas de blogs/sites micro-mobilite** (sauf espritroue.fr en nofollow forum)
- **Dependance a 1 article Notebookcheck** pour 27% des backlinks

#### Actions backlinks recommandees
1. **Desavouer** les ~30 domaines spam via Google Search Console (fichier disavow.txt)
2. **Presse belge** : cibler RTBF, La Libre, DH, L'Avenir, Le Soir pour des articles/partenariats
3. **Blogs micro-mobilite** : espritroue.fr (editorial), trottinette-electrique.info, etc.
4. **Liens vers les categories** : obtenir des backlinks vers /shop/category/trottinette-electrique-1 (pas juste la homepage)
5. **Leverager le Reseau Entreprendre** : demander des liens aux co-laureats et partenaires
6. **Renforcer les signaux .be** : annuaires belges, chambre de commerce, Liege/Namur business

### Volumes de recherche cles
| Mot-cle | Vol FR/mois | Vol BE/mois | Position actuelle (BE) |
|---------|-------------|-------------|----------------------|
| trottinette electrique | 450 000 | 18 100 | **2** |
| trottinettes electriques | - | 500 | **2** |
| trottinette electrique belgique | - | 210 | **1** |
| gyroroue | 6 600 | - | a verifier |
| marques de trottinettes electriques | 480 | - | 3 (FR) |
| marque trottinette electrique fiable | 70 | - | 1 (FR) |
| freemoov (marque) | 390 | - | **1** |

### Keyword Research complet (SE Ranking)

#### Volumes cles — Belgique (marche principal)
| Mot-cle | Vol BE | Diff | Position actuelle |
|---------|--------|------|-------------------|
| trottinette electrique | 18 100 | 84 | **2** |
| trottinette electrique pas cher | 590 | 9 | a creer |
| trottinettes electriques | 500 | 22 | **2** |
| prix trottinette electrique | 480 | 9 | a creer |
| trottinette electrique bruxelles | 480 | **5** | a creer |
| magasin de trottinette electrique | 390 | 6 | a optimiser |
| trottinette electrique avec siege | 320 | 8 | - |
| trottinette electrique belgique | 210 | 7 | **1** |
| trottinette electrique liege | 210 | **7** | a creer |
| meilleur trottinette electrique | 210 | 10 | a creer |
| trottinette electrique occasion | 210 | 8 | - |
| trottinette electrique 50 km h | 170 | 8 | - |
| magasin trottinette electrique belgique | 140 | **4** | a optimiser |
| trottinette electrique puissante | 140 | 7 | - |
| trottinette electrique solde | 140 | 9 | a creer |
| assurance trottinette electrique | 140 | 9 | a creer (CPC 0.82!) |
| monoroue | 140 | 13 | - |
| magasin trottinette electrique bruxelles | 110 | **1** | a creer |
| trottinette electrique namur | 110 | **6** | a creer |
| trottinette electrique legere | 90 | 9 | - |
| trottinette electrique ecocheque | 70 | 8 | a creer (specifique BE) |
| batterie trottinette electrique | 70 | 5 | - |
| entretien trottinette electrique | 70 | 6 | a creer |

#### Volumes cles — France
| Mot-cle | Vol FR | Diff | Position actuelle |
|---------|--------|------|-------------------|
| trottinette electrique | 450 000 | 89 | hors top 10 |
| velo electrique pliable | 5 400 | 58 | - |
| gyroroue tout terrain | 480 | 5 | a creer |
| trottinette electrique teverun | 480 | **5** | a optimiser |
| trottinette electrique la plus rapide | 590 | **5** | a creer |
| trottinette electrique legere | 590 | 7 | - |
| trottinette electrique pliable | 590 | 10 | - |
| trottinette electrique batterie amovible | 590 | **6** | - |
| trottinette electrique puissante 80 km/h | 590 | 9 | - |
| fatbike electrique | 810 | **14** | a optimiser |
| velo pliable electrique | 810 | **8** | a optimiser |
| trottinette electrique inmotion | 140 | **5** | a optimiser (on vend!) |
| trottinette electrique vsett | 90 | **4** | a optimiser (on vend!) |

#### QUICK WINS — Actions prioritaires SEO local (Belgique)

**Difficulte 1-5 (victoires quasi garanties) :**
1. **"magasin trottinette electrique bruxelles"** — diff 1, vol 110 BE → page magasin dediee
2. **"magasin trottinette electrique belgique"** — diff 4, vol 140 BE → page magasin
3. **"trottinette electrique bruxelles"** — diff 5, vol 480 BE → landing page locale
4. **"trottinette electrique teverun"** — diff 5, vol 480 FR → page marque optimisee
5. **"gyroroue tout terrain"** — diff 5, vol 480 FR → categorie + blog

**Difficulte 6-10 (opportunities solides) :**
6. **"trottinette electrique namur"** — diff 6, vol 110 BE → landing locale (magasin Namur!)
7. **"trottinette electrique liege"** — diff 7, vol 210 BE → landing locale (magasin Liege!)
8. **"trottinette electrique belgique"** — diff 7, vol 210 BE → DEJA Position 1
9. **"trottinette electrique pas cher"** — diff 9, vol 590 BE → page promotions
10. **"prix trottinette electrique"** — diff 9, vol 480 BE → guide prix

#### Questions (contenu blog/FAQ)
| Question | Vol | Diff | Type |
|----------|-----|------|------|
| Casque obligatoire trottinette electrique ? | 480 | 16 | Info |
| Trottinette electrique a partir de quel age ? | 480 | 13 | Info |
| Quelle trottinette electrique choisir adulte ? | 260 | 22 | Commercial |
| Loi/legislation trottinette electrique | 590 | 34 | Info |
| Assurance trottinette electrique (BE) | 140 | 9 | Commercial |
| Comment choisir sa gyroroue ? | - | - | Info |
| Entretien trottinette electrique | 70 | 6 | Info |
| Trottinette electrique ecocheque ? | 70 | 8 | Commercial (BE!) |

#### Saisonnalite
- **Pic trottinette** : avril-juillet (+45% vs hiver)
- **Pic gyroroue** : septembre (x2 vs moyenne — rentree)
- **Pic fatbike** : juillet-aout (x3.4 vs hiver)
- **Pic "magasin" queries** : mars-mai (x4 vs dec-jan) → **preparer les landing pages MAINTENANT**

#### Pages marques a creer/optimiser (brand keywords)
| Marque | Vol FR | Vol BE | Diff | Statut |
|--------|--------|--------|------|--------|
| Teverun | 480 | - | 5 | On vend — optimiser |
| Inmotion | 140 | - | 5 | On vend — optimiser |
| Vsett | 90 | - | 4 | On vend — optimiser |
| Dualtron | 120 | - | 14 | On vend — optimiser |
| Ninebot/Segway | - | 590 | 17 | On vend — optimiser |
| Xiaomi | - | (dans FR 40 500) | 99 | Trop competitif |

### AI Search (visibilite IA)
- Brand "FreeMoov" detectee par SE Ranking (BE + FR)
- **Zero presence dans les moteurs IA** : ChatGPT, Perplexity, Gemini ne citent ni ne linkent freemoov.com
- 0 prompts, 0 liens, 0 trafic IA
- **Opportunite majeure** : les concurrents ne sont probablement pas mieux positionnes → premier entrant avantage

### Localisations SERP Belgique (IDs pour le rank tracking local)
| Ville | Location ID | Interet |
|-------|-------------|---------|
| Bruxelles | 1439 / 89171 | Marche principal |
| Liege | 2081 / 89195 | Magasin physique |
| Namur | 2084 / 89201 | Magasin physique |
| Charleroi | 2018 | Extension future |
| Mons | 2039 | Wallonie |
| Anvers | 1472 / 89174 | Flandre |
| Gand | 1805 | Flandre |

### Historique domaine BE (croissance)
```
Avr 2024:  11 kw /    4 trafic /  0 top5
Jul 2024:  45 kw /  352 trafic / 11 top5
Sep 2024: 120 kw /  746 trafic / 25 top5
Nov 2025: 223 kw / 1112 trafic / 49 top5  ← PIC
Mar 2026: 247 kw /  990 trafic / 55 top5  ← MAINTENANT (valeur EUR max: 272)
```

### Historique domaine FR (effondrement + recovery)
```
Jul 2024: 1590 kw / 1288 trafic /  93 top5  ← Pic keywords
Jan 2025: 2049 kw / 1998 trafic / 113 top5  ← PIC absolu
Fev 2025: 1690 kw /  329 trafic /  98 top5  ← CHUTE BRUTALE
Mai 2025:  681 kw /   49 trafic /  29 top5  ← Creux
Jan 2026:  770 kw /  803 trafic /  77 top5  ← Debut recovery
Mar 2026:  734 kw /  395 trafic /  59 top5  ← MAINTENANT
```
> La chute FR fev-2025 est probablement liee a la migration/consolidation .be → .com. Recovery en cours mais loin des niveaux de jan 2025.

### Endpoints API fonctionnels (reference)
```
# Website Audit
GET /v1/site-audit/audits
GET /v1/site-audit/audits/report?audit_id=5128
GET /v1/site-audit/audits/pages?audit_id=5128
GET /v1/site-audit/audits/issue-pages?audit_id=5128&code=XXX
GET /v1/site-audit/audits/links?audit_id=5128

# Domain Analysis
GET /v1/domain/overview/db?source=fr&domain=freemoov.com
GET /v1/domain/overview/history?source=fr&domain=freemoov.com&type=organic
GET /v1/domain/keywords?source=fr&domain=freemoov.com&type=organic
GET /v1/domain/competitors?source=fr&domain=freemoov.com&type=organic

# Backlinks
GET /v1/backlinks/summary?target=freemoov.com&mode=domain
GET /v1/backlinks/all?target=freemoov.com&mode=domain
GET /v1/backlinks/anchors?target=freemoov.com&mode=domain
GET /v1/backlinks/refdomains?target=freemoov.com&mode=domain

# Keyword Research
POST /v1/keywords/export?source=fr (body: {"keywords": [...]})
GET /v1/keywords/similar?source=fr&keyword=trottinette+electrique
GET /v1/keywords/related?source=fr&keyword=trottinette+electrique
GET /v1/keywords/longtail?source=fr&keyword=trottinette+electrique
GET /v1/keywords/questions?source=fr&keyword=trottinette+electrique

# SERP
GET /v1/serp/classic/locations?country_code=be
POST /v1/serp/classic/tasks (rank check)
```

---

## PARTIE 5 : SUIVI & KPI

### Metriques a suivre
1. **Position moyenne** pour "trottinette electrique belgique" (Google Search Console)
2. **Nombre de rich results** (GSC > Performance > Apparence dans les resultats)
3. **Core Web Vitals** (PageSpeed Insights / GSC)
4. **Pages indexees** vs pages dans le sitemap
5. **CTR moyen** par page dans GSC
6. **Trafic organique** mensuel (GA4 / PostHog)
7. **Erreurs d'exploration** (GSC > Couverture)

### Outils
- Google Search Console (deja en place via GTM)
- Google PageSpeed Insights
- Schema Markup Validator (validator.schema.org)
- SE Ranking (une fois l'API fonctionnelle)
- PostHog (deja integre)
