# Copyright 2024 Tecnativa - Sergio Teruel
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    barcodes_is_reviewed = fields.Boolean(
        string="Reviewed", copy=False, help="Checked by a reviewer of the batch"
    )
    capture_card_review = fields.Boolean(compute="_compute_capture_card_review")

    @api.depends_context("capture_review")
    def _compute_capture_card_review(self):
        """The card is shown on a screen reviewing what was captured"""
        self.capture_card_review = bool(self.env.context.get("capture_review"))

    def action_capture_card_review(self):
        """Confirm the review of the card"""
        self._capture_card_lines().barcodes_is_reviewed = True
        self.env["stock.capture.session"]._capture_refresh_from_context()
        return True

    def action_capture_card_unreview(self):
        self._capture_card_lines().barcodes_is_reviewed = False
        self.env["stock.capture.session"]._capture_refresh_from_context()
        return True
