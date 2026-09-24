/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { api, setApiLocale, setApiTenant } from "./api";
import { configCollection } from "./config_schema";
import { extensions } from "./extensions";

/**
 * Global reactive state of the admin: client config (collections/globals
 * schema), authenticated user, breadcrumbs, nav state, toasts & modals.
 */
export const store = reactive({
    ready: false,
    config: null,
    user: null,
    stepNav: [],
    navOpen: window.innerWidth > 1440 && localStorage.getItem("payload-nav-open") !== "false",
    toasts: [],
    modals: [],
    locale: null,
    tenant: null,
    tenants: [],
});

// ----------------------------------------------------------------------
// Multisite (tenant selector)
// ----------------------------------------------------------------------
export function multitenancy() {
    return store.config?.multitenancy?.enabled ? store.config.multitenancy : null;
}

export function currentTenant() {
    return store.tenants.find((t) => t.id === store.tenant) || null;
}

/** Reload the sites of the selector (after a site is created, renamed or deleted). */
export function refreshTenants() {
    return syncTenant();
}

async function syncTenant() {
    if (!multitenancy()) {
        store.tenants = [];
        store.tenant = null;
        setApiTenant(null);
        return;
    }
    try {
        const res = await api.get("/tenants", { limit: 500, depth: 0, sort: "name", pagination: "false" });
        store.tenants = res.docs.map((d) => ({ id: d.id, name: d.name || d.slug || `#${d.id}`, slug: d.slug, siteUrls: d.siteUrls || [] }));
    } catch {
        store.tenants = [];
    }
    let id = store.tenant;
    try {
        id = id ?? (Number(localStorage.getItem("payload-tenant")) || null);
    } catch {
        // storage unavailable
    }
    const restricted = store.config.multitenancy.userTenants;
    if (!store.tenants.some((t) => t.id === id)) {
        // restricted editors always work in one of their sites
        id = restricted?.length ? store.tenants[0]?.id || null : null;
    }
    store.tenant = id;
    setApiTenant(id);
}

export function setTenant(id) {
    try {
        localStorage.setItem("payload-tenant", id ? String(id) : "");
    } catch {
        // storage unavailable
    }
    store.tenant = id || null;
    setApiTenant(store.tenant);
}

const MULTITENANCY_GLOBAL = {
    slug: "_config_multitenancy",
    virtual: true,
    label: "Multisite",
    labels: { singular: "Multisite", plural: "Multisite" },
    apiPath: "/_admin/schema/multitenancy",
    adminPath: "/admin/config/multitenancy",
    versions: { enabled: false, drafts: false },
    admin: {
        description: "Multi-tenant mode, like WordPress Multisite: networks of sites on subdomains ({site}.example.com) or custom domains, each site with its own content.",
    },
    fields: [
        {
            name: "enabled",
            type: "checkbox",
            label: "Enable multisite",
            admin: { description: "Adds the Networks and Sites collections, the site selector of the navigation and the X-Payload-Tenant header to the API." },
        },
        {
            name: "scopedCollections",
            type: "select",
            hasMany: true,
            label: "Collections scoped per site",
            options: [],
            admin: { description: "Their documents belong to a site (\"Site\" field) and the API only returns the documents of the current site. Scoped globals have one document per site (falling back to the shared one)." },
        },
        {
            type: "row",
            fields: [
                { name: "resolveByHost", type: "checkbox", label: "Resolve the site from the domain", admin: { width: "50%", description: "blog.example.com or a custom domain selects the site automatically (frontends need no header)." } },
                { name: "corsSites", type: "checkbox", label: "Allow site domains (CORS)", admin: { width: "50%", description: "Frontends served on the site domains can call the API." } },
            ],
        },
        {
            type: "row",
            fields: [
                { name: "networkCount", type: "number", label: "Networks", admin: { width: "50%", readOnly: true } },
                { name: "siteCount", type: "number", label: "Sites", admin: { width: "50%", readOnly: true } },
            ],
        },
    ],
};

