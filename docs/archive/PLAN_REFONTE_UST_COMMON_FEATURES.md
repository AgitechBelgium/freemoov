# Plan de Refonte — ust_common_features (Sliders/Carousels)

**Date :** 2026-03-22
**Module :** ust_common_features (Upstackers — tiers)
**Strategie :** Overrides dans website_freemoov (ne PAS modifier le module tiers directement)
**Version cible :** 16.0.0.5.0

---

## Diagnostic

### Problemes identifies

Le module `ust_common_features` genere les sliders produit utilises sur les pages categories
("TOP DU MOMENT", "Selection Freemoov 2026", etc.) et sur la homepage. Deux templates
principaux : `product_grid` (cartes statiques) et `product_slider` (carousel Owl).

| Probleme | Source | Impact SEO |
|----------|--------|-----------|
| **73 H3 prix** sur la page categorie | `ust_all_in_one_slider.xml` L211, L233, L253, L309, L344, L374 | Google interprete les prix comme des titres de section |
| **H6 noms produits** dans les sliders | L202, L290 | Noms produits au niveau semantique le plus bas |
| **Microdata schema.org/Product** sur chaque carte slider | L185, L273 | Bonne pratique MAIS en conflit avec le Product JSON-LD principal |
| **Pas de brand visible** | L201, L289 : `brand_id.name` affiche mais peu visible | Marque peu mise en avant |
| **Pas de stock badge** dans les sliders | Absent | Incoherence avec la grille principale |
| **Pas de "Payez par mois"** | Absent des sliders | Incoherence UX |
| **Design non-Freemoov** | Bouton btn-outline-dark, pas de border-radius | Ne suit pas la charte (vert, arrondi) |
| **Owl Carousel 90KB non minifie** | `ust_carousel_product.js` | Performance (charge sur chaque page) |

### Templates concernes

| Template ID | Fichier | Lignes | Usage |
|-------------|---------|--------|-------|
| `product_grid` | `ust_all_in_one_slider.xml` | 178-265 | Cartes statiques dans les blocs CMS |
| `product_slider` | `ust_all_in_one_slider.xml` | 267-390 | Carousel Owl (homepage, sliders) |
| `ust_all_in_one_slider_template` | `ust_all_in_one_slider.xml` | 1-175 | Container principal + tabs |
| `ust_product_label_temp` | `template.xml` | ? | Labels produit (Promo, New) |

---

## Plan de refonte

### Phase 1 — Fixes SEO critiques (overrides dans website_freemoov)

#### 1.1 Override H3 prix → span dans product_grid

Creer un template dans `website_freemoov/views/seo_ust_overrides.xml` :

```xml
<!-- Override UST product_grid: fix H3 price tags -->
<template id="ust_product_grid_price_fix"
          inherit_id="ust_common_features.product_grid"
          name="FM: Fix UST grid price headings">
    <!-- H3 prix mode visible (css_editable_mode_hidden) -->
    <xpath expr="//h3[hasclass('css_editable_mode_hidden')]" position="attributes">
        <attribute name="t-tag">div</attribute>
    </xpath>
    <!-- H3 prix mode editeur (css_non_editable_mode_hidden) -->
    <xpath expr="//h3[hasclass('css_non_editable_mode_hidden')]" position="attributes">
        <attribute name="t-tag">div</attribute>
    </xpath>
    <!-- H3 "Pas disponible" -->
    <xpath expr="//div[@id='product_unavailable']/h3" position="attributes">
        <attribute name="t-tag">div</attribute>
    </xpath>
</template>
```

> Note : `t-tag` ne fonctionne pas pour changer un tag HTML en Odoo QWeb.
> Il faut utiliser `position="replace"` pour remplacer les H3 complets.
> Mais comme les H3 contiennent beaucoup de logique conditionnelle,
> la strategie recommandee est de copier le template entier et le remplacer.

**Strategie recommandee :** Creer un template `replace` complet qui reprend
le contenu du `product_grid` et `product_slider` mais avec `<div>` au lieu de `<h3>`.

#### 1.2 Override H6 noms produits → div

```xml
<template id="ust_product_grid_name_fix"
          inherit_id="ust_common_features.product_grid"
          name="FM: Fix UST grid product name">
    <xpath expr="//h6[hasclass('o_wsale_products_item_title')]" position="replace">
        <div class="o_wsale_products_item_title h6 mb8">
            <a class="text-primary text-decoration-none" itemprop="name"
               t-att-href="'/shop/product/%s' % slug(product)"
               t-att-content="product.name" t-esc="product.name"/>
        </div>
    </xpath>
</template>
```

Idem pour `product_slider`.

### Phase 2 — Design Freemoov sur les cartes slider

#### 2.1 Carte produit slider redesignee

Chaque carte slider doit visuellement matcher la grille principale :

**AVANT (design UST defaut) :**
- Fond blanc sans arrondi
- Nom en H6 italic uppercase
- Prix en H3 (trop grand, mauvais heading)
- Bouton fleche `btn-outline-dark`
- Pas de stock badge
- Pas de marque visible
- Pas de "Payez par mois"

