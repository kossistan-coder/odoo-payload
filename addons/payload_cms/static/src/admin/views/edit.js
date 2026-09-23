/** @odoo-module **/

import { Component, markup, onMounted, onWillStart, onWillUnmount, useRef, useState, useSubEnv } from "@odoo/owl";
import { api, ApiError, request } from "../core/api";
import { drawerViews } from "../core/drawers";
import { createForm } from "../core/form";
import { t } from "../core/i18n";
import { cacheDoc } from "../core/relations";
import { EMBEDDED, navigate, router } from "../core/router";
import { defaultValues, splitSidebar, validate } from "../core/schema";
import { adminBase, apiBase, confirmModal, currentLocale, currentTenant, refreshTenants, setLocale, getCollection, getGlobal, localization, openDrawer, reloadConfig, setStepNav, store, toast } from "../core/store";
import { debounce, deepCopy, docTitle, formatDate, formatDistance, formatFilesize, icon, isImage } from "../core/utils";
import { Banner, Button, Popup, PopupButton, ShimmerEffect, Thumbnail } from "../components/base";
import { RenderFields } from "../fields/fields";
import { ListView } from "./list";

const META_KEYS = new Set([
    "id", "createdAt", "updatedAt", "_status", "_hasPublishedVersion", "globalType",
    "url", "thumbnailURL", "filename", "mimeType", "filesize", "width", "height", "focalX", "focalY", "sizes",
]);

/** Payload's DocumentHeader (title + Edit / Versions / API tabs). */
export class DocumentHeader extends Component {
    static template = "payload.DocumentHeader";
}

/** Props of the DocumentHeader for a collection document or a global. */
export function documentHeaderProps({ title, titleIsId = false, docId, description, adminPath, hasVersions, versionCount, active, showTabs = true }) {
    const tabs = [{ key: "edit", label: t("general:edit"), href: adminPath, active: active === "edit" }];
    if (hasVersions) {
        tabs.push({ key: "versions", label: t("version:versions"), href: `${adminPath}/versions`, count: versionCount, active: active === "versions" });
    }
    tabs.push({ key: "api", label: "API", href: `${adminPath}/api`, active: active === "api" });
    return { title, titleIsId, docId, description, showTabs, tabs };
}

// ----------------------------------------------------------------------
// Live preview
// ----------------------------------------------------------------------
export class LivePreviewWindow extends Component {
    static template = "payload.LivePreviewWindow";
    static components = { Popup, PopupButton };

    setup() {
        this.icon = icon;
        this.t = t;
        this.iframeRef = useRef("iframe");
        this.frameRef = useRef("frame");
        const breakpoints = [...(this.props.breakpoints || []), { name: "responsive", label: "Responsive", width: "100%", height: "100%" }];
        this.breakpoints = breakpoints;
        this.zoomOptions = [50, 75, 100, 125, 150, 200];
        this.state = useState({ breakpoint: "responsive", width: 0, height: 0, zoom: 1, ready: false, loading: true, measured: { width: 0, height: 0 } });
        this.onMessage = (event) => {
            if (!this.props.url.startsWith(event.origin) && !(this.props.url.startsWith("/") && event.origin === window.location.origin)) {
                return;
            }
            if (event.data?.type === "payload-live-preview" && event.data.ready) {
                this.state.ready = true;
                this.send();
                this.post({ type: "payload-document-event" });
            }
        };
        this.resizeObserver = new ResizeObserver(() => this.measure());
        onMounted(() => {
            window.addEventListener("message", this.onMessage);
            if (this.frameRef.el) {
                this.resizeObserver.observe(this.frameRef.el);
            }
            this.props.register?.(this);
        });
        onWillUnmount(() => {
            window.removeEventListener("message", this.onMessage);
            this.resizeObserver.disconnect();
            this.props.register?.(null);
        });
    }

    get absoluteUrl() {
        return new URL(this.props.url, window.location.origin).href;
    }

    measure() {
        const el = this.frameRef.el;
        if (el) {
            this.state.measured = { width: el.offsetWidth, height: el.offsetHeight };
        }
    }

    post(message) {
        const win = this.iframeRef.el?.contentWindow;
        if (win) {
            win.postMessage(message, new URL(this.absoluteUrl).origin);
        }
    }

    /** Payload live preview protocol: send the current form values. */
    send() {
        if (!this.state.ready) {
            return;
        }
        this.post({
            type: "payload-live-preview",
            collectionSlug: this.props.collectionSlug || undefined,
            globalSlug: this.props.globalSlug || undefined,
            data: this.props.getData(),
            externallyUpdatedRelationship: null,
            locale: "en",
        });
    }

    documentEvent() {
        this.post({ type: "payload-document-event" });
    }

    get breakpointLabel() {
        const bp = this.breakpoints.find((b) => b.name === this.state.breakpoint);
        return bp ? bp.label : t("general:custom");
    }

