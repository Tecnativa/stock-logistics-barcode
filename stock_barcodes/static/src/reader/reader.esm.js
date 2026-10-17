/* Copyright 2026 Tecnativa - Carlos Dauden
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). */
import {Component, onMounted, onPatched, usePlugin, useProps} from "@odoo/owl";
import {useBus, useService} from "@web/core/utils/hooks";
import {BarcodePlugin} from "@barcodes/barcode_plugin";
import {registry} from "@web/core/registry";
import {isBarcodeScannerSupported} from "@web/core/barcode/barcode_video_scanner";
import {scanBarcode} from "@web/core/barcode/barcode_dialog";
import {standardWidgetProps} from "@web/views/widgets/standard_widget_props";

const SOUNDS = {
    ok: "/stock_barcodes/static/src/sounds/bell.wav",
    ko: "/stock_barcodes/static/src/sounds/error.wav",
};

/**
 * Reads the barcodes of a capture session: the barcode scanner, or a barcode
 * typed by hand. stock_capture processes them, and the session tells what to
 * play, show and focus after each reading or action.
 */
export class StockBarcodesReader extends Component {
    static template = "stock_barcodes.Reader";
    props = useProps(standardWidgetProps);

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.barcode = usePlugin(BarcodePlugin);
        this.lastFeedback = this.record.data.feedback_seq;
        this.cameraSupported = isBarcodeScannerSupported();
        useBus(this.barcode.bus, "barcode_scanned", (ev) =>
            this.onBarcodeScanned(ev.detail.barcode)
        );
        onMounted(() => this.focusInput());
        onPatched(() => this.giveFeedback());
    }

    get record() {
        return this.props.record;
    }

    get messageClass() {
        const type = this.record.data.message_type || "info";
        return `alert-${type}`;
    }

    async onBarcodeScanned(barcode) {
        if (!barcode || !this.record.resId) {
            return;
        }
        if (this.record.isDirty) {
            await this.record.save();
        }
        const result = await this.orm.call("stock.capture.session", "capture_barcode", [
            [this.record.resId],
            barcode,
        ]);
        if (result.action) {
            await this.action.doAction(result.action);
            return;
        }
        await this.record.load();
        this.giveFeedback();
    }

    /** Play the sound, show the notification and focus the field asked by the
     * session after a reading or an action */
    giveFeedback() {
        const data = this.record.data;
        if (!data.feedback_seq || data.feedback_seq === this.lastFeedback) {
            return;
        }
        this.lastFeedback = data.feedback_seq;
        if (data.feedback_sound && SOUNDS[data.feedback_sound]) {
            new Audio(SOUNDS[data.feedback_sound]).play().catch(() => false);
        }
        if (data.feedback_notification) {
            this.notification.add(data.feedback_notification, {type: "danger"});
        }
        if (data.feedback_focus) {
            const input = document.querySelector(
                `.o_stock_barcodes_form [name='${data.feedback_focus}'] input`
            );
            if (input) {
                input.focus();
                input.select();
                return;
            }
        }
        this.focusInput();
    }

    focusInput() {
        if (this.record.data.manual_entry) {
            return;
        }
        document.querySelector(".o_stock_barcodes_input")?.focus();
    }

    /** Read a barcode with the camera of the device */
    async onCameraClick() {
        let barcode = false;
        try {
            barcode = await scanBarcode(this.env);
        } catch (error) {
            this.notification.add(error.message, {type: "danger"});
            return;
        }
        await this.onBarcodeScanned(barcode);
    }

    onInputKeydown(ev) {
        if (ev.key !== "Enter") {
            return;
        }
        const barcode = ev.target.value.trim();
        ev.target.value = "";
        this.onBarcodeScanned(barcode);
    }
}

registry.category("view_widgets").add("stock_barcodes_reader", {
    component: StockBarcodesReader,
    fieldDependencies: [
        {name: "message", type: "char"},
        {name: "message_type", type: "selection"},
        {name: "step_message", type: "char"},
        {name: "manual_entry", type: "boolean"},
        {name: "feedback_seq", type: "integer"},
        {name: "feedback_sound", type: "selection"},
        {name: "feedback_focus", type: "char"},
        {name: "feedback_notification", type: "char"},
    ],
});
