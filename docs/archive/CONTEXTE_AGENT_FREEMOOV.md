# Contexte complet du projet Freemoov – Transmission à un agent

Ce document résume **l’ensemble des informations et du contexte** appris durant la conversation, afin qu’un agent qui ne connaît rien au projet puisse comprendre **100 % des éléments** : demandes, réalisations, architecture, pièges techniques et travail restant.

---

## 1. Présentation du projet

- **Client** : Freemoov (e-commerce mobilité : trottinettes électriques, fatbikes, gyroroues).
- **Stack** : Odoo v17 (Community ou mix Community/Enterprise selon l’environnement), site web public via le module `website_sale` et un module custom **`website_freemoov`**.
- **Environnement** : développement local via **Docker** (Odoo 17 + PostgreSQL 16). Staging Odoo.sh possible (SSH/DB mentionnés en conversation).
- **Objectif global** : adapter le site (listes produits, fiches produit, catégories) à la **charte graphique Freemoov**, améliorer le **responsive**, la **lisibilité** et la **conversion**, sans introduire de régressions.

---

## 2. Charte graphique Freemoov (à respecter partout)

- **Vert principal** : `#099D5D`
- **Vert secondaire / gradient** : `#7AC144` (souvent en dégradé avec le vert principal pour les CTA)
- **Fond gris** : `#F5F6F7`
- **Texte** : noir `#000`, gris pour secondaire `#7F7F7F`, `#BABABA` pour éléments désactivés
- **Style** : propre, professionnel, boutons avec `border-radius` (ex. 12px), ombres légères au hover, typographie lisible (titres en gras, prix bien mis en avant).

---

## 3. Rappel de TOUTES les demandes utilisateur (dans l’ordre et en détail)

### 3.1 Demandes initiales (liste produits + fiche produit + global)

1. **Analyser l’architecture** : identifier le thème utilisé et les possibilités d’optimisation en accord avec la charte Freemoov.

2. **Vue mobile et responsive**  
   - Listes de produits et fiches produit mal organisées sur mobile.  
   - Éléments et disposition peu lisibles, « fouilli ».  
   - Objectif : centrer les éléments, normaliser l’affichage pour que le responsive soit clair (détails, infos produit, blocs autour).  
   - Exemple de page : `https://freemoov-staging-27497775.dev.odoo.com/shop/category/trottinette-electrique-1`

3. **Image produit en sticky (desktop)**  
   - Sur la fiche produit, l’image (ou la zone photo) doit rester **fixe** au scroll : elle « descend » avec le défilement pour ne rien cacher.  
   - Problème actuel : un **gros bloc blanc vide** sous l’image, inutile et qui pollue la page.

4. **Remplacer le bouton « Télécharger » par un bouton « Partager »**  
   - Supprimer le bouton de téléchargement d’image.  
   - À la place : un **bouton de partage** qui copie le **lien de la page** (raccourci ou non) dans le presse-papier.

5. **Position du logo Cœur (wishlist)**  
   - Le cœur est « à la mauvaise place », des dizaines de px plus bas.  
   - Il doit être **centré** par rapport à la div / au bloc image ou au bloc fiche produit.

6. **Réorganisation des blocs sous la fiche produit**  
   - Une ROW avec caractéristiques textuelles (image, fabricant, texte…) et une ROW avec statistiques (autonomie, puissance, vitesse…) avec des logos.  
   - Problème : layout 1-1 en horizontal, la place pour les stats est très petite alors que l’autre colonne peut être immense selon le texte.  
   - Objectif : soit fixer une des parties, soit remodeler l’ensemble pour un rendu propre et adaptable (beaucoup ou peu de texte).

7. **Prix TOUJOURS en TVA belge 21 % (pages catégories)**  
   - Les prix sur les **pages catégories** doivent **toujours** être affichés **TVA comprise (TVA belge 21 %)**, quel que soit le pays / VPN / origine du visiteur.  
   - Éviter que des clients à l’étranger ou avec VPN voient un prix selon leur pays.

8. **Blocs éditable sous les produits des pages catégories**  
   - Pouvoir ajouter des **éléments éditable (snippets)** **sous les produits** de chaque page catégorie (sous les bullets / liste de produits).  
   - Contenu possiblement **spécifique par catégorie** (comme dans une vidéo Loom décrite par l’utilisateur).

