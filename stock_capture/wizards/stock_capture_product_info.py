# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class StockCaptureProductInfo(models.TransientModel):
    _name = "stock.capture.product.info"
    _description = "Stock of a product read on a capture screen"

    session_id = fields.Many2one(
        comodel_name="stock.capture.session", required=True, ondelete="cascade"
    )
    location_field = fields.Selection(
        [("location_id", "Source"), ("location_dest_id", "Destination")],
        default="location_id",
    )
    product_id = fields.Many2one(comodel_name="product.product", readonly=True)
    uom_id = fields.Many2one(related="product_id.uom_id")
    show_product_info = fields.Boolean(default=True)
    qty_available = fields.Float(string="On Hand", digits="Product Unit")
    incoming_qty = fields.Float(string="Incoming", digits="Product Unit")
    outgoing_qty = fields.Float(string="Outgoing", digits="Product Unit")
    virtual_available = fields.Float(string="Forecasted", digits="Product Unit")
    line_ids = fields.One2many(
        comodel_name="stock.capture.product.info.line", inverse_name="info_id"
    )


class StockCaptureProductInfoLine(models.TransientModel):
    _name = "stock.capture.product.info.line"
    _description = "Stock of a product in a location"
    _order = "sequence, id"

    info_id = fields.Many2one(
        comodel_name="stock.capture.product.info", required=True, ondelete="cascade"
    )
    sequence = fields.Integer()
    location_id = fields.Many2one(comodel_name="stock.location", readonly=True)
    quantity = fields.Float(digits="Product Unit", readonly=True)
    uom_id = fields.Many2one(related="info_id.uom_id")

    def action_select(self):
        """Use the location on the screen"""
        self.ensure_one()
        session = self.info_id.session_id
        session._capture_set_location(self.info_id.location_field, self.location_id)
        session._capture_feedback()
        return {"type": "ir.actions.act_window_close"}
