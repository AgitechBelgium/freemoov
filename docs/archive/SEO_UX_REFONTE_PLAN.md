# Plan de Refonte SEO + UX — Freemoov.com
## "Devenir le Weebot de la Belgique"

**Date :** 2026-03-21
**Objectif :** Surpasser Weebot en qualite SEO tout en gardant le design Freemoov
**Contraintes :** Odoo v16, Odoo.sh mono-thread, editable via website builder

---

## PARTIE 1 : DIAGNOSTIC

### Ce que fait Weebot qu'on ne fait pas
| Element | Weebot | Freemoov | Gap |
|---------|--------|----------|-----|
| Contenu categorie | 3 000 mots (guide, FAQ, reglementation) | ~100 mots | x30 |
| Avis produit | 121 avis, 5.0 etoiles (Judge.me) | Placeholders fake | Critique |
| FAQ produit | 4 Q&A + FAQPage schema | Aucune | Critique |
| Specs inline cartes | 4 specs (vitesse, autonomie, W, batterie) | Badges variant | A ameliorer |
| Stars sur cartes grille | Oui (note + count) | Non | Critique |
| Blog lie au shop | 17 liens blog sur categorie | 0 | Important |
| Sous-categories visuelles | 6 cartes H3 en haut de grille | Aucune | Important |
| Alt text descriptif | "Dualtron Togo : Confortable - Weebot" | Nom produit seul | Moyen |
| Cross-sell "Ca va vous plaire" | 3 sections (marque, recent, recommande) | Accessoires uniquement | Moyen |

### Ce que Freemoov fait MIEUX que Weebot
- ShippingDetails 4 pays dans Product schema
- MerchantReturnPolicy dans schema
- CollectionPage + ItemList sur categories
- priceValidUntil + weight dans Product schema
- Magasins physiques (Liege + Namur) → avantage SEO local

### Ce qu'AUCUN concurrent belge ne fait
- Contenu editorial > 100 mots sur categories
- FAQ + FAQPage schema
- JSON-LD complet (Product, BreadcrumbList, ItemList)
- Avis integres avec AggregateRating
→ **Premier arrivant = leader inconteste du marche belge**

---

## PARTIE 2 : ARCHITECTURE TECHNIQUE

### Nouveaux modeles Python

```
product.faq           # FAQ par produit (question/reponse structurees)
  - product_id        : Many2one → product.template
  - question          : Char (translatable)
  - answer            : Html (translatable, sanitize=False)
  - sequence          : Integer

product.template (extensions)
  - faq_ids           : One2many → product.faq
  - editorial_review  : Html (translatable) — "Notre avis Freemoov"
  - seo_specs_summary : Char (computed) — "1800W | 80km | 28kg | 60V"

product.public.category (extensions)
  - blog_id           : Many2one → blog.blog — pour lier les articles
  - seo_intro         : Html (translatable) — intro editable au-dessus de la grille
```

### Nouveaux templates XML

```
seo_category_content.xml    # Blocs SEO sous la grille categorie
  - Section intro (H2 + t-field seo_intro)
  - Section FAQ categorie (t-field category_bottom_content)
  - Section blog (dynamic snippet filtre par blog_id)
  - Section "liens utiles" (cross-links categories)

seo_product_enrichment.xml  # Enrichissement page produit
  - Section "Notre avis Freemoov" (t-field editorial_review)
  - Section FAQ produit (accordion depuis product.faq)
  - Section avis clients (natif Odoo, toggle product_comment)
  - Section "Ca va vous plaire" (produits meme categorie)
  - Section blog lies (articles du meme blog que la categorie)

seo_product_cards.xml       # Amelioration cartes produit grille
  - Stars + review count
  - 4 specs inline (vitesse, autonomie, puissance, batterie)
  - Brand name visible
  - Alt text enrichi
```

### Fichiers modifies

```
models/product.py          # Ajout faq_ids, editorial_review, seo_specs_summary
models/seo.py              # AggregateRating, FAQPage JSON-LD, specs summary
views/inherited_template.xml  # Fix headings, supprimer pro_description des cartes
                              # Ajouter stars, specs inline, brand sur cartes
__manifest__.py            # Nouveaux fichiers data + views
```

---

## PARTIE 3 : FIXES HEADING HIERARCHY

### Page categorie — Avant vs Apres

**AVANT :**
```
H1: Trottinette electrique                    (etait H3)
  H6: Dualtron Togo Limited                   (nom produit)
    H3: 899,00 EUR                            (PRIX en heading!)
    H3: Pas disponible a la vente             (STOCK en heading!)
  H2: ACHETEZ EN TOUTE CONFIANCE              (trust block x50 via pro_description)
  H2: Besoin de conseils ?                    (x50)
  H2: Vos avantages Freemoov                  (x50)
```