const API_DOCS_GLOBAL = {
    slug: "_config_api_docs",
    virtual: true,
    label: "API Docs Settings",
    labels: { singular: "API Docs Settings", plural: "API Docs Settings" },
    apiPath: "/_admin/schema/api-docs",
    adminPath: "/admin/config/api-docs",
    versions: { enabled: false, drafts: false },
    admin: { description: "Swagger UI and OpenAPI 3 specification (/api-docs) of the API routes written by your modules: the controller routes marked with @api_doc and the collection methods marked with @expose." },
    fields: [
        {
            type: "row",
            fields: [
                { name: "enabled", type: "checkbox", label: "Enable the API documentation", admin: { width: "50%" } },
                { name: "public", type: "checkbox", label: "Public", admin: { width: "50%", description: "Anyone can read /api-docs. Otherwise only CMS users." } },
            ],
        },
        {
            type: "row",
            fields: [
                { name: "title", type: "text", label: "Title", admin: { width: "50%" } },
                { name: "version", type: "text", label: "Version", admin: { width: "50%", placeholder: "1.0.0" } },
            ],
        },
        { name: "description", type: "textarea", label: "Description", admin: { description: "Markdown, shown at the top of the documentation." } },
        {
            name: "modules",
            type: "select",
            hasMany: true,
            label: "Documented modules",
            options: [],
            admin: { description: "Modules using payload_cms whose API is documented. Leave empty to document every module." },
        },
        {
            type: "row",
            fields: [
                { name: "includeRpc", type: "checkbox", label: "Document the generic JSON-RPC endpoint", admin: { width: "50%", description: "/payload/dataset/call_kw (search_read, web_search_read…)." } },
                { name: "includeAuth", type: "checkbox", label: "Document the authentication endpoint", admin: { width: "50%", description: "Login returning a JWT (routes reserved to the CMS users)." } },
            ],
        },
        {
            name: "servers",
            type: "array",
            label: "Servers",
            labels: { singular: "Server", plural: "Servers" },
            admin: { description: "Base URLs listed in the documentation (default: this server).", rowLabelField: "url" },
            fields: [
                {
                    type: "row",
                    fields: [
                        { name: "url", type: "text", label: "URL", required: true, admin: { width: "50%", placeholder: "https://cms.example.com" } },
                        { name: "description", type: "text", label: "Description", admin: { width: "50%", placeholder: "Production" } },
                    ],
                },
            ],
        },
        {
            type: "row",
            fields: [
                { name: "docsUrl", type: "text", label: "Swagger UI", admin: { width: "50%", readOnly: true } },
                { name: "specUrl", type: "text", label: "OpenAPI (JSON)", admin: { width: "50%", readOnly: true } },
            ],
        },
    ],
};

