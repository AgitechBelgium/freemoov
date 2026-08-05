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
        # assertRaisesRegex, not assertRaises: an unregistered tool also raises
        # ToolError, which would make this test pass for the wrong reason.
        with self.assertRaisesRegex(tools.ToolError, "introuvable"):
            tools.run_tool(self.env, self.channel, "fiche_produit", {"product_id": tmpl.id})