9. **Flèches du carousel fiche produit**  
   - Les **flèches** de sélection d’images du carousel produit doivent être **toujours visibles** (ou au moins visibles au clic sur les bords de la photo).

10. **Design global**  
    - Analyser ce qui ne va pas dans le design (incohérences, bugs visuels) et proposer des corrections **adaptées, cohérentes, sans bugs**, pour améliorer la conversion et l’expérience client.

### 3.2 Demandes après premières implémentations

11. **Lancer le projet Odoo via Docker (v17)** avec toutes les assets et la DB, et vérifier que tout est correct et fonctionnel.

12. **Correction critique « vue article »**  
    - Après des modifs SCSS, la **vue produit** affichait « plus aucune information, tout est blanc » (plus d’images, plus d’infos).  
    - Il a fallu corriger les overrides CSS qui cassaient le layout natif Odoo (images, flex).

13. **Centrage et affichage « style Tailwind » liste produits**  
    - Sur les listes produits : centrer correctement les éléments, affichage **propre type grid** pour distinguer clairement les informations (prix, stock, CTA, etc.).

14. **Emojis dans les noms d’attributs**  
    - Les emojis (⛽, ⚡, 🔋, 🚀, etc.) dans les **noms d’attributs produit** doivent s’afficher **correctement** (pas de transformation en texte ou coupure).

15. **Refonte styling liste shop + fiche produit**  
    - Liste : blocs produits **propres, professionnels, attractifs** ; bouton « Ajouter au panier » **mis en avant** ; badge de disponibilité et prix barré **bien positionnés** ; réorganisation des éléments dans le bloc produit pour la conversion.  
    - Fiche produit : même logique de **netteté et professionnalisme**.

16. **Doublon bouton panier**  
    - Sur les cartes produits (liste), **deux boutons « Ajouter au panier »** apparaissaient ; il fallait n’en garder qu’un.

### 3.3 Dernière demande (contexte actuel)

17. **Fiche produit toujours très désorganisée**  
    - Éléments partout, **image avec un immense bloc blanc en dessous**.  
    - Demande : **revoir tout** et proposer un **plan cohérent, joli**, en accord avec ce qui a été fait sur la **liste produits**.

18. **Frameworks / approche CSS**  
    - Vérifier ce qu’on peut faire avec les **meilleurs usages** (SCSS ou Tailwind si pertinent) pour rendre le tout propre.

19. **Intégration du bloc HTML de production (liste catégories)**  
    - Sur la **fiche produit**, intégrer la **même phrase / le même bloc** que celui utilisé en **production** sous les listes de produits catégories, à savoir le bloc `prod_desc_div` avec le contenu suivant (donné par l’utilisateur) :
    - **Payez par mois** : à partir de 125,62€/mois en 30 fois (lien `/payez-par-mois`), TAEG 5,99 %, uniquement en magasin.
    - **ACHETEZ EN TOUTE CONFIANCE** : boutons/liens « Spécialiste en mobilité » (`/about-us`), « Services après-vente ultra rapide » (`/services-atelier`), « Magasin et Atelier accessible » (`/magasin`).
    - **Besoin de conseils ?** : texte « Nous sommes là… », numéro **+32 81 65 91 66**.
    - **Paiement en ligne sécurisé** : texte + image bannière logos paiement (URL production : `https://www.freemoov.com/web/image/27551-1ff2a372/...`).
    - **Avis clients** : 4.8 étoiles, lien « Voir les avis Google ».
    - **Vos avantages Freemoov** / **Qui sommes-nous ?** : texte Freemoov (mobilité, trottinettes, fatbikes, gyroroues, Liège et Namur).

Ce bloc doit donc être intégré sur la **fiche produit** (pas seulement sur les listes catégories), de façon lisible et cohérente avec le reste du design.

---

## 4. Architecture technique du module `website_freemoov`

### 4.1 Structure des fichiers principaux

- **`website_freemoov/__manifest__.py`**  
  - Déclare les dépendances (`website_sale`, `website_sale_wishlist`, `website_sale_stock`, `ust_common_features`, etc.), les vues XML, les assets (SCSS, JS).  
  - **Version actuelle** : `17.0.0.1.1`. À **incrémenter** après chaque modification de vues XML pour forcer le rechargement des vues par Odoo.

