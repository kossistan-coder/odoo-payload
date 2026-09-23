/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { api, request } from "../core/api";
import { t } from "../core/i18n";
import { ensureDocs, relationCache, relationLabel, searchDocs } from "../core/relations";
import { navigate, setQuery } from "../core/router";
import { defaultActiveColumns, listColumns, operatorsFor } from "../core/schema";
import { adminBase, apiBase, confirmModal, getCollection, openDrawer, refreshTenants, setStepNav, toast } from "../core/store";
import { ExportDrawer, ImportDrawer } from "./import_export";
import { CalendarView, GraphView, KanbanView, PivotView, VIEW_MODES, ViewSwitcher } from "./list_views";
import { debounce, docTitle, formatDate, formatFilesize, icon, lexicalToText, rowLabels } from "../core/utils";
import { AnimateHeight, Button, CheckboxInput, Pill, Popup, PopupButton, Select, Thumbnail } from "../components/base";

const PER_PAGE = [5, 10, 25, 50, 100];

/** One table cell rendered like Payload's DefaultCell. */
export class Cell extends Component {
    static template = "payload.Cell";
    static components = { Thumbnail };

    setup() {
        this.icon = icon;
        this.t = t;
    }

    get field() {
        return this.props.column.field;
    }

    get value() {
        return this.props.doc[this.props.column.accessor];
    }

    get isEmpty() {
        const v = this.value;
        return v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length && !["array", "blocks"].includes(this.field.type));
    }

    get noLabel() {
        return t("general:noLabel", { label: this.props.column.label });
    }

    get selectInfo() {
        const values = Array.isArray(this.value) ? this.value : [this.value];
        const options = this.field.options || [];
        let labels = values.map((v) => options.find((o) => o.value === v)?.label || v);
        let classes = values.map((v) => `selected--${v}`);
        if (this.props.column.accessor === "_status" && this.value === "draft" && this.props.doc._hasPublishedVersion) {
            labels = [t("version:draftHasPublishedVersion")];
            classes = ["selected--changed"];
        }
        return { label: labels.join(", "), className: classes.join(" ") };
    }

    get relationText() {
        const values = (Array.isArray(this.value) ? this.value : [this.value]).filter((v) => v !== null && v !== undefined);
        const ids = values.map((v) => (typeof v === "object" ? v.id : v));
        const items = ids.slice(0, 3).map((id) => relationLabel(this.field.relationTo, id));
        const text = items.join(", ");
        return ids.length > 3 ? t("fields:itemsAndMore", { items: text, count: ids.length - 3 }) : text;
    }

    get uploadDocs() {
        const values = (Array.isArray(this.value) ? this.value : [this.value]).filter((v) => v !== null && v !== undefined);
        return values.slice(0, 3).map((v) => this.props.relations?.[this.field.relationTo]?.[typeof v === "object" ? v.id : v]).filter(Boolean);
    }

    get arrayText() {
        const rows = Array.isArray(this.value) ? this.value : [];
        if (this.field.type === "blocks") {
            const labels = this.field.labels || { singular: "Block", plural: "Blocks" };
            if (!rows.length) {
                return `0 ${labels.plural}`;
            }
            const names = rows.map((r) => this.field.blocks?.find((b) => b.slug === r.blockType)?.labels?.singular || r.blockType);
            const shown = names.slice(0, 5).join(", ");
            const more = names.length > 5 ? ` and ${names.length - 5} more` : "";
            return `${rows.length} ${rows.length === 1 ? labels.singular : labels.plural} - ${shown}${more}`;
        }
        const labels = rowLabels(this.field);
        return `${rows.length} ${rows.length === 1 ? labels.singular : labels.plural}`;
    }

    get text() {
        const v = this.value;
        switch (this.field.type) {
            case "date":
                return formatDate(v);
            case "richText":
                return lexicalToText(v, 100);
            case "textarea":
            case "code":
                return String(v).length > 100 ? `${String(v).slice(0, 100)}…` : String(v);
            case "json":
                return JSON.stringify(v).slice(0, 100);
            case "filesize":
                return formatFilesize(v);
            default:
                return typeof v === "object" ? JSON.stringify(v) : String(v);
        }
    }

    get thumbnailSrc() {
        const doc = this.props.doc;
        return doc.thumbnailURL || (doc.mimeType?.startsWith("image/") ? doc.url : null);
    }

    onClick(ev) {
        if (this.props.onSelect) {
            ev.preventDefault();
            this.props.onSelect(this.props.doc);
        }
    }
}

