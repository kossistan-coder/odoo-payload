/** @odoo-module **/

import { markup } from "@odoo/owl";
import { ICONS } from "./icons";

/** SVG icon markup usable with t-out. */
export function icon(name, extraClass = "") {
    let svg = ICONS[name] || "";
    if (extraClass) {
        svg = svg.replace(/class="([^"]*)"/, (_m, cls) => `class="${cls} ${extraClass}"`);
    }
    return markup(svg);
}

export function classNames(...parts) {
    return parts
        .flat()
        .filter(Boolean)
        .join(" ");
}

/** Payload's ObjectID-like row ids (24 hex chars). */
export function rowId() {
    const bytes = new Uint8Array(12);
    crypto.getRandomValues(bytes);
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function deepCopy(value) {
    return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

export function isEqual(a, b) {
    return JSON.stringify(a) === JSON.stringify(b);
}

export function debounce(fn, wait) {
    let timer = null;
    const debounced = (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), wait);
    };
    debounced.cancel = () => clearTimeout(timer);
    return debounced;
}

/** Payload's default slugify (with accent transliteration for non-English titles). */
export function slugify(value) {
    if (!value || typeof value !== "string") {
        return "";
    }
    return value
        .normalize("NFKD")
        .replace(/[̀-ͯ]/g, "")
        .trim()
        .replace(/\s+/g, "-")
        .replace(/[^\w-]+/g, "")
        .replace(/-{2,}/g, "-")
        .toLowerCase();
}

/** 'heroImage' -> 'Hero Image' (Payload's toWords). */
export function toWords(name = "") {
    return String(name)
        .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
        .replace(/[_-]+/g, " ")
        .split(" ")
        .filter(Boolean)
        .map((w) => w[0].toUpperCase() + w.slice(1))
        .join(" ");
}

export function singularize(word = "") {
    if (/ies$/i.test(word)) {
        return word.replace(/ies$/i, "y");
    }
    if (/(ss|us)$/i.test(word)) {
        return word;
    }
    return word.replace(/s$/i, "");
}

export function fieldLabel(field) {
    if (field.label === false) {
        return "";
    }
    return field.label || toWords(field.name || "");
}

/** Array/blocks row labels: field.labels, else {singular: label}, else Row/Rows. */
export function rowLabels(field, fallback = { singular: "Row", plural: "Rows" }) {
    if (field.labels) {
        return field.labels;
    }
    if (field.name) {
        const plural = fieldLabel(field);
        return { singular: singularize(plural), plural };
    }
    return fallback;
}

