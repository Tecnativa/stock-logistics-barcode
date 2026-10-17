# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Stock Barcodes MRP",
    "summary": "Read barcodes on manufacturing orders",
    "version": "20.0.1.0.0",
    "author": "Tecnativa, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-logistics-barcode",
    "license": "AGPL-3",
    "maintainers": ["carlosdauden"],
    "development_status": "Alpha",
    "category": "Manufacturing/Manufacturing",
    "depends": ["stock_barcodes", "mrp_capture"],
    "data": ["views/mrp_production_views.xml"],
    "auto_install": True,
}