/** Value input of a where-builder condition. */
export class ConditionValue extends Component {
    static template = "payload.ConditionValue";
    static components = { Select };

    setup() {
        this.state = useState({ options: [], loading: false });
        this.t = t;
        this.onSearch = debounce((q) => this.loadRelations(q), 250);
    }

    get field() {
        return this.props.field;
    }

    get isMulti() {
        return ["in", "not_in"].includes(this.props.operator);
    }

    get kind() {
        const type = this.field?.type;
        if (this.props.operator === "exists") {
            return "exists";
        }
        if (type === "select" || type === "radio") {
            return "select";
        }
        if (type === "relationship" || type === "upload") {
            return "relationship";
        }
        if (type === "number" || type === "id" || type === "filesize") {
            return "number";
        }
        if (type === "date") {
            return "date";
        }
        if (type === "checkbox") {
            return "checkbox";
        }
        return "text";
    }

    get multiValue() {
        const v = this.props.value;
        if (Array.isArray(v)) {
            return v;
        }
        return v ? String(v).split(",").filter(Boolean) : [];
    }

    get numericValues() {
        return this.multiValue.map((v) => Number(v));
    }

    get numericValue() {
        return this.props.value ? Number(this.props.value) : null;
    }

    async loadRelations(q = "") {
        this.state.loading = true;
        try {
            const res = await searchDocs(this.field.relationTo, q);
            this.state.options = res.options;
        } finally {
            this.state.loading = false;
        }
    }

    relationLabel(id) {
        return relationLabel(this.field.relationTo, id);
    }

    setValue(v) {
        this.props.onChange(Array.isArray(v) ? v.join(",") : v);
    }
}

export class WhereBuilder extends Component {
    static template = "payload.WhereBuilder";
    static components = { Button, Select, ConditionValue };

    setup() {
        this.t = t;
        this.icon = icon;
        this.emit = debounce(() => this.props.onChange(this.props.conditions), 300);
    }

    get fieldOptions() {
        return this.props.columns
            .filter((c) => operatorsFor(c.field.type).length)
            .map((c) => ({ value: c.accessor, label: c.label }));
    }

    column(accessor) {
        return this.props.columns.find((c) => c.accessor === accessor);
    }

    andsOf(group) {
        return group.and || [];
    }

    operatorOptions(accessor) {
        const col = this.column(accessor);
        return operatorsFor(col?.field.type).map((o) => ({ value: o.value, label: t(o.key) }));
    }

    newCondition() {
        const first = this.fieldOptions[0];
        return { field: first?.value, operator: this.operatorOptions(first?.value)[0]?.value || "equals", value: "" };
    }

    addFirst() {
        this.props.conditions.push({ and: [this.newCondition()] });
        this.props.onChange(this.props.conditions);
    }

    addOr() {
        this.props.conditions.push({ and: [this.newCondition()] });
        this.props.onChange(this.props.conditions);
    }

    addAnd(orIndex, andIndex) {
        this.props.conditions[orIndex].and.splice(andIndex + 1, 0, this.newCondition());
        this.props.onChange(this.props.conditions);
    }

    remove(orIndex, andIndex) {
        const group = this.props.conditions[orIndex];
        group.and.splice(andIndex, 1);
        if (!group.and.length) {
            this.props.conditions.splice(orIndex, 1);
        }
        this.props.onChange(this.props.conditions);
    }

