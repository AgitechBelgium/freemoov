# Chatbot IA Freemoov — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformer `freemoov_livechat_ai` en assistant à outils (tool use) : réponses fondées sur les données Odoo, vérification d'identité 2 facteurs, cartes produit, socle HTTP pour l'agent vocal.

**Architecture:** Registre d'outils Python (`services/tools/`) consommé par une boucle agentique (`services/agent_loop.py`) branchée sur le hook `mail.message.create` existant. Autorité de sécurité côté serveur (`run_tool` vérifie l'état 2FA du canal, jamais le LLM). Widget = im_livechat natif restylé + patches OWL.

**Tech Stack:** Odoo 17 (Python 3.10, OWL, QWeb), API Anthropic Messages (HTTP direct via `requests`, pas de SDK), Haiku 4.5.

**Spec:** `docs/superpowers/specs/2026-07-31-chatbot-ia-design.md`

## Global Constraints

- Env de test : `docker exec freemoov-odoo-v17 odoo -d freemoov_v17 -u freemoov_livechat_ai --test-tags=freemoov_ai --stop-after-init --no-http` (containers `freemoov-odoo-v17` + `freemoov-db-v17` démarrés).
- Tests : `odoo.tests.TransactionCase`, tag `@tagged("post_install", "-at_install", "freemoov_ai")`. Jamais d'appel réseau réel dans les tests — `unittest.mock.patch` sur `AnthropicClient.create_message`.
- JS : `/** @odoo-module **/` en tête, pas de jQuery, pas d'import `jsonrpc`/`@web/core/network/rpc` (convention CLAUDE.md du repo).
- Textes visibles utilisateur : français. Code, identifiants, commits : anglais.
- Commits : `type(scope): description`, titre en anglais, pas d'emoji, aucune mention d'IA/génération. **Ne pas pousser.**
- Ne pas modifier les dépendances Python (`requirements.txt`) — `requests` suffit.
- La donnée sensible ne sort JAMAIS d'un outil si `run_tool` ne confirme pas la vérification du canal en base.
- Modèle par défaut : `claude-haiku-4-5-20251001` (param existant `freemoov_livechat_ai.model`).

---

### Task 1: Test scaffolding + tool registry

**Files:**
- Create: `freemoov_livechat_ai/services/tools/__init__.py`
- Create: `freemoov_livechat_ai/tests/__init__.py`
- Create: `freemoov_livechat_ai/tests/common.py`
- Test: `freemoov_livechat_ai/tests/test_tools_registry.py`

