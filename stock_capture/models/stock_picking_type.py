# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    def _capture_result_package(self, result_package, location_dest):
        """Destination package of a capture going to the given location.

        :param result_package: the package given by the user, ``None`` when
            none was given and an empty recordset to capture without package
        :return: the package to capture into, with the same meaning
        """
        return result_package
