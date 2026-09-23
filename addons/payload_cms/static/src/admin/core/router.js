/** @odoo-module **/

import { reactive } from "@odoo/owl";

const ADMIN = "/admin";

/**
 * Tiny history-based router. `router.route` is reactive: components reading it
 * re-render on navigation.
 */
function parse(pathname, search) {
    const path = pathname.replace(/\/+$/, "") || ADMIN;
    const rel = path.startsWith(ADMIN) ? path.slice(ADMIN.length) : path;
    const seg = rel.split("/").filter(Boolean).map(decodeURIComponent);
    const query = Object.fromEntries(new URLSearchParams(search || ""));
    const route = { name: "notFound", params: {}, query, path: pathname + (search || "") };
    if (!seg.length) {
        route.name = "dashboard";
    } else if (seg[0] === "login" && seg.length === 1) {
        route.name = "login";
    } else if (seg[0] === "logout" && seg.length === 1) {
        route.name = "logout";
    } else if (seg[0] === "account" && seg.length === 1) {
        route.name = "account";
    } else if (seg[0] === "collections" && seg.length >= 2) {
        const [, slug, id, view, versionId] = seg;
        route.params = { slug, kind: "collection" };
        if (!id) {
            route.name = "list";
        } else {
            route.params.id = id === "create" ? null : id;
            if (!view) {
                route.name = "edit";
            } else if (view === "versions" && versionId) {
                route.name = "version";
                route.params.versionId = versionId;
            } else if (view === "versions") {
                route.name = "versions";
            } else if (view === "api") {
                route.name = "apiView";
            }
        }
    } else if (seg[0] === "config" && ["localization", "multitenancy", "api-docs"].includes(seg[1]) && seg.length === 2) {
        route.name = "edit";
        route.params = { slug: `_config_${seg[1].replace("-", "_")}`, kind: "global", id: null };
    } else if (seg[0] === "api-docs" && seg.length === 1) {
        route.name = "apiDocs";
    } else if (seg[0] === "config" && seg.length >= 2 && ["collections", "globals", "fields"].includes(seg[1])) {
        const [, section, id] = seg;
        route.params = { slug: `_config_${section}`, kind: "collection" };
        if (!id) {
            route.name = "list";
        } else {
            route.name = "edit";
            route.params.id = id === "create" ? null : id;
        }
    } else if (seg[0] === "globals" && seg.length >= 2) {
        const [, slug, view, versionId] = seg;
        route.params = { slug, kind: "global", id: null };
        if (!view) {
            route.name = "edit";
        } else if (view === "versions" && versionId) {
            route.name = "version";
            route.params.versionId = versionId;
        } else if (view === "versions") {
            route.name = "versions";
        } else if (view === "api") {
            route.name = "apiView";
        }
    }
    return route;
}

/** True when the admin runs inside the Odoo web client (client action iframe). */
export const EMBEDDED = window.self !== window.top && (() => {
    try {
        return window.top.location.origin === window.location.origin;
    } catch {
        return false;
    }
})();

/** Keep the Odoo URL in sync with the Payload route when embedded. */
export function notifyParent(route) {
    if (!EMBEDDED) {
        return;
    }
    const path = route.path.replace(/^\/admin/, "").split("?")[0];
    window.parent.postMessage({ type: "payload-admin-route", path: path || "", title: document.title.replace(/ - Payload$/, "") }, window.location.origin);
}

export const router = reactive({
    route: parse(window.location.pathname, window.location.search),
    /** Guards (e.g. "leave without saving") can veto a navigation. */
    guards: new Set(),
    /** Position in the admin's own history (0 = first page opened). */
    depth: window.history.state?.payloadDepth || 0,
});

if (window.history.state?.payloadDepth === undefined) {
    window.history.replaceState({ ...(window.history.state || {}), payloadDepth: 0 }, "");
}

/**
 * Back arrow: previous page of the admin history, else the parent page
 * (`fallback`, e.g. the list of a document) or the dashboard.
 */
export function goBack(fallback) {
    if (router.depth > 0) {
        window.history.back();
        return;
    }
    navigate(fallback || ADMIN);
}

export function adminURL(path = "") {
    return `${ADMIN}${path}`;
}

export async function navigate(url, { replace = false, force = false } = {}) {
    if (!force) {
        for (const guard of router.guards) {
            if (!(await guard(url))) {
                return false;
            }
        }
    }
    const target = new URL(url, window.location.origin);
    if (replace) {
        window.history.replaceState({ payloadDepth: router.depth }, "", target.pathname + target.search);
    } else {
        router.depth += 1;
        window.history.pushState({ payloadDepth: router.depth }, "", target.pathname + target.search);
    }
    router.route = parse(target.pathname, target.search);
    window.scrollTo(0, 0);
    setTimeout(() => notifyParent(router.route), 50);
    return true;
}

/** Update the query string of the current route (list filters, pagination...). */
export function setQuery(query, { replace = true } = {}) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
        if (value !== undefined && value !== null && value !== "") {
            params.set(key, value);
        }
    }
    const search = params.toString() ? `?${params}` : "";
    const url = window.location.pathname + search;
    if (replace) {
        window.history.replaceState({}, "", url);
    } else {
        window.history.pushState({}, "", url);
    }
    router.route = parse(window.location.pathname, search);
}

window.addEventListener("popstate", (event) => {
    router.depth = event.state?.payloadDepth || 0;
    router.route = parse(window.location.pathname, window.location.search);
    setTimeout(() => notifyParent(router.route), 50);
});

/** Intercept clicks on internal <a href="/admin/..."> links. */
document.addEventListener("click", (ev) => {
    if (ev.defaultPrevented || ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) {
        return;
    }
    const link = ev.target.closest?.("a[href]");
    if (!link || link.target === "_blank" || link.hasAttribute("download")) {
        return;
    }
    const href = link.getAttribute("href");
    if (href && href.startsWith(ADMIN) && !link.dataset.external) {
        ev.preventDefault();
        navigate(href);
    }
});
