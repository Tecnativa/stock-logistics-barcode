/* Copyright 2026 Tecnativa - Carlos Dauden
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). */
import {registry} from "@web/core/registry";

const PRODUCT_CARD = ".o_stock_barcodes_card:has(a:contains('Tour product'))";

registry.category("web_tour.tours").add("stock_barcodes_scan", {
    steps: () => [
        {
            content: "Read the product barcode",
            trigger: ".o_stock_barcodes_input",
            run: "edit 1234567890128 && press Enter",
        },
        {
            content: "The product is captured",
            trigger: ".o_stock_barcodes_message.alert-success:contains('Tour product')",
        },
        {
            content: "Read the lot product: its only lot in stock is proposed",
            trigger: ".o_stock_barcodes_input",
            run: "edit 2345678901234 && press Enter",
        },
        {
            trigger:
                ".o_stock_barcodes_message.alert-success:contains('Tour lot product')",
        },
        {
            content: "Capture what is left of the first product, shown on the button",
            trigger: `${PRODUCT_CARD} button[name='action_capture_card_remaining']:contains('2')`,
            run: "click",
        },
        {
            trigger: `.o_stock_barcodes_cards:not(:has(${PRODUCT_CARD} button[name='action_capture_card_remaining']))`,
        },
        {
            content: "Validate the transfer",
            trigger: ".o_form_statusbar button[name='action_validate']",
            run: "click",
        },
        {
            content: "Create the backorder",
            trigger: ".modal button[name='process']",
            run: "click",
        },
        {
            content: "Back to the transfers to read",
            trigger: ".o_list_view",
        },
    ],
});
