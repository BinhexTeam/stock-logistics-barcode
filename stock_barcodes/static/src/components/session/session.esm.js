/** @odoo-module **/
import {Component, onWillStart, useRef, useState, useSubEnv} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {useBus, useService} from "@web/core/utils/hooks";

import {BarcodeSessionHeader} from "./panels/header.esm";
import {BarcodeSessionScanPanel} from "./panels/scan_panel.esm";
import {BarcodeSessionMovesTable} from "./panels/moves_table.esm";
import {BarcodeSessionChatter} from "./panels/chatter.esm";
import {BarcodeSessionExtensionPanels} from "./root/extension_panels.esm";

export class BarcodeSessionRoot extends Component {
    static components = {
        BarcodeSessionHeader,
        BarcodeSessionScanPanel,
        BarcodeSessionMovesTable,
        BarcodeSessionChatter,
        BarcodeSessionExtensionPanels,
    };

    setup() {
        useSubEnv({
            _t,
        });
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.router = useService("router");
        this.barcode = useService("barcode");
        this.state = useState({
            loading: true,
            payload: null,
        });
        this.scanFormState = useState({
            barcode: "",
            quantity: 1,
        });
        this.scanResultState = useState({
            status: "info",
            message: "",
            focusMoveId: null,
        });
        this.barcodeInputRef = useRef("barcodeInput");
        this.soundSuccess = this._createAudio(
            "/stock_barcodes/static/src/sounds/bell.wav"
        );
        this.soundWarning = this._createAudio(
            "/stock_barcodes/static/src/sounds/error.wav"
        );
        useBus(this.barcode.bus, "barcode_scanned", (event) => {
            this.onBarcodeScanned(event.detail?.barcode);
        });
        onWillStart(async () => {
            await this.loadPayload();
        });
    }

    get sessionId() {
        return (
            this.props.action?.context?.session_id ??
            this.props.context?.session_id ??
            this.env.searchModel?.context?.session_id
        );
    }

    async _ensureSessionId() {
        if (this.sessionId) {
            return this.sessionId;
        }
        // When launched from a generic ir.actions.client (no session_id),
        // create a session server-side using the action context.
        const actionContext = this.props.action?.context || {};
        const createdAction = await this.orm.call(
            "wiz.stock.barcode.session",
            "open_from_client_action",
            [],
            {context: actionContext}
        );
        // The returned value is another ir.actions.client that includes session_id.
        if (createdAction?.context?.session_id) {
            this.props.action.context = {
                ...(this.props.action.context || {}),
                session_id: createdAction.context.session_id,
            };
            return createdAction.context.session_id;
        }
        return null;
    }

