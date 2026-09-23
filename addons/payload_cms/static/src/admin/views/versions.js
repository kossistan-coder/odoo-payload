/** @odoo-module **/

import { Component, markup, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { api } from "../core/api";
import { diffText, escapeHtml } from "../core/diff";
import { t } from "../core/i18n";
import { ensureDocs, relationLabel } from "../core/relations";
import { navigate, setQuery } from "../core/router";
import { dataFields } from "../core/schema";
import { confirmModal, getCollection, getGlobal, setStepNav, toast } from "../core/store";
import { docTitle, fieldLabel, formatDate, formatDistance, icon, lexicalToText, rowLabels } from "../core/utils";
import { CheckboxInput, Popup, PopupButton, Select } from "../components/base";
import { DocumentHeader, documentHeaderProps } from "./edit";

const PER_PAGE = [5, 10, 25, 50, 100];

/** Shared loading of the document the versions belong to. */
class VersionsBase extends Component {
    get params() {
        return this.props.route.params;
    }

    get isGlobal() {
        return this.params.kind === "global";
    }

    get config() {
        return this.isGlobal ? getGlobal(this.params.slug) : getCollection(this.params.slug);
    }

    get adminPath() {
        return this.isGlobal ? `/admin/globals/${this.params.slug}` : `/admin/collections/${this.params.slug}/${this.params.id}`;
    }

    get versionsApi() {
        return this.isGlobal ? `/globals/${this.params.slug}/versions` : `/${this.params.slug}/versions`;
    }

    get docApi() {
        return this.isGlobal ? `/globals/${this.params.slug}` : `/${this.params.slug}/${this.params.id}`;
    }

    async loadDoc() {
        this.state.doc = await api.get(this.docApi, { depth: 0, draft: "true" });
        const res = await api.get(this.versionsApi, this.isGlobal ? { limit: 1 } : { where: { parent: { equals: this.params.id } }, limit: 1 });
        this.state.versionCount = res.totalDocs;
        if (this.config.versions?.drafts) {
            const where = (extra) => (this.isGlobal ? extra : { ...extra, parent: { equals: this.params.id } });
            const [published, draft] = await Promise.all([
                api.get(this.versionsApi, { where: where({ "version._status": { equals: "published" } }), limit: 1 }),
                api.get(this.versionsApi, { where: where({ "version._status": { equals: "draft" } }), limit: 1 }),
            ]);
            this.state.currentlyPublished = published.docs[0] || null;
            this.state.latestDraft = draft.docs[0] || null;
        }
    }

    get title() {
        if (this.isGlobal) {
            return this.config.label;
        }
        return docTitle(this.config, this.state.doc) || String(this.params.id);
    }

    headerProps(active) {
        return documentHeaderProps({
            title: this.title,
            titleIsId: !this.isGlobal && this.title === String(this.params.id),
            docId: this.params.id,
            adminPath: this.adminPath,
            hasVersions: true,
            versionCount: this.state.versionCount,
            active,
        });
    }

    /** Payload's getVersionLabel. */
    versionLabel(version) {
        const published = this.state.currentlyPublished;
        const draft = this.state.latestDraft;
        if (version.version?._status === "draft") {
            if (published && draft && new Date(published.updatedAt) > new Date(draft.updatedAt)) {
                return { label: t("version:draft"), pillStyle: "light" };
            }
            return { label: draft && version.id === draft.id ? t("version:currentDraft") : t("version:draft"), pillStyle: "light" };
        }
        if (published && version.id === published.id) {
            return { label: t("version:currentlyPublished"), pillStyle: "success" };
        }
        return { label: t("version:previouslyPublished"), pillStyle: "light" };
    }
}

export class VersionsView extends VersionsBase {
    static template = "payload.VersionsView";
    static components = { DocumentHeader, Popup };

    setup() {
        this.t = t;
        this.icon = icon;
        this.formatDate = formatDate;
        this.perPage = PER_PAGE;
        this.state = useState({ loading: true, doc: null, versions: [], meta: null, versionCount: 0, currentlyPublished: null, latestDraft: null });
        onWillStart(() => this.load(this.props));
        onWillUpdateProps((next) => this.load(next));
    }

    async load(props) {
        const query = props.route.query;
        this.state.loading = true;
        try {
            await this.loadDoc();
            const params = {
                limit: query.limit || 10,
                page: query.page || 1,
                sort: query.sort || "-updatedAt",
            };
            if (!this.isGlobal) {
                params.where = { parent: { equals: this.params.id } };
            }
            const res = await api.get(this.versionsApi, params);
            const { docs, ...meta } = res;
            this.state.versions = docs;
            this.state.meta = meta;
        } catch (e) {
            toast.error(e.message);
        }
        this.state.loading = false;
        const nav = this.isGlobal
            ? [{ label: this.config.label, url: this.adminPath }, { label: t("version:versions") }]
            : [
                  { label: this.config.labels.plural, url: `/admin/collections/${this.params.slug}` },
                  { label: this.title, url: this.adminPath },
                  { label: t("version:versions") },
              ];
        setStepNav(nav);
    }

    get pageInfo() {
        const { page, limit, totalPages, totalDocs } = this.state.meta;
        const from = page * limit - (limit - 1);
        const to = totalPages > 1 && totalPages !== page ? limit * page : totalDocs;
        return `${from}-${to} ${t("general:of")} ${totalDocs}`;
    }

    get pages() {
        const meta = this.state.meta;
        const pages = [];
        for (let n = Math.max(1, meta.page - 1); n <= Math.min(meta.totalPages, meta.page + 1); n++) {
            pages.push(n);
        }
        return pages;
    }

    go(patch) {
        setQuery({ ...this.props.route.query, ...patch });
    }

    sortActive(dir) {
        const sort = this.props.route.query.sort || "-updatedAt";
        return dir === "asc" ? sort === "updatedAt" : sort === "-updatedAt";
    }
}

// ----------------------------------------------------------------------
// Diff rendering
// ----------------------------------------------------------------------
export class FieldDiffs extends Component {
    static template = "payload.FieldDiffs";
    static components = {};

    setup() {
        this.state = useState({ collapsed: {} });
        this.icon = icon;
        this.t = t;
    }

    get fields() {
        return (this.props.fields || []).filter((f) => !f.admin?.hidden);
    }

    equal(a, b) {
        return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
    }

    fromOf(field) {
        return field.name ? this.props.from?.[field.name] : this.props.from;
    }

    toOf(field) {
        return field.name ? this.props.to?.[field.name] : this.props.to;
    }

    changed(field) {
        if (field.type === "row" || field.type === "collapsible") {
            return dataFields(field.fields || []).some((f) => !this.equal(this.props.from?.[f.name], this.props.to?.[f.name]));
        }
        if (field.type === "tabs") {
            return (field.tabs || []).some((tab) => this.tabChanged(tab));
        }
        return !this.equal(this.fromOf(field), this.toOf(field));
    }

    tabChanged(tab) {
        if (tab.name) {
            return !this.equal(this.props.from?.[tab.name], this.props.to?.[tab.name]);
        }
        return dataFields(tab.fields || []).some((f) => !this.equal(this.props.from?.[f.name], this.props.to?.[f.name]));
    }

    visible(field) {
        return !this.props.modifiedOnly || this.changed(field);
    }

    label(field) {
        return fieldLabel(field);
    }

    diffClass(field) {
        const map = { select: "select-diff", radio: "select-diff", date: "date-diff", relationship: "relationship-diff-container", upload: "upload-diff-container", richText: "lexical-diff" };
        return map[field.type] || "text-diff";
    }

    toggle(key) {
        this.state.collapsed[key] = !this.state.collapsed[key];
    }

    changeCount(field) {
        const from = this.fromOf(field) || {};
        const to = this.toOf(field) || {};
        return dataFields(field.fields || []).filter((f) => !this.equal(from?.[f.name], to?.[f.name])).length;
    }

    textOf(field, value) {
        if (value === undefined || value === null || value === "") {
            return "";
        }
        switch (field.type) {
            case "richText":
                return lexicalBlocks(value).join("\n");
            case "select":
            case "radio": {
                const values = Array.isArray(value) ? value : [value];
                return values.map((v) => (field.options || []).find((o) => o.value === v)?.label || v).join(", ");
            }
            case "date":
                return formatDate(value);
            case "checkbox":
                return value ? "true" : "false";
            case "json":
                return JSON.stringify(value, null, 2);
            case "relationship":
            case "upload": {
                const values = Array.isArray(value) ? value : [value];
                return values.map((v) => relationLabel(field.relationTo, typeof v === "object" ? v.id : v)).join(", ");
            }
            default:
                return typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
        }
    }

    diffHtml(field) {
        const from = this.textOf(field, this.fromOf(field));
        const to = this.textOf(field, this.toOf(field));
        if (from === to && !from) {
            const empty = '<span class="html-diff-no-value"></span>';
            return { old: markup(empty), new: markup(empty) };
        }
        const byChar = ["text", "textarea", "email", "number", "code", "slug"].includes(field.type);
        if (field.type === "richText") {
            const res = diffText(from, to, { wrap: "" });
            return {
                old: markup(res.old.split("\n").map((l) => `<p>${l}</p>`).join("")),
                new: markup(res.new.split("\n").map((l) => `<p>${l}</p>`).join("")),
            };
        }
        const res = diffText(from, to, { byChar, wrap: ["json", "code"].includes(field.type) ? "pre" : "p" });
        return { old: markup(res.old), new: markup(res.new) };
    }

    rows(field) {
        const from = Array.isArray(this.fromOf(field)) ? this.fromOf(field) : [];
        const to = Array.isArray(this.toOf(field)) ? this.toOf(field) : [];
        const count = Math.max(from.length, to.length);
        const rows = [];
        for (let i = 0; i < count; i++) {
            const rowFrom = from[i] || {};
            const rowTo = to[i] || {};
            if (this.props.modifiedOnly && this.equal(rowFrom, rowTo)) {
                continue;
            }
            let fields = field.fields || [];
            if (field.type === "blocks") {
                const block = (field.blocks || []).find((b) => b.slug === (rowTo.blockType || rowFrom.blockType));
                fields = block?.fields || [];
            }
            const label = field.type === "blocks" ? t("fields:block") : t("general:item");
            rows.push({ index: i, from: rowFrom, to: rowTo, fields, label: `${label} ${String(i + 1).padStart(2, "0")}` });
        }
        return rows;
    }

    rowCount(field) {
        return Math.max((this.fromOf(field) || []).length, (this.toOf(field) || []).length);
    }

    pluralLabel(field) {
        return rowLabels(field).plural;
    }
}
FieldDiffs.components = { FieldDiffs };

function lexicalBlocks(state) {
    return (state?.root?.children || []).map((block) => {
        if (block.type === "upload" || block.type === "relationship") {
            return `[${block.type}: ${block.relationTo} ${block.value}]`;
        }
        if (block.type === "horizontalrule") {
            return "———";
        }
        return lexicalToText({ root: { children: [block] } });
    });
}

export class VersionView extends VersionsBase {
    static template = "payload.VersionView";
    static components = { DocumentHeader, FieldDiffs, Select, CheckboxInput, Popup, PopupButton };

    setup() {
        this.t = t;
        this.icon = icon;
        this.formatDate = formatDate;
        this.formatDistance = formatDistance;
        this.state = useState({ loading: true, doc: null, versionTo: null, versionFrom: null, options: [], versionCount: 0, currentlyPublished: null, latestDraft: null });
        onWillStart(() => this.load(this.props));
        onWillUpdateProps((next) => this.load(next));
    }

    get modifiedOnly() {
        return this.props.route.query.modifiedOnly !== "false";
    }

    async load(props) {
        const query = props.route.query;
        this.state.loading = true;
        try {
            await this.loadDoc();
            const versionTo = await api.get(`${this.versionsApi}/${this.params.versionId}`, { depth: 0 });
            this.state.versionTo = versionTo;
            const listParams = { limit: 50, sort: "-updatedAt" };
            if (!this.isGlobal) {
                listParams.where = { parent: { equals: this.params.id } };
            }
            const list = await api.get(this.versionsApi, listParams);
            const others = list.docs.filter((v) => v.id !== versionTo.id);
            this.state.options = others.map((v) => ({ value: v.id, label: `${this.versionLabel(v).label} — ${formatDate(v.updatedAt)}` }));
            let fromId = query.versionFrom ? Number(query.versionFrom) : null;
            if (!fromId) {
                const previous = others.find((v) => new Date(v.updatedAt) < new Date(versionTo.updatedAt) || v.id < versionTo.id);
                fromId = previous?.id || others[0]?.id || null;
            }
            this.state.versionFrom = fromId ? others.find((v) => v.id === fromId) || (await api.get(`${this.versionsApi}/${fromId}`, { depth: 0 })) : null;
            await this.preloadRelations();
        } catch (e) {
            toast.error(e.message);
        }
        this.state.loading = false;
        const date = formatDate(this.state.versionTo?.updatedAt);
        const nav = this.isGlobal
            ? [{ label: this.config.label, url: this.adminPath }, { label: t("version:versions"), url: `${this.adminPath}/versions` }, { label: date }]
            : [
                  { label: this.config.labels.plural, url: `/admin/collections/${this.params.slug}` },
                  { label: this.title, url: this.adminPath },
                  { label: t("version:versions"), url: `${this.adminPath}/versions` },
                  { label: date },
              ];
        setStepNav(nav);
    }

    async preloadRelations() {
        const byCollection = {};
        const walk = (fields, from, to) => {
            for (const field of dataFields(fields)) {
                const values = [from?.[field.name], to?.[field.name]];
                if (field.type === "relationship" || field.type === "upload") {
                    for (const v of values) {
                        for (const id of (Array.isArray(v) ? v : [v]).filter((x) => x !== null && x !== undefined)) {
                            (byCollection[field.relationTo] ||= []).push(typeof id === "object" ? id.id : id);
                        }
                    }
                } else if (field.type === "group") {
                    walk(field.fields || [], from?.[field.name], to?.[field.name]);
                } else if (field.type === "array" || field.type === "blocks") {
                    const rowsFrom = from?.[field.name] || [];
                    const rowsTo = to?.[field.name] || [];
                    for (let i = 0; i < Math.max(rowsFrom.length, rowsTo.length); i++) {
                        const block = field.type === "blocks" ? (field.blocks || []).find((b) => b.slug === (rowsTo[i] || rowsFrom[i])?.blockType) : null;
                        walk(field.type === "blocks" ? block?.fields || [] : field.fields || [], rowsFrom[i], rowsTo[i]);
                    }
                }
            }
        };
        walk(this.config.fields, this.state.versionFrom?.version, this.state.versionTo?.version);
        await Promise.all(Object.entries(byCollection).map(([slug, ids]) => ensureDocs(slug, ids)));
    }

    setVersionFrom(id) {
        setQuery({ ...this.props.route.query, versionFrom: id });
    }

    toggleModifiedOnly(checked) {
        setQuery({ ...this.props.route.query, modifiedOnly: checked ? "" : "false" });
    }

    get canRestoreAsDraft() {
        return this.config.versions?.drafts && this.state.versionTo?.version?._status !== "draft";
    }

    async restore(draft = false) {
        const label = this.isGlobal ? this.config.label : this.config.labels.singular;
        const versionDate = formatDate(this.state.versionTo.updatedAt);
        const ok = await confirmModal({
            heading: t("version:confirmVersionRestoration"),
            body: this.isGlobal ? t("version:aboutToRestoreGlobal", { label, versionDate }) : t("version:aboutToRestore", { label, versionDate }),
            confirmingLabel: t("version:restoring"),
            onConfirm: async () => {
                try {
                    const res = await api.post(`${this.versionsApi}/${this.params.versionId}`, {}, { draft: draft ? "true" : "false" });
                    toast.success(res.message);
                } catch (e) {
                    toast.error(t("version:problemRestoringVersion"));
                    throw e;
                }
            },
        });
        if (ok) {
            navigate(this.adminPath, { force: true });
        }
    }

    pill(version) {
        return this.versionLabel(version);
    }
}

export { escapeHtml };
