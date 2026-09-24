/** @odoo-module **/

import { fieldLabel } from "./utils";

/** Fields owning a key in the current object (row/collapsible/unnamed tabs are transparent). */
export function dataFields(fields = []) {
    const result = [];
    for (const field of fields) {
        if (field.type === "row" || field.type === "collapsible") {
            result.push(...dataFields(field.fields));
        } else if (field.type === "tabs") {
            for (const tab of field.tabs || []) {
                if (tab.name) {
                    result.push({ type: "group", name: tab.name, label: tab.label, fields: tab.fields || [], admin: {} });
                } else {
                    result.push(...dataFields(tab.fields));
                }
            }
        } else if (field.name) {
            result.push(field);
        }
    }
    return result;
}

/** Split top level fields into main / sidebar (admin.position). */
export function splitSidebar(fields = []) {
    const main = [];
    const sidebar = [];
    for (const field of fields) {
        (field.admin?.position === "sidebar" ? sidebar : main).push(field);
    }
    return { main, sidebar };
}

/** Default value tree for a new document / row. */
export function defaultValues(fields = [], data = {}) {
    for (const field of dataFields(fields)) {
        if (field.type === "group") {
            data[field.name] = defaultValues(field.fields || [], data[field.name] || {});
        } else if (data[field.name] === undefined) {
            if (field.defaultValue !== undefined) {
                data[field.name] = JSON.parse(JSON.stringify(field.defaultValue));
            } else if (field.type === "checkbox") {
                data[field.name] = false;
            } else if (field.type === "array" || field.type === "blocks") {
                data[field.name] = [];
            } else if ((field.type === "relationship" || field.type === "upload") && field.hasMany) {
                data[field.name] = [];
            }
        }
    }
    return data;
}

function isEmpty(field, value) {
    if (value === undefined || value === null || value === "") {
        return true;
    }
    if (Array.isArray(value)) {
        return value.length === 0;
    }
    if (field.type === "richText") {
        const walk = (node) =>
            node && (["upload", "relationship", "block", "horizontalrule"].includes(node.type) || (node.text || "").trim() || (node.children || []).some(walk));
        return !walk(value.root);
    }
    return false;
}

/** Client side validation (same rules as the server) -> {path: message}. */
/**
 * Declarative version of Payload's `admin.condition(data, siblingData)`:
 * `{field: "confirmationType", equals: "message"}` (also `not_equals`, `in`,
 * `exists`), evaluated against the sibling data. Returns false when the field
 * must be hidden (hidden fields are not validated either).
 */
export function checkCondition(field, siblingData) {
    const cond = field.admin?.condition;
    if (cond === false) {
        return false;
    }
    if (!cond || typeof cond !== "object" || !cond.field) {
        return true;
    }
    const value = cond.field.split(".").reduce((obj, key) => (obj && typeof obj === "object" ? obj[key] : undefined), siblingData);
    if ("equals" in cond) {
        return value === cond.equals;
    }
    if ("not_equals" in cond) {
        return value !== cond.not_equals;
    }
    if (Array.isArray(cond.in)) {
        return cond.in.includes(value);
    }
    if ("exists" in cond) {
        const exists = value !== undefined && value !== null && value !== "" && value !== false;
        return cond.exists ? exists : !exists;
    }
    return true;
}

