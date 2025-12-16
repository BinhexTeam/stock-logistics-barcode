/* @odoo-module */

import {ListController} from "@web/views/list/list_controller";
import {listView} from "@web/views/list/list_view";
import {registry} from "@web/core/registry";
import {Domain} from "@web/core/domain";

/**
 * List controller for stock pickings that listens to raw barcode scans
 * (global key events) and reloads the list with an augmented domain.
 *
 * It does not require focus on the search bar: scanners typing into the
 * page will be captured here. When a code arrives, we rebuild the action
 * with an extra domain covering picking name/origin and any product on
 * the picking (barcode, internal ref, display name).
 */
export class PickingBarcodeListController extends ListController {
    setup() {
        super.setup(...arguments);
        this._barcodeBuffer = "";
        this._onKeydown = this.onBarcodeKeydown.bind(this);
        window.addEventListener("keydown", this._onKeydown);
    }

    willUnmount() {
        window.removeEventListener("keydown", this._onKeydown);
        super.willUnmount(...arguments);
    }

    async onBarcodeKeydown(ev) {
        // Ignore modifier-only keys
        if (ev.key === "Shift" || ev.key === "Alt" || ev.key === "Control" || ev.key === "Meta") {
            return;
        }
        // Finish scan on Enter
        if (ev.key === "Enter") {
            const code = this._barcodeBuffer.trim();
            this._barcodeBuffer = "";
            if (code) {
                await this.applyBarcodeFilter(code);
            }
            return;
        }
        // Build buffer from printable keys
        if (ev.key.length === 1) {
            this._barcodeBuffer += ev.key;
        }
    }

    _buildScannedDomain(code) {
        // Picking identifiers (exact match for label scans)
        const pickingDomain = Domain.or([
            Domain.fromList([["name", "=", code]]),
            Domain.fromList([["origin", "=", code]]),
        ]);

        // Product lookups (barcode exact, others fuzzy)
        const productDomain = Domain.or([
            Domain.fromList([["move_ids.product_id.barcode_ids.name", "in", [code]]]),
            Domain.fromList([["move_ids.product_id.barcode", "=", code]]),
            Domain.fromList([["move_ids.product_id.default_code", "ilike", code]]),
            Domain.fromList([["move_ids.product_id.display_name", "ilike", code]]),
        ]);

        return Domain.or([pickingDomain, productDomain]);
    }

    async applyBarcodeFilter(code) {
        const baseDomain = Domain.fromList(this.props.domain || []);
        const scannedDomain = this._buildScannedDomain(code);
        const finalDomain = Domain.and([baseDomain, scannedDomain]).toList();

        // Re-trigger the same action with the narrowed domain so the UI updates
        const action = {
            ...this.props.action,
            domain: finalDomain,
        };
        await this.actionService.doAction(action, {replaceCurrentAction: true});
    }
}

export const pickingBarcodeListView = {
    ...listView,
    Controller: PickingBarcodeListController,
};

registry.category("views").add("stock_picking_barcode_list", pickingBarcodeListView);
