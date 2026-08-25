from odoo.tests import TransactionCase, tagged
from odoo.tools import float_compare


@tagged("post_install", "-at_install")
class TestPosPickingDedup(TransactionCase):
    """End-to-end-ish tests for the POS picking creation when a SOL was already delivered.

    These do not run the JS POS UI — they hit the Python entry point
    `_create_picking_from_pos_order_lines` that the POS server-side calls when an
    order is paid.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create({
            "name": "Trotinette",
            "type": "product",
            "list_price": 1000.0,
        })
        cls.casque = cls.env["product.product"].create({
            "name": "Casque",
            "type": "product",
            "list_price": 50.0,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Buyer"})
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.env.company.id)], limit=1)
        cls.env["stock.quant"]._update_available_quantity(cls.product, cls.warehouse.lot_stock_id, 100.0)
        cls.env["stock.quant"]._update_available_quantity(cls.casque, cls.warehouse.lot_stock_id, 100.0)

        # Sur une base neuve avec compta anglo-saxonne (plan générique des CI),
        # le POS passe par défaut en "update stock at closing" et
        # _create_order_picking ne crée aucun picking par commande — or c'est ce
        # flux temps réel que le module dédoublonne. La session fige
        # update_stock_at_closing à sa création depuis le champ company.
        cls.env.company.point_of_sale_update_stock_quantities = "real"

        cls.config = cls.env["pos.config"].search([("active", "=", True)], limit=1)
        if not cls.config:
            cls.config = cls.env["pos.config"].create({"name": "Test config"})
        cls.config.open_ui()
        cls.session = cls.config.current_session_id
        # Une session ouverte avant ce setUp (base recyclée) garderait l'ancien
        # mode : on aligne son flag sur la config temps réel.
        cls.session.update_stock_at_closing = False

    def _make_so_with_fsm_done(self, qty=1.0):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": qty,
                "price_unit": 1000.0,
            })],
        })
        so.action_confirm()
        sol = so.order_line[0]
        # Simulate FSM done by validating the auto-created delivery picking
        for picking in so.picking_ids:
            for move in picking.move_ids:
                move.quantity = move.product_uom_qty
                move.picked = True
            picking.button_validate()
        return so, sol

    def _make_pos_order(self, sol, qty, partner=None, extra_lines=None):
        partner = partner or self.partner
        line_vals = [{
            "product_id": sol.product_id.id,
            "qty": qty,
            "price_unit": 1000.0,
            "price_subtotal": 1000.0 * qty,
            "price_subtotal_incl": 1000.0 * qty,
            "sale_order_line_id": sol.id,
        }]
        if extra_lines:
            line_vals.extend(extra_lines)
        order = self.env["pos.order"].create({
            "session_id": self.session.id,
            "partner_id": partner.id,
            "amount_tax": 0.0,
            "amount_total": sum(l["price_subtotal_incl"] for l in line_vals),
            "amount_paid": sum(l["price_subtotal_incl"] for l in line_vals),
            "amount_return": 0.0,
            "lines": [(0, 0, lv) for lv in line_vals],
        })
        return order

    def _customer_done_qty(self, product, sale_line=None, pos_order=None):
        """Sum done qty going to customer for a given product, scoped to a SO line or POS order."""
        domain = [("state", "=", "done"), ("product_id", "=", product.id), ("location_dest_id.usage", "=", "customer")]
        if sale_line:
            domain.append(("sale_line_id", "=", sale_line.id))
        moves = self.env["stock.move"].search(domain)
        total = sum(m.product_uom._compute_quantity(m.quantity, product.uom_id) for m in moves)
        if pos_order:
            for picking in pos_order.picking_ids:
                for m in picking.move_ids:
                    if m.state == "done" and m.product_id == product and m.location_dest_id.usage == "customer":
                        total += m.product_uom._compute_quantity(m.quantity, product.uom_id)
        return total

    def test_full_match_pos_creates_no_picking_for_already_delivered_line(self):
        so, sol = self._make_so_with_fsm_done(qty=1.0)
        self.assertEqual(sol._freemoov_qty_already_to_customer(), 1.0)

        order = self._make_pos_order(sol, qty=1.0)
        order._create_order_picking()

        moves = order.picking_ids.move_ids.filtered(lambda m: m.product_id == self.product)
        self.assertFalse(moves, "POS should not create any move for the trotinette already delivered via FSM")

    def test_pos_picking_only_contains_extra_products(self):
        so, sol = self._make_so_with_fsm_done(qty=1.0)
        order = self._make_pos_order(sol, qty=1.0, extra_lines=[{
            "product_id": self.casque.id,
            "qty": 1.0,
            "price_unit": 50.0,
            "price_subtotal": 50.0,
            "price_subtotal_incl": 50.0,
        }])
        order._create_order_picking()

        trotinette_moves = order.picking_ids.move_ids.filtered(lambda m: m.product_id == self.product)
        casque_moves = order.picking_ids.move_ids.filtered(lambda m: m.product_id == self.casque)
        self.assertFalse(trotinette_moves)
        self.assertEqual(len(casque_moves), 1)
        self.assertEqual(casque_moves.product_uom_qty, 1.0)

    def test_pos_partial_delta_when_qty_increased_at_counter(self):
        """SO=1 trotinette, FSM delivers 1, customer pays for 2 at the counter (takes 1 more).
        The POS picking should ship the missing 1 unit, not 2.
        """
        so, sol = self._make_so_with_fsm_done(qty=1.0)
        order = self._make_pos_order(sol, qty=2.0)
        order._create_order_picking()

        moves = order.picking_ids.move_ids.filtered(lambda m: m.product_id == self.product)
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.product_uom_qty, 1.0,
                         "POS move must ship only the delta (2 wanted - 1 already delivered = 1)")

    def test_total_customer_qty_equals_what_customer_received(self):
        so, sol = self._make_so_with_fsm_done(qty=1.0)
        order = self._make_pos_order(sol, qty=1.0)
        order._create_order_picking()

        total = self._customer_done_qty(self.product, sale_line=sol, pos_order=order)
        self.assertEqual(total, 1.0,
                         "Across FSM and POS pickings, total qty to customer must equal what was actually delivered (1)")

    def test_no_sale_link_falls_through_to_native(self):
        """Standalone POS sale (no sale_order_line_id) must keep its picking + move untouched."""
        order = self.env["pos.order"].create({
            "session_id": self.session.id,
            "partner_id": self.partner.id,
            "amount_tax": 0.0,
            "amount_total": 50.0,
            "amount_paid": 50.0,
            "amount_return": 0.0,
            "lines": [(0, 0, {
                "product_id": self.casque.id,
                "qty": 1.0,
                "price_unit": 50.0,
                "price_subtotal": 50.0,
                "price_subtotal_incl": 50.0,
            })],
        })
        order._create_order_picking()
        casque_moves = order.picking_ids.move_ids.filtered(lambda m: m.product_id == self.casque)
        self.assertEqual(len(casque_moves), 1)
        self.assertEqual(casque_moves.product_uom_qty, 1.0)

    def test_refund_line_is_not_skipped(self):
        """Negative qty (refund) must always create its picking — refunds are unrelated to FSM."""
        so, sol = self._make_so_with_fsm_done(qty=1.0)
        order = self.env["pos.order"].create({
            "session_id": self.session.id,
            "partner_id": self.partner.id,
            "amount_tax": 0.0,
            "amount_total": -1000.0,
            "amount_paid": -1000.0,
            "amount_return": 0.0,
            "lines": [(0, 0, {
                "product_id": self.product.id,
                "qty": -1.0,
                "price_unit": 1000.0,
                "price_subtotal": -1000.0,
                "price_subtotal_incl": -1000.0,
                "sale_order_line_id": sol.id,
            })],
        })
        order._create_order_picking()
        moves = order.picking_ids.move_ids.filtered(lambda m: m.product_id == self.product)
        self.assertEqual(len(moves), 1, "Refund must produce its own move")