    setField(cond, value) {
        cond.field = value;
        cond.operator = this.operatorOptions(value)[0]?.value || "equals";
        cond.value = "";
        this.props.onChange(this.props.conditions);
    }

    setOperator(cond, value) {
        cond.operator = value;
        if (value === "exists" || cond.value === "true" || cond.value === "false") {
            cond.value = "";
        }
        this.props.onChange(this.props.conditions);
    }

    setValue(cond, value) {
        cond.value = value;
        this.emit();
    }
}

export class ColumnSelector extends Component {
    static template = "payload.ColumnSelector";
    static components = { Pill };

    setup() {
        this.icon = icon;
    }

    onDragOver() {}
}

/**
 * Payload's list view. Also used in "drawer" mode (ListDrawer) to choose
 * existing documents (upload / relationship fields).
 */
export class ListView extends Component {
    static template = "payload.ListView";
    static components = { Button, Pill, Popup, PopupButton, CheckboxInput, AnimateHeight, WhereBuilder, ColumnSelector, Cell, Select, ViewSwitcher };

    setup() {
        this.t = t;
        this.icon = icon;
        this.state = useState({
            docs: [],
            meta: null,
            loading: true,
            search: "",
            drawer: null,
            selected: [],
            selectAllAvailable: false,
            columns: [],
            conditions: [],
            relations: {},
            query: {},
            activeSlug: null,
        });
        this.searchChanged = debounce(() => this.applyQuery({ search: this.state.search, page: 1 }), 300);
        onWillStart(() => this.init(this.props));
        onWillUpdateProps((next) => {
            if (!this.isDrawer && next.route?.path !== this.props.route?.path) {
                return this.init(next, false);
            }
        });
    }

    get isDrawer() {
        return Boolean(this.props.collectionSlug);
    }

    get slug() {
        return this.state.activeSlug || this.props.collectionSlug || this.props.route.params.slug;
    }

    get collectionOptions() {
        return (this.props.collectionSlugs || []).map((slug) => ({ value: slug, label: getCollection(slug)?.labels.plural || slug }));
    }

    switchCollection(slug) {
        this.state.activeSlug = slug;
        this.state.conditions = [];
        this.state.query = {};
        this.init(this.props, true);
    }

    get collection() {
        return getCollection(this.slug);
    }

    get allColumns() {
        return listColumns(this.collection);
    }

    get activeColumns() {
        return this.state.columns.filter((c) => c.active).map((c) => this.allColumns.find((col) => col.accessor === c.accessor)).filter(Boolean);
    }

    get searchPlaceholder() {
        const c = this.collection;
        const fields = c.admin?.listSearchableFields?.length ? c.admin.listSearchableFields : [c.admin?.useAsTitle || "id"];
        const labels = fields.map((name) => this.allColumns.find((col) => col.accessor === name)?.label || (name === "id" ? "ID" : name));
        let text = t("general:searchBy", { label: labels[0] });
        labels.slice(1).forEach((label, i) => {
            text += i === labels.length - 2 ? ` ${t("general:or").toLowerCase()} ${label}` : `, ${label}`;
        });
        return text;
    }

    columnsKey() {
        return `payload-columns-${this.slug}`;
    }