export function validate(fields, data, path = "", errors = {}) {
    for (const field of dataFields(fields)) {
        if (!checkCondition(field, data || {})) {
            continue;
        }
        const fpath = path ? `${path}.${field.name}` : field.name;
        const value = data?.[field.name];
        if (field.required && isEmpty(field, value)) {
            errors[fpath] = "This field is required.";
            continue;
        }
 if (value === undefined || value === null || value === "") {
            continue;
        }
        if (field.pattern && typeof value === "string" && !new RegExp(`^(?:${field.pattern})$`).test(value)) {
            errors[fpath] = field.patternMessage || `"${value}" does not match the expected format.`;
            continue;
        }
        if (field.type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
            errors[fpath] = "Please enter a valid email address.";
        } else if (field.type === "number") {
            if (typeof value !== "number" || isNaN(value)) {
                errors[fpath] = `"${value}" is not a valid number.`;
            } else if (field.min !== undefined && value < field.min) {
                errors[fpath] = `"${value}" is less than the min allowed value of ${field.min}.`;
            } else if (field.max !== undefined && value > field.max) {
                errors[fpath] = `"${value}" is greater than the max allowed value of ${field.max}.`;
            }
        } else if (field.type === "group") {
            validate(field.fields || [], value, fpath, errors);
        } else if (field.type === "array" || field.type === "blocks") {
            const rows = Array.isArray(value) ? value : [];
            if (field.minRows && rows.length < field.minRows) {
                errors[fpath] = `This field requires at least ${field.minRows} ${fieldLabel(field)}.`;
            }
            if (field.maxRows && rows.length > field.maxRows) {
                errors[fpath] = `This field requires no more than ${field.maxRows} ${fieldLabel(field)}.`;
            }
            rows.forEach((row, i) => {
                const sub = field.type === "array" ? field.fields : field.blocks?.find((b) => b.slug === row.blockType)?.fields;
                validate(sub || [], row, `${fpath}.${i}`, errors);
            });
        }
    }
    return errors;
}

/** Columns available in the list view. */
export function listColumns(collection) {
    const columns = [];
    const push = (accessor, field, label) => columns.push({ accessor, field, label: label || fieldLabel(field) });
    if (collection.upload) {
        push("filename", { name: "filename", type: "upload-file" }, "Filename");
    }
    for (const field of dataFields(collection.fields)) {
        if (field.admin?.hidden || field.admin?.disableListColumn || field.type === "group") {
            continue;
        }
        push(field.name, field);
    }
    push("id", { name: "id", type: "id" }, "ID");
    if (collection.upload) {
        push("mimeType", { name: "mimeType", type: "text" }, "MIME Type");
        push("filesize", { name: "filesize", type: "filesize" }, "File Size");
    }
    if (collection.versions?.drafts) {
        push("_status", {
            name: "_status",
            type: "select",
            options: [
                { value: "draft", label: "Draft" },
                { value: "published", label: "Published" },
            ],
        }, "Status");
    }
    push("updatedAt", { name: "updatedAt", type: "date" }, "Updated At");
    push("createdAt", { name: "createdAt", type: "date" }, "Created At");
    return columns;
}

export function defaultActiveColumns(collection) {
    const all = listColumns(collection).map((c) => c.accessor);
    const configured = (collection.admin?.defaultColumns || []).filter((c) => all.includes(c));
    if (configured.length) {
        return configured;
    }
    const title = collection.admin?.useAsTitle || "id";
    const rest = all.filter((c) => c !== title && c !== "id");
    return [title, ...rest].slice(0, 4);
}

/** Operators available in the where builder, per field type (Payload's getOperators). */
const OPS = {
    equals: "operators:equals",
    not_equals: "operators:isNotEqualTo",
    in: "operators:isIn",
    not_in: "operators:isNotIn",
    exists: "operators:exists",
    greater_than: "operators:isGreaterThan",
    less_than: "operators:isLessThan",
    less_than_equal: "operators:isLessThanOrEqualTo",
    greater_than_equal: "operators:isGreaterThanOrEqualTo",
    like: "operators:isLike",
    not_like: "operators:isNotLike",
    contains: "operators:contains",
};

export function operatorsFor(type) {
    const base = ["equals", "not_equals", "in", "not_in", "exists"];
    let ops;
    switch (type) {
        case "text":
        case "textarea":
        case "code":
        case "slug":
        case "upload-file":
            ops = [...base, "like", "not_like", "contains"];
            break;
        case "email":
            ops = [...base, "contains"];
            break;
        case "number":
        case "date":
        case "id":
        case "filesize":
            ops = [...base, "greater_than", "less_than", "less_than_equal", "greater_than_equal"];
            break;
        case "checkbox":
            ops = ["equals", "not_equals", "exists"];
            break;
        case "json":
        case "richText":
        case "array":
        case "blocks":
            ops = ["exists"];
            break;
        default:
            ops = base;
    }
    return ops.map((value) => ({ value, key: OPS[value] }));
}
