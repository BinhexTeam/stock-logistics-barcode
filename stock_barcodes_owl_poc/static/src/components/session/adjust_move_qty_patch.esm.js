/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";

import {BarcodeSessionRoot} from "@stock_barcodes/components/session/session.esm";

patch(BarcodeSessionRoot.prototype, {
    async adjustMoveQty(move, delta) {
        const moveId = move.id;
        const result = await this.orm.call(
            "wiz.stock.barcode.session",
            "adjust_move_done_qty",
            [[this.sessionId], moveId, delta],
            {context: this.props.action?.context}
        );
        if (result?.picking) {
            this.state.payload = {
                ...(this.state.payload || {}),
                picking: result.picking,
            };
        }
    },
});