**APRES (design Freemoov) :**
- Fond blanc, `border-radius: 20px`, shadow on hover
- Nom en `div.h6` (pas de heading)
- Marque visible au-dessus du nom (couleur #7F7F7F)
- Prix en `span.h6` avec "TVAC" suffix
- Stock badge (vert/rouge) coherent avec la grille
- "Payez par mois" badge compact
- Bouton CTA vert gradient "DECOUVRIR"
- Border-radius 12px sur les boutons
- Stars si `rating_count > 0`

#### 2.2 Style SCSS a ajouter

Dans `website_freemoov/static/src/scss/shop.scss`, ajouter une section
`/* UST Slider Cards — Freemoov Override */` qui cible :

```scss
.ust_all_in_one_configure_slider {
    #ust-product-grid,
    #ust-product-slider {
        .oe_product_cart {
            border-radius: 20px;
            background: #fff;
            transition: transform 0.2s, box-shadow 0.2s;
            &:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
            }
        }
        .product_price_div {
            div { /* was h3 */
                font-size: 18px;
                font-weight: 700;
                color: #000;
            }
        }
        .s_btn a {
            background: linear-gradient(135deg, #099D5D, #7AC144);
            color: #fff;
            border: 0;
            border-radius: 12px;
            padding: 8px 16px;
            font-weight: 600;
            font-size: 13px;
            &:hover {
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(9, 157, 93, 0.3);
            }
        }
        .brand {
            font-size: 12px;
            color: #7F7F7F;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
    }
}
```

### Phase 3 — Enrichissement des cartes slider

#### 3.1 Ajouter stock badge dans les sliders

Override le template pour ajouter apres le prix :
```xml
<t t-set="stock_available" t-value="product.get_stock_availability(website)"/>
<span t-if="stock_available['qty_avail'] > 0 or stock_available.get('is_dropship') or stock_available.get('allow_out_of_stock')"
      class="stock_badge stock_available"><span class="stock_dot"/>Disponible</span>
<span t-else="" class="stock_badge stock_unavailable"><span class="stock_dot"/>Rupture de stock</span>
```

#### 3.2 Ajouter "Payez par mois" badge

```xml
<a t-att-href="'/shop/product/%s' % slug(product)" class="monthly-payment-badge">
    <i class="fa fa-credit-card"></i>
    <span>Payez par mois</span>
</a>
```

#### 3.3 Ajouter etoiles review (si actif)

```xml
<div t-if="product.rating_count" class="fm-card-stars">
    <i t-foreach="range(1, 6)" t-as="star"
       t-attf-class="fa #{'fa-star' if star &lt;= round(product.rating_avg) else 'fa-star-o'}"/>
    <span class="fm-card-rating-count">(<t t-esc="product.rating_count"/>)</span>
</div>
```

### Phase 4 — Nettoyage microdata

#### 4.1 Supprimer microdata Product/Offer des sliders

Les sliders CMS ne doivent PAS avoir de microdata `schema.org/Product`
car ils creent des doublons avec le JSON-LD Product principal.

Supprimer :
- `itemscope="itemscope" itemtype="http://schema.org/Product"` de la form
- `itemprop="url"`, `itemprop="name"`, `itemprop="price"`, `itemprop="priceCurrency"`, `itemprop="listPrice"` des elements

Le JSON-LD Product (dans `seo_jsonld.xml`) est la source unique de structured data.

### Phase 5 — Performance Owl Carousel

#### 5.1 Minifier owl.carousel.js

Remplacer `ust_common_features/static/src/js/owl.carousel.js` (90 KB)
par la version minifiee `owl.carousel.min.js` (~42 KB).

OU

#### 5.2 Migrer vers Bootstrap Carousel natif

Les sliders simples (2-4 produits) peuvent utiliser le Bootstrap 5 carousel
deja charge par Odoo, eliminant la dependance Owl.
Cela economise ~42 KB JS + la CSS Owl (~3 KB).

**Recommandation :** Phase 5.1 (minification) dans un premier temps,
Phase 5.2 (migration Bootstrap) dans un sprint ulterieur car plus risque.

---

## Architecture des overrides

```
website_freemoov/
  views/
    seo_ust_overrides.xml       # Override H3→div, H6→div, microdata cleanup
                                # Stock badge, "Payez par mois", stars
  static/src/scss/
    shop.scss                   # Section "UST Slider Cards — Freemoov Override"
```

Fichier unique `seo_ust_overrides.xml` contenant 4 templates :
1. `ust_product_grid_freemoov` — remplace `product_grid` complet
2. `ust_product_slider_freemoov` — remplace `product_slider` complet
3. `ust_product_grid_name_fix` — override nom H6→div
4. `ust_product_slider_name_fix` — override nom H6→div

**Approche :** Comme les H3 sont profondement imbriques dans la logique conditionnelle
(prix promo vs normal, editable vs non-editable), le plus propre est de faire
un `position="replace"` sur les blocs `product_price_div` entiers dans chaque template.

---

## Calendrier

| Sprint | Taches | Effort |
|--------|--------|--------|
| 1 | Override H3→div dans product_grid + product_slider | 3-4h |
| 1 | Override H6→div pour noms produits | 30min |
| 1 | Supprimer microdata Product des sliders | 1h |
| 2 | Style SCSS Freemoov sur cartes slider | 2-3h |
| 2 | Ajouter stock badge + "Payez par mois" | 1-2h |
| 2 | Ajouter stars review | 30min |
| 3 | Minifier Owl Carousel | 30min |
| 3 | Tests visuels + responsive | 1-2h |

**Total estime :** 10-12h sur 2-3 sprints

---

## Impact attendu

| Metrique | Avant | Apres |
|----------|-------|-------|
| H3 prix sur categorie | 73 | **0** |
| H6 noms produits sliders | 24+ | **0** (div.h6) |
| Microdata doublons | Product x48 | **0** (JSON-LD seul) |
| Design coherence slider/grille | Incoherent | **Unifie** charte Freemoov |
| Owl Carousel JS | 90 KB | **42 KB** (minifie) |
| Stock badge dans sliders | Absent | **Present** |
| Stars review dans sliders | Absent | **Present** |