/** Virtual global of the file storage settings (Configuration → Storage). */
const S3 = { condition: { field: "backend", equals: "s3" } };
const STORAGE_GLOBAL = {
    slug: "_config_storage",
    virtual: true,
    label: "Storage",
    labels: { singular: "Storage", plural: "Storage" },
    apiPath: "/_admin/schema/storage",
    adminPath: "/admin/config/storage",
    versions: { enabled: false, drafts: false },
    admin: {
        description: "Where the files of the upload collections (media…) are stored: Odoo attachments, or an S3-compatible bucket (AWS S3, MinIO…). Existing files stay in the storage they were uploaded to.",
    },
    fields: [
        {
            name: "backend",
            type: "radio",
            label: "Storage",
            defaultValue: "native",
            options: [
                { value: "native", label: "Odoo (attachments / filestore)" },
                { value: "s3", label: "S3-compatible bucket (AWS S3, MinIO…)" },
            ],
            admin: { description: "New uploads go to this storage. The connection is checked on save." },
        },
        {
            type: "row",
            admin: S3,
            fields: [
                { name: "endpoint", type: "text", label: "Endpoint URL", admin: { width: "50%", placeholder: "http://minio:9000", description: "Empty for AWS S3 (https://s3.{region}.amazonaws.com)." } },
                { name: "region", type: "text", label: "Region", admin: { width: "50%", placeholder: "us-east-1" } },
            ],
        },
        {
            type: "row",
            admin: S3,
            fields: [
                { name: "bucket", type: "text", label: "Bucket", admin: { width: "50%", placeholder: "payload-media" } },
                { name: "prefix", type: "text", label: "Path prefix", admin: { width: "50%", placeholder: "media", description: "Optional folder of the objects in the bucket." } },
            ],
        },
        {
            type: "row",
            admin: S3,
            fields: [
                { name: "accessKey", type: "text", label: "Access key", admin: { width: "50%" } },
                { name: "secretKey", type: "text", label: "Secret key", admin: { width: "50%", description: "Leave empty to keep the saved key." } },
            ],
        },
        {
            type: "row",
            admin: S3,
            fields: [
                { name: "secretKeySet", type: "checkbox", label: "A secret key is saved", admin: { width: "50%", readOnly: true } },
                { name: "clearSecretKey", type: "checkbox", label: "Remove the saved key", admin: { width: "50%" } },
            ],
        },
        {
            name: "addressing",
            type: "radio",
            label: "Addressing style",
            defaultValue: "path",
            options: [
                { value: "path", label: "Path (endpoint/bucket/key, MinIO)" },
                { value: "virtual", label: "Virtual host (bucket.endpoint/key)" },
            ],
            admin: S3,
        },
        {
            name: "delivery",
            type: "radio",
            label: "File delivery",
            defaultValue: "proxy",
            options: [
                { value: "proxy", label: "Through Odoo (/api/{collection}/file/{filename}, private bucket)" },
                { value: "public", label: "Directly from the public URL of the bucket (or CDN)" },
            ],
            admin: { ...S3, description: "Direct delivery needs a publicly readable bucket: file URLs point to the public URL and /api/…/file/… redirects to it." },
        },
        { name: "publicUrl", type: "text", label: "Public base URL", admin: { ...S3, placeholder: "http://localhost:9010/payload-media", description: "Base URL of the objects (bucket URL or CDN), required for direct delivery." } },
        {
            type: "row",
            fields: [
                { name: "testConnection", type: "checkbox", label: "Test the S3 connection on save", admin: { width: "33%", description: "Always done when the S3 storage is selected." } },
                { name: "createBucket", type: "checkbox", label: "Create the bucket if missing", admin: { width: "33%" } },
                { name: "migrateExisting", type: "checkbox", label: "Move existing files to this storage", admin: { width: "33%", description: "On save, copies the files stored elsewhere, then deletes the originals." } },
            ],
        },
        {
            type: "row",
            fields: [
                { name: "nativeCount", type: "number", label: "Files in Odoo", admin: { width: "50%", readOnly: true } },
                { name: "s3Count", type: "number", label: "Files in S3", admin: { width: "50%", readOnly: true } },
            ],
        },
        { name: "envVariables", type: "text", label: "Set by environment variables", admin: { readOnly: true, description: "PAYLOAD_STORAGE and PAYLOAD_S3_* (docker compose / odoo.conf) override these settings and cannot be changed here." } },
    ],
};

/** Storage settings whose fields set by environment variables are read-only. */
let storageGlobal = { config: null, global: null };
function withStorageLocks() {
    if (storageGlobal.config !== store.config) {
        const locked = new Set(store.config.storage?.envKeys || []);
        const patch = (fields) =>
            fields.map((f) => (locked.has(f.name) ? { ...f, admin: { ...f.admin, readOnly: true } } : f.fields ? { ...f, fields: patch(f.fields) } : f));
        storageGlobal = { config: store.config, global: { ...STORAGE_GLOBAL, fields: patch(STORAGE_GLOBAL.fields) } };
    }
    return storageGlobal.global;
}

// ----------------------------------------------------------------------
// Localization (Payload's `localization` config + locale selector)
// ----------------------------------------------------------------------
export function localization() {
    const conf = store.config?.localization;
    return conf?.enabled && conf.locales?.length ? conf : null;
}

