# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestStockCaptureScan(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.stock_location = cls.env.ref("stock.warehouse0").lot_stock_id
        cls.shelf = cls.env["stock.location"].create(
            {
                "name": "Capture shelf",
                "barcode": "CAPTURE-SHELF",
                "location_id": cls.stock_location.id,
            }
        )
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.kg = cls.env.ref("uom.product_uom_kgm")
        Product = cls.env["product.product"]
        cls.product = Product.create(
            {"name": "Scanned", "is_storable": True, "barcode": "1234567890128"}
        )
        cls.product_lot = Product.create(
            {
                "name": "Scanned lot",
                "is_storable": True,
                "tracking": "lot",
                "barcode": "2345678901234",
            }
        )
        cls.product_kg = Product.create(
            {
                "name": "Scanned kg",
                "is_storable": True,
                "uom_id": cls.kg.id,
                "barcode": "08412345678905",
            }
        )
        cls.lot = cls.env["stock.lot"].create(
            {"name": "SCAN-LOT", "product_id": cls.product_lot.id}
        )
        Quant = cls.env["stock.quant"]
        Quant._update_available_quantity(cls.product, cls.stock_location, 30)
        Quant._update_available_quantity(cls.product, cls.shelf, 5)
        Quant._update_available_quantity(
            cls.product_lot, cls.stock_location, 10, lot_id=cls.lot
        )
        Quant._update_available_quantity(cls.product_kg, cls.stock_location, 50)

    def _create_delivery(self, products, quantity=10.0):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_out.id,
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "uom_id": product.uom_id.id,
                            "product_uom_qty": quantity,
                            "location_id": self.stock_location.id,
                            "location_dest_id": self.customer_location.id,
                        }
                    )
                    for product in products
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        return picking

    def _scan(self, picking, *barcodes):
        """Read barcodes as a screen does, keeping the values between them"""
        scan_values = {}
        for barcode in barcodes:
            result = picking.capture_scan(barcode, scan_values)
            scan_values = result["scan_values"]
        return result

    def _move(self, picking, product):
        return picking.move_ids.filtered(lambda move: move.product_id == product)

    def test_scan_product(self):
        picking = self._create_delivery(self.product)
        result = self._scan(picking, "1234567890128")
        self.assertEqual(result["message_type"], "success")
        move = self._move(picking, self.product)
        self.assertEqual(move.captured_quantity, 1)
        self.assertEqual(move.capture_state, "capturing")
        line = self.env["stock.move.line"].browse(result["line_ids"])
        self.assertEqual(line.capture_user_id, self.env.user)
        self.assertTrue(line.capture_date)
        self._scan(picking, "1234567890128")
        self.assertEqual(move.move_line_ids.filtered("picked").quantity, 2)

    def test_scan_packaging(self):
        pack = self.env["uom.uom"].create(
            {
                "name": "Pack of 6",
                "relative_factor": 6,
                "relative_uom_id": self.unit.id,
            }
        )
        self.env["product.uom"].create(
            {
                "product_id": self.product.id,
                "uom_id": pack.id,
                "barcode": "CAPTURE-PACK6",
            }
        )
        picking = self._create_delivery(self.product)
        self._scan(picking, "CAPTURE-PACK6")
        self.assertEqual(self._move(picking, self.product).captured_quantity, 6)

    def test_scan_lot_after_product(self):
        picking = self._create_delivery(self.product_lot)
        result = self._scan(picking, "2345678901234")
        self.assertEqual(result["message_type"], "warning")
        self.assertEqual(result["scan_values"]["product_id"], self.product_lot.id)
        result = picking.capture_scan("SCAN-LOT", result["scan_values"])
        self.assertEqual(result["message_type"], "success")
        line = self.env["stock.move.line"].browse(result["line_ids"])
        self.assertEqual(line.lot_id, self.lot)
        self.assertEqual(line.quantity, 1)

    def test_scan_lot_alone(self):
        picking = self._create_delivery(self.product_lot)
        result = self._scan(picking, "SCAN-LOT")
        line = self.env["stock.move.line"].browse(result["line_ids"])
        self.assertEqual(line.product_id, self.product_lot)
        self.assertEqual(line.lot_id, self.lot)

    def test_scan_location_then_products(self):
        picking = self._create_delivery(self.product)
        result = self._scan(picking, "CAPTURE-SHELF", "1234567890128")
        line = self.env["stock.move.line"].browse(result["line_ids"])
        self.assertEqual(line.location_id, self.shelf)
        # The location is kept for the next products
        self.assertEqual(result["scan_values"], {"location_id": self.shelf.id})

    def test_scan_gs1(self):
        self.env.company.nomenclature_id = self.env.ref(
            "barcodes_gs1_nomenclature.default_gs1_nomenclature"
        )
        picking = self._create_delivery(self.product_kg)
        # GTIN, net weight of 12.5 kg
        self._scan(picking, "01084123456789053102001250")
        self.assertEqual(self._move(picking, self.product_kg).captured_quantity, 12.5)

    def test_scan_package_content(self):
        package = self.env["stock.package"].create({"name": "SCAN-PACK"})
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.stock_location, 4, package_id=package
        )
        picking = self._create_delivery(self.product)
        result = self._scan(picking, "SCAN-PACK")
        line = self.env["stock.move.line"].browse(result["line_ids"])
        self.assertEqual(line.package_id, package)
        self.assertEqual(line.result_package_id, package)
        self.assertEqual(line.quantity, 4)

    def test_scan_unknown(self):
        picking = self._create_delivery(self.product)
        result = self._scan(picking, "NOT-A-BARCODE")
        self.assertEqual(result["message_type"], "danger")
        self.assertFalse(result["line_ids"])

    def test_capture_state_and_lock(self):
        picking = self._create_delivery(self.product, quantity=2)
        move = self._move(picking, self.product)
        self.assertEqual(move.capture_state, "to_capture")
        self._scan(picking, "1234567890128", "1234567890128")
        self.assertEqual(move.capture_state, "captured")
        move._capture_lock()
        other_user = new_test_user(
            self.env, login="capture_other", groups="stock.group_stock_user"
        )
        self.assertTrue(move.with_user(other_user).is_capture_locked)
        with self.assertRaises(UserError):
            move.with_user(other_user)._capture_lock()
        move._capture_unlock()
        self.assertFalse(move.with_user(other_user).is_capture_locked)

    def test_scan_display(self):
        picking = self._create_delivery(self.product_lot)
        result = self._scan(picking, "2345678901234")
        self.assertEqual(
            result["scan_display"]["product_id"], self.product_lot.display_name
        )

    def test_capture_remaining_and_undo(self):
        picking = self._create_delivery(self.product | self.product_kg)
        move = self._move(picking, self.product)
        self._scan(picking, "1234567890128")
        picking.move_ids.action_capture_remaining()
        self.assertEqual(move.captured_quantity, 10)
        self.assertEqual(self._move(picking, self.product_kg).captured_quantity, 10)
        self.assertEqual(set(picking.move_ids.mapped("capture_state")), {"captured"})
        picking.move_ids.action_capture_undo()
        self.assertEqual(set(picking.move_ids.mapped("captured_quantity")), {0})
        self.assertEqual(sum(move.move_line_ids.mapped("quantity")), 10)
