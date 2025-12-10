/** @odoo-module **/
import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";
import {useEffect} from "@odoo/owl";
import {KanbanController} from "@web/views/kanban/kanban_controller";

const originalOpenRecord = KanbanController.prototype.openRecord;

patch(KanbanController.prototype, {
    setup() {
        super.setup();
        this.ormService = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");
        this.barcodeService = this.env.services.barcode ? useService("barcode") : null;
        this.scanFilterGroupId = null;

        if (this.barcodeService && this.props.resModel === "stock.picking") {
            useEffect(
                () => {
                    const handler = (event) =>
                        this._onPickingBarcodeScanned(event.detail?.barcode);
                    this.barcodeService.bus.addEventListener(
                        "barcode_scanned",
                        handler
                    );
                    return () => {
                        this.barcodeService.bus.removeEventListener(
                            "barcode_scanned",
                            handler
                        );
                    };
                },
                () => [this.barcodeService]
            );
        }
    },

    async openRecord(record, mode) {
        if (
            this._isBarcodeOperationsMode() &&
            this.props.resModel === "stock.picking"
        ) {
            try {
                await this._openBarcodeInterface(record, mode);
            } catch (error) {
                this.notification.add(error.message, {type: "danger"});
                throw error;
            }
            return;
        }
        return originalOpenRecord.call(this, record, mode);
    },

    _getSearchGroupIds() {
        if (!this.env.searchModel || !this.env.searchModel._getGroups) {
            return [];
        }
        return this.env.searchModel._getGroups().map((group) => group.id);
    },

    _isBarcodeOperationsMode() {
        const searchContext = this.env.searchModel?.context || {};
        return Boolean(
            searchContext.operations_mode || this.props.context?.operations_mode
        );
    },

    async _openBarcodeInterface(record, mode) {
        const searchContext = this.env.searchModel?.context || {};
        const actionContext = {...this.props.context, ...searchContext};
        let action = null;
        try {
            action = await this.ormService.call(
                "stock.picking",
                "action_barcode_scan",
                [[record.resId]],
                {context: actionContext}
            );
        } catch (error) {
            return originalOpenRecord.call(this, record, mode);
        }
        if (!action) {
            return originalOpenRecord.call(this, record, mode);
        }
        await this.actionService.doAction(action);
    },

    async _onPickingBarcodeScanned(rawBarcode) {
        if (
            !rawBarcode ||
            this.props.resModel !== "stock.picking" ||
            !this.env.searchModel
        ) {
            return;
        }
        const barcode = String(rawBarcode).trim();
        if (!barcode) {
            return;
        }
        try {
            const context = this.env.searchModel.context || this.props.context || {};
            const prevGroupIds = this._getSearchGroupIds();
            const result = await this.ormService.call(
                "stock.picking",
                "get_barcode_filter_domain",
                [barcode],
                {context}
            );
            if (!result || !result.domain) {
                this.notification.add(
                    _t("No transfer or product matches barcode %(barcode)s.", {
                        barcode,
                    }),
                    {type: "warning"}
                );
                return;
            }

            await this.env.searchModel.splitAndAddDomain(
                result.domain,
                this.scanFilterGroupId
            );
            const nextGroupIds = this._getSearchGroupIds();
            const newGroupId = nextGroupIds.find((id) => !prevGroupIds.includes(id));
            if (newGroupId) {
                this.scanFilterGroupId = newGroupId;
            }
            this.env.searchModel.search();

            const label = result.label || barcode;
            const message =
                result.match === "picking"
                    ? _t("Filtered by transfer %(label)s", {label})
                    : _t("Filtered by product %(label)s", {label});
            this.notification.add(message, {type: "success"});
        } catch (error) {
            this.notification.add(error.message, {type: "danger"});
            throw error;
        }
    },
});
