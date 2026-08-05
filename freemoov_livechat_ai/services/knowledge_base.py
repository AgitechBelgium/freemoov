"""The stable half of what the model knows: Freemoov's commercial policies.

Deliberately *only* the policies. Everything that moves — prices, stock,
opening hours, orders, repairs — is read live through the tools, because a
fact copied into the prompt is a fact frozen at prompt-build time and repeated
with the same confidence long after it stopped being true.

Addresses and opening hours appear below as a reminder, not as a source: the
source is `website._STORES` (same data as the store pages and their
LocalBusiness JSON-LD), served to the model by the `infos_magasins` tool.
"""

STATIC_FAQ = """
## Freemoov — politiques commerciales (faits stables, à citer uniquement si certains)

### Paiement
- **3x sans frais** jusqu'à 2.000€ via nos partenaires (Bancontact, VISA, MasterCard, PayPal…). Sans dossier.
- **24x avec financement** via Cetelem pour les montants plus élevés. Dossier avec justificatifs, acceptation soumise aux conditions du partenaire financier.
- Page dédiée : https://www.freemoov.com/payez-par-mois
- Situations CPAS/chômage : le financement 24x n'est pas garanti (c'est Cetelem qui décide). Le 3x sans frais reste toujours accessible.

### Livraison et retour
- Livraison gratuite dès 190€ d'achat.
- Délai standard : 1 à 5 jours ouvrés en Belgique.
- Droit de rétractation : 14 jours à compter de la réception. Les frais de renvoi sont à charge du client.

### Magasins (rappel — horaires et coordonnées à jour : outil `infos_magasins`)
- Liège — Boulevard de la Sauvenière 136B, 4000 Liège
- Namur — Avenue du Bourgmestre Jean Materne 120, 5100 Namur
- Charleroi — Rue de Dampremy 69, 6000 Charleroi
- Horaires des trois magasins : mardi-vendredi 11:00-19:00, samedi 11:00-17:00, dimanche et lundi fermés.
- Téléphone : +32 81 65 91 66
- Prise de rendez-vous possible pour un essai ou un SAV.

### Garantie et SAV
- Garantie 2 ans incluse sur toutes les trottinettes neuves.
- Services premium Freemoov inclus.
- Suivi d'un dossier de réparation déjà ouvert : vérifier l'identité, puis `statut_reparation`.
- Diagnostic technique, pièce défectueuse, prise en charge à organiser : transférer à un conseiller.

### Législation belge (trottinettes électriques)
- Vitesse max autorisée sur voie publique : 25 km/h.
- Âge minimum : 16 ans sur voie publique.
- Casque recommandé, obligatoire pour les moins de 16 ans sur certaines voies.
- Pas de plaque d'immatriculation ni permis pour les modèles limités 25 km/h.
- Les modèles débridés (au-delà de 25 km/h) sont réservés à un usage privé (terrain privé).

### Hors périmètre
- Remboursement, litige, plainte, situation financière personnelle complexe : répondre brièvement, puis transférer à un conseiller humain.
- Si la réponse n'est pas sûre : dire « Je ne suis pas certain, je transfère à un conseiller » plutôt que d'inventer.
"""


def build_knowledge_base(env):
    """The policies, and nothing else.

    The catalogue summary this used to concatenate is gone: it was capped at 40
    products out of the whole shop, ordered by price rather than by relevance,
    frozen at build time (prices *and* stock), and paid for in tokens on every
    single turn including the ones about opening hours. `chercher_produits` and
    `fiche_produit` answer the same questions against the live database.

    `env` is kept in the signature: the callers pass it, and the policies are
    the next thing to make configurable per website.
    """
    return STATIC_FAQ
