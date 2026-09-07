# Assistant IA — recette du 8 septembre 2026

État : version `17.0.0.1.3` installée et testée sur
`freemoov-staging-36939736`. **Pas d'ouverture en production.**
Les comptes rendus du 7 septembre décrivent des étapes antérieures.

## Correctifs validés

- Recherche : pluriels usuels, accents, ordre des mots et catégories parentes.
  Les références telles que N15S ne sont pas tronquées. Budget, publication et
  disponibilité à la vente restent filtrés par le serveur.
- Réponses Markdown rendues : liens, listes, emphase et retours à la ligne.
  HTML non fiable échappé, attributs nettoyés, liens dangereux et images issues
  du texte du modèle supprimés. Les cartes QWeb conservent leurs images.
- Historique : liens conservés, cartes techniques exclues du contexte envoyé
  au modèle pour éviter la répétition de leurs libellés.
- Code email : validation déterministe du code unique saisi dans le message
  courant lorsqu'une vérification est en attente. Le modèle ne décide plus
  s'il faut appeler le vérificateur. Tentatives, expiration et contrôle d'accès
  utilisent toujours le même outil serveur. Un ancien code de l'historique
  fusionné n'est pas rejoué ; dry-run ne consomme aucune tentative.
- Disponibilité : résumé explicite par produit, séparant commande en ligne et
  stock de chaque magasin. Le prompt interdit de transférer le stock d'un
  produit vers un autre ; les chiffres restent fournis par Odoo.
- Mobile : le plein écran ne s'applique plus à la fenêtre réduite.

## Preuves

- Dernière suite complète : **240 tests, zéro échec, zéro erreur**.
  Journal staging `/tmp/fm-readiness-release-013.log`, fin le
  7 septembre 2026 à 22:01:35 UTC (8 septembre à 00:01 heure de Paris).
  Inclut compilation des assets. Version installée relue : `17.0.0.1.3`.
- Les régressions recherche/formatage/identification ont été observées en
  échec avant leur correctif puis sont passées après.
- `probe_ai_catalog.py` : trois appels au modèle réel. F2 PLUS E correctement
  annoncée non commandable et sans stock ; deux autres demandes ont proposé
  exactement Kingsong N15 et Hikerboy Curtis Plus, sous 600 €, avec stock.
  Les contrôles automatisés portent sur budget, cartes et possibilité d'achat ;
  la formulation et la concordance des stocks ont été lues manuellement.
  Ce résultat ne garantit pas toutes les futures réponses du modèle.
- `probe_ai_identity_handoff.py` : modèle réel + ORM réel ; refus avant
  identification, mauvais code consommant un essai, bon code puis commande
  du seul client vérifié, refus inter-client/inter-conversation, expiration,
  deux réponses à un compte portail sans contournement de l'identification,
  relais hors ligne puis affectation réelle au sélecteur Odoo avec un
  opérateur synthétique connecté. L'IA reste silencieuse après reprise humaine.
- Ces deux sondes annulent leurs transactions. Aucun destinataire réel : seul
  le transport du code email est intercepté en mémoire pour le client
  synthétique. La livraison d'un email n'est donc **pas** validée par ce test.
  La présence opérateur est créée côté serveur, pas par un second navigateur.
- Navigateur à **320 × 667** : question puis réponse puis exactement deux
  cartes ; Markdown rendu ; largeurs internes égales aux largeurs défilables
  (pas de débordement horizontal), saisie visible jusqu'à y=656.
- Réduction : échec observé à 320 × 667, puis bulle **48 × 48** après correction.
  Rechargement et réouverture : conversation et deux cartes conservées,
  fenêtre ouverte à 320 × 667. Viewport rétabli ensuite à 1280 × 720.

## Écarts encore ouverts avant diffusion générale

1. Une ancienne session de recette a provoqué `/mail/init_messaging` 404 :
   Odoo ne retrouvait pas de visiteur authentifié, alors que le navigateur
   tentait de restaurer le chat. Fermer la conversation puis recharger a
   débloqué le navigateur. Une conversation neuve survit au rechargement.
   **Cause de la perte d'identification et récupération automatique à traiter** ;
   ne pas présenter cet incident comme corrigé par le seul nettoyage manuel.
2. Tester la réception d'un vrai code sur une boîte détenue par l'équipe,
   puis le passage visiteur → opérateur dans deux navigateurs. Aucun email
   ne doit partir vers un client pendant cette recette.
3. Vérifier un téléphone réel avec clavier ouvert. Le viewport navigateur
   couvre la mise en page, pas le clavier virtuel iOS/Android.
4. Les arguments des outils sont masqués dans l'audit. Les messages de chat et
   les champs texte du journal ne constituent pas un stockage anonymisé :
   rétention, habilitations et minimisation des codes restent à vérifier.
5. Des erreurs du site hôte (`gtag` non défini et `querySelector` sur null)
   subsistent dans sa console. Elles ne proviennent pas du bundle du chatbot
   identifié dans cette recette ; pas de promesse de console globalement vide.
6. Pas de test de charge réel. Éprouver le comportement des limites API et
   l'attente sous trafic avant un déploiement sans restriction. Le suivi
   réparation reste désactivé tant que ses étapes métier ne sont pas validées.

## Rejouer les sondes (staging uniquement)

Depuis la racine du dépôt :

```sh
ssh 36939736@freemoov-staging-36939736.dev.odoo.com \
  'odoo-bin shell --no-http --max-cron-threads=0 --logfile=/tmp/fm-catalog-probe.log' \
  < docs/probe_ai_catalog.py
ssh 36939736@freemoov-staging-36939736.dev.odoo.com \
  'odoo-bin shell --no-http --max-cron-threads=0 --logfile=/tmp/fm-identity-probe.log' \
  < docs/probe_ai_identity_handoff.py
```

Les assertions de base et de configuration doivent rester en place. Ces sondes
utilisent l'API Anthropic configurée et consomment des tokens. Ne pas les
exécuter pendant une mise à jour de module.
