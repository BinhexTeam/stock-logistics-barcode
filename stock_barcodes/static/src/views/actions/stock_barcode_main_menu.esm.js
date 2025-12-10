/** @odoo-module **/
import {_t} from "@web/core/l10n/translation";
import {browser} from "@web/core/browser/browser";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

const {Component, onWillStart, useEffect, useState, useSubEnv} = owl;
const NAV_STATE_STORAGE_KEY = "stock_barcodes.navigation_state";

export class StockBarcodesMainMenu extends Component {
    setup() {
        super.setup();
        useSubEnv({_t});
        this.actionService = useService("action");
        this.ormService = useService("orm");
        this.notification = useService("notification");
        this.homeMenuService = this.hasService("home_menu")
            ? useService("home_menu")
            : null;
        this.barcodeService = this.hasService("barcode") ? useService("barcode") : null;
        this.state = useState({
            loading: true,
            profiles: [],
            selectedProfileId: null,
        });
        const busService = this.env.services.bus_service;

        onWillStart(async () => {
            await this.loadOverview();
        });

        const handleNotification = ({detail: notifications}) => {
            if (!notifications || !notifications.length) {
                return;
            }
            notifications.forEach((notif) => {
                const {payload, type} = notif;
                if (type === "actions_main_menu_barcode") {
                    if (payload.action_ok && payload.action) {
                        this.actionService.doAction(payload.action);
                    } else {
                        this.notification.add(
                            _t("No action found with barcode: %(barcode)s", {
                                barcode: payload.barcode || "",
                            }),
                            {type: "danger"}
                        );
                    }
                }
            });
        };

        useEffect(() => {
            busService.addChannel("stock_barcodes_main_menu");
            busService.addEventListener("notification", handleNotification);
            return () => {
                busService.deleteChannel("stock_barcodes_main_menu");
                busService.removeEventListener("notification", handleNotification);
            };
        });

        useEffect(
            () => {
                if (!this.barcodeService?.bus) {
                    return () => undefined;
                }
                const barcodeHandler = (ev) => {
                    this._handleOperationBarcode(ev.detail?.barcode);
                };
                this.barcodeService.bus.addEventListener(
                    "barcode_scanned",
                    barcodeHandler
                );
                return () => {
                    this.barcodeService.bus.removeEventListener(
                        "barcode_scanned",
                        barcodeHandler
                    );
                };
            },
            () => [this.barcodeService]
        );
    }

    hasService(service) {
        return service in this.env.services;
    }

    async loadOverview() {
        this.state.loading = true;
        try {
            const profiles = await this.ormService.call(
                "stock.barcode.profile",
                "get_navigation_payload",
                [],
                {context: this.props.action?.context}
            );
            this.state.profiles = profiles;
            const storedProfileId = this._getStoredProfileId();
            if (
                storedProfileId &&
                profiles.some((profile) => profile.id === storedProfileId)
            ) {
                this.state.selectedProfileId = storedProfileId;
            } else {
                this.state.selectedProfileId = null;
                this._storeProfileId(null);
            }
        } catch (error) {
            this.notification.add(error.message, {type: "danger"});
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    mainMenuHome() {
        if (this.homeMenuService && this.hasService("home_menu")) {
            this.homeMenuService.toggle(true);
        } else {
            browser.setTimeout(() => browser.location.reload(), 100);
            return this.actionService.doAction("mail.action_discuss");
        }
    }

    selectProfile(profileId) {
        this.state.selectedProfileId = profileId;
        this._storeProfileId(profileId);
    }

    goToProfiles() {
        this.selectProfile(null);
    }

    get profiles() {
        return this.state.profiles;
    }

    get currentProfile() {
        return this.state.profiles.find(
            (profile) => profile.id === this.state.selectedProfileId
        );
    }

    get currentOperations() {
        if (!this.currentProfile) {
            return [];
        }
        return this.currentProfile.picking_types || [];
    }

    isProfileEnabled(profile) {
        if (!profile) {
            return false;
        }
        if (profile.scope === "inventory") {
            return true;
        }
        return Boolean(profile.picking_types && profile.picking_types.length);
    }

    async _handleOperationBarcode(barcode) {
        if (!barcode || !this.currentProfile) {
            return;
        }
        const value = (barcode || "").trim();
        if (!value) {
            return;
        }
        const targetOperation = this.currentOperations.find(
            (operation) => operation.barcode && operation.barcode === value
        );
        if (targetOperation) {
            await this.openOperationList(targetOperation.id);
            return;
        }
        this.notification.add(
            _t("No operation type matches barcode %(barcode)s", {
                barcode: value,
            }),
            {type: "warning"}
        );
    }

    async openOperationList(pickingTypeId) {
        try {
            const context = {
                ...(this.props.action?.context || {}),
                operations_mode: true,
            };
            const action = await this.ormService.call(
                "stock.picking.type",
                "get_action_picking_tree_ready",
                [[pickingTypeId]],
                {context}
            );
            await this.actionService.doAction(action);
        } catch (error) {
            this.notification.add(error.message, {type: "danger"});
            throw error;
        }
    }

    async startScan(pickingTypeId) {
        try {
            const action = await this.ormService.call(
                "stock.picking.type",
                "action_barcode_scan",
                [[pickingTypeId]],
                {context: this.props.action?.context}
            );
            await this.actionService.doAction(action);
        } catch (error) {
            this.notification.add(error.message, {type: "danger"});
            throw error;
        }
    }

    _storeProfileId(profileId) {
        if (typeof window === "undefined") {
            return;
        }
        try {
            if (profileId) {
                window.sessionStorage.setItem(
                    NAV_STATE_STORAGE_KEY,
                    JSON.stringify({profileId})
                );
            } else {
                window.sessionStorage.removeItem(NAV_STATE_STORAGE_KEY);
            }
        } catch (error) {
            // Ignore storage errors (e.g., private mode)
        }
    }

    _getStoredProfileId() {
        if (typeof window === "undefined") {
            return null;
        }
        try {
            const raw = window.sessionStorage.getItem(NAV_STATE_STORAGE_KEY);
            if (!raw) {
                return null;
            }
            const payload = JSON.parse(raw);
            return payload.profileId || null;
        } catch (error) {
            return null;
        }
    }
}

StockBarcodesMainMenu.template = "stock_barcodes.MainMenu";

registry.category("actions").add("stock_barcodes_main_menu", StockBarcodesMainMenu);
