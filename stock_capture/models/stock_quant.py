# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _capture_count(self, quantity):
        for quant in self.with_context(inventory_mode=True):
            quant.write(
                {
                    "inventory_quantity": quantity,
                    "user_id": self.env.user.id,
                    "inventory_date": fields.Date.context_today(self),
                }
            )
        self.env["stock.capture.session"]._capture_refresh_from_context()
        return True

    def action_capture_count_add(self):
        """One more unit counted"""
        for quant in self:
            quant._capture_count(quant.inventory_quantity + 1)
        return True

    def action_capture_count_remove(self):
        """One unit less counted"""
        for quant in self:
            quant._capture_count(max(quant.inventory_quantity - 1, 0.0))
        return True

    def action_capture_count_clear(self):
        """Forget the count"""
        self.with_context(inventory_mode=True).action_clear_inventory_quantity()
        self.env["stock.capture.session"]._capture_refresh_from_context()
        return True

    def action_capture_card_select(self):
        """Fill the capture screen from the card"""
        self.ensure_one()
        session = self.env["stock.capture.session"]._capture_from_context()
        if session:
            session.action_select_card(self._name, self.id)
        return True
