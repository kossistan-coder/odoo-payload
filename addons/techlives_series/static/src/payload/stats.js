/** @odoo-module **/

// Écrans ajoutés à l'admin OdooPayload par le module (voir payload_cms/static/src/admin/core/extensions.js).

import { Component, onWillStart, useState } from "@odoo/owl";
import { callKw, registerDashboardWidget, registerView } from "@payload_cms/admin/core/extensions";
import { setStepNav } from "@payload_cms/admin/core/store";

/** /admin/x/statistiques : chiffres clés et prochains lives. */
class StatsView extends Component {
    static template = "techlives_series.StatsView";

    setup() {
        this.state = useState({ loading: true, error: null, counts: [], upcoming: [] });
        onWillStart(async () => {
            setStepNav([{ label: "Tech Lives" }, { label: "Statistiques" }]);
            try {
                const [lives, replays, speakers, participants, messages, upcoming] = await Promise.all([
                    callKw("events", "search_count", [[["active", "=", true]]]),
                    callKw("events", "search_count", [[["active", "=", true], ["episode", "!=", false]]]),
                    callKw("speakers", "search_count", [[["active", "=", true]]]),
                    callKw("participants", "search_count", [[]]),
                    callKw("messages", "search_count", [[["status", "=", "new"]]]),
                    callKw("events", "a_venir", [], { limit: 5 }),
                ]);
                this.state.counts = [
                    { label: "Lives actifs", value: lives, href: "/admin/collections/events" },
                    { label: "Replays disponibles", value: replays, href: "/admin/collections/episodes" },
                    { label: "Intervenants", value: speakers, href: "/admin/collections/speakers" },
                    { label: "Participants inscrits", value: participants, href: "/admin/collections/participants" },
                    { label: "Messages non lus", value: messages, href: "/admin/collections/messages" },
                ];
                this.state.upcoming = upcoming;
            } catch (e) {
                this.state.error = e.message;
            }
            this.state.loading = false;
        });
    }

    speakersOf(live) {
        return (live.speakers || []).map((s) => `${s.prenom} ${s.nom}`).join(", ");
    }
}

/** Tableau de bord : le prochain live. */
class NextLiveWidget extends Component {
    static template = "techlives_series.NextLiveWidget";

    setup() {
        this.state = useState({ live: null, loaded: false });
        onWillStart(async () => {
            try {
                this.state.live = (await callKw("events", "a_venir", [], { limit: 1 }))[0] || null;
            } catch {
                this.state.live = null;
            }
            this.state.loaded = true;
        });
    }
}

registerView({ path: "statistiques", label: "Statistiques", group: "Tech Lives", component: StatsView, sequence: 10 });
registerDashboardWidget({ key: "techlives-next-live", component: NextLiveWidget, sequence: 10 });
