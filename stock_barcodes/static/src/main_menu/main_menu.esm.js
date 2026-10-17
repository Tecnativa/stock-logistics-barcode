/* Copyright 2026 Tecnativa - Carlos Dauden
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). */
import {Component, onWillStart, proxy, usePlugin} from "@odoo/owl";
import {useBus, useService} from "@web/core/utils/hooks";
import {BarcodePlugin} from "@barcodes/barcode_plugin";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";

/**
 * Main menu of the barcode screens: a tile per barcode action. Reading the
 * barcode of an action opens it too.
 */
export class StockBarcodesMainMenu extends Component {
    static template = "stock_barcodes.MainMenu";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = proxy({tiles: []});
        this.barcode = usePlugin(BarcodePlugin);
        useBus(this.barcode.bus, "barcode_scanned", (ev) =>
            this.onBarcodeScanned(ev.detail.barcode)
        );
        onWillStart(async () => {
            this.state.tiles = await this.orm.call(
                "stock.barcodes.action",
                "get_main_menu",
                []
            );
        });
    }

    async openTile(tile) {
        const action = await this.orm.call("stock.barcodes.action", "open_action", [
            [tile.id],
        ]);
        await this.action.doAction(action);
    }

    async onBarcodeScanned(barcode) {
        const action = await this.orm.call("stock.barcodes.action", "open_by_barcode", [
            barcode,
        ]);
        if (action) {
            await this.action.doAction(action);
        } else {
            this.notification.add(_t("Barcode %s not found", barcode), {
                type: "danger",
            });
        }
    }
}

registry.category("actions").add("stock_barcodes_main_menu", StockBarcodesMainMenu);
