/** @odoo-module **/

/**
 * Payload's custom Lexical nodes (link, upload, relationship, horizontal rule)
 * serialized exactly like @payloadcms/richtext-lexical 3.90 (Lexical 0.50).
 */
import { ensureDocs, getCachedDoc } from "../core/relations";
import { getCollection } from "../core/store";
import { docTitle, icon, rowId } from "../core/utils";

const L = window.PayloadLexical;

function iconHTML(name) {
    return String(icon(name));
}

// ----------------------------------------------------------------------
// Link
// ----------------------------------------------------------------------
const SUPPORTED_PROTOCOLS = new Set(["http:", "https:", "mailto:", "sms:", "tel:"]);

function sanitizeUrl(url) {
    try {
        const parsed = new URL(url);
        if (!SUPPORTED_PROTOCOLS.has(parsed.protocol)) {
            return "about:blank";
        }
    } catch {
        return url;
    }
    return url;
}

export class PayloadLinkNode extends L.ElementNode {
    static getType() {
        return "link";
    }

    static clone(node) {
        return new PayloadLinkNode({ fields: JSON.parse(JSON.stringify(node.__fields || {})), id: node.__id }, node.__key);
    }

    constructor({ fields = { linkType: "custom", newTab: false, url: "https://" }, id } = {}, key) {
        super(key);
        this.__fields = fields;
        this.__id = id || rowId();
    }

    createDOM(config) {
        const el = document.createElement("a");
        this._applyAttributes(el);
        L.addClassNamesToElement(el, config.theme.link);
        return el;
    }

    _applyAttributes(el) {
        const fields = this.__fields || {};
        if (fields.linkType !== "internal" && fields.url) {
            el.href = sanitizeUrl(fields.url);
        } else {
            el.removeAttribute("href");
        }
        if (fields.newTab) {
            el.target = "_blank";
            el.rel = fields.linkType === "custom" ? "noopener" : "";
        } else {
            el.removeAttribute("target");
            el.removeAttribute("rel");
        }
    }

    updateDOM(prevNode, dom) {
        this._applyAttributes(dom);
        return false;
    }

    static importDOM() {
        return {
            a: () => ({
                conversion: (dom) => ({
                    node: $createPayloadLinkNode({
                        fields: { linkType: "custom", newTab: dom.getAttribute("target") === "_blank", url: dom.getAttribute("href") || "" },
                    }),
                }),
                priority: 1,
            }),
        };
    }

    static importJSON(json) {
        let fields = json.fields || {};
        if (fields.doc?.value && typeof fields.doc.value === "object") {
            fields = { ...fields, doc: { ...fields.doc, value: fields.doc.value.id } };
        }
        return $createPayloadLinkNode({ fields, id: json.id }).updateFromJSON(json);
    }

    exportJSON() {
        const fields = { ...(this.getFields() || {}) };
        if (fields.linkType === "internal") {
            delete fields.url;
        } else if (fields.linkType === "custom") {
            delete fields.doc;
        }
        return { ...super.exportJSON(), type: "link", version: 3, fields, id: this.getID() };
    }

    getFields() {
        return this.getLatest().__fields;
    }

    setFields(fields) {
        this.getWritable().__fields = fields;
    }

    getID() {
        return this.getLatest().__id;
    }

    isInline() {
        return true;
    }

    canInsertTextBefore() {
        return false;
    }

    canInsertTextAfter() {
        return false;
    }

    canBeEmpty() {
        return false;
    }

    insertNewAfter(_selection, restoreSelection = true) {
        const node = $createPayloadLinkNode({ fields: this.__fields });
        this.insertAfter(node, restoreSelection);
        return node;
    }

    extractWithChild(_child, selection) {
        if (!L.$isRangeSelection(selection)) {
            return false;
        }
        const anchor = selection.anchor.getNode();
        const focus = selection.focus.getNode();
        return this.isParentOf(anchor) && this.isParentOf(focus) && selection.getTextContent().length > 0;
    }
}

export function $createPayloadLinkNode(opts) {
    return L.$applyNodeReplacement(new PayloadLinkNode(opts));
}

export function $isPayloadLinkNode(node) {
    return node instanceof PayloadLinkNode;
}

