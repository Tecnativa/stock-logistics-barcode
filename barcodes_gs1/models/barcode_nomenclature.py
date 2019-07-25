# Copyright 2018-2019 Sergio Teruel <sergio.teruel@tecantiva.com>.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models


class BarcodeNomenclature(models.Model):
    _inherit = 'barcode.nomenclature'

    def gs1_checksum(self, barcode):
        """ It performs GS-1 checksum operation
        :param barcode: Barcode string to validate, including check digit
        :return: ``int`` representing calculated checksum
        """
        if len(barcode) != 18:
            return -1
        barcode = barcode[:-1]
        total = 0
        for (idx, digit) in enumerate(barcode):
            try:
                digit = int(digit)
            except ValueError:
                return -1
            if idx % 2 == 1:
                total += digit
            else:
                total += (3 * digit)
        check_digit = (10 - (total % 10)) % 10
        return check_digit

    def check_encoding(self, barcode, encoding):
        """ It adds additional types to the core encodings """
        if encoding == 'gs1':
            pass
        return super(BarcodeNomenclature, self).check_encoding(
            barcode, encoding,
        )
