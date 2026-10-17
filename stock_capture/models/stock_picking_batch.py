# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models


class StockPickingBatch(models.Model):
    """The operations of all the transfers of a batch are captured together"""

    _name = "stock.picking.batch"
    _inherit = ("stock.picking.batch", "stock.capture.document")

    def _capture_profile(self):
        return self.picking_type_id._capture_profile()

    def _capture_kind(self):
        return self.picking_type_id.code or "internal"

    def _capture_moves(self):
        return self.move_ids

    def _capture_source_locations(self):
        return self.picking_ids.location_id

    def _capture_dest_locations(self):
        return self.picking_ids.location_dest_id

    def _capture_info(self):
        info = super()._capture_info()
        info.update(note=self.description or False, company_id=self.company_id)
        return info

    def _capture_can_validate(self):
        return self.state == "in_progress"

    def _capture_validate(self, session):
        pickings = self.picking_ids.filtered(
            lambda p: p.state not in ("done", "cancel")
        )
        pickings._capture_put_in_pack()
        return self.with_context(
            **pickings._capture_validate_context(session)
        ).action_done()
