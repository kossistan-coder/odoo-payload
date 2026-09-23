/** @odoo-module **/

import { t } from "./i18n";
import { getCollection, openDrawer } from "./store";

/**
 * Views used inside drawers (document drawer, list drawer). They are
 * registered by the view modules themselves to avoid circular imports.
 */
export const drawerViews = { EditView: null, ListView: null, RenderFields: null };

/** Payload's DocumentDrawer: create or edit a document of `slug` in a drawer. */
export function openDocumentDrawer(slug, docId, extra = {}) {
    const collection = getCollection(slug);
    return openDrawer(drawerViews.EditView, { collectionSlug: slug, docId, ...extra }, {
        header: false,
        className: "doc-drawer",
        title: docId ? t("general:editLabel", { label: collection.labels.singular }) : t("general:createNewLabel", { label: collection.labels.singular }),
    });
}

/** Payload's ListDrawer: choose an existing document. */
export function openListDrawer(slug, props = {}) {
    return openDrawer(drawerViews.ListView, { collectionSlug: slug, ...props }, { header: false, className: "list-drawer", gutter: false });
}
