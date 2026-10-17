# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    capture_new_package = fields.Boolean(
        string="New Package per Capture",
        help="Each quantity read or weighed without a destination package goes "
        "to a new package, e.g. one package per weighing.",
    )
    capture_package_type_id = fields.Many2one(
        comodel_name="stock.package.type",
        help="Package type of the packages created for the captured quantities.",
    )

    def _capture_result_package(self, result_package, location_dest):
        result_package = super()._capture_result_package(result_package, location_dest)
        # Consumed or scrapped goods do not go into packages
        if (
            result_package is not None
            or not self.capture_new_package
            or location_dest.usage in ("production", "inventory")
        ):
            return result_package
        return self.env["stock.package"].create(
            {"package_type_id": self.capture_package_type_id.id}
        )
