/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, reactive, status, useRef, useState } from "@odoo/owl";
import { t } from "../core/i18n";
import { cacheDoc, ensureDocs, getCachedDoc, relationLabel, searchDocs } from "../core/relations";
import { checkCondition, defaultValues } from "../core/schema";
import { getCollection, openDrawer } from "../core/store";
import { drawerViews, openDocumentDrawer, openListDrawer } from "../core/drawers";
import { debounce, deepCopy, formatFilesize, icon, rowId, rowLabels, slugify } from "../core/utils";
import { AnimateHeight, Banner, Button, CheckboxInput, FieldError, Popup, PopupButton, Select, ShimmerEffect, Thumbnail } from "../components/base";
import { FieldBase } from "./field_base";
import { RichTextField } from "../richtext/richtext_field";

function joinPath(path, name) {
    return path ? `${path}.${name}` : name;
}

// ----------------------------------------------------------------------
// Simple inputs
// ----------------------------------------------------------------------
export class TextField extends FieldBase {
    static template = "payload.TextField";
    static components = { FieldError };

    onInput(ev) {
        this.setValue(ev.target.value);
    }
}

export class EmailField extends TextField {
    static template = "payload.EmailField";
}

export class PasswordField extends TextField {
    static template = "payload.PasswordField";
}

export class TextareaField extends TextField {
    static template = "payload.TextareaField";
}

export class NumberField extends FieldBase {
    static template = "payload.NumberField";
    static components = { FieldError };

    onInput(ev) {
        const raw = ev.target.value;
        const n = parseFloat(raw);
        this.setValue(raw === "" || isNaN(n) ? null : n);
    }
}

export class CheckboxField extends FieldBase {
    static template = "payload.CheckboxField";
    static components = { FieldError, CheckboxInput };
}

export class RadioField extends FieldBase {
    static template = "payload.RadioField";
    static components = { FieldError };

    get options() {
        return (this.field.options || []).map((o) => (typeof o === "string" ? { value: o, label: o } : o));
    }
}

export class SelectField extends FieldBase {
    static template = "payload.SelectField";
    static components = { FieldError, Select };

    get options() {
        return (this.field.options || []).map((o) => (typeof o === "string" ? { value: o, label: o } : o));
    }
}

export class DateField extends FieldBase {
    static template = "payload.DateField";
    static components = { FieldError };

    get appearance() {
        return this.admin.date?.pickerAppearance || "default";
    }

    get inputType() {
        return { dayAndTime: "datetime-local", timeOnly: "time" }[this.appearance] || "date";
    }

    get inputValue() {
        const v = this.value;
        if (!v) {
            return "";
        }
        const d = new Date(v);
        if (isNaN(d)) {
            return "";
        }
        const pad = (n) => String(n).padStart(2, "0");
        const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
        const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
        return this.inputType === "datetime-local" ? `${date}T${time}` : this.inputType === "time" ? time : date;
    }

    onChange(ev) {
        const raw = ev.target.value;
        if (!raw) {
            this.setValue(null);
            return;
        }
        let d;
        if (this.inputType === "date") {
            // Payload stores date-only values at 12:00 UTC.
            d = new Date(`${raw}T12:00:00.000Z`);
        } else if (this.inputType === "time") {
            d = new Date();
            const [h, m] = raw.split(":");
            d.setHours(+h, +m, 0, 0);
        } else {
            d = new Date(raw);
        }
        this.setValue(d.toISOString());
    }

    clear() {
        this.setValue(null);
    }
}

export class CodeField extends FieldBase {
    static template = "payload.CodeField";
    static components = { FieldError };

    setup() {
        super.setup();
        this.state = useState({ text: null, jsonError: null });
    }

    get isJson() {
        return this.field.type === "json";
    }

    get text() {
        if (this.state.text !== null) {
            return this.state.text;
        }
        const v = this.value;
        if (this.isJson) {
            return v === undefined || v === null ? "" : JSON.stringify(v, null, 2);
        }
        return v || "";
    }

    get rows() {
        return Math.max(3, this.text.split("\n").length);
    }

    onInput(ev) {
        const raw = ev.target.value;
        this.state.text = raw;
        if (!this.isJson) {
            this.setValue(raw);
            return;
        }
        if (!raw.trim()) {
            this.state.jsonError = null;
            this.setValue(null);
            return;
        }
        try {
            this.setValue(JSON.parse(raw));
            this.state.jsonError = null;
        } catch (e) {
            this.state.jsonError = e.message;
        }
    }
}

/** Payload 3.90 slugField: locked by default, follows the source field until unlocked. */
export class SlugField extends FieldBase {
    static template = "payload.SlugField";
    static components = { FieldError, Button };

