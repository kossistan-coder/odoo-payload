/** @odoo-module **/

/**
 * Thème CSS pour l'éditeur Lexical dans Odoo.
 * Associe les nœuds Lexical (headings, quotes, lists, links) aux classes préfixées du module.
 */
export const LexicalTheme = {
    ltr: 'ltr',
    rtl: 'rtl',
    placeholder: 'o_payload_lexical_placeholder',
    paragraph: 'o_payload_lexical_paragraph',
    quote: 'o_payload_lexical_quote',
    heading: {
        h1: 'o_payload_lexical_h1',
        h2: 'o_payload_lexical_h2',
        h3: 'o_payload_lexical_h3',
        h4: 'o_payload_lexical_h4',
        h5: 'o_payload_lexical_h5',
    },
    list: {
        nested: {
            listitem: 'o_payload_lexical_nested_li',
        },
        ol: 'o_payload_lexical_ol',
        ul: 'o_payload_lexical_ul',
        listitem: 'o_payload_lexical_li',
    },
    link: 'o_payload_lexical_link',
    text: {
        bold: 'o_payload_lexical_bold',
        italic: 'o_payload_lexical_italic',
        underline: 'o_payload_lexical_underline',
        strikethrough: 'o_payload_lexical_strikethrough',
        code: 'o_payload_lexical_code',
    },
};
