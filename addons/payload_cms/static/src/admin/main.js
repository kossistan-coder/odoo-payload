/** @odoo-module **/

import { App, Component, onWillStart, useState, whenReady } from "@odoo/owl";
import { getTemplate } from "@web/core/templates";
import { EMBEDDED, navigate, notifyParent, router } from "./core/router";
import { loadSession, store } from "./core/store";
import { DefaultTemplate, LoginView, LogoutView, ModalContainer, Toaster } from "./components/shell";
import { DashboardView } from "./views/dashboard";
import { ListView } from "./views/list";
import { EditView } from "./views/edit";
import { VersionsView, VersionView } from "./views/versions";
import { ApiView } from "./views/api_view";
import { AccountView } from "./views/account";
import { NotFoundView } from "./views/not_found";
import { ApiDocsView } from "./views/api_docs";
import { ExtensionView } from "./views/extension";

const VIEWS = {
    dashboard: DashboardView,
    list: ListView,
    edit: EditView,
    versions: VersionsView,
    version: VersionView,
    apiView: ApiView,
    account: AccountView,
    notFound: NotFoundView,
    apiDocs: ApiDocsView,
    extension: ExtensionView,
};

class Root extends Component {
    static template = "payload.Root";
    static components = { DefaultTemplate, LoginView, LogoutView, ModalContainer, Toaster };

    setup() {
        this.store = useState(store);
        this.router = useState(router);
        onWillStart(async () => {
            await loadSession();
            this.guard();
        });
    }

    guard() {
        const name = router.route.name;
        if (EMBEDDED && !store.user) {
            // Inside Odoo: the Odoo session is the source of truth.
            window.top.location.href = `/web/login?redirect=${encodeURIComponent(window.top.location.pathname + window.top.location.search)}`;
            return;
        }
        if (!store.user && !["login", "logout"].includes(name)) {
            const redirect = encodeURIComponent(window.location.pathname + window.location.search);
            navigate(`/admin/login?redirect=${redirect}`, { replace: true, force: true });
        } else if (store.user && name === "login") {
            navigate("/admin", { replace: true, force: true });
        }
    }

    get route() {
        return this.router.route;
    }

    get View() {
        return VIEWS[this.route.name] || NotFoundView;
    }

    /** Remount views when the document (not only the tab) changes. */
    get viewKey() {
        const { name, params } = this.route;
        return `${name}:${params.path || ""}:${params.kind || ""}:${params.slug || ""}:${params.id ?? "new"}:${params.versionId || ""}:${this.store?.locale || ""}:${this.store?.tenant || ""}`;
    }

    get templateClass() {
        const { name, params } = this.route;
        if (name === "dashboard") {
            return "dashboard";
        }
        if (name === "list") {
            return `${params.slug}-list`;
        }
        if (name === "extension") {
            return `extension-view extension-view--${(params.path || "").split("/")[0]}`;
        }
        if (name === "apiDocs") {
            return "api-docs-view";
        }
        if (params.kind === "global") {
            return "global-edit";
        }
        return "collection-default-edit";
    }
}

whenReady(async () => {
    if (EMBEDDED) {
        document.documentElement.classList.add("payload-embedded");
    }
    const app = new App(Root, {
        getTemplate,
        dev: new URLSearchParams(window.location.search).has("debug"),
        warnIfNoStaticProps: false,
        translatableAttributes: [],
    });
    await app.mount(document.getElementById("app"));
    setTimeout(() => notifyParent(router.route), 300);
});

export { router };