- **`website_freemoov/views/inherited_template.xml`**  
  - Fichier central d’héritage des templates Odoo (QWeb). Contient notamment :
    - Héritages **liste produits** (`products_item`, `products_add_to_cart`, breadcrumb, etc.).
    - Héritages **fiche produit** : template `product_details_inherited` (inherit_id `website_sale.product`), xpath sur `#product_detail`, `#product_details`, prix, stock, CTA, wishlist, compare, `custom_product_list`, `custom-text`, etc.
    - Bloc **catégories** (bannière sous les produits, `category_bottom_content`).
  - Les xpath ciblent des éléments du template standard `website_sale.product` ; l’ordre d’injection et le contenu définissent la structure réelle de la page.

- **`website_freemoov/static/src/scss/shop.scss`**  
  - Styles des **listes de produits** (grille et liste) : cartes produits, image, prix, badge stock, variantes, bouton « Ajouter au panier », wishlist, compare.  
  - Responsive mobile déjà travaillé (padding, tailles, flex).

- **`website_freemoov/static/src/scss/product_detail.scss`**  
  - Styles de la **fiche produit** : `#product_detail`, `#o-carousel-product` (sticky, flèches), `#product_details` (titre, prix, CTA, wishlist, compare, `custom-text`), propriétés, avis, etc.  
  - C’est ici qu’il faut corriger le bloc blanc sous le carousel et refaire le layout de la colonne droite.

- **`website_freemoov/static/src/js/common.js`**  
  - Logique partagée : par ex. **partage de lien** (copie URL dans le presse-papier), compteur du carousel produit (slide X/Y).  
  - Référence à `.carousel_product_num` et `#o-carousel-product`.

- **`website_freemoov/models/product.py`**  
  - Surcharges sur `product.template` (et éventuellement champs custom) pour la **TVA belge forcée** et la logique métier liée aux prix / stock.

- **`website_freemoov/models/product_public_category.py`** (si présent)  
  - Champ **`category_bottom_content`** pour le contenu éditable sous les produits des pages catégories.

### 4.2 Ordre des éléments dans la fiche produit (état actuel du DOM)

D’après l’analyse du template et des xpath :

1. Fil d’ariane (breadcrumb)  
2. Colonne gauche : `o_wsale_product_images` → carousel `#o-carousel-product` (images produit)  
3. Colonne droite (`#product_details`) :
   - Ligne « top-line » : marque, avis (reviews)
   - **h1** (titre produit)
   - **product_tags_block** (badges type BIG PROMO, Soldes)
   - Sélecteur de variantes (t-placeholder `select`)
   - **Prix** (injecté après `t-placeholder='select'` via xpath)
   - **Label stock** (En stock / Rupture)
   - **custom_product_list** (En stock, Délai 1–5 jours, Services Freemoov)
   - **add_to_cart_wrap** (bouton Ajouter au panier)
   - **product_option_block** (wishlist)
   - **compare-box** (Voir disponibilité en magasin, bouton Comparez)
   - **o_product_terms_and_share** (conditions, garanties, partage)
   - **custom-text** (paiement sécurisé + avantages Freemoov – version actuelle limitée)

Ensuite, sous la section `#product_detail`, viennent les blocs « properties » (stats, description, caractéristiques, livraison, garantie), accessoires, galerie, safety, avis clients, etc.

### 4.3 Cause identifiée du « bloc blanc » sous l’image

- **`#o-carousel-product`** a `position: sticky !important; top: 120px;` et **`max-height: calc(100vh - 140px)`**.
- **`.o_wsale_product_images`** a **`align-self: flex-start`**.
- Conséquence : hauteur fixe du carousel + colonne gauche qui ne s’étire pas comme la droite → grand espace vide sous le carousel.  
- **Piste de correction** : supprimer `max-height` sur le carousel pour qu’il prenne la hauteur naturelle des images ; garder `sticky` et `top` (ex. 100px).

### 4.4 Problème des doublons de boutons (liste produits)

- Deux vues **actives** injectaient du contenu dans `.o_wsale_product_btn` :
  - Une copie **website-specific** du template natif `website_sale.products_add_to_cart` (id 3510),
  - Une copie **website-specific** du template custom `website_freemoov.products_add_to_cart` (id 3567).
- **Solution appliquée** : suppression en base des deux enregistrements `ir_ui_view` (IDs 3510 et 3567) pour que seule la vue générique du module custom soit utilisée.  
- **Leçon** : après mise à jour de templates, Odoo peut garder des **copies website-specific** en base ; si les changements ne s’affichent pas, il faut soit incrémenter la version du module, soit supprimer ces copies dans `ir_ui_view`.

