import json

from odoo.tests import tagged

from ..services import tools
from ..services.tools.catalog import _WAREHOUSE_MAP_PARAM
from .common import FreemoovAiCase


@tagged("post_install", "-at_install", "freemoov_ai")
class TestPublicTools(FreemoovAiCase):
    def _pin_warehouses(self, mapping):
        """Freeze the store -> warehouse mapping so tests never depend on the
        warehouses that happen to exist in the database."""
        self.env["ir.config_parameter"].sudo().set_param(
            _WAREHOUSE_MAP_PARAM, json.dumps(mapping)
        )

    def _storable(self, name, **values):
        return self.env["product.template"].create(dict({
            "name": name,
            "list_price": 800.0,
            "detailed_type": "product",
            "is_published": True,
            "sale_ok": True,
        }, **values))

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

    def test_dispo_per_store_aggregates_variants(self):
        # Warehouse names deliberately unrelated to the localities: the payload
        # keys must come from website._STORES, never from the warehouse names.
        wh_a = self.env["stock.warehouse"].create({"name": "Entrepot AI A", "code": "AIA"})
        wh_b = self.env["stock.warehouse"].create({"name": "Entrepot AI B", "code": "AIB"})
        self._pin_warehouses({"liege": wh_a.id, "namur": wh_b.id, "charleroi": None})
        # The site sells from a third warehouse, so the `commandable is False`
        # asserted below holds by construction rather than by accident.
        website = self.env["website"].sudo().get_current_website()
        website.warehouse_id = self.env["stock.warehouse"].create(
            {"name": "Entrepot AI Web", "code": "AIW"}).id

        attribute = self.env["product.attribute"].create({
            "name": "Couleur AI",
            "create_variant": "always",
            "value_ids": [(0, 0, {"name": "Noir AI"}), (0, 0, {"name": "Blanc AI"})],
        })
        tmpl = self._storable(
            "Multi Variant AI",
            allow_out_of_stock_order=False,
            attribute_line_ids=[(0, 0, {
                "attribute_id": attribute.id,
                "value_ids": [(6, 0, attribute.value_ids.ids)],
            })],
        )
        self.assertEqual(len(tmpl.product_variant_ids), 2)

        Quant = self.env["stock.quant"].sudo()
        Quant._update_available_quantity(tmpl.product_variant_ids[0], wh_a.lot_stock_id, 3)
        # Stock on the SECOND variant only: reading product_variant_ids[:1]
        # would wrongly report Namur empty.
        Quant._update_available_quantity(tmpl.product_variant_ids[1], wh_b.lot_stock_id, 5)

        res = tools.run_tool(self.env, self.channel, "fiche_produit", {"product_id": tmpl.id})
        # Charleroi has no warehouse: null, not 0 — untracked is not out of stock.
        self.assertEqual(res["dispo"], {"Liège": 3, "Namur": 5, "Charleroi": None})
        # The two semantics diverge here, and that is the point: 8 units sit in
        # the shops, none in the website warehouse, so the site refuses the
        # online order while the visitor can still collect in store.
        self.assertIs(res["commandable"], False)

    def test_commandable_without_stock(self):
        wh = self.env["stock.warehouse"].create({"name": "Entrepot AI C", "code": "AIC"})
        self._pin_warehouses({"liege": wh.id, "namur": None, "charleroi": None})

        sellable = self._storable("Precommande AI", allow_out_of_stock_order=True)
        res = tools.run_tool(self.env, self.channel, "fiche_produit", {"product_id": sellable.id})
        self.assertEqual(res["dispo"], {"Liège": 0, "Namur": None, "Charleroi": None})
        self.assertIs(res["commandable"], True)

        # Control: same product without the flag is genuinely not orderable.
        blocked = self._storable("Rupture AI", allow_out_of_stock_order=False)
        res = tools.run_tool(self.env, self.channel, "fiche_produit", {"product_id": blocked.id})
        self.assertIs(res["commandable"], False)

    def test_commandable_follows_site_sale_gate(self):
        """`commandable` mirrors the real sale gate, not a display badge.

        website_sale_stock refuses the cart line when free_qty in the website's
        own warehouse is short (sale_order._verify_updated_quantity), so a unit
        already reserved by an open order is NOT sellable online — even though
        the `get_stock_availability` badge, which sums on-hand quants, still
        shows the product as available.
        """
        wh = self.env["stock.warehouse"].create({"name": "Entrepot AI D", "code": "AID"})
        self._pin_warehouses({"liege": wh.id, "namur": None, "charleroi": None})
        website = self.env["website"].sudo().get_current_website()
        website.warehouse_id = wh.id

        tmpl = self._storable("Reserve AI", allow_out_of_stock_order=False)
        self.env["stock.quant"].sudo()._update_available_quantity(
            tmpl.product_variant_ids, wh.lot_stock_id, quantity=1, reserved_quantity=1,
        )

        res = tools.run_tool(self.env, self.channel, "fiche_produit", {"product_id": tmpl.id})
        self.assertEqual(res["dispo"]["Liège"], 0)
        self.assertIs(res["commandable"], False)

        # Same stock situation, but the product accepts out-of-stock orders:
        # the site takes the order, so the bot must not refuse it.
        tmpl.allow_out_of_stock_order = True
        res = tools.run_tool(self.env, self.channel, "fiche_produit", {"product_id": tmpl.id})
        self.assertIs(res["commandable"], True)

    def test_commandable_with_one_oversold_variant(self):
        """One oversold sibling must not hide a variant that is in stock.

        The site adds a specific variant to the cart, so it happily sells the
        healthy one while another sits at a negative free_qty. Summing the
        variants would net out to -2 here and refuse that sale.
        """
        wh = self.env["stock.warehouse"].create({"name": "Entrepot AI E", "code": "AIE"})
        self._pin_warehouses({"liege": wh.id, "namur": None, "charleroi": None})
        website = self.env["website"].sudo().get_current_website()
        website.warehouse_id = wh.id

        attribute = self.env["product.attribute"].create({
            "name": "Taille AI",
            "create_variant": "always",
            "value_ids": [(0, 0, {"name": "S AI"}), (0, 0, {"name": "M AI"})],
        })
        tmpl = self._storable(
            "Survente AI",
            allow_out_of_stock_order=False,
            attribute_line_ids=[(0, 0, {
                "attribute_id": attribute.id,
                "value_ids": [(6, 0, attribute.value_ids.ids)],
            })],
        )
        Quant = self.env["stock.quant"].sudo()
        Quant._update_available_quantity(tmpl.product_variant_ids[0], wh.lot_stock_id, quantity=3)
        Quant._update_available_quantity(tmpl.product_variant_ids[1], wh.lot_stock_id, quantity=-5)

        res = tools.run_tool(self.env, self.channel, "fiche_produit", {"product_id": tmpl.id})
        self.assertIs(res["commandable"], True)

    def test_store_warehouse_map_tolerates_garbage(self):
        """A misconfigured parameter degrades to 'untracked', never raises:
        the exception would surface in the middle of a visitor conversation."""
        for raw in ('{"liege": "wh_liege"}', "not json at all", '{"liege": 999999999}',
                    "3", "[]"):
            self.env["ir.config_parameter"].sudo().set_param(_WAREHOUSE_MAP_PARAM, raw)
            res = tools.run_tool(self.env, self.channel, "chercher_produits", {})
            self.assertIn("produits", res)

        self.env["ir.config_parameter"].sudo().set_param(
            _WAREHOUSE_MAP_PARAM, '{"liege": "wh_liege"}')
        tmpl = self._storable("Garbage Param AI")
        res = tools.run_tool(self.env, self.channel, "fiche_produit", {"product_id": tmpl.id})
        self.assertIsNone(res["dispo"]["Liège"])

    def test_chercher_produits_limit_and_note(self):
        for index in range(7):
            self._storable("Limite AI %s" % index, list_price=100.0 + index)
        res = tools.run_tool(self.env, self.channel, "chercher_produits",
                             {"recherche": "Limite AI"})
        self.assertEqual(len(res["produits"]), 5)
        self.assertTrue(res["note"])
        self.assertIn("commandable", res["produits"][0])
