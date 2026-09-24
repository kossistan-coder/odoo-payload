/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { t } from "../core/i18n";
import { extensions } from "../core/extensions";
import { navGroups, setStepNav, store } from "../core/store";
import { icon } from "../core/utils";

/** Payload's default dashboard: the "collections" widget with grouped cards. */
export class DashboardView extends Component {
    static template = "payload.DashboardView";

    setup() {
        this.store = useState(store);
        this.icon = icon;
        this.t = t;
        onWillStart(() => {
            setStepNav([{ label: t("general:dashboard") }]);
            document.title = "Dashboard - Payload";
        });
    }

    /** Widgets registered by the modules (core/extensions.js), above the collections. */
    get widgets() {
        return extensions.widgets.filter((w) => !w.adminOnly || this.store.config?.isAdmin);
    }

    widgetStyle(widget) {
        const width = { half: "50%", third: "33.333%" }[widget.width] || "100%";
        return `width: ${width}; padding: 6px; position: relative`;
    }

    get groups() {
        void this.store.config; // subscribe to config reloads (schema changes)
        return navGroups();
    }
}
