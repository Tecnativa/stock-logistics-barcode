# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import datetime

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockCaptureProductExpiry(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref("stock.group_production_lot")
        cls.env.company.nomenclature_id = cls.env.ref(
            "barcodes_gs1_nomenclature.default_gs1_nomenclature"
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Yogurt",
                "is_storable": True,
                "tracking": "lot",
                "use_expiration_date": True,
                "use_time": 5,
                "barcode": "08412345678905",
            }
        )
        cls.picking_type = cls.env.ref("stock.picking_type_in")
        cls.picking_type.use_create_lots = True
        supplier = cls.env.ref("stock.stock_location_suppliers")
        stock = cls.env.ref("stock.warehouse0").lot_stock_id
        cls.picking = cls.env["stock.picking"].create(
            {
                "picking_type_id": cls.picking_type.id,
                "location_id": supplier.id,
                "location_dest_id": stock.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": 10,
                            "location_id": supplier.id,
                            "location_dest_id": stock.id,
                        }
                    )
                ],
            }
        )
        cls.picking.action_confirm()

    def _read(self, barcode):
        action = self.picking.action_capture_open()
        session = self.env[action["res_model"]].browse(action["res_id"])
        session.capture_barcode(barcode)
        return self.picking.move_line_ids.filtered("picked").lot_id

    def test_expiration_date(self):
        # GTIN, expiration 2027-03-31 (17), lot EXP-1 (10)
        lot = self._read("010841234567890517270331\x1d10EXP-1")
        self.assertEqual(lot.name, "EXP-1")
        self.assertEqual(lot.expiration_date.date(), datetime.date(2027, 3, 31))

    def test_best_before_date(self):
        # GTIN, best before 2027-03-31 (15), lot EXP-2 (10)
        lot = self._read("010841234567890515270331\x1d10EXP-2")
        self.assertEqual(lot.use_date.date(), datetime.date(2027, 3, 31))
        self.assertEqual(lot.expiration_date.date(), datetime.date(2027, 4, 5))
