/** @odoo-module **/

import { Component, onWillStart } from "@odoo/owl";
import { setStepNav, store } from "../core/store";
import { icon } from "../core/utils";

/** Swagger UI of the REST API (/api-docs), inside the Payload admin shell. */
export class ApiDocsView extends Component {
    static template = "payload.ApiDocsView";

    setup() {
        this.icon = icon;
        this.store = store;
        onWillStart(() => {
            setStepNav([{ label: "API Docs" }]);
            document.title = "API Docs - Payload";
        });
    }

    get enabled() {
        return Boolean(this.store.config?.apiDocs?.enabled);
    }
}