    async loadPayload() {
        const sessionId = await this._ensureSessionId();
        if (!sessionId) {
            this.notification.add(_t("Missing barcode session identifier."), {
                type: "danger",
            });
            return;
        }
        this.state.loading = true;
        try {
            const payload = await this.orm.call(
                "wiz.stock.barcode.session",
                "get_session_payload",
                [sessionId],
                {context: this.props.action?.context}
            );
            this.state.payload = payload;
            this.scanResultState.focusMoveId = null;
            this.scanResultState.message = "";
            this.scanResultState.status = "info";
        } catch (error) {
            this.notification.add(error.message, {type: "danger"});
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    goBack() {
        // Navigate like the browser back button (webclient history).
        if (this.router?.back) {
            this.router.back();
            return;
        }
        // Fallbacks (should rarely be needed in the backend).
        if (window?.history?.back) {
            window.history.back();
            return;
        }
        return this.action.doAction({type: "ir.actions.act_window_close"});
    }

    async openPicking() {
        const pickingId = this.state.payload?.picking?.id;
        if (!pickingId) {
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "stock.picking",
            res_id: pickingId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    get profileBadges() {
        const profile = this.state.payload?.profile;
        if (!profile) {
            return [];
        }
        const badges = [];
        if (profile.allow_gs1_parsing) {
            badges.push({
                key: "gs1",
                label: _t("GS1"),
                title: _t("GS1 parsing enabled"),
            });
        }
        if (profile.lot_policy !== "disabled") {
            badges.push({key: "lots", label: _t("Lots"), title: _t("Lots / Serials")});
        }
        if (profile.package_policy !== "disabled") {
            badges.push({
                key: "packages",
                label: _t("Packages"),
                title: _t("Package handling"),
            });
        }
        return badges;
    }

    get messages() {
        return this.state.payload?.messages || [];
    }

    get picking() {
        return this.state.payload?.picking;
    }

    get profile() {
        return this.state.payload?.profile || {};
    }

    get sessionMeta() {
        return this.state.payload?.session || {};
    }

    get inventory() {
        return this.state.payload?.inventory;
    }

    get scanForm() {
        return this.scanFormState;
    }

    get scanResult() {
        return this.scanResultState;
    }

    onBarcodeInput(ev) {
        this.scanFormState.barcode = ev.target.value;
    }

    onQuantityInput(ev) {
        this.scanFormState.quantity = ev.target.value;
    }

    get scanAlertClass() {
        switch (this.scanResultState.status) {
            case "success":
                return "success";
            case "warning":
                return "warning";
            case "error":
                return "danger";
            default:
                return "info";
        }
    }

    moveRowClass(move) {
        return this.scanResultState.focusMoveId === move.id ? "table-primary" : "";
    }

    async submitScan(ev) {
        ev?.preventDefault();
        const barcode = (this.scanFormState.barcode || "").trim();
        if (!barcode) {
            this.notification.add(_t("Please scan or type a barcode first."), {
                type: "warning",
            });
            return;
        }
        if (!this.sessionId) {
            this.notification.add(_t("The session is not initialized yet."), {
                type: "danger",
            });
            return;
        }
        let quantity = Number.parseFloat(this.scanFormState.quantity);
        if (!Number.isFinite(quantity) || quantity <= 0) {
            quantity = 1;
        }
        this.scanFormState.quantity = quantity;
        try {
            const result = await this.orm.call(
                "wiz.stock.barcode.session",
                "scan_barcode",
                [[this.sessionId], barcode, quantity],
                {context: this.props.action?.context}
            );
            this.scanResultState.status = result.status || "info";
            this.scanResultState.message = result.message || "";
            this.scanResultState.focusMoveId = result.focus_move_id || null;
            if (result.picking) {
                this.state.payload = {
                    ...(this.state.payload || {}),
                    picking: result.picking,
                };
            }
            if (result.inventory) {
                this.state.payload = {
                    ...(this.state.payload || {}),
                    inventory: result.inventory,
                };
            }
            if (result.messages) {
                this.state.payload = {
                    ...(this.state.payload || {}),
                    messages: result.messages,
                };
            }
            this.scanFormState.barcode = "";
            this._playScanFeedback(this.scanResultState.status);
        } catch (error) {
            this.notification.add(error.message, {type: "danger"});
            throw error;
        } finally {
            if (this.barcodeInputRef.el) {
                this.barcodeInputRef.el.focus();
            }
        }
    }

    onBarcodeScanned(barcode) {
        if (!barcode) {
            return;
        }
        this.scanFormState.barcode = barcode;
        this.submitScan();
    }

    _createAudio(src) {
        if (typeof Audio === "undefined") {
            return null;
        }
        const audio = new Audio(src);
        audio.preload = "auto";
        return audio;
    }

    _playScanFeedback(status) {
        if (!status) {
            return;
        }
        const normalized = status.toLowerCase();
        let sound = null;
        if (normalized === "success") {
            sound = this.soundSuccess;
        } else if (["warning", "danger", "error"].includes(normalized)) {
            sound = this.soundWarning;
        }
        if (!sound) {
            return;
        }
        try {
            sound.currentTime = 0;
            sound.play();
        } catch (error) {
            // Ignore autoplay issues; scanner feedback still visible onscreen.
        }
    }
}

BarcodeSessionRoot.template = "stock_barcodes.BarcodeSessionRoot";

registry.category("actions").add("stock_barcode_session", BarcodeSessionRoot);
