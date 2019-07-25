# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.addons import decimal_precision as dp


class WizStockBarcodesRead(models.TransientModel):
    _inherit = 'barcodes.barcode_events_mixin'
    _name = 'wiz.stock.barcodes.read'
    _description = 'Wizard to read barcode'

    barcode = fields.Char()
    res_model_id = fields.Many2one(
        comodel_name='ir.model',
        index=True,
    )
    res_id = fields.Integer(index=True)
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
    )
    lot_id = fields.Many2one(
        comodel_name='stock.production.lot',
        string='Lot scanned',
    )
    location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Location',
    )
    packaging_id = fields.Many2one(
        comodel_name='product.packaging',
        string='Packaging',
    )
    packaging_qty = fields.Float(
        string='Package Qty',
        digits=dp.get_precision('Product Unit of Measure'),
    )
    product_qty = fields.Float(
        string='Product Qty',
        digits=dp.get_precision('Product Unit of Measure'),
    )
    force_input_qty = fields.Boolean(
        string='Force input quantities',
    )
    scan_log_ids = fields.Many2many(
        comodel_name='stock.barcodes.read.log',
        compute='_compute_scan_log_ids',
    )
    message_info = fields.Html(readonly=True)

    @api.onchange('location_id')
    def onchange_location_id(self):
        self.packaging_id = False
        self.product_id = False

    @api.onchange('packaging_qty')
    def onchange_packaging_qty(self):
        if self.packaging_id:
            self.product_qty = self.packaging_qty * self.packaging_id.qty

    def name_get(self):
        return [
            (rec.id, _('Read barcode (%s)') % rec.env.user.name)
            for rec in self]

    def _get_messagge_info(self, type, messagge):
        return {
            'message_type': type,
            'message_info': messagge,
        }

    def process_barcode(self, barcode):
        message = self._get_messagge_info(
            'success', _('Barcode read correctly'))
        domain = self._barcode_domain(barcode)
        product = self.env['product.product'].search(domain)
        if product:
            if len(product) > 1:
                return self._get_messagge_info(
                    'danger', _('More than one product found'))
            self.action_product_scaned_post(product)
            self.action_done()
            return message
        packaging = self.env['product.packaging'].search(domain)
        if packaging:
            if len(packaging) > 1:
                return self._get_messagge_info(
                    'danger', _('More than one package found'))
            self.action_packaging_scaned_post(packaging)
            self.action_done()
            return message
        lot = self.env['stock.production.lot'].search([
            ('name', '=', barcode),
            ('product_id', '=', self.product_id.id),
        ])
        if lot:
            self.lot_id = lot
            return message
        location = self.env['stock.location'].search(domain)
        if location:
            self.location_id = location
            return message
        return self._get_messagge_info('danger', _('Barcode not found'))

    def _barcode_domain(self, barcode):
        return [('barcode', '=', barcode)]

    def on_barcode_scanned(self, barcode):
        self.packaging_id = False
        self.product_id = False
        self.lot_id = False
        self.barcode = barcode
        self.reset_qty()
        message = self.process_barcode(barcode)
        self.message_info = "<div class='alert alert-%(message_type)s'>" \
                            "%(message_info)s" \
                            "</div>" % message
        self._add_read_log()

    def action_done(self):
        pass

    def action_product_scaned_post(self, product):
        self.packaging_id = False
        self.product_id = product
        self.product_qty = 0.0 if self.force_input_qty else 1.0

    def action_packaging_scaned_post(self, packaging):
        self.packaging_id = packaging
        self.product_id = packaging.product_id
        self.packaging_qty = 0.0 if self.force_input_qty else 1.0
        self.product_qty = packaging.qty * self.packaging_qty

    def action_clean_lot(self):
        self.lot_id = False

    def action_manual_entry(self):
        self._add_read_log()
        return True

    def _prepare_scan_log_values(self):
        return {
            'name': self.barcode,
            'location_id': self.location_id.id,
            'product_id': self.product_id.id,
            'packaging_id': self.packaging_id.id,
            'lot_id': self.lot_id.id,
            'packaging_qty': self.packaging_qty,
            'product_qty': self.product_qty,
            'force_input_qty': self.force_input_qty,
            'res_model_id': self.res_model_id.id,
            'res_id': self.res_id,
        }

    def _add_read_log(self):
        if self.product_qty:
            self.env['stock.barcodes.read.log'].create(
                self._prepare_scan_log_values())

    @api.depends('_barcode_scanned')
    def _compute_scan_log_ids(self):
        logs = self.env['stock.barcodes.read.log'].search([
            ('res_model_id', '=', self.res_model_id.id),
            ('res_id', '=', self.res_id),
            ('location_id', '=', self.location_id.id),
            ('product_id', '=', self.product_id.id),
        ], limit=10)
        self.scan_log_ids = logs

    def reset_qty(self):
        self.product_qty = 0
        self.packaging_qty = 0

    def action_remove_last_scan(self):
        pass