/** Port of Lexical's $toggleLink for Payload link nodes. */
export function $toggleLink(payload) {
    const selection = L.$getSelection();
    if (!L.$isRangeSelection(selection) && !(payload?.selectedNodes?.length)) {
        return;
    }
    const nodes = L.$isRangeSelection(selection) ? selection.extract() : payload.selectedNodes;
    if (payload === null) {
        const seen = new Set();
        for (const node of nodes) {
            const parent = L.$findMatchingParent(node, $isPayloadLinkNode);
            if (parent && !seen.has(parent.getKey())) {
                seen.add(parent.getKey());
                for (const child of parent.getChildren()) {
                    parent.insertBefore(child);
                }
                parent.remove();
            }
        }
        return;
    }
    const fields = { linkType: "custom", newTab: false, url: "https://", ...(payload.fields || {}) };
    if (fields.linkType === "custom" && !fields.url) {
        fields.url = "https://";
    }
    if (nodes.length === 1) {
        const existing = L.$findMatchingParent(nodes[0], $isPayloadLinkNode);
        if (existing) {
            existing.setFields(fields);
            if (payload.text && payload.text !== existing.getTextContent()) {
                existing.clear();
                existing.append(L.$createTextNode(payload.text));
            }
            return;
        }
    }
    let prevParent = null;
    let linkNode = null;
    for (const node of nodes) {
        const parent = node.getParent();
        if (parent === linkNode || parent === null || (L.$isElementNode(node) && !node.isInline())) {
            continue;
        }
        if ($isPayloadLinkNode(parent)) {
            linkNode = parent;
            parent.setFields(fields);
            continue;
        }
        if (!parent.is(prevParent)) {
            prevParent = parent;
            linkNode = $createPayloadLinkNode({ fields });
            if ($isPayloadLinkNode(parent)) {
                if (node.getPreviousSibling() === null) {
                    parent.insertBefore(linkNode);
                } else {
                    parent.insertAfter(linkNode);
                }
            } else {
                node.insertBefore(linkNode);
            }
        }
        if ($isPayloadLinkNode(node)) {
            if (node.is(linkNode)) {
                continue;
            }
            if (linkNode !== null) {
                for (const child of node.getChildren()) {
                    linkNode.append(child);
                }
            }
            node.remove();
            continue;
        }
        if (linkNode !== null) {
            linkNode.append(node);
        }
    }
    if (payload.text && linkNode && nodes.length && linkNode.getTextContent() !== payload.text) {
        linkNode.clear();
        linkNode.append(L.$createTextNode(payload.text));
    }
}

// ----------------------------------------------------------------------
// Decorator helpers
// ----------------------------------------------------------------------
function button(className, iconName, tooltip, onClick) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `btn ${className} btn--icon btn--icon-style-without-border btn--icon-only btn--size-medium btn--icon-position-right btn--has-tooltip btn--withoutPopup btn--style-icon-label btn--round btn--withoutPopup`;
    btn.innerHTML = `<aside class="tooltip btn__tooltip tooltip--caret-center tooltip--position-top" title="${tooltip}"><div class="tooltip-content">${tooltip}</div></aside><span class="btn__content"><span class="btn__icon">${iconHTML(iconName)}</span></span>`;
    let timer;
    btn.addEventListener("pointerenter", () => {
        timer = setTimeout(() => btn.querySelector("aside").classList.add("tooltip--show"), 350);
    });
    btn.addEventListener("pointerleave", () => {
        clearTimeout(timer);
        btn.querySelector("aside").classList.remove("tooltip--show");
    });
    btn.addEventListener("mousedown", (ev) => ev.preventDefault());
    btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        onClick();
    });
    return btn;
}

function activeEditor() {
    try {
        return L.$getEditor();
    } catch {
        return null;
    }
}

function hostOf(editor) {
    return editor._payloadHost || {};
}

// ----------------------------------------------------------------------
// Upload
// ----------------------------------------------------------------------
export class UploadNode extends L.DecoratorNode {
    static getType() {
        return "upload";
    }

    static clone(node) {
        return new UploadNode({ data: { ...node.__data }, format: node.__format }, node.__key);
    }

    constructor({ data = {}, format = "" } = {}, key) {
        super(key);
        this.__data = { id: data.id || rowId(), fields: data.fields ?? null, relationTo: data.relationTo, value: data.value };
        this.__format = format || "";
    }

    static importJSON(json) {
        let value = json.value;
        if (value && typeof value === "object") {
            value = value.id;
        }
        return $createUploadNode({ data: { id: json.id, fields: json.fields ?? null, relationTo: json.relationTo, value }, format: json.format });
    }

    exportJSON() {
        const d = this.getLatest().__data;
        return { format: this.getLatest().__format || "", type: "upload", version: 3, id: d.id, fields: d.fields ?? null, relationTo: d.relationTo, value: d.value };
    }

    exportDOM() {
        const img = document.createElement("img");
        img.setAttribute("data-lexical-upload-id", this.__data.value);
        img.setAttribute("data-lexical-upload-relation-to", this.__data.relationTo);
        return { element: img };
    }

    createDOM(_config, editor) {
        const el = document.createElement("div");
        el.className = "LexicalEditorTheme__upload";
        el.contentEditable = "false";
        renderUpload(el, this.getKey(), this.__data, this.__format, editor);
        return el;
    }