    async init(props, first = true) {
        const collection = getCollection(this.slug);
        if (!collection) {
            this.state.loading = false;
            return;
        }
        if (first) {
            let saved = null;
            try {
                saved = JSON.parse(localStorage.getItem(this.columnsKey()) || "null");
            } catch {
                saved = null;
            }
            const all = listColumns(collection).map((c) => c.accessor);
            const active = defaultActiveColumns(collection);
            if (saved && Array.isArray(saved)) {
                const known = saved.filter((c) => all.includes(c.accessor));
                const missing = all.filter((a) => !known.some((c) => c.accessor === a)).map((a) => ({ accessor: a, active: false }));
                this.state.columns = [...known, ...missing];
            } else {
                this.state.columns = [
                    ...active.map((a) => ({ accessor: a, active: true })),
                    ...all.filter((a) => !active.includes(a)).map((a) => ({ accessor: a, active: false })),
                ];
            }
        }
        const query = this.isDrawer ? this.state.query : { ...props.route.query };
        this.state.query = query;
        this.state.search = query.search || "";
        try {
            this.state.conditions = query.where ? JSON.parse(query.where).or || [] : this.state.conditions;
        } catch {
            this.state.conditions = [];
        }
        if (first && this.state.conditions.length) {
            this.state.drawer = "where";
        }
        if (!this.isDrawer) {
            setStepNav([{ label: collection.labels.plural }]);
            document.title = `${collection.labels.plural} - Payload`;
        }
        await this.fetch();
    }

    buildWhere() {
        const c = this.collection;
        const clauses = [];
        const search = (this.state.query.search || "").trim();
        if (search) {
            const fields = c.admin?.listSearchableFields?.length ? c.admin.listSearchableFields : [c.admin?.useAsTitle || "id"];
            const ors = fields.map((f) => (f === "id" ? { id: { equals: search } } : { [f]: { like: search } }));
            clauses.push(ors.length === 1 ? ors[0] : { or: ors });
        }
        const ors = [];
        for (const group of this.state.conditions) {
            const ands = [];
            for (const cond of group.and || []) {
                if (!cond.field || !cond.operator) {
                    continue;
                }
                if (cond.value === "" && cond.operator !== "exists") {
                    continue;
                }
                let value = cond.value;
                if (cond.operator === "exists" && value === "") {
                    continue;
                }
                ands.push({ [cond.field]: { [cond.operator]: value } });
            }
            if (ands.length) {
                ors.push({ and: ands });
            }
        }
        if (ors.length) {
            clauses.push({ or: ors });
        }
        if (this.props.baseWhere) {
            clauses.push(this.props.baseWhere);
        }
        if (!clauses.length) {
            return undefined;
        }
        return clauses.length === 1 ? clauses[0] : { and: clauses };
    }

    async fetch() {
        const c = this.collection;
        const q = this.state.query;
        this.state.loading = true;
        try {
            const res = await api.get(apiBase(c), {
                depth: 0,
                draft: "true",
                _admin: "1",
                limit: q.limit || c.defaultLimit || 10,
                page: q.page || 1,
                sort: q.sort || c.defaultSort,
                where: this.buildWhere(),
            });
            this.state.docs = res.docs;
            const { docs, ...meta } = res;
            this.state.meta = meta;
            this.state.selected = [];
            this.state.selectAllAvailable = false;
            await this.loadRelations(res.docs);
        } catch (e) {
            toast.error(e.message);
        } finally {
            this.state.loading = false;
        }
    }

    async loadRelations(docs) {
        const byCollection = {};
        for (const col of this.activeColumns) {
            const f = col.field;
            if (f.type !== "relationship" && f.type !== "upload") {
                continue;
            }
            for (const doc of docs) {
                const v = doc[col.accessor];
                const values = (Array.isArray(v) ? v : [v]).filter((x) => x !== null && x !== undefined);
                byCollection[f.relationTo] = [...(byCollection[f.relationTo] || []), ...values.map((x) => (typeof x === "object" ? x.id : x))];
            }
        }
        await Promise.all(
            Object.entries(byCollection).map(async ([slug, ids]) => {
                await ensureDocs(slug, ids);
                this.state.relations[slug] = relationCache[slug];
            })
        );
    }

    applyQuery(patch) {
        const query = { ...this.state.query, ...patch };
        for (const key of Object.keys(query)) {
            if (query[key] === "" || query[key] === undefined || query[key] === null) {
                delete query[key];
            }
        }
        if (this.isDrawer) {
            this.state.query = query;
            this.fetch();
        } else {
            setQuery(query);
        }
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
        this.searchChanged();
    }

