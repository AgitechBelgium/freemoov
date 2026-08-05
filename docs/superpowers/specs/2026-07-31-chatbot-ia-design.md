# Spec — Chatbot IA Freemoov (v1)

Date : 2026-07-31
Statut : validé (approche A, périmètre et arbitrages confirmés par Enzo)

## 1. Objectif

Transformer `freemoov_livechat_ai` (appel API simple + FAQ figée) en assistant type
Intercom : réponses fondées sur les données Odoo réelles via tool use, identification
du visiteur en deux facteurs, widget soigné aux couleurs Freemoov, transfert
intelligent vers un conseiller dans Discuss.

La couche d'outils sert aussi de socle à l'agent vocal ElevenLabs (lot 4 du devis) :
mêmes fonctions, exposées en HTTP authentifié.

## 2. Hors périmètre v1

- Prise de rendez-vous atelier (module `appointment` non installé).
- Langues autres que le français.
- Vrai streaming mot à mot (indicateur de frappe à la place — arbitré).
- Affichage de la facture dans le chat (envoi à l'adresse enregistrée uniquement — arbitré).
- Modification de commandes, paiements, remboursements : toujours transférés.

## 3. Architecture (approche A validée)

```
Widget OWL Freemoov ── bus Odoo ── discuss.channel (im_livechat standard)
                                        │ hook mail.message.create (existant)
                                        ▼
                              Boucle IA tool use (anthropic_client)
                                        │
                        services/tools/*.py  (registre d'outils, ORM direct)
                                        │
                        controllers /api/assistant/v1/*  (mêmes fonctions,
                        token serveur→serveur, pour l'agent vocal — non
                        consommé par le widget)
```

Principes :
- Le widget custom pilote une session `im_livechat` standard : canal, historique et
  escalade opérateur dans Discuss restent natifs.
- Chaque outil = un nom, un schéma JSON, un callable Python. Registre unique.
- Le chatbot appelle les callables directement (pas d'aller-retour HTTP).
- Modèle : Haiku 4.5 (configuré), paramétrable. Boucle plafonnée à 6 appels
  d'outils par tour de parole.

## 4. Outils v1

| Outil | Entrées | Sorties | Identité |
|---|---|---|---|
| `infos_magasins` | ville? | horaires, adresse, tél (source : mapping `_STORES` de website_freemoov/models/seo.py) | non |
| `chercher_produits` | budget?, usage?, autonomie_min?, marque?, categorie? | ≤5 produits {nom, prix, dispo par magasin, url, id} | non |
| `fiche_produit` | product_id | specs, prix, stock par magasin, url | non |
| `envoyer_code` | email \| num_commande \| num_reparation | canal d'envoi masqué (« j.***@gmail.com ») | — |
| `verifier_code` | code | vérifié / échec (essais restants) | — |
| `statut_commande` | — (partner du canal vérifié) | commandes récentes : état, transporteur, n° suivi | **oui** |
| `statut_reparation` | — (partner du canal vérifié) | dossiers FSM : état traduit client | **oui** |
| `renvoyer_facture` | commande | confirmation d'envoi à l'adresse enregistrée | **oui** |

`statut_reparation` : livré mais **désactivé par paramètre** tant que l'atelier de
traduction des statuts FSM (lot 2 du devis) n'a pas eu lieu. En attendant : transfert.

## 5. Vérification d'identité (2 facteurs)

Flux : identifiant fourni (e-mail ou n° commande/réparation) → lookup partner →
code 6 chiffres envoyé vers l'e-mail **ou** le téléphone déjà enregistrés dans Odoo
(jamais vers une coordonnée fournie dans le chat) → saisie du code → canal marqué
vérifié.

État porté par un modèle `freemoov.livechat.verification` lié au canal :
`partner_id`, `code_hash` (sha256 + sel), `expires_at` (10 min), `attempts` (max 3),
`verified_at`, `method`.

**Règle de sécurité centrale : l'autorité est côté serveur.** Chaque outil sensible
relit l'état de vérification du canal en base avant de répondre. Le modèle de langage
ne peut pas accorder l'accès — une injection de prompt ne donne rien.

Envoi : e-mail via mail serveur Odoo ; SMS via IAP Odoo (prérequis : crédits sur le
compte — à vérifier). Mode test (`freemoov_livechat_ai.verification_test_mode`) :
code visible dans le journal backend, car les envois sont neutralisés sur staging
Odoo.sh.

## 6. Widget

OWL Odoo 17, conventions du repo (pas de jQuery ajouté, `/** @odoo-module **/`).

- Lanceur flottant + panneau aux couleurs Freemoov.
- Indicateur de frappe pendant la génération (notification bus native im_livechat).
- Cartes produit cliquables : quand un tour a utilisé `chercher_produits` /
  `fiche_produit`, le module poste un second message HTML rendu en QWeb
  (image, nom, prix, dispo, lien) — le widget le style.
- Suggestions au démarrage : « Suivre ma réparation », « Trouver une trottinette »,
  « Horaires et magasins », « Suivre ma commande ».
- Bouton permanent « Parler à un conseiller » → escalade immédiate.

## 7. Prompt système

Réécrit : ton Freemoov conservé, mais la FAQ statique est réduite aux politiques
(livraison, garantie, retours, financement, législation) — le catalogue et les
magasins sortent du prompt puisqu'ils passent par les outils. Corrections au
passage : Charleroi (pas « Bruxelles à confirmer »), retour 14 jours aligné sur
`RETURN_DAYS` du module SEO. Règles inchangées : ne jamais inventer, `[ESCALATE]`,
français.

## 8. Erreurs et garde-fous

Conservés : dry run, rate limit/min, silence si humain actif < 120 s, log complet.
Ajoutés :
- plafond 6 appels d'outils/tour, budget tokens/conversation ;
- outil en échec → le bot le dit et propose le transfert (jamais d'invention) ;
- chaque appel d'outil journalisé (nom, arguments, vérifié o/n, durée) dans le log
  existant ;
- timeout Anthropic → message d'excuse + notification opérateurs.

## 9. Tests

1. **Local** : stack Docker `freemoov-odoo-v17` (port 8069), test dans le vrai
   widget, IA en dry run puis actif.
2. **Régression** : suite de conversations types rejouée par script — les 9 appels
   Ringover transcrits sont les 9 premiers cas (suivi réparation, facture non reçue,
   conseil budget 1 400 €, pièce détachée → transfert attendu, etc.). Vérifie :
   outil appelé attendu, pas de donnée personnelle sans vérification, escalades.
3. **Staging Odoo.sh** : tests par l'équipe Freemoov, mode test 2FA.
4. **Prod restreinte** : périmètre infos pratiques + produits d'abord, puis
   commandes/réparations après validation des logs.

## 10. Prérequis et risques

| Point | Impact | Traitement |
|---|---|---|
| Statuts FSM non structurés | suivi réparation inactif | atelier techniciens (lot 2) ; outil livré désactivé |
| Crédits IAP SMS | 2FA e-mail seul | vérifier le compte ; e-mail suffit au lancement |
| E-mails neutralisés sur staging | 2FA intestable | mode test : code au journal |
| Stock produit peu fiable (58 % rupture) | le bot annonce des dispos fausses | le bot cite la dispo **par magasin** depuis stock.quant, pas le flag site ; mention « à confirmer en magasin » |
| Coût API | dérive | budget/conversation + log coût existant |

## 11. Critères de succès

- Les 9 cas de régression passent (bon outil, bonne donnée, bonne escalade).
- Aucune donnée personnelle servie sans vérification serveur (test d'injection dédié).
- Réponse complète < 8 s en médiane hors outils lents.
- L'équipe peut suivre chaque conversation et son coût dans le journal backend.
