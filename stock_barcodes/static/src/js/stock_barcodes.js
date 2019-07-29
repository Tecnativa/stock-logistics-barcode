/* Copyright 2018-2019 Sergio Teruel <sergio.teruel@tecnativa.com>.
 * License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl). */

odoo.define('stock_barcodes.FormController', function(require) {
    'use strict';

    var FormController = require('web.FormController');

    FormController.include({
        _barcodeScanned: function (barcode, target) {
            var self = this;
            var res = this._super(barcode, target);
            res.then(function () {
                self.saveRecord(this.handle, {'stayInEdit': true});
                console.log('Ejecutar post action');
            });
            return res;
        },
    });
});
