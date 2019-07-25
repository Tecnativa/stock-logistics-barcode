/* Copyright 2018-2019 Sergio Teruel <sergio.teruel@tecnativa.com>.
 * License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl). */

odoo.define('gtin_gs1.BarcodeParser', function(require) {
    'use strict';

    var BarcodeParser = require('barcodes.BarcodeParser');
    
    BarcodeParser.include({
        
        /* It performs GS-1 checksum operation
         * :param barcode: Barcode string to validate, including check digit
         * :return: ``int`` representing calculated checksum
         **/
        gs1_checksum: function(barcode) {
            if (barcode.length !== 18) {
                return -1;
            }
            barcode = barcode.slice(0, -1);
            var total = 0;
            _.each(barcode, function(digit, idx) {
                digit = parseInt(digit);
                if (isNaN(digit)) {
                    return -1;
                }
                if (idx % 2 === 1) {
                    total += digit;
                } else {
                    total += (3 * digit);
                }
            });
            var check_digit = (10 - (total % 10)) % 10;
            return check_digit;
        },
        
        // It adds additional types to the core encodings
        check_encoding: function(barcode, encoding) {
            var self = this;
            if (encoding === 'gs1') {
                var check_digit = parseInt(barcode.slice(-1));
                if (isNaN(check_digit)) {
                    return false;
                }
                return _.every([
                    /^\d+$/.test(barcode),
                    self.ean14_checksum(barcode) == check_digit,
                ]);
            }
            return this._super(barcode, encoding);
        },
    });
    return BarcodeParser;
});
