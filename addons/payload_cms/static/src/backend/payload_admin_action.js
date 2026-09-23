/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { router } from "@web/core/browser/router";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Client action embedding the Payload admin (/admin) inside the Odoo web
 * client: the Odoo navbar / apps menu stay visible, the Payload route is
 * kept in the Odoo URL (`?payload=/collections/posts/2`).
 */
export class PayloadAdminAction extends Component {
    static template = "payload_cms.PayloadAdminAction";
    static props = ["*"];

    setup() {
        this.frameRef = useRef("frame");
        this.title = useService("title");
        // `?payload=` restores the page after a reload, but only for the action that wrote it:
        // opening another menu (Collections -> Globals -> Fields...) must show that menu's page.
        const actionId = String(this.props.action?.id || "");
        const saved = router.current.payload && String(router.current.payload_action || "") === actionId ? router.current.payload : "";
        const path = saved || this.props.action?.params?.path || "";
        this.src = `/admin${path.startsWith("/") ? path : ""}`;
        this.actionId = actionId;
        this.onMessage = (ev) => {
            if (ev.origin !== window.location.origin || ev.source !== this.frameRef.el?.contentWindow) {
                return;
            }
            const data = ev.data || {};
            if (data.type === "payload-admin-route") {
                router.replaceState({ payload: data.path || undefined, payload_action: data.path ? this.actionId : undefined });
                if (data.title) {
                    this.title.setParts({ action: data.title });
                }
            }
        };
        onMounted(() => window.addEventListener("message", this.onMessage));
        onWillUnmount(() => window.removeEventListener("message", this.onMessage));
    }
}

registry.category("actions").add("payload_cms.admin", PayloadAdminAction);
