# Copyright 2024 Tecnativa - Sergio Teruel
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    barcodes_requested_review = fields.Boolean(
        string="Review Requested",
        copy=False,
        help="The batch waits for another user to review what was prepared",
    )

    def write(self, vals):
        result = super().write(vals)
        if vals.get("barcodes_requested_review"):
            # Any user can take the batch to review it
            self.user_id = False
        return result

    def action_barcodes_review(self):
        """Review the batch with the barcode screen"""
        self.ensure_one()
        action = self.action_capture_open()
        session = self.env[action["res_model"]].browse(action["res_id"])
        session._capture_start_review()
        return action