    setup() {
        super.setup();
        this.state = useState({ locked: true });
        this.listener = (path, value) => {
            const source = this.field.useAsSlug || "title";
            const sourcePath = this.props.path.replace(/[^.]+$/, source);
            if (this.state.locked && path === sourcePath && typeof value === "string") {
                this.props.data[this.field.name] = slugify(value);
                this.env.form.onChange(this.props.path, this.props.data[this.field.name]);
            }
        };
        this.env.form.listeners.add(this.listener);
        onWillUnmount(() => this.env.form.listeners.delete(this.listener));
    }

    generate() {
        const source = this.field.useAsSlug || "title";
        this.setValue(slugify(this.props.data[source] || ""));
    }

    toggleLock() {
        this.state.locked = !this.state.locked;
    }

    onInput(ev) {
        this.setValue(ev.target.value);
    }
}

// ----------------------------------------------------------------------
// Relationship & upload
// ----------------------------------------------------------------------
export class RelationshipField extends FieldBase {
    static template = "payload.RelationshipField";
    static components = { FieldError, Select };

    setup() {
        super.setup();
        this.state = useState({ options: [], loading: false, page: 1, hasNextPage: false, search: "" });
        this.onSearch = debounce((q) => this.load(q, 1), 300);
        onWillStart(() => this.ensureLabels());
    }

    get relationTo() {
        return this.field.relationTo;
    }

    get collection() {
        return getCollection(this.relationTo);
    }

    get ids() {
        const v = this.value;
        const list = Array.isArray(v) ? v : v === undefined || v === null ? [] : [v];
        return list.map((x) => (x && typeof x === "object" ? x.id ?? x.value : x));
    }

    async ensureLabels() {
        if (this.ids.length) {
            await ensureDocs(this.relationTo, this.ids);
        }
    }

    labelOf(id) {
        return relationLabel(this.relationTo, id);
    }

    async load(search = "", page = 1) {
        this.state.loading = true;
        try {
            const res = await searchDocs(this.relationTo, search, page);
            this.state.options = page === 1 ? res.options : [...this.state.options, ...res.options];
            this.state.hasNextPage = res.hasNextPage;
            this.state.page = page;
            this.state.search = search;
        } finally {
            this.state.loading = false;
        }
    }

    loadMore() {
        if (this.state.hasNextPage && !this.state.loading) {
            this.load(this.state.search, this.state.page + 1);
        }
    }

    onChange(value) {
        this.setValue(this.field.hasMany ? value || [] : value);
    }

    async addNew() {
        const doc = await openDocumentDrawer(this.relationTo, null);
        if (doc?.id) {
            cacheDoc(this.relationTo, doc);
            if (this.field.hasMany) {
                this.setValue([...this.ids, doc.id]);
            } else {
                this.setValue(doc.id);
            }
        }
    }

    async edit(id) {
        const doc = await openDocumentDrawer(this.relationTo, id);
        if (doc?.id) {
            cacheDoc(this.relationTo, doc);
        }
    }
}

export class UploadField extends FieldBase {
    static template = "payload.UploadField";
    static components = { FieldError, Button, Thumbnail, ShimmerEffect };

    setup() {
        super.setup();
        this.state = useState({ dragging: false });
        this.fileInput = useRef("fileInput");
        this.formatFilesize = formatFilesize;
        onWillStart(() => this.ensure());
    }

    get relationTo() {
        return this.field.relationTo;
    }

    get collection() {
        return getCollection(this.relationTo);
    }

    get ids() {
        const v = this.value;
        const list = Array.isArray(v) ? v : v === undefined || v === null ? [] : [v];
        return list.map((x) => (x && typeof x === "object" ? x.id : x));
    }

    async ensure() {
        if (this.ids.length) {
            await ensureDocs(this.relationTo, this.ids);
        }
    }

    doc(id) {
        return getCachedDoc(this.relationTo, id);
    }

    get showDropzone() {
        if (!this.ids.length) {
            return true;
        }
        if (this.field.hasMany) {
            return !this.field.maxRows || this.ids.length < this.field.maxRows;
        }
        return false;
    }

    meta(doc) {
        return [formatFilesize(doc.filesize), doc.width && doc.height ? `${doc.width}x${doc.height}` : null, doc.mimeType].filter(Boolean).join(" — ");
    }

    thumb(doc) {
        return doc?.thumbnailURL || (doc?.mimeType?.startsWith("image/") ? doc.url : null);
    }

    add(id) {
        if (this.field.hasMany) {
            this.setValue([...this.ids, id]);
        } else {
            this.setValue(id);
        }
    }

    remove(id) {
        if (this.field.hasMany) {
            this.setValue(this.ids.filter((x) => x !== id));
        } else {
            this.setValue(null);
        }
    }

