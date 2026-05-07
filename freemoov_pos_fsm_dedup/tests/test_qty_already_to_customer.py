from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestQtyAlreadyToCustomer(TransactionCase):
    """Unit tests for sale.order.line._freemoov_qty_already_to_customer.

    The helper is the single source of truth used by both the POS-side and FSM-side
    overrides. If it stays correct, the dedup behaviour stays correct.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create({
            "name": "Test trotinette",
            "type": "product",
            "list_price": 1000.0,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Test partner"})
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.env.company.id)], limit=1)
        cls.stock_loc = cls.warehouse.lot_stock_id
        cls.customer_loc = cls.env.ref("stock.stock_location_customers")
        cls.env["stock.quant"]._update_available_quantity(cls.product, cls.stock_loc, 50.0)

        cls.so = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "order_line": [(0, 0, {
                "product_id": cls.product.id,
                "product_uom_qty": 1.0,
                "price_unit": 1000.0,
            })],
        })
        cls.so.action_confirm()
        cls.sol = cls.so.order_line[0]

    def _make_done_move(self, qty, picking=None):
        move = self.env["stock.move"].create({
            "name": self.product.name,
            "product_id": self.product.id,
            "product_uom": self.product.uom_id.id,
            "product_uom_qty": qty,
            "location_id": self.stock_loc.id,
            "location_dest_id": self.customer_loc.id,
            "sale_line_id": self.sol.id if not picking else False,
            "picking_id": picking.id if picking else False,
        })
        move._action_confirm()
        move._action_assign()
        move.quantity = qty
        move.picked = True
        move._action_done()
        return move

    def test_zero_when_no_moves(self):
        self.assertEqual(self.sol._freemoov_qty_already_to_customer(), 0.0)

    def test_aggregates_done_move_linked_via_sale_line_id(self):
        self._make_done_move(1.0)
        self.assertEqual(self.sol._freemoov_qty_already_to_customer(), 1.0)

    def test_ignores_cancelled_moves(self):
        move = self.env["stock.move"].create({
            "name": self.product.name,
            "product_id": self.product.id,
            "product_uom": self.product.uom_id.id,
            "product_uom_qty": 1.0,
            "location_id": self.stock_loc.id,
            "location_dest_id": self.customer_loc.id,
            "sale_line_id": self.sol.id,
        })
        move._action_cancel()
        self.assertEqual(self.sol._freemoov_qty_already_to_customer(), 0.0)

    def test_ignores_internal_moves(self):
        internal_loc = self.env["stock.location"].search([("usage", "=", "internal")], limit=1)
        self.env["stock.move"].create({
            "name": self.product.name,
            "product_id": self.product.id,
            "product_uom": self.product.uom_id.id,
            "product_uom_qty": 1.0,
            "location_id": self.stock_loc.id,
            "location_dest_id": internal_loc.id,
            "sale_line_id": self.sol.id,
        })
        self.assertEqual(self.sol._freemoov_qty_already_to_customer(), 0.0)

    def test_does_not_double_count_same_move(self):
        """A move that's both linked via sale_line_id AND visible through a pos_order_line
        on this SOL should be counted only once.
        """
        self._make_done_move(1.0)
        self.assertEqual(self.sol._freemoov_qty_already_to_customer(), 1.0)
