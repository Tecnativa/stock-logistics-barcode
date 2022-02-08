/* Copyright 2022 Tecnativa - Alexandre D. Díaz
 * License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl). */

odoo.define("stock_barcodes.BarcodesModelsMixin", function(require) {
    "use strict";


    const BarcodesModelsMixin = {
        // Models allowed to have extra keybinding features
        _barcode_models: [
            "wiz.stock.barcodes.read",
            "wiz.stock.barcodes.read.picking",
            "wiz.stock.barcodes.read.inventory",
            "stock.picking.type",
            "stock.picking",
            "wiz.stock.barcodes.read.todo",
            "stock.barcodes.action",
        ],

        /**
         * Helper to know if the given model is allowed
         *
         * @private
         * @returns {Boolean}
         */
        _isAllowedBarcodeModel: function(model_name) {
            return this._barcode_models.indexOf(model_name) !== -1;
        },
    };

    return BarcodesModelsMixin;
});
