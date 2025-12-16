/** @odoo-module **/

/*
 * StockBarcodesFormController for Odoo 18 (compatible with 16/17).
 *
 * Goals:
 * - Provide a public method `openBarcodeScanner()` that starts scanning via the
 *   (optional) "barcode" service when available, with graceful fallback.
 * - Emit an app-level event on successful scans so other parts (renderer, model,
 *   kanban list, etc.) can react without tight coupling.
 * - Ensure proper cleanup on unmount / navigation to avoid leaks.
 *
 * OCA-friendly: uses public services/hooks only (no private APIs).
 */

import {FormController} from "@web/views/form/form_controller";
import {_t} from "@web/core/l10n/translation";
import {scanBarcode} from "@web/core/barcode/barcode_dialog";
import {useService} from "@web/core/utils/hooks";
import {useEffect} from "@odoo/owl";

export class StockBarcodesFormController extends FormController {
    setup() {
        super.setup();
        // Needed to hide the odoo's navbar
        this.display = {...this.display, controlPanel: false};
        // Public services (safe across 16/17/18)
        this.notification = useService("notification");
        this.action = useService("action");
        this.ui = useService("ui");
        this.ormService = useService("orm");

        // Barcode service is optional (exists if stock_barcode or similar is loaded).
        // Keep it guarded so the controller works even without that module.
        this.barcode = null;
        try {
            this.barcode = useService("barcode");
        } catch {
            // Service not available; fall back gracefully
            this.barcode = null;
        }

        // Track stop handler for cleanup if barcode service is in use
        this._stopBarcode = null;
        this._scanSeq = 0;

        // Defensive cleanup on page/tab visibility or component teardown
        useEffect(
            () => {
                const onVisibilityChange = () => {
                    if (document.hidden) {
                        this._stopScannerIfAny();
                    }
                };
                document.addEventListener("visibilitychange", onVisibilityChange, true);

                return () => {
                    document.removeEventListener(
                        "visibilitychange",
                        onVisibilityChange,
                        true
                    );
                    this._stopScannerIfAny();
                };
            },
            () => []
        );

        // Bind the optional camera scan button injected in the wizard view (delegated for robustness)
        useEffect(() => {
            const handler = (ev) => {
                const target = ev.target instanceof HTMLElement ? ev.target : null;
                if (!target) {
                    return;
                }
                const btn = target.closest(".o_stock_barcodes_camera_btn");
                if (!btn) {
                    return;
                }
                ev.preventDefault();
                ev.stopPropagation();
                this.openBarcodeScanner();
            };
            document.addEventListener("click", handler, true);
            return () => document.removeEventListener("click", handler, true);
        });
    }

    /**
     * Public: open the barcode scanner.
     * Prefer the "barcode" service when available, otherwise warn the user.
     */
    async openBarcodeScanner() {
        // If a scanner is already running, stop and restart for a clean session.
        this._stopScannerIfAny();

        if (this.barcode && typeof this.barcode.start === "function") {
            // Start service-based scanning
            const stop = this.barcode.start({
                // Called on every successful scan
                onBarcodeScanned: (payload) => {
                    // Some impls pass a raw string, others an object { barcode, ... }
                    const code =
                        typeof payload === "string" ? payload : payload?.barcode || "";
                    if (!code) {
                        this._notifyWarn(_t("Empty barcode."));
                        return;
                    }
                    this.onBarcodeScanned(code);
                },
                // Error callback for camera/permission issues, etc.
                onError: (err) => {
                    this.onBarcodeError(err);
                },
            });
            this._stopBarcode = typeof stop === "function" ? stop : null;
            this._notifyInfo(_t("Scanner started. Press Esc or switch tab to stop."));
            return;
        }

        // Fallback: open the camera dialog-based scanner (Odoo web client)
        const scanned = await this._openCameraDialog();
        if (scanned) {
            await this.onBarcodeScanned(scanned);
            return;
        }

        // If nothing handled the request, inform the user
        this._notifyWarn(
            _t(
                "No barcode service available. Install/enable stock_barcode or use a hardware wedge scanner."
            )
        );
    }

