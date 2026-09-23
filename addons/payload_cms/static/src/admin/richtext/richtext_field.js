/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState, useSubEnv } from "@odoo/owl";
import { drawerViews, openDocumentDrawer, openListDrawer } from "../core/drawers";
import { createForm } from "../core/form";
import { t } from "../core/i18n";
import { cacheDoc } from "../core/relations";
import { openDrawer, store } from "../core/store";
import { deepCopy } from "../core/utils";
import { Button, FieldError } from "../components/base";
import { FieldBase } from "../fields/field_base";
import { PayloadEditor, PLACEHOLDER } from "./editor";

/** Payload's "Edit Link" drawer (FieldsDrawer of the LinkFeature). */
export class LinkDrawer extends Component {
    static template = "payload.LinkDrawer";
    static components = { Button };

    setup() {
        this.t = t;
        const initial = deepCopy(this.props.data || {});
        this.data = useState({
            text: initial.text || "",
            linkType: initial.linkType || "custom",
            url: initial.url || "",
            newTab: Boolean(initial.newTab),
            _relationTo: initial.doc?.relationTo || this.linkableCollections[0]?.slug || null,
            _docValue: initial.doc?.value ?? null,
        });
        this.form = createForm();
        this.formState = useState(this.form.state);
        useSubEnv({ form: this.form });
    }

    get RenderFields() {
        return drawerViews.RenderFields;
    }

    get linkableCollections() {
        return (store.config?.collections || []).filter((c) => !c.upload && !c.admin?.hidden);
    }

    get fields() {
        const fields = [
            { name: "text", type: "text", label: "Text to display", required: true, admin: {} },
            {
                name: "linkType",
                type: "radio",
                label: "Link Type",
                required: true,
                options: [
                    { value: "custom", label: "Custom URL" },
                    ...(this.linkableCollections.length ? [{ value: "internal", label: "Internal Link" }] : []),
                ],
                admin: { description: "Choose between entering a custom text URL or linking to another document." },
            },
        ];
        if (this.data.linkType === "internal") {
            fields.push({
                type: "row",
                fields: [
                    {
                        name: "_relationTo",
                        type: "select",
                        label: "Collection",
                        options: this.linkableCollections.map((c) => ({ value: c.slug, label: c.labels.singular })),
                        admin: { width: "35%", isClearable: false },
                    },
                    this.data._relationTo && {
                        name: "_docValue",
                        type: "relationship",
                        label: "Choose a document to link to",
                        relationTo: this.data._relationTo,
                        required: true,
                        admin: { width: "65%" },
                    },
                ].filter(Boolean),
            });
        } else {
            fields.push({ name: "url", type: "text", label: "Enter a URL", required: true, admin: {} });
        }
        fields.push({ name: "newTab", type: "checkbox", label: "Open in new tab", admin: {} });
        return fields;
    }

    save() {
        const d = this.data;
        const errors = {};
        if (!d.text) {
            errors.text = t("validation:required");
        }
        if (d.linkType === "internal" && !d._docValue) {
            errors._docValue = t("validation:required");
        }
        if (d.linkType !== "internal" && !d.url) {
            errors.url = t("validation:required");
        }
        this.form.state.errors = errors;
        this.form.state.submitted = true;
        if (Object.keys(errors).length) {
            return;
        }
        const result = { text: d.text, linkType: d.linkType, newTab: d.newTab };
        if (d.linkType === "internal") {
            result.doc = { relationTo: d._relationTo, value: d._docValue };
        } else {
            result.url = d.url;
        }
        this.props.close(result);
    }
}

/** The richText field (Lexical editor with Payload's default features). */
export class RichTextField extends FieldBase {
    static template = "payload.RichTextField";
    static components = { FieldError };

    setup() {
        super.setup();
        this.editableRef = useRef("editable");
        this.anchorRef = useRef("anchor");
        this.placeholderRef = useRef("placeholder");
        this.fixedToolbarRef = useRef("fixedToolbar");
        this.placeholderText = this.admin.placeholder || PLACEHOLDER;
        this.state = useState({ gutter: window.innerWidth > 768 });
        this.onResize = () => (this.state.gutter = window.innerWidth > 768);
        onMounted(() => {
            window.addEventListener("resize", this.onResize);
            this.pe = new PayloadEditor({
                contentEditable: this.editableRef.el,
                anchor: this.anchorRef.el,
                placeholder: this.placeholderRef.el,
                fixedToolbar: this.fixedToolbarRef.el,
                value: deepCopy(this.props.data[this.field.name] ?? null),
                readOnly: this.readOnly,
                onChange: (json) => this.setValue(json),
                host: {
                    openLinkDrawer: (data) =>
                        openDrawer(LinkDrawer, { data }, { title: "Edit Link", className: "lexical-link-edit-drawer" }),
                    openUploadDrawer: (opts) => this.chooseDoc("upload", opts),
                    openRelationshipDrawer: (opts) => this.chooseDoc("relationship", opts),
                    openDocDrawer: async (slug, id) => {
                        const doc = await openDocumentDrawer(slug, id);
                        if (doc?.id) {
                            cacheDoc(slug, doc);
                        }
                    },
                },
            });
        });
        onWillUnmount(() => {
            window.removeEventListener("resize", this.onResize);
            this.pe?.destroy();
        });
    }

    /** Payload's FixedToolbarFeature, enabled unless `admin.hideFixedToolbar` is set on the field. */
    get showFixedToolbar() {
        return !this.readOnly && !this.admin.hideFixedToolbar;
    }

    async chooseDoc(kind, { replace } = {}) {
        const collections = (store.config?.collections || []).filter((c) => (kind === "upload" ? c.upload : !c.upload) && !c.admin?.hidden);
        if (!collections.length) {
            return;
        }
        this.pe.rememberSelection();
        const doc = await openListDrawer(collections[0].slug, { collectionSlugs: collections.map((c) => c.slug) });
        if (!doc?.id) {
            return;
        }
        cacheDoc(doc.__collection || collections[0].slug, doc);
        this.pe.insertDecorator(kind, { relationTo: doc.__collection || collections[0].slug, value: doc.id }, replace || null);
    }

    insertParagraphAtEnd() {
        const L = window.PayloadLexical;
        this.pe?.editor.update(() => {
            const p = L.$createParagraphNode();
            L.$getRoot().append(p);
            p.select();
        });
    }
}
