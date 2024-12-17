/** @odoo-module */

import * as BarcodeScanner from "@web/webclient/barcode/barcode_scanner";
import {FormRenderer} from "@web/views/form/form_renderer";

export class BarcodeFormRenderer extends FormRenderer {
    async setup() {
        super.setup();
        console.warn("Initial BarcodeFormRenderer");
    }

    async openBarcodeScanner() {
        this.barcode = await BarcodeScanner.scanBarcode();
    }
}
