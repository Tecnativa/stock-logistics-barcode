# Copyright 2024 Tecnativa - Sergio Teruel
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class StockCaptureSession(models.TransientModel):
    _inherit = "stock.capture.session"

    review_mode = fields.Boolean(
        help="The screen reviews the detailed operations already captured "
        "instead of capturing quantities"
    )
    barcodes_requested_review = fields.Boolean(
        compute="_compute_barcodes_requested_review"
    )

    def _compute_barcodes_requested_review(self):
        for session in self:
            document = session._capture_document()
            session.barcodes_requested_review = (
                document._name == "stock.picking.batch"
                and document.barcodes_requested_review
            )

    def _capture_start_review(self):
        self.write({"review_mode": True, "card_filter": "pending"})
        self._capture_refresh()

    def action_request_review(self):
        """Ask another user to review the batch"""
        document = self._capture_document()
        if document._name == "stock.picking.batch":
            document.barcodes_requested_review = not (
                document.barcodes_requested_review
            )
        return True

    def _capture_cards_of_document(self):
        moves, lines = super()._capture_cards_of_document()
        if self.review_mode:
            # The captured detailed operations are the cards to review
            document = self._capture_document()
            lines = self._capture_sort_cards(
                document._capture_moves().move_line_ids.filtered("picked")
            )
            moves = moves.browse()
        return moves, lines

    def _capture_card_done(self, card):
        if self.review_mode and card._name == "stock.move.line":
            return card.barcodes_is_reviewed
        return super()._capture_card_done(card)

    def _capture_confirm(self):
        if not self.review_mode:
            return super()._capture_confirm()
        return self._capture_review()

    def _capture_review(self):
        """Mark as reviewed the captured detailed operations of what is read"""
        if not self.product_id:
            return self._capture_fail(self.env._("Waiting product"), "info")
        if self.product_id.tracking and not self.lot_id:
            return self._capture_fail(self.env._("Waiting lot"), "info")
        document = self._capture_document()
        lines = document._capture_moves().move_line_ids.filtered(
            lambda ml: (
                ml.picked
                and not ml.barcodes_is_reviewed
                and ml.product_id == self.product_id
                and (not self.lot_id or ml.lot_id == self.lot_id)
                and (not self.package_id or ml.package_id == self.package_id)
            )
        )
        product_name = self.product_id.display_name
        if not lines:
            return self._capture_fail(
                self.env._(
                    "Nothing captured to review for %(product)s", product=product_name
                )
            )
        remaining = self._capture_quantity_in_product_uom()
        reviewed = self.env["stock.move.line"]
        for line in lines:
            if line.product_id.uom_id.compare(remaining, 0) <= 0:
                break
            reviewed |= line
            remaining -= line.quantity_product_uom
        reviewed.barcodes_is_reviewed = True
        self._capture_clean_values()
        self._capture_refresh()
        self._capture_message(
            self.env._("%(product)s reviewed", product=product_name), "success"
        )
        return reviewed
