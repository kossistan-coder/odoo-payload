/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { renderLexicalToHtml } from "../lexical_editor/lexical_renderer";

/**
 * Composant OWL reproduisant fidèlement le panneau "Live Preview" de Payload CMS.
 * Se met à jour en temps réel lors de la modification des champs title, featured_image et content.
 */
export class PayloadLivePreview extends Component {
    static template = "payload_cms.PayloadLivePreview";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({
            viewportMode: "Responsive",
            width: 960,
            height: 840,
            zoom: 100,
        });
    }

    get title() {
        return this.props.record.data.title || "Titre de l'article";
    }

    get formattedDate() {
        const rawDate = this.props.record.data.published_at || this.props.record.data.create_date;
        if (rawDate) {
            const dateObj = new Date(rawDate);
            return dateObj.toLocaleDateString("en-US", {
                month: "long",
                day: "numeric",
                year: "numeric",
            }).toUpperCase();
        }
        return "NOVEMBER 19, 2024";
    }

    get bannerImageSrc() {
        const image = this.props.record.data.featured_image;
        if (!image) {
            return null;
        }
        if (typeof image === "string" && image.startsWith("data:")) {
            return image;
        }
        return `data:image/png;base64,${image}`;
    }

    get renderedHtmlContent() {
        const rawContent = this.props.record.data.content;
        let rootNode = null;

        if (typeof rawContent === "object" && rawContent?.root) {
            rootNode = rawContent.root;
        } else if (typeof rawContent === "string" && rawContent.trim().startsWith("{")) {
            try {
                const parsed = JSON.parse(rawContent);
                rootNode = parsed.root;
            } catch (e) {
                console.error("[Live Preview] Parsing error:", e);
            }
        }

        if (!rootNode) {
            return `
                <h2>Flexibility and Advanced Features</h2>
                <p>One standout feature of Payload CMS is its highly customizable backend. Developers can define schemas in JavaScript or TypeScript, making it simple to create structured content tailored to specific project needs.</p>
                <h2>Open Source and Community-Driven</h2>
                <p>Payload's open-source nature has fostered a vibrant and growing community of developers who continuously contribute to its evolution.</p>
            `;
        }

        return renderLexicalToHtml(rootNode);
    }
}

export const payloadLivePreview = {
    component: PayloadLivePreview,
    supportedTypes: ["json", "char", "text", "html", "boolean", "integer"],
};

registry.category("fields").add("payload_live_preview", payloadLivePreview);