    async createNew(file = null) {
        const doc = await openDocumentDrawer(this.relationTo, null, { initialFile: file });
        if (doc?.id) {
            cacheDoc(this.relationTo, doc);
            this.add(doc.id);
        }
    }

    async chooseExisting() {
        const doc = await openListDrawer(this.relationTo, {
            onCreate: () => this.createNew(),
        });
        if (doc?.id) {
            await ensureDocs(this.relationTo, [doc.id]);
            this.add(doc.id);
        }
    }

    async edit(id) {
        const doc = await openDocumentDrawer(this.relationTo, id);
        if (doc?.id) {
            cacheDoc(this.relationTo, doc);
        }
    }

    onDrop(ev) {
        ev.preventDefault();
        this.state.dragging = false;
        const file = ev.dataTransfer?.files?.[0];
        if (file && !this.readOnly) {
            this.createNew(file);
        }
    }
}

// ----------------------------------------------------------------------
// Containers
// ----------------------------------------------------------------------
export class RenderFields extends Component {
    static template = "payload.RenderFields";

    setup() {
        // re-render when a sibling value used by an `admin.condition` changes
        this.observed = null;
        this.rerender = () => status(this) === "mounted" && this.render();
    }

    get siblingData() {
        const data = this.props.data;
        if (!data || typeof data !== "object" || !(this.props.fields || []).some((f) => f.admin?.condition)) {
            return data || {};
        }
        if (this.observed?.source !== data) {
            this.observed = { source: data, proxy: reactive(data, this.rerender) };
        }
        return this.observed.proxy;
    }

    get fields() {
        const siblings = this.siblingData;
        return (this.props.fields || []).filter((f) => !f.admin?.hidden && checkCondition(f, siblings));
    }

    componentFor(field) {
        return FIELD_COMPONENTS[field.type] || TextField;
    }

    childPath(field) {
        return field.name ? joinPath(this.props.path || "", field.name) : this.props.path || "";
    }

    get classes() {
        const c = ["render-fields"];
        if (this.props.margins === "small") {
            c.push("render-fields--margins-small");
        } else if (this.props.margins === false) {
            c.push("render-fields--margins-none");
        }
        if (this.props.className) {
            c.push(this.props.className);
        }
        return c.join(" ");
    }
}

export class GroupField extends FieldBase {
    static template = "payload.GroupField";
    static components = { RenderFields };

    get groupData() {
        if (!this.props.data[this.field.name] || typeof this.props.data[this.field.name] !== "object") {
            this.props.data[this.field.name] = {};
        }
        return this.props.data[this.field.name];
    }
}

export class RowField extends FieldBase {
    static template = "payload.RowField";
    static components = { RenderFields };
}

export class CollapsibleField extends FieldBase {
    static template = "payload.CollapsibleField";
    static components = { RenderFields, AnimateHeight };

    setup() {
        super.setup();
        this.state = useState({ collapsed: Boolean(this.admin.initCollapsed) });
    }
}

export class TabsField extends FieldBase {
    static template = "payload.TabsField";
    static components = { RenderFields };

    setup() {
        super.setup();
        this.state = useState({ active: 0 });
    }

    get tabs() {
        return this.field.tabs || [];
    }

    tabData(tab) {
        if (!tab.name) {
            return this.props.data;
        }
        if (!this.props.data[tab.name] || typeof this.props.data[tab.name] !== "object") {
            this.props.data[tab.name] = {};
        }
        return this.props.data[tab.name];
    }

    tabPath(tab) {
        return tab.name ? joinPath(this.props.path, tab.name) : this.props.path;
    }

    tabErrors(tab) {
        if (!this.form.submitted && !this.form.serverErrors) {
            return 0;
        }
        const prefixes = tab.name
            ? [this.tabPath(tab)]
            : (tab.fields || []).filter((f) => f.name).map((f) => joinPath(this.props.path, f.name));
        return Object.keys(this.form.errors).filter((p) => prefixes.some((pre) => p === pre || p.startsWith(`${pre}.`))).length;
    }
}

/** Shared logic of array & blocks fields. */
class RowsField extends FieldBase {
    setup() {
        super.setup();
        this.state = useState({ collapsed: {} });
    }

    get rows() {
        const v = this.observe(this.props.data)[this.field.name];
        if (!Array.isArray(v)) {
            return [];
        }
        return this.observe(v);
    }

    get rawRows() {
        if (!Array.isArray(this.props.data[this.field.name])) {
            this.props.data[this.field.name] = [];
        }
        return this.props.data[this.field.name];
    }

    get labels() {
        return rowLabels(this.field, this.field.type === "blocks" ? { singular: "Block", plural: "Blocks" } : undefined);
    }

