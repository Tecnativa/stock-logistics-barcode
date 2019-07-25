# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models
from odoo.fields import first
from odoo.addons import decimal_precision as dp


class WizStockBarcodesReadInventory(models.TransientModel):
    _inherit = 'wiz.stock.barcodes.read'
    _name = 'wiz.stock.barcodes.read.inventory'
    _description = 'Wizard to read barcode on inventory'

    inventory_id = fields.Many2one(
        comodel_name='stock.inventory',
        string='Inventory',
        readonly=True,
    )
    inventory_product_qty = fields.Float(
        string='Inventory quantities',
        digits=dp.get_precision('Product Unit of Measure'),
        readonly=True,
    )

    def _prepare_inventory_line(self):
        return {
            'inventory_id': self.inventory_id.id,
            'product_id': self.product_id.id,
            'location_id': self.location_id.id,
            'product_uom_id': self.product_id.uom_id.id,
            'product_qty': self.product_qty,
            'prod_lot_id': self.lot_id.id,
        }

    def _add_inventory_line(self):
        if not self.product_qty:
            return
        StockInventoryLine = self.env['stock.inventory.line']
        line = first(StockInventoryLine.search([
            ('inventory_id', '=', self.inventory_id.id),
            ('product_id', '=', self.product_id.id),
            ('location_id', '=', self.location_id.id),
            ('prod_lot_id', '=', self.lot_id.id),
        ]))
        if line:
            line.write({
                'product_qty': line.product_qty + self.product_qty,
            })
        else:
            line = StockInventoryLine.create(self._prepare_inventory_line())
        self.inventory_product_qty = line.product_qty

    def action_done(self):
        self._add_inventory_line()

    def action_manual_entry(self):
        super().action_manual_entry()
        self._add_inventory_line()

    def reset_qty(self):
        super().reset_qty()
        self.inventory_product_qty = 0.0

    def action_remove_last_scan(self):
        res = super().action_remove_last_scan()
        log_scan = first(self.scan_log_ids.filtered(
            lambda x: x.create_uid == self.env.user))
        if log_scan:
            inventory_line = self.env['stock.inventory.line'].search([
                ('inventory_id', '=', self.inventory_id.id),
                ('product_id', '=', log_scan.product_id.id),
                ('location_id', '=', log_scan.location_id.id),
                ('prod_lot_id', '=', log_scan.lot_id.id),
            ])
            if inventory_line:
                inventory_line.product_qty -= log_scan.product_qty
                self.inventory_product_qty = inventory_line.product_qty
        log_scan.unlink()
        return res
