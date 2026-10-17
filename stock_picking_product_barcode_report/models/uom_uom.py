# Copyright 2024 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class UomUom(models.Model):
    _inherit = "uom.uom"

    print_one_label_by_item = fields.Boolean(
        help="If checked, Odoo takes into account the units included in this "
        "packaging unit to compute the number of labels"
    )
