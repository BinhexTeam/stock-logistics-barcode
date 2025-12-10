/** @odoo-module **/

import {Component} from "@odoo/owl";

/**
 * Pure presentational header. Keep logic in the root component.
 *
 * Props:
 * - profile, picking, inventory, profileBadges
 * - onBack, onReload, onOpenPicking
 */
export class BarcodeSessionHeader extends Component {
    get hasPicking() {
        return Boolean(this.props.picking);
    }
}

BarcodeSessionHeader.template = "stock_barcodes.BarcodeSessionHeader";
