/** @odoo-module **/

import { Component, useRef, useState } from "@odoo/owl";
import { api, ApiError, stringifyQuery } from "../core/api";
import { dataFields } from "../core/schema";
import { apiBase, currentLocale, multitenancy, store, toast } from "../core/store";
import { icon } from "../core/utils";
import { Button, CheckboxInput, Select } from "../components/base";

/** Spreadsheet columns of a collection: data paths, groups flattened with dots. */
export function exportColumns(fields, prefix = "", labelPrefix = "") {
    const result = [];
    for (const field of dataFields(fields || [])) {
        const path = prefix ? `${prefix}.${field.name}` : field.name;
        const label = typeof field.label === "string" && field.label ? field.label : field.name;
        const full = labelPrefix ? `${labelPrefix} › ${label}` : label;
        if (field.type === "group") {
            result.push(...exportColumns(field.fields, path, full));
        } else if (!field.private) {
            result.push({ value: path, label: full, field });
        }
    }
    return result;
}

/** Site of the file operations (the API reads `?tenant=` when no header can be sent). */
function tenantParam() {
    return multitenancy() ? { tenant: store.tenant || "all" } : {};
}

/** Export drawer (CSV / Excel / JSON), like @payloadcms/plugin-import-export. */
export class ExportDrawer extends Component {
    static template = "payload.ExportDrawer";
    static components = { Button, CheckboxInput, Select };

    setup() {
        this.icon = icon;
        const hasSelection = (this.props.selectedIds || []).length > 0;
        this.state = useState({
            format: "xlsx",
            scope: hasSelection ? "selection" : this.props.where ? "filter" : "all",
            columns: [],
            headers: "labels",
            draft: true,
        });
    }

    get collection() {
        return this.props.collection;
    }

    get columnOptions() {
        return exportColumns(this.collection.fields).map(({ value, label }) => ({ value, label }));
    }

    get scopes() {
        const scopes = [{ value: "all", label: "All documents" }];
        if (this.props.where) {
            scopes.push({ value: "filter", label: "Current search / filters" });
        }
        if ((this.props.selectedIds || []).length) {
            scopes.push({ value: "selection", label: `Selection (${this.props.selectedIds.length})` });
        }
        return scopes;
    }

    get formats() {
        return [
            { value: "xlsx", label: "Excel (.xlsx)" },
            { value: "csv", label: "CSV" },
            { value: "json", label: "JSON" },
        ];
    }

    get localeLabel() {
        const locale = currentLocale();
        return locale ? locale.label || locale.code : "";
    }

    get url() {
        const s = this.state;
        const params = {
            format: s.format,
            draft: this.collection.versions?.drafts && s.draft ? "true" : undefined,
            sort: this.props.sort || undefined,
            fields: s.columns.length ? s.columns.join(",") : undefined,
            headers: s.format !== "json" && s.headers === "labels" ? "labels" : undefined,
            locale: store.locale || undefined,
            ...tenantParam(),
        };
        if (s.scope === "selection") {
            params.ids = this.props.selectedIds.join(",");
        } else if (s.scope === "filter" && this.props.where) {
            params.where = this.props.where;
        }
        return `/api${apiBase(this.collection)}/export?${stringifyQuery(params)}`;
    }

    download() {
        const link = document.createElement("a");
        link.href = this.url;
        link.setAttribute("download", "");
        link.dataset.external = "1";
        document.body.appendChild(link);
        link.click();
        link.remove();
        toast.success("The export is downloading.");
        this.props.close();
    }
}

/** Import drawer: CSV / Excel / JSON file, validation (dry run), then import. */
export class ImportDrawer extends Component {
    static template = "payload.ImportDrawer";
    static components = { Button, CheckboxInput, Select };

    setup() {
        this.icon = icon;
        this.fileInput = useRef("file");
        this.state = useState({
            file: null,
            dragging: false,
            mode: "create",
            matchField: "id",
            draft: false,
            processing: false,
            report: null,
            imported: false,
        });
    }

    get collection() {
        return this.props.collection;
    }

    get modes() {
        return [
            { value: "create", label: "Create new documents" },
            { value: "update", label: "Update existing documents" },
            { value: "upsert", label: "Update or create" },
        ];
    }

    get matchOptions() {
        const unique = exportColumns(this.collection.fields)
            .filter(({ field }) => field.unique || field.type === "slug" || ["text", "email"].includes(field.type))
            .map(({ value, label }) => ({ value, label }));
        return [{ value: "id", label: "ID" }, ...unique];
    }

    get localeLabel() {
        const locale = currentLocale();
        return locale ? locale.label || locale.code : "";
    }

    templateURL(format) {
        return `/api${apiBase(this.collection)}/import/template?${stringifyQuery({ format, ...tenantParam() })}`;
    }

    setMode(mode) {
        this.state.mode = mode;
        this.state.report = null;
    }

    pick() {
        this.fileInput.el?.click();
    }

    onFile(ev) {
        this.setFile(ev.target.files?.[0]);
    }

    onDrop(ev) {
        this.state.dragging = false;
        this.setFile(ev.dataTransfer?.files?.[0]);
    }

    setFile(file) {
        if (!file) {
            return;
        }
        if (!/\.(csv|xlsx|json)$/i.test(file.name)) {
            toast.error("Select a CSV, Excel (.xlsx) or JSON file.");
            return;
        }
        this.state.file = file;
        this.state.report = null;
        this.state.imported = false;
    }

    clearFile() {
        this.state.file = null;
        this.state.report = null;
        if (this.fileInput.el) {
            this.fileInput.el.value = "";
        }
    }

    async run(dryRun) {
        if (!this.state.file || this.state.processing) {
            return;
        }
        this.state.processing = true;
        try {
            const options = { mode: this.state.mode, matchField: this.state.matchField, draft: this.state.draft, dryRun };
            const report = await api.upload(`${apiBase(this.collection)}/import`, this.state.file, options, tenantParam());
            this.state.report = report;
            if (!dryRun) {
                this.state.imported = true;
                (report.failed ? toast.warning : toast.success)(report.message);
                this.props.onImported?.();
            }
        } catch (e) {
            toast.error(e instanceof ApiError ? e.message : String(e));
        } finally {
            this.state.processing = false;
        }
    }

    get fileSize() {
        return this.state.file ? `${Math.max(1, Math.ceil(this.state.file.size / 1024))} KB` : "";
    }

    get errorRows() {
        return (this.state.report?.results || []).filter((r) => r.status === "error");
    }

    get mappedColumns() {
        const mapping = this.state.report?.mapping || {};
        return Object.entries(mapping).map(([column, path]) => ({ column, path }));
    }

    formatErrors(row) {
        return (row.errors || []).map((e) => `${e.label || e.path}: ${e.message}`).join(" · ");
    }
}