    /**
     * Hook: called when a barcode has been scanned.
     * Default behavior is to emit an event that others can subscribe to.
     * Override this to implement custom search/write/open flows.
     */
    async onBarcodeScanned(code) {
        const normalizedCode = this._normalizeBarcodePayload(code);
        if (!normalizedCode) {
            this._notifyWarn(_t("Empty barcode."));
            return;
        }

        const seq = ++this._scanSeq;
        const resModel = this.props?.resModel || null;
        const resId = this.props?.resId || null;
        console.log(
            "[BARCODE SCAN][FORM CTRL] onBarcodeScanned entry seq=%s | code=%s | resModel=%s | resId=%s | ctx=%o",
            seq,
            normalizedCode,
            resModel,
            resId,
            this.props?.context || {}
        );

        // If we are on a barcode wizard, process immediately via RPC to keep UX tight
        if (resModel && resId && resModel.startsWith("wiz.stock.barcodes.read")) {
            return await this._processWizardBarcode(normalizedCode, resModel, resId, seq);
        }

        // Fallback: emit an application-level event so renderers/parents can react
        const payload = {
            code: normalizedCode,
            model: resModel,
            resId,
            viewType: "form",
        };
        this.env.bus.trigger("stock_barcodes:scan", payload);

        // Optional UX hint
        this._notifySuccess(_t("Scanned: %s").replace("%s", normalizedCode));
    }

    /**
     * Hook: called when the barcode service reports an error.
     */
    onBarcodeError(err) {
        const msg =
            (err && (err.message || err.toString?.())) || _t("Barcode scan error.");
        this._notifyDanger(msg);
        this._stopScannerIfAny();
    }

    /**
     * Ensure we stop the scanner on navigation.
     * Odoo calls beforeLeave() in several flows; we keep it defensive.
     */
    async beforeLeave() {
        this._stopScannerIfAny();
        if (super.beforeLeave) {
            return super.beforeLeave();
        }
    }

    // -----------------------------
    // Internal helpers
    // -----------------------------

    _stopScannerIfAny() {
        if (typeof this._stopBarcode === "function") {
            try {
                this._stopBarcode();
            } catch {
                // Ignore
            }
        }
        this._stopBarcode = null;
    }

    _normalizeBarcodePayload(payload) {
        if (typeof payload === "string") {
            return payload.trim();
        }
        if (payload && typeof payload === "object" && payload.barcode) {
            return String(payload.barcode).trim();
        }
        return "";
    }

    async _processWizardBarcode(code, resModel, resId, seq = null) {
        try {
            const ctx = Object.assign({}, this.props?.context || {}, {
                barcode_processing: true,
            });
            console.log(
                "[BARCODE SCAN][FORM CTRL] RPC start seq=%s | code=%s | resModel=%s | resId=%s | ctx=%o",
                seq,
                code,
                resModel,
                resId,
                ctx
            );
            await this.ormService.call(resModel, "on_barcode_scanned", [[resId], code], {
                context: ctx,
            });

            // Refresh current record to reflect server-side changes
            if (this.model?.root?.load) {
                await this.model.root.load();
            }
            if (this.model?.notify) {
                this.model.notify();
            }

            this._notifySuccess(_t("Scanned: %s").replace("%s", code));
            console.log(
                "[BARCODE SCAN][FORM CTRL] RPC done seq=%s | code=%s",
                seq,
                code
            );
        } catch (err) {
            const msg =
                err?.message ||
                err?.data?.message ||
                err?.toString?.() ||
                _t("Camera scan failed.");
            this._notifyDanger(msg);
            console.error(
                "[BARCODE SCAN][FORM CTRL] RPC error seq=%s | code=%s",
                seq,
                code,
                err
            );
            this._stopScannerIfAny();
        }
    }

    async _openCameraDialog() {
        try {
            // Use Odoo's built-in camera dialog; works on mobile and desktop.
            const barcode = await scanBarcode(this.env, "environment");
            return barcode || "";
        } catch (err) {
            const msg =
                err?.message ||
                err?.data?.message ||
                err?.toString?.() ||
                _t("Camera scan failed.");
            this._notifyDanger(msg);
            return "";
        }
    }

    _notifyInfo(message) {
        this.notification.add(message, {type: "info"});
    }
    _notifyWarn(message) {
        this.notification.add(message, {type: "warning"});
    }
    _notifyDanger(message) {
        this.notification.add(message, {type: "danger"});
    }
    _notifySuccess(message) {
        this.notification.add(message, {type: "success"});
    }
}
