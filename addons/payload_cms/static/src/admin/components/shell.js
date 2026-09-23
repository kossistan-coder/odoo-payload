/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { api, ApiError } from "../core/api";
import { t } from "../core/i18n";
import { EMBEDDED, goBack, navigate, router } from "../core/router";
import { currentLocale, dismissToast, getCollection, loadSession, localization, multitenancy, navGroups, setLocale, setTenant, store, toast } from "../core/store";
import { icon, md5 } from "../core/utils";
import { AnimateHeight, Button, FieldError, Popup, PopupButton, Select } from "./base";

/** Payload's NavGroup (collapsible, state remembered in localStorage). */
export class NavGroup extends Component {
    static template = "payload.NavGroup";
    static components = { AnimateHeight };

    setup() {
        const key = `payload-nav-group-${this.props.label}`;
        this.key = key;
        this.state = useState({ collapsed: localStorage.getItem(key) === "closed" });
        this.icon = icon;
        this.router = useState(router);
    }

    toggle() {
        this.state.collapsed = !this.state.collapsed;
        localStorage.setItem(this.key, this.state.collapsed ? "closed" : "open");
    }

    isActive(href) {
        const path = window.location.pathname;
        return path.startsWith(href) && ["/", undefined].includes(path[href.length]);
    }

    isExact(href) {
        return this.router.route && window.location.pathname === href;
    }
}

export class Nav extends Component {
    static template = "payload.Nav";
    static components = { NavGroup };

    setup() {
        this.store = useState(store);
        this.icon = icon;
        this.t = t;
        this.embedded = EMBEDDED;
    }

    get groups() {
        void this.store.config; // subscribe to config reloads (schema changes)
        return navGroups();
    }

    closeNav() {
        this.store.navOpen = false;
    }
}

export class StepNav extends Component {
    static template = "payload.StepNav";

    setup() {
        this.store = useState(store);
        this.router = useState(router);
        this.icon = icon;
    }

    /** Every page except the dashboard has a back arrow. */
    get showBack() {
        return this.router.route.name !== "dashboard";
    }

    back() {
        // fallback when the page was opened directly: the parent crumb (e.g. the list)
        const crumbs = this.store.stepNav.filter((item) => item.url);
        goBack(crumbs.length ? crumbs[crumbs.length - 1].url : "/admin");
    }
}

/** Tenant selector of the navigation (@payloadcms/plugin-multi-tenant). */
export class TenantSelector extends Component {
    static template = "payload.TenantSelector";
    static components = { Select };

    setup() {
        this.store = useState(store);
    }

    get visible() {
        void this.store.config;
        return Boolean(multitenancy());
    }

    get options() {
        const restricted = this.store.config.multitenancy.userTenants?.length;
        const sites = this.store.tenants.map((t) => ({ value: t.id, label: t.name }));
        return restricted ? sites : [{ value: "all", label: "All sites" }, ...sites];
    }

    get value() {
        return this.store.tenant || "all";
    }

    async onChange(value) {
        const id = Number(value) || null;
        if (id === this.store.tenant) {
            return;
        }
        const url = window.location.pathname + window.location.search;
        for (const guard of router.guards) {
            if (!(await guard(url))) {
                return;
            }
        }
        setTenant(id);
        // a document of another site cannot stay open: back to its list
        const route = router.route;
        if (route.name === "edit" && route.params.kind === "collection" && route.params.id && getCollection(route.params.slug)?.multiTenant) {
            await navigate(`/admin/collections/${route.params.slug}`, { force: true });
        }
    }
}

Nav.components = { NavGroup, TenantSelector };

/** Payload's Localizer: locale selector of the app header. */
export class Localizer extends Component {
    static template = "payload.Localizer";
    static components = { Popup, PopupButton };

    setup() {
        this.store = useState(store);
        this.icon = icon;
        this.t = t;
    }

    get localePrefix() {
        return `${t("general:locale")}:\u00A0`;
    }

    get locales() {
        void this.store.config;
        return localization()?.locales || [];
    }

    get current() {
        void this.store.locale;
        return currentLocale();
    }

    optionLabel(locale) {
        return locale.label && locale.label !== locale.code ? `${locale.label} (${locale.code})` : locale.code;
    }

    async select(locale, close) {
        close?.();
        if (locale.code === this.store.locale) {
            return;
        }
        // the current view is re-mounted with the new locale (see Root.viewKey):
        // unsaved changes are guarded like a navigation
        const url = window.location.pathname + window.location.search;
        for (const guard of router.guards) {
            if (!(await guard(url))) {
                return;
            }
        }
        setLocale(locale.code);
    }
}

export class AppHeader extends Component {
    static template = "payload.AppHeader";
    static components = { StepNav, Localizer };

    get localePrefix() {
        return `${t("general:locale")}:\u00A0`;
    }

