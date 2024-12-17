/** @odoo-module **/

import {BarcodeDialog} from "@web/webclient/barcode/barcode_scanner";
import {browser} from "@web/core/browser/browser";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";

patch(BarcodeDialog.prototype, "stock_barcodes.BarcodeScanner", {
    /* eslint-disable no-unused-vars */
    setup() {
        this._super(...arguments);
        this.rpc = useService("rpc");
    },
    onResult(barcode) {
        this.camera_barcode_scanner(barcode);
        super.onResult(...arguments);
    },
    camera_barcode_scanner(barcode) {
        this.rpc({
            model: "wiz.stock.barcodes.read",
            method: "camera_barcode_scanner",
            kwargs: {
                barcode: barcode.replace(/Alt|Shift|Control/g, ""),
                location_hash: browser.location.hash,
            },
        });
        browser.location.reload();
    },
});
