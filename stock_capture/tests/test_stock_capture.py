# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import Command
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockCapture(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.stock_location = cls.env.ref("stock.warehouse0").lot_stock_id
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")
        cls.Quant = cls.env["stock.quant"]
        cls.product = cls.env["product.product"].create(
            {"name": "Captured product", "is_storable": True}
        )
        cls.product_lot = cls.env["product.product"].create(
            {"name": "Captured lot product", "is_storable": True, "tracking": "lot"}
        )
        cls.lot_a = cls.env["stock.lot"].create(
            {"name": "CAPTURE-A", "product_id": cls.product_lot.id}
        )
        cls.lot_b = cls.env["stock.lot"].create(
            {"name": "CAPTURE-B", "product_id": cls.product_lot.id}
        )
        cls.Quant._update_available_quantity(cls.product, cls.stock_location, 15.0)
        cls.Quant._update_available_quantity(
            cls.product_lot, cls.stock_location, 10.0, lot_id=cls.lot_a
        )
        cls.Quant._update_available_quantity(
            cls.product_lot, cls.stock_location, 10.0, lot_id=cls.lot_b
        )

    def _create_delivery(self, product=None, quantity=10.0):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_out.id,
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": (product or self.product).id,
                            "product_uom_qty": quantity,
                            "location_id": self.stock_location.id,
                            "location_dest_id": self.customer_location.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        return picking

    def _reserved(self, product, lot=None):
        return sum(
            self.Quant._gather(
                product, self.stock_location, lot_id=lot, strict=True
            ).mapped("reserved_quantity")
        )

    def _lines(self, move, picked):
        return move.move_line_ids.filtered(lambda ml: ml.picked == picked)

    def _validate(self, picking):
        action = picking.button_validate()
        if isinstance(action, dict) and action.get("res_model"):
            self.assertEqual(action["res_model"], "stock.backorder.confirmation")
            Form(
                self.env[action["res_model"]].with_context(**action["context"])
            ).save().process_cancel_backorder()
        self.assertEqual(picking.state, "done")

    def test_capture_less_than_reserved_keeps_reservation(self):
        picking = self._create_delivery()
        move = picking.move_ids
        picking._capture_product(self.product, 3.0)
        self.assertEqual(self._lines(move, True).quantity, 3.0)
        self.assertEqual(self._lines(move, False).quantity, 7.0)
        self.assertEqual(self._reserved(self.product), 10.0)
        self.assertEqual(move.state, "assigned")
        picking._capture_product(self.product, 4.0)
        self.assertEqual(self._lines(move, True).quantity, 7.0)
        self.assertEqual(self._lines(move, False).quantity, 3.0)
        self.assertEqual(self._reserved(self.product), 10.0)
        self._validate(picking)
        self.assertEqual(move.quantity, 7.0)
        self.assertEqual(self.product.qty_available, 8.0)

    def test_capture_over_reserved(self):
        picking = self._create_delivery()
        move = picking.move_ids
        picking._capture_product(self.product, 12.0)
        self.assertEqual(self._lines(move, True).quantity, 12.0)
        self.assertFalse(self._lines(move, False))
        self.assertEqual(self._reserved(self.product), 12.0)
        self._validate(picking)
        self.assertEqual(self.product.qty_available, 3.0)

    def test_capture_other_lot_takes_reservation(self):
        picking = self._create_delivery(self.product_lot)
        move = picking.move_ids
        self.assertEqual(move.move_line_ids.lot_id, self.lot_a)
        picking._capture_product(self.product_lot, 4.0, lot=self.lot_b)
        captured = self._lines(move, True)
        self.assertEqual(captured.lot_id, self.lot_b)
        self.assertEqual(captured.quantity, 4.0)
        self.assertEqual(self._lines(move, False).quantity, 6.0)
        self.assertEqual(move.quantity, 10.0)
        self.assertEqual(self._reserved(self.product_lot, self.lot_a), 6.0)
        self.assertEqual(self._reserved(self.product_lot, self.lot_b), 4.0)

    def test_capture_in_packages(self):
        picking = self._create_delivery()
        move = picking.move_ids
        package_1 = self.env["stock.package"].create({"name": "CAPTURE-P1"})
        package_2 = self.env["stock.package"].create({"name": "CAPTURE-P2"})
        picking._capture_product(self.product, 3.0, result_package=package_1)
        picking._capture_product(self.product, 2.0, result_package=package_2)
        picking._capture_product(self.product, 1.0, result_package=package_1)
        captured = self._lines(move, True)
        self.assertEqual(
            {(ml.result_package_id, ml.quantity) for ml in captured},
            {(package_1, 4.0), (package_2, 2.0)},
        )
        self.assertEqual(self._lines(move, False).quantity, 4.0)
        self.assertEqual(self._reserved(self.product), 10.0)

    def test_undo_returns_to_reservation(self):
        picking = self._create_delivery()
        move = picking.move_ids
        line = picking._capture_product(self.product, 3.0)
        line._capture_undo(1.0)
        self.assertEqual(self._lines(move, True).quantity, 2.0)
        self.assertEqual(self._lines(move, False).quantity, 8.0)
        line._capture_undo()
        self.assertFalse(self._lines(move, True))
        self.assertEqual(self._lines(move, False).quantity, 10.0)
        self.assertEqual(self._reserved(self.product), 10.0)

    def test_undo_whole_reservation_unpicks_the_line(self):
        picking = self._create_delivery()
        move = picking.move_ids
        line = picking._capture_product(self.product, 10.0)
        line._capture_undo()
        self.assertEqual(move.move_line_ids, line)
        self.assertFalse(line.picked)
        self.assertEqual(self._reserved(self.product), 10.0)

    def test_undo_over_reserved_releases_the_excess(self):
        picking = self._create_delivery()
        move = picking.move_ids
        line = picking._capture_product(self.product, 12.0)
        line._capture_undo()
        self.assertFalse(self._lines(move, True))
        self.assertEqual(self._lines(move, False).quantity, 10.0)
        self.assertEqual(self._reserved(self.product), 10.0)

    def test_capture_spreads_over_the_moves_of_the_product(self):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_out.id,
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
                # Different descriptions, as two order lines of the same
                # product, keep Odoo from merging the moves
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": quantity,
                            "description_picking": description,
                            "location_id": self.stock_location.id,
                            "location_dest_id": self.customer_location.id,
                        }
                    )
                    for quantity, description in ((4.0, "First"), (6.0, "Second"))
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        move_1, move_2 = picking.move_ids
        self.assertEqual(move_1.product_uom_qty, 4.0)
        picking._capture_product(self.product, 7.0)
        self.assertEqual(self._lines(move_1, True).quantity, 4.0)
        self.assertEqual(self._lines(move_2, True).quantity, 3.0)
        picking._capture_product(self.product, 5.0)
        self.assertEqual(self._lines(move_2, True).quantity, 8.0)

    def test_capture_product_not_in_the_transfer(self):
        picking = self._create_delivery()
        line = picking._capture_product(self.product_lot, 2.0, lot=self.lot_b)
        self.assertEqual(line.move_id.picking_id, picking)
        self.assertEqual(line.move_id.product_id, self.product_lot)
        self.assertTrue(line.picked)
        self.assertEqual(line.quantity, 2.0)
        self.assertEqual(self._reserved(self.product_lot, self.lot_b), 2.0)

    def test_capture_without_merge(self):
        picking = self._create_delivery()
        move = picking.move_ids
        line_1 = picking._capture_product(self.product, 3.0, merge=False)
        line_2 = picking._capture_product(self.product, 2.0, merge=False)
        self.assertNotEqual(line_1, line_2)
        self.assertEqual(sorted(self._lines(move, True).mapped("quantity")), [2.0, 3.0])
        self.assertEqual(self._lines(move, False).quantity, 5.0)
        self.assertEqual(self._reserved(self.product), 10.0)
        # Over the reservation, a capture still gets a single line
        line_3 = picking._capture_product(self.product, 7.0, merge=False)
        self.assertEqual(line_3.quantity, 7.0)
        self.assertFalse(self._lines(move, False))
        self.assertEqual(self._reserved(self.product), 12.0)

    def test_set_quantity_on_a_line(self):
        picking = self._create_delivery()
        move = picking.move_ids
        line = move.move_line_ids
        line._capture_set_quantity(8.5)
        self.assertTrue(line.picked)
        self.assertEqual(line.quantity, 8.5)
        self.assertEqual(self._lines(move, False).quantity, 1.5)
        line._capture_set_quantity(9.0)
        self.assertEqual(line.quantity, 9.0)
        self.assertEqual(self._lines(move, False).quantity, 1.0)
        line._capture_set_quantity(11.0)
        self.assertEqual(line.quantity, 11.0)
        self.assertFalse(self._lines(move, False))
        self.assertEqual(self._reserved(self.product), 11.0)
        line._capture_set_quantity(7.0)
        self.assertEqual(line.quantity, 7.0)
        self.assertEqual(self._lines(move, False).quantity, 3.0)
        self.assertEqual(self._reserved(self.product), 10.0)
        self.assertFalse(line._capture_set_quantity(0.0))
        # The capture goes back to the reservation of the same goods
        self.assertFalse(line.exists())
        self.assertEqual(move.move_line_ids.mapped("quantity"), [10.0])
        self.assertFalse(move.move_line_ids.picked)
        self.assertEqual(self._reserved(self.product), 10.0)

    def test_set_quantity_partially_and_back(self):
        """A partial capture split from its line joins it again when it is
        captured for less or undone"""
        picking = self._create_delivery()
        move = picking.move_ids
        line = move.move_line_ids
        line._capture_set_quantity(4.0)
        rest = self._lines(move, False)
        self.assertEqual(rest.quantity, 6.0)
        line._capture_set_quantity(3.0)
        self.assertEqual(line.quantity, 3.0)
        self.assertEqual(rest.quantity, 7.0)
        self.assertEqual(move.move_line_ids, line | rest)
        line.action_capture_undo()
        self.assertFalse(line.exists())
        self.assertEqual(move.move_line_ids, rest)
        self.assertEqual(rest.quantity, 10.0)
        self.assertFalse(rest.picked)
