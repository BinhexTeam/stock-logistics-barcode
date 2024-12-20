/** @odoo-module */

import {BarcodeFormRenderer} from "../form/form_renderer.esm";
import {formView} from "@web/views/form/form_view";
import {registry} from "@web/core/registry";

export const BarcodeScannerFormView = {
    ...formView,
    Renderer: BarcodeFormRenderer,
};

registry.category("views").add("barcode_scanner", BarcodeScannerFormView);