**Interfaces:**
- Produces: `tools.register(name, description, input_schema, requires_verification=False)` (décorateur), `tools.TOOLS` (dict), `tools.ToolError(Exception)`, `tools.anthropic_tool_specs() -> list[dict]`, `tools.run_tool(env, channel, name, arguments) -> dict`.
- `run_tool` : outil inconnu → `ToolError("Outil inconnu")` ; outil `requires_verification` sur canal non vérifié → `ToolError("verification_required")` ; le callable reçoit `(env, channel, **arguments)`.
- La vérification du canal est lue via `channel._freemoov_ai_verified_partner()` (implémenté Task 3 ; d'ici là `run_tool` utilise `getattr(channel, "_freemoov_ai_verified_partner", lambda: False)()`).

- [ ] **Step 1: Write the failing test**

```python
# freemoov_livechat_ai/tests/__init__.py
from . import test_tools_registry
```

```python
# freemoov_livechat_ai/tests/common.py
from odoo.tests import TransactionCase


class FreemoovAiCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env["discuss.channel"].create({
            "name": "Test visiteur",
            "channel_type": "livechat",
            "livechat_operator_id": cls.env.ref("base.partner_admin").id,
        })
```

```python
# freemoov_livechat_ai/tests/test_tools_registry.py
from odoo.tests import tagged

from ..services import tools
from .common import FreemoovAiCase


@tagged("post_install", "-at_install", "freemoov_ai")
class TestToolsRegistry(FreemoovAiCase):
    def test_register_and_specs(self):
        @tools.register("t_echo", "Echo test", {
            "type": "object",
            "properties": {"txt": {"type": "string"}},
            "required": ["txt"],
        })
        def t_echo(env, channel, txt):
            return {"echo": txt}

        self.addCleanup(tools.TOOLS.pop, "t_echo", None)
        specs = tools.anthropic_tool_specs()
        spec = next(s for s in specs if s["name"] == "t_echo")
        self.assertEqual(set(spec), {"name", "description", "input_schema"})

    def test_run_tool_ok_and_unknown(self):
        @tools.register("t_add", "Add", {"type": "object", "properties": {}})
        def t_add(env, channel):
            return {"ok": True}

        self.addCleanup(tools.TOOLS.pop, "t_add", None)
        self.assertEqual(tools.run_tool(self.env, self.channel, "t_add", {}), {"ok": True})
        with self.assertRaises(tools.ToolError):
            tools.run_tool(self.env, self.channel, "nope", {})

    def test_sensitive_tool_blocked_without_verification(self):
        @tools.register("t_secret", "Secret", {"type": "object", "properties": {}},
                        requires_verification=True)
        def t_secret(env, channel):
            return {"secret": 42}

        self.addCleanup(tools.TOOLS.pop, "t_secret", None)
        with self.assertRaisesRegex(tools.ToolError, "verification_required"):
            tools.run_tool(self.env, self.channel, "t_secret", {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec freemoov-odoo-v17 odoo -d freemoov_v17 -u freemoov_livechat_ai --test-tags=freemoov_ai --stop-after-init --no-http 2>&1 | grep -E "FAIL|ERROR|freemoov_ai" | head -20`
Expected: ERROR (import `..services.tools` inexistant)

- [ ] **Step 3: Write minimal implementation**

```python
# freemoov_livechat_ai/services/tools/__init__.py
"""Tool registry for the AI assistant.

Security invariant: authorization lives HERE, server-side. A tool flagged
`requires_verification` never runs unless the channel's verification state,
read from the database, confirms an identified partner. The LLM has no say.
"""
import logging

_logger = logging.getLogger(__name__)

TOOLS = {}


class ToolError(Exception):
    """Raised by tools; the message is safe to relay to the model."""


def register(name, description, input_schema, requires_verification=False):
    def decorator(fn):
        TOOLS[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "requires_verification": requires_verification,
            "fn": fn,
        }
        return fn
    return decorator


def anthropic_tool_specs():
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
        for t in TOOLS.values()
    ]


def run_tool(env, channel, name, arguments):
    tool = TOOLS.get(name)
    if not tool:
        raise ToolError("Outil inconnu : %s" % name)
    if tool["requires_verification"]:
        verified = getattr(channel, "_freemoov_ai_verified_partner", lambda: False)()
        if not verified:
            raise ToolError("verification_required")
    return tool["fn"](env, channel, **(arguments or {}))
```

Ajouter l'import dans `freemoov_livechat_ai/services/__init__.py` :

```python
from . import tools
```

Et dans `freemoov_livechat_ai/__manifest__.py`, aucun changement pour cette task (les tests sont découverts via `tests/__init__.py`).

- [ ] **Step 4: Run test to verify it passes**

Run: même commande que Step 2
Expected: `0 failed, 0 error(s)` sur les 3 tests

- [ ] **Step 5: Commit**

```bash
git add freemoov_livechat_ai/services/tools/__init__.py freemoov_livechat_ai/services/__init__.py freemoov_livechat_ai/tests/
git commit -m "feat(livechat_ai): add tool registry with server-side verification gate"
```

---

### Task 2: Public tools — stores & catalog

**Files:**
- Create: `freemoov_livechat_ai/services/tools/store_info.py`
- Create: `freemoov_livechat_ai/services/tools/catalog.py`
- Modify: `freemoov_livechat_ai/services/tools/__init__.py` (imports en fin de fichier)
- Modify: `freemoov_livechat_ai/__manifest__.py` (depends + `website_freemoov`, `project`)
- Test: `freemoov_livechat_ai/tests/test_tools_public.py`

**Interfaces:**
- Consumes: `tools.register`, `website._STORES` / `_STORE_HOURS` / `_STORE_PHONE` (définis dans `website_freemoov/models/seo.py`, classe `WebsiteSeo`).
- Produces: outils `infos_magasins(ville?)`, `chercher_produits(recherche?, budget_max?, marque?, categorie?)`, `fiche_produit(product_id)`. `chercher_produits` retourne `{"produits": [{"id", "nom", "prix_tvac", "url", "marque", "dispo": {"Namur": 2, ...}}], "note": str}` (≤5). `fiche_produit` retourne `{"id","nom","prix_tvac","url","description","dispo",...}`.

- [ ] **Step 1: Write the failing test**

```python
# freemoov_livechat_ai/tests/test_tools_public.py
from odoo.tests import tagged

from ..services import tools
from .common import FreemoovAiCase


@tagged("post_install", "-at_install", "freemoov_ai")
class TestPublicTools(FreemoovAiCase):
    def test_infos_magasins_all_and_filtered(self):
        res = tools.run_tool(self.env, self.channel, "infos_magasins", {})
        self.assertEqual(len(res["magasins"]), 3)
        villes = {m["ville"] for m in res["magasins"]}
        self.assertEqual(villes, {"Liège", "Namur", "Charleroi"})
        res = tools.run_tool(self.env, self.channel, "infos_magasins", {"ville": "charleroi"})
        self.assertEqual(len(res["magasins"]), 1)
        self.assertIn("Dampremy", res["magasins"][0]["adresse"])

    def test_chercher_produits_budget(self):
        self.env["product.template"].create({
            "name": "Trott Test AI",
            "list_price": 500.0,
            "is_published": True,
            "sale_ok": True,
        })
        res = tools.run_tool(self.env, self.channel, "chercher_produits",
                             {"recherche": "Trott Test", "budget_max": 600})
        self.assertTrue(any(p["nom"] == "Trott Test AI" for p in res["produits"]))
        res2 = tools.run_tool(self.env, self.channel, "chercher_produits",
                              {"recherche": "Trott Test", "budget_max": 100})
        self.assertFalse(res2["produits"])

    def test_fiche_produit_unpublished_hidden(self):
        tmpl = self.env["product.template"].create({
            "name": "Cache AI", "list_price": 10.0, "is_published": False,
        })
        with self.assertRaises(tools.ToolError):
            tools.run_tool(self.env, self.channel, "fiche_produit", {"product_id": tmpl.id})
```

- [ ] **Step 2: Run test to verify it fails**

Run: commande de test globale (cf. Global Constraints)
Expected: FAIL — outils non enregistrés (`ToolError: Outil inconnu`)

- [ ] **Step 3: Write the implementation**

```python
# freemoov_livechat_ai/services/tools/store_info.py
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
```

```python
# freemoov_livechat_ai/services/tools/catalog.py
"""Product search & detail. Availability read from stock per warehouse,
never from the website publication flag (known to be stale)."""
from . import ToolError, register

_SEARCH_LIMIT = 5
_DISPO_NOTE = "Stock indicatif — à confirmer en magasin."


def _brand(tmpl):
    if "x_studio_marque" in tmpl._fields and tmpl.x_studio_marque:
        return str(tmpl.x_studio_marque)
    return ""


def _dispo_by_store(env, tmpl):
    variant = tmpl.product_variant_ids[:1]
    if not variant:
        return {}
    dispo = {}
    for wh in env["stock.warehouse"].sudo().search([]):
        qty = variant.sudo().with_context(warehouse=wh.id).free_qty
        dispo[wh.name] = int(qty)
    return dispo


def _serialize(env, tmpl, with_description=False):
    data = {
        "id": tmpl.id,
        "nom": tmpl.name,
        "prix_tvac": round(tmpl.list_price, 2),
        "marque": _brand(tmpl),
        "url": "https://www.freemoov.com%s" % (tmpl.website_url or ""),
        "dispo": _dispo_by_store(env, tmpl),
    }
    if with_description:
        data["description"] = (tmpl.description_sale or tmpl.name)[:500]
    return data


@register(
    "chercher_produits",
    "Recherche dans le catalogue Freemoov (trottinettes, vélos, gyroroues, pièces, "
    "accessoires) par texte libre, budget maximum, marque ou catégorie. "
    "Retourne au plus 5 produits avec prix TVAC et stock par magasin.",
    {
        "type": "object",
        "properties": {
            "recherche": {"type": "string"},
            "budget_max": {"type": "number"},
            "marque": {"type": "string"},
            "categorie": {"type": "string"},
        },
    },
)
def chercher_produits(env, channel, recherche=None, budget_max=None, marque=None, categorie=None):
    domain = [("is_published", "=", True), ("active", "=", True), ("sale_ok", "=", True)]
    if recherche:
        domain.append(("name", "ilike", recherche))
    if budget_max:
        domain.append(("list_price", "<=", budget_max))
    if categorie:
        domain.append(("public_categ_ids.name", "ilike", categorie))
    tmpls = env["product.template"].sudo().search(domain, limit=40, order="list_price desc")
    if marque:
        tmpls = tmpls.filtered(lambda t: marque.lower() in _brand(t).lower())
    tmpls = tmpls[:_SEARCH_LIMIT]
    return {"produits": [_serialize(env, t) for t in tmpls], "note": _DISPO_NOTE}


@register(
    "fiche_produit",
    "Détail d'un produit (id retourné par chercher_produits) : description, prix, "
    "stock par magasin, lien.",
    {
        "type": "object",
        "properties": {"product_id": {"type": "integer"}},
        "required": ["product_id"],
    },
)
def fiche_produit(env, channel, product_id):
    tmpl = env["product.template"].sudo().browse(int(product_id))
    if not tmpl.exists() or not tmpl.is_published or not tmpl.active:
        raise ToolError("Produit introuvable ou non publié.")
    data = _serialize(env, tmpl, with_description=True)
    data["note"] = _DISPO_NOTE
    return data
```

Fin de `freemoov_livechat_ai/services/tools/__init__.py`, après les définitions :

```python
# Import tool modules so they self-register (order matters: after registry defs).
from . import store_info  # noqa: E402,F401
from . import catalog  # noqa: E402,F401
```

`__manifest__.py` — depends :

```python
    'depends': ['im_livechat', 'product', 'website_sale', 'website_freemoov', 'project'],
```

- [ ] **Step 4: Run test to verify it passes**

Run: commande de test globale
Expected: PASS (6 tests au total)

- [ ] **Step 5: Commit**

```bash
git add freemoov_livechat_ai/services/tools/ freemoov_livechat_ai/__manifest__.py freemoov_livechat_ai/tests/test_tools_public.py freemoov_livechat_ai/tests/__init__.py
git commit -m "feat(livechat_ai): add store info and catalog tools with per-warehouse stock"
```

(Ne pas oublier d'ajouter `from . import test_tools_public` dans `tests/__init__.py` — idem pour chaque task suivante.)

---

### Task 3: Verification model (2FA)

**Files:**
- Create: `freemoov_livechat_ai/models/verification.py`
- Modify: `freemoov_livechat_ai/models/__init__.py`
- Modify: `freemoov_livechat_ai/security/ir.model.access.csv`
- Modify: `freemoov_livechat_ai/data/ir_config_parameter_data.xml` (param `verification_test_mode`)
- Test: `freemoov_livechat_ai/tests/test_verification.py`

**Interfaces:**
- Produces: modèle `freemoov.livechat.verification` avec `start_verification(channel, identifier) -> {"target_masked": str, "method": "email"|"sms"}` et `check_code(channel, code) -> {"verified": bool, "attempts_left": int}`. Sur `discuss.channel` : `_freemoov_ai_verified_partner() -> res.partner | False` (consommé par `run_tool` depuis Task 1).
- Identifier accepté : e-mail, référence `sale.order` (`name`), ou référence `project.task` FSM. Le code part vers l'e-mail/téléphone **du partner en base**, jamais vers une coordonnée du chat.
- Code : 6 chiffres, `sha256(code + str(channel.id))`, expiration 10 min, 3 essais.

- [ ] **Step 1: Write the failing test**

```python
# freemoov_livechat_ai/tests/test_verification.py
from unittest.mock import patch

from odoo.tests import tagged

from .common import FreemoovAiCase


@tagged("post_install", "-at_install", "freemoov_ai")
class TestVerification(FreemoovAiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Client Test", "email": "client@test.be", "phone": "+32470000000",
        })
        cls.Verif = cls.env["freemoov.livechat.verification"]

    def _start(self):
        with patch.object(type(self.Verif), "_send_code") as send:
            res = self.Verif.start_verification(self.channel, "client@test.be")
            code = send.call_args.args[2]  # (partner, method, code)
        return res, code

    def test_start_masks_target_and_sends(self):
        res, code = self._start()
        self.assertEqual(res["method"], "email")
        self.assertNotIn("client@test.be", res["target_masked"])
        self.assertIn("***", res["target_masked"])
        self.assertEqual(len(code), 6)

    def test_good_code_verifies_channel(self):
        _, code = self._start()
        res = self.Verif.check_code(self.channel, code)
        self.assertTrue(res["verified"])
        self.assertEqual(self.channel._freemoov_ai_verified_partner(), self.partner)

    def test_three_bad_codes_lock(self):
        self._start()
        for _ in range(3):
            res = self.Verif.check_code(self.channel, "000000")
        self.assertFalse(res["verified"])
        self.assertEqual(res["attempts_left"], 0)
        # même le bon code est refusé après verrouillage
        self.assertFalse(self.channel._freemoov_ai_verified_partner())

    def test_unknown_identifier(self):
        from ..services.tools import ToolError
        with self.assertRaises(ToolError):
            self.Verif.start_verification(self.channel, "inconnu@nulpart.be")
```

- [ ] **Step 2: Run test to verify it fails**

Run: commande de test globale
Expected: ERROR — modèle `freemoov.livechat.verification` inexistant

- [ ] **Step 3: Write the implementation**

```python
# freemoov_livechat_ai/models/verification.py
import hashlib
import logging
import secrets
from datetime import timedelta

from odoo import fields, models

from ..services.tools import ToolError

_logger = logging.getLogger(__name__)

CODE_TTL_MIN = 10
MAX_ATTEMPTS = 3


class LivechatVerification(models.Model):
    _name = "freemoov.livechat.verification"
    _description = "Vérification d'identité livechat (2FA)"
    _order = "id desc"

    channel_id = fields.Many2one("discuss.channel", required=True, index=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", required=True)
    code_hash = fields.Char(required=True)
    method = fields.Selection([("email", "E-mail"), ("sms", "SMS")], required=True)
    expires_at = fields.Datetime(required=True)
    attempts = fields.Integer(default=0)
    verified_at = fields.Datetime()

    # -- lookup -----------------------------------------------------------
    def _find_partner(self, identifier):
        ident = (identifier or "").strip()
        if not ident:
            return self.env["res.partner"]
        if "@" in ident:
            return self.env["res.partner"].sudo().search([("email", "=ilike", ident)], limit=1)
        order = self.env["sale.order"].sudo().search([("name", "=ilike", ident)], limit=1)
        if order:
            return order.partner_id
        task = self.env["project.task"].sudo().search([("name", "ilike", ident)], limit=1)
        return task.partner_id if task else self.env["res.partner"]

    @staticmethod
    def _mask(value):
        if "@" in (value or ""):
            local, _, dom = value.partition("@")
            return "%s***@%s" % (local[:1], dom)
        return "***%s" % (value or "")[-4:]

    def _hash(self, code, channel):
        return hashlib.sha256((code + str(channel.id)).encode()).hexdigest()

    # -- API --------------------------------------------------------------
    def start_verification(self, channel, identifier):
        partner = self._find_partner(identifier)
        if not partner or not (partner.email or partner.phone):
            raise ToolError(
                "Je ne retrouve pas ce client. Vérifie l'e-mail ou la référence, "
                "ou propose un transfert vers un conseiller."
            )
        method = "email" if partner.email else "sms"
        code = "%06d" % secrets.randbelow(1_000_000)
        self.sudo().search([("channel_id", "=", channel.id), ("verified_at", "=", False)]).unlink()
        self.sudo().create({
            "channel_id": channel.id,
            "partner_id": partner.id,
            "code_hash": self._hash(code, channel),
            "method": method,
            "expires_at": fields.Datetime.now() + timedelta(minutes=CODE_TTL_MIN),
        })
        self._send_code(partner, method, code)
        target = partner.email if method == "email" else partner.phone
        return {"target_masked": self._mask(target), "method": method}

    def check_code(self, channel, code):
        rec = self.sudo().search([
            ("channel_id", "=", channel.id), ("verified_at", "=", False),
        ], limit=1)
        if not rec or rec.expires_at < fields.Datetime.now() or rec.attempts >= MAX_ATTEMPTS:
            return {"verified": False, "attempts_left": 0}
        if rec.code_hash != self._hash((code or "").strip(), channel):
            rec.attempts += 1
            return {"verified": False, "attempts_left": MAX_ATTEMPTS - rec.attempts}
        rec.verified_at = fields.Datetime.now()
        return {"verified": True, "attempts_left": MAX_ATTEMPTS - rec.attempts}

    # -- envoi ------------------------------------------------------------
    def _send_code(self, partner, method, code):
        ICP = self.env["ir.config_parameter"].sudo()
        if ICP.get_param("freemoov_livechat_ai.verification_test_mode") == "True":
            _logger.warning("freemoov_ai 2FA TEST MODE — code pour %s : %s", partner.name, code)
            return
        if method == "email":
            self.env["mail.mail"].sudo().create({
                "email_to": partner.email,
                "subject": "Votre code de vérification Freemoov",
                "body_html": "<p>Votre code de vérification : <b>%s</b> "
                             "(valable %s minutes).</p>" % (code, CODE_TTL_MIN),
            }).send()
        else:
            self.env["sms.sms"].sudo().create({
                "partner_id": partner.id,
                "number": partner.phone,
                "body": "Freemoov — code de vérification : %s" % code,
            }).send()


class DiscussChannelVerification(models.Model):
    _inherit = "discuss.channel"

    def _freemoov_ai_verified_partner(self):
        """Server-side authority consumed by tools.run_tool. DB read, no cache."""
        self.ensure_one()
        rec = self.env["freemoov.livechat.verification"].sudo().search([
            ("channel_id", "=", self.id), ("verified_at", "!=", False),
        ], limit=1, order="verified_at desc")
        return rec.partner_id if rec else False
```

`models/__init__.py` : ajouter `from . import verification`.

`security/ir.model.access.csv` : ajouter la ligne (accès techniciens back-office uniquement, les visiteurs passent par les outils en sudo) :

```csv
access_livechat_verification_system,freemoov.livechat.verification.system,model_freemoov_livechat_verification,base.group_system,1,1,1,1
```

`data/ir_config_parameter_data.xml` : ajouter dans `<odoo noupdate="1">` :

```xml
    <record id="param_verification_test_mode" model="ir.config_parameter">
        <field name="key">freemoov_livechat_ai.verification_test_mode</field>
        <field name="value">False</field>
    </record>
```

- [ ] **Step 4: Run test to verify it passes**

Run: commande de test globale
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add freemoov_livechat_ai/models/ freemoov_livechat_ai/security/ freemoov_livechat_ai/data/ freemoov_livechat_ai/tests/
git commit -m "feat(livechat_ai): add two-factor identity verification model"
```

---

### Task 4: Verification tools + sensitive tools

**Files:**
- Create: `freemoov_livechat_ai/services/tools/verification_tools.py`
- Create: `freemoov_livechat_ai/services/tools/orders.py`
- Create: `freemoov_livechat_ai/services/tools/repairs.py`
- Modify: `freemoov_livechat_ai/services/tools/__init__.py` (imports)
- Modify: `freemoov_livechat_ai/data/ir_config_parameter_data.xml` (param `repair_tool_enabled`)
- Test: `freemoov_livechat_ai/tests/test_tools_sensitive.py`

**Interfaces:**
- Consumes: `freemoov.livechat.verification.start_verification/check_code` (Task 3), `run_tool` gate (Task 1).
- Produces: outils `envoyer_code(identifiant)`, `verifier_code(code)`, `statut_commande()` (requires_verification), `statut_reparation()` (requires_verification + param `repair_tool_enabled`), `renvoyer_facture(reference_commande)` (requires_verification — envoie à l'adresse en base, ne retourne jamais le PDF ni les montants).

- [ ] **Step 1: Write the failing test**

```python
# freemoov_livechat_ai/tests/test_tools_sensitive.py
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from ..services import tools
from .common import FreemoovAiCase


@tagged("post_install", "-at_install", "freemoov_ai")
class TestSensitiveTools(FreemoovAiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Client Vérifié", "email": "verif@test.be",
        })
        product = cls.env["product.product"].create({"name": "P", "list_price": 5})
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "order_line": [(0, 0, {"product_id": product.id})],
        })
        cls.order.action_confirm()

    def _verify_channel(self):
        Verif = self.env["freemoov.livechat.verification"]
        with patch.object(type(Verif), "_send_code") as send:
            Verif.start_verification(self.channel, "verif@test.be")
            code = send.call_args.args[2]
        Verif.check_code(self.channel, code)

    def test_statut_commande_blocked_then_ok(self):
        with self.assertRaisesRegex(tools.ToolError, "verification_required"):
            tools.run_tool(self.env, self.channel, "statut_commande", {})
        self._verify_channel()
        res = tools.run_tool(self.env, self.channel, "statut_commande", {})
        self.assertTrue(any(c["reference"] == self.order.name for c in res["commandes"]))

    def test_envoyer_et_verifier_code_flow(self):
        Verif = self.env["freemoov.livechat.verification"]
        with patch.object(type(Verif), "_send_code") as send:
            res = tools.run_tool(self.env, self.channel, "envoyer_code",
                                 {"identifiant": "verif@test.be"})
            code = send.call_args.args[2]
        self.assertIn("***", res["envoye_vers"])
        res = tools.run_tool(self.env, self.channel, "verifier_code", {"code": code})
        self.assertTrue(res["verifie"])

    def test_statut_reparation_disabled_by_param(self):
        self._verify_channel()
        self.env["ir.config_parameter"].sudo().set_param(
            "freemoov_livechat_ai.repair_tool_enabled", "False")
        with self.assertRaisesRegex(tools.ToolError, "indisponible"):
            tools.run_tool(self.env, self.channel, "statut_reparation", {})

    def test_renvoyer_facture_no_amount_in_response(self):
        self._verify_channel()
        invoice = self.order._create_invoices()
        invoice.action_post()
        with patch("odoo.addons.mail.models.mail_template.MailTemplate.send_mail") as sm:
            res = tools.run_tool(self.env, self.channel, "renvoyer_facture",
                                 {"reference_commande": self.order.name})
        self.assertTrue(sm.called)
        self.assertNotIn(str(invoice.amount_total), str(res))
        self.assertIn("***", res["envoye_vers"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: commande de test globale
Expected: FAIL — outils non enregistrés

- [ ] **Step 3: Write the implementation**

```python
# freemoov_livechat_ai/services/tools/verification_tools.py
from . import register


@register(
    "envoyer_code",
    "Démarre la vérification d'identité : envoie un code à 6 chiffres vers l'e-mail ou "
    "le téléphone ENREGISTRÉS chez Freemoov pour ce client. L'identifiant peut être un "
    "e-mail, une référence de commande (ex. S00123) ou de réparation. Toujours demander "
    "l'identifiant AVANT d'appeler cet outil.",
    {
        "type": "object",
        "properties": {"identifiant": {"type": "string"}},
        "required": ["identifiant"],
    },
)
def envoyer_code(env, channel, identifiant):
    res = env["freemoov.livechat.verification"].start_verification(channel, identifiant)
    return {"envoye_vers": res["target_masked"], "canal": res["method"],
            "consigne": "Demande au visiteur de saisir le code reçu."}


@register(
    "verifier_code",
    "Vérifie le code à 6 chiffres saisi par le visiteur. 3 essais maximum.",
    {
        "type": "object",
        "properties": {"code": {"type": "string"}},
        "required": ["code"],
    },
)
def verifier_code(env, channel, code):
    res = env["freemoov.livechat.verification"].check_code(channel, code)
    return {"verifie": res["verified"], "essais_restants": res["attempts_left"]}
```

```python
# freemoov_livechat_ai/services/tools/orders.py
from . import ToolError, register

_STATE_FR = {
    "draft": "devis en attente", "sent": "devis envoyé",
    "sale": "confirmée", "done": "terminée", "cancel": "annulée",
}
_PICKING_FR = {
    "draft": "en préparation", "waiting": "en attente de stock",
    "confirmed": "en préparation", "assigned": "prête à expédier",
    "done": "expédiée", "cancel": "annulée",
}


def _partner_domain(partner):
    return [("partner_id", "child_of", partner.commercial_partner_id.id)]


@register(
    "statut_commande",
    "Commandes récentes du client vérifié : état, expédition, numéro de suivi. "
    "Nécessite une identité vérifiée (envoyer_code puis verifier_code).",
    {"type": "object", "properties": {}},
    requires_verification=True,
)
def statut_commande(env, channel):
    partner = channel._freemoov_ai_verified_partner()
    orders = env["sale.order"].sudo().search(
        _partner_domain(partner) + [("state", "in", ("sale", "done"))],
        limit=5, order="date_order desc")
    out = []
    for o in orders:
        pickings = o.picking_ids.filtered(lambda p: p.state != "cancel")
        last = pickings.sorted("id")[-1:] if pickings else None
        out.append({
            "reference": o.name,
            "date": str(o.date_order.date()),
            "etat": _STATE_FR.get(o.state, o.state),
            "livraison": _PICKING_FR.get(last.state, "") if last else "",
            "transporteur": last.carrier_id.name if last and last.carrier_id else "",
            "numero_suivi": last.carrier_tracking_ref or "" if last else "",
        })
    if not out:
        raise ToolError("Aucune commande confirmée trouvée pour ce client.")
    return {"commandes": out}


@register(
    "renvoyer_facture",
    "Renvoie la facture d'une commande à l'adresse e-mail ENREGISTRÉE du client vérifié. "
    "Ne jamais afficher le contenu de la facture dans le chat.",
    {
        "type": "object",
        "properties": {"reference_commande": {"type": "string"}},
        "required": ["reference_commande"],
    },
    requires_verification=True,
)
def renvoyer_facture(env, channel, reference_commande):
    partner = channel._freemoov_ai_verified_partner()
    order = env["sale.order"].sudo().search(
        _partner_domain(partner) + [("name", "=ilike", reference_commande.strip())], limit=1)
    if not order:
        raise ToolError("Commande introuvable pour ce client.")
    invoice = order.invoice_ids.filtered(lambda m: m.state == "posted")[:1]
    if not invoice:
        raise ToolError("Aucune facture validée sur cette commande — proposer un transfert.")
    template = env.ref("account.email_template_edi_invoice")
    template.sudo().send_mail(invoice.id, email_layout_xmlid="mail.mail_notification_light")
    local, _, dom = (partner.email or "").partition("@")
    return {"envoye_vers": "%s***@%s" % (local[:1], dom)}
```

```python
# freemoov_livechat_ai/services/tools/repairs.py
import json

from . import ToolError, register

_DEFAULT_STAGE_MAP = {}  # rempli via param JSON après l'atelier techniciens


@register(
    "statut_reparation",
    "Dossiers de réparation en cours du client vérifié. Nécessite une identité vérifiée.",
    {"type": "object", "properties": {}},
    requires_verification=True,
)
def statut_reparation(env, channel):
    ICP = env["ir.config_parameter"].sudo()
    if ICP.get_param("freemoov_livechat_ai.repair_tool_enabled") != "True":
        raise ToolError(
            "Le suivi de réparation est indisponible dans l'assistant pour le moment — "
            "proposer un transfert vers un conseiller."
        )
    partner = channel._freemoov_ai_verified_partner()
    domain = [("partner_id", "child_of", partner.commercial_partner_id.id)]
    Task = env["project.task"].sudo()
    if "is_fsm" in Task._fields:
        domain.append(("is_fsm", "=", True))
    tasks = Task.search(domain, limit=5, order="create_date desc")
    if not tasks:
        raise ToolError("Aucun dossier de réparation trouvé pour ce client.")
    stage_map = _DEFAULT_STAGE_MAP
    raw = ICP.get_param("freemoov_livechat_ai.repair_stage_map")
    if raw:
        stage_map = json.loads(raw)
    return {"reparations": [{
        "reference": t.name,
        "magasin": t.project_id.name or "",
        "etat": stage_map.get(t.stage_id.name, t.stage_id.name),
        "ouvert_le": str(t.create_date.date()),
    } for t in tasks]}
```

Imports en fin de `services/tools/__init__.py` :

```python
from . import verification_tools  # noqa: E402,F401
from . import orders  # noqa: E402,F401
from . import repairs  # noqa: E402,F401
```

Param dans `data/ir_config_parameter_data.xml` :

```xml
    <record id="param_repair_tool_enabled" model="ir.config_parameter">
        <field name="key">freemoov_livechat_ai.repair_tool_enabled</field>
        <field name="value">False</field>
    </record>
```

- [ ] **Step 4: Run test to verify it passes**

Run: commande de test globale
Expected: PASS (15 tests)

- [ ] **Step 5: Commit**

```bash
git add freemoov_livechat_ai/services/tools/ freemoov_livechat_ai/data/ freemoov_livechat_ai/tests/
git commit -m "feat(livechat_ai): add 2FA flow tools and verified-only order/repair/invoice tools"
```

---

### Task 5: Anthropic client tool support + agent loop

**Files:**
- Modify: `freemoov_livechat_ai/services/anthropic_client.py`
- Create: `freemoov_livechat_ai/services/agent_loop.py`
- Test: `freemoov_livechat_ai/tests/test_agent_loop.py`

**Interfaces:**
- Consumes: `tools.anthropic_tool_specs()`, `tools.run_tool`, `AnthropicClient`.
- Produces: `AnthropicClient.create_message(system_prompt, messages, tools=None)` retourne en plus `"content"` (blocs bruts) et `"stop_reason"`. `agent_loop.run_agent(env, channel, client, system_prompt, messages) -> {"text", "escalate", "product_ids", "tool_calls", "input_tokens", "output_tokens", "latency_ms"}`. Plafond : `MAX_TOOL_ITERATIONS = 6`.
- `tool_calls` : liste de `{"name", "arguments", "ok": bool, "duration_ms": int}`.
- `product_ids` : ids collectés depuis les résultats de `chercher_produits`/`fiche_produit` (pour les cartes, Task 6).

- [ ] **Step 1: Write the failing test**

```python
# freemoov_livechat_ai/tests/test_agent_loop.py
from unittest.mock import patch

from odoo.tests import tagged

from ..services import agent_loop, tools
from ..services.anthropic_client import AnthropicClient
from .common import FreemoovAiCase


def _resp(text=None, tool_use=None, stop="end_turn"):
    content = []
    if tool_use:
        content.append({"type": "tool_use", "id": "tu_1",
                        "name": tool_use[0], "input": tool_use[1]})
        stop = "tool_use"
    if text:
        content.append({"type": "text", "text": text})
    return {"text": text or "", "content": content, "stop_reason": stop,
            "input_tokens": 10, "output_tokens": 5, "latency_ms": 50}


@tagged("post_install", "-at_install", "freemoov_ai")
class TestAgentLoop(FreemoovAiCase):
    def test_tool_call_then_answer(self):
        responses = [
            _resp(tool_use=("infos_magasins", {"ville": "namur"})),
            _resp(text="Le magasin de Namur est ouvert du mardi au samedi."),
        ]
        client = AnthropicClient(api_key="k", model="m")
        with patch.object(AnthropicClient, "create_message", side_effect=responses):
            out = agent_loop.run_agent(self.env, self.channel, client, "sys",
                                       [{"role": "user", "content": "horaires namur ?"}])
        self.assertIn("Namur", out["text"])
        self.assertEqual(out["tool_calls"][0]["name"], "infos_magasins")
        self.assertTrue(out["tool_calls"][0]["ok"])
        self.assertFalse(out["escalate"])

    def test_tool_error_is_relayed_not_fatal(self):
        responses = [
            _resp(tool_use=("statut_commande", {})),  # canal non vérifié -> ToolError
            _resp(text="Je dois d'abord vérifier votre identité. [ESCALATE]"),
        ]
        client = AnthropicClient(api_key="k", model="m")
        with patch.object(AnthropicClient, "create_message", side_effect=responses):
            out = agent_loop.run_agent(self.env, self.channel, client, "sys",
                                       [{"role": "user", "content": "ma commande ?"}])
        self.assertFalse(out["tool_calls"][0]["ok"])
        self.assertTrue(out["escalate"])
        self.assertNotIn("[ESCALATE]", out["text"])

    def test_iteration_cap(self):
        responses = [_resp(tool_use=("infos_magasins", {}))] * 10
        client = AnthropicClient(api_key="k", model="m")
        with patch.object(AnthropicClient, "create_message", side_effect=responses) as cm:
            out = agent_loop.run_agent(self.env, self.channel, client, "sys",
                                       [{"role": "user", "content": "boucle"}])
        self.assertLessEqual(cm.call_count, agent_loop.MAX_TOOL_ITERATIONS + 1)
        self.assertTrue(out["escalate"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: commande de test globale
Expected: ERROR — `agent_loop` inexistant

- [ ] **Step 3: Write the implementation**

Dans `anthropic_client.py`, remplacer le corps de `create_message` (la signature gagne `tools=None`) :

```python
    def create_message(self, system_prompt, messages, tools=None):
        if not self.api_key:
            raise ValueError("Anthropic API key is not configured")
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        t0 = time.monotonic()
        resp = requests.post(API_URL, headers=headers, data=json.dumps(payload), timeout=self.timeout)
        latency_ms = int((time.monotonic() - t0) * 1000)
        if resp.status_code != 200:
            raise RuntimeError(f"Anthropic API {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        content = data.get("content", [])
        text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        usage = data.get("usage", {})
        return {
            "text": text.strip(),
            "content": content,
            "stop_reason": data.get("stop_reason"),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "latency_ms": latency_ms,
        }
```

```python
# freemoov_livechat_ai/services/agent_loop.py
"""Agentic loop: model <-> tools, capped, with per-call audit trail."""
import json
import logging
import time

from . import tools
from .prompt_builder import parse_response

_logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 6
_PRODUCT_TOOLS = ("chercher_produits", "fiche_produit")


def _collect_product_ids(name, result):
    if name not in _PRODUCT_TOOLS:
        return []
    if "produits" in result:
        return [p["id"] for p in result["produits"]]
    return [result["id"]] if "id" in result else []


def run_agent(env, channel, client, system_prompt, messages):
    specs = tools.anthropic_tool_specs()
    convo = list(messages)
    tool_calls, product_ids = [], []
    total_in = total_out = total_latency = 0
    escalate_forced = False
    result = None

    for _ in range(MAX_TOOL_ITERATIONS + 1):
        result = client.create_message(system_prompt, convo, tools=specs)
        total_in += result["input_tokens"]
        total_out += result["output_tokens"]
        total_latency += result["latency_ms"]

        if result["stop_reason"] != "tool_use":
            break

        convo.append({"role": "assistant", "content": result["content"]})
        tool_results = []
        for block in result["content"]:
            if block.get("type") != "tool_use":
                continue
            name, args = block["name"], block.get("input") or {}
            t0 = time.monotonic()
            try:
                out = tools.run_tool(env, channel, name, args)
                ok, payload = True, json.dumps(out, ensure_ascii=False, default=str)
                product_ids += _collect_product_ids(name, out)
            except tools.ToolError as exc:
                ok, payload = False, json.dumps({"erreur": str(exc)}, ensure_ascii=False)
            except Exception:
                _logger.exception("freemoov_ai: tool %s crashed", name)
                ok, payload = False, json.dumps(
                    {"erreur": "Erreur interne de l'outil — proposer un transfert."},
                    ensure_ascii=False)
            tool_calls.append({
                "name": name, "arguments": args, "ok": ok,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            })
            tool_results.append({
                "type": "tool_result", "tool_use_id": block["id"],
                "content": payload, "is_error": not ok,
            })
        convo.append({"role": "user", "content": tool_results})
    else:
        # cap atteint : on force une sortie propre
        escalate_forced = True

    text, escalate = parse_response(result["text"] if result else "")
    if escalate_forced and not text:
        text = "Je n'arrive pas à aboutir sur cette demande, je préfère vous passer un conseiller."
    return {
        "text": text,
        "escalate": escalate or escalate_forced,
        "product_ids": list(dict.fromkeys(product_ids)),
        "tool_calls": tool_calls,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "latency_ms": total_latency,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: commande de test globale
Expected: PASS (18 tests)

- [ ] **Step 5: Commit**

```bash
git add freemoov_livechat_ai/services/anthropic_client.py freemoov_livechat_ai/services/agent_loop.py freemoov_livechat_ai/tests/
git commit -m "feat(livechat_ai): add tool-use support to client and capped agent loop"
```

---

### Task 6: Wire loop into channel + tool audit log + product cards + typing

**Files:**
- Modify: `freemoov_livechat_ai/models/discuss_channel.py` (dans `_freemoov_ai_respond`)
- Modify: `freemoov_livechat_ai/models/livechat_ai_log.py` (2 champs)
- Create: `freemoov_livechat_ai/views/product_cards_template.xml`
- Modify: `freemoov_livechat_ai/__manifest__.py` (data)
- Modify: `freemoov_livechat_ai/views/livechat_ai_log_view.xml` (afficher les 2 champs)
- Test: `freemoov_livechat_ai/tests/test_respond_flow.py`

**Interfaces:**
- Consumes: `agent_loop.run_agent` (Task 5).
- Produces: `_freemoov_ai_respond` utilise la boucle, journalise `tools_used` (Char) + `tool_calls_json` (Text), applique un budget tokens par conversation (statut de log `skipped_budget`, à ajouter à la sélection `status` du modèle de log ; param `freemoov_livechat_ai.conversation_token_budget`, défaut 50 000, à lire dans `_freemoov_ai_config`), poste les cartes via `_freemoov_ai_post_product_cards(product_ids)` (template QWeb `freemoov_livechat_ai.assistant_product_cards`), et signale la frappe via `_freemoov_ai_notify_typing(is_typing)`.

- [ ] **Step 1: Write the failing test**

```python
# freemoov_livechat_ai/tests/test_respond_flow.py
from unittest.mock import patch

from odoo.tests import tagged

from ..services.anthropic_client import AnthropicClient
from .common import FreemoovAiCase
from .test_agent_loop import _resp


@tagged("post_install", "-at_install", "freemoov_ai")
class TestRespondFlow(FreemoovAiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("freemoov_livechat_ai.enabled", "True")
        ICP.set_param("freemoov_livechat_ai.dry_run", "False")
        ICP.set_param("freemoov_livechat_ai.api_key", "test-key")

    def test_respond_logs_tools_and_posts(self):
        responses = [
            _resp(tool_use=("infos_magasins", {})),
            _resp(text="Nos trois magasins sont ouverts du mardi au samedi."),
        ]
        with patch.object(AnthropicClient, "create_message", side_effect=responses):
            log = self.channel._freemoov_ai_respond("vos horaires ?")
        self.assertEqual(log.status, "ok")
        self.assertEqual(log.tools_used, "infos_magasins")
        self.assertIn('"ok": true', log.tool_calls_json)
        body = self.channel.message_ids[0].body
        self.assertIn("mardi", str(body))

    def test_product_cards_posted(self):
        tmpl = self.env["product.template"].create({
            "name": "Carte Trott", "list_price": 999.0,
            "is_published": True, "sale_ok": True,
        })
        responses = [
            _resp(tool_use=("fiche_produit", {"product_id": tmpl.id})),
            _resp(text="Voici la fiche."),
        ]
        with patch.object(AnthropicClient, "create_message", side_effect=responses):
            self.channel._freemoov_ai_respond("montre la Carte Trott")
        bodies = [str(m.body) for m in self.channel.message_ids]
        self.assertTrue(any("fm-assistant-card" in b for b in bodies))
        self.assertTrue(any("Carte Trott" in b and "999" in b for b in bodies))
```

- [ ] **Step 2: Run test to verify it fails**

Run: commande de test globale
Expected: FAIL — `tools_used` inexistant sur le log ; pas de carte postée

- [ ] **Step 3: Write the implementation**

`models/livechat_ai_log.py` — ajouter les champs (près des champs existants) :

```python
    tools_used = fields.Char(string="Outils utilisés")
    tool_calls_json = fields.Text(string="Détail des appels d'outils")
```

`views/livechat_ai_log_view.xml` — ajouter `<field name="tools_used"/>` dans la tree view et `tool_calls_json` (readonly, widget text) dans la form view existante.

`views/product_cards_template.xml` :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<odoo>
    <template id="assistant_product_cards" name="Assistant: Product Cards">
        <div class="fm-assistant-cards">
            <t t-foreach="products" t-as="p">
                <a t-att-href="p['url']" target="_blank" class="fm-assistant-card">
                    <img t-attf-src="/web/image/product.template/#{p['id']}/image_256"
                         t-att-alt="p['nom']" loading="lazy"/>
                    <div class="fm-assistant-card-body">
                        <div class="fm-assistant-card-name" t-esc="p['nom']"/>
                        <div class="fm-assistant-card-price">
                            <t t-esc="'%.0f' % p['prix_tvac']"/> € TVAC
                        </div>
                    </div>
                </a>
            </t>
        </div>
    </template>
</odoo>
```

Manifest : ajouter `'views/product_cards_template.xml'` à `data`.

`models/discuss_channel.py` — imports :

```python
from ..services import agent_loop
from ..services.tools.catalog import _serialize
```

Nouvelles méthodes sur `DiscussChannel` :

```python
    def _freemoov_ai_notify_typing(self, is_typing):
        """Typing indicator via the bot's channel membership (native bus)."""
        bot = self._freemoov_ai_bot_partner()
        if not bot:
            return
        member = self.channel_member_ids.filtered(lambda m: m.partner_id == bot)
        if not member:
            self.sudo().add_members(partner_ids=bot.ids, post_joined_message=False)
            member = self.channel_member_ids.filtered(lambda m: m.partner_id == bot)
        try:
            member.sudo()._notify_typing(is_typing)
        except Exception:
            _logger.debug("freemoov_ai: typing notify failed", exc_info=True)

    def _freemoov_ai_post_product_cards(self, product_ids):
        tmpls = self.env["product.template"].sudo().browse(product_ids).exists()
        tmpls = tmpls.filtered(lambda t: t.is_published and t.active)[:3]
        if not tmpls:
            return
        html = self.env["ir.qweb"]._render(
            "freemoov_livechat_ai.assistant_product_cards",
            {"products": [_serialize(self.env, t) for t in tmpls]},
        )
        post_kwargs = {"body": html, "message_type": "comment",
                       "subtype_xmlid": "mail.mt_comment"}
        bot = self._freemoov_ai_bot_partner()
        if bot:
            post_kwargs["author_id"] = bot.id
        self.sudo().message_post(**post_kwargs)
```

Dans `_freemoov_ai_respond`, remplacer le bloc entre la construction du prompt et le `parse_response` (l'appel simple `client.create_message` + `parse_response(result["text"])`) par :

```python
        # Budget tokens par conversation (spec §8) : somme des logs du canal.
        Log = self.env["freemoov.livechat.ai.log"].sudo()
        budget = int(cfg.get("conversation_token_budget") or 50_000)
        spent = sum((l.input_tokens or 0) + (l.output_tokens or 0)
                    for l in Log.search([("channel_id", "=", self.id)]))
        if spent >= budget:
            return self._freemoov_ai_log("skipped_budget", visitor_message=visitor_message_text)

        client = AnthropicClient(api_key=cfg["api_key"], model=cfg["model"], max_tokens=cfg["max_tokens"])
        self._freemoov_ai_notify_typing(True)
        try:
            out = agent_loop.run_agent(self.env, self, client, system_prompt, messages)
        except Exception as e:
            _logger.exception("freemoov_ai: agent loop failed")
            return self._freemoov_ai_log("error", visitor_message=visitor_message_text, error_message=str(e))
        finally:
            self._freemoov_ai_notify_typing(False)

        text, escalate = out["text"], out["escalate"]
        cost = estimate_cost_eur(out["input_tokens"], out["output_tokens"])
        tool_kw = {
            "tools_used": ", ".join(dict.fromkeys(c["name"] for c in out["tool_calls"])),
            "tool_calls_json": json.dumps(out["tool_calls"], ensure_ascii=False, default=str),
        }
```

(ajouter `import json` en tête de fichier ; passer `**tool_kw` aux deux `_freemoov_ai_log` de fin — dry_run et ok/escalated — et remplacer leurs `input_tokens=result[...]` par `out[...]`, `latency_ms=out["latency_ms"]`).

Après le `message_post` existant du texte, ajouter :

```python
        if out["product_ids"]:
            self._freemoov_ai_post_product_cards(out["product_ids"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: commande de test globale
Expected: PASS (20 tests)

- [ ] **Step 5: Commit**

```bash
git add freemoov_livechat_ai/
git commit -m "feat(livechat_ai): route responses through agent loop with cards, typing and tool audit"
```

---

### Task 7: System prompt rewrite

**Files:**
- Modify: `freemoov_livechat_ai/services/prompt_builder.py` (SYSTEM_TEMPLATE)
- Modify: `freemoov_livechat_ai/services/knowledge_base.py` (STATIC_FAQ réduit ; suppression de l'injection catalogue)
- Test: `freemoov_livechat_ai/tests/test_prompt.py`

**Interfaces:**
- Consumes: rien de nouveau.
- Produces: `build_system_prompt(env)` sans dump catalogue (les produits passent par les outils) ; politiques corrigées : Charleroi listé, retour **14 jours** (aligné `RETURN_DAYS` de `website_freemoov/models/seo.py`), pas de « Bruxelles à confirmer ».

- [ ] **Step 1: Write the failing test**

```python
# freemoov_livechat_ai/tests/test_prompt.py
from odoo.tests import tagged

from ..services.prompt_builder import build_system_prompt
from .common import FreemoovAiCase


@tagged("post_install", "-at_install", "freemoov_ai")
class TestPrompt(FreemoovAiCase):
    def test_prompt_content(self):
        prompt = build_system_prompt(self.env)
        self.assertIn("Charleroi", prompt)
        self.assertNotIn("Bruxelles", prompt)
        self.assertIn("14 jours", prompt)
        self.assertNotIn("30 jours", prompt)
        # le catalogue ne doit plus être injecté : il passe par les outils
        self.assertNotIn("Catalogue produits", prompt)
        self.assertIn("chercher_produits", prompt)
        self.assertIn("[ESCALATE]", prompt)
```

- [ ] **Step 2: Run test to verify it fails**

Run: commande de test globale
Expected: FAIL (« Bruxelles » présent, « Catalogue produits » injecté)

- [ ] **Step 3: Write the implementation**

Dans `knowledge_base.py` : remplacer `STATIC_FAQ` par la version corrigée (mêmes rubriques, avec : magasins = Liège / Namur / Charleroi + horaires ; « Retour gratuit sous 14 jours » ; supprimer la ligne Bruxelles) et remplacer `build_knowledge_base` :

```python
def build_knowledge_base(env):
    # Catalogue et magasins passent désormais par les outils : le prompt ne
    # transporte plus que les politiques stables.
    return STATIC_FAQ
```

Dans `prompt_builder.py`, ajouter au `SYSTEM_TEMPLATE`, après la section « Règles absolues » :

```python
# Outils
Tu disposes d'outils pour consulter les données réelles : `chercher_produits`,
`fiche_produit`, `infos_magasins`, `statut_commande`, `statut_reparation`,
`renvoyer_facture`, et `envoyer_code`/`verifier_code` pour vérifier une identité.
- Utilise TOUJOURS un outil plutôt que ta mémoire pour un prix, un stock, un horaire,
  une commande ou une réparation.
- Pour toute donnée personnelle (commande, réparation, facture) : identité vérifiée
  d'abord (envoyer_code puis verifier_code). Si le visiteur refuse : [ESCALATE].
- Si un outil renvoie `verification_required`, explique la démarche et demande
  l'e-mail ou la référence.
- Ne relaie JAMAIS le contenu brut d'une erreur d'outil : reformule ou escalade.
```

- [ ] **Step 4: Run test to verify it passes**

Run: commande de test globale
Expected: PASS (21 tests)

- [ ] **Step 5: Commit**

```bash
git add freemoov_livechat_ai/services/ freemoov_livechat_ai/tests/
git commit -m "feat(livechat_ai): rewrite system prompt for tool use and fix policy facts"
```

---

### Task 8: HTTP socle `/api/assistant/v1` (outils publics, pour l'agent vocal)

**Files:**
- Create: `freemoov_livechat_ai/controllers/__init__.py`
- Create: `freemoov_livechat_ai/controllers/assistant_api.py`
- Modify: `freemoov_livechat_ai/__init__.py` (`from . import controllers`)
- Modify: `freemoov_livechat_ai/data/ir_config_parameter_data.xml` (param `api_token`, vide par défaut)
- Test: `freemoov_livechat_ai/tests/test_http_api.py` (`HttpCase`)

**Interfaces:**
- Produces: `POST /api/assistant/v1/call/<tool_name>` (JSON `{"arguments": {...}}`, header `X-Assistant-Token`) et `GET /api/assistant/v1/tools`. Seuls les outils de `PUBLIC_HTTP_TOOLS = {"infos_magasins", "chercher_produits", "fiche_produit"}` sont exposés — les outils à identité restent internes en v1 (l'agent vocal aura son propre flux d'identité, hors périmètre).
- Token vide en base ⇒ API désactivée (403 systématique).

- [ ] **Step 1: Write the failing test**

```python
# freemoov_livechat_ai/tests/test_http_api.py
import json

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "freemoov_ai")
class TestAssistantApi(HttpCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param(
            "freemoov_livechat_ai.api_token", "tok-test")

    def _call(self, tool, args=None, token="tok-test"):
        return self.url_open(
            "/api/assistant/v1/call/%s" % tool,
            data=json.dumps({"arguments": args or {}}),
            headers={"Content-Type": "application/json",
                     **({"X-Assistant-Token": token} if token else {})},
        )

    def test_no_token_403(self):
        self.assertEqual(self._call("infos_magasins", token=None).status_code, 403)
        self.assertEqual(self._call("infos_magasins", token="mauvais").status_code, 403)

    def test_empty_param_disables_api(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "freemoov_livechat_ai.api_token", "")
        self.assertEqual(self._call("infos_magasins").status_code, 403)

    def test_public_tool_ok(self):
        resp = self._call("infos_magasins", {"ville": "namur"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["magasins"][0]["ville"], "Namur")

    def test_sensitive_tool_not_exposed(self):
        self.assertEqual(self._call("statut_commande").status_code, 404)
```

- [ ] **Step 2: Run test to verify it fails**

Run: commande de test globale
Expected: FAIL — 404 partout (routes inexistantes), y compris là où on attend 200/403

- [ ] **Step 3: Write the implementation**

```python
# freemoov_livechat_ai/controllers/__init__.py
from . import assistant_api
```

```python
# freemoov_livechat_ai/controllers/assistant_api.py
"""Server-to-server tool API (voice agent socle). Public tools only in v1."""
import hmac
import json

from odoo import http
from odoo.http import request

from ..services import tools

PUBLIC_HTTP_TOOLS = {"infos_magasins", "chercher_produits", "fiche_produit"}


class AssistantApiController(http.Controller):

    def _check_token(self):
        expected = request.env["ir.config_parameter"].sudo().get_param(
            "freemoov_livechat_ai.api_token") or ""
        provided = request.httprequest.headers.get("X-Assistant-Token") or ""
        return bool(expected) and hmac.compare_digest(expected, provided)

    def _json(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, ensure_ascii=False, default=str),
            headers=[("Content-Type", "application/json")], status=status)

    @http.route("/api/assistant/v1/tools", type="http", auth="public",
                methods=["GET"], csrf=False)
    def list_tools(self):
        if not self._check_token():
            return self._json({"error": "forbidden"}, 403)
        specs = [s for s in tools.anthropic_tool_specs() if s["name"] in PUBLIC_HTTP_TOOLS]
        return self._json({"tools": specs})

    @http.route("/api/assistant/v1/call/<string:tool_name>", type="http",
                auth="public", methods=["POST"], csrf=False)
    def call_tool(self, tool_name):
        if not self._check_token():
            return self._json({"error": "forbidden"}, 403)
        if tool_name not in PUBLIC_HTTP_TOOLS:
            return self._json({"error": "unknown_tool"}, 404)
        try:
            body = json.loads(request.httprequest.get_data() or b"{}")
        except ValueError:
            return self._json({"error": "invalid_json"}, 400)
        try:
            result = tools.run_tool(request.env, None, tool_name,
                                    body.get("arguments") or {})
        except tools.ToolError as exc:
            return self._json({"error": str(exc)}, 422)
        return self._json(result)
```

`freemoov_livechat_ai/__init__.py` : ajouter `from . import controllers`.

Param :

```xml
    <record id="param_api_token" model="ir.config_parameter">
        <field name="key">freemoov_livechat_ai.api_token</field>
        <field name="value"></field>
    </record>
```

- [ ] **Step 4: Run test to verify it passes**

Run: commande de test globale
Expected: PASS (25 tests)

- [ ] **Step 5: Commit**

```bash
git add freemoov_livechat_ai/
git commit -m "feat(livechat_ai): expose public tools over token-authenticated HTTP API"
```

---

### Task 9: Widget theming + patches OWL

**Files:**
- Create: `freemoov_livechat_ai/static/src/scss/assistant_theme.scss`
- Create: `freemoov_livechat_ai/static/src/js/assistant_suggestions.js`
- Create: `freemoov_livechat_ai/static/src/xml/assistant_suggestions.xml`
- Modify: `freemoov_livechat_ai/__manifest__.py` (`assets`)
- Test: vérification manuelle (frontend) + `freemoov_livechat_ai/tests/test_assets.py`

**Interfaces:**
- Consumes: messages HTML des cartes (classe `fm-assistant-cards`, Task 6) rendus nativement par le widget im_livechat.
- Produces: bundle `im_livechat.assets_embed_core` étendu : thème Freemoov (couleurs, cartes) + barre de suggestions au démarrage + bouton « Parler à un conseiller » (envoie le message littéral `Je veux parler à un conseiller` — le prompt système répond par `[ESCALATE]`).

- [ ] **Step 1: Write the failing asset test**

```python
# freemoov_livechat_ai/tests/test_assets.py
from odoo.tests import tagged

from .common import FreemoovAiCase


@tagged("post_install", "-at_install", "freemoov_ai")
class TestAssets(FreemoovAiCase):
    def test_assets_registered(self):
        manifest = self.env["ir.module.module"].search(
            [("name", "=", "freemoov_livechat_ai")])
        self.assertEqual(manifest.state, "installed")
        attachments = self.env["ir.asset"].search(
            [("bundle", "=", "im_livechat.assets_embed_core"),
             ("path", "like", "freemoov_livechat_ai%")])
        self.assertTrue(attachments, "assets du widget non enregistrés")
```

- [ ] **Step 2: Run to verify it fails**

Run: commande de test globale
Expected: FAIL — aucun asset

- [ ] **Step 3: Write the implementation**

`__manifest__.py` :

```python
    'assets': {
        'im_livechat.assets_embed_core': [
            'freemoov_livechat_ai/static/src/scss/assistant_theme.scss',
            'freemoov_livechat_ai/static/src/js/assistant_suggestions.js',
            'freemoov_livechat_ai/static/src/xml/assistant_suggestions.xml',
        ],
    },
```

`assistant_theme.scss` (extrait fonctionnel — couleurs à affiner avec la charte) :

```scss
// Freemoov livechat theme
.o-livechat-LivechatButton {
    background: #1a1a2e;
}
.o-mail-ChatWindow-header {
    background: #1a1a2e;
    color: #fff;
}
.fm-assistant-cards {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    .fm-assistant-card {
        display: block;
        width: 140px;
        border: 1px solid #e3e3e3;
        border-radius: 8px;
        overflow: hidden;
        text-decoration: none;
        color: inherit;
        img { width: 100%; height: 100px; object-fit: cover; }
        .fm-assistant-card-body { padding: 6px 8px; }
        .fm-assistant-card-name { font-size: 12px; font-weight: 600; }
        .fm-assistant-card-price { font-size: 12px; color: #0d6efd; }
    }
}
.fm-assistant-suggestions {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    padding: 8px;
    button {
        border: 1px solid #ccc;
        border-radius: 16px;
        background: #fff;
        padding: 4px 10px;
        font-size: 12px;
        cursor: pointer;
        &:hover { background: #f3f3f3; }
    }
}
```

`assistant_suggestions.js` :

```javascript
/** @odoo-module **/

import { Thread } from "@mail/core/common/thread";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

export const FM_SUGGESTIONS = [
    "Suivre ma réparation",
    "Trouver une trottinette",
    "Horaires et magasins",
    "Suivre ma commande",
    "Je veux parler à un conseiller",
];

patch(Thread.prototype, {
    setup() {
        super.setup(...arguments);
        this.fmThreadService = useService("mail.thread");
    },
    get fmShowSuggestions() {
        const thread = this.props.thread;
        return thread?.channel_type === "livechat" &&
            (thread.messages?.length ?? 0) <= 1;
    },
    get fmSuggestions() {
        return FM_SUGGESTIONS;
    },
    async fmSendSuggestion(text) {
        await this.fmThreadService.post(this.props.thread, text);
    },
});
```

`assistant_suggestions.xml` (héritage du template Thread pour insérer la barre) :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="freemoov_livechat_ai.ThreadSuggestions"
       t-inherit="mail.Thread" t-inherit-mode="extension">
        <xpath expr="//*[hasclass('o-mail-Thread')]" position="inside">
            <div t-if="fmShowSuggestions" class="fm-assistant-suggestions">
                <t t-foreach="fmSuggestions" t-as="sugg" t-key="sugg">
                    <button t-esc="sugg" t-on-click="() => this.fmSendSuggestion(sugg)"/>
                </t>
            </div>
        </xpath>
    </t>
</templates>
```

**Note d'exécution :** les points d'extension exacts (`mail.Thread`, service `mail.thread`, classe `o-livechat-LivechatButton`) sont à confronter aux sources locales avant d'écrire :
`docker exec freemoov-odoo-v17 sh -c "grep -rn 'o-livechat-LivechatButton\|t-name=\"mail.Thread\"' /usr/lib/python3/dist-packages/odoo/addons/im_livechat/static /usr/lib/python3/dist-packages/odoo/addons/mail/static | head"`
Ajuster les sélecteurs/xpaths à ce que renvoie ce grep — le mécanisme (patch OWL + t-inherit extension) reste celui-ci.

- [ ] **Step 4: Verify**

Run: commande de test globale → asset test PASS.
Vérification manuelle : `docker restart freemoov-odoo-v17`, activer le canal livechat sur le site local, ouvrir `http://localhost:8069`, contrôler : bouton themé, suggestions visibles à l'ouverture, clic « Horaires et magasins » → réponse du bot (dry_run désactivé + clé API de test), cartes stylées.

- [ ] **Step 5: Commit**

```bash
git add freemoov_livechat_ai/static/ freemoov_livechat_ai/__manifest__.py freemoov_livechat_ai/tests/test_assets.py freemoov_livechat_ai/tests/__init__.py
git commit -m "feat(livechat_ai): theme livechat widget and add start suggestions"
```

---

### Task 10: Regression suite (9 cas Ringover)

**Files:**
- Create: `freemoov_livechat_ai/tests/test_scenarios.py`
- Test: lui-même

**Interfaces:**
- Consumes: tout le pipeline (`_freemoov_ai_respond` mocké au niveau `AnthropicClient.create_message`).
- Produces: suite de scénarios vérifiant **le contrat outillage/sécurité** (quel outil doit être appelable, quelle donnée ne doit jamais sortir), indépendante du texte généré. Les réponses du modèle sont simulées ; ce qu'on teste, c'est le comportement du serveur.

- [ ] **Step 1: Write the scenarios test**

```python
# freemoov_livechat_ai/tests/test_scenarios.py
"""Cas tirés des appels Ringover des 30-31/07/2026 (voir docs/ANALYSE_APPELS_2026-07-31.md).
On ne teste pas la prose du modèle : on teste que les outils et les barrières
serveur se comportent comme la conversation réelle l'exige."""
from unittest.mock import patch

from odoo.tests import tagged

from ..services import tools
from .common import FreemoovAiCase


@tagged("post_install", "-at_install", "freemoov_ai")
class TestRingoverScenarios(FreemoovAiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Martino Lançoulon", "email": "martino@test.be",
        })

    def _verify(self):
        Verif = self.env["freemoov.livechat.verification"]
        with patch.object(type(Verif), "_send_code") as send:
            Verif.start_verification(self.channel, "martino@test.be")
            code = send.call_args.args[2]
        Verif.check_code(self.channel, code)

    # Appel « suivi réparation Namur » : sans vérification, rien ne sort.
    def test_repair_status_needs_verification(self):
        with self.assertRaisesRegex(tools.ToolError, "verification_required"):
            tools.run_tool(self.env, self.channel, "statut_reparation", {})

    # Même vérifié : outil désactivé tant que l'atelier statuts n'a pas eu lieu.
    def test_repair_status_gated_by_param(self):
        self._verify()
        with self.assertRaisesRegex(tools.ToolError, "indisponible"):
            tools.run_tool(self.env, self.channel, "statut_reparation", {})

    # Appel « facture non reçue » (Caterina) : jamais de montant dans la réponse.
    def test_invoice_flow_no_amounts(self):
        product = self.env["product.product"].create({"name": "T", "list_price": 1234.56})
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": product.id})],
        })
        order.action_confirm()
        inv = order._create_invoices()
        inv.action_post()
        self._verify()
        with patch("odoo.addons.mail.models.mail_template.MailTemplate.send_mail"):
            res = tools.run_tool(self.env, self.channel, "renvoyer_facture",
                                 {"reference_commande": order.name})
        self.assertNotIn("1234", str(res))

    # Appel « conseil 1400 € » : la recherche respecte le budget.
    def test_budget_search(self):
        self.env["product.template"].create({
            "name": "Odyssor Drift Test", "list_price": 1399.0,
            "is_published": True, "sale_ok": True,
        })
        self.env["product.template"].create({
            "name": "Grosse Machine Test", "list_price": 2500.0,
            "is_published": True, "sale_ok": True,
        })
        res = tools.run_tool(self.env, self.channel, "chercher_produits",
                             {"recherche": "Test", "budget_max": 1400})
        noms = [p["nom"] for p in res["produits"]]
        self.assertIn("Odyssor Drift Test", noms)
        self.assertNotIn("Grosse Machine Test", noms)

    # Appel « Dualtron Popular vue sur le site » : le stock cité vient des
    # entrepôts, pas du flag de publication (58 % de publiés en rupture).
    def test_availability_from_stock_not_publication(self):
        tmpl = self.env["product.template"].create({
            "name": "Popular Rupture Test", "list_price": 800.0,
            "is_published": True, "sale_ok": True, "detailed_type": "product",
        })
        res = tools.run_tool(self.env, self.channel, "fiche_produit",
                             {"product_id": tmpl.id})
        self.assertTrue(all(q == 0 for q in res["dispo"].values()))
        self.assertIn("confirmer en magasin", res["note"])

    # Injection : le visiteur prétend être vérifié — le serveur décide.
    def test_prompt_injection_cannot_bypass_gate(self):
        with self.assertRaisesRegex(tools.ToolError, "verification_required"):
            tools.run_tool(self.env, self.channel, "statut_commande",
                           {})  # aucun argument du modèle ne peut lever la barrière
```

- [ ] **Step 2: Run to verify state**

Run: commande de test globale
Expected: PASS direct (tout est déjà implémenté) — si un cas échoue, c'est un bug réel à corriger avant de continuer.

- [ ] **Step 3: Commit**

```bash
git add freemoov_livechat_ai/tests/test_scenarios.py freemoov_livechat_ai/tests/__init__.py
git commit -m "test(livechat_ai): add regression scenarios derived from real call transcripts"
```

---

### Task 11: Config settings UI + full local check

**Files:**
- Modify: `freemoov_livechat_ai/models/res_config_settings.py`
- Modify: `freemoov_livechat_ai/views/res_config_settings_view.xml`
- Test: vérification manuelle backend + suite complète

**Interfaces:**
- Produces: dans Réglages → Livechat AI, exposer 3 nouveaux booléens/champs liés aux params : `verification_test_mode`, `repair_tool_enabled`, `api_token` (suivre le pattern des champs existants du fichier — `config_parameter=...`).

- [ ] **Step 1: Add fields**

Dans `res_config_settings.py`, suivre le pattern existant du fichier et ajouter :

```python
    freemoov_ai_verification_test_mode = fields.Boolean(
        string="2FA en mode test (code au journal)",
        config_parameter="freemoov_livechat_ai.verification_test_mode")
    freemoov_ai_repair_tool_enabled = fields.Boolean(
        string="Activer le suivi de réparation",
        config_parameter="freemoov_livechat_ai.repair_tool_enabled")
    freemoov_ai_api_token = fields.Char(
        string="Token API assistant (vocal)",
        config_parameter="freemoov_livechat_ai.api_token")
```

Vue : ajouter les 3 champs dans le bloc existant de `res_config_settings_view.xml`.

- [ ] **Step 2: Run the whole suite + module update**

Run: commande de test globale
Expected: PASS complet (≈31 tests), aucun warning de vue au chargement.

- [ ] **Step 3: Manual smoke test (site local)**

1. `docker restart freemoov-odoo-v17`
2. Backend : Réglages → activer `enabled`, désactiver `dry_run`, renseigner une vraie clé API de test, activer `verification_test_mode`.
3. Site `http://localhost:8069` : ouvrir le chat, dérouler les 4 suggestions une à une.
4. Vérifier dans Livechat AI → Journal : outils appelés, coût, latence par échange.
5. Tester le flux 2FA avec un client existant de la base locale (code lu dans le journal serveur : `docker logs freemoov-odoo-v17 | grep "2FA TEST MODE"`).

- [ ] **Step 4: Commit**

```bash
git add freemoov_livechat_ai/models/res_config_settings.py freemoov_livechat_ai/views/res_config_settings_view.xml
git commit -m "feat(livechat_ai): expose verification, repair and API token settings"
```

---

## Post-plan (hors tasks, à planifier avec Enzo)

1. **Staging Odoo.sh** : pousser la branche, activer `verification_test_mode`, faire tester l'équipe Freemoov (spec §9.3).
2. **Atelier statuts FSM** avec les techniciens → remplir `freemoov_livechat_ai.repair_stage_map` (JSON `{"nom de stage": "libellé client"}`) → activer `repair_tool_enabled`.
3. **Prod restreinte** : `enabled=True` avec prompt limité aux infos pratiques + produits, puis élargissement après lecture des journaux (spec §9.4).
4. **Crédits IAP SMS** à vérifier sur le compte avant d'annoncer le 2FA par SMS.
