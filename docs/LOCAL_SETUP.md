# Environnement de développement local

## Prérequis

- Docker Desktop (ou OrbStack)
- 15 Go d'espace disque libre
- Accès SSH aux environnements Odoo.sh (pour générer des dumps)

## Structure `.local/`

Tout l'environnement de développement est dans `.local/` (ignoré git) :

```
.local/
├── docker-compose.yml       # Service principal (Odoo 17 + Postgres 15)
├── config/
│   └── odoo.conf            # Config Odoo active
├── enterprise/              # Code Odoo Enterprise 17.0 extrait
│   └── odoo/addons/         # 1243 modules (core + Enterprise)
├── filestore/               # Backup du filestore prod v16 (6.7 Go)
├── dumps/                   # Dumps SQL (à générer via SSH)
├── scripts/                 # Scripts sync prod/staging, COW, etc.
├── backups-wip/             # Versions historiques WIP checkout
└── .env                     # Secrets (licence, mots de passe) — à créer
```

## Premier démarrage

### 1. Créer `.local/.env`

```bash
cat > .local/.env <<'EOF'
POSTGRES_PASSWORD=odoo
ODOO_ADMIN_PASS=admin
# Licence Enterprise (ne jamais committer)
ODOO_ENTERPRISE_LICENSE=M22121463936514
EOF
chmod 600 .local/.env
```

### 2. Démarrer les conteneurs

```bash
cd .local
docker compose up -d
docker compose logs -f odoo
```

Odoo devrait être accessible sur **http://localhost:8069** après ~30s.

### 3. Initialiser la base

Deux options :

#### Option A — Base vide (dev rapide)

```bash
# L'interface /web/database/manager permet de créer une base fresh
# ou via CLI :
docker compose exec odoo odoo -d freemoov_dev -i base,website,website_sale \
  --without-demo=all --stop-after-init
```

#### Option B — Restore d'un dump prod migré v17

```bash
# 1. Générer un dump prod via SSH (si pas déjà fait)
ssh 6801067@freemoov.odoo.com "pg_dump -Fc agitechbelgium-freemoov-production-6801067" \
  > .local/dumps/prod-v16-$(date +%Y%m%d).pgdump

# 2. Upload sur upgrade.odoo.com en mode TEST (voir https://upgrade.odoo.com)
#    → Retour dump v17 par email (24-72h)

# 3. Restore du dump v17 retourné
docker compose exec -T db psql -U odoo -c "CREATE DATABASE freemoov_v17 OWNER odoo;"
docker compose exec -T db pg_restore -U odoo -d freemoov_v17 < dump_v17.pgdump

# 4. Relier au filestore restauré
# Le volume `.local/filestore/` contient déjà le filestore v16
```

## Commandes utiles

```bash
# Démarrer
cd .local && docker compose up -d

# Logs Odoo
docker compose logs -f odoo

# Installer/mettre à jour un module
docker compose exec odoo odoo -d freemoov_dev -u website_freemoov --stop-after-init

# Shell Odoo (Python interactif avec env)
docker compose exec odoo odoo shell -d freemoov_dev

# Tests d'un module
docker compose exec odoo odoo -d test_db -i website_freemoov \
  --test-enable --test-tags=website_freemoov --stop-after-init

# Arrêter + nettoyer
docker compose down            # arrête, garde volumes
docker compose down -v         # arrête + supprime volumes (réinit DB)

# Rebuild après changement docker-compose
docker compose up -d --build
```

## Configuration `dev_mode`

Le docker-compose lance Odoo avec `--dev=all`. Cela active :
- **reload** : auto-reload Python (changement .py → redémarre workers)
- **qweb** : auto-reload templates QWeb
- **xml** : auto-reload vues XML (pas besoin de `-u` après modification)
- **werkzeug** : stack traces détaillées
- **assets** : recompile assets à chaque requête (SCSS, JS)

Équivalent à 80% du workflow Odoo.sh.

## Débogage

### Odoo ne démarre pas
```bash
docker compose logs odoo | tail -50
# Souvent : addons_path incorrect, db_host inaccessible, port 8069 occupé
```

### Enterprise modules manquants
Vérifier que `.local/enterprise/odoo/addons` est bien monté :
```bash
docker compose exec odoo ls /mnt/enterprise-addons | head
# Doit lister : account, account_accountant, account_3way_match, ...
```

### Modifications non prises en compte
Avec `--dev=all` :
- `.py` → attendre 2-3s après sauvegarde
- `.xml` → rafraîchir page navigateur (pas de restart)
- `.scss`/`.js` → rafraîchir avec **Ctrl+F5** (vider cache)

Si rien ne marche : `docker compose restart odoo`.

## Dumps & filestores

**Dump prod v16 frais** :
```bash
ssh 6801067@freemoov.odoo.com "pg_dump -Fc -Z9 -d agitechbelgium-freemoov-production-6801067" \
  > .local/dumps/prod-$(date +%Y%m%d).pgdump
```

**Dump staging actuel (Odoo.sh)** :
```bash
ssh 29368987@freemoov-staging-29368987.dev.odoo.com "pg_dump -Fc -Z9 -d freemoov-staging-29368987" \
  > .local/dumps/staging-$(date +%Y%m%d).pgdump
```

**Sync filestore prod** :
```bash
rsync -avz 6801067@freemoov.odoo.com:filestore/ .local/filestore/
```

## Sécurité

- **Ne jamais committer** la licence Enterprise ni `.local/.env`
- Les dumps contiennent des données réelles clients → traitement RGPD
- Odoo local écoute sur `localhost:8069` uniquement (pas exposé réseau par défaut)
