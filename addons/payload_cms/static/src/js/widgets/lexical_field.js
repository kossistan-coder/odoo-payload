/** @odoo-module **/

import { Component, useRef, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { LexicalTheme } from "../lexical_editor/lexical_theme";
import { getLexicalLib, normalizePayloadContent, getInitialPayloadState } from "../lexical_editor/lexical_helper";
import { createDefaultFeatureRegistry } from "../lexical_editor/lexical_features";

/**
 * Widget OWL pour l'intégration de l'éditeur Lexical avec toolbar stylisée Payload CMS.
 */
export class LexicalRichTextField extends Component {
    static template = "payload_cms.LexicalRichTextField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.editorContainerRef = useRef("editorContainer");
        this.featureRegistry = createDefaultFeatureRegistry();
        this.editor = null;
        this.cleanups = [];
        this.isInternalUpdate = false;

        this.state = useState({
            isFocused: false,
            isEmpty: true,
            currentBlock: "paragraph",
        });

        this.inlineFormats = [
            this.featureRegistry.get('bold'),
            this.featureRegistry.get('italic'),
            this.featureRegistry.get('underline'),
            this.featureRegistry.get('strikethrough'),
            this.featureRegistry.get('subscript'),
            this.featureRegistry.get('superscript'),
            this.featureRegistry.get('code'),
            this.featureRegistry.get('link'),
        ].filter(Boolean);

        onMounted(() => {
            this.initLexicalEditor();
        });

        onWillUnmount(() => {
            this.destroyLexicalEditor();
        });
    }

    initLexicalEditor() {
        const Lexical = getLexicalLib();
        const editableElement = this.editorContainerRef.el;
        if (!editableElement) return;

        const initialConfig = {
            namespace: "PayloadCMS",
            theme: LexicalTheme,
            nodes: this.featureRegistry.getRequiredNodes(),
            onError: (error) => console.error("[Payload CMS Lexical Error]", error),
        };

        this.editor = Lexical.createEditor(initialConfig);
        this.editor.setRootElement(editableElement);

        if (typeof Lexical.registerRichText === "function") {
            this.cleanups.push(Lexical.registerRichText(this.editor));
        }
        if (typeof Lexical.registerHistory === "function" && typeof Lexical.createEmptyHistoryState === "function") {
            this.cleanups.push(
                Lexical.registerHistory(this.editor, Lexical.createEmptyHistoryState(), 1000)
            );
        }

        this.loadInitialContent();

        const unregisterUpdate = this.editor.registerUpdateListener(({ editorState, dirtyElements, dirtyLeaves }) => {
            if (dirtyElements.size === 0 && dirtyLeaves.size === 0) return;

            editorState.read(() => {
                const root = Lexical.$getRoot();
                this.state.isEmpty = root.getChildrenSize() === 0 || (
                    root.getChildrenSize() === 1 &&
                    root.getFirstChild() &&
                    root.getFirstChild().getType() === 'paragraph' &&
                    root.getFirstChild().getTextContent().trim() === ''
                );
            });

            if (!this.isInternalUpdate) {
                this.saveToOdoo(editorState);
            }
        });
        this.cleanups.push(unregisterUpdate);
    }

    loadInitialContent() {
        const rawValue = this.props.record.data[this.props.name];
        const normalizedJsonStr = normalizePayloadContent(rawValue);

        this.isInternalUpdate = true;
        try {
            const parsedState = this.editor.parseEditorState(normalizedJsonStr);
            this.editor.setEditorState(parsedState);
        } catch (err) {
            console.error("[Payload CMS] Erreur parsing Lexical:", err);
            const fallbackState = this.editor.parseEditorState(JSON.stringify(getInitialPayloadState()));
            this.editor.setEditorState(fallbackState);
        } finally {
            this.isInternalUpdate = false;
        }
    }

    saveToOdoo(editorState) {
        const jsonState = editorState.toJSON();
        const fieldType = this.props.record.fields[this.props.name]?.type;
        let valueToSave = jsonState;
        if (fieldType === "text" || fieldType === "char" || fieldType === "html") {
            valueToSave = JSON.stringify(jsonState);
        }
        this.props.record.update({
            [this.props.name]: valueToSave,
        });
    }

    onBlockTypeChange(ev) {
        const type = ev.target.value;
        this.state.currentBlock = type;
        const feature = this.featureRegistry.get(type);
        if (feature) {
            feature.execute(this.editor);
            this.editorContainerRef.el?.focus();
        }
    }

    onAlignChange(ev) {
        const align = ev.target.value;
        const feature = this.featureRegistry.get(`align_${align}`);
        if (feature) {
            feature.execute(this.editor);
            this.editorContainerRef.el?.focus();
        }
    }

    onExecuteFeature(feature) {
        if (!this.editor || this.props.readonly) return;
        feature.execute(this.editor);
        this.editorContainerRef.el?.focus();
    }

    destroyLexicalEditor() {
        for (const cleanup of this.cleanups) {
            if (typeof cleanup === "function") cleanup();
        }
        this.cleanups = [];
        if (this.editor) {
            this.editor.setRootElement(null);
            this.editor = null;
        }
    }
}

export const lexicalRichTextField = {
    component: LexicalRichTextField,
    supportedTypes: ["json", "text", "char", "html"],
};

registry.category("fields").add("payload_lexical", lexicalRichTextField);
