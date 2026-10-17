# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    def action_barcode_scan(self):
        """Read barcodes on the transfers of the operation type"""
        return self.action_capture_open()

    def action_barcode_new_picking(self):
        """Read barcodes on a new unplanned transfer"""
        return self.action_capture_new_picking()

    def action_barcode_ready_pickings(self):
        """Transfers ready to read with barcodes"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_barcodes.action_picking_barcode"
        )
        action["display_name"] = self.display_name
        action["context"] = {
            "search_default_available": 1,
            "search_default_picking_type_id": [self.id],
            "default_picking_type_id": self.id,
        }
        return action
