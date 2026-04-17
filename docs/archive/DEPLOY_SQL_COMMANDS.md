# Commandes SQL de deploiement — Production

## Pre-requis
- Branche `seo-overhaul` mergee dans `production`
- Git push vers Odoo.sh (le build s'execute automatiquement)
- Attendre que le build soit termine (1-2 min)

## 1. Apres le build Odoo.sh (automatique via migration scripts)

Les migration scripts `16.0.0.3.0` et `16.0.0.4.0` s'executent automatiquement lors du module upgrade.
Ils font :
- Clear asset + sitemap cache
- Sync COW copies header/footer
- Set seo_name sur les categories
- Set website_meta_title sur categories + produits
- Fix homepage_url (/ vs /home)
- Activer toggle product_comment (reviews natives)

## 2. Commandes SQL manuelles (apres le build)

### 2.1 Configurer shop_ppg (produits par page)

```sql
-- Limiter a 24 produits par page (performance mono-thread)
UPDATE website SET shop_ppg = 24 WHERE id = 1;
```

### 2.2 Sync COW copies UST slider

```sql
-- Synchroniser le template product_slider COW copy
-- Base view id: a determiner en prod (SELECT id FROM ir_ui_view WHERE key = 'ust_common_features.product_slider' AND website_id IS NULL)
-- COW view id: a determiner en prod (SELECT id FROM ir_ui_view WHERE key = 'ust_common_features.product_slider' AND website_id = 1)

-- Trouver les IDs
SELECT id, key, website_id FROM ir_ui_view
WHERE key = 'ust_common_features.product_slider'
ORDER BY website_id;

-- Sync COW → base (remplacer BASE_ID et COW_ID par les valeurs trouvees)
UPDATE ir_ui_view AS cow
SET arch_db = base.arch_db
FROM ir_ui_view AS base
WHERE base.id = BASE_ID AND cow.id = COW_ID
  AND base.arch_db IS DISTINCT FROM cow.arch_db;
```

### 2.3 Sync COW copies footer

```sql
-- Footer base → COW
UPDATE ir_ui_view AS cow
SET arch_db = base.arch_db
FROM ir_ui_view AS base
WHERE base.id = 3053 AND cow.id = 3479
  AND base.arch_db IS DISTINCT FROM cow.arch_db;

-- Header base → COW
UPDATE ir_ui_view AS cow
SET arch_db = base.arch_db
FROM ir_ui_view AS base
WHERE base.id = 3500 AND cow.id = 3533
  AND base.arch_db IS DISTINCT FROM cow.arch_db;
```

> NOTE: Les IDs 3053/3479/3500/3533 sont specifiques a la DB actuelle.
> En prod (Odoo.sh), les IDs peuvent etre differents apres un rebuild.
> Utiliser les queries suivantes pour trouver les bons IDs:
> ```sql
> SELECT id, key, website_id FROM ir_ui_view
> WHERE key IN ('website_freemoov.footer', 'website_freemoov.header_freemoov_two')
> ORDER BY key, website_id;
> ```

### 2.4 Clear caches

```sql
-- Clear asset cache (force regeneration CSS/JS)
DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';

-- Clear sitemap cache (force regeneration avec nouvelles URLs)
DELETE FROM ir_attachment WHERE url LIKE '/sitemap-%' AND type = 'binary';
```

### 2.5 Inserer des FAQ de test (optionnel — mieux via l'interface backend)

Les FAQ doivent etre saisies via le **backend Odoo** :
1. Aller dans Ventes > Produits > ouvrir un produit
2. Onglet "FAQ (SEO)"
3. Ajouter des lignes (question + reponse)

Si insertion SQL necessaire (pour migration bulk) :
```sql
-- Les champs question et answer sont JSONB (translatable)
-- Utiliser le dollar-quoting PostgreSQL pour eviter les problemes d'echappement
INSERT INTO product_faq (product_id, question, answer, sequence, create_uid, write_uid, create_date, write_date)
VALUES (
    PRODUCT_ID,
    $q${"fr_BE": "La question en français ?", "en_US": "The question in English?"}$q$::jsonb,
    $a${"fr_BE": "<p>La réponse en <strong>français</strong>.</p>", "en_US": "<p>Answer in English.</p>"}$a$::jsonb,
    10, 2, 2, NOW(), NOW()
);
```

### 2.6 Inserer le contenu editorial (optionnel — mieux via l'interface)

```sql
-- Editorial review (champ JSONB)
UPDATE product_template
SET editorial_review = $er${"fr_BE": "<h2>Notre verdict</h2><p>Contenu de l'avis expert...</p>"}$er$::jsonb
WHERE id = PRODUCT_ID;

-- SEO intro categorie (champ JSONB)
UPDATE product_public_category
SET seo_intro = $si${"fr_BE": "<h2>Guide d'achat</h2><p>Contenu intro SEO...</p>"}$si$::jsonb
WHERE id = CATEGORY_ID;

-- Video URL (champ VARCHAR, pas JSONB)
UPDATE product_template
SET video_url = 'https://www.youtube.com/watch?v=VIDEO_ID'
WHERE id = PRODUCT_ID;

-- Blog associe a une categorie
UPDATE product_public_category
SET blog_id = BLOG_ID
WHERE id = CATEGORY_ID;
```

## 3. Verification post-deploiement

```bash
# Verifier la page categorie
curl -s "https://www.freemoov.com/shop/category/trottinette-electrique-1" | python3 -c "
import sys, re, json
html = sys.stdin.read()
print(f'Page: {len(html)/1024:.0f} KB')
print(f'H1: {len(re.findall(r\"<h1\", html))}')
print(f'JSON-LD: {len(re.findall(r\"application/ld.json\", html))}')
print(f'Hreflang: {len(re.findall(r\"hreflang\", html))}')
"

# Verifier la page produit
curl -sL "https://www.freemoov.com/shop/trottinette-electrique-dualtron-togo-limited-1190" | python3 -c "
import sys, re, json
html = sys.stdin.read()
jsonld = re.findall(r'<script[^>]*type=\"application/ld\+json\"[^>]*>(.*?)</script>', html, re.DOTALL)
for j in jsonld:
    try:
        d = json.loads(j)
        print(f'  @type: {d.get(\"@type\")}')
    except: pass
"

# Verifier les robots.txt
curl -s "https://www.freemoov.com/robots.txt"

# Verifier le magasin
curl -sL "https://www.freemoov.com/magasin" | python3 -c "
import sys, re, json
html = sys.stdin.read()
jsonld = re.findall(r'<script[^>]*type=\"application/ld\+json\"[^>]*>(.*?)</script>', html, re.DOTALL)
for j in jsonld:
    try:
        d = json.loads(j)
        print(f'  {d.get(\"@type\")}: {d.get(\"name\")} — {d.get(\"aggregateRating\",{}).get(\"ratingValue\")}')
    except: pass
"
```

## 4. Actions manuelles dans le website builder

Ces elements doivent etre corriges manuellement dans l'editeur Odoo :

1. **H3 CMS dans les blocs oe_structure** (sliders "TOP DU MOMENT", "Selection Freemoov") :
   - Naviguer vers la page categorie
   - Cliquer "Modifier"
   - Supprimer les blocs slider existants et les re-inserer
   - Cela regenerera le HTML avec les nouveaux templates (div au lieu de H3)

2. **H1 CMS dupliques** sur la page categorie :
   - Les H1 supplementaires ("DECOUVREZ TOUTES NOS TROTTINETTES") viennent du CMS
   - Les modifier en H2 ou les supprimer dans l'editeur

3. **Contenu SEO des categories** :
   - Naviguer vers chaque page categorie
   - Cliquer "Modifier"
   - Le bloc "SEO Introduction" apparait au-dessus de la grille — y ajouter du contenu
   - Le bloc "Contenu SEO" apparait sous la grille — y ajouter FAQ, guide d'achat

4. **FAQ produits** :
   - Backend > Produits > Onglet "FAQ (SEO)" > Ajouter des FAQ par produit
   - Les FAQ apparaitront automatiquement sur la page produit + JSON-LD FAQPage

5. **Editorial review** :
   - Backend > Produits > Onglet "Contenu SEO" > Champ "Notre avis Freemoov"
   - OU directement sur la page produit via le website builder (section editable)

6. **Video produit** :
   - Backend > Produits > Onglet "Contenu SEO" > Champ "Video URL"
   - Coller l'URL YouTube/Instagram/TikTok
