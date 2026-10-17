# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import Command
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockCapturePackage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.stock_location = cls.env.ref("stock.warehouse0").lot_stock_id
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.package_type = cls.env["stock.package.type"].create({"name": "Capture box"})
        cls.picking_type = cls.env.ref("stock.picking_type_out")
        cls.picking_type.write(
            {
                "capture_new_package": True,
                "capture_package_type_id": cls.package_type.id,
                "auto_print_package_label": True,
                "package_label_to_print": "pdf",
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Captured product", "is_storable": True}
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product, cls.stock_location, 20.0
        )

    def _create_picking(self, quantities=(10.0,), location_dest=None):
        location_dest = location_dest or self.customer_location
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type.id,
                "location_id": self.stock_location.id,
                "location_dest_id": location_dest.id,
                # Different descriptions keep Odoo from merging the moves
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": quantity,
                            "description_picking": f"Line {index}",
                            "location_id": self.stock_location.id,
                            "location_dest_id": location_dest.id,
                        }
                    )
                    for index, quantity in enumerate(quantities)
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        return picking

    def test_each_capture_gets_a_new_package(self):
        picking = self._create_picking()
        line_1 = picking._capture_product(self.product, 3.0)
        line_2 = picking._capture_product(self.product, 2.0)
        packages = (line_1 | line_2).result_package_id
        self.assertEqual(len(packages), 2)
        self.assertEqual(packages.package_type_id, self.package_type)
        self.assertEqual(line_1.quantity, 3.0)
        self.assertEqual(line_2.quantity, 2.0)
        unpicked = picking.move_line_ids.filtered(lambda ml: not ml.picked)
        self.assertEqual(unpicked.quantity, 5.0)
        self.assertFalse(unpicked.result_package_id)
        action = picking.button_validate()
        Form(
            self.env[action["res_model"]].with_context(**action["context"])
        ).save().process_cancel_backorder()
        self.assertEqual(picking.state, "done")
        quants = self.env["stock.quant"]._gather(self.product, self.customer_location)
        self.assertEqual(
            sorted(quants.mapped("quantity")),
            [2.0, 3.0],
        )
        self.assertEqual(quants.package_id, packages)

    def test_given_package_is_kept(self):
        picking = self._create_picking()
        package = self.env["stock.package"].create({"name": "CAPTURE-GIVEN"})
        line = picking._capture_product(self.product, 3.0, result_package=package)
        self.assertEqual(line.result_package_id, package)
        line = picking._capture_product(
            self.product, 1.0, result_package=self.env["stock.package"]
        )
        self.assertFalse(line.result_package_id)

    def test_capture_over_several_moves_in_one_package(self):
        picking = self._create_picking(quantities=(2.0, 6.0))
        lines = picking._capture_product(self.product, 5.0)
        self.assertEqual(len(lines.move_id), 2)
        self.assertEqual(len(lines.result_package_id), 1)

    def test_option_disabled(self):
        self.picking_type.capture_new_package = False
        picking = self._create_picking()
        line = picking._capture_product(self.product, 3.0)
        self.assertFalse(line.result_package_id)

    def test_no_package_for_goods_written_off(self):
        loss_location = self.env["stock.location"].search(
            [("usage", "=", "inventory"), ("company_id", "in", [False])], limit=1
        ) or self.env["stock.location"].create(
            {"name": "Capture loss", "usage": "inventory"}
        )
        picking = self._create_picking(location_dest=loss_location)
        line = picking._capture_product(self.product, 3.0)
        self.assertFalse(line.result_package_id)

    def test_package_label_action(self):
        picking = self._create_picking()
        line = picking._capture_product(self.product, 3.0)
        action = line._capture_package_label_action()
        self.assertEqual(action["type"], "ir.actions.report")
        self.assertEqual(
            [label["name"] for label in action["data"]["labels"]],
            [line.result_package_id.name],
        )
        self.picking_type.auto_print_package_label = False
        self.assertFalse(line._capture_package_label_action())
