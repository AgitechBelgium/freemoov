# Consolidation des deux repos — 2026-04-16

## Contexte

Deux clones locaux du repo `AgitechBelgium/freemoov` existaient en parallèle, avec un travail étalé sur 3 mois non committé et perdu entre les deux.

| | Repo A (gardé) | Repo B (archivé) |
|---|---|---|
| Chemin | `/Users/enzonaute/dev/CLIENTS/freemoov` | `/Users/enzonaute/dev/1 - CLIENTS/freemoov-ARCHIVE-20260416` |
| Remote | `AgitechBelgium/freemoov` | idem |
| Commits uniques | Aucun | Aucun |
| Travail checkout WIP | ✅ V3 Shopify-level (1514 lignes scss) | V2 (793 lignes) — archivé dans `.local/backups-wip/` |
| Infrastructure (docker, scripts, docs, Floa) | ❌ (rapatrié depuis B) | ✅ Était l'unique source |

## Règle stricte

**Un seul repo actif : `/Users/enzonaute/dev/CLIENTS/freemoov`**. Ne jamais rouvrir le repo archivé — tout ce qui était utile a été migré.

## Ce qui a été rapatrié depuis B

### Vers le repo (versionné git)
- `docs/archive/` : 12 fichiers historiques (audits, plans SEO, guide inventaire, analyses v19)
- `CLAUDE.md` : instructions projet pour Claude Code
- `payment_floa/` : module Floa BNPL Belgique v16.0.1.0.0 (à porter v17, à ne pas installer)
- `website_freemoov/migrations/16.0.0.1.6` → `16.0.0.2.1` : scripts post-migrate v16 non pushés
- `website_freemoov/static/src/img/homepage/*.webp` : 9 images optimisées WebP

### Vers `.local/` (ignoré git)
- `docker-compose*.yml`, `Dockerfile.odoo16` : 4 compose historiques
- `config/odoo*.conf` : 4 configs historiques
- `enterprise/` : extraction de `odoo_17.0+e.20260416.tar.gz` (1.6 Go, 1243 addons)
- `filestore/` : backup prod v16 filestore (6.7 Go, 257 entrées)
- `scripts/` : 13 scripts Python/Bash/SQL (sync prod→staging, COW apply, etc.)
- `backups-wip/` : 4 versions de sauvegarde du checkout WIP (v2, v3, v4)
- `DEVIS_MIGRATION_ODOO_V17.md` : devis client (confidentiel, non pushé)

## Ce qui n'a pas été copié

- `.claude/settings.local.json` : settings IDE locaux (régénérable)
- `__pycache__/*` : cache Python
- `*.csv` exports (volumineux, regénérables)
- `prod_cow_*.json`, `update_cow*.sql` : scripts de correction COW déjà appliqués
- `staging_dump.pgdump`, `staging_dump.sql.gz` : fichiers vides (0 et 20 B)
- Pixel_meta (underscore) : doublon du pixel-meta (tiret), à supprimer plus tard

## Licence Enterprise

Licence Odoo Enterprise stockée **uniquement** dans `.local/.env` (non committé). Voir `LOCAL_SETUP.md` pour configuration.

## Historique des branches

Les deux repos partagent les mêmes remotes. Branches locales uniques vérifiées, aucune ne contenait de commit non-pushé. La branche active est **`staging`** (contient la migration v17 en cours).

## Date de consolidation

2026-04-16