    get hasMaxRows() {
        return Boolean(this.field.maxRows) && this.rows.length >= this.field.maxRows;
    }

    rowNumber(i) {
        return String(i + 1).padStart(2, "0");
    }

    isCollapsed(row) {
        const value = this.state.collapsed[row.id];
        return value === undefined ? Boolean(this.admin.initCollapsed) : value;
    }

    toggle(row) {
        this.state.collapsed[row.id] = !this.isCollapsed(row);
    }

    setAll(collapsed) {
        for (const row of this.rawRows) {
            this.state.collapsed[row.id] = collapsed;
        }
    }

    changed() {
        this.env.form.onChange(this.props.path, this.rawRows);
    }

    moveRow(from, to) {
        const rows = this.rawRows;
        if (to < 0 || to >= rows.length) {
            return;
        }
        const [row] = rows.splice(from, 1);
        rows.splice(to, 0, row);
        this.changed();
    }

    removeRow(i) {
        this.rawRows.splice(i, 1);
        this.changed();
    }

    duplicateRow(i) {
        const copy = deepCopy(this.rawRows[i]);
        const renew = (obj) => {
            if (Array.isArray(obj)) {
                obj.forEach(renew);
            } else if (obj && typeof obj === "object") {
                if (typeof obj.id === "string" && /^[0-9a-f]{24}$/.test(obj.id)) {
                    obj.id = rowId();
                }
                Object.values(obj).forEach(renew);
            }
        };
        renew(copy);
        copy.id = rowId();
        this.rawRows.splice(i + 1, 0, copy);
        this.changed();
    }

    rowPath(i) {
        return `${this.props.path}.${i}`;
    }

    rowErrors(i) {
        return this.errorCount(this.rowPath(i));
    }

    // native drag & drop reordering
    onDragOver() {}

    onDragStart(ev, i) {
        ev.dataTransfer.setData("text/payload-row", String(i));
        ev.dataTransfer.effectAllowed = "move";
    }

    onDrop(ev, i) {
        const from = ev.dataTransfer.getData("text/payload-row");
        if (from !== "") {
            ev.preventDefault();
            this.moveRow(Number(from), i);
        }
    }
}

export class ArrayField extends RowsField {
    static template = "payload.ArrayField";
    static components = { RenderFields, Popup, PopupButton, Button, AnimateHeight, FieldError, Banner };

    addRow(index = this.rawRows.length) {
        const row = defaultValues(this.field.fields || [], {});
        row.id = rowId();
        this.rawRows.splice(index, 0, row);
        this.state.collapsed[row.id] = false;
        this.changed();
    }
}

export class BlocksField extends RowsField {
    static template = "payload.BlocksField";
    static components = { RenderFields, Popup, PopupButton, Button, AnimateHeight, FieldError, Banner };

    get blocks() {
        return this.field.blocks || [];
    }

    blockFor(row) {
        return this.blocks.find((b) => b.slug === row.blockType);
    }

    blockLabel(row) {
        return this.blockFor(row)?.labels?.singular || row.blockType;
    }

    async addBlock(index = this.rawRows.length) {
        const block = await openDrawer(BlocksDrawer, { blocks: this.blocks }, { title: t("fields:addLabel", { label: this.labels.singular }), className: "blocks-drawer" });
        if (!block) {
            return;
        }
        const row = defaultValues(block.fields || [], {});
        row.id = rowId();
        row.blockType = block.slug;
        this.rawRows.splice(index, 0, row);
        this.state.collapsed[row.id] = false;
        this.changed();
    }

    setBlockName(row, ev) {
        row.blockName = ev.target.value;
        this.changed();
    }
}

/** Payload's BlocksDrawer (block selector with search). */
export class BlocksDrawer extends Component {
    static template = "payload.BlocksDrawer";

    setup() {
        this.state = useState({ search: "" });
        this.t = t;
        this.icon = icon;
    }

    get blocks() {
        const q = this.state.search.toLowerCase();
        return this.props.blocks.filter((b) => (b.labels?.singular || b.slug).toLowerCase().includes(q));
    }
}

export const FIELD_COMPONENTS = {
    text: TextField,
    email: EmailField,
    password: PasswordField,
    textarea: TextareaField,
    number: NumberField,
    checkbox: CheckboxField,
    radio: RadioField,
    select: SelectField,
    date: DateField,
    code: CodeField,
    json: CodeField,
    slug: SlugField,
    relationship: RelationshipField,
    upload: UploadField,
    group: GroupField,
    row: RowField,
    collapsible: CollapsibleField,
    tabs: TabsField,
    array: ArrayField,
    blocks: BlocksField,
    richText: RichTextField,
};

drawerViews.RenderFields = RenderFields;
