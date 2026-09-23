/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { api } from "./api";
import { getCollection } from "./store";
import { docTitle } from "./utils";

/**
 * Cache of related documents (id -> doc) shared by relationship fields, upload
 * fields and list cells (like Payload's RelationshipProvider).
 */
export const relationCache = reactive({});

function bucket(slug) {
    if (!relationCache[slug]) {
        relationCache[slug] = {};
    }
    return relationCache[slug];
}

export function cacheDoc(slug, doc) {
    if (doc && doc.id !== undefined) {
        bucket(slug)[doc.id] = doc;
    }
}

export function getCachedDoc(slug, id) {
    return relationCache[slug]?.[id];
}

export function relationLabel(slug, id) {
    const doc = getCachedDoc(slug, id);
    if (!doc) {
        return "Loading...";
    }
    return docTitle(getCollection(slug), doc) || `Untitled - ID: ${id}`;
}

const pending = {};

/** Batch-fetch documents missing from the cache. */
export async function ensureDocs(slug, ids) {
    const missing = [...new Set(ids.filter((id) => id !== null && id !== undefined && !getCachedDoc(slug, id)))];
    if (!missing.length) {
        return;
    }
    const key = `${slug}:${missing.join(",")}`;
    if (!pending[key]) {
        pending[key] = api
            .get(`/${slug}`, {
                depth: 0,
                draft: "true",
                limit: missing.length,
                pagination: "true",
                where: { id: { in: missing.join(",") } },
            })
            .then((res) => {
                for (const doc of res.docs) {
                    cacheDoc(slug, doc);
                }
                for (const id of missing) {
                    if (!getCachedDoc(slug, id)) {
                        bucket(slug)[id] = { id, __missing: true };
                    }
                }
            })
            .finally(() => delete pending[key]);
    }
    return pending[key];
}

/** Search documents of a collection for relationship selects. */
export async function searchDocs(slug, search = "", page = 1, extraWhere = null) {
    const collection = getCollection(slug);
    const titleField = collection?.admin?.useAsTitle || "id";
    const params = { depth: 0, draft: "true", limit: 10, page, sort: titleField === "id" ? "-id" : titleField };
    const clauses = [];
    if (search) {
        clauses.push(titleField === "id" ? { id: { equals: search } } : { [titleField]: { like: search } });
    }
    if (extraWhere) {
        clauses.push(extraWhere);
    }
    if (clauses.length) {
        params.where = clauses.length === 1 ? clauses[0] : { and: clauses };
    }
    const res = await api.get(`/${slug}`, params);
    for (const doc of res.docs) {
        cacheDoc(slug, doc);
    }
    return {
        options: res.docs.map((doc) => ({ value: doc.id, label: docTitle(collection, doc) || `Untitled - ID: ${doc.id}` })),
        hasNextPage: res.hasNextPage,
    };
}
