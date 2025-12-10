/** @odoo-module **/

import {registry} from "@web/core/registry";

/**
 * Extension points for the Barcode Session UI.
 *
 * Other modules can register additional panels that will be rendered in the session
 * screen without patching the core JS component.
 *
 * Usage (in another module):
 *   import {barcodeSessionPanelsRegistry} from "stock_barcodes/.../registry.esm";
 *   barcodeSessionPanelsRegistry.add("my_module.panel", { Component: MyPanel, sequence: 50 });
 */
export const barcodeSessionPanelsRegistry = registry.category(
    "stock_barcodes.barcode_session_panels"
);
