/** @odoo-module */

import * as BarcodeScanner from "@web/webclient/barcode/barcode_scanner";
import { browser } from "@web/core/browser/browser";
import { FormRenderer } from "@web/views/form/form_renderer";
import { patch } from "@web/core/utils/patch";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

patch(FormRenderer.prototype, {
    setup() {
        super.setup(...arguments);

        this.orm = useService("orm");
        this.action = useService("action");

        this._onGlobalBarcodeCameraTriggerClick =
            this._onGlobalBarcodeCameraTriggerClick.bind(this);

        onMounted(() => {
            document.addEventListener("click", this._onGlobalBarcodeCameraTriggerClick, true);
        });

        onWillUnmount(() => {
            document.removeEventListener("click", this._onGlobalBarcodeCameraTriggerClick, true);
        });
    },

    async _onGlobalBarcodeCameraTriggerClick(ev) {
        const trigger = ev.target?.closest?.(".o_barcode_camera_trigger");
        if (!trigger) return;

        // Only react inside our injected scope
        const scope = trigger.closest?.(".o_barcode_camera_scope");
        if (!scope) return;

        ev.preventDefault();
        ev.stopPropagation();

        try {
            // 1) Open camera scanner => returns scanned string
            const barcode = await BarcodeScanner.scanBarcode(this.env, "environment");

            // 2) Call your server method (it resolves wizard from location_hash)
            await this.orm.call(
                "wiz.stock.barcodes.read",
                "camera_barcode_scanner",
                [],
                {
                    barcode: (barcode || "").replace(/Alt|Shift|Control/g, ""),
                    location_hash: browser.location.hash,
                }
            );

            // 3) Reload current action/view (immediate UI refresh, no browser reload)
            await this.action.doAction({ type: "ir.actions.client", tag: "reload" });
        } catch (err) {
            // If camera permissions / device issues occur, you'll see it here
            console.error("stock_barcodes_camera: scan/apply failed:", err);
        }
    },
});