    toggleDrawer(name) {
        this.state.drawer = this.state.drawer === name ? null : name;
    }

    onConditionsChange(conditions) {
        this.state.conditions = conditions;
        const valid = conditions.filter((g) => g.and?.length);
        this.applyQuery({ where: valid.length ? JSON.stringify({ or: valid }) : "", page: 1 });
    }

    toggleColumn(accessor) {
        const col = this.state.columns.find((c) => c.accessor === accessor);
        col.active = !col.active;
        localStorage.setItem(this.columnsKey(), JSON.stringify(this.state.columns));
        this.loadRelations(this.state.docs);
    }

    moveColumn(from, to) {
        const [item] = this.state.columns.splice(from, 1);
        this.state.columns.splice(to, 0, item);
        localStorage.setItem(this.columnsKey(), JSON.stringify(this.state.columns));
    }

    isSortable(col) {
        return !["array", "blocks", "group", "richText", "json", "upload-file"].includes(col.field.type) || col.accessor === "filename";
    }

    sort(accessor, desc) {
        this.applyQuery({ sort: desc ? `-${accessor}` : accessor });
    }

    docHref(doc) {
        if (this.collection.hrefFor) {
            return this.collection.hrefFor(doc);
        }
        return `${adminBase(this.collection)}/${encodeURIComponent(doc.id)}`;
    }

    // --- selection --------------------------------------------------
    get createURL() {
        return `${adminBase(this.collection)}/create`;
    }

    get canSelect() {
        return !this.collection.noSelect && (!this.isDrawer || this.props.allowMultiple);
    }

    get allSelected() {
        return this.state.docs.length > 0 && this.state.selected.length === this.state.docs.length;
    }

    toggleAll() {
        this.state.selectAllAvailable = false;
        this.state.selected = this.allSelected ? [] : this.state.docs.map((d) => d.id);
    }

    toggleRow(id) {
        this.state.selectAllAvailable = false;
        const index = this.state.selected.indexOf(id);
        if (index >= 0) {
            this.state.selected.splice(index, 1);
        } else {
            this.state.selected.push(id);
        }
    }

    // ------------------------------------------------------------------
    // Views: list, kanban, pivot, graph, calendar
    // ------------------------------------------------------------------
    get viewMode() {
        if (this.isDrawer || this.collection.virtual) {
            return "list";
        }
        const mode = this.state.query.view || this.storedView;
        return VIEW_MODES.some((m) => m.key === mode) ? mode : "list";
    }

    get storedView() {
        try {
            return localStorage.getItem(`payload-view-${this.collection.slug}`) || "list";
        } catch {
            return "list";
        }
    }

    setViewMode(mode) {
        try {
            localStorage.setItem(`payload-view-${this.collection.slug}`, mode);
        } catch {
            // storage unavailable
        }
        this.state.drawer = this.state.drawer === "columns" ? null : this.state.drawer;
        this.applyQuery({ view: mode === "list" ? "" : mode, page: 1 });
    }

    get showViewSwitcher() {
        return !this.isDrawer && !this.collection.virtual;
    }

    get viewComponent() {
        return { kanban: KanbanView, pivot: PivotView, graph: GraphView, calendar: CalendarView }[this.viewMode];
    }

    /** The alternative views are re-created when the search / filters change. */
    get viewKey() {
        return `${this.viewMode}:${JSON.stringify(this.buildWhere() || {})}`;
    }

    // ------------------------------------------------------------------
    // Import / export (CSV, Excel, JSON)
    // ------------------------------------------------------------------
    get canImportExport() {
        return !this.isDrawer && !this.collection.virtual && !this.collection.isUsers;
    }

