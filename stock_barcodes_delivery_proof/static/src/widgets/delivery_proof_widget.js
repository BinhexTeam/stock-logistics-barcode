/** @odoo-module **/

import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {Component, useState, onWillStart} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {ImageCarousel} from "../components/image_carousel/image_carousel";
import {CameraCapture} from "../components/camera_capture/camera_capture";

export class DeliveryProofWidget extends Component {
    static template = "stock_barcodes_delivery_proof.DeliveryProofWidget";
    static components = {ImageCarousel, CameraCapture};
    static props = {...standardFieldProps};

    setup() {
        this.state = useState({
            showCamera: false,
            images: [],
            moveLines: [],
            isLoading: false,
        });
        this.orm = useService("orm");
        this.notification = useService("notification");

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        try {
            this.state.isLoading = true;
            await Promise.all([this.loadImages(), this.loadMoveLines()]);
        } finally {
            this.state.isLoading = false;
        }
    }

    async loadImages() {
        // Get images from the wizard's delivery_proof_data method
        if (this.props.record.resModel === "wiz.stock.barcodes.read.picking") {
            try {
                const result = await this.orm.call(
                    this.props.record.resModel,
                    "get_delivery_proof_data",
                    [this.props.record.resId] // Single ID, not wrapped in array
                );
                this.state.images = result || [];
            } catch (error) {
                console.error("Error loading delivery proof images:", error);
                this.state.images = [];
            }
        } else {
            // For regular picking forms, load from the field value
            const recordIds = this.props.value.records?.map((r) => r.resId) || [];
            if (recordIds.length > 0) {
                try {
                    this.state.images = await this.orm.read(
                        "stock.delivery.proof.image",
                        recordIds,
                        ["id", "name", "capture_date", "captured_by_id", "move_line_id"]
                    );
                } catch (error) {
                    console.error("Error loading images:", error);
                    this.state.images = [];
                }
            }
        }
    }

    async loadMoveLines() {
        if (this.props.record.resModel === "wiz.stock.barcodes.read.picking") {
            try {
                const result = await this.orm.call(
                    this.props.record.resModel,
                    "get_move_lines_for_proof",
                    [this.props.record.resId] // Single ID, not wrapped in array
                );
                this.state.moveLines = result || [];
            } catch (error) {
                console.error("Error loading move lines:", error);
                this.state.moveLines = [];
            }
        }
    }

    get proofLevel() {
        // Try to get from record data
        const level = this.props.record.data.delivery_proof_level;
        return level || "picking";
    }

    get isReadonly() {
        return this.props.readonly;
    }

    openCamera = () => {
        this.state.showCamera = true;
    };

    closeCamera = () => {
        this.state.showCamera = false;
    };

    onCapture = async (imageData, moveLineId = null) => {
        try {
            if (this.props.record.resModel === "wiz.stock.barcodes.read.picking") {
                // Call wizard method to save delivery proof
                const kwargs = {
                    image_data: imageData,
                    move_line_id: moveLineId || false,
                };

                await this.orm.call(
                    this.props.record.resModel,
                    "action_save_delivery_proof",
                    [this.props.record.resId], // Just the wizard ID
                    kwargs // Pass params as kwargs
                );
            } else {
                // Direct creation for regular forms
                const vals = {
                    image: imageData,
                    name: `Delivery Photo ${new Date().toISOString()}`,
                };

                if (this.props.record.resModel === "stock.picking") {
                    vals.picking_id = this.props.record.resId;
                } else if (
                    this.props.record.resModel === "stock.move.line" &&
                    moveLineId
                ) {
                    vals.move_line_id = moveLineId;
                }

                await this.orm.create("stock.delivery.proof.image", [vals]);
            }

            this.notification.add("Photo saved successfully", {type: "success"});
            this.closeCamera();

            // Reload data
            await this.loadData();

            // Notify parent if needed
            if (this.props.record.load) {
                await this.props.record.load();
            }
        } catch (error) {
            console.error("Error saving photo:", error);
            this.notification.add("Error saving photo", {type: "danger"});
        }
    };

    onDelete = async (proofId) => {
        try {
            console.log("Deleting proof:", proofId);
            console.log("Record model:", this.props.record.resModel);
            console.log("Record ID:", this.props.record.resId);

            if (this.props.record.resModel === "wiz.stock.barcodes.read.picking") {
                // Use wizard method - try with kwargs instead
                console.log("Calling action_delete_delivery_proof");

                const result = await this.orm.call(
                    this.props.record.resModel,
                    "action_delete_delivery_proof",
                    [this.props.record.resId], // Just pass the wizard ID
                    {
                        proof_id: proofId, // Pass proof_id as kwarg
                    }
                );

                console.log("Delete result:", result);

                if (!result) {
                    this.notification.add(
                        "Failed to delete photo - it may not belong to this picking",
                        {
                            type: "warning",
                        }
                    );
                    return;
                }
            } else {
                // Direct deletion
                await this.orm.unlink("stock.delivery.proof.image", [proofId]);
            }

            this.notification.add("Photo deleted successfully", {type: "success"});
            await this.loadData();

            if (this.props.record.load) {
                await this.props.record.load();
            }
        } catch (error) {
            console.error("Error deleting photo:", error);
            console.error("Error details:", JSON.stringify(error, null, 2));
            this.notification.add(
                "Error deleting photo: " + (error.message || "Unknown error"),
                {
                    type: "danger",
                }
            );
        }
    };

    get hasImages() {
        return this.state.images.length > 0;
    }

    get imageCount() {
        return this.state.images.length;
    }
}

registry.category("fields").add("delivery_proof", {
    component: DeliveryProofWidget,
    supportedTypes: ["one2many"],
});