---

## 5. Ce qui a déjà été fait (résumé implémenté)

- **Liste produits (shop)** :  
  - Grille avec cartes retravaillées (ombre, border-radius, hover).  
  - Prix TVAC, badge stock (En stock / Rupture) avec point coloré.  
  - Un seul bouton « Ajouter au panier » par produit (résolution du doublon).  
  - Typo (marque, titre, prix, attributs avec emojis).  
  - Variantes en grille 2 colonnes, CTA vert en gradient.  
  - Responsive mobile ajusté.  
  - `prod_desc_div` et `oe_subdescription` masqués en vue grille pour alléger.

- **Fiche produit (déjà partiellement)** :  
  - Titre h1, prix, labels, CTA avec gradient vert, wishlist/compare, partage (remplacement téléchargement), flèches carousel visibles.  
  - **Pas encore fait** : suppression du bloc blanc, réorganisation complète de la colonne droite, intégration du gros bloc « Achetez en toute confiance » de production.

- **Prix TVA belge** : logique côté backend (product template / website) pour forcer l’affichage en TVA belge 21 % sur les pages catégories.

- **Catégories** : champ `category_bottom_content` et affichage sous les produits (snippets éditable par catégorie).

- **Docker** : `docker-compose.yml` pour Odoo 17 + PostgreSQL 16 ; commande de mise à jour du module :  
  `docker exec freemoov-odoo17-test odoo -c /etc/odoo/odoo.conf -u website_freemoov --stop-after-init`

---

## 6. Plan de refonte fiche produit (à exécuter)

Le plan détaillé est dans **`.cursor/plans/refonte_fiche_produit_aff6036b.plan.md`**. Résumé des tâches :

1. **Corriger sticky + bloc blanc**  
   Dans `product_detail.scss` : garder `position: sticky` et `top` sur `#o-carousel-product`, **supprimer** `max-height: calc(100vh - 140px)`.

2. **Réorganiser `#product_details`** (XML)  
   Ordre cible : badges → titre → prix → **un seul** label stock → liste confiance (livraison, retour, garantie) → CTA pleine largeur → wishlist + comparer sur une ligne → « Payer en plusieurs fois » → bloc paiement → **bloc « Achetez en toute confiance »** (contenu production).

3. **Ajouter le bloc « Achetez en toute confiance »**  
   Remplacer l’actuel `custom-text` par un bloc structuré contenant :  
   - Paiement sécurisé (texte + image logos).  
   - ACHETEZ EN TOUTE CONFIANCE (liens about-us, services-atelier, magasin).  
   - Besoin de conseils ? + numéro +32 81 65 91 66.  
   - Paiement en ligne sécurisé + bannière.  
   - Avis clients 4.8 + lien Google.  
   - Vos avantages Freemoov / Qui sommes-nous ? (texte Freemoov).  
   - Éventuellement « Payez par mois » (125,62€/mois, lien `/payez-par-mois`).

4. **SCSS fiche produit**  
   CTA à 100 % de largeur, `#product_option_block` en flex horizontal, nouveaux blocs `.trust-features`, `.trust-block`, `.confidence-block`, etc., palette et espacements cohérents avec la liste produits.

5. **Responsive mobile**  
   Stack vertical, CTA pleine largeur, blocs confiance empilés, tailles de police adaptées (titre 22px, prix 24px), carousel non sticky en mobile (déjà prévu).

6. **Déploiement / test**  
   Incrémenter la version dans `__manifest__.py`, lancer la mise à jour du module, vérifier en navigateur ; si les vues ne se mettent pas à jour, envisager la suppression des copies website-specific dans `ir_ui_view` (voir section 4.4).

---

## 7. Pièges et bonnes pratiques (pour l’agent)

- **Modification de vues XML** : toujours **incrémenter la version** du module dans `__manifest__.py` pour forcer le rechargement. Si le front ne change pas, vérifier en base les vues `ir_ui_view` du site (website_id) et supprimer les copies qui écrasent le template custom.

- **CSS et layout Odoo** : ne pas surcharger avec des `height` ou `flex` qui cassent le layout natif (ex. images avec `padding-top` et `position: absolute`). Tester après chaque changement important sur une fiche produit réelle.

- **Un seul CTA « Ajouter au panier »** : ne pas réinjecter un second template ou un second bouton dans le même conteneur (`.o_wsale_product_btn` en liste, `#add_to_cart_wrap` en fiche).

