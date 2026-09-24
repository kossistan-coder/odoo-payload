/** @odoo-module **/

import { Component, onMounted, useState, xml } from "@odoo/owl";
import { t } from "../core/i18n";
import { setStepNav, store } from "../core/store";
import { setTheme, theme } from "../core/theme";
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
                    <div class="field-type radio-group radio-group--layout-horizontal">
                        <label class="field-label" for="field-theme" t-esc="t('general:adminTheme')"/>
                        <div class="field-type__wrap">
                            <ul class="radio-group--group" id="field-theme">
                                <li t-foreach="themeOptions" t-as="opt" t-key="opt.value">
                                    <label t-att-for="'field-theme-' + opt.value">
                                        <div t-att-class="'radio-input' + (theme.preference === opt.value ? ' radio-input--is-selected' : '')">
                                            <input type="radio" name="theme" t-att-id="'field-theme-' + opt.value" t-att-value="opt.value"
                                                   t-att-checked="theme.preference === opt.value" t-on-change="() => this.setTheme(opt.value)"/>
                                            <span class="radio-input__styled-radio"/>
                                            <span class="radio-input__label" t-esc="opt.label"/>
                                        </div>
                                    </label>
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>`;
    static components = { EditView };

    setup() {
        this.t = t;
        this.store = useState(store);
        // Payload's ToggleTheme ("Admin Theme": Automatic / Light / Dark)
        this.theme = useState(theme);
        this.setTheme = setTheme;
        this.themeOptions = [
            { value: "auto", label: t("general:automatic") },
            { value: "light", label: t("general:light") },
            { value: "dark", label: t("general:dark") },
        ];
        onMounted(() => setStepNav([{ label: t("authentication:account") }]));
    }

    get route() {
        return { name: "edit", params: { kind: "collection", slug: "users", id: this.store.user.id }, query: {}, path: "/admin/account" };
    }
}