    setBreakpoint(bp) {
        this.state.breakpoint = bp.name;
        if (bp.name !== "responsive") {
            this.state.width = Number(bp.width);
            this.state.height = Number(bp.height);
        }
    }

    setSize(axis, ev) {
        const value = Number(ev.target.value) || 0;
        const zoom = this.state.zoom;
        if (this.state.breakpoint === "responsive") {
            this.state.width = Math.round(this.state.measured.width * zoom);
            this.state.height = Math.round(this.state.measured.height * zoom);
        }
        this.state.breakpoint = "custom";
        this.state[axis] = value;
    }

    get inputWidth() {
        return this.state.breakpoint === "responsive" ? Math.round(this.state.measured.width * this.state.zoom) : this.state.width;
    }

    get inputHeight() {
        return this.state.breakpoint === "responsive" ? Math.round(this.state.measured.height * this.state.zoom) : this.state.height;
    }

    get deviceStyle() {
        const zoom = this.state.zoom;
        if (this.state.breakpoint === "responsive") {
            const size = `${100 / zoom}%`;
            return `height: ${size}; margin: 0; transform: translate3d(0, 0, 0); width: ${size};`;
        }
        return `height: ${this.state.height / zoom}px; margin: 0 auto; transform: translate3d(0, 0, 0); width: ${this.state.width / zoom}px;`;
    }

    onLoad() {
        this.state.loading = false;
    }

    get zoomPercent() {
        return Math.round(this.state.zoom * 100);
    }

    setZoom(z) {
        this.state.zoom = z / 100;
    }

    noop() {}
}

// ----------------------------------------------------------------------
// Upload: focal point & crop drawer (EditUpload)
// ----------------------------------------------------------------------
export class EditUploadDrawer extends Component {
    static template = "payload.EditUploadDrawer";
    static components = { Button };

    setup() {
        this.t = t;
        this.icon = icon;
        this.containerRef = useRef("container");
        this.state = useState({
            focalX: this.props.focalX ?? 50,
            focalY: this.props.focalY ?? 50,
            crop: { x: 0, y: 0, width: 100, height: 100, unit: "%" },
            dragging: false,
            drawing: null,
            naturalWidth: 0,
            naturalHeight: 0,
        });
    }

    onImageLoad(ev) {
        this.state.naturalWidth = ev.target.naturalWidth;
        this.state.naturalHeight = ev.target.naturalHeight;
    }

    pointToPercent(ev) {
        const rect = this.containerRef.el.getBoundingClientRect();
        return {
            x: Math.max(0, Math.min(100, ((ev.clientX - rect.left) / rect.width) * 100)),
            y: Math.max(0, Math.min(100, ((ev.clientY - rect.top) / rect.height) * 100)),
        };
    }

    onFocalMouseDown(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.state.dragging = true;
        const move = (e) => {
            const p = this.pointToPercent(e);
            this.state.focalX = Math.round(p.x * 100) / 100;
            this.state.focalY = Math.round(p.y * 100) / 100;
        };
        const up = () => {
            this.state.dragging = false;
            window.removeEventListener("mousemove", move);
            window.removeEventListener("mouseup", up);
        };
        window.addEventListener("mousemove", move);
        window.addEventListener("mouseup", up);
    }

    onCropMouseDown(ev) {
        if (!this.props.crop) {
            return;
        }
        ev.preventDefault();
        const start = this.pointToPercent(ev);
        const move = (e) => {
            const p = this.pointToPercent(e);
            const x = Math.min(start.x, p.x);
            const y = Math.min(start.y, p.y);
            const width = Math.abs(p.x - start.x);
            const height = Math.abs(p.y - start.y);
            if (width > 1 && height > 1) {
                this.state.crop = { x, y, width, height, unit: "%" };
            }
        };
        const up = () => {
            window.removeEventListener("mousemove", move);
            window.removeEventListener("mouseup", up);
        };
        window.addEventListener("mousemove", move);
        window.addEventListener("mouseup", up);
    }

    get cropPx() {
        return {
            width: Math.round((this.state.crop.width / 100) * this.state.naturalWidth),
            height: Math.round((this.state.crop.height / 100) * this.state.naturalHeight),
        };
    }

    setCropPx(axis, ev) {
        const px = Number(ev.target.value) || 0;
        const natural = axis === "width" ? this.state.naturalWidth : this.state.naturalHeight;
        if (natural) {
            this.state.crop[axis] = Math.min(100, (px / natural) * 100);
        }
    }

    resetCrop() {
        this.state.crop = { x: 0, y: 0, width: 100, height: 100, unit: "%" };
    }

    resetFocal() {
        const c = this.state.crop;
        this.state.focalX = c.x + c.width / 2;
        this.state.focalY = c.y + c.height / 2;
    }

