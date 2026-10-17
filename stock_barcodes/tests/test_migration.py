# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import importlib.util
from pathlib import Path

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMigration(TransactionCase):
    """The option groups of 18.0 become capture profiles"""

    def _run_migration(self):
        path = (
            Path(__file__).parent.parent
            / "migrations"
            / "20.0.1.0.0"
            / "post-migration.py"
        )
        spec = importlib.util.spec_from_file_location("stock_barcodes_mig", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, "18.0.1.3.0")

    def test_option_groups_to_profiles(self):
        cr = self.env.cr
        cr.execute(
            """CREATE TABLE stock_barcodes_option_group (
                id SERIAL PRIMARY KEY, name VARCHAR, code VARCHAR,
                barcode_guided_mode VARCHAR, is_manual_confirm BOOLEAN,
                source_pending_moves VARCHAR, show_pending_moves VARCHAR,
                group_key_for_todo_records VARCHAR, fill_fields_from_lot BOOLEAN
            )"""
        )
        cr.execute(
            """CREATE TABLE stock_barcodes_option (
                id SERIAL PRIMARY KEY, option_group_id INTEGER, name VARCHAR,
                field_name VARCHAR, step INTEGER, sequence INTEGER,
                to_scan BOOLEAN, required BOOLEAN, filled_default BOOLEAN,
                forced BOOLEAN, clean_after_done BOOLEAN
            )"""
        )
        cr.execute(
            """INSERT INTO stock_barcodes_option_group
            (name, code, barcode_guided_mode, is_manual_confirm,
            source_pending_moves, show_pending_moves, group_key_for_todo_records,
            fill_fields_from_lot)
            VALUES ('Picking OUT options', 'OUT', 'guided', TRUE, 'move_ids',
            'pending', 'object.location_id,object.product_id', TRUE)
            RETURNING id"""
        )
        group_id = cr.fetchone()[0]
        cr.execute(
            """INSERT INTO stock_barcodes_option
            (option_group_id, name, field_name, step, sequence, to_scan, required,
            filled_default, forced, clean_after_done) VALUES
            (%s, 'Product', 'product_id', 1, 10, TRUE, TRUE, FALSE, TRUE, TRUE),
            (%s, 'Qty', 'product_qty', 2, 20, FALSE, TRUE, FALSE, FALSE, TRUE),
            (%s, 'Master box', 'master_box_id', 1, 30, TRUE, FALSE, FALSE, FALSE,
            TRUE)""",
            (group_id, group_id, group_id),
        )
        picking_type = self.env.ref("stock.picking_type_out")
        cr.execute(
            "ALTER TABLE stock_picking_type ADD COLUMN barcode_option_group_id INTEGER"
        )
        cr.execute(
            "UPDATE stock_picking_type SET barcode_option_group_id = %s WHERE id = %s",
            (group_id, picking_type.id),
        )
        self._run_migration()
        profile = picking_type.capture_profile_id
        self.assertEqual(profile.name, "Picking OUT options")
        self.assertTrue(profile.guided)
        self.assertTrue(profile.manual_confirm)
        self.assertTrue(profile.fill_from_stock)
        self.assertFalse(profile.quantity_from_stock)
        self.assertEqual(profile.card_source, "move")
        self.assertEqual(profile.card_filter, "pending")
        self.assertEqual(profile.card_group, "location_product")
        # The field of another module is left out
        self.assertEqual(
            profile.field_ids.mapped("field_name"), ["product_id", "quantity"]
        )
        self.assertTrue(profile.field_ids[0].forced)
