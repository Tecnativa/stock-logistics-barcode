# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import Command
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestStockBarcodesPickingBatchRevision(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        stock = cls.env.ref("stock.warehouse0").lot_stock_id
        customers = cls.env.ref("stock.stock_location_customers")
        cls.product = cls.env["product.product"].create(
            {"name": "Reviewed", "is_storable": True, "barcode": "REVIEW-1"}
        )
        cls.env["stock.quant"]._update_available_quantity(cls.product, stock, 10)
        picking = cls.env["stock.picking"].create(
            {
                "picking_type_id": cls.env.ref("stock.picking_type_out").id,
                "location_id": stock.id,
                "location_dest_id": customers.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": 2,
                            "location_id": stock.id,
                            "location_dest_id": customers.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        cls.batch = cls.env["stock.picking.batch"].create(
            {"picking_ids": [Command.set(picking.ids)], "user_id": cls.env.uid}
        )
        cls.batch.action_confirm()
        cls.reviewer = new_test_user(
            cls.env, login="batch_reviewer", groups="stock.group_stock_user"
        )

    def _session(self, action):
        return self.env[action["res_model"]].browse(action["res_id"])

    def test_review(self):
        picker = self._session(self.batch.action_capture_open())
        picker.capture_barcode("REVIEW-1")
        picker.capture_barcode("REVIEW-1")
        picker.action_request_review()
        self.assertTrue(self.batch.barcodes_requested_review)
        self.assertFalse(self.batch.user_id)
        batch = self.batch.with_user(self.reviewer)
        review = self._session(batch.action_barcodes_review())
        self.assertTrue(review.review_mode)
        self.assertEqual(len(review.card_line_ids), 1)
        result = review.capture_barcode("REVIEW-1")
        self.assertEqual(result["message_type"], "success")
        self.assertTrue(self.batch.move_line_ids.barcodes_is_reviewed)
        # Reading during the review does not change the captured quantity
        self.assertEqual(self.batch.move_ids.captured_quantity, 2)
        self.assertFalse(review.card_line_ids)