/** Current locale object ({code, label}) or null when localization is off. */
export function currentLocale() {
    const conf = localization();
    if (!conf) {
        return null;
    }
    return conf.locales.find((l) => l.code === store.locale) || conf.locales.find((l) => l.code === conf.defaultLocale) || conf.locales[0];
}

function syncLocale() {
    const conf = localization();
    if (!conf) {
        store.locale = null;
    } else {
        let code = store.locale || new URLSearchParams(window.location.search).get("locale");
        try {
            code = code || localStorage.getItem("payload-locale");
        } catch {
            // storage unavailable
        }
        store.locale = conf.locales.some((l) => l.code === code) ? code : conf.defaultLocale;
    }
    setApiLocale(store.locale);
}

export function setLocale(code) {
    try {
        localStorage.setItem("payload-locale", code);
    } catch {
        // storage unavailable
    }
    store.locale = code;
    setApiLocale(code);
}

/** Virtual global of the localization settings (Configuration → Localization). */
const LOCALIZATION_GLOBAL = {
    slug: "_config_localization",
    virtual: true,
    label: "Localization",
    labels: { singular: "Localization", plural: "Localization" },
    apiPath: "/_admin/schema/localization",
    adminPath: "/admin/config/localization",
    versions: { enabled: false, drafts: false },
    admin: {
        description: "Payload's localization: one value per locale for the fields marked \"Localized\", and automatic translation with Google Translate.",
    },
    fields: [
        {
            name: "enabled",
            type: "checkbox",
            label: "Enable localization",
            admin: { description: "Adds the locale selector to the admin and the ?locale= parameter to the REST API." },
        },
        {
            name: "locales",
            type: "array",
            label: "Locales",
            labels: { singular: "Locale", plural: "Locales" },
            minRows: 1,
            admin: { rowLabelField: "label", rowLabelFallback: "code" },
            fields: [
                {
                    type: "row",
                    fields: [
                        { name: "code", type: "text", label: "Code", required: true, admin: { width: "33%", placeholder: "fr", description: "ISO code, also used by Google Translate." } },
                        { name: "label", type: "text", label: "Label", admin: { width: "33%", placeholder: "Français" } },
                        { name: "rtl", type: "checkbox", label: "Right to left", admin: { width: "33%" } },
                    ],
                },
            ],
        },
        {
            type: "row",
            fields: [
                { name: "defaultLocale", type: "text", label: "Default Locale", required: true, admin: { width: "50%", description: "Code of the locale used when none is requested." } },
                { name: "fallback", type: "checkbox", label: "Fallback to default locale", admin: { width: "50%", description: "Empty localized values return the default locale value." } },
            ],
        },
        {
            name: "localizedCollections",
            type: "select",
            hasMany: true,
            label: "Translated collections",
            options: [],
            admin: {
                description: "The text, textarea, rich text and slug fields of the selected collections become \"Localized\" (one value per locale). You can also check \"Localized\" field by field in Configuration → Collections. Removing a collection keeps its default locale values.",
            },
        },
        {
            type: "collapsible",
            label: "Machine translation",
            admin: {},
            fields: [
                {
                    name: "provider",
                    type: "radio",
                    label: "Translation service",
                    defaultValue: "google",
                    options: [
                        { value: "mymemory", label: "MyMemory (free, no key)" },
                        { value: "google", label: "Google Translate (API key)" },
                        { value: "libretranslate", label: "LibreTranslate (open source, self-hosted)" },
                    ],
                    admin: { description: "MyMemory works without any configuration (daily quota, higher with an email). Google Cloud Translation needs an API key." },
                },
                {
                    name: "apiKey",
                    type: "text",
                    label: "API Key",
                    admin: {
                        condition: { field: "provider", in: ["google", "libretranslate"] },
                        description: "Google: Cloud Translation API (v2) key. LibreTranslate: optional. Leave empty to keep the saved key.",
                        placeholder: "AIza…",
                    },
                },
                { name: "url", type: "text", label: "LibreTranslate URL", admin: { condition: { field: "provider", equals: "libretranslate" }, placeholder: "https://translate.example.com" } },
                { name: "email", type: "email", label: "Email (optional)", admin: { condition: { field: "provider", equals: "mymemory" }, description: "Raises the MyMemory daily quota from 5,000 to 50,000 characters." } },
                { name: "apiKeySet", type: "checkbox", label: "An API key is saved", admin: { readOnly: true, width: "50%", condition: { field: "provider", in: ["google", "libretranslate"] } } },
                { name: "clearApiKey", type: "checkbox", label: "Remove the saved key", admin: { width: "50%", condition: { field: "provider", in: ["google", "libretranslate"] } } },
                {
                    name: "autoTranslate",
                    type: "radio",
                    label: "Automatic translation",
                    defaultValue: "off",
                    options: [
                        { value: "off", label: "Off (manual “Translate” action only)" },
                        { value: "missing", label: "Fill empty locales on save" },
                        { value: "always", label: "Re-translate all locales on save" },
                    ],
                    admin: { description: "Runs after each save made in the default locale." },
                },
                {
                    name: "translateExisting",
                    type: "checkbox",
                    label: "Translate existing documents now",
                    admin: { description: "On save, fills the empty translations of every document of the translated collections (can take a while)." },
                },
            ],
        },
    ],
};

