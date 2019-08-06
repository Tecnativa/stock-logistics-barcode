# Copyright 2108-2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.stock_barcodes.tests.test_stock_barcodes_common import\
    TestStockBarcodesCommon


class TestStockBarcodesNewLot(TestStockBarcodesCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScanReadLot = cls.env['wiz.stock.barcodes.new.lot']
        cls.wiz_scan_lot = cls.ScanReadLot.new()

    def test_new_lot(self):
        self.action_barcode_scanned(self.wiz_scan_lot, '8433281006850')
        self.assertEqual(self.wiz_scan_lot.product_id, self.product_tracking)
        self.action_barcode_scanned(self.wiz_scan_lot, '8433281xy6850')
        self.assertEqual(self.wiz_scan_lot.lot_name, '8433281xy6850')
        new_lot = self.wiz_scan_lot.confirm()
        self.assertEqual(self.wiz_scan_lot.lot_name, new_lot.name)
