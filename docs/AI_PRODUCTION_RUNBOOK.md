# Déploiement progressif de l'assistant Freemoov

## Situation de départ vérifiée le 7 septembre 2026

- Production : commit `3563c53`, `website_freemoov` installé en `17.0.1.1.6`.
- `freemoov_livechat_ai` absent de la liste des modules en base ; paramètres
  d'activation, clé, dry-run et mode test absents. Aucune mutation de production
  effectuée pendant la recette.
- Staging utilise `6b88480` avec les fichiers du candidat synchronisés. Un
  rebuild peut remplacer ces fichiers et la configuration : la recette SSH
  n'est pas un déploiement durable tant que sa source n'est pas intégrée.

## 1. Candidat isolé

Partir de la pointe **production relue et récupérée à l'instant du déploiement**.
Importer uniquement `freemoov_livechat_ai/` depuis le candidat validé, et ajouter
`Markdown==3.3.6` aux dépendances existantes sans les remplacer. Ne pas fusionner
la branche staging entière : elle comporte notamment des travaux de paiement
sans rapport avec l'assistant.

Revoir le diff de portée, exécuter la compilation et les tests du module,
et conserver l'identifiant du commit exact. Les tests sur une base où le module
est déjà installé ne remplacent pas une recette de **première installation**
du candidat fondé sur production.

## 2. Installer sans ouverture publique

Après résolution des écarts bloquants de `AI_READINESS_2026-09-08.md`, réaliser
une sauvegarde Odoo.sh vérifiée puis le déploiement contrôlé du code. **Le push
Git seul n'installe pas les modèles SQL.** Installer explicitement
`freemoov_livechat_ai` par le mécanisme Odoo.sh/Odoo adapté au build courant.
Ne jamais lancer deux processus de mise à jour simultanés.

Le candidat `17.0.0.1.5` ajoute la colonne
`discuss_channel.freemoov_ai_visitor_partner_id`. Pour un environnement où
le module est déjà installé, effectuer sa mise à jour contrôlée avant de
servir le nouveau code, puis vérifier la colonne et redémarrer les workers.
Un simple redémarrage après push n'est pas une migration de schéma.

Les données initiales imposent `enabled=False`, `dry_run=True`,
`verification_test_mode=False`, `repair_tool_enabled=False`. Relire les valeurs
effectives après installation : `noupdate` préserve une configuration existante.
Vérifier l'état `installed`, la version, les modèles SQL et les vues avant de
redémarrer/servir le widget. Contrôler accueil, boutique, produit, panier et
connexion en lecture, sans créer de paiement de test en production.

## 3. Pilote restreint

- Ajouter la clé en interface sécurisée ; ne jamais la copier dans un ticket,
  script versionné, journal ou commande visible. Ne pas supposer que la clé
  staging doit être réutilisée en production.
- Vérifier les opérateurs du canal, les règles d'affichage et le contact hors
  horaires. Prévoir une règle autorisant un chemin de recette connu et une
  règle de masquage ailleurs, avec leur priorité testée avant activation.
  Conserver les règles préexistantes pour le retour arrière.
- Valider à deux navigateurs : demande, code reçu sur boîte contrôlée, refus
  d'un mauvais code, bon code, accès uniquement au client de recette, reprise
  humaine et silence du bot. Ne pas utiliser le mode test pour la preuve email.
- Relire stocks/prix/horaire de plusieurs réponses et confronter les cartes
  aux données Odoo. Tester déconnexion, session périmée, limite de débit et
  indisponibilité du fournisseur sans exposer des erreurs techniques au visiteur.

## 4. Ouverture générale

Étendre l'affichage uniquement après les preuves du pilote. Réglages attendus :
`enabled=True`, `dry_run=False`, `verification_test_mode=False` ; réparations
toujours désactivées tant que non validées. Conserver des limites de coût/débit
et contrôler erreurs, taux de transfert et latence après ouverture.

## Retour arrière

Premier levier : `freemoov_livechat_ai.enabled=False`, puis rétablissement des
règles livechat précédentes. Vérifier la disparition des réponses IA et le
fonctionnement du site. Ce n'est pas une suppression du module ni de ses données.
Ne pas restaurer une ancienne base au risque de perdre des commandes récentes.
Si retour de code nécessaire, utiliser un commit correctif/revert explicite et
vérifier la compatibilité des vues et du schéma ; pas de reset forcé de production.