export function formatFilesize(bytes) {
    if (!bytes && bytes !== 0) {
        return "";
    }
    if (bytes === 0) {
        return "0 bytes";
    }
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${parseFloat((bytes / 1024 ** i).toFixed(0))}${[" bytes", "KB", "MB", "GB", "TB"][i]}`;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function ordinal(n) {
    const s = ["th", "st", "nd", "rd"];
    const v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

/** date-fns 'MMMM do yyyy, h:mm a' (Payload's default admin.dateFormat). */
export function formatDate(value) {
    if (!value) {
        return "";
    }
    const d = value instanceof Date ? value : new Date(value);
    if (isNaN(d)) {
        return String(value);
    }
    let hours = d.getHours();
    const ampm = hours >= 12 ? "PM" : "AM";
    hours = hours % 12 || 12;
    const minutes = String(d.getMinutes()).padStart(2, "0");
    return `${MONTHS[d.getMonth()]} ${ordinal(d.getDate())} ${d.getFullYear()}, ${hours}:${minutes} ${ampm}`;
}

/** date-fns formatDistanceToNow (English). */
export function formatDistance(value) {
    const d = value instanceof Date ? value : new Date(value);
    const seconds = Math.abs(Date.now() - d.getTime()) / 1000;
    const minutes = Math.round(seconds / 60);
    if (seconds < 30) {
        return "less than a minute";
    }
    if (minutes < 2) {
        return "1 minute";
    }
    if (minutes < 45) {
        return `${minutes} minutes`;
    }
    const hours = Math.round(minutes / 60);
    if (minutes < 90) {
        return "about 1 hour";
    }
    if (hours < 24) {
        return `about ${hours} hours`;
    }
    const days = Math.round(hours / 24);
    if (hours < 42) {
        return "1 day";
    }
    if (days < 30) {
        return `${days} days`;
    }
    const months = Math.round(days / 30);
    if (days < 45) {
        return "about 1 month";
    }
    if (months < 12) {
        return `${months} months`;
    }
    const years = Math.round(days / 365);
    return years <= 1 ? "about 1 year" : `about ${years} years`;
}

export function getByPath(obj, path) {
    return path.split(".").reduce((acc, key) => (acc == null ? undefined : acc[key]), obj);
}

/** Plain text of a Lexical state (list cells, titles). */
export function lexicalToText(state, limit) {
    const parts = [];
    const walk = (node) => {
        if (!node || typeof node !== "object") {
            return;
        }
        if (node.type === "text") {
            parts.push(node.text || "");
        }
        (node.children || []).forEach(walk);
        if (["paragraph", "heading", "quote", "listitem"].includes(node.type)) {
            parts.push(" ");
        }
    };
    walk(state?.root);
    const text = parts.join("").replace(/\s+/g, " ").trim();
    return limit && text.length > limit ? `${text.slice(0, limit)}…` : text;
}

/** Title of a document as Payload's formatDocTitle does. */
export function docTitle(collection, doc) {
    if (!doc) {
        return "";
    }
    const field = collection?.admin?.useAsTitle || "id";
    let value = doc[field];
    if (field === "id") {
        return String(doc.id ?? "");
    }
    if (value && typeof value === "object" && value.root) {
        value = lexicalToText(value);
    }
    if (value === undefined || value === null || value === "") {
        return doc.id ? `Untitled - ID: ${doc.id}` : "";
    }
    return String(value);
}

export function isImage(mimeType) {
    return Boolean(mimeType && mimeType.startsWith("image/"));
}

/** Tiny MD5 (for Gravatar avatars, like Payload's default `avatar: 'gravatar'`). */
export function md5(input) {
    const str = unescape(encodeURIComponent(input));
    const k = [];
    for (let i = 0; i < 64; i++) {
        k[i] = Math.floor(Math.abs(Math.sin(i + 1)) * 4294967296) | 0;
    }
    const r = [7, 12, 17, 22, 5, 9, 14, 20, 4, 11, 16, 23, 6, 10, 15, 21];
    const words = [];
    for (let i = 0; i < str.length; i++) {
        words[i >> 2] |= str.charCodeAt(i) << ((i % 4) * 8);
    }
    words[str.length >> 2] |= 0x80 << ((str.length % 4) * 8);
    words[(((str.length + 8) >> 6) + 1) * 16 - 2] = str.length * 8;
    let [a0, b0, c0, d0] = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476];
    for (let i = 0; i < words.length; i += 16) {
        let [a, b, c, d] = [a0, b0, c0, d0];
        for (let j = 0; j < 64; j++) {
            let f;
            let g;
            if (j < 16) {
                f = (b & c) | (~b & d);
                g = j;
            } else if (j < 32) {
                f = (d & b) | (~d & c);
                g = (5 * j + 1) % 16;
            } else if (j < 48) {
                f = b ^ c ^ d;
                g = (3 * j + 5) % 16;
            } else {
                f = c ^ (b | ~d);
                g = (7 * j) % 16;
            }
            const tmp = d;
            d = c;
            c = b;
            const sum = (a + f + k[j] + (words[i + g] | 0)) | 0;
            const shift = r[(j >> 4) * 4 + (j % 4)];
            b = (b + ((sum << shift) | (sum >>> (32 - shift)))) | 0;
            a = tmp;
        }
        a0 = (a0 + a) | 0;
        b0 = (b0 + b) | 0;
        c0 = (c0 + c) | 0;
        d0 = (d0 + d) | 0;
    }
    return [a0, b0, c0, d0]
        .map((n) => Array.from({ length: 4 }, (_, i) => ((n >>> (i * 8)) & 255).toString(16).padStart(2, "0")).join(""))
        .join("");
}
