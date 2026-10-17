# Copyright 2019 Sergio Teruel <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Stock Barcodes",
    "summary": "Screens to read barcodes on stock operations and inventories",
    "version": "20.0.1.0.0",
    "author": "Tecnativa, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-logistics-barcode",
    "license": "AGPL-3",
    "maintainers": ["carlosdauden", "sergio-teruel"],
    "category": "Inventory/Inventory",
    "depends": ["barcodes", "stock_capture", "web_widget_numeric_step"],
    "data": [
        "security/ir.access.csv",
        "data/stock_barcodes_action_data.xml",
        "views/stock_capture_session_views.xml",
        "views/stock_barcodes_action_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_picking_type_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_barcodes/static/src/**/*.esm.js",
            "stock_barcodes/static/src/**/*.xml",
            "stock_barcodes/static/src/**/*.scss",
        ],
        "web.assets_tests": [
            "stock_barcodes/static/tests/tours/*.esm.js",
        ],
    },
}