**APRES :**
```
H1: Trottinette electrique — Freemoov Belgique
  [cartes produit : AUCUN heading, juste des spans/divs]
  [prix : span.price, pas de heading]
  [stock : span.stock-badge, pas de heading]
H2: Guide d'achat trottinette electrique      (contenu editorial)
  H3: Comment choisir sa trottinette ?
  H3: Quelle puissance pour quel usage ?
H2: Questions frequentes                       (FAQ avec schema)
  H3: Faut-il une assurance en Belgique ?
  H3: A partir de quel age ?
H2: Nos marques de trottinettes electriques   (liens internes)
H2: Articles du blog                          (blog posts lies)
```

### Page produit — Avant vs Apres

**AVANT :**
```
H1: Trottinette electrique Teverun Space
  H3: 1.199,00 EUR                           (prix)
  H6: Paiement en ligne securise              (trust)
  H6: ACHETEZ EN TOUTE CONFIANCE
H2: Teverun Space : L'Equilibre Parfait...    (description — OK)
  H3: L'ingenierie Teverun                    (OK)
H2: Performances et Specifications            (OK)
  H3: L'ADN Fighter...                       (OK)
H5: Avis clients                              (fake reviews)
```

**APRES :**
```
H1: Trottinette electrique Teverun Space | Freemoov
  [prix : span.price]
  [trust : div.trust-feature, pas de heading]
H2: Description                               (contenu editorial)
  H3: sous-sections description
H2: Caracteristiques techniques               (specs table)
H2: Notre avis Freemoov                       (editorial_review, editable)
H2: Questions frequentes                       (product.faq accordion + FAQPage schema)
  H3: Question 1 ?
  H3: Question 2 ?
H2: Avis clients                              (natif Odoo, vrais avis)
H2: Ca va vous plaire                         (cross-sell)
H2: Articles lies                             (blog)
```

### Modifications template specifiques

| Fichier | Ligne | Avant | Apres | Raison |
|---------|-------|-------|-------|--------|
| inherited_template.xml | 217 | `<h6>` nom produit | `<span class="h6">` | Pas de heading dans une boucle produit |
| inherited_template.xml | 225-227 | `t-esc="product.pro_description"` | **Supprimer** (ne rendre que sur page detail) | Cause des 50x H2 trust |
| inherited_template.xml | 469 | `<span class="h6">` prix | Garder (deja correct) | C'est une classe CSS, pas un heading |
| inherited_template.xml | 904-953 | `<h6>` trust titles | `<div class="trust-title">` | Trust block n'est pas une section semantique |
| inherited_template.xml | 625-762 | Fake reviews "Marine" | Remplacer par reviews natives | Faux contenu nuit au SEO |

---

## PARTIE 4 : SYSTEME D'AVIS

### Architecture

**Phase 1 — Natif Odoo (gratuit, immediat)**
1. Activer toggle `website_sale.product_comment`
2. Ajouter `aggregateRating` dans `seo.py` → `_get_jsonld_product()`
3. Supprimer les fake reviews "Marine" du template
4. Ajouter etoiles + count sur les cartes produit grille
5. Email automatique J+7 post-achat pour demander un avis

**Phase 2 — Google Shopping (quand 50+ avis)**
1. Construire feed XML Product Reviews (controller Python)
2. Postuler au programme Product Ratings de Google
3. Etoiles dans Google Shopping = 0 EUR/mois

**Phase 3 — Optionnel (si acceleration souhaitee)**
- Reviews.io a 29 EUR/mois = agregateur Google approuve, feed GMC auto

### JSON-LD AggregateRating
```python
if self.rating_count > 0:
    data['aggregateRating'] = {
        '@type': 'AggregateRating',
        'ratingValue': '%.1f' % self.rating_avg,
        'reviewCount': self.rating_count,
        'bestRating': '5',
        'worstRating': '1',
    }
```

---

## PARTIE 5 : CONTENU EDITORIAL CATEGORIES

### Approche technique

Utiliser le pattern `t-field` sur un Html field (`seo_intro` et `category_bottom_content`) ENVELOPPE dans un template QWeb structure :

