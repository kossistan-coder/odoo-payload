/** @odoo-module **/

/**
 * Minimal REST client for the Payload-compatible API exposed by Odoo on /api.
 * The admin panel uses the same public API as any headless frontend.
 */

export class ApiError extends Error {
    constructor(status, payload) {
        const first = payload?.errors?.[0];
        super(first?.message || `Request failed (${status})`);
        this.status = status;
        this.payload = payload;
        this.fieldErrors = first?.data?.errors || [];
    }
}

/** Serialize nested params with `qs` bracket syntax (where[or][0][title][like]=x). */
export function stringifyQuery(params, prefix = "") {
    const parts = [];
    for (const [key, value] of Object.entries(params || {})) {
        if (value === undefined || value === null || value === "") {
            continue;
        }
        const name = prefix ? `${prefix}[${key}]` : key;
        if (typeof value === "object") {
            parts.push(stringifyQuery(value, name));
        } else {
            parts.push(`${encodeURIComponent(name)}=${encodeURIComponent(value)}`);
        }
    }
    return parts.filter(Boolean).join("&");
}

let apiLocale = null;
let apiTenant = null;

/** Multisite: current site sent as `X-Payload-Tenant` (null = every site). */
export function setApiTenant(id) {
    apiTenant = id || null;
}

/** Locale sent with every request (`?locale=`) when localization is enabled. */
export function setApiLocale(code) {
    apiLocale = code || null;
}

/**
 * The admin edits the Lexical state of rich text fields (`richText=lexical`);
 * `rest: true` returns the plain REST output (rich text as HTML), as used by
 * the API view.
 */
export async function request(path, { method = "GET", params, body, formData, signal, rest = false } = {}) {
    const query = stringifyQuery({
        ...(rest ? {} : { richText: "lexical" }),
        ...(apiLocale ? { locale: apiLocale } : {}),
        ...params,
    });
    const url = `/api${path}${query ? `?${query}` : ""}`;
    const init = { method, credentials: "same-origin", headers: { Accept: "application/json" }, signal };
    // "" = every site (disables the resolution from the host name)
    init.headers["X-Payload-Tenant"] = apiTenant ? String(apiTenant) : "";
    if (formData) {
        init.body = formData;
    } else if (body !== undefined) {
        init.headers["Content-Type"] = "application/json";
        init.body = JSON.stringify(body);
    }
    const response = await fetch(url, init);
    let payload = null;
    const text = await response.text();
    if (text) {
        try {
            payload = JSON.parse(text);
        } catch {
            payload = { errors: [{ message: text.slice(0, 200) }] };
        }
    }
    if (!response.ok) {
        throw new ApiError(response.status, payload);
    }
    return payload;
}

export const api = {
    get: (path, params, opts) => request(path, { ...opts, params }),
    post: (path, body, params) => request(path, { method: "POST", body, params }),
    patch: (path, body, params) => request(path, { method: "PATCH", body, params }),
    delete: (path, params) => request(path, { method: "DELETE", params }),
    upload: (path, file, data, params, method = "POST") => {
        const formData = new FormData();
        if (file) {
            formData.append("file", file);
        }
        formData.append("_payload", JSON.stringify(data || {}));
        return request(path, { method, formData, params });
    },
};
