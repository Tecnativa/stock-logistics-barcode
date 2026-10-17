# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from ..hooks import _capture_read_quantities


@tagged("post_install", "-at_install")
class TestStockCaptureSession(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.env.user.group_ids |= cls.env.ref("stock.group_production_lot") | (
            cls.env.ref("stock.group_tracking_lot")
        )
        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.shelf = cls.env["stock.location"].create(
            {
                "name": "Capture shelf",
                "barcode": "CAPTURE-SHELF",
                "location_id": cls.stock_location.id,
            }
        )
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")
        cls.picking_type_in = cls.env.ref("stock.picking_type_in")
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.kg = cls.env.ref("uom.product_uom_kgm")
        Product = cls.env["product.product"]
        cls.product = Product.create(
            {"name": "Scanned", "is_storable": True, "barcode": "1234567890128"}
        )
        cls.product2 = Product.create(
            {"name": "Scanned 2", "is_storable": True, "barcode": "CAPTURE-P2"}
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
        Quant._update_available_quantity(cls.product2, cls.stock_location, 30)
        Quant._update_available_quantity(
            cls.product_lot, cls.stock_location, 10, lot_id=cls.lot
        )
        Quant._update_available_quantity(cls.product_kg, cls.stock_location, 50)
        cls.delivery_profile = cls.env.ref(
            "stock_capture.stock_capture_profile_delivery"
        )

    @classmethod
    def _create_profile(cls, steps, **values):
        """Profile with the steps given as (step, field, options)"""
        return cls.env["stock.capture.profile"].create(
            dict(
                values,
                name="Test profile",
                field_ids=[
                    Command.create(
                        dict(
                            name=field_name,
                            step=step,
                            field_name=field_name,
                            **{option: True for option in options.split()},
                        )
                    )
                    for step, field_name, options in steps
                ],
            )
        )

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

    def _open(self, document, profile=None):
        """Open the capture screen as the buttons of the documents do"""
        action = document.action_capture_open(profile=profile)
        return self.env[action["res_model"]].browse(action["res_id"])

    def _scan(self, session, *barcodes):
        for barcode in barcodes:
            result = session.capture_barcode(barcode)
        return result

    def _move(self, picking, product):
        return picking.move_ids.filtered(lambda move: move.product_id == product)

    def test_scan_product(self):
        picking = self._create_delivery(self.product)
        session = self._open(picking)
        self.assertEqual(session.profile_id, self.delivery_profile)
        self.assertEqual(session.location_id, self.stock_location)
        result = self._scan(session, "1234567890128")
        self.assertEqual(result["message_type"], "success")
        self.assertEqual(result["sound"], "ok")
        move = self._move(picking, self.product)
        self.assertEqual(move.captured_quantity, 1)
        self.assertEqual(move.capture_state, "capturing")
        self._scan(session, "1234567890128")
        self.assertEqual(move.move_line_ids.filtered("picked").quantity, 2)
        # The screen is ready for the next product
        self.assertFalse(session.product_id)
        self.assertEqual(session.step, 2)
        self.assertTrue(session.step_message)
        # The same session is opened again
        self.assertEqual(self._open(picking), session)

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
        self._scan(self._open(picking), "CAPTURE-PACK6")
        self.assertEqual(self._move(picking, self.product).captured_quantity, 6)

    def test_lot_filled_from_stock(self):
        picking = self._create_delivery(self.product_lot)
        # The delivery profile proposes the only lot in stock
        self._scan(self._open(picking), "2345678901234")
        line = picking.move_line_ids.filtered("picked")
        self.assertEqual(line.lot_id, self.lot)

    def test_scan_lot_after_product(self):
        picking = self._create_delivery(self.product_lot)
        session = self._open(
            picking, self.env.ref("stock_capture.stock_capture_profile_operation")
        )
        self._scan(session, "2345678901234")
        self.assertEqual(session.product_id, self.product_lot)
        self.assertFalse(picking.move_line_ids.filtered("picked"))
        self.assertIn("Lot", session.step_message)
        self._scan(session, "SCAN-LOT")
        line = picking.move_line_ids.filtered("picked")
        self.assertEqual(line.lot_id, self.lot)
        self.assertEqual(line.quantity, 1)

    def test_scan_lot_alone(self):
        picking = self._create_delivery(self.product_lot)
        self._scan(self._open(picking), "SCAN-LOT")
        line = picking.move_line_ids.filtered("picked")
        self.assertEqual(line.product_id, self.product_lot)
        self.assertEqual(line.lot_id, self.lot)

    def test_scan_location_then_products(self):
        profile = self._create_profile(
            [
                (1, "location_id", "to_scan required filled_default"),
                (2, "product_id", "to_scan required clean_after_done"),
                (2, "location_id", "to_scan"),
                (3, "quantity", "required clean_after_done"),
            ]
        )
        picking = self._create_delivery(self.product)
        session = self._open(picking, profile)
        self._scan(session, "CAPTURE-SHELF", "1234567890128")
        line = picking.move_line_ids.filtered("picked")
        self.assertEqual(line.location_id, self.shelf)
        # The location is kept for the next products
        self.assertEqual(session.location_id, self.shelf)

    def test_free_source_follows_reservations(self):
        product_shelf = self.env["product.product"].create(
            {"name": "On shelf", "is_storable": True, "barcode": "CAPTURE-SHELF-P"}
        )
        self.env["stock.quant"]._update_available_quantity(product_shelf, self.shelf, 5)
        picking = self._create_delivery(product_shelf | self.product2, quantity=2)
        session = self._open(picking)
        result = self._scan(session, "CAPTURE-SHELF-P")
        self.assertIn("On shelf", result["message"])
        # The source proposed by the screen follows where each product is
        # reserved
        self.assertEqual(session.location_id, self.shelf)
        self.assertFalse(session.location_from_user)
        self._scan(session, "CAPTURE-P2")
        line = self._move(picking, self.product2).move_line_ids.filtered("picked")
        self.assertEqual(line.location_id, self.stock_location)

    def test_scan_gs1(self):
        self.env.company.nomenclature_id = self.env.ref(
            "barcodes_gs1_nomenclature.default_gs1_nomenclature"
        )
        picking = self._create_delivery(self.product_kg, quantity=20)
        # GTIN, net weight of 12.5 kg
        self._scan(self._open(picking), "01084123456789053102001250")
        self.assertEqual(self._move(picking, self.product_kg).captured_quantity, 12.5)

    def test_scan_gs1_lot_and_serial(self):
        """The batch or lot number (AI 10) wins over the serial number (21)"""
        self.env.company.nomenclature_id = self.env.ref(
            "barcodes_gs1_nomenclature.default_gs1_nomenclature"
        )
        self.product_lot.barcode = "08412345678912"
        picking = self._create_delivery(self.product_lot, quantity=5)
        session = self._open(
            picking, self.env.ref("stock_capture.stock_capture_profile_operation")
        )
        # GTIN, serial OTHER (21), lot SCAN-LOT (10), 2 units (37)
        self._scan(session, "010841234567891221OTHER\x1d10SCAN-LOT\x1d372")
        line = picking.move_line_ids.filtered("picked")
        self.assertEqual(line.lot_id, self.lot)
        self.assertEqual(line.quantity, 2)

    def test_scan_gs1_destination(self):
        self.env.company.nomenclature_id = self.env.ref(
            "barcodes_gs1_nomenclature.default_gs1_nomenclature"
        )
        bin_location = self.env["stock.location"].create(
            {
                "name": "GLN bin",
                "barcode": "8412345000010",
                "location_id": self.stock_location.id,
            }
        )
        session = self._open(self.picking_type_out)
        self._scan(session, "4108412345000010")
        self.assertEqual(session.location_dest_id, bin_location)

    def test_scan_package_content(self):
        package = self.env["stock.package"].create({"name": "SCAN-PACK"})
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.stock_location, 4, package_id=package
        )
        profile = self._create_profile(
            [
                (1, "location_id", "required filled_default"),
                (2, "package_id", "to_scan clean_after_done"),
                (2, "product_id", "to_scan required clean_after_done"),
                (3, "quantity", "required clean_after_done"),
            ]
        )
        picking = self._create_delivery(self.product)
        self._scan(self._open(picking, profile), "SCAN-PACK")
        line = picking.move_line_ids.filtered("picked")
        self.assertEqual(line.package_id, package)
        self.assertEqual(line.result_package_id, package)
        self.assertEqual(line.quantity, 4)

    def test_scan_unknown(self):
        picking = self._create_delivery(self.product)
        result = self._scan(self._open(picking), "NOT-A-BARCODE")
        self.assertEqual(result["message_type"], "danger")
        self.assertEqual(result["sound"], "ko")
        self.assertFalse(picking.move_line_ids.filtered("picked"))

    def test_manual_confirm(self):
        profile = self.delivery_profile.copy({"manual_confirm": True})
        picking = self._create_delivery(self.product)
        session = self._open(picking, profile)
        result = self._scan(session, "1234567890128")
        self.assertEqual(result["message_type"], "info")
        self.assertFalse(picking.move_line_ids.filtered("picked"))
        session.quantity = 3
        session.action_confirm()
        self.assertEqual(self._move(picking, self.product).captured_quantity, 3)

    def test_accumulate_read_quantity(self):
        profile = self.delivery_profile.copy(
            {"manual_confirm": True, "accumulate_read_quantity": True}
        )
        picking = self._create_delivery(self.product)
        session = self._open(picking, profile)
        self._scan(session, "1234567890128", "1234567890128", "1234567890128")
        self.assertEqual(session.quantity, 3)
        session.action_confirm()
        self.assertEqual(self._move(picking, self.product).captured_quantity, 3)

    def test_over_demand_needs_force(self):
        picking = self._create_delivery(self.product, quantity=2)
        session = self._open(
            picking, self.delivery_profile.copy({"manual_confirm": True})
        )
        self._scan(session, "1234567890128")
        session.quantity = 3
        session.action_confirm()
        self.assertTrue(session.force_visible)
        self.assertEqual(self._move(picking, self.product).captured_quantity, 0)
        session.action_force()
        self.assertEqual(self._move(picking, self.product).captured_quantity, 3)
        self.assertFalse(session.force_visible)

    def test_not_available_in_location(self):
        picking = self._create_delivery(self.product, quantity=10)
        session = self._open(
            picking, self.delivery_profile.copy({"manual_confirm": True})
        )
        self._scan(session, "1234567890128")
        session.write({"location_id": self.shelf.id, "quantity": 6})
        session.action_confirm()
        self.assertEqual(self._move(picking, self.product).captured_quantity, 0)
        self.assertEqual(session.feedback_sound, "ko")

    def test_not_demanded_product(self):
        picking = self._create_delivery(self.product)
        session = self._open(picking)
        result = self._scan(session, "CAPTURE-P2")
        self.assertEqual(result["sound"], "ko")
        self.assertFalse(self._move(picking, self.product2))
        session = self._open(
            picking, self.delivery_profile.copy({"allow_not_demanded_product": True})
        )
        self._scan(session, "CAPTURE-P2")
        self.assertEqual(self._move(picking, self.product2).captured_quantity, 1)

    def test_guided_wrong_product(self):
        profile = self._create_profile(
            [
                (1, "location_id", "required filled_default"),
                (2, "product_id", "to_scan required forced clean_after_done"),
                (3, "quantity", "required clean_after_done"),
            ],
            guided=True,
            card_source="move",
        )
        picking = self._create_delivery(self.product | self.product2)
        session = self._open(picking, profile)
        first = session.card_move_id
        self.assertTrue(first)
        other = (self.product | self.product2) - first.product_id
        result = self._scan(session, other.barcode)
        self.assertEqual(result["sound"], "ko")
        self.assertFalse(picking.move_line_ids.filtered("picked"))
        session.action_next_card()
        self.assertEqual(session.card_move_id.product_id, other)
        self._scan(session, other.barcode)
        self.assertEqual(self._move(picking, other).captured_quantity, 1)

    def test_cards(self):
        picking = self._create_delivery(self.product | self.product2, quantity=2)
        session = self._open(picking)
        self.assertEqual(len(session.card_line_ids), 2)
        self._scan(session, "1234567890128", "1234567890128")
        # The captured line is not pending any more
        self.assertEqual(session.card_line_ids.product_id, self.product2)
        session.card_line_ids.with_context(
            capture_session_id=session.id
        ).action_capture_card_remaining()
        self.assertFalse(session.card_line_ids)
        session.action_toggle_card_filter()
        self.assertEqual(len(session.card_line_ids), 2)

    def test_card_fills_the_screen(self):
        picking = self._create_delivery(self.product | self.product2, quantity=2)
        session = self._open(picking)
        card = session.card_line_ids.filtered(
            lambda ml: ml.product_id == self.product
        ).with_context(capture_session_id=session.id)
        self.assertEqual(card.capture_card_pending, 2)
        # The edit button of the card fills the screen without capturing
        card.action_capture_card_select()
        self.assertEqual(session.product_id, self.product)
        self.assertEqual(session.location_id, card.location_id)
        self.assertEqual(self._move(picking, self.product).captured_quantity, 0)
        # The quantity is typed and confirmed, as on the screen
        session.quantity = 1
        session.action_confirm()
        move = self._move(picking, self.product)
        self.assertEqual(move.captured_quantity, 1)
        self.assertEqual(move.capture_pending_quantity, 1)

    def test_close_card_without_backorder(self):
        picking = self._create_delivery(self.product | self.product2, quantity=4)
        session = self._open(picking)
        self._scan(session, "1234567890128")
        self._move(picking, self.product).with_context(
            capture_session_id=session.id,
            capture_backorder_action="skip_backorder",
        ).action_capture_close()
        self._move(picking, self.product2).with_context(
            capture_session_id=session.id
        ).action_capture_remaining()
        session.action_validate()
        self.assertEqual(picking.state, "done")
        self.assertFalse(picking.backorder_ids)
        self.assertEqual(self._move(picking, self.product).quantity, 1)

    def test_validate_with_backorder(self):
        picking = self._create_delivery(self.product, quantity=4)
        session = self._open(picking)
        self._scan(session, "1234567890128")
        action = session.action_validate()
        # Odoo asks what to do with the rest
        self.assertEqual(action["res_model"], "stock.backorder.confirmation")

    def test_operation_type_finds_picking(self):
        profile = self.delivery_profile.copy({"search_picking_from_product": "first"})
        self.picking_type_out.capture_profile_id = profile
        picking = self._create_delivery(self.product)
        session = self._open(self.picking_type_out)
        result = self._scan(session, "1234567890128")
        self.assertEqual(session.res_model, "stock.picking")
        self.assertEqual(session.res_id, picking.id)
        self.assertEqual(result["action"]["res_id"], session.id)
        self.assertEqual(self._move(picking, self.product).captured_quantity, 1)

    def test_open_document(self):
        profile = self.delivery_profile.copy({"search_picking_from_product": "first"})
        self.picking_type_out.capture_profile_id = profile
        picking = self._create_delivery(self.product)
        session = self._open(self.picking_type_out)
        # Before a product is read the document is the operation type
        action = session.action_open_document()
        self.assertEqual(action["res_model"], "stock.picking.type")
        self.assertEqual(action["res_id"], self.picking_type_out.id)
        self._scan(session, "1234567890128")
        action = session.action_open_document()
        self.assertEqual(action["res_model"], "stock.picking")
        self.assertEqual(action["res_id"], picking.id)

    def test_new_picking(self):
        profile = self.delivery_profile.copy({"allow_not_demanded_product": True})
        self.picking_type_out.capture_new_picking_profile_id = profile
        action = self.picking_type_out.action_capture_new_picking()
        session = self.env[action["res_model"]].browse(action["res_id"])
        picking = session._capture_document()
        self._scan(session, "1234567890128")
        self.assertEqual(picking.move_ids.product_id, self.product)
        self.assertEqual(picking.move_ids.captured_quantity, 1)

    def test_receipt_create_lot(self):
        self.picking_type_in.use_create_lots = True
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_in.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product_lot.id,
                            "product_uom_qty": 5,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        profile = self._create_profile(
            [
                (1, "product_id", "to_scan required clean_after_done"),
                (2, "lot_name", "to_scan required clean_after_done"),
                (3, "quantity", "required clean_after_done"),
            ]
        )
        session = self._open(picking, profile)
        self._scan(session, "2345678901234", "NEW-LOT")
        line = picking.move_line_ids.filtered("picked")
        self.assertEqual(line.lot_id.name, "NEW-LOT")
        self.assertEqual(line.quantity, 1)

    def test_destination_read(self):
        bin_location = self.env["stock.location"].create(
            {
                "name": "Bin",
                "barcode": "CAPTURE-BIN",
                "location_id": self.stock_location.id,
            }
        )
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_in.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 5,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        profile = self._create_profile(
            [
                (1, "location_dest_id", "to_scan required"),
                (2, "product_id", "to_scan required clean_after_done"),
                (3, "quantity", "required clean_after_done"),
            ]
        )
        session = self._open(picking, profile)
        self._scan(session, "CAPTURE-BIN", "1234567890128")
        line = picking.move_line_ids.filtered("picked")
        self.assertEqual(line.location_dest_id, bin_location)
        self.assertEqual(line.quantity, 1)

    def test_propose_location_dest(self):
        profile = self.env.ref("stock_capture.stock_capture_profile_receipt").copy(
            {"propose_location_dest": True}
        )
        new_product = self.env["product.product"].create(
            {"name": "New", "is_storable": True, "barcode": "CAPTURE-NEW"}
        )
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_in.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": 5,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                    for product in (self.product, new_product)
                ],
            }
        )
        picking.action_confirm()
        self.env["stock.quant"]._update_available_quantity(self.product, self.shelf, 50)
        session = self._open(picking, profile.copy({"manual_confirm": True}))
        self._scan(session, "1234567890128")
        # The shelf has most stock of the product
        self.assertEqual(session.location_dest_id, self.shelf)
        self.assertTrue(session.location_dest_proposed)
        self.assertEqual(session.location_stock_count, 2)
        # A product without stock leaves the destination to be read
        session.action_clean()
        self._scan(session, "CAPTURE-NEW")
        self.assertFalse(session.location_dest_id)
        # A destination read by the user is kept
        self._scan(session, "CAPTURE-SHELF")
        self._scan(session, "1234567890128")
        self.assertEqual(session.location_dest_id, self.shelf)
        self.assertFalse(session.location_dest_proposed)

    def test_product_outgoing_qty(self):
        self._create_delivery(self.product, quantity=7)
        session = self._open(self.picking_type_in)
        session.product_id = self.product
        self.assertEqual(session.product_outgoing_qty, 7)

    def test_inventory(self):
        session = self._open(self.stock_location)
        self.assertEqual(session.capture_kind, "inventory")
        self.assertEqual(session.location_id, self.stock_location)
        self._scan(session, "1234567890128", "1234567890128")
        quant = self.env["stock.quant"].search(
            [
                ("product_id", "=", self.product.id),
                ("location_id", "=", self.stock_location.id),
            ]
        )
        self.assertEqual(quant.inventory_quantity, 2)
        self.assertEqual(quant.user_id, self.env.user)
        session.card_filter = "done"
        self.assertIn(quant, session.card_quant_ids)
        quant.with_context(capture_session_id=session.id).action_capture_count_add()
        self.assertEqual(quant.inventory_quantity, 3)
        # Editing a counted quant replaces its quantity
        session.action_select_card("stock.quant", quant.id)
        session.quantity = 30
        session.action_confirm()
        self.assertEqual(quant.inventory_quantity, 30)
        action = session.action_validate()
        self.assertEqual(action["context"]["default_quant_ids"], [quant.id])

    def test_inventory_serial(self):
        product = self.env["product.product"].create(
            {
                "name": "Serial",
                "is_storable": True,
                "tracking": "serial",
                "barcode": "CAPTURE-SERIAL",
            }
        )
        serial = self.env["stock.lot"].create({"name": "SN1", "product_id": product.id})
        session = self._open(self.stock_location)
        self._scan(session, "CAPTURE-SERIAL", "SN1")
        quant = self.env["stock.quant"].search([("lot_id", "=", serial.id)])
        self.assertEqual(quant.inventory_quantity, 1)
        result = self._scan(session, "CAPTURE-SERIAL", "SN1")
        self.assertEqual(result["sound"], "ko")
        self.assertEqual(quant.inventory_quantity, 1)

    def test_product_info(self):
        picking = self._create_delivery(self.product)
        session = self._open(
            picking, self.delivery_profile.copy({"manual_confirm": True})
        )
        self._scan(session, "1234567890128")
        action = session.action_product_info()
        info = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(info.qty_available, 35)
        self.assertEqual(info.line_ids.location_id, self.stock_location | self.shelf)
        info.line_ids.filtered(lambda ln: ln.location_id == self.shelf).action_select()
        self.assertEqual(session.location_id, self.shelf)

    def test_fixed_putaway_kept(self):
        self.env["stock.putaway.rule"].create(
            {
                "product_id": self.product.id,
                "location_in_id": self.stock_location.id,
                "location_out_id": self.shelf.id,
            }
        )
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_in.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 5,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        self._scan(self._open(picking), "1234567890128")
        line = picking.move_line_ids.filtered("picked")
        self.assertEqual(line.location_dest_id, self.shelf)

    def test_auto_put_in_pack(self):
        self.env.user.group_ids |= self.env.ref("stock.group_tracking_lot")
        profile = self.delivery_profile.copy({"auto_put_in_pack": True})
        self.picking_type_out.capture_profile_id = profile
        picking = self._create_delivery(self.product, quantity=2)
        session = self._open(picking)
        self._scan(session, "1234567890128", "1234567890128")
        session.action_validate()
        self.assertEqual(picking.state, "done")
        self.assertTrue(picking.move_line_ids.result_package_id)

    def test_new_packaging(self):
        pack = self.env["uom.uom"].create(
            {"name": "Pack of 4", "relative_factor": 4, "relative_uom_id": self.unit.id}
        )
        # Packaging units are units of the product, with several units enabled
        self.env.ref("base.group_user").implied_ids |= self.env.ref("uom.group_uom")
        self.product.uom_ids = pack
        picking = self._create_delivery(self.product)
        session = self._open(picking)
        session.product_id = self.product
        action = session.action_new_packaging()
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        self.assertIn(pack, wizard.allowed_uom_ids)
        wizard.write({"uom_id": pack.id, "barcode": "CAPTURE-PACK4"})
        wizard.action_confirm()
        self.assertEqual(session.packaging_id.barcode, "CAPTURE-PACK4")
        session.action_clean()
        self._scan(session, "CAPTURE-PACK4")
        self.assertEqual(self._move(picking, self.product).captured_quantity, 4)

    def test_assign_serials(self):
        product = self.env["product.product"].create(
            {"name": "Serial in", "is_storable": True, "tracking": "serial"}
        )
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_in.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": 2,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        session = self._open(picking)
        session.product_id = product
        action = session.action_assign_serials()
        move = picking.move_ids
        # The detailed operations dialog saves the generated serial numbers
        move.with_context(**action["context"]).write(
            {
                "move_line_ids": [Command.clear()]
                + [
                    Command.create(
                        {
                            "product_id": product.id,
                            "lot_name": name,
                            "quantity": 1,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                    for name in ("SN-A", "SN-B")
                ]
            }
        )
        self.assertEqual(move.captured_quantity, 2)
        self.assertEqual(move.move_line_ids.picking_id, picking)

    def test_grouped_cards(self):
        lot2 = self.env["stock.lot"].create(
            {"name": "SCAN-LOT2", "product_id": self.product_lot.id}
        )
        self.env["stock.quant"]._update_available_quantity(
            self.product_lot, self.stock_location, 3, lot_id=lot2
        )
        profile = self.delivery_profile.copy({"card_group": "location_product"})
        picking = self._create_delivery(self.product_lot, quantity=12)
        self.assertEqual(len(picking.move_line_ids), 2)
        session = self._open(picking, profile)
        self.assertEqual(len(session.card_line_ids), 1)
        card = session.card_line_ids.with_context(capture_session_id=session.id)
        self.assertEqual(card.capture_card_quantity, 12)
        card.action_capture_card_remaining()
        self.assertEqual(picking.move_ids.captured_quantity, 12)

    def test_batch(self):
        picking1 = self._create_delivery(self.product, quantity=2)
        picking2 = self._create_delivery(self.product | self.product2, quantity=1)
        batch = self.env["stock.picking.batch"].create(
            {"picking_ids": [Command.set((picking1 | picking2).ids)]}
        )
        batch.action_confirm()
        session = self._open(batch)
        self.assertEqual(session.capture_kind, "outgoing")
        # The product read fills the operations of all the transfers
        self._scan(session, *["1234567890128"] * 3, "CAPTURE-P2")
        self.assertEqual(self._move(picking1, self.product).captured_quantity, 2)
        self.assertEqual(self._move(picking2, self.product).captured_quantity, 1)
        self.assertEqual(self._move(picking2, self.product2).captured_quantity, 1)
        session.action_validate()
        self.assertEqual(batch.state, "done")

    def test_migrate_read_quantities(self):
        """Quantities read in 18.0 (qty_picked) are captured on install"""
        picking = self._create_delivery(self.product, quantity=10)
        move = self._move(picking, self.product)
        cr = self.env.cr
        cr.execute("ALTER TABLE stock_move_line ADD COLUMN qty_picked NUMERIC")
        cr.execute("ALTER TABLE stock_move ADD COLUMN barcode_backorder_action VARCHAR")
        cr.execute(
            "UPDATE stock_move_line SET qty_picked = 4 WHERE id = %s",
            (move.move_line_ids.id,),
        )
        cr.execute(
            "UPDATE stock_move SET barcode_backorder_action = 'skip_backorder' "
            "WHERE id = %s",
            (move.id,),
        )
        self.env.invalidate_all()
        _capture_read_quantities(self.env)
        self.assertEqual(move.captured_quantity, 4)
        self.assertEqual(move.quantity, 10)
        self.assertEqual(move.capture_backorder_action, "skip_backorder")

    def test_grouped_cards_expression(self):
        lot2 = self.env["stock.lot"].create(
            {"name": "SCAN-LOT3", "product_id": self.product_lot.id}
        )
        self.env["stock.quant"]._update_available_quantity(
            self.product_lot, self.stock_location, 3, lot_id=lot2
        )
        profile = self.delivery_profile.copy(
            {
                "card_group": "expression",
                "card_group_expression": "object.location_id, object.product_id",
            }
        )
        picking = self._create_delivery(self.product_lot, quantity=12)
        session = self._open(picking, profile)
        self.assertEqual(len(session.card_line_ids), 1)
        card = session.card_line_ids.with_context(capture_session_id=session.id)
        self.assertEqual(card.capture_card_quantity, 12)

    def test_capture_state_and_lock(self):
        picking = self._create_delivery(self.product, quantity=2)
        move = self._move(picking, self.product)
        self.assertEqual(move.capture_state, "to_capture")
        self._scan(self._open(picking), "1234567890128", "1234567890128")
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

    def test_capture_remaining_and_undo(self):
        picking = self._create_delivery(self.product | self.product_kg)
        move = self._move(picking, self.product)
        self._scan(self._open(picking), "1234567890128")
        picking.move_ids.action_capture_remaining()
        self.assertEqual(move.captured_quantity, 10)
        self.assertEqual(self._move(picking, self.product_kg).captured_quantity, 10)
        self.assertEqual(set(picking.move_ids.mapped("capture_state")), {"captured"})
        picking.move_ids.action_capture_undo()
        self.assertEqual(set(picking.move_ids.mapped("captured_quantity")), {0})
        self.assertEqual(sum(move.move_line_ids.mapped("quantity")), 10)
