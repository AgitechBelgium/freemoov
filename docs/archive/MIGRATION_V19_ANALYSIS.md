# Analyse de Migration Odoo v17 → v19 - Projet Freemoov

## 📋 Résumé Exécutif

**État actuel** : Les modules sont migrés vers Odoo 17 (branche `migrate-to-v17-ennau`)
**Objectif** : Migration vers Odoo 19 avec maintien de l'apparence visuelle v16

### Modules à migrer

| Module | Version actuelle | Complexité |
|--------|-----------------|------------|
| `website_freemoov` | 17.0.0.0.7 | 🔴 Haute |
| `ust_common_features` | 17.0.0.0.0 | 🔴 Haute |
| `pixel-meta` | 17.0.3.1.0 | 🟡 Moyenne |
| `website_cookies_consent` | 17.0.1.1.1 | 🟡 Moyenne |
| `website_google_tag` | 17.0.1.1.0 | 🟢 Faible |
| `sky_signup_google_recaptcha` | 17.0.1.1.0 | 🟢 Faible |
| `mask_as_done_extends` | 17.0.1.0.1 | 🟢 Faible |
| `moov_reparation` | 17.0.1.0.0 | 🟢 Faible |

---

## 🔄 Changements Majeurs v17 → v18 → v19

### 1. JavaScript / OWL Framework

#### Changements critiques :
```javascript
// v17 (actuel)
import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

// v18/v19 (cible)
import publicWidget from "@web/legacy/js/public/public_widget";  // Toujours disponible
import { rpc } from "@web/core/network/rpc";  // jsonrpc déprécié → rpc
```

**Actions requises :**
- [ ] Remplacer `jsonrpc` par `rpc` dans tous les fichiers JS
- [ ] Vérifier la compatibilité des imports OWL
- [ ] Adapter les widgets publics si nécessaire

### 2. Templates XML / QWeb

#### Bootstrap 5.3 (v18/v19)
- Les classes Bootstrap restent largement compatibles
- Quelques ajustements mineurs possibles pour les modals et dropdowns

#### Changements XPath potentiels
Les templates Odoo de base peuvent avoir changé de structure. Les `inherit_id` suivants doivent être vérifiés :
- `website_sale.products_breadcrumb`
- `website_sale.products_item`
- `website_sale.product`
- `website_blog.dynamic_filter_template_blog_post_card`

### 3. Contrôleurs Python

#### Signature de méthode `shop()`
```python
# v17 (actuel)
def shop(self, page=0, category=None, search='', min_price=0.0, max_price=0.0, ppg=False, **post):

# v18/v19 - Vérifier les nouveaux paramètres
# Possibles ajouts : order, attrib_values, etc.
```

### 4. Modèles / ORM

#### Changements potentiels :
- Vérifier les champs `product.template` et `product.public.category`
- S'assurer que `stock.quant` et ses champs (`on_hand`, etc.) existent toujours
- Vérifier le module `stock_dropshipping` et sa route

---

## 📁 Fichiers à Modifier

### JavaScript (Haute priorité)

| Fichier | Changements |
|---------|-------------|
| `website_freemoov/static/src/js/common.js` | `jsonrpc` → `rpc` |
| `website_freemoov/static/src/js/variant.js` | Vérifier imports OWL |
| `ust_common_features/static/src/js/snippets/ust_all_in_one_frontend.js` | `jsonrpc` → `rpc` |
| `ust_common_features/static/src/js/snippets/ust_all_in_one_s.js` | `jsonrpc` → `rpc` |
| `ust_common_features/static/src/js/ust_carousel_product.js` | OK (vanilla JS) |
| `pixel-meta/static/src/js/cookies_bar.js` | Vérifier imports |
| `website_cookies_consent/static/src/js/cookies_consent.js` | Vérifier imports |
| `sky_signup_google_recaptcha/static/src/js/signup.js` | Vérifier imports |

### Manifests (Tous les modules)

Tous les `__manifest__.py` doivent passer de `'version': '17.x.x.x.x'` à `'version': '19.x.x.x.x'`

### Templates XML

| Fichier | Risque |
|---------|--------|
| `website_freemoov/views/inherited_template.xml` | 🔴 Haut - Nombreux XPath |
| `website_freemoov/views/header_freemoov_template.xml` | 🟡 Moyen |
| `ust_common_features/views/snippets/ust_all_in_one_slider.xml` | 🟡 Moyen |

---

## 🧪 Plan de Test Local

### Prérequis

1. **Docker avec Odoo 19** ou installation locale
2. **Base de données de test** (copie de production migrée)
3. **PostgreSQL 15+**

### Étapes de test

```bash
# 1. Cloner Odoo 19
git clone https://github.com/odoo/odoo.git --branch 19.0 --depth 1 odoo-19

# 2. Créer un environnement virtuel
python3 -m venv venv-odoo19
source venv-odoo19/bin/activate
pip install -r odoo-19/requirements.txt

# 3. Configurer odoo.conf
cat > odoo.conf << EOF
[options]
addons_path = ./odoo-19/addons,./freemoov-modules
db_host = localhost
db_port = 5432
db_user = odoo
db_password = odoo
db_name = freemoov_v19_test
EOF

# 4. Lancer Odoo
./odoo-19/odoo-bin -c odoo.conf -i base --stop-after-init
./odoo-19/odoo-bin -c odoo.conf -u website_freemoov
```

### Checklist de validation

- [ ] Odoo démarre sans erreur
- [ ] Tous les modules s'installent
- [ ] Page d'accueil s'affiche correctement
- [ ] Shop/Catalogue fonctionne
- [ ] Détail produit s'affiche
- [ ] Panier fonctionne
- [ ] Sliders/Carrousels fonctionnent
- [ ] Header personnalisé s'affiche
- [ ] Footer s'affiche
- [ ] Recherche fonctionne
- [ ] Wishlist fonctionne
- [ ] Comparaison produits fonctionne

---

## ⚠️ Points d'Attention

### 1. Dépendances externes
- **Owl Carousel** : Librairie jQuery, peut nécessiter des ajustements
- **Font Awesome** : Vérifier la version incluse dans Odoo 19
- **Bootstrap** : v5.3 dans Odoo 18/19

### 2. Champs personnalisés
Les champs suivants sont ajoutés aux modèles Odoo :
- `product.template` : `pro_description`, `delivery_return`, `warranty_support`, `summary`, `is_dropship_product`
- `product.public.category` : `brand_ids`, `category_description`
- `product.attribute` : `image_1920`, `category_id`

### 3. Modèles personnalisés
- `all_in.one.slider`
- `ust.product.tab`
- `ust.product.tab.line`
- `ust.product.brand`
- `menu.cms`

---

## 📊 Estimation du Travail

| Tâche | Temps estimé |
|-------|--------------|
| Mise à jour des manifests | 30 min |
| Migration JavaScript | 2-4 heures |
| Vérification/Adaptation XML | 4-8 heures |
| Tests et corrections | 8-16 heures |
| **Total estimé** | **15-30 heures** |

---

## 🚀 Prochaines Étapes

1. ✅ Synchroniser `staging` avec `migrate-to-v17-ennau`
2. ⬜ Créer une branche `migrate-to-v19`
3. ⬜ Mettre à jour tous les `__manifest__.py` vers v19
4. ⬜ Migrer les fichiers JavaScript
5. ⬜ Tester avec Odoo 19 en local
6. ⬜ Corriger les erreurs XPath si nécessaire
7. ⬜ Valider visuellement chaque fonctionnalité
8. ⬜ Déployer en staging pour tests utilisateurs
