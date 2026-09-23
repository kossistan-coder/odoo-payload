/** @odoo-module **/

/**
 * Moteur de rendu HTML pour l'arbre d'état JSON Lexical (compatible Payload CMS).
 * Transforme les nœuds récursivement pour le panneau "Live Preview".
 */

export function renderLexicalToHtml(node) {
    if (!node) {
        return "";
    }

    // Nœud racine
    if (node.type === "root") {
        if (!node.children || !node.children.length) {
            return "<p class='text-muted'>Aucun contenu rédigé pour l'instant...</p>";
        }
        return node.children.map(renderLexicalToHtml).join("");
    }

    // Paragraphe
    if (node.type === "paragraph") {
        const content = renderChildren(node);
        if (!content || content.trim() === "") {
            return "<p><br/></p>";
        }
        return `<p>${content}</p>`;
    }

    // Titres H1, H2, H3
    if (node.type === "heading") {
        const tag = node.tag || "h2";
        const content = renderChildren(node);
        return `<${tag}>${content}</${tag}>`;
    }

    // Citation
    if (node.type === "quote") {
        return `<blockquote>${renderChildren(node)}</blockquote>`;
    }

    // Listes
    if (node.type === "list") {
        const tag = node.listType === "number" ? "ol" : "ul";
        return `<${tag}>${renderChildren(node)}</${tag}>`;
    }

    // Éléments de liste
    if (node.type === "listitem") {
        return `<li>${renderChildren(node)}</li>`;
    }

    // Liens
    if (node.type === "link") {
        const url = node.fields?.url || node.url || "#";
        return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${renderChildren(node)}</a>`;
    }

    // Nœud texte avec formatage (Gras, Italique, Souligné, Code, etc.)
    if (node.type === "text") {
        let text = escapeHtml(node.text || "");
        const format = node.format || 0;

        // Lexical format bitmask:
        // 1: Bold, 2: Italic, 4: Strikethrough, 8: Underline, 16: Code, 32: Subscript, 64: Superscript
        if (format & 1) text = `<strong>${text}</strong>`;
        if (format & 2) text = `<em>${text}</em>`;
        if (format & 4) text = `<s>${text}</s>`;
        if (format & 8) text = `<u>${text}</u>`;
        if (format & 16) text = `<code>${text}</code>`;
        if (format & 32) text = `<sub>${text}</sub>`;
        if (format & 64) text = `<sup>${text}</sup>`;

        return text;
    }

    // Nœuds enfants par défaut
    if (node.children && Array.isArray(node.children)) {
        return renderChildren(node);
    }

    return "";
}

function renderChildren(node) {
    if (!node.children || !Array.isArray(node.children)) {
        return "";
    }
    return node.children.map(renderLexicalToHtml).join("");
}

function escapeHtml(str) {
    if (typeof str !== "string") return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
