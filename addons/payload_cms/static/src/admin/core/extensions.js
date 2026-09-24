/** @odoo-module **/

// Extension points of the admin, for the modules using payload_cms.
//
// A module adds its files to the admin bundle in its manifest:
//
//     'assets': {'payload_cms.assets_admin': ['my_module/static/src/payload/**/*']},
//
// and registers its screens from a JS module of that folder:
//
//     import { registerView, registerDashboardWidget, registerField, callKw } from "@payload_cms/admin/core/extensions";
//
//     registerView({ path: "stats", label: "Statistiques", group: "Tech Lives", component: StatsView });
//     registerDashboardWidget({ key: "next-live", component: NextLiveWidget, width: "half" });
//     registerField("color", ColorField);   // fields declared with component="color"
//
// Views are shown on /admin/x/<path> (Odoo menu: client action payload_cms.admin
// with params {'path': '/x/<path>'}), listed in the navigation and on the dashboard.

import { reactive } from "@odoo/owl";

export const extensions = reactive({ views: [], widgets: [], fields: {} });

/**
 * Adds a screen to the admin.
 *
 * @param {Object} view
 * @param {string} view.path        URL of the view: /admin/x/<path> (letters, digits, - _ /)
 * @param {string} view.label       label in the navigation and on the dashboard card
 * @param {Function} view.component OWL component; props: `route` (with `route.params.subpath`
 *                                  for /admin/x/<path>/<more>, and `route.query`)
 * @param {string} [view.group]     navigation group (default "Views")
 * @param {number} [view.sequence]  order inside the group (default 100)
 * @param {boolean} [view.adminOnly] only for the CMS administrators
 * @param {boolean} [view.nav]      listed in the navigation / dashboard (default true)
 * @param {string} [view.title]     document title (default: label)
 */
export function registerView(view) {
    if (!view?.path || !view.component) {
        throw new Error("registerView(): `path` and `component` are required");
    }
    const path = view.path.replace(/^\/+|\/+$/g, "");
    if (!/^[A-Za-z0-9_\-/]+$/.test(path)) {
        throw new Error(`registerView(): invalid path "${view.path}"`);
    }
    const entry = { group: "Views", sequence: 100, adminOnly: false, nav: true, ...view, path, label: view.label || path };
    const index = extensions.views.findIndex((v) => v.path === path);
    if (index >= 0) {
        extensions.views.splice(index, 1, entry);
    } else {
        extensions.views.push(entry);
    }
    extensions.views.sort((a, b) => a.sequence - b.sequence);
}

/**
 * Adds a widget to the dashboard, above the collections.
 *
 * @param {Object} widget
 * @param {string} widget.key        unique key
 * @param {Function} widget.component OWL component (no props)
 * @param {string} [widget.width]    "full" (default), "half" or "third"
 * @param {number} [widget.sequence] order (default 100)
 * @param {boolean} [widget.adminOnly]
 */
export function registerDashboardWidget(widget) {
    if (!widget?.key || !widget.component) {
        throw new Error("registerDashboardWidget(): `key` and `component` are required");
    }
    const entry = { width: "full", sequence: 100, adminOnly: false, ...widget };
    const index = extensions.widgets.findIndex((w) => w.key === widget.key);
    if (index >= 0) {
        extensions.widgets.splice(index, 1, entry);
    } else {
        extensions.widgets.push(entry);
    }
    extensions.widgets.sort((a, b) => a.sequence - b.sequence);
}

/**
 * Replaces the input of the fields declared with ``component="<name>"`` (Python)
 * or ``admin.component`` (field config). The component should extend
 * ``FieldBase`` (``@payload_cms/admin/fields/field_base``): ``this.value`` /
 * ``this.setValue(v)``, ``this.field``, ``this.readOnly``...
 */
export function registerField(name, component) {
    extensions.fields[name] = component;
}

/** View registered for /admin/x/<path>[/<subpath>] (longest matching path). */
export function findView(fullPath) {
    const clean = (fullPath || "").replace(/^\/+|\/+$/g, "");
    let match = null;
    for (const view of extensions.views) {
        if ((clean === view.path || clean.startsWith(view.path + "/")) && (!match || view.path.length > match.path.length)) {
            match = view;
        }
    }
    return match;
}

/**
 * Calls a method of a collection through JSON-RPC (/payload/dataset/call_kw),
 * like ``orm.call`` in the Odoo web client: the Odoo-like API of
 * ``payload_cms.payload.Model`` (search_read, web_search_read, create, write, @expose methods...).
 *
 *     const lives = await callKw("events", "search_read", [[["active", "=", true]]], { fields: ["designation"], limit: 5 });
 */
export async function callKw(model, method, args = [], kwargs = {}) {
    const response = await fetch("/payload/dataset/call_kw", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: { model, method, args, kwargs } }),
    });
    const res = await response.json();
    if (res.error) {
        throw new Error(res.error.data?.message || res.error.message);
    }
    return res.result;
}