```xml
<!-- Template fournit la structure H2/H3 -->
<!-- t-field fournit le contenu editable -->
<section t-if="category" class="fm-seo-section">
    <div class="container">
        <!-- Intro editable -->
        <div t-if="category.seo_intro" class="fm-seo-intro mb-4">
            <h2>Tout savoir sur les <t t-esc="category.name"/></h2>
            <div t-field="category.seo_intro" class="fm-seo-text"/>
        </div>

        <!-- FAQ categorie (dans category_bottom_content) -->
        <div t-if="category.category_bottom_content"
             class="fm-seo-faq mt-4">
            <h2>Questions frequentes — <t t-esc="category.name"/></h2>
            <div t-field="category.category_bottom_content"/>
        </div>

        <!-- Blog articles lies -->
        <div t-if="category.blog_id" class="fm-seo-blog mt-4">
            <h2>Articles et guides</h2>
            <section data-snippet="s_blog_posts"
                     class="s_dynamic_snippet_blog_posts"
                     t-att-data-filter-by-blog-id="category.blog_id.id"
                     data-template-key="website_blog.dynamic_filter_template_blog_post_card"
                     data-number-of-elements="3"/>
        </div>

        <!-- Cross-links categories -->
        <div class="fm-seo-links mt-4">
            <h2>Decouvrez aussi</h2>
            <div class="d-flex flex-wrap gap-2">
                <t t-foreach="category.parent_id.child_id" t-as="sibling">
                    <t t-if="sibling.id != category.id">
                        <a t-att-href="'/shop/category/%s-%s' % (sibling.seo_name or sibling.name, sibling.id)"
                           class="fm-seo-link btn btn-outline-secondary btn-sm rounded-pill">
                            <t t-esc="sibling.name"/>
                        </a>
                    </t>
                </t>
            </div>
        </div>
    </div>
</section>
```

### Contenu a rediger (priorite)

| Categorie | Mots cible | H2 suggerees |
|-----------|-----------|-------------|
| Trottinette electrique | 1 500 | Guide achat, reglementation BE, gammes prix, marques |
| Gyroroue | 1 000 | Choisir sa gyroroue, apprendre, securite |
| Velo electrique | 1 000 | Types (pliable, fatbike), autonomie, usage |
| Pieces detachees | 500 | Comment entretenir, quand changer |
| Accessoires | 500 | Equipement obligatoire BE, protection |

---

## PARTIE 6 : ENRICHISSEMENT PAGE PRODUIT

### FAQ produit (product.faq model)

- Modele structure : question (Char) + reponse (Html)
- Editable via formulaire backend (onglet "FAQ" sur fiche produit)
- Reponses editables via website builder (`t-field` sur answer)
- JSON-LD FAQPage auto-genere depuis les records
- Google AI Overviews : pages avec FAQ schema = 3.2x plus de chances d'apparaitre

### "Notre avis Freemoov" (editorial_review Html field)

