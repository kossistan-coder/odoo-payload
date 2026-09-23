/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { t } from "../core/i18n";
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

    get groups() {
        void this.store.config; // subscribe to config reloads (schema changes)
        return navGroups();
    }
}
