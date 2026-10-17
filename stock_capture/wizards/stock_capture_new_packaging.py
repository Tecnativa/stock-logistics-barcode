# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models
from odoo.exceptions import UserError


class StockCaptureNewPackaging(models.TransientModel):
    _name = "stock.capture.new.packaging"
    _description = "Packaging barcode registered from a capture screen"

    session_id = fields.Many2one(
        comodel_name="stock.capture.session", required=True, ondelete="cascade"
    )
    product_id = fields.Many2one(comodel_name="product.product", required=True)
    allowed_uom_ids = fields.Many2many(
        comodel_name="uom.uom", compute="_compute_allowed_uom_ids"
    )
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit",
        domain="[('id', 'in', allowed_uom_ids)]",
        help="Unit of the packaging, e.g. Pack of 6",
    )
    barcode = fields.Char()

    @api.depends("product_id")
    def _compute_allowed_uom_ids(self):
        for wizard in self:
            wizard.allowed_uom_ids = wizard.product_id._get_available_uoms()

    def action_confirm(self):
        """Create the packaging and use it on the screen"""
        self.ensure_one()
        if not self.uom_id or not self.barcode:
            raise UserError(self.env._("Set the unit and the barcode of the packaging"))
        packaging = self.env["product.uom"].create(
            {
                "product_id": self.product_id.id,
                "uom_id": self.uom_id.id,
                "barcode": self.barcode,
            }
        )
        self.session_id.write(
            {"packaging_id": packaging.id, "uom_id": self.uom_id.id, "quantity": 1.0}
        )
        self.session_id._capture_feedback(sound="ok")
        return {"type": "ir.actions.act_window_close"}
