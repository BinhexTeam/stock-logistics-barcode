/** @odoo-module **/

import {Component, useRef} from "@odoo/owl";

/**
 * Scan panel.
 *
 * Props:
 * - scanForm, scanResult, scanAlertClass, sessionMeta, profile
 * - onBarcodeInput, onQuantityInput, onSubmit
 * - barcodeInputRefName (string)
 */
export class BarcodeSessionScanPanel extends Component {
    setup() {
        this.inputRef = useRef(this.props.barcodeInputRefName || "barcodeInput");
    }
}

BarcodeSessionScanPanel.template = "stock_barcodes.BarcodeSessionScanPanel";
