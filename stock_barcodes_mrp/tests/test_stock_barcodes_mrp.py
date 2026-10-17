# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import Command
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockBarcodesMrp(TransactionCase):
    def test_scan_manufacturing_order(self):
        Product = self.env["product.product"]
        finished = Product.create({"name": "Fillets", "is_storable": True})
        component = Product.create(
            {"name": "Fish", "is_storable": True, "barcode": "MO-FISH"}
        )
        bom = self.env["mrp.bom"].create(
            {
                "product_tmpl_id": finished.product_tmpl_id.id,
                "bom_line_ids": [
                    Command.create({"product_id": component.id, "product_qty": 2})
                ],
            }
        )
        self.env["stock.quant"]._update_available_quantity(
            component, self.env.ref("stock.warehouse0").lot_stock_id, 10
        )
        production_form = Form(self.env["mrp.production"])
        production_form.product_id = finished
        production_form.bom_id = bom
        production = production_form.save()
        production.action_confirm()
        action = production.action_capture_open()
        self.assertEqual(action["path"], "barcode-reader")
        session = self.env[action["res_model"]].browse(action["res_id"])
        session.capture_barcode("MO-FISH")
        self.assertEqual(production.move_raw_ids.captured_quantity, 1)
