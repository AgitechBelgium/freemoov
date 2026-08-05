"""Identity verification flow (2FA) exposed to the model.

The two tools here are the only way into the sensitive half of the toolbox.
They never take the model's word for anything: the authorisation is read from
the database by `run_tool`, and the send quota below is read from the
verification records themselves.
"""
from . import ToolError, register

# Three codes per channel per hour. Two problems, one cap:
#   * `_start_verification` hands out a fresh 3-attempt budget on every send,
#     so an uncapped resend turns the lockout into a formality;
#   * every send is a real e-mail or SMS to a real customer, so an uncapped
#     resend is a mail-bombing button with no login behind it.
MAX_SENDS_PER_HOUR = 3
SEND_WINDOW_MIN = 60

TOO_MANY_SENDS_MSG = (
    "Nous avons déjà envoyé trop de codes de vérification pour cette "
    "conversation. Merci de réessayer dans une heure, ou propose un transfert "
    "vers un conseiller."
)

# Reminder carried by every tool that requires an identity: the verification
# expires after 30 minutes (VERIFIED_TTL_MIN), and `run_tool` refuses before
# the tool runs, so only the model can explain the refusal to the visitor.
VERIFICATION_HINT = (
    "Si l'outil est refusé avec 'verification_required', c'est que le visiteur "
    "n'est pas (ou n'est plus) vérifié : la vérification expire au bout de 30 "
    "minutes. Relance envoyer_code puis verifier_code, en expliquant que la "
    "session de vérification a expiré."
)


@register(
    "envoyer_code",
    "Démarre la vérification d'identité : envoie un code à 6 chiffres vers l'e-mail ou "
    "le téléphone ENREGISTRÉS chez Freemoov pour ce client. L'identifiant peut être un "
    "e-mail, une référence de commande (ex. S00123) ou de réparation. Toujours demander "
    "l'identifiant AVANT d'appeler cet outil. Maximum 3 envois par conversation et par "
    "heure : ne pas relancer l'outil en boucle.",
    {
        "type": "object",
        "properties": {"identifiant": {"type": "string"}},
        "required": ["identifiant"],
    },
)
def envoyer_code(env, channel, identifiant):
    Verification = env["freemoov.livechat.verification"].sudo()
    if Verification._sends_since(channel, SEND_WINDOW_MIN) >= MAX_SENDS_PER_HOUR:
        raise ToolError(TOO_MANY_SENDS_MSG)
    res = Verification._start_verification(channel, identifiant)
    return {"envoye_vers": res["target_masked"], "canal": res["method"],
            "consigne": "Demande au visiteur de saisir le code reçu."}


@register(
    "verifier_code",
    "Vérifie le code à 6 chiffres saisi par le visiteur. 3 essais maximum. "
    "La vérification obtenue vaut 30 minutes.",
    {
        "type": "object",
        "properties": {"code": {"type": "string"}},
        "required": ["code"],
    },
)
def verifier_code(env, channel, code):
    res = env["freemoov.livechat.verification"].sudo()._check_code(channel, code)
    return {"verifie": res["verified"], "essais_restants": res["attempts_left"]}
