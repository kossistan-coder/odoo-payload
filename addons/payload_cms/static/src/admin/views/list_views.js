/** @odoo-module **/

import { Component, markup, onWillStart, useState } from "@odoo/owl";
import { api, ApiError, request } from "../core/api";
import { ensureDocs, relationLabel } from "../core/relations";
import { dataFields, listColumns } from "../core/schema";
import { apiBase, adminBase, toast } from "../core/store";
import { navigate } from "../core/router";
import { docTitle, formatDate, icon } from "../core/utils";
import { Select, Thumbnail } from "../components/base";

/**
 * Alternative views of a collection (Odoo's kanban / pivot / graph / calendar),
 * rendered with Payload's design system. They share the search and filters of
 * the list view (`where` prop).
 */

export const VIEW_MODES = [
    { key: "list", label: "List", icon: "view-list" },
    { key: "kanban", label: "Kanban", icon: "view-kanban" },
    { key: "pivot", label: "Pivot", icon: "view-pivot" },
    { key: "graph", label: "Graph", icon: "view-graph" },
    { key: "calendar", label: "Calendar", icon: "view-calendar" },
];

const INTERVALS = [
    { value: "day", label: "Day" },
    { value: "week", label: "Week" },
    { value: "month", label: "Month" },
    { value: "quarter", label: "Quarter" },
    { value: "year", label: "Year" },
];
// The first colour follows the theme (dark grey on light, light grey on dark).
const PALETTE = ["var(--theme-elevation-800)", "#6b8afd", "#4caf82", "#f2b441", "#e0675c", "#8c6bd9", "#3fb3c4", "#a3a3a3", "#d96ba5", "#7a9a3d"];

function statusField() {
    return { name: "_status", type: "select", label: "Status", options: [{ value: "draft", label: "Draft" }, { value: "published", label: "Published" }] };
}

/** Fields a collection can be grouped by (kanban columns, pivot rows, graph axis). */
export function groupableFields(collection, { dates = true, kanban = false } = {}) {
    const result = [];
    if (collection.versions?.drafts) {
        result.push({ value: "_status", label: "Status", field: statusField(), kind: "status" });
    }
    const walk = (fields, prefix, labelPrefix) => {
        for (const field of dataFields(fields || [])) {
            const path = prefix ? `${prefix}.${field.name}` : field.name;
            const label = `${labelPrefix}${typeof field.label === "string" && field.label ? field.label : field.name}`;
            if (field.type === "group") {
                walk(field.fields, path, `${label} › `);
                continue;
            }
            if (["select", "radio"].includes(field.type) && !field.hasMany) {
                result.push({ value: path, label, field, kind: "select" });
            } else if (field.type === "checkbox") {
                result.push({ value: path, label, field, kind: "checkbox" });
            } else if (["relationship", "upload"].includes(field.type) && !field.hasMany && typeof field.relationTo === "string") {
                result.push({ value: path, label, field, kind: "relationship" });
            } else if (field.type === "date" && dates) {
                result.push({ value: path, label, field, kind: "date" });
            } else if (!kanban && ["text", "email", "number"].includes(field.type) && !field.hasMany && !field.localized) {
                result.push({ value: path, label, field, kind: field.type });
            }
        }
    };
    walk(collection.fields, "", "");
    if (dates) {
        result.push({ value: "createdAt", label: "Created At", field: { name: "createdAt", type: "date" }, kind: "date" });
        result.push({ value: "updatedAt", label: "Updated At", field: { name: "updatedAt", type: "date" }, kind: "date" });
    }
    return result;
}

function numberFields(collection) {
    const result = [];
    const walk = (fields, prefix, labelPrefix) => {
        for (const field of dataFields(fields || [])) {
            const path = prefix ? `${prefix}.${field.name}` : field.name;
            const label = `${labelPrefix}${field.label || field.name}`;
            if (field.type === "group") {
                walk(field.fields, path, `${label} › `);
            } else if (field.type === "number" && !field.hasMany) {
                result.push({ path, label });
            }
        }
    };
    walk(collection.fields, "", "");
    return result;
}

