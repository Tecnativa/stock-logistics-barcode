# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def fill_from_pending_line(self):
        wiz_barcode_id = self.env.context.get("wiz_barcode_id", False)
        wiz_barcode_read_picking = self.env["wiz.stock.barcodes.read.picking"].browse(
            wiz_barcode_id
        )
        wiz_barcode_read_picking.product_id = self.product_id
