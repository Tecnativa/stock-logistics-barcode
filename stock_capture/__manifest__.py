# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Stock Capture",
    "summary": "Engine of the screens reading or weighing quantities on stock "
    "documents",
    "version": "20.0.1.0.0",
    "category": "Inventory/Inventory",
    "website": "https://github.com/OCA/stock-logistics-barcode",
    "author": "Tecnativa, Odoo Community Association (OCA)",
    "maintainers": ["carlosdauden"],
    "development_status": "Alpha",
    "license": "AGPL-3",
    "depends": ["stock"],
    "data": [
        "security/ir.access.csv",
        "data/stock_capture_profile_data.xml",
        "views/stock_capture_profile_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
}
