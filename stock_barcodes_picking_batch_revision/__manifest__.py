# Copyright 2024 Tecnativa - Sergio Teruel
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Stock Barcodes Picking Batch Revision",
    "summary": "Review with barcodes the batch transfers prepared by other users",
    "version": "20.0.1.0.0",
    "author": "Tecnativa, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-logistics-barcode",
    "license": "AGPL-3",
    "maintainers": ["carlosdauden"],
    "category": "Inventory/Inventory",
    "depends": ["stock_barcodes"],
    "data": [
        "views/stock_picking_batch_views.xml",
        "views/stock_capture_session_views.xml",
        "data/stock_barcodes_action_data.xml",
    ],
}
