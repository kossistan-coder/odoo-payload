/** @odoo-module **/
import { getLexicalLib } from './lexical_helper';

/**
 * Registre extensible des fonctionnalités (features) de l'éditeur Lexical.
 * Chaque fonctionnalité fournit ses nœuds de syntaxe, ses commandes de barre d'outils et son état actif.
 */
export class LexicalFeatureRegistry {
    constructor() {
        this.features = new Map();
    }

    register(featureConfig) {
        if (!featureConfig.id) {
            throw new Error("[LexicalFeatureRegistry] Une fonctionnalité doit avoir un 'id' unique.");
        }
        this.features.set(featureConfig.id, featureConfig);
    }

    getAll() {
        return Array.from(this.features.values());
    }

    get(id) {
        return this.features.get(id);
    }

    getRequiredNodes() {
        const nodes = new Set();
        for (const feature of this.features.values()) {
            if (feature.nodes && Array.isArray(feature.nodes)) {
                for (const node of feature.nodes) {
                    nodes.add(node);
                }
            }
        }
        return Array.from(nodes);
    }
}

/**
 * Initialise et configure l'ensemble des fonctionnalités de base reproduisant la toolbar Payload CMS.
 */
export function createDefaultFeatureRegistry() {
    const Lexical = getLexicalLib();
    const registry = new LexicalFeatureRegistry();

    // 1. Annuler / Rétablir
    registry.register({
        id: 'undo',
        label: 'Annuler (Ctrl+Z)',
        icon: 'fa-undo',
        group: 'history',
        execute(editor) {
            editor.dispatchCommand(Lexical.UNDO_COMMAND, undefined);
        },
    });

    registry.register({
        id: 'redo',
        label: 'Rétablir (Ctrl+Y)',
        icon: 'fa-repeat',
        group: 'history',
        execute(editor) {
            editor.dispatchCommand(Lexical.REDO_COMMAND, undefined);
        },
    });

    // 2. Types de blocs
    registry.register({
        id: 'paragraph',
        label: 'Normal Text',
        group: 'block',
        execute(editor) {
            editor.update(() => {
                const selection = Lexical.$getSelection();
                if (Lexical.$isRangeSelection(selection)) {
                    Lexical.$setBlocksType(selection, () => Lexical.$createParagraphNode());
                }
            });
        },
    });

    registry.register({
        id: 'h1',
        label: 'Heading 1',
        group: 'block',
        nodes: [Lexical.HeadingNode],
        execute(editor) {
            editor.update(() => {
                const selection = Lexical.$getSelection();
                if (Lexical.$isRangeSelection(selection)) {
                    Lexical.$setBlocksType(selection, () => Lexical.$createHeadingNode('h1'));
                }
            });
        },
    });

    registry.register({
        id: 'h2',
        label: 'Heading 2',
        group: 'block',
        nodes: [Lexical.HeadingNode],
        execute(editor) {
            editor.update(() => {
                const selection = Lexical.$getSelection();
                if (Lexical.$isRangeSelection(selection)) {
                    Lexical.$setBlocksType(selection, () => Lexical.$createHeadingNode('h2'));
                }
            });
        },
    });

    registry.register({
        id: 'h3',
        label: 'Heading 3',
        group: 'block',
        nodes: [Lexical.HeadingNode],
        execute(editor) {
            editor.update(() => {
                const selection = Lexical.$getSelection();
                if (Lexical.$isRangeSelection(selection)) {
                    Lexical.$setBlocksType(selection, () => Lexical.$createHeadingNode('h3'));
                }
            });
        },
    });

    registry.register({
        id: 'quote',
        label: 'Quote',
        group: 'block',
        nodes: [Lexical.QuoteNode],
        execute(editor) {
            editor.update(() => {
                const selection = Lexical.$getSelection();
                if (Lexical.$isRangeSelection(selection)) {
                    Lexical.$setBlocksType(selection, () => Lexical.$createQuoteNode());
                }
            });
        },
    });

    // 3. Formats en ligne (Inline Formats)
    registry.register({
        id: 'bold',
        label: 'Bold (Ctrl+B)',
        char: 'B',
        group: 'format',
        execute(editor) {
            editor.dispatchCommand(Lexical.FORMAT_TEXT_COMMAND, 'bold');
        },
    });

    registry.register({
        id: 'italic',
        label: 'Italic (Ctrl+I)',
        char: 'I',
        style: 'font-style: italic;',
        group: 'format',
        execute(editor) {
            editor.dispatchCommand(Lexical.FORMAT_TEXT_COMMAND, 'italic');
        },
    });

    registry.register({
        id: 'underline',
        label: 'Underline (Ctrl+U)',
        char: 'U',
        style: 'text-decoration: underline;',
        group: 'format',
        execute(editor) {
            editor.dispatchCommand(Lexical.FORMAT_TEXT_COMMAND, 'underline');
        },
    });

    registry.register({
        id: 'strikethrough',
        label: 'Strikethrough',
        char: 'S',
        style: 'text-decoration: line-through;',
        group: 'format',
        execute(editor) {
            editor.dispatchCommand(Lexical.FORMAT_TEXT_COMMAND, 'strikethrough');
        },
    });

    registry.register({
        id: 'subscript',
        label: 'Subscript',
        html: 'X<sub>2</sub>',
        group: 'format',
        execute(editor) {
            editor.dispatchCommand(Lexical.FORMAT_TEXT_COMMAND, 'subscript');
        },
    });

    registry.register({
        id: 'superscript',
        label: 'Superscript',
        html: 'X<sup>2</sup>',
        group: 'format',
        execute(editor) {
            editor.dispatchCommand(Lexical.FORMAT_TEXT_COMMAND, 'superscript');
        },
    });

    registry.register({
        id: 'code',
        label: 'Inline Code',
        html: '&lt;/&gt;',
        group: 'format',
        execute(editor) {
            editor.dispatchCommand(Lexical.FORMAT_TEXT_COMMAND, 'code');
        },
    });

    // 4. Alignement
    registry.register({
        id: 'align_left',
        label: 'Align Left',
        icon: 'fa-align-left',
        group: 'align',
        execute(editor) {
            editor.dispatchCommand(Lexical.FORMAT_ELEMENT_COMMAND, 'left');
        },
    });

    registry.register({
        id: 'align_center',
        label: 'Align Center',
        icon: 'fa-align-center',
        group: 'align',
        execute(editor) {
            editor.dispatchCommand(Lexical.FORMAT_ELEMENT_COMMAND, 'center');
        },
    });

    registry.register({
        id: 'align_right',
        label: 'Align Right',
        icon: 'fa-align-right',
        group: 'align',
        execute(editor) {
            editor.dispatchCommand(Lexical.FORMAT_ELEMENT_COMMAND, 'right');
        },
    });

    // 5. Listes
    registry.register({
        id: 'bullet_list',
        label: 'Bullet List',
        icon: 'fa-list-ul',
        group: 'list',
        nodes: [Lexical.ListNode, Lexical.ListItemNode],
        execute(editor) {
            editor.dispatchCommand(Lexical.INSERT_UNORDERED_LIST_COMMAND, undefined);
        },
    });

    registry.register({
        id: 'numbered_list',
        label: 'Numbered List',
        icon: 'fa-list-ol',
        group: 'list',
        nodes: [Lexical.ListNode, Lexical.ListItemNode],
        execute(editor) {
            editor.dispatchCommand(Lexical.INSERT_ORDERED_LIST_COMMAND, undefined);
        },
    });

    // 6. Lien
    registry.register({
        id: 'link',
        label: 'Insert Link',
        icon: 'fa-link',
        group: 'insert',
        nodes: [Lexical.LinkNode, Lexical.AutoLinkNode],
        execute(editor) {
            const url = window.prompt("Entrez l'URL du lien :");
            if (url !== null) {
                if (url.trim() === '') {
                    editor.dispatchCommand(Lexical.TOGGLE_LINK_COMMAND, null);
                } else {
                    editor.dispatchCommand(Lexical.TOGGLE_LINK_COMMAND, url.trim());
                }
            }
        },
    });

    return registry;
}
