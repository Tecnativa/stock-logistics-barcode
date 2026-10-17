# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestStockBarcodes(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("base.user_admin").group_ids = [
            Command.link(cls.env.ref("stock.group_production_lot").id)
        ]
        cls.stock = cls.env.ref("stock.warehouse0").lot_stock_id
        customers = cls.env.ref("stock.stock_location_customers")
        Product = cls.env["product.product"]
        cls.product = Product.create(
            {"name": "Tour product", "is_storable": True, "barcode": "1234567890128"}
        )
        cls.product_lot = Product.create(
            {
                "name": "Tour lot product",
                "is_storable": True,
                "tracking": "lot",
                "barcode": "2345678901234",
            }
        )
        cls.lot = cls.env["stock.lot"].create(
            {"name": "TOUR-LOT", "product_id": cls.product_lot.id}
        )
        Quant = cls.env["stock.quant"]
        Quant._update_available_quantity(cls.product, cls.stock, 10)
        Quant._update_available_quantity(cls.product_lot, cls.stock, 10, lot_id=cls.lot)
        cls.picking = cls.env["stock.picking"].create(
            {
                "picking_type_id": cls.env.ref("stock.picking_type_out").id,
                "location_id": cls.stock.id,
                "location_dest_id": customers.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": 3,
                            "location_id": cls.stock.id,
                            "location_dest_id": customers.id,
                        }
                    )
                    for product in (cls.product, cls.product_lot)
                ],
            }
        )
        cls.picking.action_confirm()
        cls.picking.action_assign()

    def test_open_barcode_screen(self):
        action = self.picking.action_barcode_scan()
        session = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(session._capture_document(), self.picking)
        self.assertEqual(
            action["views"],
            [
                (
                    self.env.ref("stock_barcodes.stock_capture_session_view_form").id,
                    "form",
                )
            ],
        )
        self.assertEqual(action["path"], "barcode-reader")

    def test_open_batch(self):
        batch = self.env["stock.picking.batch"].create(
            {"picking_ids": [Command.set(self.picking.ids)]}
        )
        batch.action_confirm()
        action = batch.action_capture_open()
        self.assertEqual(action["path"], "barcode-reader")
        session = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(len(session.card_line_ids), 2)

    def test_main_menu(self):
        tiles = self.env["stock.barcodes.action"].get_main_menu()
        deliveries = next(t for t in tiles if t["name"] == "Deliveries")
        self.assertGreaterEqual(deliveries["count"], 1)
        action = (
            self.env["stock.barcodes.action"].browse(deliveries["id"]).open_action()
        )
        self.assertEqual(action["res_model"], "stock.picking.type")
        self.assertTrue(action["context"]["search_default_capture_outgoing"])
        inventory = self.env.ref("stock_barcodes.stock_barcodes_action_inventory")
        action = inventory.open_action()
        session = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(session._capture_document(), self.stock)

    def test_action_barcode(self):
        inventory = self.env.ref("stock_barcodes.stock_barcodes_action_inventory")
        inventory.barcode = "MENU-INVENTORY"
        action = self.env["stock.barcodes.action"].open_by_barcode("MENU-INVENTORY")
        self.assertEqual(action["res_model"], "stock.capture.session")
        self.assertFalse(self.env["stock.barcodes.action"].open_by_barcode("NOPE"))

    def test_scan_tour(self):
        admin = self.env.ref("base.user_admin")
        session_id = self.picking.with_user(admin).action_barcode_scan()["res_id"]
        self.start_tour(
            f"/odoo/barcode-reader/{session_id}", "stock_barcodes_scan", login="admin"
        )
        self.assertEqual(self.picking.state, "done")
        move = self.picking.move_ids.filtered(lambda m: m.product_id == self.product)
        self.assertEqual(move.quantity, 3)
        move_lot = self.picking.move_ids - move
        self.assertEqual(move_lot.quantity, 1)
        self.assertEqual(move_lot.move_line_ids.lot_id, self.lot)
        backorder = self.env["stock.picking"].search(
            [("backorder_id", "=", self.picking.id)]
        )
        self.assertEqual(backorder.move_ids.product_uom_qty, 2)