    openExport(selection = false) {
        const ids = selection && !this.state.selectAllAvailable ? [...this.state.selected] : [];
        const where = selection && this.state.selectAllAvailable ? this.selectionWhere() : this.buildWhere();
        openDrawer(ExportDrawer, { collection: this.collection, where: where || null, selectedIds: ids, sort: this.state.sort || this.route?.query?.sort || "" },
            { title: `Export ${this.collection.labels.plural}` });
    }

    async openImport() {
        let imported = false;
        await openDrawer(ImportDrawer, { collection: this.collection, onImported: () => (imported = true) },
            { title: `Import ${this.collection.labels.plural}` });
        if (imported) {
            await this.fetch();
        }
    }

    get selectedCount() {
        return this.state.selectAllAvailable ? this.state.meta.totalDocs : this.state.selected.length;
    }

    selectionWhere() {
        if (this.state.selectAllAvailable) {
            return this.buildWhere() || { id: { exists: true } };
        }
        return { id: { in: this.state.selected.join(",") } };
    }

    async bulkDelete() {
        const count = this.selectedCount;
        const label = count === 1 ? this.collection.labels.singular : this.collection.labels.plural;
        const ok = await confirmModal({
            heading: t("general:confirmDeletion"),
            body: t("general:aboutToDeleteCount", { count, label }),
            confirmingLabel: t("general:deleting"),
            onConfirm: async () => {
                try {
                    const res = await api.delete(apiBase(this.collection), { where: this.selectionWhere() });
                    toast.success(res.message || t("general:deletedCountSuccessfully", { count, label }));
                    if (this.collection?.slug === "tenants") {
                        refreshTenants();
                    }
                } catch (e) {
                    toast.error(e.message);
                }
            },
        });
        if (ok) {
            this.fetch();
        }
    }

    async bulkStatus(status) {
        const count = this.selectedCount;
        const label = count === 1 ? this.collection.labels.singular : this.collection.labels.plural;
        const ok = await confirmModal({
            heading: status === "published" ? t("version:confirmPublish") : t("version:confirmUnpublish"),
            body: status === "published" ? t("version:aboutToPublishSelection", { label }) : t("version:aboutToUnpublishSelection", { label }),
            confirmingLabel: status === "published" ? t("version:publishing") : t("version:unpublishing"),
            onConfirm: async () => {
                try {
                    const res = await request(apiBase(this.collection), {
                        method: "PATCH",
                        body: { _status: status },
                        params: { where: this.selectionWhere() },
                    });
                    toast.success(res.message);
                } catch (e) {
                    toast.error(e.message);
                }
            },
        });
        if (ok) {
            this.fetch();
        }
    }

    // --- pagination --------------------------------------------------
    get pages() {
        const meta = this.state.meta;
        if (!meta) {
            return [];
        }
        const pages = [];
        for (let n = Math.max(1, meta.page - 1); n <= Math.min(meta.totalPages, meta.page + 1); n++) {
            pages.push(n);
        }
        return pages;
    }

    get pageInfo() {
        const { page, limit, totalPages, totalDocs } = this.state.meta;
        const from = page * limit - (limit - 1);
        const to = totalPages > 1 && totalPages !== page ? limit * page : totalDocs;
        return `${from}-${to} ${t("general:of")} ${totalDocs}`;
    }

    get perPageOptions() {
        return PER_PAGE;
    }

    goPage(n) {
        this.applyQuery({ page: n });
    }

    setLimit(n) {
        this.applyQuery({ limit: n, page: 1 });
    }

    createNew() {
        if (this.isDrawer) {
            this.props.close?.();
            this.props.onCreate?.();
        } else {
            navigate(`${adminBase(this.collection)}/create`);
        }
    }

    selectDoc(doc) {
        const result = { ...doc, __collection: this.slug };
        if (this.props.onSelect) {
            this.props.onSelect(result);
        } else {
            this.props.close?.(result);
        }
    }

    title(doc) {
        return docTitle(this.collection, doc);
    }
}

// the kanban cards render their fields with the list cells
KanbanView.components = { ...KanbanView.components, Cell };
