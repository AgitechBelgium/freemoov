# Recette : ordre des messages et cartes produits

## Correctifs

- Déclenchement IA après le `message_post` Odoo complet, et non dans
  `mail.message.create` : la notification de la question précède la réponse.
- Les messages et cartes du bot ne reprennent plus le `temporary_id` de la
  question. L'accusé de réception du message optimiste reste réservé au visiteur.
- Les cartes proviennent des liens de la réponse finale, dans leur ordre de
  citation, et uniquement parmi les produits retournés par un outil réussi.
  Aucun produit supplémentaire si le modèle consulte cinq produits mais n'en
  recommande que deux. Déduplication des liens et validation domaine/chemin ;
  une question de clarification sans lien produit n'affiche aucune carte.
- Les protections existantes restent testées : identité du bot, absence de
  récursion, portail, 2FA, reprise des erreurs PostgreSQL et relais humain.

## Validation du 7 septembre 2026

- Six tests nouveaux : six échecs avant correction, six succès après.
- Suite complète staging : **225 tests, zéro échec, zéro erreur**,
  `/tmp/fm-presentation-final.log`, terminée à 21:16:25 UTC.
- Navigateur staging, journal 425 : deux recommandations (Kingsong N15,
  Hikerboy Curtis Plus), exactement deux cartes, après la question et la réponse.
- Journal 426 : fiche Kingsong N15 seule, exactement une carte, dans le bon ordre.
- Ordre des messages et cartes conservé après rechargement de la page.
- Un appel de recherche sans résultat (424) n'a produit aucune carte.
- Aucun changement en production. Correctifs appliqués au build de recette
  `freemoov-staging-36939736` ; ils doivent encore être intégrés à une branche
  de déploiement pour survivre à la reconstruction de ce build.

## Limites relevées pendant cette recette

- Filtre de catégorie « trottinettes » au pluriel : aucun résultat, alors que
  la recherche « trottinette » sans catégorie retourne des produits. Corriger
  la normalisation/résolution des catégories avant l'ouverture générale.
- Mise en forme Markdown encore affichée en texte brut.
- Recettes mobile, identification de bout en bout et relais avec un conseiller
  connecté toujours requises avant production.
