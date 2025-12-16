/** @odoo-module **/

import {ListController} from "@web/views/list/list_controller";
import {KanbanController} from "@web/views/kanban/kanban_controller";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";
import {onMounted, useEffect} from "@odoo/owl";

// Patch List Controller for stock.picking
patch(ListController.prototype, {
    setup() {
        console.log("[BARCODE FILTER] ListController.setup() called");
        super.setup(...arguments);
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.barcodeService = this.env.services.barcode ? useService("barcode") : null;
        this.scanFilterGroupId = null;

        console.log("[BARCODE FILTER] ResModel:", this.props.resModel);
        if (this.props.resModel === "stock.picking") {
            console.log("[BARCODE FILTER] Setting up barcode scanner for List view");
            this.setupBarcodeScanner();
        }
    },

    setupBarcodeScanner() {
        console.log("[BARCODE FILTER] setupBarcodeScanner() called for List");

        this.barcodeBuffer = "";
        this.barcodeTimeout = null;

        // Prefer native barcode service when available (handles scanners reliably)
        if (this.barcodeService) {
            useEffect(
                () => {
                    const handler = (event) => {
                        const scanned = event?.detail?.barcode || event?.barcode;
                        console.log(
                            "[BARCODE FILTER] Barcode service event (List):",
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
                        "[BARCODE FILTER] Barcode service listener attached (List)"
                    );
                    return () => {
                        this.barcodeService.bus.removeEventListener(
                            "barcode_scanned",
                            handler
                        );
                        console.log(
                            "[BARCODE FILTER] Barcode service listener removed (List)"
                        );
                    };
                },
                () => [this.barcodeService]
            );
            return;
        }

        onMounted(() => {
            console.log(
                "[BARCODE FILTER] List view mounted, adding keydown listener on window (fallback, capture)"
            );

            // Create the handler with proper binding; use keydown (keypress is deprecated and may not fire)
            const handler = (ev) => {
                console.log("[BARCODE FILTER] RAW Keydown event fired (List):", ev.key);
                this._onBarcodeKeypress(ev);
            };

            // Capture phase true to catch events early, even when nothing is focused
            window.addEventListener("keydown", handler, {capture: true});
            console.log(
                "[BARCODE FILTER] Event listener added successfully (window keydown, capture=true)"
            );

            // Store handler for cleanup if needed
            this._keypressHandler = handler;
        });
    },

    _onBarcodeKeypress(ev) {
        console.log(
            "[BARCODE FILTER] Keypress detected:",
            ev.key,
            "Target:",
            ev.target.tagName
        );

        if (this.props.resModel !== "stock.picking") {
            console.log("[BARCODE FILTER] Not stock.picking model, ignoring");
            return;
        }

        // Ignore if typing in an input field
        if (ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA") {
            console.log("[BARCODE FILTER] Input/Textarea focus, ignoring");
            return;
        }

        clearTimeout(this.barcodeTimeout);

        if (ev.key === "Enter") {
            console.log(
                "[BARCODE FILTER] Enter key pressed, buffer:",
                this.barcodeBuffer
            );
            if (this.barcodeBuffer) {
                this._onBarcodeScanned(this.barcodeBuffer);
                this.barcodeBuffer = "";
            }
        } else {
            // Only append printable characters
            if (ev.key && ev.key.length === 1) {
                this.barcodeBuffer += ev.key;
            }
            console.log("[BARCODE FILTER] Buffer updated:", this.barcodeBuffer);

            // Auto-submit after 100ms of no input (for barcode scanners)
            this.barcodeTimeout = setTimeout(() => {
                if (this.barcodeBuffer) {
                    console.log(
                        "[BARCODE FILTER] Auto-submit timeout, buffer:",
                        this.barcodeBuffer
                    );
                    this._onBarcodeScanned(this.barcodeBuffer);
                    this.barcodeBuffer = "";
                }
            }, 100);
        }
    },

    async _onBarcodeScanned(barcode) {
        console.log("[BARCODE FILTER] Processing barcode:", barcode);
        try {
            // Call the filter_by_barcode method
            console.log("[BARCODE FILTER] Calling filter_by_barcode on backend");
            const result = await this.orm.call(
                "stock.picking",
                "filter_by_barcode",
                [],
                {barcode}
            );

            console.log("[BARCODE FILTER] Backend result:", result);

            if (result.type === "not_found") {
                console.log("[BARCODE FILTER] Barcode not found");
                this.notification.add(result.message, {
                    type: "danger",
                    title: "Barcode Not Found",
                });
                return;
            }

            // Show notification
            console.log("[BARCODE FILTER] Showing success notification");
            this.notification.add(result.message, {
                type: "success",
                title: "Filter Applied",
            });

            // Apply the domain filter to the search bar (like v17) when possible
            const domain = result.domain;
            const searchModel = this.env.searchModel;
            console.log(
                "[BARCODE FILTER] Applying domain via searchModel (List):",
                domain
            );

            if (searchModel && searchModel.splitAndAddDomain) {
                const prevGroupIds = searchModel._getGroups
                    ? searchModel._getGroups().map((g) => g.id)
                    : [];

                await searchModel.splitAndAddDomain(domain, this.scanFilterGroupId);

                const nextGroupIds = searchModel._getGroups
                    ? searchModel._getGroups().map((g) => g.id)
                    : [];
                const newGroupId = nextGroupIds.find(
                    (id) => !prevGroupIds.includes(id)
                );
                if (newGroupId) {
                    this.scanFilterGroupId = newGroupId;
                }

                searchModel.search();
                console.log("[BARCODE FILTER] Domain applied via searchModel (List)");
            } else {
                // Fallback: direct load
                await this.model.root.load({domain});
                console.log("[BARCODE FILTER] Domain applied via model load (List)");
            }
        } catch (error) {
            console.error("[BARCODE FILTER] Error processing barcode:", error);
            this.notification.add("Error processing barcode", {
                type: "danger",
            });
        }
    },
});

// Patch Kanban Controller for stock.picking
patch(KanbanController.prototype, {
    setup() {
        console.log("[BARCODE FILTER] KanbanController.setup() called");
        super.setup(...arguments);
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.barcodeService = this.env.services.barcode ? useService("barcode") : null;
        this.scanFilterGroupId = null;

        console.log("[BARCODE FILTER] ResModel:", this.props.resModel);
        if (this.props.resModel === "stock.picking") {
            console.log("[BARCODE FILTER] Setting up barcode scanner for Kanban view");
            this.setupBarcodeScanner();
        }
    },

    setupBarcodeScanner() {
        console.log("[BARCODE FILTER] setupBarcodeScanner() called for Kanban");

        this.barcodeBuffer = "";
        this.barcodeTimeout = null;

        // Prefer native barcode service when available (handles scanners reliably)
        if (this.barcodeService) {
            useEffect(
                () => {
                    const handler = (event) => {
                        const scanned = event?.detail?.barcode || event?.barcode;
                        console.log(
                            "[BARCODE FILTER] Barcode service event (Kanban):",
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
                        "[BARCODE FILTER] Barcode service listener attached (Kanban)"
                    );
                    return () => {
                        this.barcodeService.bus.removeEventListener(
                            "barcode_scanned",
                            handler
                        );
                        console.log(
                            "[BARCODE FILTER] Barcode service listener removed (Kanban)"
                        );
                    };
                },
                () => [this.barcodeService]
            );
            return;
        }

        onMounted(() => {
            console.log(
                "[BARCODE FILTER] Kanban view mounted, adding keydown listener on window (fallback, capture)"
            );

            // Create the handler with proper binding; use keydown (keypress is deprecated and may not fire)
            const handler = (ev) => {
                console.log(
                    "[BARCODE FILTER] RAW Keydown event fired (Kanban):",
                    ev.key
                );
                this._onBarcodeKeypress(ev);
            };

            // Capture phase true to catch events early, even when nothing is focused
            window.addEventListener("keydown", handler, {capture: true});
            console.log(
                "[BARCODE FILTER] Event listener added successfully (window keydown, capture=true)"
            );

            // Store handler for cleanup if needed
            this._keypressHandler = handler;
        });
    },

    _onBarcodeKeypress(ev) {
        console.log(
            "[BARCODE FILTER] Keypress detected:",
            ev.key,
            "Target:",
            ev.target.tagName
        );

        if (this.props.resModel !== "stock.picking") {
            console.log("[BARCODE FILTER] Not stock.picking model, ignoring");
            return;
        }

        // Ignore if typing in an input field
        if (ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA") {
            console.log("[BARCODE FILTER] Input/Textarea focus, ignoring");
            return;
        }

        clearTimeout(this.barcodeTimeout);

        if (ev.key === "Enter") {
            console.log(
                "[BARCODE FILTER] Enter key pressed, buffer:",
                this.barcodeBuffer
            );
            if (this.barcodeBuffer) {
                this._onBarcodeScanned(this.barcodeBuffer);
                this.barcodeBuffer = "";
            }
        } else {
            // Only append printable characters
            if (ev.key && ev.key.length === 1) {
                this.barcodeBuffer += ev.key;
            }
            console.log("[BARCODE FILTER] Buffer updated:", this.barcodeBuffer);

            // Auto-submit after 100ms of no input (for barcode scanners)
            this.barcodeTimeout = setTimeout(() => {
                if (this.barcodeBuffer) {
                    console.log(
                        "[BARCODE FILTER] Auto-submit timeout, buffer:",
                        this.barcodeBuffer
                    );
                    this._onBarcodeScanned(this.barcodeBuffer);
                    this.barcodeBuffer = "";
                }
            }, 100);
        }
    },

    async _onBarcodeScanned(barcode) {
        console.log("[BARCODE FILTER] Processing barcode:", barcode);
        try {
            // Call the filter_by_barcode method
            console.log("[BARCODE FILTER] Calling filter_by_barcode on backend");
            const result = await this.orm.call(
                "stock.picking",
                "filter_by_barcode",
                [],
                {barcode}
            );

            console.log("[BARCODE FILTER] Backend result:", result);

            if (result.type === "not_found") {
                console.log("[BARCODE FILTER] Barcode not found");
                this.notification.add(result.message, {
                    type: "danger",
                    title: "Barcode Not Found",
                });
                return;
            }

            // Show notification
            console.log("[BARCODE FILTER] Showing success notification");
            this.notification.add(result.message, {
                type: "success",
                title: "Filter Applied",
            });

            // Apply the domain filter to the search bar (like v17) when possible
            const domain = result.domain;
            const searchModel = this.env.searchModel;
            console.log(
                "[BARCODE FILTER] Applying domain via searchModel (Kanban):",
                domain
            );

            if (searchModel && searchModel.splitAndAddDomain) {
                const prevGroupIds = searchModel._getGroups
                    ? searchModel._getGroups().map((g) => g.id)
                    : [];

                await searchModel.splitAndAddDomain(domain, this.scanFilterGroupId);

                const nextGroupIds = searchModel._getGroups
                    ? searchModel._getGroups().map((g) => g.id)
                    : [];
                const newGroupId = nextGroupIds.find(
                    (id) => !prevGroupIds.includes(id)
                );
                if (newGroupId) {
                    this.scanFilterGroupId = newGroupId;
                }

                searchModel.search();
                console.log("[BARCODE FILTER] Domain applied via searchModel (Kanban)");
            } else {
                // Fallback: direct load
                await this.model.root.load({domain});
                console.log("[BARCODE FILTER] Domain applied via model load (Kanban)");
            }
        } catch (error) {
            console.error("[BARCODE FILTER] Error processing barcode:", error);
            this.notification.add("Error processing barcode", {
                type: "danger",
            });
        }
    },
});
