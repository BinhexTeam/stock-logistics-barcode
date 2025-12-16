/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {FormController} from "@web/views/form/form_controller";
import {useService} from "@web/core/utils/hooks";
import {onMounted, onWillUnmount, useEffect} from "@odoo/owl";

// Patch the form controller used by barcode scan wizards
patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.barcodeService = this.env.services.barcode ? useService("barcode") : null;
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this._scanSeq = 0;

        const isBarcodeWizard = this.props.resModel?.startsWith(
            "wiz.stock.barcodes.read"
        );
        if (isBarcodeWizard) {
            console.log(
                "[BARCODE SCAN] FormController.setup() for barcode wizard | model=%s",
                this.props.resModel
            );
            this._setupBarcodeListener();
            this._setupBarcodeRefreshListener();
        }
    },

    _setupBarcodeRefreshListener() {
        // Listen to bus notifications to refresh the wizard after qty changes or unlinks
        const wizId = this.props?.resId;
        if (!wizId || !this.busService) {
            return;
        }
        this.busService.addChannel("stock_barcodes_scan");
        this.busService.start();
        this.busService.addEventListener(
            "notification",
            this,
            ({detail: notifications}) => {
                for (const notif of notifications) {
                    const {channel, payload} = notif;
                    if (channel !== "stock_barcodes_scan") {
                        continue;
                    }
                    const isMine = payload?.wiz_id === wizId;
                    const isQtyChange = payload?.type === "barcode_qty_change";
                    const isUnlink = payload?.type === "barcode_move_line_unlink";
                    if (isMine && (isQtyChange || isUnlink)) {
                        console.log(
                            "[BARCODE SCAN] Reloading wizard after qty/unlink notification"
                        );
                        this.reload();
                        break;
                    }
                }
            }
        );
    },

    _setupBarcodeListener() {
        console.log("[BARCODE SCAN] Setting up barcode listener for barcode wizard");
        // Always register both the barcode service bus (if available) and a keydown fallback
        if (this.barcodeService) {
            useEffect(
                () => {
                    const handler = (event) => {
                        const scanned = event?.detail?.barcode || event?.barcode;
                        if (event?.stopImmediatePropagation) {
                            event.stopImmediatePropagation();
                        }
                        if (event?.stopPropagation) {
                            event.stopPropagation();
                        }
                        console.log(
                            "[BARCODE SCAN] Barcode service event (Form):",
                            scanned
                        );
                        if (scanned) {
                            this._onBarcodeScanned(scanned);
                        }
                    };
                    this.barcodeService.bus.addEventListener(
                        "barcode_scanned",
                        handler
                    );
                    console.log(
                        "[BARCODE SCAN] Barcode service listener attached (Form)"
                    );
                    return () => {
                        this.barcodeService.bus.removeEventListener(
                            "barcode_scanned",
                            handler
                        );
                        console.log(
                            "[BARCODE SCAN] Barcode service listener removed (Form)"
                        );
                    };
                },
                () => [this.barcodeService]
            );
        }

        // Keydown fallback only when barcode service is unavailable
        if (!this.barcodeService) {
            onMounted(() => {
                console.log(
                    "[BARCODE SCAN] Adding keydown listener (fallback) for barcode wizard"
                );
                this._barcodeBuffer = "";
                this._barcodeTimeout = null;

                const handler = (ev) => {
                    // Ignore if typing in inputs/textareas
                    if (
                        ev.target?.tagName === "INPUT" ||
                        ev.target?.tagName === "TEXTAREA"
                    ) {
                        return;
                    }
                    if (ev.key === "Enter") {
                        if (this._barcodeBuffer) {
                            console.log(
                                "[BARCODE SCAN] Enter pressed, buffer:",
                                this._barcodeBuffer
                            );
                            this._onBarcodeScanned(this._barcodeBuffer);
                            this._barcodeBuffer = "";
                        }
                        return;
                    }
                    if (ev.key && ev.key.length === 1) {
                        this._barcodeBuffer += ev.key;
                    }
                    clearTimeout(this._barcodeTimeout);
                    this._barcodeTimeout = setTimeout(() => {
                        if (this._barcodeBuffer) {
                            console.log(
                                "[BARCODE SCAN] Auto-submit buffer:",
                                this._barcodeBuffer
                            );
                            this._onBarcodeScanned(this._barcodeBuffer);
                            this._barcodeBuffer = "";
                        }
                    }, 120);
                };

                window.addEventListener("keydown", handler, {capture: true});
                this._barcodeKeydownHandler = handler;
            });

            onWillUnmount(() => {
                if (this._barcodeKeydownHandler) {
                    window.removeEventListener("keydown", this._barcodeKeydownHandler, {
                        capture: true,
                    });
                    this._barcodeKeydownHandler = null;
                    this._barcodeBuffer = "";
                }
            });
        }
    },

    async _onBarcodeScanned(barcode) {
        const normalized = this._normalizeBarcodePayload
            ? this._normalizeBarcodePayload(barcode)
            : String(barcode || "").trim();
        const seq = ++this._scanSeq;
        const resModel = this.props?.resModel;
        const resId = this.props?.resId;
        console.log(
            "[BARCODE SCAN] Dispatching (seq=%s) barcode=%s | resModel=%s | resId=%s",
            seq,
            normalized,
            resModel,
            resId
        );

        // Deduplicate fast double-fires (service + keydown) and avoid overlapping RPC writes
        const now = Date.now();
        if (
            this._lastBarcode === normalized &&
            now - (this._lastBarcodeTs || 0) < 400
        ) {
            console.log(
                "[BARCODE SCAN] Skipped duplicate barcode in debounce window (seq=%s)",
                seq
            );
            return;
        }
        if (this._barcodeInFlight) {
            console.log(
                "[BARCODE SCAN] Skip scan while previous is in flight (seq=%s)",
                seq
            );
            return;
        }
        this._lastBarcode = normalized;
        this._lastBarcodeTs = now;
        this._barcodeInFlight = true;

        try {
            const isWizard = resModel?.startsWith("wiz.stock.barcodes.read");

            // Prefer the existing RPC flow for barcode wizards so server logic runs immediately
            if (isWizard && typeof this._processWizardBarcode === "function") {
                await this._processWizardBarcode(normalized, resModel, resId, seq);
                return;
            }

            // Fallback: update the record and poke the dummy button
            const record = this.model.root;
            if (!record) {
                console.warn("[BARCODE SCAN] No form record to dispatch to");
                return;
            }

            if (record.update) {
                await record.update({
                    _barcode_scanned: normalized,
                    barcode: normalized,
                });
            }

            if (record.getField) {
                const dummyButton = record.getField("dummy_on_barcode_scanned");
                if (dummyButton?.activate) {
                    console.log(
                        "[BARCODE SCAN] Triggering dummy_on_barcode_scanned button"
                    );
                    await dummyButton.activate();
                }
            }
        } catch (err) {
            console.error("[BARCODE SCAN] Wizard RPC failed (seq=%s)", seq, err);
            this.notification?.add(err?.message || "Barcode handling failed", {
                type: "danger",
                title: "Barcode",
            });
        } finally {
            this._barcodeInFlight = false;
        }
    },

    async _processWizardBarcode(barcode, resModel, resId, seq = null) {
        if (!resModel || !resId) {
            console.warn("[BARCODE SCAN] Missing resModel/resId for wizard processing");
            return;
        }
        const context = Object.assign(
            {},
            this.model?.root?.context || this.props?.context || {},
            {
                barcode_processing: true,
            }
        );
        console.log(
            "[BARCODE SCAN] RPC start (seq=%s) | barcode=%s | resModel=%s | resId=%s | ctx=%o",
            seq,
            barcode,
            resModel,
            resId,
            context
        );
        await this.orm.call(resModel, "on_barcode_scanned", [[resId], barcode], {
            context,
        });
        console.log("[BARCODE SCAN] RPC done (seq=%s) | barcode=%s", seq, barcode);
    },
});
