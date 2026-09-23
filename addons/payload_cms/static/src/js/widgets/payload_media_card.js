/** @odoo-module **/

import { Component, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Widget OWL reproduisant la carte média de Payload CMS pour l'upload d'image de bannière.
 */
export class PayloadMediaCard extends Component {
    static template = "payload_cms.PayloadMediaCard";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.fileInputRef = useRef("fileInput");
    }

    get hasImage() {
        return Boolean(this.props.record.data[this.props.name]);
    }

    get imageSrc() {
        const val = this.props.record.data[this.props.name];
        if (!val) return "";
        if (typeof val === "string" && val.startsWith("data:")) return val;
        return `data:image/png;base64,${val}`;
    }

    get filename() {
        return this.props.record.data.featured_image_filename || "banner-image.webp";
    }

    get fileDetails() {
        return "31KB - 1600x800 - image/webp";
    }

    onUploadClick() {
        if (this.props.readonly) return;
        if (this.fileInputRef.el) {
            this.fileInputRef.el.click();
        }
    }

    onFileChange(ev) {
        const file = ev.target.files?.[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = () => {
            const result = reader.result;
            const base64 = result.split(",")[1];
            this.props.record.update({
                [this.props.name]: base64,
                featured_image_filename: file.name,
            });
        };
        reader.readAsDataURL(file);
    }

    onRemoveImage(ev) {
        ev.stopPropagation();
        if (this.props.readonly) return;
        this.props.record.update({
            [this.props.name]: false,
            featured_image_filename: false,
        });
    }

    onCopyLink(ev) {
        ev.stopPropagation();
        navigator.clipboard?.writeText(window.location.href);
    }
}

export const payloadMediaCard = {
    component: PayloadMediaCard,
    supportedTypes: ["binary"],
};

registry.category("fields").add("payload_media_card", payloadMediaCard);
