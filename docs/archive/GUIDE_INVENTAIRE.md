# Guide d'inventaire Freemoov

## Structure du fichier exporté

| Colonne | Description | À modifier ? |
|---------|-------------|--------------|
| `id` (1ère) | ID externe du quant | ❌ NE PAS TOUCHER |
| `id` (2ème) | Doublon, ignorer | ❌ Supprimer cette colonne |
| `product_id/id` | ID externe produit | ❌ NE PAS TOUCHER |
| `product_id` | Référence [SKU] Nom | ❌ Informatif |
| `product_id/name` | Nom du produit | ❌ Informatif |
| `location_id` | Emplacement (LIEGE/NAMUR) | ❌ Informatif |
| `location_id/id` | ID externe emplacement | ❌ NE PAS TOUCHER |
| `on_hand` | Stock système actuel | ❌ Informatif (vide = 0) |
| `inventory_quantity` | **Quantité comptée** | ✅ **À MODIFIER** |
| `inventory_quantity_auto_apply` | Ancienne valeur | ❌ Supprimer avant import |
| `inventory_quantity_set` | Flag technique | ❌ Supprimer avant import |

## Étapes dans Google Sheets

### 1. Importer le CSV
- Fichier → Importer → Upload
- Séparateur : Virgule (,)
- Encodage : UTF-8

### 2. Nettoyer le fichier
- **Supprimer** la 2ème colonne `id` (doublon)
- **Supprimer** la colonne `inventory_quantity_auto_apply`
- **Supprimer** la colonne `inventory_quantity_set`

### 3. Ajouter des colonnes utiles (optionnel)
- Colonne "Écart" : `=I2-H2` (inventory_quantity - on_hand)
- Colonne "Commentaire" pour vos notes

### 4. Remplir l'inventaire
- Modifier la colonne **`inventory_quantity`** avec vos comptages
- Laisser à 0 si le produit n'est pas en stock

### 5. Filtrer par emplacement
- Créer un filtre sur `location_id`
- Travailler par zone : LIEGE/Stock puis NAMUR/Stock

### 6. Exporter pour réimport
- Fichier → Télécharger → CSV (.csv)
- Vérifier l'encodage UTF-8

## Colonnes à garder pour l'import

Pour le réimport, ne gardez QUE ces colonnes :

```
id,inventory_quantity
```

Ou si vous voulez plus de sécurité :

```
id,product_id/id,location_id/id,inventory_quantity
```

## Workflow complet

```
1. Export Odoo     → CSV avec ID externes
2. Google Sheets   → Nettoyer + Remplir inventory_quantity
3. Export Sheets   → CSV propre
4. Import Odoo     → Inventaire → Importer
5. Valider         → Appliquer l'inventaire
```
