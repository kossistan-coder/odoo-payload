/*
 * Built-in frontend used by "Preview" and "Live Preview" when no external URL
 * is configured. It speaks the same protocol as @payloadcms/live-preview:
 *   - posts {type: 'payload-live-preview', ready: true} to the admin window,
 *   - receives {type: 'payload-live-preview', data} on every form change,
 *   - merges the data through POST /api/... + X-Payload-HTTP-Method-Override: GET
 *     to populate relationships and uploads.
 * It is plain JS (no build step) so it can be copied as a starting point.
 */
(function () {
    "use strict";

    const LOCALE = new URLSearchParams(window.location.search).get("locale");
    const LOCALE_QUERY = LOCALE ? `&locale=${encodeURIComponent(LOCALE)}` : "";

    const config = window.__PREVIEW_CONFIG__;
    const root = document.getElementById("preview-root");
    const isGlobal = config.kind === "globals";
    const apiPath = isGlobal ? `/api/globals/${config.slug}` : `/api/${config.slug}/${config.id}`;
    const DEPTH = 2;
    let header = null;

    const esc = (s) =>
        String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

    // ------------------------------------------------------------------
    // Lexical JSON -> HTML (same output as @payloadcms/richtext-lexical/html)
    // ------------------------------------------------------------------
    const FORMAT = { bold: 1, italic: 2, strikethrough: 4, underline: 8, code: 16, subscript: 32, superscript: 64 };

    function textHTML(node) {
        let html = esc(node.text);
        const f = node.format || 0;
        if (f & FORMAT.bold) html = `<strong>${html}</strong>`;
        if (f & FORMAT.italic) html = `<em>${html}</em>`;
        if (f & FORMAT.strikethrough) html = `<span style="text-decoration: line-through">${html}</span>`;
        if (f & FORMAT.underline) html = `<span style="text-decoration: underline">${html}</span>`;
        if (f & FORMAT.code) html = `<code>${html}</code>`;
        if (f & FORMAT.subscript) html = `<sub>${html}</sub>`;
        if (f & FORMAT.superscript) html = `<sup>${html}</sup>`;
        return html;
    }

    function nodesHTML(nodes) {
        return (nodes || []).map(nodeHTML).join("");
    }

    function style(node) {
        const parts = [];
        if (node.format && typeof node.format === "string") parts.push(`text-align: ${node.format}`);
        if (node.indent) parts.push(`padding-inline-start: ${node.indent * 40}px`);
        return parts.length ? ` style="${parts.join(";")}"` : "";
    }

    function nodeHTML(node) {
        switch (node.type) {
            case "text":
                return textHTML(node);
            case "linebreak":
                return "<br>";
            case "tab":
                return "\t";
            case "paragraph":
                return `<p${style(node)}>${nodesHTML(node.children) || "<br>"}</p>`;
            case "heading":
                return `<${node.tag}${style(node)}>${nodesHTML(node.children)}</${node.tag}>`;
            case "quote":
                return `<blockquote${style(node)}>${nodesHTML(node.children)}</blockquote>`;
            case "list": {
                const tag = node.listType === "number" ? "ol" : "ul";
                const cls = node.listType === "check" ? ' class="checklist"' : "";
                return `<${tag}${cls}>${nodesHTML(node.children)}</${tag}>`;
            }
            case "listitem": {
                const check = node.checked !== undefined ? `<input type="checkbox" disabled ${node.checked ? "checked" : ""}> ` : "";
                return `<li>${check}${nodesHTML(node.children)}</li>`;
            }
            case "link":
            case "autolink": {
                const f = node.fields || {};
                let href = f.url || "#";
                if (f.linkType === "internal" && f.doc) {
                    const doc = typeof f.doc.value === "object" ? f.doc.value : null;
                    href = doc?.slug ? `/${doc.slug}` : "#";
                }
                const target = f.newTab ? ' target="_blank" rel="noopener noreferrer"' : "";
                return `<a href="${esc(href)}"${target}>${nodesHTML(node.children)}</a>`;
            }
            case "horizontalrule":
                return "<hr>";
            case "upload": {
                const doc = typeof node.value === "object" ? node.value : null;
                if (!doc?.url) return "";
                if (doc.mimeType?.startsWith("image/")) {
                    return `<figure><img src="${esc(doc.sizes?.large?.url || doc.url)}" alt="${esc(doc.alt || doc.filename)}"></figure>`;
                }
                return `<p><a href="${esc(doc.url)}">${esc(doc.filename)}</a></p>`;
            }
            case "relationship": {
                const doc = typeof node.value === "object" ? node.value : null;
                return `<div class="relationship-card">${esc(doc?.title || doc?.filename || `${node.relationTo} #${node.value}`)}</div>`;
            }
            default:
                return nodesHTML(node.children);
        }
    }

    // The REST API returns rich text as HTML; Lexical JSON is still accepted.
    function richText(state) {
        if (typeof state === "string") {
            return state;
        }
        return state?.root ? nodesHTML(state.root.children) : "";
    }

    // ------------------------------------------------------------------
    // Page rendering (generic, driven by the collection's field config)
    // ------------------------------------------------------------------
    function media(doc, size = "large") {
        if (!doc || typeof doc !== "object" || !doc.url) return "";
        if (!doc.mimeType?.startsWith("image/")) return `<a href="${esc(doc.url)}">${esc(doc.filename)}</a>`;
        return `<img src="${esc(doc.sizes?.[size]?.url || doc.url)}" alt="${esc(doc.alt || "")}" style="object-position: ${doc.focalX ?? 50}% ${doc.focalY ?? 50}%">`;
    }

    function links(items) {
        if (!Array.isArray(items) || !items.length) return "";
        return `<div class="links">${items.map((l) => `<a class="button" href="${esc(l.url || "#")}"${l.newTab ? ' target="_blank"' : ""}>${esc(l.label)}</a>`).join("")}</div>`;
    }

    function block(row) {
        switch (row.blockType) {
            case "content":
                return `<section class="block block-content">${richText(row.richText)}</section>`;
            case "mediaBlock":
                return `<section class="block block-media">${media(row.media)}</section>`;
            case "cta":
                return `<section class="block block-cta"><div>${richText(row.richText)}</div>${links(row.links)}</section>`;
            case "archive":
                return `<section class="block block-archive">${richText(row.introContent)}<div class="archive" data-limit="${row.limit || 10}"></div></section>`;
            default:
                return `<section class="block"><pre>${esc(JSON.stringify(row, null, 2))}</pre></section>`;
        }
    }

    function flatten(fields) {
        const out = [];
        for (const f of fields || []) {
            if (f.type === "row" || f.type === "collapsible") out.push(...flatten(f.fields));
            else if (f.type === "tabs") for (const tab of f.tabs || []) {
                if (tab.name) out.push({ ...tab, type: "group" });
                else out.push(...flatten(tab.fields));
            }
            else out.push(f);
        }
        return out;
    }

    function fieldsHTML(fields, data) {
        let html = "";
        for (const field of flatten(fields)) {
            const value = data?.[field.name];
            if (value === undefined || value === null || value === "" || field.admin?.hidden) continue;
            if (Array.isArray(value) && !value.length) continue;
            if (["title", "slug", "hero", "meta", "publishedAt"].includes(field.name) && fields === config.fields) continue;
            switch (field.type) {
                case "richText":
                    html += `<div class="rich-text">${richText(value)}</div>`;
                    break;
                case "upload":
                    html += `<div class="media">${Array.isArray(value) ? value.map((v) => media(v)).join("") : media(value)}</div>`;
                    break;
                case "blocks":
                    html += (value || []).map(block).join("");
                    break;
                case "array":
                    if (field.fields?.some((f) => f.name === "url" || flatten(f.fields || []).some((s) => s.name === "url"))) {
                        html += links(value);
                    } else {
                        html += `<ul class="array">${value.map((row) => `<li>${fieldsHTML(field.fields, row)}</li>`).join("")}</ul>`;
                    }
                    break;
                case "group":
                    html += `<div class="group">${fieldsHTML(field.fields, value)}</div>`;
                    break;
                case "relationship": {
                    const docs = Array.isArray(value) ? value : [value];
                    html += `<p class="meta"><strong>${esc(field.label || field.name)}:</strong> ${docs.map((d) => esc(typeof d === "object" ? d.title || d.id : d)).join(", ")}</p>`;
                    break;
                }
                case "checkbox":
                case "json":
                case "code":
                    break;
                default:
                    html += `<p class="meta"><strong>${esc(field.label || field.name)}:</strong> ${esc(value)}</p>`;
            }
        }
        return html;
    }

    function hero(data) {
        const h = data.hero;
        const image = h?.media || data.heroImage || data.meta?.image;
        const date = data.publishedAt || data.updatedAt;
        const title = data.title ?? config.label;
        const type = h?.type || (image ? "mediumImpact" : "lowImpact");
        return `<header class="hero hero--${esc(type)}">
            ${image && typeof image === "object" && type !== "lowImpact" ? `<div class="hero__media">${media(image)}</div>` : ""}
            <div class="hero__content container">
                ${date ? `<div class="hero__date">${esc(new Date(date).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" }))}</div>` : ""}
                <h1>${esc(title)}</h1>
                ${h?.richText ? `<div class="rich-text">${richText(h.richText)}</div>` : ""}
                ${links(h?.links)}
            </div>
        </header>`;
    }

    function siteHeader() {
        const items = header?.navItems || [];
        return `<nav class="site-nav container">
            <a class="logo" href="/cms/preview/globals/header/global" onclick="return false"><svg viewBox="0 0 25 25" width="26" height="26"><path fill="currentColor" d="M11.8673 21.2336L4.40922 16.9845C4.31871 16.9309 4.25837 16.8355 4.25837 16.7282V10.1609C4.25837 10.0477 4.38508 9.97616 4.48162 10.0298L13.1404 14.9642C13.2611 15.0358 13.412 14.9464 13.412 14.8093V11.6091C13.412 11.4839 13.3456 11.3647 13.2309 11.2992L2.81624 5.36353C2.72573 5.30989 2.60505 5.30989 2.51454 5.36353L1.15085 6.14422C1.06034 6.19786 1 6.29321 1 6.40048V18.5995C1 18.7068 1.06034 18.8021 1.15085 18.8558L11.8491 24.9583C11.9397 25.0119 12.0603 25.0119 12.1509 24.9583L21.1355 19.8331C21.2562 19.7616 21.2562 19.5948 21.1355 19.5232L18.3357 17.9261C18.2211 17.8605 18.0883 17.8605 17.9737 17.9261L12.175 21.2336C12.0845 21.2872 11.9638 21.2872 11.8733 21.2336H11.8673Z"/><path fill="currentColor" d="M22.8491 6.13827L12.1508 0.0417218C12.0603 -0.0119135 11.9397 -0.0119135 11.8491 0.0417218L6.19528 3.2658C6.0746 3.33731 6.0746 3.50418 6.19528 3.57569L8.97092 5.16091C9.08557 5.22647 9.21832 5.22647 9.33296 5.16091L11.8672 3.71872C11.9578 3.66508 12.0784 3.66508 12.1689 3.71872L19.627 7.96782C19.7175 8.02146 19.7778 8.11681 19.7778 8.22408V14.8212C19.7778 14.9464 19.8442 15.0656 19.9589 15.1311L22.7345 16.7104C22.8552 16.7819 23.006 16.6925 23.006 16.5554V6.40048C23.006 6.29321 22.9457 6.19786 22.8552 6.14423L22.8491 6.13827Z"/></svg></a>
            <div class="site-nav__links">${items.map((i) => `<a href="${esc(i.url)}">${esc(i.label)}</a>`).join("")}</div>
        </nav>`;
    }

    async function renderArchives() {
        for (const el of root.querySelectorAll(".archive")) {
            try {
                const res = await fetch(`/api/posts?limit=${el.dataset.limit}&depth=1${LOCALE_QUERY}`, { credentials: "same-origin" });
                const json = await res.json();
                el.innerHTML = (json.docs || [])
                    .map((p) => `<article class="card">${media(p.heroImage, "medium")}<h3>${esc(p.title)}</h3></article>`)
                    .join("");
            } catch {
                el.innerHTML = "";
            }
        }
    }

    function render(data) {
        root.classList.remove("preview-loading");
        root.innerHTML = `${siteHeader()}${hero(data)}<main class="container">${fieldsHTML(config.fields, data)}</main>`;
        renderArchives();
    }

    // ------------------------------------------------------------------
    // Data loading & live preview protocol
    // ------------------------------------------------------------------
    async function loadInitial() {
        try {
            const res = await fetch(`${apiPath}?depth=${DEPTH}&draft=true${LOCALE_QUERY}`, { credentials: "same-origin" });
            return await res.json();
        } catch {
            return {};
        }
    }

    async function merge(data) {
        const res = await fetch(`${apiPath}?depth=${DEPTH}${LOCALE_QUERY}`, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-Payload-HTTP-Method-Override": "GET" },
            body: JSON.stringify({ data, depth: DEPTH }),
        });
        return res.json();
    }

    let pending = 0;
    window.addEventListener("message", async (event) => {
        if (event.origin !== window.location.origin || event.data?.type !== "payload-live-preview" || !event.data.data) {
            return;
        }
        const ticket = ++pending;
        try {
            const merged = await merge(event.data.data);
            if (ticket === pending) {
                render(merged);
            }
        } catch {
            render(event.data.data);
        }
    });

    (async () => {
        try {
            const res = await fetch(`/api/globals/header?depth=1${LOCALE_QUERY}`, { credentials: "same-origin" });
            header = await res.json();
        } catch {
            header = null;
        }
        render(await loadInitial());
        const parent = window.opener || window.parent;
        if (parent && parent !== window) {
            parent.postMessage({ type: "payload-live-preview", ready: true }, window.location.origin);
        }
    })();
})();