/** Built-in "users" auth collection (backed by Odoo res.users). */
export const USERS_COLLECTION = {
    slug: "users",
    labels: { singular: "User", plural: "Users" },
    label: "Users",
    isUsers: true,
    admin: {
        useAsTitle: "email",
        defaultColumns: ["email", "name", "roles", "updatedAt"],
        listSearchableFields: ["email", "name"],
        group: false,
        description: "",
    },
    auth: true,
    versions: { enabled: false, drafts: false },
    upload: false,
    defaultSort: "email",
    defaultLimit: 10,
    fields: [
        { name: "email", type: "email", label: "Email", required: true, admin: {} },
        { name: "name", type: "text", label: "Name", admin: {} },
        {
            name: "roles",
            type: "select",
            label: "Roles",
            hasMany: true,
            options: [
                { value: "admin", label: "Admin" },
                { value: "editor", label: "Editor" },
            ],
            admin: { readOnly: true, position: "sidebar" },
        },
    ],
};

export async function loadSession() {
    try {
        const me = await api.get("/users/me");
        store.user = me.user;
        if (me.user) {
            store.config = await api.get("/_admin/config");
            syncLocale();
            await syncTenant();
        }
    } catch {
        store.user = null;
    }
    store.ready = true;
}

let usersWithTenants = null;
export function getCollection(slug) {
    if (slug === "users") {
        if (!multitenancy()) {
            return USERS_COLLECTION;
        }
        // multisite: sites an editor can manage (admins only)
        usersWithTenants ||= {
            ...USERS_COLLECTION,
            fields: [
                ...USERS_COLLECTION.fields,
                { name: "tenants", type: "relationship", relationTo: "tenants", hasMany: true, label: "Sites", admin: { position: "sidebar", description: "Sites this editor can manage (empty = all). Admins manage every site." } },
            ],
        };
        return store.config?.isAdmin ? usersWithTenants : { ...usersWithTenants, fields: usersWithTenants.fields.map((f) => (f.name === "tenants" ? { ...f, admin: { ...f.admin, readOnly: true } } : f)) };
    }
    if (slug?.startsWith("_config_")) {
        return store.config?.isAdmin ? configCollection(slug, store.config) : null;
    }
    return store.config?.collections.find((c) => c.slug === slug) || null;
}

export function getGlobal(slug) {
    if (slug === LOCALIZATION_GLOBAL.slug) {
        return store.config?.isAdmin ? withCollectionOptions(LOCALIZATION_GLOBAL, "localizedCollections") : null;
    }
    if (slug === MULTITENANCY_GLOBAL.slug) {
        return store.config?.isAdmin ? withCollectionOptions(MULTITENANCY_GLOBAL, "scopedCollections") : null;
    }
    if (slug === API_DOCS_GLOBAL.slug) {
        return store.config?.isAdmin ? withModuleOptions() : null;
    }
    if (slug === STORAGE_GLOBAL.slug) {
        return store.config?.isAdmin ? withStorageLocks() : null;
    }
    return store.config?.globals.find((g) => g.slug === slug) || null;
}

