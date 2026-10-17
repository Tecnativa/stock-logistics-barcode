# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_barcode_scan(self):
        """Open the barcode reading screen of the transfer"""
        return self.action_capture_open()
