# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, models


class WizStockBarcodesRead(models.TransientModel):
    _inherit = 'wiz.stock.barcodes.read'

    def _prepare_lot_values(self, barcode_decoded):
        lot_barcode = barcode_decoded.get('10', False)
        return {
            'name': lot_barcode,
            'product_id': self.product_id.id,
        }

    def _create_lot(self, barcode_decoded):
        return self.env['stock.production.lot'].create(
            self._prepare_lot_values(barcode_decoded))

    def process_lot(self, barcode_decoded):
        lot_barcode = barcode_decoded.get('10', False)
        lot = self.env['stock.production.lot'].search([
            ('name', '=', lot_barcode),
            ('product_id', '=', self.product_id.id),
        ])
        if not lot:
            lot = self._create_lot(barcode_decoded)
        self.lot_id = lot

    def process_barcode(self, barcode):
        try:
            barcode_decoded = self.env['gs1_barcode'].decode(barcode)
        except Exception:
            return super().process_barcode(barcode)
        package_barcode = barcode_decoded.get('01', False)
        product_barcode = barcode_decoded.get('02', False)
        lot_barcode = barcode_decoded.get('10', False)
        product_qty = barcode_decoded.get('37', False)
        if product_barcode:
            product = self.env['product.product'].search(
                self._barcode_domain(product_barcode))
            if product:
                if len(product) > 1:
                    self._set_messagge_info(
                        'more_match', _('More than one product found'))
                    return False
                self.action_product_scaned_post(product)
        if package_barcode:
            packaging = self.env['product.packaging'].search(
                self._barcode_domain(package_barcode))
            if packaging:
                if len(packaging) > 1:
                    self._set_messagge_info(
                        'more_match', _('More than one package found'))
                    return False
                self.action_packaging_scaned_post(packaging)
        if lot_barcode and self.product_id.tracking != 'none':
            self.process_lot(barcode_decoded)
        if product_qty:
            self.product_qty = product_qty
        if not self.product_id and not self.packaging_id and not self.lot_id:
            self._set_messagge_info('not_found', _('Barcode no found'))
            return False
        self.action_done()
        return self._set_messagge_info('success', _('Barcode read correctly'))
