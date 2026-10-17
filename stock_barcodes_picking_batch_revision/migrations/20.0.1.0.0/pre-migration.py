# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).


def migrate(cr, version):
    """Batch transfers are part of stock in 20.0: this module now depends on
    stock_barcodes, which reads them, instead of stock_barcodes_picking_batch.
    The review fields keep their names."""