function measureOptions(collection) {
    const options = [{ value: "count", label: "Count" }];
    for (const { path, label } of numberFields(collection)) {
        options.push({ value: `sum:${path}`, label: `${label} (sum)` }, { value: `avg:${path}`, label: `${label} (average)` },
            { value: `max:${path}`, label: `${label} (max)` }, { value: `min:${path}`, label: `${label} (min)` });
    }
    return options;
}

function getPath(doc, path) {
    return path.split(".").reduce((obj, key) => (obj && typeof obj === "object" ? obj[key] : undefined), doc);
}

function loadSettings(collection, view, defaults) {
    try {
        return { ...defaults, ...JSON.parse(localStorage.getItem(`payload-view-${collection.slug}-${view}`) || "{}") };
    } catch {
        return { ...defaults };
    }
}

function saveSettings(collection, view, settings) {
    try {
        localStorage.setItem(`payload-view-${collection.slug}-${view}`, JSON.stringify(settings));
    } catch {
        // storage unavailable
    }
}

function andWhere(...clauses) {
    const list = clauses.filter(Boolean);
    return list.length > 1 ? { and: list } : list[0];
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Label of a group key (dates: by interval). */
function keyLabel(key, labels, kind, interval) {
    if (key === null || key === undefined || key === "") {
        return "None";
    }
    if (labels && labels[String(key)] !== undefined) {
        return labels[String(key)];
    }
    if (kind === "date" && /^\d{4}-\d{2}-\d{2}/.test(key)) {
        const [y, m, d] = key.split("-").map(Number);
        switch (interval) {
            case "year":
                return String(y);
            case "quarter":
                return `Q${Math.floor((m - 1) / 3) + 1} ${y}`;
            case "month":
                return `${MONTHS[m - 1]} ${y}`;
            case "week":
                return `Week of ${MONTHS[m - 1]} ${d}, ${y}`;
            default:
                return `${MONTHS[m - 1]} ${d}, ${y}`;
        }
    }
    return String(key);
}

function formatNumber(value) {
    if (value === null || value === undefined) {
        return "";
    }
    const number = Number(value);
    return number.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

export class ViewSwitcher extends Component {
    static template = "payload.ViewSwitcher";

    setup() {
        this.icon = icon;
    }

    get modes() {
        return VIEW_MODES;
    }

    get current() {
        return this.props.current;
    }
}

// ----------------------------------------------------------------------
// Kanban
// ----------------------------------------------------------------------
export class KanbanView extends Component {
    static template = "payload.KanbanView";
    // `Cell` (list.js) is registered by the list view, which imports this module
    static components = { Select, Thumbnail };

    setup() {
        this.icon = icon;
        this.formatDate = formatDate;
        const options = this.groupOptions;
        const settings = loadSettings(this.props.collection, "kanban", { groupBy: options[0]?.value || "" });
        if (!options.some((o) => o.value === settings.groupBy)) {
            settings.groupBy = options[0]?.value || "";
        }
        this.state = useState({ ...settings, docs: [], loading: true, dragging: null, over: null, total: 0 });
        onWillStart(() => this.load());
    }

    get collection() {
        return this.props.collection;
    }

    get groupOptions() {
        return groupableFields(this.collection, { dates: false, kanban: true }).map(({ value, label }) => ({ value, label }));
    }

    get group() {
        return groupableFields(this.collection, { dates: false, kanban: true }).find((g) => g.value === this.state.groupBy);
    }

    async load(props = this.props) {
        this.state.loading = true;
        try {
            const res = await api.get(apiBase(props.collection), { depth: 0, draft: "true", _admin: "1", limit: 300, sort: "-updatedAt", where: props.where });
            this.state.docs = res.docs;
            this.state.total = res.totalDocs;
            await this.loadRelations(res.docs);
        } catch (e) {
            toast.error(e.message);
        } finally {
            this.state.loading = false;
        }
    }

    async loadRelations(docs) {
        const wanted = {};
        const add = (slug, value) => {
            const id = value && typeof value === "object" ? value.id : value;
            if (slug && id !== undefined && id !== null) {
                (wanted[slug] ||= new Set()).add(id);
            }
        };
        for (const column of this.cardColumns) {
            if (["relationship", "upload"].includes(column.field.type) && typeof column.field.relationTo === "string") {
                docs.forEach((d) => [].concat(d[column.accessor] ?? []).forEach((v) => add(column.field.relationTo, v)));
            }
        }
        const group = this.group;
        if (group?.kind === "relationship") {
            docs.forEach((d) => add(group.field.relationTo, getPath(d, group.value)));
        }
        await Promise.all(Object.entries(wanted).map(([slug, ids]) => ensureDocs(slug, [...ids])));
    }

    setGroupBy(value) {
        this.state.groupBy = value;
        saveSettings(this.collection, "kanban", { groupBy: value });
        this.loadRelations(this.state.docs);
    }

    valueOf(doc) {
        const value = getPath(doc, this.state.groupBy);
        return value && typeof value === "object" ? value.id : value;
    }

    get columns() {
        const group = this.group;
        if (!group) {
            return [];
        }
        let columns = [];
        if (group.kind === "status" || group.kind === "select") {
            columns = (group.field.options || []).map((o) => (typeof o === "object" ? { value: o.value, label: o.label || o.value } : { value: o, label: o }));
        } else if (group.kind === "checkbox") {
            columns = [{ value: true, label: "Yes" }, { value: false, label: "No" }];
        } else if (group.kind === "relationship") {
            const ids = [...new Set(this.state.docs.map((d) => this.valueOf(d)).filter((v) => v !== null && v !== undefined))];
            columns = ids.map((id) => ({ value: id, label: relationLabel(group.field.relationTo, id) || `#${id}` }));
        }
        const known = new Set(columns.map((c) => String(c.value)));
        const result = columns.map((c) => ({ ...c, key: String(c.value), docs: [] }));
        const none = { value: null, label: "None", key: "__none__", docs: [] };
        for (const doc of this.state.docs) {
            let value = this.valueOf(doc);
            if (group.kind === "checkbox") {
                value = Boolean(value);
            }
            if (group.kind === "status") {
                value = value || "draft";
            }
            const column = known.has(String(value)) ? result.find((c) => c.key === String(value)) : none;
            column.docs.push(doc);
        }
        if (none.docs.length || group.kind === "relationship") {
            result.push(none);
        }
        return result;
    }

    get titleField() {
        return this.collection.admin?.useAsTitle || "id";
    }

    /** Up to 3 fields shown on the cards: the default columns of the collection. */
    get cardColumns() {
        const all = listColumns(this.collection);
        const defaults = this.collection.admin?.defaultColumns?.length ? this.collection.admin.defaultColumns : all.map((c) => c.accessor);
        return defaults
            .filter((a) => ![this.titleField, this.state.groupBy, "id", "updatedAt", "createdAt", "filename"].includes(a))
            .map((a) => all.find((c) => c.accessor === a))
            .filter((c) => c && !["richText", "array", "blocks", "json", "group"].includes(c.field.type))
            .slice(0, 3);
    }

    title(doc) {
        return docTitle(this.collection, doc) || `#${doc.id}`;
    }

    href(doc) {
        return `${adminBase(this.collection)}/${doc.id}`;
    }

    thumbnail(doc) {
        return this.collection.upload ? doc.thumbnailURL || (doc.mimeType?.startsWith("image/") ? doc.url : null) : null;
    }

    open(doc) {
        navigate(this.href(doc));
    }

    onDragStart(ev, doc) {
        this.state.dragging = doc.id;
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", String(doc.id));
    }

    onDragEnd() {
        this.state.dragging = null;
        this.state.over = null;
    }

    async onDrop(column) {
        const id = this.state.dragging;
        this.state.over = null;
        this.state.dragging = null;
        const doc = this.state.docs.find((d) => d.id === id);
        if (!doc || String(this.valueOf(doc)) === String(column.value)) {
            return;
        }
        const group = this.group;
        const path = group.value.split(".");
        const body = {};
        let target = body;
        path.slice(0, -1).forEach((key) => {
            target[key] = { ...(getPath(doc, path.slice(0, path.indexOf(key) + 1).join(".")) || {}) };
            target = target[key];
        });
        target[path[path.length - 1]] = column.value;
        const previous = getPath(doc, group.value);
        // optimistic move
        this.setPath(doc, group.value, column.value);
        try {
            const res = await request(`${apiBase(this.collection)}/${doc.id}`, { method: "PATCH", body, params: { depth: 0, _admin: "1" } });
            Object.assign(doc, res.doc);
            toast.success(`${this.title(doc)} → ${column.label}`);
        } catch (e) {
            this.setPath(doc, group.value, previous);
            toast.error(e instanceof ApiError && e.fieldErrors?.length ? `${e.message}: ${e.fieldErrors.map((f) => f.message).join(", ")}` : e.message);
        }
    }

    setPath(doc, path, value) {
        const keys = path.split(".");
        let obj = doc;
        keys.slice(0, -1).forEach((key) => {
            obj[key] = obj[key] && typeof obj[key] === "object" ? obj[key] : {};
            obj = obj[key];
        });
        obj[keys[keys.length - 1]] = value;
    }
}

// ----------------------------------------------------------------------
// Pivot
// ----------------------------------------------------------------------
class AggregateView extends Component {
    setup() {
        this.icon = icon;
        const groups = this.groupFields;
        const defaults = this.defaults(groups);
        const settings = loadSettings(this.props.collection, this.viewName, defaults);
        for (const key of ["rows", "cols", "x", "stack"]) {
            if (settings[key] && !groups.some((g) => g.value === settings[key])) {
                settings[key] = defaults[key] || "";
            }
        }
        if (!this.measures.some((m) => m.value === settings.measure)) {
            settings.measure = "count";
        }
        this.state = useState({ ...settings, data: null, loading: true });
        onWillStart(() => this.load());
    }

    get collection() {
        return this.props.collection;
    }

    get groupFields() {
        return groupableFields(this.props.collection);
    }

    get groupOptions() {
        return this.groupFields.map(({ value, label }) => ({ value, label }));
    }

    get optionalGroupOptions() {
        return [{ value: "__none__", label: "None" }, ...this.groupOptions];
    }

    get measures() {
        return measureOptions(this.props.collection);
    }

    get intervals() {
        return INTERVALS;
    }

    kindOf(path) {
        return this.groupFields.find((g) => g.value === path)?.kind;
    }

    spec(path) {
        return this.kindOf(path) === "date" ? `${path}:${this.state.interval || "month"}` : path;
    }

    get hasDateGroup() {
        return this.axes.some((a) => this.kindOf(a) === "date");
    }

    get settingsToSave() {
        const { data, loading, ...settings } = this.state;
        return settings;
    }

    set(key, value) {
        this.state[key] = value === "__none__" ? "" : value;
        saveSettings(this.collection, this.viewName, this.settingsToSave);
        this.load();
    }

    async load(props = this.props) {
        const axes = this.axes;
        if (!axes.length) {
            this.state.data = null;
            this.state.loading = false;
            return;
        }
        this.state.loading = true;
        try {
            this.state.data = await api.get(`${apiBase(props.collection)}/aggregate`, {
                groupBy: axes.map((a) => this.spec(a)).join(","),
                measures: this.state.measure || "count",
                draft: "true",
                where: props.where,
            });
        } catch (e) {
            this.state.data = null;
            toast.error(e.message);
        } finally {
            this.state.loading = false;
        }
    }

    value(row) {
        return row ? row[this.state.measure || "count"] : null;
    }

    label(axisIndex, key) {
        const path = this.axes[axisIndex];
        const spec = this.spec(path);
        return keyLabel(key, this.state.data?.labels?.[spec], this.kindOf(path), this.state.interval);
    }

    get measureLabel() {
        return this.measures.find((m) => m.value === (this.state.measure || "count"))?.label || "Count";
    }
}

export class PivotView extends AggregateView {
    static template = "payload.PivotView";
    static components = { Select };

    get viewName() {
        return "pivot";
    }

    defaults(groups) {
        const first = groups.find((g) => g.kind !== "date") || groups[0];
        const second = groups.find((g) => g.kind === "status" && g !== first) || null;
        return { rows: first?.value || "", cols: second?.value || "", measure: "count", interval: "month" };
    }

    get axes() {
        return [this.state.rows, this.state.cols].filter(Boolean);
    }

    get table() {
        const data = this.state.data;
        if (!data) {
            return null;
        }
        const twoAxes = Boolean(this.state.cols) && Boolean(this.state.rows);
        const measure = this.state.measure || "count";
        const isAvg = measure.startsWith("avg:") || measure.startsWith("min:") || measure.startsWith("max:");
        const rowKeys = [];
        const colKeys = [];
        const cells = new Map();
        for (const row of data.rows) {
            const r = String(row.keys[0]);
            const c = twoAxes ? String(row.keys[1]) : "__total__";
            if (!rowKeys.some((k) => k.key === r)) {
                rowKeys.push({ key: r, raw: row.keys[0], label: this.label(0, row.keys[0]) });
            }
            if (twoAxes && !colKeys.some((k) => k.key === c)) {
                colKeys.push({ key: c, raw: row.keys[1], label: this.label(1, row.keys[1]) });
            }
            cells.set(`${r}|${c}`, row);
        }
        const combine = (rows) => {
            const values = rows.map((r) => r && r[measure]).filter((v) => v !== null && v !== undefined);
            if (!values.length) {
                return null;
            }
            if (measure === "count" || measure.startsWith("sum:")) {
                return values.reduce((a, b) => a + b, 0);
            }
            if (measure.startsWith("max:")) {
                return Math.max(...values);
            }
            if (measure.startsWith("min:")) {
                return Math.min(...values);
            }
            // average of averages weighted by count
            const weighted = rows.filter((r) => r && r[measure] !== null);
            const count = weighted.reduce((a, r) => a + r.count, 0);
            return count ? weighted.reduce((a, r) => a + r[measure] * r.count, 0) / count : null;
        };
        const cols = twoAxes ? colKeys : [];
        const body = rowKeys.map((r) => {
            const rowCells = cols.map((c) => cells.get(`${r.key}|${c.key}`));
            const all = twoAxes ? rowCells : [cells.get(`${r.key}|__total__`)];
            return { ...r, cells: rowCells.map((cell) => formatNumber(cell ? cell[measure] : null)), total: formatNumber(combine(all)) };
        });
        const footer = cols.map((c) => formatNumber(combine(rowKeys.map((r) => cells.get(`${r.key}|${c.key}`)))));
        const grand = formatNumber(combine(data.rows));
        return { cols, body, footer, grand, isAvg };
    }

    swap() {
        const { rows, cols } = this.state;
        if (!cols) {
            return;
        }
        this.state.rows = cols;
        this.state.cols = rows;
        saveSettings(this.collection, "pivot", this.settingsToSave);
        this.load();
    }

    download() {
        const table = this.table;
        if (!table) {
            return;
        }
        const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
        const head = [this.groupOptions.find((g) => g.value === this.state.rows)?.label || "", ...table.cols.map((c) => c.label), "Total"];
        const lines = [head.map(esc).join(",")];
        for (const row of table.body) {
            lines.push([row.label, ...row.cells, row.total].map(esc).join(","));
        }
        lines.push(["Total", ...table.footer, table.grand].map(esc).join(","));
        const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `${this.collection.slug}-pivot.csv`;
        link.dataset.external = "1";
        document.body.appendChild(link);
        link.click();
        link.remove();
    }
}

// ----------------------------------------------------------------------
// Graph (SVG, no chart library)
// ----------------------------------------------------------------------
function esc(text) {
    return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function niceMax(value) {
    if (value <= 0) {
        return 1;
    }
    const power = 10 ** Math.floor(Math.log10(value));
    const unit = [1, 2, 2.5, 5, 10].find((u) => u * power >= value) * power;
    return unit;
}

export class GraphView extends AggregateView {
    static template = "payload.GraphView";
    static components = { Select };

    get viewName() {
        return "graph";
    }

    defaults(groups) {
        const dates = groups.find((g) => g.value === "createdAt");
        return { type: "bar", x: dates?.value || groups[0]?.value || "", stack: "", measure: "count", interval: "month" };
    }

    get axes() {
        return [this.state.x, this.state.type === "pie" ? "" : this.state.stack].filter(Boolean);
    }

    get types() {
        return [
            { key: "bar", label: "Bar", icon: "view-graph" },
            { key: "line", label: "Line", icon: "view-list" },
            { key: "pie", label: "Pie", icon: "view-pivot" },
        ];
    }

    setType(type) {
        this.set("type", type);
    }

    /** {categories, series: [{key, label, color, values}]} */
    get dataset() {
        const data = this.state.data;
        if (!data) {
            return null;
        }
        const measure = this.state.measure || "count";
        const categories = [];
        const series = new Map();
        const stacked = this.axes.length > 1;
        for (const row of data.rows) {
            const cat = String(row.keys[0]);
            if (!categories.some((c) => c.key === cat)) {
                categories.push({ key: cat, label: this.label(0, row.keys[0]) });
            }
            const sKey = stacked ? String(row.keys[1]) : "__value__";
            if (!series.has(sKey)) {
                series.set(sKey, { key: sKey, label: stacked ? this.label(1, row.keys[1]) : this.measureLabel, values: {} });
            }
            series.get(sKey).values[cat] = (series.get(sKey).values[cat] || 0) + (row[measure] || 0);
        }
        const list = [...series.values()].map((s, i) => ({ ...s, color: PALETTE[i % PALETTE.length] }));
        return { categories, series: list };
    }

    get legend() {
        const data = this.dataset;
        if (!data) {
            return [];
        }
        if (this.state.type === "pie") {
            return data.categories.map((c, i) => ({ label: c.label, color: PALETTE[i % PALETTE.length] }));
        }
        return data.series.length > 1 ? data.series.map((s) => ({ label: s.label, color: s.color })) : [];
    }

    get svg() {
        const data = this.dataset;
        if (!data || !data.categories.length) {
            return null;
        }
        const type = this.state.type;
        return markup(type === "pie" ? this.pie(data) : this.cartesian(data, type));
    }

    cartesian(data, type) {
        const W = 960;
        const H = 380;
        const m = { top: 16, right: 16, bottom: 64, left: 56 };
        const iw = W - m.left - m.right;
        const ih = H - m.top - m.bottom;
        const cats = data.categories;
        const totals = cats.map((c) => data.series.reduce((a, s) => a + (s.values[c.key] || 0), 0));
        const max = niceMax(type === "bar" ? Math.max(...totals, 0) : Math.max(...data.series.flatMap((s) => cats.map((c) => s.values[c.key] || 0)), 0));
        const y = (v) => m.top + ih - (v / max) * ih;
        const band = iw / cats.length;
        const parts = [`<svg class="graph-view__svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img">`];
        for (let i = 0; i <= 4; i++) {
            const v = (max / 4) * i;
            parts.push(`<line class="graph-view__grid" x1="${m.left}" x2="${W - m.right}" y1="${y(v)}" y2="${y(v)}"/>`);
            parts.push(`<text class="graph-view__tick" x="${m.left - 8}" y="${y(v) + 4}" text-anchor="end">${esc(formatNumber(v))}</text>`);
        }
        const labelEvery = Math.max(1, Math.ceil(cats.length / 16));
        cats.forEach((c, i) => {
            if (i % labelEvery === 0) {
                const cx = m.left + band * i + band / 2;
                const text = c.label.length > 16 ? `${c.label.slice(0, 15)}…` : c.label;
                parts.push(`<text class="graph-view__tick" x="${cx}" y="${H - m.bottom + 18}" text-anchor="middle">${esc(text)}<title>${esc(c.label)}</title></text>`);
            }
        });
        if (type === "bar") {
            const bw = Math.max(4, Math.min(56, band * 0.62));
            cats.forEach((c, i) => {
                let acc = 0;
                const x = m.left + band * i + (band - bw) / 2;
                for (const s of data.series) {
                    const v = s.values[c.key] || 0;
                    if (!v) {
                        continue;
                    }
                    const top = y(acc + v);
                    const h = y(acc) - top;
                    parts.push(`<rect class="graph-view__bar" x="${x}" y="${top}" width="${bw}" height="${Math.max(0, h)}" rx="2" fill="${s.color}"><title>${esc(c.label)} — ${esc(s.label)}: ${esc(formatNumber(v))}</title></rect>`);
                    acc += v;
                }
            });
        } else {
            for (const s of data.series) {
                const points = cats.map((c, i) => [m.left + band * i + band / 2, y(s.values[c.key] || 0)]);
                parts.push(`<polyline class="graph-view__line" fill="none" stroke="${s.color}" points="${points.map((p) => p.join(",")).join(" ")}"/>`);
                points.forEach(([px, py], i) => {
                    parts.push(`<circle class="graph-view__dot" cx="${px}" cy="${py}" r="4" fill="${s.color}"><title>${esc(cats[i].label)} — ${esc(s.label)}: ${esc(formatNumber(s.values[cats[i].key] || 0))}</title></circle>`);
                });
            }
        }
        parts.push(`<line class="graph-view__axis" x1="${m.left}" x2="${W - m.right}" y1="${y(0)}" y2="${y(0)}"/>`);
        parts.push("</svg>");
        return parts.join("");
    }

    pie(data) {
        const W = 960;
        const H = 380;
        const cx = W / 2;
        const cy = H / 2;
        const r = 150;
        const values = data.categories.map((c) => data.series.reduce((a, s) => a + (s.values[c.key] || 0), 0));
        const total = values.reduce((a, b) => a + b, 0) || 1;
        const parts = [`<svg class="graph-view__svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img">`];
        let angle = -Math.PI / 2;
        data.categories.forEach((c, i) => {
            const share = values[i] / total;
            const next = angle + share * Math.PI * 2;
            const color = PALETTE[i % PALETTE.length];
            const title = `<title>${esc(c.label)}: ${esc(formatNumber(values[i]))} (${Math.round(share * 100)}%)</title>`;
            if (share >= 0.9999) {
                parts.push(`<circle cx="${cx}" cy="${cy}" r="${r}" fill="${color}">${title}</circle>`);
            } else if (share > 0) {
                const large = share > 0.5 ? 1 : 0;
                const [x1, y1] = [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
                const [x2, y2] = [cx + r * Math.cos(next), cy + r * Math.sin(next)];
                parts.push(`<path class="graph-view__slice" d="M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} Z" fill="${color}">${title}</path>`);
            }
            angle = next;
        });
        parts.push(`<circle cx="${cx}" cy="${cy}" r="${r * 0.55}" fill="var(--theme-elevation-0)"/>`);
        parts.push(`<text class="graph-view__total" x="${cx}" y="${cy - 2}" text-anchor="middle">${esc(formatNumber(values.reduce((a, b) => a + b, 0)))}</text>`);
        parts.push(`<text class="graph-view__tick" x="${cx}" y="${cy + 20}" text-anchor="middle">${esc(this.measureLabel)}</text>`);
        parts.push("</svg>");
        return parts.join("");
    }
}

// ----------------------------------------------------------------------
// Calendar
// ----------------------------------------------------------------------
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function isoDay(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export class CalendarView extends Component {
    static template = "payload.CalendarView";
    static components = { Select };

    setup() {
        this.icon = icon;
        const fields = this.dateFields;
        const settings = loadSettings(this.props.collection, "calendar", { dateField: fields.find((f) => !["createdAt", "updatedAt"].includes(f.value))?.value || "createdAt" });
        if (!fields.some((f) => f.value === settings.dateField)) {
            settings.dateField = "createdAt";
        }
        const now = new Date();
        this.state = useState({ ...settings, year: now.getFullYear(), month: now.getMonth(), docs: [], loading: true, dragging: null, over: null });
        onWillStart(() => this.load());
    }

    get collection() {
        return this.props.collection;
    }

    get dateFields() {
        return groupableFields(this.collection).filter((g) => g.kind === "date").map(({ value, label }) => ({ value, label }));
    }

    get editable() {
        return !["createdAt", "updatedAt"].includes(this.state.dateField);
    }

    get monthLabel() {
        return new Date(this.state.year, this.state.month, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
    }

    get weekdays() {
        return WEEKDAYS;
    }

    /** 6 weeks starting on Monday. */
    get range() {
        const first = new Date(this.state.year, this.state.month, 1);
        const start = new Date(first);
        start.setDate(1 - ((first.getDay() + 6) % 7));
        const end = new Date(start);
        end.setDate(start.getDate() + 42);
        return { start, end };
    }

    async load(props = this.props) {
        this.state.loading = true;
        const { start, end } = this.range;
        const field = this.state.dateField;
        try {
            const res = await api.get(apiBase(props.collection), {
                depth: 0, draft: "true", _admin: "1", limit: 500, sort: field,
                where: andWhere(props.where, { [field]: { greater_than_equal: start.toISOString() } }, { [field]: { less_than: end.toISOString() } }),
            });
            this.state.docs = res.docs;
        } catch (e) {
            toast.error(e.message);
        } finally {
            this.state.loading = false;
        }
    }

    get weeks() {
        const { start } = this.range;
        const today = isoDay(new Date());
        const byDay = {};
        for (const doc of this.state.docs) {
            const value = getPath(doc, this.state.dateField);
            if (!value) {
                continue;
            }
            const key = isoDay(new Date(value));
            (byDay[key] ||= []).push(doc);
        }
        const weeks = [];
        for (let w = 0; w < 6; w++) {
            const days = [];
            for (let d = 0; d < 7; d++) {
                const date = new Date(start);
                date.setDate(start.getDate() + w * 7 + d);
                const key = isoDay(date);
                const docs = byDay[key] || [];
                days.push({
                    key,
                    date,
                    number: date.getDate(),
                    outside: date.getMonth() !== this.state.month,
                    today: key === today,
                    docs: docs.slice(0, 4),
                    more: Math.max(0, docs.length - 4),
                });
            }
            weeks.push(days);
        }
        return weeks;
    }

    move(delta) {
        const date = new Date(this.state.year, this.state.month + delta, 1);
        this.state.year = date.getFullYear();
        this.state.month = date.getMonth();
        this.load();
    }

    today() {
        const now = new Date();
        this.state.year = now.getFullYear();
        this.state.month = now.getMonth();
        this.load();
    }

    setField(value) {
        this.state.dateField = value;
        saveSettings(this.collection, "calendar", { dateField: value });
        this.load();
    }

    title(doc) {
        return docTitle(this.collection, doc) || `#${doc.id}`;
    }

    href(doc) {
        return `${adminBase(this.collection)}/${doc.id}`;
    }

    statusClass(doc) {
        return doc._status === "draft" ? " calendar-view__event--draft" : "";
    }

    onDragStart(ev, doc) {
        if (!this.editable) {
            ev.preventDefault();
            return;
        }
        this.state.dragging = doc.id;
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", String(doc.id));
    }

    async onDrop(day) {
        const id = this.state.dragging;
        this.state.dragging = null;
        this.state.over = null;
        const doc = this.state.docs.find((d) => d.id === id);
        if (!doc || !this.editable) {
            return;
        }
        const field = this.state.dateField;
        const old = getPath(doc, field);
        const previous = old ? new Date(old) : new Date(day.date);
        const target = new Date(day.date);
        target.setHours(previous.getHours(), previous.getMinutes(), previous.getSeconds());
        const keys = field.split(".");
        const body = {};
        let obj = body;
        keys.slice(0, -1).forEach((k, i) => {
            obj[k] = { ...(getPath(doc, keys.slice(0, i + 1).join(".")) || {}) };
            obj = obj[k];
        });
        obj[keys[keys.length - 1]] = target.toISOString();
        try {
            const res = await request(`${apiBase(this.collection)}/${doc.id}`, { method: "PATCH", body, params: { depth: 0, _admin: "1" } });
            Object.assign(doc, res.doc);
            toast.success(`${this.title(doc)} → ${target.toLocaleDateString()}`);
        } catch (e) {
            toast.error(e.message);
        }
    }
}
