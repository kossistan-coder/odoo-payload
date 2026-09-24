/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { api } from "../core/api";
import { t } from "../core/i18n";
import { getCollection, getGlobal, setStepNav, store, toast } from "../core/store";
import { docTitle, icon } from "../core/utils";
import { CheckboxInput } from "../components/base";
import { DocumentHeader, documentHeaderProps } from "./edit";

/** Recursive JSON tree of the API view (RenderJSON). */
export class RenderJSON extends Component {
    static template = "payload.RenderJSON";

    setup() {
        this.state = useState({ open: true });
        this.icon = icon;
    }

    get isArray() {
        return Array.isArray(this.props.value);
    }

    get entries() {
        const v = this.props.value || {};
        return this.isArray ? v.map((item, i) => [i, item]) : Object.entries(v);
    }

    get isEmpty() {
        return this.entries.length === 0;
    }

    isObject(v) {
        return v !== null && typeof v === "object";
    }

    typeOf(v) {
        if (v === null) {
            return "null";
        }
        if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}T/.test(v)) {
            return "date";
        }
        return typeof v;
    }

    stringify(v) {
        return JSON.stringify(v);
    }
}
RenderJSON.components = { RenderJSON };

/** Default `web_read` specification: every field of the document, relations as {id, display_name}. */
function defaultSpecification(fields) {
    const spec = {};
    const walk = (list) => {
        for (const field of list || []) {
            if (["row", "collapsible"].includes(field.type)) {
                walk(field.fields);
            } else if (field.type === "tabs") {
                for (const tab of field.tabs || []) {
                    if (tab.name) {
                        spec[tab.name] = {};
                    } else {
                        walk(tab.fields);
                    }
                }
            } else if (field.name && !field.admin?.hidden) {
                spec[field.name] = {};
            }
        }
    };
    walk(fields);
    return spec;
}

/**
 * API tab of a document: the document read like the API of the site reads it
 * (`web_read` of /payload/dataset/call_kw, Odoo shapes), the specification of the
 * fields, the calls to copy, and the documented routes of the collection.
 */
export class ApiView extends Component {
    static template = "payload.ApiView";
    static components = { DocumentHeader, CheckboxInput, RenderJSON };

    setup() {
        this.t = t;
        this.icon = icon;
        this.store = store;
        this.state = useState({
            data: null, error: null, draft: false, authenticated: true, fullscreen: false, versionCount: 0,
            specText: JSON.stringify(defaultSpecification(this.config.fields), null, 2), routes: [],
        });
        onWillStart(async () => {
            await Promise.all([this.fetch(), this.loadRoutes()]);
            if (this.config.versions?.enabled) {
                const res = this.isGlobal
                    ? await api.get(`/globals/${this.params.slug}/versions`, { limit: 1 })
                    : await api.get(`/${this.params.slug}/versions`, { where: { parent: { equals: this.params.id } }, limit: 1 });
                this.state.versionCount = res.totalDocs;
            }
            this.updateStepNav();
        });
    }

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

    get specification() {
        try {
            return JSON.parse(this.state.specText || "{}");
        } catch {
            return null;
        }
    }

    get context() {
        const context = {};
        if (this.state.draft) {
            context.draft = true;
        }
        if (store.locale) {
            context.lang = store.locale;
        }
        return context;
    }

    get rpcParams() {
        const kwargs = { specification: this.specification || {} };
        if (Object.keys(this.context).length) {
            kwargs.context = this.context;
        }
        return { model: this.params.slug, method: "web_read", args: [this.isGlobal ? [] : [Number(this.params.id)]], kwargs };
    }

    get rpcURL() {
        return `${window.location.origin}/payload/dataset/call_kw`;
    }

    get curl() {
        const body = JSON.stringify({ jsonrpc: "2.0", method: "call", params: this.rpcParams });
        return `curl -X POST ${this.rpcURL} -H 'Content-Type: application/json' -d '${body.replace(/'/g, "'\\''")}'`;
    }

    get python() {
        const spec = JSON.stringify(this.specification || {}, null, 4).replace(/\btrue\b/g, "True").replace(/\bfalse\b/g, "False").replace(/\bnull\b/g, "None");
        const ctx = Object.keys(this.context).length
            ? `.with_context(${Object.entries(this.context).map(([k, v]) => `${k}=${typeof v === "string" ? `'${v}'` : "True"}`).join(", ")})`
            : "";
        return `from odoo.addons.payload_cms.payload import Model\n\nModel(env, '${this.params.slug}')${ctx}.web_read(${this.isGlobal ? "[]" : `[${this.params.id}]`}, ${spec})`;
    }

    get title() {
        if (this.isGlobal) {
            return this.config.label;
        }
        return this.state.data?.display_name || docTitle(this.config, this.state.data || {}) || String(this.params.id);
    }

    get headerProps() {
        return documentHeaderProps({
            title: this.title,
            titleIsId: !this.isGlobal && this.title === String(this.params.id),
            docId: this.params.id,
            adminPath: this.adminPath,
            hasVersions: Boolean(this.config.versions?.enabled),
            versionCount: this.state.versionCount,
            active: "api",
        });
    }

    updateStepNav() {
        const nav = this.isGlobal
            ? [{ label: this.config.label, url: this.adminPath }, { label: "API" }]
            : [
                  { label: this.config.labels.plural, url: `/admin/collections/${this.params.slug}` },
                  { label: this.title, url: this.adminPath },
                  { label: "API" },
              ];
        setStepNav(nav);
    }

    async fetch() {
        if (!this.specification) {
            this.state.error = "The specification is not valid JSON.";
            return;
        }
        try {
            const response = await fetch(this.rpcURL, {
                method: "POST",
                credentials: this.state.authenticated ? "include" : "omit",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: this.rpcParams }),
            });
            const res = await response.json();
            if (res.error) {
                this.state.error = res.error.data?.message || res.error.message;
                this.state.data = null;
            } else {
                this.state.error = null;
                this.state.data = res.result?.[0] || {};
            }
        } catch (e) {
            this.state.error = e.message;
        }
    }

    async loadRoutes() {
        try {
            const res = await api.get("/_admin/routes", { model: this.params.slug });
            this.state.routes = res.routes || [];
        } catch {
            this.state.routes = [];
        }
    }

    setFlag(name, value) {
        this.state[name] = value;
        this.fetch();
    }

    onSpecInput(ev) {
        this.state.specText = ev.target.value;
    }

    resetSpec() {
        this.state.specText = JSON.stringify(defaultSpecification(this.config.fields), null, 2);
        this.fetch();
    }

    async copy(text) {
        await navigator.clipboard?.writeText(text);
        toast.success(t("general:copied"));
    }
}
