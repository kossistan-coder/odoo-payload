/** @odoo-module **/

import { Component, onMounted, useState, xml } from "@odoo/owl";
import { t } from "../core/i18n";
import { setStepNav, store } from "../core/store";
import { EditView } from "./edit";

/** Payload's Account view: the edit view of the logged-in user. */
export class AccountView extends Component {
    static template = xml`
        <div class="account">
            <EditView route="route"/>
            <div class="gutter gutter--left gutter--right">
                <div class="payload-settings">
                    <h3 t-esc="t('general:payloadSettings')"/>
                    <div class="payload-settings__language">
                        <label class="field-label" t-esc="t('general:language')"/>
                        <div>English</div>
                    </div>
                </div>
            </div>
        </div>`;
    static components = { EditView };

    setup() {
        this.t = t;
        this.store = useState(store);
        onMounted(() => setStepNav([{ label: t("authentication:account") }]));
    }

    get route() {
        return { name: "edit", params: { kind: "collection", slug: "users", id: this.store.user.id }, query: {}, path: "/admin/account" };
    }
}
