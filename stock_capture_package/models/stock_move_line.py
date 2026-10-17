# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models

from odoo.addons.web.controllers.utils import clean_action


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _capture_package_label_action(self):
        """Action printing the labels of the destination packages of these
        lines, when their operation type prints the package label on "Put in
        Pack", as Odoo does when putting in pack.

        :return: the report action, or ``False`` when there is nothing to print
        """
        packages = self.result_package_id
        picking_type = self.move_id.picking_type_id[:1]
        print_format = picking_type.package_label_to_print
        if (
            not packages
            or not picking_type.auto_print_package_label
            or print_format not in ("pdf", "zpl")
        ):
            return False
        action = self.env["stock.package.label.layout"]._process_package_labels(
            packages, print_format
        )
        clean_action(action, self.env)
        return action
