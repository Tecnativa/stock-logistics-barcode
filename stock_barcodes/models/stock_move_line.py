# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    barcode_scan_state = fields.Selection(
        [("pending", "Pending"), ("done", "Done"), ("done_forced", "Done forced")],
        string="Scan State",
        default="pending",
        compute="_compute_barcode_scan_state",
        readonly=False,
        store=True,
    )

    @api.depends("qty_done", "product_uom_qty")
    def _compute_barcode_scan_state(self):
        for line in self:
            if line.qty_done >= line.product_uom_qty:
                line.barcode_scan_state = "done"
            else:
                line.barcode_scan_state = "pending"

    def fill_from_pending_line(self):
        wiz_barcode_id = self.env.context.get("wiz_barcode_id", False)
        wiz_barcode_read_picking = self.env["wiz.stock.barcodes.read.picking"].browse(
            wiz_barcode_id
        )
        wiz_barcode_read_picking.product_id = self.product_id
        wiz_barcode_read_picking.lot_id = self.lot_id