- Section H2 dediee sur la page produit
- Editable via website builder
- Contenu type : avis expert, comparatif, pour qui, verdict
- 200-400 mots par produit (fait la difference vs concurrents qui n'ont que des specs)

### Avis clients natifs

- Toggle `product_comment` active
- Stars + count sur cartes grille et page detail
- AggregateRating dans JSON-LD
- Email automatique J+7 pour collecter

### "Ca va vous plaire" (cross-sell enrichi)

- Produits meme categorie (different de alternative_product_ids)
- Dynamic snippet `s_dynamic_snippet_products`
- Possibilite d'editer via le builder

### Blog articles lies

- Champ `blog_id` sur categorie → affiche les 3 derniers articles
- Dynamic snippet blog filtre par blog_id de la categorie du produit

---

## PARTIE 7 : CARTES PRODUIT AMELIOREES

### Avant (actuel)
```
[Image]
[Nom produit (H6)]
[pro_description HTML avec H2 trust x5]
[Badges variant 2x2]
[Prix]
[Stock badge]
[Payez par mois]
[Decouvrir CTA]
```

### Apres (cible)
```
[Image + hover effect]
[Marque (span.brand)]           ← NOUVEAU
[Nom produit (span.h6)]        ← Fix: H6 → span
[Stars ★★★★★ (23)]             ← NOUVEAU (rating_avg + rating_count)
[4 specs: 35km/h | 80km | 1800W | 60V 28Ah]  ← NOUVEAU
[Prix TVAC]
[Stock badge]
[Payez par mois]
[Decouvrir CTA]
```

**Pas de pro_description sur les cartes** — le contenu HTML marketing est supprime du listing.

### Specs inline

Les 4 specs sont extraites des attributs produit. On identifie les attributs par leur nom :
- Vitesse max (km/h)
- Autonomie (km)
- Puissance moteur (W)
- Batterie (V Ah)

```python
def _get_seo_specs_summary(self):
    """Return a compact spec string for product cards."""
    specs = {}
    for line in self.attribute_line_ids:
        name = line.attribute_id.name.lower()
        val = line.product_template_value_ids[:1]
        if not val:
            continue
        if 'vitesse' in name or 'speed' in name:
            specs['speed'] = val.name
        elif 'autonomie' in name or 'range' in name:
            specs['range'] = val.name
        elif 'puissance' in name or 'moteur' in name or 'watt' in name:
            specs['power'] = val.name
        elif 'batterie' in name or 'battery' in name:
            specs['battery'] = val.name
    return specs
```

---

## PARTIE 8 : DESIGN UX INSPIRATIONS

### Principes directeurs
- **Charte Freemoov** : vert #099D5D, fond #F5F6F7, border-radius 12px
- **Mobile-first** : 70%+ du trafic e-commerce est mobile
- **Pas de surcharge visuelle** : chaque element a un objectif SEO ou conversion

### Inspirations Shopify adaptees a Odoo

**1. Trust bar sous le header (deja en place)**
Garder tel quel — "Specialiste mobilite | Expert satisfaction | SAV | A votre ecoute"

**2. Section "Pourquoi Freemoov ?" sur categories**
Inspires de Weebot mais adapte BE :
- Showrooms Liege + Namur (pas juste en ligne)
- Reparation sur place
- Livraison gratuite BE
- Paiement 3x/24x
- Expert depuis 2019

**3. Sous-categories visuelles en haut de grille**
Cards avec icone/image + nom + lien. Ex pour trottinettes :
[Budget < 500 EUR] [Milieu de gamme] [Ultra performante] [Par marque]

**4. Section review sur cartes style Shopify**
Etoiles dorées compactes + "(23 avis)" en gris, sous le nom produit.

**5. Accordion FAQ sur page produit**
Style Bootstrap 5 natif, fond #F5F6F7, border-radius 12px.
Questions en H3, reponses editables.

**6. "Notre avis" avec avatar + signature**
Bloc style "editorial review" avec photo de l'equipe Freemoov,
verdict en 2-3 phrases, note /5, signature "L'equipe Freemoov"

---

## PARTIE 9 : CALENDRIER

### Sprint 1 (Semaine 1) — Fixes critiques
- [ ] Supprimer `pro_description` du rendu cartes categorie
- [ ] H6 nom produit → span dans cartes
- [ ] Trust block H6 → div sur page detail
- [ ] Supprimer fake reviews "Marine"
- [ ] Activer toggle `product_comment`
- [ ] AggregateRating dans JSON-LD
- [ ] Fix title categorie avec "Freemoov"

### Sprint 2 (Semaine 2) — Modeles + structures
- [ ] Creer modele `product.faq`
- [ ] Ajouter champs `editorial_review`, `seo_intro`, `blog_id`
- [ ] Template FAQ accordion avec FAQPage schema
- [ ] Template "Notre avis Freemoov"
- [ ] Stars + review count sur cartes produit
- [ ] 4 specs inline sur cartes produit

### Sprint 3 (Semaine 3) — Contenu categories
- [ ] Section SEO sous grille categorie (H2 + t-field + blog + cross-links)
- [ ] Rediger contenu trottinette electrique (1 500 mots)
- [ ] Rediger contenu gyroroue (1 000 mots)
- [ ] Configurer blog_id sur categories principales

### Sprint 4 (Semaine 4) — Contenu produits
- [ ] Remplir FAQ pour 20 produits phares
- [ ] Remplir "Notre avis" pour 20 produits phares
- [ ] Nettoyer pro_description (retirer trust HTML)
- [ ] Email automatique post-achat J+7

### Sprint 5 (Semaine 5+) — Optimisations
- [ ] Feed XML Product Reviews pour GMC (quand 50+ avis)
- [ ] Landing pages locales (Liege, Namur, Bruxelles)
- [ ] Sous-categories visuelles en haut de grille
- [ ] "Ca va vous plaire" cross-sell enrichi

---

## PARTIE 10 : KPIs

| KPI | Baseline | Objectif 3 mois | Objectif 6 mois |
|-----|----------|----------------|----------------|
| Position "trottinette electrique" BE | 2 | **1** | 1 |
| Rich snippets (GSC) | 0 pages | 50+ | 200+ |
| CTR moyen | 1.3% | 3% | 5-8% |
| Avis produit (total) | 0 | 50 | 200 |
| Etoiles dans Google Shopping | Non | - | **Oui** |
| Contenu categories (mots) | ~100 | 5 000+ | 10 000+ |
| FAQ produits | 0 | 80+ Q&A | 200+ Q&A |
| Trafic organique BE | 990/mois | 2 000 | 4 000 |
| Visibilite AI Search | 0 | Detection | Citations |
