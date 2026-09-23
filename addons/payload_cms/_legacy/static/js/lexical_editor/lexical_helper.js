/** @odoo-module **/

/**
 * Fonctions d'aide pour l'éditeur Lexical et la compatibilité avec le format Payload CMS.
 */

/**
 * Retourne l'état initial par défaut d'un éditeur Lexical au format JSON Payload CMS.
 */
export function getInitialPayloadState() {
    return {
        root: {
            children: [
                {
                    children: [],
                    direction: "ltr",
                    format: "",
                    indent: 0,
                    type: "paragraph",
                    version: 1
                }
            ],
            direction: "ltr",
            format: "",
            indent: 0,
            type: "root",
            version: 1
        }
    };
}

/**
 * Normalise et analyse la valeur brute issue du champ Odoo (Objet, Chaîne JSON ou texte).
 * Garantit de toujours renvoyer une chaîne JSON valide exploitable par editor.parseEditorState().
 */
export function normalizePayloadContent(value) {
    if (!value) {
        return JSON.stringify(getInitialPayloadState());
    }

    // Si la valeur est déjà un objet JavaScript (cas d'un fields.Json dans Odoo)
    if (typeof value === 'object') {
        if (value.root && Array.isArray(value.root.children)) {
            return JSON.stringify(value);
        }
        return JSON.stringify(getInitialPayloadState());
    }

    // Si la valeur est une chaîne
    if (typeof value === 'string') {
        const trimmed = value.trim();
        if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
            try {
                const parsed = JSON.parse(trimmed);
                if (parsed.root && Array.isArray(parsed.root.children)) {
                    return trimmed;
                }
            } catch (e) {
                console.warn("[Payload CMS] JSON invalide dans le champ rich text, réinitialisation de l'état.", e);
            }
        }
    }

    return JSON.stringify(getInitialPayloadState());
}

/**
 * Vérifie que la librairie PayloadLexical est bien chargée dans la page.
 */
export function getLexicalLib() {
    if (!window.PayloadLexical) {
        throw new Error(
            "[Payload CMS] La librairie Lexical n'est pas chargée. Vérifiez que static/lib/lexical/lexical.bundle.js est bien inclus dans web.assets_backend."
        );
    }
    return window.PayloadLexical;
}