/** API Docs settings whose `modules` select lists the modules using payload_cms. */
let moduleOptions = { config: null, global: null };
function withModuleOptions() {
    if (moduleOptions.config !== store.config) {
        const options = store.config.apiDocs?.modules || [];
        const patch = (fields) => fields.map((f) => (f.name === "modules" ? { ...f, options } : f.fields ? { ...f, fields: patch(f.fields) } : f));
        moduleOptions = { config: store.config, global: { ...API_DOCS_GLOBAL, fields: patch(API_DOCS_GLOBAL.fields) } };
    }
    return moduleOptions.global;
}

/** Copy of a virtual global whose `name` select lists the collections & globals. */
const optionsCache = new WeakMap();
function withCollectionOptions(global, name, { globals = true } = {}) {
    const config = store.config;
    const key = `${global.slug}:${name}`;
    const cached = optionsCache.get(config)?.[key];
    if (cached) {
        return cached;
    }
    const options = [
        ...config.collections.filter((c) => !["tenants", "networks"].includes(c.slug)).map((c) => ({ value: c.slug, label: c.labels.plural })),
        ...(globals ? config.globals.map((g) => ({ value: `globals/${g.slug}`, label: `${g.label} (global)` })) : []),
    ];
    const patch = (fields) => fields.map((f) => (f.name === name ? { ...f, options } : f.fields ? { ...f, fields: patch(f.fields) } : f));
    const result = { ...global, fields: patch(global.fields) };
    if (!optionsCache.has(config)) {
        optionsCache.set(config, {});
    }
    optionsCache.get(config)[key] = result;
    return result;
}

/** Nav groups: "Collections", "Globals", then custom admin.group labels. */
export function navGroups() {
    if (!store.config) {
        return [];
    }
    const groups = new Map([
        ["Collections", []],
        ["Globals", []],
    ]);
    const add = (label, entity) => {
        if (!groups.has(label)) {
            groups.set(label, []);
        }
        groups.get(label).push(entity);
    };
    // Pages, Posts, Media, Users, then the other collections (by sequence)
    const ordered = [...store.config.collections, { ...USERS_COLLECTION, sequence: 35 }]
        .map((c, index) => ({ c, index }))
        .sort((a, b) => (a.c.sequence ?? 100) - (b.c.sequence ?? 100) || a.index - b.index)
        .map(({ c }) => c);
    for (const c of ordered) {
        if (c.admin?.hidden) {
            continue;
        }
        add(c.admin?.group || "Collections", {
            type: "collection",
            slug: c.slug,
            label: c.labels.plural,
            singular: c.labels.singular,
            href: `/admin/collections/${c.slug}`,
        });
    }
    for (const g of store.config.globals) {
        if (g.admin?.hidden) {
            continue;
        }
        add(g.admin?.group || "Globals", {
            type: "global",
            slug: g.slug,
            label: g.label,
            href: `/admin/globals/${g.slug}`,
        });
    }
    // views registered by the modules (core/extensions.js)
    void extensions.views.length; // re-render the navigation when a module registers a view
    for (const view of extensions.views) {
        if (view.nav === false || (view.adminOnly && !store.config.isAdmin)) {
            continue;
        }
        add(view.group, { type: "view", slug: `x-${view.path.replace(/\//g, "-")}`, label: view.label, href: `/admin/x/${view.path}` });
    }
    if (store.config.isAdmin) {
        for (const [section, label, singular] of [["collections", "Collections", "Collection"], ["globals", "Globals", "Global"], ["blocks", "Blocks", "Block"], ["fields", "Fields", "Field"]]) {
            add("Configuration", {
                type: "collection",
                slug: `_config_${section}`,
                label,
                singular,
                href: `/admin/config/${section}`,
                noCreate: section === "fields",
            });
        }
        add("Configuration", { type: "global", slug: LOCALIZATION_GLOBAL.slug, label: "Localization", href: "/admin/config/localization" });
        add("Configuration", { type: "global", slug: MULTITENANCY_GLOBAL.slug, label: "Multisite", href: "/admin/config/multitenancy" });
        add("Configuration", { type: "global", slug: STORAGE_GLOBAL.slug, label: "Storage", href: "/admin/config/storage" });
        add("Configuration", { type: "global", slug: API_DOCS_GLOBAL.slug, label: "API Docs Settings", href: "/admin/config/api-docs" });
    }
    if (store.config.apiDocs?.enabled) {
        add("Developers", { type: "view", slug: "api-docs", label: "API Docs", href: "/admin/api-docs" });
    }
    return [...groups.entries()].filter(([, e]) => e.length).map(([label, entities]) => ({ label, entities }));
}

