# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models


class StockCaptureSession(models.TransientModel):
    _inherit = "stock.capture.session"

    def _capture_action(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_barcodes.action_capture_session"
        )
        action.update(
            name=self.document_name,
            res_id=self.id,
            views=[(action["view_id"][0] if action.get("view_id") else False, "form")],
        )
        return action

    def _capture_after_validate(self):
        """Back to the transfers of the operation type ready to read"""
        document = self._capture_document()
        if "picking_type_id" in document._fields and document.picking_type_id:
            action = document.picking_type_id.action_barcode_ready_pickings()
            # A new breadcrumb: the validated document is left behind
            action["target"] = "main"
            return action
        return super()._capture_after_validate()

    def action_open_menu(self):
        return self.env["ir.actions.actions"]._for_xml_id(
            "stock_barcodes.action_stock_barcodes_main_menu"
        )
