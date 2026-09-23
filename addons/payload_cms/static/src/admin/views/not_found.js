/** @odoo-module **/

import { Component, onMounted, xml } from "@odoo/owl";
import { t } from "../core/i18n";
import { setStepNav } from "../core/store";

/** Payload's NotFound view. */
export class NotFoundView extends Component {
    static template = xml`
        <div class="not-found">
            <div class="gutter gutter--left gutter--right">
                <h1 t-esc="t('general:nothingFound')"/>
                <p t-esc="t('general:sorryNotFound')"/>
                <a href="/admin" class="btn not-found__button btn--icon-style-without-border btn--size-large btn--withoutPopup btn--style-secondary btn--withoutPopup">
                    <span class="btn__content"><span class="btn__label" t-esc="t('general:backToDashboard')"/></span>
                </a>
            </div>
        </div>`;

    setup() {
        this.t = t;
        onMounted(() => setStepNav([{ label: t("general:notFound") }]));
    }
}