- **Emojis** : les noms d’attributs peuvent contenir des emojis ; éviter `text-transform: uppercase` ou des font-size trop petites qui les rendent illisibles.

- **Base de données** : les commandes type `DELETE FROM ir_ui_view WHERE id = ...` doivent être faites avec précaution (sauvegarde si besoin). Conteneur PostgreSQL : `freemoov-postgres17` (ou équivalent selon `docker-compose`), base typiquement `freemoov-staging-27497775` ou nom local.

- **Répondre en français** : l’utilisateur a indiqué vouloir les réponses en français.

---

## 8. Fichiers à modifier pour la refonte fiche produit

| Fichier | Rôle |
|--------|------|
| `website_freemoov/views/inherited_template.xml` | XPath fiche produit (ordre des blocs, contenu du bloc confiance, suppression doublons stock). |
| `website_freemoov/static/src/scss/product_detail.scss` | Sticky/carousel, layout colonne droite, CTA 100 %, trust-block, responsive. |
| `website_freemoov/__manifest__.py` | Incrémenter version après modif XML. |

---

## 9. Contenu HTML de production à intégrer (référence)

Le bloc ci-dessous est celui utilisé en production dans les listes catégories (`prod_desc_div`). Sur la fiche produit, il faut en s’inspirer pour le **bloc « Achetez en toute confiance »** (structure, liens, textes, image paiement) ; l’image peut rester celle du module ou être remplacée par l’URL production selon la convention du projet.

```html
<div class="prod_desc_div">
  <p><font class="text-600">Payez par mois : à partir de&nbsp;</font><font class="text-o-color-1"><strong><a href="/payez-par-mois">125,62€ / mois en 30&nbsp;fois</a></strong></font><font class="text-600"> (Sur base de 3499€). TAEG de 5,99%. Uniquement disponible en magasin.</font></p>
  <p><br></p>
  <h2><strong><em>ACHETEZ EN TOUTE CONFIANCE</em></strong></h2>
  <p><a href="/about-us" class="btn btn-secondary"><span class="fa fa-check"></span>&nbsp;Spécialiste en mobilité </a></p>
  <p><a href="/services-atelier" class="btn btn-secondary"><span class="fa fa-check"></span>&nbsp;Services après-vente ultra rapide</a></p>
  <p><a href="/magasin" class="btn btn-secondary"><span class="fa fa-check"></span>&nbsp;Magasin et Atelier accessible</a></p>
  <p><br></p>
  <h2><strong>Besoin de conseils ?&nbsp;</strong></h2>
  <p><strong>Nous sommes-là ! Nos experts sont à votre disposition</strong>&nbsp;pour vous aider à trouver le produit qui vous correspond.&nbsp;<u>Appelez-nous</u>&nbsp;afin que nous puissions en discuter.&nbsp;</p>
  <p>+32 81 65 91 66</p>
  <p><br></p>
  <h2><strong><em>Paiement en ligne sécurisé</em></strong></h2>
  <p>Payez de manière 100 % sécurisée avec le moyen de paiement qui vous convient.</p>
  <p><img class="img-fluid" src="https://www.freemoov.com/web/image/27551-1ff2a372/Bannier%20logo%20paiement%20%281%29.png"></p>
  <p><br></p>
  <p><strong>Avis de nos supers clients | 4.8&nbsp;​<i class="fa fa-star"></i>...</strong></p>
  <p>... (<a href="...">Voir les&nbsp;avis Google</a>)</p>
  <p><br></p>
  <h2><em><strong>Vos avantages Freemoov</strong></em></h2>
  <h2><em><strong>Qui sommes-nous ?</strong></em></h2>
  <p>Chez&nbsp;<b>Freemoov</b>, la mobilité... (texte complet Freemoov, Liège et Namur).</p>
</div>
```

L’agent devra **reproduire cette structure et ce contenu** dans le template de la fiche produit (bloc après `o_product_terms_and_share`), en utilisant des classes SCSS dédiées (ex. `trust-block`, `confidence-block`) pour un rendu propre et cohérent avec la liste produits et la charte Freemoov.

---

Ce document constitue le **contexte complet** à transmettre à un agent pour qu’il comprenne l’ensemble des demandes, l’état actuel du projet et le travail restant (refonte fiche produit + intégration du bloc « Achetez en toute confiance »).
