/** @odoo-module **/

import { TRANSLATIONS } from "./translations";

/**
 * Payload's `t('ns:key', {vars})` with the English strings of @payloadcms/translations.
 */
export function t(key, vars = {}) {
    const [ns, name] = key.includes(":") ? key.split(":") : ["general", key];
    let text = TRANSLATIONS[ns]?.[name];
    if (text === undefined) {
        text = name;
    }
    return String(text).replace(/{{\s*(\w+)\s*}}/g, (_m, v) => (vars[v] !== undefined ? vars[v] : ""));
}

/** Resolve a label that may be a string or a {lang: string} object. */
export function getTranslation(label) {
    if (!label) {
        return "";
    }
    if (typeof label === "object") {
        return label.en || Object.values(label)[0] || "";
    }
    return label;
}
