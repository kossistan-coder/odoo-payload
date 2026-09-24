/** @odoo-module **/

import { Component, onWillStart } from "@odoo/owl";
import { t } from "../core/i18n";
import { extensions, findView } from "../core/extensions";
import { setStepNav, store } from "../core/store";

/** /admin/x/<path>: view registered by a module (core/extensions.js). */
export class ExtensionView extends Component {
    static template = "payload.ExtensionView";

    setup() {
        this.t = t;
        onWillStart(() => {
            const view = this.view;
            if (view) {
                // default breadcrumb and title; the view can call setStepNav() itself
                setStepNav([{ label: view.label }]);
                document.title = `${view.title || view.label} - Payload`;
            }
        });
    }

    get view() {
        void extensions.views.length;
        const view = findView(this.props.route.params.path);
        return view && (!view.adminOnly || store.config?.isAdmin) ? view : null;
    }

    /** Route given to the view, with the part of the URL after its path (`params.subpath`). */
    get viewRoute() {
        const route = this.props.route;
        const subpath = route.params.path.slice(this.view.path.length).replace(/^\/+/, "");
        return { ...route, params: { ...route.params, subpath } };
    }
}
