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

export class ApiView extends Component {
    static template = "payload.ApiView";
    static components = { DocumentHeader, CheckboxInput, RenderJSON };

    setup() {
        this.t = t;
        this.icon = icon;
        this.state = useState({ data: null, depth: 2, draft: false, authenticated: true, fullscreen: false, versionCount: 0 });
        onWillStart(async () => {
            await this.fetch();
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

    get fetchURL() {
        const path = this.isGlobal ? `/api/globals/${this.params.slug}` : `/api/${this.params.slug}/${this.params.id}`;
        const params = new URLSearchParams({ depth: String(this.state.depth), draft: String(this.state.draft), trash: "false" });
        if (store.locale) {
            params.set("locale", store.locale);
        }
        return `${window.location.origin}${path}?${params}`;
    }

    get title() {
        if (this.isGlobal) {
            return this.config.label;
        }
        return docTitle(this.config, this.state.data || {}) || String(this.params.id);
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
        try {
            const response = await fetch(this.fetchURL, { credentials: this.state.authenticated ? "include" : "omit", headers: { "Accept-Language": "en" } });
            this.state.data = await response.json();
        } catch (e) {
            toast.error(e.message);
        }
    }

    setDepth(ev) {
        this.state.depth = Math.max(0, Math.min(10, Number(ev.target.value) || 0));
        this.fetch();
    }

    setFlag(name, value) {
        this.state[name] = value;
        this.fetch();
    }

    async copy() {
        await navigator.clipboard?.writeText(this.fetchURL);
        toast.success(t("general:copied"));
    }
}