    updateDOM(prevNode, dom, _config) {
        if (prevNode.__data.value !== this.__data.value || prevNode.__format !== this.__format) {
            renderUpload(dom, this.getKey(), this.__data, this.__format, activeEditor());
        }
        return false;
    }

    getData() {
        return this.getLatest().__data;
    }

    setFormat(format) {
        this.getWritable().__format = format;
    }

    getFormat() {
        return this.getLatest().__format;
    }

    decorate() {
        return null;
    }

    isInline() {
        return false;
    }

    getTextContent() {
        return "";
    }
}

export function $createUploadNode(opts) {
    return L.$applyNodeReplacement(new UploadNode(opts));
}

function renderUpload(el, key, data, format, editor) {
    const editable = editor ? editor.isEditable() : true;
    const collection = getCollection(data.relationTo);
    el.innerHTML = "";
    const contents = document.createElement("div");
    contents.className = "LexicalEditorTheme__upload__contents LexicalEditorTheme__upload__contents--landscape";
    if (format) {
        contents.dataset.align = format;
    }
    const card = document.createElement("div");
    card.className = "LexicalEditorTheme__upload__card";
    const media = document.createElement("div");
    media.className = "LexicalEditorTheme__upload__media";
    const thumb = document.createElement("div");
    thumb.className = "thumbnail thumbnail--size-none ";
    thumb.innerHTML = `<div class="shimmer-effect" style="height:100%;width:100%"><div class="shimmer-effect__shine" style="animation-delay:0ms"></div></div>`;
    media.appendChild(thumb);
    if (editable) {
        const overlay = document.createElement("div");
        overlay.className = "LexicalEditorTheme__upload__overlay LexicalEditorTheme__upload__floater";
        const actions = document.createElement("div");
        actions.className = "LexicalEditorTheme__upload__actions";
        actions.setAttribute("role", "toolbar");
        actions.appendChild(button("LexicalEditorTheme__upload__swap-drawer-toggler", "swap", "Swap Upload", () => hostOf(editor).openUploadDrawer?.({ replace: key })));
        actions.appendChild(
            button("LexicalEditorTheme__upload__removeButton", "x", "Remove Upload", () => editor.update(() => L.$getNodeByKey(key)?.remove()))
        );
        overlay.appendChild(actions);
        media.appendChild(overlay);
    }
    const meta = document.createElement("div");
    meta.className = "LexicalEditorTheme__upload__metaOverlay LexicalEditorTheme__upload__floater";
    const toggler = document.createElement("button");
    toggler.type = "button";
    toggler.className = "LexicalEditorTheme__upload__doc-drawer-toggler doc-drawer__toggler";
    toggler.setAttribute("aria-label", "Edit Media");
    const filename = document.createElement("strong");
    filename.className = "LexicalEditorTheme__upload__filename";
    filename.textContent = "Loading...";
    toggler.appendChild(filename);
    toggler.addEventListener("click", (ev) => {
        ev.preventDefault();
        hostOf(editor).openDocDrawer?.(data.relationTo, data.value);
    });
    const label = document.createElement("div");
    label.className = "LexicalEditorTheme__upload__collectionLabel";
    label.textContent = collection?.labels.singular || data.relationTo;
    meta.append(toggler, label);
    card.append(media, meta);
    contents.appendChild(card);
    el.appendChild(contents);

    const fill = () => {
        const doc = getCachedDoc(data.relationTo, data.value);
        if (!doc || doc.__missing) {
            filename.textContent = "Untitled";
            thumb.innerHTML = iconHTML("graphic-file");
            return;
        }
        filename.textContent = doc.filename || "Untitled";
        contents.dataset.filename = doc.filename || "";
        const src = doc.thumbnailURL || doc.url;
        if (src && doc.mimeType?.startsWith("image/")) {
            thumb.innerHTML = "";
            const img = document.createElement("img");
            img.src = src;
            if (doc.width) {
                img.width = doc.width;
                img.height = doc.height;
            }
            thumb.appendChild(img);
            if (doc.width && doc.height && doc.height > doc.width) {
                contents.classList.replace("LexicalEditorTheme__upload__contents--landscape", "LexicalEditorTheme__upload__contents--portrait");
            }
        } else {
            thumb.innerHTML = iconHTML("graphic-file");
        }
    };
    ensureDocs(data.relationTo, [data.value]).then(fill, fill);
}

// ----------------------------------------------------------------------
// Relationship
// ----------------------------------------------------------------------
export class RelationshipNode extends L.DecoratorNode {
    static getType() {
        return "relationship";
    }

    static clone(node) {
        return new RelationshipNode({ data: { ...node.__data }, format: node.__format }, node.__key);
    }

    constructor({ data = {}, format = "" } = {}, key) {
        super(key);
        this.__data = { relationTo: data.relationTo, value: data.value };
        this.__format = format || "";
    }