    get currentLocaleLabel() {
        void this.store.locale;
        const locale = currentLocale();
        return locale ? locale.label || locale.code : "";
    }

    get hasLocalizer() {
        void this.store.config;
        return Boolean(localization());
    }

    setup() {
        this.store = useState(store);
        this.icon = icon;
        this.t = t;
    }

    get gravatar() {
        const email = this.store.user?.email;
        if (!email) {
            return null;
        }
        return `https://www.gravatar.com/avatar/${md5(email.trim().toLowerCase())}?default=mp&r=g&s=50`;
    }

    toggleNav() {
        this.store.navOpen = !this.store.navOpen;
        if (window.innerWidth > 1440) {
            localStorage.setItem("payload-nav-open", String(this.store.navOpen));
        }
    }
}

/** Payload's Default template: nav + app header + view. */
export class DefaultTemplate extends Component {
    static template = "payload.DefaultTemplate";
    static components = { Nav, AppHeader };

    setup() {
        this.store = useState(store);
        this.state = useState({ hydrated: false, animate: false });
        this.icon = icon;
        this.onResize = () => {
            if (window.innerWidth <= 1440 && this.store.navOpen && !this._manual) {
                this.store.navOpen = false;
            }
        };
        onMounted(() => {
            this.state.hydrated = true;
            setTimeout(() => (this.state.animate = true), 100);
            window.addEventListener("resize", this.onResize);
        });
        onWillUnmount(() => window.removeEventListener("resize", this.onResize));
    }

    toggleNav() {
        this._manual = true;
        this.store.navOpen = !this.store.navOpen;
        if (window.innerWidth > 1440) {
            localStorage.setItem("payload-nav-open", String(this.store.navOpen));
        }
    }
}

/** Sonner-like toaster with Payload's toast classes. */
export class Toaster extends Component {
    static template = "payload.Toaster";

    setup() {
        this.store = useState(store);
        this.state = useState({ expanded: false });
        this.icon = icon;
        this.dismiss = dismissToast;
    }

    toastStyle(index) {
        const count = this.store.toasts.length;
        const offset = this.state.expanded ? index * 60 : 0;
        return `--index:${index};--toasts-before:${index};--z-index:${count - index};--offset:${offset}px;--initial-height:52px;`;
    }
}

/** Renders confirmation modals and drawers inside `.payload__modal-container`. */
export class ModalContainer extends Component {
    static template = "payload.ModalContainer";
    static components = { Button };

    setup() {
        this.store = useState(store);
        this.state = useState({ confirming: null });
        this.icon = icon;
        this.t = t;
        this.onKeyDown = (ev) => {
            if (ev.key === "Escape" && this.store.modals.length) {
                const top = this.store.modals[this.store.modals.length - 1];
                top.resolve(top.kind === "confirm" ? false : undefined);
            }
        };
        onMounted(() => document.addEventListener("keydown", this.onKeyDown));
        onWillUnmount(() => document.removeEventListener("keydown", this.onKeyDown));
    }

    async confirm(modal) {
        if (modal.props.onConfirm) {
            this.state.confirming = modal.id;
            try {
                await modal.props.onConfirm();
            } finally {
                this.state.confirming = null;
            }
        }
        modal.resolve(true);
    }
}

export class LoginView extends Component {
    static template = "payload.LoginView";
    static components = { Button, FieldError };

    setup() {
        this.state = useState({ email: "", password: "", submitted: false, loading: false, errors: {} });
        this.icon = icon;
        this.t = t;
    }

    async onSubmit(ev) {
        ev.preventDefault();
        this.state.submitted = true;
        const errors = {};
        if (!this.state.email) {
            errors.email = t("validation:required");
        }
        if (!this.state.password) {
            errors.password = t("validation:required");
        }
        this.state.errors = errors;
        if (Object.keys(errors).length) {
            return;
        }
        this.state.loading = true;
        try {
            await api.post("/users/login", { email: this.state.email, password: this.state.password });
            await loadSession();
            const redirect = router.route.query.redirect;
            navigate(redirect && redirect.startsWith("/admin") ? redirect : "/admin", { replace: true, force: true });
        } catch (e) {
            toast.error(e instanceof ApiError ? e.message : String(e));
        } finally {
            this.state.loading = false;
        }
    }
}

export class LogoutView extends Component {
    static template = "payload.LogoutView";

    setup() {
        this.t = t;
        onMounted(async () => {
            if (EMBEDDED) {
                // Log out of Odoo itself (the admin shares the Odoo session).
                window.top.location.href = "/web/session/logout";
                return;
            }
            try {
                await api.post("/users/logout", {});
            } catch {
                // already logged out
            }
            store.user = null;
            store.config = null;
            toast.success(t("authentication:loggedOutSuccessfully"));
            navigate("/admin/login", { replace: true, force: true });
        });
    }
}
