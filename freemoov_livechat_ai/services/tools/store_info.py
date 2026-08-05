"""Store hours/addresses. Single source of truth: website_freemoov SEO mapping."""
from . import register


@register(
    "infos_magasins",
    "Horaires, adresse et téléphone des magasins Freemoov (Liège, Namur, Charleroi). "
    "Sans argument : les trois magasins.",
    {
        "type": "object",
        "properties": {"ville": {"type": "string", "description": "liege, namur ou charleroi"}},
    },
)
def infos_magasins(env, channel, ville=None):
    Website = env["website"]
    hours_txt = "mardi-vendredi 11:00-19:00, samedi 11:00-17:00, dimanche-lundi fermé"
    out = []
    for key, s in Website._STORES.items():
        if ville and ville.strip().lower() not in (key, s["locality"].lower()):
            continue
        out.append({
            "ville": s["locality"],
            "adresse": "%s, %s %s" % (s["street"], s["postal_code"], s["locality"]),
            "telephone": Website._STORE_PHONE,
            "horaires": hours_txt,
            "url": s["path"],
        })
    return {"magasins": out}