    apply() {
        const crop = this.state.crop;
        const isFullCrop = crop.x === 0 && crop.y === 0 && crop.width === 100 && crop.height === 100;
        this.props.close({
            crop: isFullCrop ? undefined : { ...crop },
            focalPoint: { x: this.state.focalX, y: this.state.focalY },
        });
    }
}

// ----------------------------------------------------------------------
// Edit view
// ----------------------------------------------------------------------
export class EditView extends Component {
    static template = "payload.EditView";
    static components = { RenderFields, Banner, Button, Popup, PopupButton, Thumbnail, ShimmerEffect, LivePreviewWindow, DocumentHeader };

    setup() {
        this.t = t;
        this.icon = icon;
        this.formatDate = formatDate;
        this.formatFilesize = formatFilesize;
        this.fileInput = useRef("fileInput");
        this.data = useState({});
        this.state = useState({
            loading: true,
            notFound: false,
            doc: null,
            modified: false,
            processing: false,
            autosaving: false,
            lastSaved: null,
            versionCount: 0,
            livePreview: false,
            file: null,
            filePreview: null,
            filename: "",
            fileRemoved: false,
            dragging: false,
            uploadEdits: null,
            changingPassword: false,
            tick: 0,
            formKey: 0,
        });
        this.store = useState(store);
        this.form = createForm({ onChange: (path) => this.onFieldChange(path) });
        this.formState = useState(this.form.state);
        useSubEnv({ form: this.form });
        this.autosave = debounce(() => this.runAutosave(), this.autosaveInterval);
        this.previewUpdate = debounce(() => this.livePreview?.send(), 100);
        this.guard = async () => {
            if (!this.state.modified || this.autosaveEnabled) {
                return true;
            }
            return confirmModal({
                heading: t("general:leaveWithoutSaving"),
                body: t("general:changesNotSaved"),
                cancelLabel: t("general:stayOnThisPage"),
                confirmLabel: t("general:leaveAnyway"),
            });
        };
        this.onBeforeUnload = (ev) => {
            if (this.state.modified && !this.autosaveEnabled) {
                ev.preventDefault();
                ev.returnValue = "";
            }
        };
        this.onKeyDown = (ev) => {
            if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "s") {
                ev.preventDefault();
                if (this.hasDrafts) {
                    this.save("draft");
                } else {
                    this.save();
                }
            }
        };
        this.timer = setInterval(() => this.state.tick++, 30000);
        onWillStart(() => this.load());
        onMounted(() => {
            if (!this.isDrawer) {
                router.guards.add(this.guard);
                window.addEventListener("beforeunload", this.onBeforeUnload);
                window.addEventListener("keydown", this.onKeyDown);
            }
        });
        onWillUnmount(() => {
            router.guards.delete(this.guard);
            window.removeEventListener("beforeunload", this.onBeforeUnload);
            window.removeEventListener("keydown", this.onKeyDown);
            clearInterval(this.timer);
            this.autosave.cancel();
            if (this.state.filePreview) {
                URL.revokeObjectURL(this.state.filePreview);
            }
        });
    }

    // ------------------------------------------------------------------
    // Config
    // ------------------------------------------------------------------
    get isDrawer() {
        return Boolean(this.props.collectionSlug);
    }

    get params() {
        if (this.isDrawer) {
            return { kind: "collection", slug: this.props.collectionSlug, id: this.props.docId ?? null };
        }
        return this.props.route.params;
    }

    get isGlobal() {
        return this.params.kind === "global";
    }

    get config() {
        return this.isGlobal ? getGlobal(this.params.slug) : getCollection(this.params.slug);
    }

    get docId() {
        return this.state.doc?.id ?? this.params.id ?? null;
    }

    get isCreate() {
        return !this.isGlobal && !this.docId;
    }

    get hasDrafts() {
        return Boolean(this.config?.versions?.drafts);
    }

    get autosaveEnabled() {
        return Boolean(this.config?.versions?.drafts?.autosave) && !this.isCreate;
    }

    get autosaveInterval() {
        return this.config?.versions?.drafts?.autosave?.interval || 2000;
    }

    get hasVersions() {
        return Boolean(this.config?.versions?.enabled) && !this.config?.isUsers;
    }

    get apiPath() {
        if (this.isGlobal) {
            return this.config?.apiPath || `/globals/${this.params.slug}`;
        }
        return this.docId ? `${apiBase(this.config)}/${this.docId}` : apiBase(this.config);
    }

    get adminPath() {
        if (this.isGlobal) {
            return this.config?.adminPath || `/admin/globals/${this.params.slug}`;
        }
        return `${adminBase(this.config)}/${this.docId}`;
    }

    get fields() {
        const fields = [...(this.config?.fields || [])];
        if (this.config?.isUsers && (this.isCreate || this.state.changingPassword)) {
            fields.splice(1, 0, { name: "password", type: "password", label: this.isCreate ? "Password" : "New Password", required: this.isCreate, admin: {} });
        }
        return fields;
    }

    get split() {
        return splitSidebar(this.fields);
    }

    get title() {
        if (this.isGlobal) {
            return this.config.label;
        }
        const field = this.config?.admin?.useAsTitle || "id";
        if (field === "id") {
            return this.docId ? String(this.docId) : `[${t("general:untitled")}]`;
        }
        const title = docTitle(this.config, { ...this.data, id: this.docId, filename: this.state.doc?.filename });
        if (!title || title.startsWith("Untitled - ID")) {
            return this.docId ? String(this.docId) : `[${t("general:untitled")}]`;
        }
        return title;
    }

    get titleIsId() {
        return !this.isGlobal && this.docId && this.title === String(this.docId);
    }

    get status() {
        const doc = this.state.doc;
        if (!doc) {
            return "draft";
        }
        const hasPublished = doc._hasPublishedVersion || doc._status === "published";
        if (!hasPublished) {
            return "draft";
        }
        return doc._status === "draft" ? "changed" : "published";
    }

    get statusLabel() {
        return { draft: t("version:draft"), published: t("version:published"), changed: t("version:changed") }[this.status];
    }

    get previewURL() {
        if (!this.config || (!this.docId && !this.isGlobal)) {
            return null;
        }
        const tpl = this.config.admin?.previewURL;
        const slugValue = this.data.slug || "";
        if (tpl) {
            return tpl.replaceAll("{slug}", slugValue).replaceAll("{id}", this.docId ?? "").replaceAll("{collection}", this.params.slug).replaceAll("{locale}", this.store.locale || "").replaceAll("{tenant}", currentTenant()?.slug || "");
        }
        return `/cms/preview/${this.isGlobal ? "globals" : "collections"}/${this.params.slug}/${this.docId ?? "global"}${this.localeQuery}`;
    }

    get livePreviewConfig() {
        return this.config?.admin?.livePreview || null;
    }

    get livePreviewURL() {
        const lp = this.livePreviewConfig;
        if (!lp || this.isCreate) {
            return null;
        }
        if (lp.url) {
            return lp.url.replaceAll("{slug}", this.data.slug || "").replaceAll("{id}", this.docId ?? "").replaceAll("{collection}", this.params.slug).replaceAll("{locale}", this.store.locale || "").replaceAll("{tenant}", currentTenant()?.slug || "");
        }
        return `/cms/preview/${this.isGlobal ? "globals" : "collections"}/${this.params.slug}/${this.docId ?? "global"}${this.localeQuery}`;
    }

    get localeQuery() {
        return this.store.locale ? `?locale=${encodeURIComponent(this.store.locale)}` : "";
    }

    // ------------------------------------------------------------------
    // Loading
    // ------------------------------------------------------------------
    async load() {
        const config = this.config;
        if (!config) {
            this.state.notFound = true;
            this.state.loading = false;
            return;
        }
        this.state.livePreview = Boolean(this.livePreviewConfig) && localStorage.getItem(`payload-live-preview-${this.params.slug}`) === "true";
        try {
            if (this.isCreate) {
                const initial = defaultValues(config.fields, deepCopy(this.props.initialData || {}));
                if (config.multiTenant && this.store.tenant && initial.tenant == null) {
                    // multisite: new documents belong to the site selected in the navigation
                    initial.tenant = this.store.tenant;
                }
                Object.assign(this.data, initial);
                if (this.props.initialFile) {
                    this.setFile(this.props.initialFile);
                }
                if (!this.isDrawer && config.versions?.drafts?.autosave && !config.upload) {
                    // Payload creates the draft right away when autosave is enabled.
                    const res = await api.post(`/${this.params.slug}`, { ...initial, _status: "draft" }, { draft: "true", depth: 0 });
                    await navigate(`/admin/collections/${this.params.slug}/${res.doc.id}`, { replace: true, force: true });
                    return;
                }
            } else {
                const path = config.isUsers ? `/users/${this.docId}` : this.apiPath;
                // no fallback: empty localized values must stay empty in the form
                const doc = await api.get(path, { depth: 0, draft: "true", _admin: "1", ...(this.localized ? { "fallback-locale": "none" } : {}) });
                this.applyDoc(doc);
                this.loadVersionCount();
                this.autoTranslateMissing();
            }
        } catch (e) {
            if (e instanceof ApiError && e.status === 404) {
                this.state.notFound = true;
            } else {
                toast.error(e.message);
            }
        }
        this.state.loading = false;
        this.updateStepNav();
    }

    /** `remount` recreates the fields (rich text editors keep their own state). */
    applyDoc(doc, { remount = false } = {}) {
        if (remount) {
            this.state.formKey++;
        }
        this.state.doc = doc;
        for (const key of Object.keys(this.data)) {
            delete this.data[key];
        }
        const values = {};
        for (const [key, value] of Object.entries(doc || {})) {
            if (!META_KEYS.has(key)) {
                values[key] = value;
            }
        }
        Object.assign(this.data, defaultValues(this.config.fields, values));
        this.state.modified = false;
    }

    async loadVersionCount() {
        if (!this.hasVersions || this.isCreate) {
            return;
        }
        try {
            const res = this.isGlobal
                ? await api.get(`/globals/${this.params.slug}/versions`, { limit: 1 })
                : await api.get(`/${this.params.slug}/versions`, { where: { parent: { equals: this.docId } }, limit: 1 });
            this.state.versionCount = res.totalDocs;
        } catch {
            this.state.versionCount = 0;
        }
    }

    updateStepNav() {
        if (this.isDrawer || !this.config) {
            return;
        }
        if (this.isGlobal) {
            setStepNav([{ label: this.config.label }]);
            document.title = `${this.config.label} - Payload`;
            return;
        }
        const plural = this.config.labels.plural;
        setStepNav([
            { label: plural, url: adminBase(this.config) },
            { label: this.isCreate ? t("general:createNew") : this.title },
        ]);
        document.title = `${this.isCreate ? t("general:createNew") : this.title} - Payload`;
    }

    // ------------------------------------------------------------------
    // Changes
    // ------------------------------------------------------------------
    onFieldChange(path) {
        this.state.modified = true;
        if (path === (this.config?.admin?.useAsTitle || "title")) {
            this.updateStepNav();
        }
        if (this.autosaveEnabled && !this.isDrawer) {
            this.autosave();
        }
        if (this.state.livePreview) {
            this.previewUpdate();
        }
    }

    getPreviewData() {
        return { ...deepCopy(this.data), id: this.docId };
    }

    registerLivePreview(component) {
        this.livePreview = component;
    }

    toggleLivePreview() {
        this.state.livePreview = !this.state.livePreview;
        localStorage.setItem(`payload-live-preview-${this.params.slug}`, String(this.state.livePreview));
    }

    // ------------------------------------------------------------------
    // Upload
    // ------------------------------------------------------------------
    get uploadConfig() {
        return this.config?.upload || null;
    }

    get acceptTypes() {
        return (this.uploadConfig?.mimeTypes || []).join(", ");
    }

    setFile(file) {
        if (this.state.filePreview) {
            URL.revokeObjectURL(this.state.filePreview);
        }
        this.state.file = file;
        this.state.filename = file?.name || "";
        this.state.filePreview = file && isImage(file.type) ? URL.createObjectURL(file) : null;
        this.state.fileRemoved = false;
        this.state.modified = true;
    }

    onFileInput(ev) {
        const file = ev.target.files?.[0];
        if (file) {
            this.setFile(file);
        }
    }

    onDrop(ev) {
        ev.preventDefault();
        this.state.dragging = false;
        const file = ev.dataTransfer?.files?.[0];
        if (file) {
            this.setFile(file);
        }
    }

    removeFile() {
        this.setFile(null);
        this.state.fileRemoved = true;
    }

    get showFileDetails() {
        return Boolean(this.state.doc?.filename) && !this.state.fileRemoved && !this.state.file;
    }

    get fileMeta() {
        const doc = this.state.doc;
        return [formatFilesize(doc.filesize), doc.width && doc.height ? `${doc.width}x${doc.height}` : null, doc.mimeType].filter(Boolean).join(" - ");
    }

    get canEditImage() {
        const mime = this.state.doc?.mimeType || "";
        return isImage(mime) && !["image/svg+xml", "image/jxl"].includes(mime) && (this.uploadConfig?.crop !== false || this.uploadConfig?.focalPoint !== false);
    }

    async copyUrl() {
        await navigator.clipboard?.writeText(new URL(this.state.doc.url, window.location.origin).href);
        toast.success(t("general:copied"));
    }

    async editImage() {
        const doc = this.state.doc;
        const result = await openDrawer(
            EditUploadDrawer,
            {
                src: doc.url,
                filename: doc.filename,
                focalX: this.state.uploadEdits?.focalPoint?.x ?? doc.focalX,
                focalY: this.state.uploadEdits?.focalPoint?.y ?? doc.focalY,
                crop: this.uploadConfig?.crop !== false,
                focalPoint: this.uploadConfig?.focalPoint !== false,
            },
            { header: false, className: "edit-upload" }
        );
        if (result) {
            this.state.uploadEdits = result;
            this.state.modified = true;
        }
    }

    // ------------------------------------------------------------------
    // Save
    // ------------------------------------------------------------------
    body(status) {
        const body = deepCopy(this.data);
        if (this.hasDrafts && status) {
            body._status = status;
        }
        if (this.state.uploadEdits) {
            body.uploadEdits = this.state.uploadEdits;
        }
        if (this.config.isUsers && !body.password) {
            delete body.password;
        }
        return body;
    }

    async send(body, params) {
        const config = this.config;
        const method = this.isGlobal ? "POST" : this.isCreate ? "POST" : "PATCH";
        const path = config.isUsers ? (this.isCreate ? "/users" : `/users/${this.docId}`) : this.apiPath;
        if (config.upload && this.state.file) {
            const file = this.state.filename && this.state.filename !== this.state.file.name ? new File([this.state.file], this.state.filename, { type: this.state.file.type }) : this.state.file;
            return api.upload(path, file, body, params, method);
        }
        return request(path, { method, body, params });
    }

    async save(status) {
        if (this.state.processing) {
            return;
        }
        const config = this.config;
        const isDraft = this.hasDrafts && status === "draft";
        if (!isDraft) {
            const errors = validate(this.fields, this.data);
            if (config.upload && this.isCreate && !this.state.file) {
                errors.file = t("upload:selectFile");
            }
            this.form.state.submitted = true;
            this.form.state.errors = errors;
            this.form.state.serverErrors = false;
            if (Object.keys(errors).length) {
                const paths = Object.keys(errors);
                toast.error(paths.length === 1 ? `The following field is invalid: ${paths[0]}` : `The following fields are invalid: ${paths.join(", ")}`);
                return;
            }
        }
        this.autosave.cancel();
        this.state.processing = true;
        const wasCreate = this.isCreate;
        try {
            const params = { depth: 0, _admin: "1" };
            if (isDraft) {
                params.draft = "true";
            }
            const res = await this.send(this.body(this.hasDrafts ? status || "published" : undefined), params);
            const doc = res.doc || res.result || res;
            toast.success(res.message || t("general:updatedSuccessfully"));
            this.form.state.errors = {};
            this.form.state.serverErrors = false;
            this.state.uploadEdits = null;
            if (this.state.file) {
                this.setFile(null);
            }
            this.state.fileRemoved = false;
            cacheDoc(this.params.slug, doc);
            if (this.config.virtual) {
                await reloadConfig();
            } else if (this.params.slug === "tenants") {
                // the site selector shows the site names
                await refreshTenants();
            }
            if (this.isDrawer) {
                if (wasCreate) {
                    this.props.close?.(doc);
                    return;
                }
                this.applyDoc(doc);
                this.state.lastSaved = new Date();
                return;
            }
            this.applyDoc(doc);
            this.state.lastSaved = new Date();
            this.state.versionCount += this.hasVersions ? 1 : 0;
            this.livePreview?.documentEvent();
            if (wasCreate) {
                await navigate(`${adminBase(this.config)}/${doc.id}`, { replace: true, force: true });
            } else {
                this.updateStepNav();
            }
        } catch (e) {
            this.handleError(e);
        } finally {
            this.state.processing = false;
        }
    }

    handleError(e) {
        if (e instanceof ApiError && e.fieldErrors?.length) {
            const errors = {};
            for (const err of e.fieldErrors) {
                errors[err.path] = err.message;
            }
            this.form.state.errors = errors;
            this.form.state.serverErrors = true;
        }
        toast.error(e.message);
    }

    async runAutosave() {
        if (!this.state.modified || this.state.processing || this.isCreate) {
            return;
        }
        this.state.autosaving = true;
        const started = Date.now();
        try {
            const res = await this.send(this.body("draft"), { depth: 0, draft: "true", autosave: "true", _admin: "1" });
            const doc = res.doc || res.result || res;
            this.state.doc = { ...this.state.doc, ...doc, _hasPublishedVersion: doc._hasPublishedVersion ?? this.state.doc?._hasPublishedVersion };
            this.state.modified = false;
            this.state.lastSaved = new Date();
            this.livePreview?.documentEvent();
            if (!this._autosavedOnce) {
                this._autosavedOnce = true;
                this.loadVersionCount();
            }
        } catch (e) {
            this.handleError(e);
        } finally {
            const elapsed = Date.now() - started;
            setTimeout(() => (this.state.autosaving = false), Math.max(0, 1000 - elapsed));
        }
    }

    get autosaveText() {
        void this.state.tick;
        if (this.state.autosaving) {
            return t("general:saving");
        }
        const last = this.state.lastSaved || (this.state.doc?.updatedAt ? new Date(this.state.doc.updatedAt) : null);
        return last ? t("version:lastSavedAgo", { distance: formatDistance(last) }) : "";
    }

    get canPublish() {
        return this.state.modified || this.status !== "published" || this.isCreate;
    }

    // ------------------------------------------------------------------
    // "..." menu actions
    // ------------------------------------------------------------------
    async duplicate() {
        const run = async () => {
            try {
                const res = await api.post(`/${this.params.slug}/${this.docId}/duplicate`, {}, { depth: 0 });
                toast.success(t("general:successfullyDuplicated", { label: this.config.labels.singular }));
                this.state.modified = false;
                await navigate(`/admin/collections/${this.params.slug}/${res.doc.id}`, { force: true });
            } catch (e) {
                toast.error(e.message);
            }
        };
        if (this.state.modified) {
            const ok = await confirmModal({
                heading: t("general:unsavedChanges"),
                body: t("general:unsavedChangesDuplicate"),
                confirmLabel: t("general:duplicateWithoutSaving"),
            });
            if (!ok) {
                return;
            }
        }
        await run();
    }

    async remove() {
        const label = this.config.labels.singular;
        const title = this.title;
        const ok = await confirmModal({
            heading: t("general:confirmDeletion"),
            bodyMarkup: markupBody(t("general:aboutToDelete", { label, title: "\u0000" }), title),
            className: "delete-document",
            confirmingLabel: t("general:deleting"),
            onConfirm: async () => {
                try {
                    await api.delete(this.config.isUsers ? `/users/${this.docId}` : `${apiBase(this.config)}/${this.docId}`);
                    toast.success(t("general:titleDeleted", { label, title }));
                    if (this.params.slug === "tenants") {
                        await refreshTenants();
                    }
                } catch (e) {
                    toast.error(e.message);
                    throw e;
                }
            },
        }).catch(() => false);
        if (ok) {
            this.state.modified = false;
            if (this.config.virtual) {
                await reloadConfig();
            }
            if (this.isDrawer) {
                this.props.close?.();
            } else {
                navigate(adminBase(this.config), { force: true });
            }
        }
    }

    async unpublish() {
        const ok = await confirmModal({
            heading: t("version:confirmUnpublish"),
            body: t("version:aboutToUnpublish"),
            confirmingLabel: t("version:unpublishing"),
            onConfirm: async () => {
                const method = this.isGlobal ? "POST" : "PATCH";
                const res = await request(this.apiPath, { method, body: { _status: "draft" }, params: { depth: 0, _admin: "1" } });
                const doc = res.doc || res.result;
                this.state.doc = { ...this.state.doc, ...doc, _status: "draft", _hasPublishedVersion: false };
                toast.success(t("version:unpublishedSuccessfully"));
                this.loadVersionCount();
            },
        });
        return ok;
    }

    async revertToPublished() {
        const ok = await confirmModal({
            heading: t("version:confirmRevertToSaved"),
            body: t("version:aboutToRevertToPublished"),
            confirmingLabel: t("version:reverting"),
            onConfirm: async () => {
                const published = await api.get(this.apiPath, { depth: 0 });
                const data = {};
                for (const [k, v] of Object.entries(published)) {
                    if (!META_KEYS.has(k)) {
                        data[k] = v;
                    }
                }
                const method = this.isGlobal ? "POST" : "PATCH";
                const res = await request(this.apiPath, { method, body: { ...data, _status: "published" }, params: { depth: 0, _admin: "1" } });
                this.applyDoc(res.doc || res.result, { remount: true });
                toast.success(res.message);
                this.loadVersionCount();
            },
        });
        return ok;
    }

    // ------------------------------------------------------------------
    // Localization / machine translation
    // ------------------------------------------------------------------
    /** Localization is enabled and the document has localized fields. */
    get localized() {
        return Boolean(localization()) && !this.config?.virtual && !this.config?.isUsers && hasLocalizedFields(this.config?.fields || []);
    }

    get canTranslate() {
        const conf = localization();
        return this.localized && !this.isCreate && conf.translate?.enabled && this.store.locale !== conf.defaultLocale;
    }

    get defaultLocaleLabel() {
        const conf = localization();
        return conf?.locales.find((l) => l.code === conf.defaultLocale)?.label || conf?.defaultLocale;
    }

    /** Explains why switching the locale changes nothing / how to translate. */
    get localeHint() {
        const conf = localization();
        if (!conf || this.config?.virtual || this.config?.isUsers || this.isDrawer) {
            return "";
        }
        if (!hasLocalizedFields(this.config?.fields || [])) {
            return "No field of this collection is localized: the content is the same in every locale. Select it in Configuration → Localization → Translated collections, or check \"Localized\" on its fields.";
        }
        if (this.store.locale !== conf.defaultLocale && !conf.translate?.enabled) {
            return `You are editing the ${currentLocale()?.label} version. Empty fields fall back to ${this.defaultLocaleLabel} on the API. Choose a translation service in Configuration → Localization (MyMemory needs no key) to translate automatically.`;
        }
        if (this.store.locale !== conf.defaultLocale && conf.translate?.autoTranslate === "off" && !this.isCreate) {
            return `You are editing the ${currentLocale()?.label} version. Use ⋯ → "Translate from ${this.defaultLocaleLabel}" to translate this document automatically.`;
        }
        return "";
    }

    /** `autoTranslate` enabled: opening a document in another locale fills its missing translations. */
    async autoTranslateMissing() {
        const conf = localization();
        if (!this.localized || this.isCreate || !conf.translate?.enabled || conf.translate.autoTranslate === "off" || this.store.locale === conf.defaultLocale) {
            return;
        }
        try {
            const res = await api.post(`${this.apiPath}/translate`, { from: conf.defaultLocale, to: this.store.locale, overwrite: false }, { depth: 0 });
            if (res.translated) {
                const doc = await api.get(this.apiPath, { depth: 0, draft: "true", _admin: "1", "fallback-locale": "none" });
                this.applyDoc(doc, { remount: true });
                toast.success(`Missing ${currentLocale()?.label} translations were filled automatically from ${this.defaultLocaleLabel}.`);
            }
        } catch (e) {
            toast.error(e.message);
        }
    }

    /** Native Odoo form of the document (chatter, activities, followers...). */
    get odooURL() {
        const id = this.state.doc?.id;
        if (!id || this.config?.virtual || this.config?.isUsers || this.isDrawer) {
            return null;
        }
        return `/odoo/action-payload_cms.action_cms_documents_odoo/${id}`;
    }

    openInOdoo() {
        // embedded in the Odoo web client: open the form in the top window, not in the iframe
        (EMBEDDED ? window.top : window).location.href = this.odooURL;
    }

    get currentLocaleLabel() {
        const locale = currentLocale();
        return locale?.label || locale?.code || "";
    }

    get translateReady() {
        return Boolean(localization()?.translate?.enabled);
    }

    /** Every locale except the one being edited. */
    get translateTargets() {
        return (localization()?.locales || []).filter((l) => l.code !== this.store.locale);
    }

    /** "Translate to…" button: machine translation of the current locale into `targets`. */
    async translateTo(targets, close) {
        close?.();
        if (this.state.modified) {
            toast.warning("Save your changes before translating.");
            return;
        }
        const from = currentLocale();
        const labels = this.translateTargets.filter((l) => targets.includes(l.code)).map((l) => l.label || l.code);
        const ok = await confirmModal({
            heading: "Translate",
            body: `The localized fields in ${labels.join(", ")} will be replaced by an automatic translation of the ${from.label || from.code} content.`,
            confirmLabel: "Translate",
            confirmingLabel: "Translating…",
            onConfirm: async () => {
                try {
                    const res = await api.post(`${this.apiPath}/translate`, { from: from.code, to: targets, overwrite: true }, { depth: 0 });
                    toast.success(res.message);
                } catch (e) {
                    toast.error(e.message);
                    throw e;
                }
            },
        }).catch(() => false);
        if (ok && targets.length === 1) {
            // show the result: the view re-mounts in the target locale
            setLocale(targets[0]);
        } else if (ok) {
            this.loadVersionCount();
        }
    }

    async translate() {
        const conf = localization();
        const target = currentLocale();
        const ok = await confirmModal({
            heading: "Translate",
            body: `The localized fields in ${target.label} will be replaced by an automatic translation (Google Translate) of the ${this.defaultLocaleLabel} content. Unsaved changes will be lost.`,
            confirmLabel: "Translate",
            confirmingLabel: "Translating…",
            onConfirm: async () => {
                try {
                    const res = await api.post(`${this.apiPath}/translate`, { from: conf.defaultLocale, to: target.code, overwrite: true }, { depth: 0 });
                    const doc = await api.get(this.apiPath, { depth: 0, draft: "true", _admin: "1", "fallback-locale": "none" });
                    this.applyDoc(doc, { remount: true });
                    toast.success(res.message);
                    this.loadVersionCount();
                } catch (e) {
                    toast.error(e.message);
                }
            },
        });
        return ok;
    }

    get createURL() {
        return `${adminBase(this.config)}/create`;
    }

    get headerProps() {
        return documentHeaderProps({
            title: this.title,
            titleIsId: this.titleIsId,
            docId: this.docId,
            description: this.config.admin?.description,
            adminPath: this.adminPath,
            hasVersions: this.hasVersions,
            versionCount: this.state.versionCount,
            active: "edit",
            showTabs: !this.isCreate && !this.config.isUsers && !this.config.virtual,
        });
    }
}

function markupBody(template, title) {
    const escape = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
    const [before, after] = template.replace(/<\/?1>/g, "").split("\u0000");
    return markup(`${escape(before)}<strong>${escape(title)}</strong>${escape(after || "")}`);
}

drawerViews.EditView = EditView;
drawerViews.ListView = ListView;

function hasLocalizedFields(fields) {
    return fields.some((f) => f.localized || hasLocalizedFields(f.fields || []) || (f.tabs || []).some((tab) => hasLocalizedFields(tab.fields || [])) || (f.blocks || []).some((b) => hasLocalizedFields(b.fields || [])));
}
