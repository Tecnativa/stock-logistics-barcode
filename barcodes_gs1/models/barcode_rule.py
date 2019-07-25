# Copyright 2018-2019 Sergio Teruel <sergio.teruel@tecantiva.com>.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class BarcodeRule(models.Model):
    _inherit = 'barcode.rule'

    encoding = fields.Selection(
        selection_add=[('gs1-128', 'GS1-128')],
    )
