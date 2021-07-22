# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    barcode_option_group_id = fields.Many2one(
        comodel_name="stock.barcodes.option.group"
    )

    def action_barcode_scan(self):
        vals = {
            "res_model_id": self.env.ref("stock.model_stock_picking_type").id,
            "res_id": self.id,
            "picking_type_code": self.code,
            "option_group_id": self.barcode_option_group_id.id,
            "picking_mode": "picking",
            "picking_type_id": self.id,
        }
        if self.barcode_option_group_id.get_option_value(
            "location_id", "filled_default"
        ):
            if self.code == "incoming":
                location = self.default_location_dest_id
            elif self.code in ["outgoing", "internal"]:
                location = self.default_location_src_id
            vals["location_id"] = location.id
        wiz = self.env["wiz.stock.barcodes.read.picking"].create(vals)
        action = self.env.ref(
            "stock_barcodes.action_stock_barcodes_read_picking"
        ).read()[0]
        action["res_id"] = wiz.id
        return action