    static importJSON(json) {
        let value = json.value;
        if (value && typeof value === "object") {
            value = value.id;
        }
        return $createRelationshipNode({ data: { relationTo: json.relationTo, value }, format: json.format });
    }

    exportJSON() {
        const d = this.getLatest().__data;
        return { format: this.getLatest().__format || "", type: "relationship", version: 2, relationTo: d.relationTo, value: d.value };
    }

    createDOM(_config, editor) {
        const el = document.createElement("div");
        el.className = "LexicalEditorTheme__relationship";
        el.contentEditable = "false";
        renderRelationship(el, this.getKey(), this.__data, editor);
        return el;
    }

    updateDOM(prevNode, dom) {
        if (prevNode.__data.value !== this.__data.value) {
            renderRelationship(dom, this.getKey(), this.__data, activeEditor());
        }
        return false;
    }

    setFormat(format) {
        this.getWritable().__format = format;
    }

    decorate() {
        return null;
    }

    isInline() {
        return false;
    }

    getTextContent() {
        return "";
    }
}

export function $createRelationshipNode(opts) {
    return L.$applyNodeReplacement(new RelationshipNode(opts));
}

function renderRelationship(el, key, data, editor) {
    const editable = editor ? editor.isEditable() : true;
    const collection = getCollection(data.relationTo);
    el.innerHTML = "";
    const contents = document.createElement("div");
    contents.className = "LexicalEditorTheme__relationship__contents";
    contents.contentEditable = "false";
    const wrap = document.createElement("div");
    wrap.className = "LexicalEditorTheme__relationship__wrap";
    const label = document.createElement("p");
    label.className = "LexicalEditorTheme__relationship__label";
    label.textContent = `${collection?.labels.singular || data.relationTo} Relationship`;
    const toggler = document.createElement("button");
    toggler.type = "button";
    toggler.className = "LexicalEditorTheme__relationship__doc-drawer-toggler doc-drawer__toggler";
    toggler.setAttribute("aria-label", `Edit ${collection?.labels.singular || ""}`);
    const title = document.createElement("p");
    title.className = "LexicalEditorTheme__relationship__title";
    title.textContent = String(data.value);
    toggler.appendChild(title);
    toggler.addEventListener("click", (ev) => {
        ev.preventDefault();
        hostOf(editor).openDocDrawer?.(data.relationTo, data.value);
    });
    wrap.append(label, toggler);
    contents.appendChild(wrap);
    if (editable) {
        const actions = document.createElement("div");
        actions.className = "LexicalEditorTheme__relationship__actions";
        actions.appendChild(button("LexicalEditorTheme__relationship__swapButton", "swap", "Swap Relationship", () => hostOf(editor).openRelationshipDrawer?.({ replace: key })));
        actions.appendChild(
            button("LexicalEditorTheme__relationship__removeButton", "x", "Remove Relationship", () => editor.update(() => L.$getNodeByKey(key)?.remove()))
        );
        contents.appendChild(actions);
    }
    el.appendChild(contents);
    const fill = () => {
        const doc = getCachedDoc(data.relationTo, data.value);
        if (doc && !doc.__missing) {
            title.textContent = docTitle(collection, doc) || String(data.value);
        }
    };
    ensureDocs(data.relationTo, [data.value]).then(fill, fill);
}

// ----------------------------------------------------------------------
// Horizontal rule
// ----------------------------------------------------------------------
export class HorizontalRuleNode extends L.DecoratorNode {
    static getType() {
        return "horizontalrule";
    }

    static clone(node) {
        return new HorizontalRuleNode(node.__key);
    }

    static importJSON() {
        return $createHorizontalRuleNode();
    }

    static importDOM() {
        return { hr: () => ({ conversion: () => ({ node: $createHorizontalRuleNode() }), priority: 0 }) };
    }

    exportJSON() {
        return { type: "horizontalrule", version: 1 };
    }

    exportDOM() {
        return { element: document.createElement("hr") };
    }

    createDOM(config) {
        const el = document.createElement("hr");
        L.addClassNamesToElement(el, config.theme.hr);
        el.contentEditable = "false";
        return el;
    }

    updateDOM() {
        return false;
    }

    getTextContent() {
        return "\n";
    }

    isInline() {
        return false;
    }

    decorate() {
        return null;
    }
}

export function $createHorizontalRuleNode() {
    return L.$applyNodeReplacement(new HorizontalRuleNode());
}

export function $isHorizontalRuleNode(node) {
    return node instanceof HorizontalRuleNode;
}

export const PAYLOAD_NODES = [
    L.HeadingNode,
    L.QuoteNode,
    L.ListNode,
    L.ListItemNode,
    PayloadLinkNode,
    UploadNode,
    RelationshipNode,
    HorizontalRuleNode,
];
