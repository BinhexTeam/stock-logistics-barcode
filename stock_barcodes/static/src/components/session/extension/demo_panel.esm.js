/** @odoo-module **/

import {Component} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";

import {barcodeSessionPanelsRegistry} from "../extension/registry.esm";

export class BarcodeSessionDemoPanel extends Component {
    static template = "stock_barcodes.BarcodeSessionDemoPanel";

    get pickingName() {
        return this.props?.root?.picking?.name || "";
    }
}

barcodeSessionPanelsRegistry.add("stock_barcodes.demo_panel", {
    sequence: 10,
    Component: BarcodeSessionDemoPanel,
    title: _t("Demo panel"),
});
