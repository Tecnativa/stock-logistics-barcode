# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models


class WizStockBarcodesReadPicking(models.TransientModel):
    _inherit = "wiz.stock.barcodes.read.picking"

    def _prepare_move_line_values(self, candidate_move, available_qty):
        vals = super()._prepare_move_line_values(candidate_move, available_qty)
        vals.update(
            {
                "secondary_uom_id": self.secondary_uom_id.id,
                "secondary_uom_qty": self.secondary_uom_qty,
            }
        )
        return vals

    def _get_candidate_line_domain(self):
        domain = super(WizStockBarcodesReadPicking, self)._get_candidate_line_domain()
        if self.secondary_uom_id:
            domain.extend(
                [
                    ("secondary_uom_id", "=", self.secondary_uom_id.id),
                ]
            )
        return domain
