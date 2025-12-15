/** @odoo-module **/

import {Component, useState, useRef, onMounted, onWillUnmount} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

export class CameraCapture extends Component {
    static template = "stock_barcodes_delivery_proof.CameraCapture";
    static props = {
        onCapture: {type: Function},
        onClose: {type: Function},
        moveLines: {type: Array, optional: true},
        proofLevel: {type: String, optional: true},
    };
    static defaultProps = {
        moveLines: [],
        proofLevel: "picking",
    };

    setup() {
        this.state = useState({
            isStreaming: false,
            error: null,
            facingMode: "environment", // Back camera by default
            selectedMoveLineId: null,
            showPreview: false,
            capturedImage: null,
        });
        this.videoRef = useRef("video");
        this.canvasRef = useRef("canvas");
        this.stream = null;
        this.notification = useService("notification");

        onMounted(() => this.startCamera());
        onWillUnmount(() => this.stopCamera());
    }

    get showMoveLineSelector() {
        return this.props.proofLevel === "line" && this.props.moveLines.length > 0;
    }

    async startCamera() {
        try {
            const constraints = {
                video: {
                    facingMode: this.state.facingMode,
                    width: {ideal: 1920},
                    height: {ideal: 1080},
                },
            };
            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            if (this.videoRef.el) {
                this.videoRef.el.srcObject = this.stream;
            }
            this.state.isStreaming = true;
            this.state.error = null;
        } catch (error) {
            console.error("Camera access error:", error);
            this.state.error = this._getErrorMessage(error);
            this.notification.add(this.state.error, {type: "danger"});
        }
    }

    _getErrorMessage(error) {
        if (error.name === "NotAllowedError") {
            return "Camera access denied. Please allow camera access in your browser settings.";
        } else if (error.name === "NotFoundError") {
            return "No camera found on this device.";
        } else if (error.name === "NotReadableError") {
            return "Camera is in use by another application.";
        }
        return "Could not access the camera. Please try again.";
    }

    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach((track) => track.stop());
            this.stream = null;
        }
        this.state.isStreaming = false;
    }

    async switchCamera() {
        this.stopCamera();
        this.state.facingMode =
            this.state.facingMode === "user" ? "environment" : "user";
        await this.startCamera();
    }

    capturePhoto() {
        const video = this.videoRef.el;
        const canvas = this.canvasRef.el;

        if (!video || !canvas) {
            return;
        }

        const context = canvas.getContext("2d");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0);

        // Convert to base64
        const imageData = canvas.toDataURL("image/jpeg", 0.85).split(",")[1];

        // Show preview
        this.state.capturedImage = imageData;
        this.state.showPreview = true;

        // Pause video
        this.stopCamera();
    }

    retakePhoto() {
        this.state.showPreview = false;
        this.state.capturedImage = null;
        this.startCamera();
    }

    confirmPhoto() {
        if (this.state.capturedImage) {
            this.props.onCapture(
                this.state.capturedImage,
                this.state.selectedMoveLineId
            );
        }
        this.close();
    }

    selectMoveLine(moveLineId) {
        this.state.selectedMoveLineId = moveLineId;
    }

    close() {
        this.stopCamera();
        this.props.onClose();
    }

    getPreviewUrl() {
        if (this.state.capturedImage) {
            return `data:image/jpeg;base64,${this.state.capturedImage}`;
        }
        return "";
    }
}