/** REST path of a collection (virtual config collections live under /_admin/schema). */
export function apiBase(collection) {
    return collection.apiPath || `/${collection.slug}`;
}

/** Admin URL of a collection. */
export function adminBase(collection) {
    return collection.adminPath || `/admin/collections/${collection.slug}`;
}

/** Reload the client config after a schema change. */
export async function reloadConfig() {
    store.config = await api.get("/_admin/config");
    syncLocale();
    await syncTenant();
}

export function setStepNav(items) {
    store.stepNav = items;
}

// ----------------------------------------------------------------------
// Toasts (sonner-like)
// ----------------------------------------------------------------------
let toastId = 0;

function pushToast(type, message, options = {}) {
    const id = ++toastId;
    store.toasts.unshift({ id, type, message, description: options.description, removed: false });
    const timer = setTimeout(() => dismissToast(id), options.duration || 4000);
    store.toasts[0].timer = timer;
    if (store.toasts.length > 5) {
        store.toasts.splice(5);
    }
    return id;
}

export function dismissToast(id) {
    const toast = store.toasts.find((t) => t.id === id);
    if (!toast) {
        return;
    }
    toast.removed = true;
    clearTimeout(toast.timer);
    setTimeout(() => {
        const index = store.toasts.findIndex((t) => t.id === id);
        if (index >= 0) {
            store.toasts.splice(index, 1);
        }
    }, 200);
}

export const toast = {
    success: (message, options) => pushToast("success", message, options),
    error: (message, options) => pushToast("error", message, options),
    info: (message, options) => pushToast("info", message, options),
    warning: (message, options) => pushToast("warning", message, options),
};

// ----------------------------------------------------------------------
// Modals: confirmation modals and drawers (rendered by the ModalContainer)
// ----------------------------------------------------------------------
let modalId = 0;

/** Payload's ConfirmationModal. Resolves true when confirmed. */
export function confirmModal({ heading, body, bodyMarkup, confirmLabel, cancelLabel, confirmingLabel, className, onConfirm }) {
    return new Promise((resolve) => {
        const id = ++modalId;
        store.modals.push({
            id,
            kind: "confirm",
            props: { heading, body, bodyMarkup, confirmLabel, cancelLabel, confirmingLabel, className, onConfirm },
            resolve: (value) => {
                closeModal(id);
                resolve(value);
            },
        });
    });
}

/** Open a drawer rendering `Component` with `props`. Resolves with the value passed to `close`. */
export function openDrawer(Component, props = {}, { title, className, header = true, gutter = true } = {}) {
    return new Promise((resolve) => {
        const id = ++modalId;
        const depth = store.modals.filter((m) => m.kind === "drawer").length + 1;
        store.modals.push({
            id,
            kind: "drawer",
            Component,
            depth,
            title,
            className,
            header,
            gutter,
            props,
            animateIn: false,
            resolve: (value) => {
                closeModal(id);
                resolve(value);
            },
        });
        // Payload adds `drawer--is-open` one tick after mounting to trigger the slide-in.
        setTimeout(() => {
            const modal = store.modals.find((m) => m.id === id);
            if (modal) {
                modal.animateIn = true;
            }
        }, 20);
    });
}

export function closeModal(id) {
    const index = store.modals.findIndex((m) => m.id === id);
    if (index >= 0) {
        store.modals.splice(index, 1);
    }
}
