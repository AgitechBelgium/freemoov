# Plan de migration Freemoov Odoo v16 → v17

## État au 2026-04-16

- **Production** : Odoo 16 (`freemoov.odoo.com`), actif avec features SEO/GMC/checkout récentes
- **Staging** : Odoo 17 (`freemoov-staging-29368987.dev.odoo.com`), migration technique déjà validée le 23/01/2026 (voir `archive/AUDIT_MIGRATION_V16_V17.md`)
- **Split critique** : ~53 commits de features sont sur production v16, absents de staging v17. À porter avant bascule.

## Stratégie globale

La migration BDD est assurée par **Odoo SA via Upgrade Service** (https://upgrade.odoo.com). Gratuit en Enterprise. On ne fait pas de OpenUpgrade DIY.

Trois voies parallèles :
1. **Données core** → Upgrade Service Odoo SA (dump v16 → dump v17 migré)
2. **Modules custom** → portage manuel v16 → v17 (cf `PORTING_CHECKLIST.md`)
3. **Modules tiers/OCA** → vérifier dispo v17 (pixel-meta Garazd déjà en v17 ✓)

## Phases

### Phase 0 — Gel production (J-14)
- Merge freeze sur `origin/production`
- Tag `pre-migration-v16` sur dernier commit prod
- Communication aux devs

### Phase 1 — Port code prod → staging v17 (J-14 à J-7)
Voir `PORTING_CHECKLIST.md`. Lots :
1. Cleanup staging (doublon `pixel_meta`, fichier vide `staging` root)
2. Modules Python simples (`product_faq.py`, `performance_hints.xml`)
3. Module `google_merchant_center` complet
4. Module SEO (`seo.py` 812 lignes + 5 vues)
5. Checkout redesign (unifier WIP + `cart_checkout_templates.xml`)
6. Port `payment_floa` v16 → v17 (installable=False)

### Phase 2 — Migration data (J-7 à J-3)
1. Dump prod v16 fresh (via Odoo.sh Backups ou `pg_dump` SSH)
2. Upload sur upgrade.odoo.com (mode TEST en parallèle du code, PROD la veille)
3. Restore dump v17 sur staging local (docker)
4. Itérer 3-5 passes : chaque passe corrige post-migrate scripts + relance

### Phase 3 — Réconciliation (filet anti-gap)
Script `tools/reconcile_v16_v17.py` (XML-RPC) compare prod v16 et staging v17 sur modèles critiques :
- **Comptabilité** : `account.move` (count + sum amount_total), `account.move.line`, `account.payment`
- **Ventes** : `sale.order`, `sale.order.line`
- **Stock** : `stock.picking`, `stock.move`, `stock.quant`
- **Achats** : `purchase.order`
- **POS** : `pos.order`, `pos.payment`, `pos.session`
- **FSM/SAV** : `project.task` (is_fsm=True), `helpdesk.ticket`
- **Contacts** : `res.partner`
- **Marketing** : `mailing.mailing`, `mailing.contact`, `marketing.campaign`, `marketing.trace`

Critère réussite : diff nul count/sum, date max/min ≤ 1 jour.

### Phase 4 — Tests fonctionnels (J-3 à J-1)
Trois niveaux :
1. **Unitaires Odoo** : `odoo --test-enable --test-tags=...`
2. **End-to-end scriptés** via `odoorpc` — parcours complet par module (POS, FSM, Inventaire, Achats, Site-web, Compta, Contacts, Email marketing, Marketing automation)
3. **Manuels navigateur** avec checklist + captures

### Phase 5 — Bascule (jour J)
Window vendredi soir ou dimanche matin. Séquence atomique ≤ 2h :
1. T+0 : maintenance on
2. T+5 : snapshot final (pg_dump + tar filestore hors Odoo.sh)
3. T+15 : upload dump final Upgrade Service
4. T+45 : restore dump v17 sur prod
5. T+55 : push `staging` → `production` Odoo.sh (rebuild + post-migrate)
6. T+75 : fumée (login admin, /shop, /pos, /odoo/inventory)
7. T+90 : réconciliation auto (script Phase 3) — diff ≠ 0 = rollback
8. T+100 : maintenance off + monitoring 24h

### Phase 6 — Rollback
Si KO en < 4h : maintenance on, restore dump v16 T+5, push tag `pre-migration-v16`, maintenance off, post-mortem. Au-delà de 24h, rollback dangereux (perte transactions récentes).

## Outils

- **Odoo Upgrade Service** : https://upgrade.odoo.com
- **Docker v17 local** : `.local/docker-compose.yml` avec Enterprise monté + filestore prod restauré
- **XML-RPC** via `odoorpc` pour diffs et e2e
- **Accès** : ssh `6801067@freemoov.odoo.com` (prod), ssh `29368987@freemoov-staging-29368987.dev.odoo.com` (staging)

## Historique des validations

- **23/01/2026** : audit technique staging v17 concluait "migration prête pour la production" (1971 produits, 8171 commandes, 6035 factures migrés). Voir `archive/AUDIT_MIGRATION_V16_V17.md`.
- **23/01/2026** : analyse des 13 modules dépréciés → aucun développement de remplacement nécessaire. Voir `archive/MIGRATION_MODULES_DEPRECATED.md`.
- **Depuis janvier** : ajout ~53 commits v16 non portés vers staging v17 (GMC, SEO overhaul, checkout refonte). C'est le retard à rattraper.
