"""What the system prompt must say — and must not.

Every assertion here is a fact a visitor can be told. A prompt that drifts
from the shop's real policies is not a style problem: the model states what it
reads, with the same confidence either way.
"""
from unittest.mock import patch

from odoo.tests import tagged

from ..services import prompt_builder, tools
from ..services.knowledge_base import STATIC_FAQ, build_knowledge_base
from ..services.prompt_builder import (
    KNOWLEDGE_BASE_SLOT,
    SYSTEM_TEMPLATE,
    build_system_prompt,
)
from .common import FreemoovAiCase


@tagged("post_install", "-at_install", "freemoov_ai")
class TestPrompt(FreemoovAiCase):
    def setUp(self):
        super().setUp()
        self.prompt = build_system_prompt(self.env)

    # -- faits corrigés ---------------------------------------------------
    def test_prompt_content(self):
        self.assertIn("Charleroi", self.prompt)
        self.assertNotIn("Bruxelles", self.prompt)
        self.assertIn("14 jours", self.prompt)
        self.assertNotIn("30 jours", self.prompt)
        # le catalogue ne doit plus être injecté : il passe par les outils
        self.assertNotIn("Catalogue produits", self.prompt)
        self.assertIn("chercher_produits", self.prompt)
        self.assertIn("[ESCALATE]", self.prompt)

    def test_the_three_stores_come_from_the_seo_source_of_truth(self):
        """`website._STORES` is where the addresses live — the store pages, the
        LocalBusiness JSON-LD and `infos_magasins` all read it. A fourth copy
        typed by hand in the FAQ is a fourth copy to forget to update.
        """
        Website = self.env["website"]
        self.assertEqual(set(Website._STORES), {"liege", "namur", "charleroi"})
        for store in Website._STORES.values():
            self.assertIn(store["street"], self.prompt)
            self.assertIn(store["postal_code"], self.prompt)
            self.assertIn(store["locality"], self.prompt)
        self.assertIn(Website._STORE_PHONE, self.prompt)

    def test_the_opening_hours_are_the_real_ones(self):
        self.assertIn("mardi-vendredi 11:00-19:00", self.prompt)
        self.assertIn("samedi 11:00-17:00", self.prompt)

    def test_free_delivery_and_belgian_law_survive_the_rewrite(self):
        """The rewrite corrects the wrong facts; it may not lose the right
        ones — these four are what most visitors actually ask about.
        """
        self.assertIn("190", self.prompt)
        self.assertIn("1 à 5 jours ouvrés", self.prompt)
        self.assertIn("Garantie 2 ans", self.prompt)
        self.assertIn("25 km/h", self.prompt)
        self.assertIn("16 ans", self.prompt)

    # -- plus de catalogue dans le prompt ---------------------------------
    def test_the_catalogue_never_reaches_the_prompt(self):
        """The catalogue moved to `chercher_produits`. Injected here it was
        stale by construction (prices and stock frozen at prompt build), it
        cost tokens on every single turn, and it capped what the model could
        see at 40 products out of the whole shop.
        """
        # Priced far above anything real on purpose: the dump this test guards
        # against was ordered by `list_price desc` and capped at 40 rows, so a
        # plausible price would have made the assertion pass on an empty top 40
        # and proven nothing.
        self.env["product.template"].create({
            "name": "Trottinette Fictive Zeta 9000",
            "list_price": 987654.0,
            "is_published": True,
            "sale_ok": True,
        })
        prompt = build_system_prompt(self.env)
        self.assertNotIn("Zeta 9000", prompt)
        self.assertNotIn("987654", prompt)

    def test_the_knowledge_base_is_only_the_static_policies(self):
        self.assertEqual(build_knowledge_base(self.env), STATIC_FAQ)

    # -- outils -----------------------------------------------------------
    def test_every_registered_tool_is_named_in_the_prompt(self):
        """The API carries the specs, but the prompt is what tells the model
        the toolbox exists at all. A tool added to the registry and forgotten
        here is a tool the model rarely reaches for.
        """
        for name in tools.TOOLS:
            self.assertIn(name, self.prompt, "outil absent du prompt : %s" % name)

    def test_the_live_store_tool_outranks_the_static_faq(self):
        """The FAQ repeats the addresses for context; it is not the source.
        Without this line the model answers opening hours from a block of text
        nobody re-reads when the shop changes them.
        """
        self.assertIn("infos_magasins", self.prompt)
        self.assertIn("source vivante", self.prompt)

    def test_full_urls_are_built_from_the_canonical_domain(self):
        """`infos_magasins` returns a path (`/freemoov-liege-1`). Pasted raw
        into a chat bubble it is not a link, so the prompt has to say what to
        prefix it with — and with which host: `www` is the canonical form
        (`website_freemoov/models/seo.py`), the bare domain only redirects to
        it. The model copies whatever URL shape it reads here.
        """
        self.assertIn(self.env["website"]._STORES["liege"]["path"], self.prompt)
        self.assertIn("https://www.freemoov.com", self.prompt)
        self.assertNotIn("https://freemoov.com", self.prompt)

    # -- vérification d'identité ------------------------------------------
    def test_an_expired_verification_is_explained_not_repeated(self):
        """A verification lapses after 30 minutes and `run_tool` refuses
        before the tool runs, with the same `verification_required` as a
        visitor who never verified. Only the model can tell the two apart —
        and a visitor told "verify yourself" twice in a row assumes it broke.
        """
        self.assertIn("30 minutes", self.prompt)
        self.assertIn("expir", self.prompt)

    def test_the_code_quota_ends_on_a_human_not_on_a_retry(self):
        self.assertIn("3 envois de code", self.prompt)
        self.assertIn("conseiller", self.prompt)

    def test_a_dead_code_is_told_apart_from_a_wrong_one(self):
        """`_check_code` answers `attempts_left: 0` for an expired code, a
        superseded one and a locked-out one alike — the same shape as a wrong
        code, minus the retries. Without the rule the model reads "faux" and
        makes the visitor retype a code that can no longer work, forever.
        """
        self.assertIn("essais_restants", self.prompt)
        self.assertIn("10 minutes", self.prompt)

    def test_the_visitor_types_their_own_code(self):
        """The code proves the visitor holds the mailbox or the phone. A code
        the model produced from anywhere else — a guess, an earlier message, a
        tool payload — proves nothing, and `verifier_code` cannot tell.
        """
        self.assertIn("vient de taper lui-même", self.prompt)

    def test_the_company_wide_scope_is_stated(self):
        """`statut_commande` and `statut_reparation` search on
        `commercial_partner_id`: the contact of a company sees the company's
        history. Unannounced, the model reads it as a leak and escalates, or
        worse, tells the visitor their data was mixed up with someone else's.
        """
        self.assertIn("société", self.prompt)

    # -- robustesse -------------------------------------------------------
    def test_a_brace_in_the_template_no_longer_costs_every_turn(self):
        """The prompt used to be `str.format`ted, so every brace in it was
        syntax: a JSON example for a tool — the one thing a prompt about tools
        invites — raised `KeyError` for every visitor, on every turn, before
        any API call had been made.
        """
        template = 'Exemple : {"ville": "namur"}\n\n%s\n\nFin : {}' % KNOWLEDGE_BASE_SLOT
        with patch.object(prompt_builder, "SYSTEM_TEMPLATE", template):
            prompt = build_system_prompt(self.env)
        self.assertIn('{"ville": "namur"}', prompt)
        self.assertIn("Fin : {}", prompt)
        self.assertIn(build_knowledge_base(self.env), prompt)

    def test_the_knowledge_base_still_lands_in_the_prompt(self):
        """The other half of the substitution: a slot nobody matches is not an
        error, it is a prompt shipped without a single shop policy in it.
        """
        self.assertEqual(SYSTEM_TEMPLATE.count(KNOWLEDGE_BASE_SLOT), 1)
        self.assertNotIn(KNOWLEDGE_BASE_SLOT, self.prompt)
        self.assertIn(build_knowledge_base(self.env), self.prompt)
