/** @odoo-module **/

import {Component} from "@odoo/owl";
import {barcodeSessionPanelsRegistry} from "../extension/registry.esm";

/**
 * Renders extra panels registered by other modules.
 *
 * Each panel descriptor is:
 * { Component: SomeComponent, props?: (rootProps) => object, sequence?: number }
 */
export class BarcodeSessionExtensionPanels extends Component {
    get panels() {
        const items = [];
        for (const [key, value] of barcodeSessionPanelsRegistry.getEntries()) {
            items.push({key, ...(value || {})});
        }
        items.sort((a, b) => (a.sequence || 100) - (b.sequence || 100));
        return items;
    }

    panelProps(panel) {
        if (typeof panel.props === "function") {
            return panel.props(this.props.root || {});
        }
        return panel.props || {};
    }
}

BarcodeSessionExtensionPanels.template = "stock_barcodes.BarcodeSessionExtensionPanels";
