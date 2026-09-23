/** @odoo-module **/

/**
 * Vanilla-Lexical port of Payload's default rich text editor
 * (@payloadcms/richtext-lexical 3.90): inline toolbar, slash menu, add-block
 * and drag handles, floating link editor, decorator selection, markdown
 * shortcuts, check lists and tab indentation.
 */
import { getCollection } from "../core/store";
import { docTitle } from "../core/utils";
import { ensureDocs, getCachedDoc } from "../core/relations";
import {
    $createHorizontalRuleNode,
    $createPayloadLinkNode,
    $createRelationshipNode,
    $createUploadNode,
    $isHorizontalRuleNode,
    $isPayloadLinkNode,
    $toggleLink,
    HorizontalRuleNode,
    PAYLOAD_NODES,
} from "./nodes";

const L = window.PayloadLexical;

export const EDITOR_THEME = {
    block: "LexicalEditorTheme__block",
    blockCursor: "LexicalEditorTheme__blockCursor",
    characterLimit: "LexicalEditorTheme__characterLimit",
    code: "LexicalEditorTheme__code",
    inlineBlock: "LexicalEditorTheme__inlineBlock",
    heading: {
        h1: "LexicalEditorTheme__h1",
        h2: "LexicalEditorTheme__h2",
        h3: "LexicalEditorTheme__h3",
        h4: "LexicalEditorTheme__h4",
        h5: "LexicalEditorTheme__h5",
        h6: "LexicalEditorTheme__h6",
    },
    hr: "LexicalEditorTheme__hr",
    hrSelected: "LexicalEditorTheme__hrSelected",
    indent: "LexicalEditorTheme__indent",
    link: "LexicalEditorTheme__link",
    list: {
        checklist: "LexicalEditorTheme__checklist",
        listitem: "LexicalEditorTheme__listItem",
        listitemChecked: "LexicalEditorTheme__listItemChecked",
        listitemUnchecked: "LexicalEditorTheme__listItemUnchecked",
        nested: { listitem: "LexicalEditorTheme__nestedListItem" },
        olDepth: ["LexicalEditorTheme__ol1", "LexicalEditorTheme__ol2", "LexicalEditorTheme__ol3", "LexicalEditorTheme__ol4", "LexicalEditorTheme__ol5"],
        ul: "LexicalEditorTheme__ul",
    },
    mark: "LexicalEditorTheme__mark",
    markOverlap: "LexicalEditorTheme__markOverlap",
    paragraph: "LexicalEditorTheme__paragraph",
    placeholder: "LexicalEditorTheme__placeholder",
    quote: "LexicalEditorTheme__quote",
    relationship: "LexicalEditorTheme__relationship",
    tab: "LexicalEditorTheme__tabNode",
    text: {
        bold: "LexicalEditorTheme__textBold",
        code: "LexicalEditorTheme__textCode",
        italic: "LexicalEditorTheme__textItalic",
        strikethrough: "LexicalEditorTheme__textStrikethrough",
        subscript: "LexicalEditorTheme__textSubscript",
        superscript: "LexicalEditorTheme__textSuperscript",
        underline: "LexicalEditorTheme__textUnderline",
        underlineStrikethrough: "LexicalEditorTheme__textUnderlineStrikethrough",
    },
    upload: "LexicalEditorTheme__upload",
};

// ----------------------------------------------------------------------
// Icons (richtext-lexical/src/lexical/ui/icons)
// ----------------------------------------------------------------------
const svg = (body, fill = "none") =>
    `<svg aria-hidden="true" class="icon" fill="${fill}" focusable="false" height="20" viewBox="0 0 20 20" width="20" xmlns="http://www.w3.org/2000/svg">${body}</svg>`;
const hIcon = (d) => svg(`<path d="${d}" fill="currentColor"/>`);
export const ICONS = {
    text: svg('<path d="M11.708 14.5H7.79785V13.9414H8.01367C9.00391 13.9414 9.15625 13.9033 9.15625 13.6113V6.70508H8.07715C6.82031 6.70508 6.73145 7.08594 6.28711 8.67285H5.80469L5.91895 6.12109H13.5869L13.7012 8.67285H13.2188C12.7744 7.08594 12.6855 6.70508 11.4287 6.70508H10.3496V13.6113C10.3496 13.9033 10.502 13.9414 11.4922 13.9414H11.708V14.5Z" fill="currentColor"/>', "currentColor"),
    h1: hIcon("M4.639 13.5V7.074H6.196V9.648H9.076V7.074H10.642V13.5H9.076V10.836H6.196V13.5H4.639ZM11.5656 9.045V8.019C12.6636 8.019 13.1316 7.731 13.2846 7.065H14.4006V13.5H12.8436V9.045H11.5656Z"),
    h2: hIcon("M4.139 13.5V7.074H5.696V9.648H8.576V7.074H10.142V13.5H8.576V10.836H5.696V13.5H4.139ZM15.9796 8.973C15.9796 10.116 15.1696 10.656 14.0356 11.232C13.2256 11.646 12.8206 11.943 12.7846 12.294H15.9886V13.5H11.0566V12.951C11.0566 11.601 12.1636 10.845 13.1176 10.287C14.0356 9.756 14.5126 9.486 14.5126 8.946C14.5126 8.46 14.2156 8.145 13.6306 8.145C13.0186 8.145 12.6586 8.613 12.6226 9.198H11.1196C11.2186 7.947 12.1006 6.966 13.6396 6.966C15.0346 6.966 15.9796 7.785 15.9796 8.973Z"),
    h3: hIcon("M4.139 13.5V7.074H5.696V9.648H8.576V7.074H10.142V13.5H8.576V10.836H5.696V13.5H4.139ZM16.1146 11.745C16.1146 12.744 15.2236 13.608 13.6126 13.608C12.0736 13.608 11.0926 12.762 10.9846 11.547H12.4696C12.5146 12.114 13.0006 12.456 13.6126 12.456C14.2876 12.456 14.6746 12.132 14.6746 11.619C14.6746 11.061 14.2426 10.836 13.6216 10.836H12.9826V9.738H13.6036C14.1526 9.738 14.5486 9.486 14.5486 8.937C14.5486 8.46 14.2156 8.127 13.6486 8.127C13.0366 8.127 12.6586 8.514 12.6226 9.045H11.1916C11.2726 7.929 12.1276 6.966 13.6666 6.966C15.1876 6.966 15.9706 7.848 15.9706 8.865C15.9706 9.603 15.5026 10.143 14.8186 10.269C15.6196 10.404 16.1146 10.971 16.1146 11.745Z"),
    h4: hIcon("M3.639 13.5V7.074H5.196V9.648H8.076V7.074H9.642V13.5H8.076V10.836H5.196V13.5H3.639ZM15.1736 7.074V10.854H16.3706V12.033H15.1736V13.5H13.6796V12.033H10.5116V10.845L13.4996 7.074H15.1736ZM13.6796 8.46L11.8256 10.854H13.6796V8.46Z"),
    h5: hIcon("M3.639 13.5V7.074H5.196V9.648H8.076V7.074H9.642V13.5H8.076V10.836H5.196V13.5H3.639ZM13.1576 10.269C12.6896 10.269 12.3746 10.494 12.2216 10.737H10.8176L11.1956 7.074H15.2546V8.28H12.3206L12.1856 9.549C12.4016 9.351 12.8516 9.126 13.4636 9.126C14.7866 9.126 15.6596 10.053 15.6596 11.358C15.6596 12.609 14.7326 13.608 13.1756 13.608C11.5826 13.608 10.6556 12.753 10.5566 11.511H12.1136C12.1586 12.06 12.5456 12.465 13.1576 12.465C13.8236 12.465 14.1746 11.97 14.1746 11.376C14.1746 10.764 13.8416 10.269 13.1576 10.269Z"),
    h6: hIcon("M3.639 13.5V7.074H5.196V9.648H8.076V7.074H9.642V13.5H8.076V10.836H5.196V13.5H3.639ZM13.3646 8.127C12.5456 8.127 12.0416 8.937 12.0416 9.999C12.3296 9.54 12.8246 9.207 13.5536 9.207C14.8586 9.207 15.8036 10.134 15.8036 11.376C15.8036 12.645 14.8226 13.608 13.3196 13.608C11.7266 13.608 10.6196 12.393 10.6196 10.395C10.6196 8.316 11.7716 6.966 13.4186 6.966C14.7056 6.966 15.5786 7.749 15.7316 8.829H14.3186C14.2016 8.415 13.9226 8.127 13.3646 8.127ZM13.3106 12.51C13.9586 12.51 14.3816 12.042 14.3816 11.385C14.3816 10.737 13.9586 10.278 13.3106 10.278C12.6536 10.278 12.2126 10.737 12.2126 11.385C12.2126 12.042 12.6536 12.51 13.3106 12.51Z"),
    orderedList: svg('<path d="M5.89284 12.479C5.89284 13.368 5.26284 13.788 4.38084 14.236C3.75084 14.558 3.43584 14.789 3.40784 15.062H5.89984V16H2.06384V15.573C2.06384 14.523 2.92484 13.935 3.66684 13.501C4.38084 13.088 4.75184 12.878 4.75184 12.458C4.75184 12.08 4.52084 11.835 4.06584 11.835C3.58984 11.835 3.30984 12.199 3.28184 12.654H2.11284C2.18984 11.681 2.87584 10.918 4.07284 10.918C5.15784 10.918 5.89284 11.555 5.89284 12.479Z" fill="currentColor"/><path d="M2.68608 4.535V3.737C3.54008 3.737 3.90408 3.513 4.02308 2.995H4.89108V8H3.68008L3.68008 4.535H2.68608Z" fill="currentColor"/><path d="M8 15L17 15" stroke="currentColor" stroke-width="1.5"/><path d="M8 10L17 10" stroke="currentColor" stroke-width="1.5"/><path d="M8 5L17 5" stroke="currentColor" stroke-width="1.5"/>'),
    unorderedList: svg('<circle cx="4" cy="5" fill="currentColor" r="1.15" stroke="currentColor" stroke-width="0.3"/><circle cx="4" cy="10" fill="currentColor" r="1.15" stroke="currentColor" stroke-width="0.3"/><circle cx="4" cy="15" fill="currentColor" r="1.15" stroke="currentColor" stroke-width="0.3"/><path d="M17 5H7" stroke="currentColor" stroke-width="1.5"/><path d="M17 10H7" stroke="currentColor" stroke-width="1.5"/><path d="M17 15H7" stroke="currentColor" stroke-width="1.5"/>'),
    checklist: svg('<rect height="13" rx="1.5" stroke="currentColor" width="13" x="3.5" y="3.5"/><path d="M7 10L9 12.5L13 7.5" stroke="currentColor" stroke-width="1.5"/>'),
    blockquote: svg('<path d="M13.5353 10.5725C13.5353 9.47709 11.0456 9.99991 11.0456 7.85883C11.0456 6.46464 12.1162 5.61816 13.361 5.61816C14.805 5.61816 16 6.86298 16 8.92937C16 11.2945 14.4564 13.7841 11.1203 14.3816L10.8216 13.1368C12.888 12.4895 13.5353 11.4937 13.5353 10.5725ZM6.71369 10.5725C6.71369 9.47709 4.22407 9.99991 4.22407 7.85883C4.22407 6.46464 5.29461 5.61816 6.53942 5.61816C7.9834 5.61816 9.17842 6.86298 9.17842 8.92937C9.17842 11.2945 7.63485 13.7841 4.29876 14.3816L4 13.1368C6.06639 12.4895 6.71369 11.4937 6.71369 10.5725Z" fill="currentColor"/>'),
    alignLeft: svg('<path d="M2.5 5H17.5" stroke="currentColor" stroke-width="1.5"/><path d="M2.5 10H17.5" stroke="currentColor" stroke-width="1.5"/><path d="M2.5 15H12.5" stroke="currentColor" stroke-width="1.5"/>'),
    alignCenter: svg('<path d="M2.5 5H17.5" stroke="currentColor" stroke-width="1.5"/><path d="M2.5 10H17.5" stroke="currentColor" stroke-width="1.5"/><path d="M5 15H15" stroke="currentColor" stroke-width="1.5"/>'),
    alignRight: svg('<path d="M2.5 5H17.5" stroke="currentColor" stroke-width="1.5"/><path d="M2.5 10H17.5" stroke="currentColor" stroke-width="1.5"/><path d="M7.5 15H17.5" stroke="currentColor" stroke-width="1.5"/>'),
    alignJustify: svg('<path d="M2.5 5H17.5" stroke="currentColor" stroke-width="1.5"/><path d="M2.5 10H17.5" stroke="currentColor" stroke-width="1.5"/><path d="M2.5 15H17.5" stroke="currentColor" stroke-width="1.5"/>'),
    indentDecrease: svg('<path d="M2.5 5H10.5" stroke="currentColor" stroke-width="1.5"/><path d="M2.5 10H10.5" stroke="currentColor" stroke-width="1.5"/><path d="M2.5 15H17.5" stroke="currentColor" stroke-width="1.5"/><path d="M12.25 7.25L17.25 3.75V10.75L12.25 7.25Z" fill="currentColor"/>'),
    indentIncrease: svg('<path d="M17.5 5H9.5" stroke="currentColor" stroke-width="1.5"/><path d="M17.5 10H9.5" stroke="currentColor" stroke-width="1.5"/><path d="M17.5 15H2.5" stroke="currentColor" stroke-width="1.5"/><path d="M7.75 7.25L2.75 3.75V10.75L7.75 7.25Z" fill="currentColor"/>'),
    bold: svg('<path d="M10.6772 15H6.27017V5.718H10.4172C12.6792 5.718 13.8492 6.602 13.8492 8.292C13.8492 9.098 13.1992 9.982 12.4712 10.216C13.3812 10.476 14.1742 11.256 14.1742 12.322C14.1742 14.09 12.9002 15 10.6772 15ZM8.46717 9.501H10.3262C11.3012 9.501 11.7042 9.046 11.7042 8.409C11.7042 7.72 11.2362 7.317 10.3392 7.317H8.46717V9.501ZM8.46717 11.061V13.401H10.4822C11.4702 13.401 11.9642 12.959 11.9642 12.218C11.9642 11.49 11.4702 11.061 10.4822 11.061H8.46717Z" fill="currentColor"/>', "currentColor"),
    italic: svg('<path d="M11.311 14.2969L11.0327 15H6.18408L6.4624 14.2969C7.54639 14.2969 7.70752 14.209 7.83936 13.8721L10.8423 6.45996C10.8716 6.38672 10.8862 6.32812 10.8862 6.26953C10.8862 6.09375 10.6519 6.03516 9.80225 6.03516L10.0952 5.33203H14.9438L14.6509 6.03516C13.5669 6.03516 13.4204 6.12305 13.2886 6.45996L10.2856 13.8721C10.2563 13.9453 10.2271 14.0039 10.2271 14.0625C10.2271 14.2383 10.4614 14.2969 11.311 14.2969Z" fill="currentColor"/>', "currentColor"),
    underline: svg('<path d="M13.9656 11.256C13.9656 13.791 12.5096 15.156 10.0006 15.156C7.50461 15.156 6.03561 13.791 6.03561 11.23V5.718H7.76461V11.243C7.76461 12.868 8.50561 13.778 10.0006 13.778C11.4956 13.778 12.2496 12.868 12.2496 11.243V5.718H13.9656V11.256Z" fill="currentColor"/><path d="M5.09961 16.3H14.9016V16.95H5.09961V16.3Z" fill="currentColor"/>', "currentColor"),
    strikethrough: svg('<path d="M5.50756 12.76H7.42756C7.56256 14.215 8.82256 14.71 10.1576 14.71C11.4326 14.71 12.4226 14.14 12.4226 13.06C12.4226 12.28 11.9576 11.845 10.6676 11.605L8.70256 11.245C7.12756 10.96 5.85256 10.21 5.85256 8.335C5.85256 6.43 7.53256 5.11 9.87256 5.11C12.4226 5.11 13.9526 6.22 14.1626 8.23H12.2876C12.1526 7.18 11.2226 6.595 9.88756 6.595C8.59756 6.595 7.78756 7.27 7.78756 8.215C7.78756 9.1 8.34256 9.385 9.49756 9.61L11.5676 10.015C13.3226 10.345 14.3726 11.215 14.3726 12.94C14.3726 14.89 12.5876 16.18 10.2176 16.18C7.66756 16.18 5.70256 15.115 5.50756 12.76Z" fill="currentColor"/><path d="M4.99756 11.44H15.0026V12.19H4.99756V11.44Z" fill="currentColor"/>', "currentColor"),
    subscript: svg('<path d="M10.167 15L7.45002 11.36L4.73302 15H2.91302L6.55302 10.177L3.23802 5.718H5.20102L7.54102 8.89L9.89402 5.718H11.714L8.43802 10.06L12.13 15H10.167ZM16.7768 13.258C16.7768 14.155 16.1398 14.532 15.2038 15C14.5538 15.325 14.2808 15.546 14.2418 15.78H16.7898V16.82H12.7208V16.339C12.7208 15.286 13.5918 14.675 14.3588 14.233C15.0868 13.83 15.4378 13.635 15.4378 13.232C15.4378 12.894 15.2038 12.686 14.8268 12.686C14.3848 12.686 14.1248 13.024 14.1118 13.427H12.7468C12.8248 12.426 13.5528 11.633 14.8398 11.633C15.9448 11.633 16.7768 12.257 16.7768 13.258Z" fill="currentColor"/>', "currentColor"),
    superscript: svg('<path d="M10.167 15L7.45002 11.36L4.73302 15H2.91302L6.55302 10.177L3.23802 5.718H5.20102L7.54102 8.89L9.89402 5.718H11.714L8.43802 10.06L12.13 15H10.167ZM16.7768 7.252C16.7768 8.149 16.1398 8.526 15.2038 8.994C14.5538 9.319 14.2808 9.54 14.2418 9.774H16.7898V10.814H12.7208V10.333C12.7208 9.28 13.5918 8.669 14.3588 8.227C15.0868 7.824 15.4378 7.629 15.4378 7.226C15.4378 6.888 15.2038 6.68 14.8268 6.68C14.3848 6.68 14.1248 7.018 14.1118 7.421H12.7468C12.8248 6.42 13.5528 5.627 14.8398 5.627C15.9448 5.627 16.7768 6.251 16.7768 7.252Z" fill="currentColor"/>', "currentColor"),
    inlineCode: svg('<path d="M7.76465 6L3.76465 10L7.76465 14" stroke="currentColor"/><path d="M12.2354 6L16.2354 10L12.2354 14" stroke="currentColor"/>'),
    link: '<svg aria-hidden="true" class="icon" fill="none" height="20" viewBox="0 0 20 20" width="20" xmlns="http://www.w3.org/2000/svg"><path d="M8.5 11.5L11.5 8.5M8.5 7L9.625 5.875C10.868 4.633 12.882 4.633 14.125 5.875C15.368 7.118 15.368 9.133 14.125 10.375L13 11.5M7 8.5L5.746 9.754C4.56 10.94 4.519 12.85 5.652 14.087C6.814 15.354 8.78 15.449 10.058 14.298L11.5 13" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    relationship: svg('<path d="M7.75 12.25L15.25 4.75M15.25 4.75H11.5M15.25 4.75V8.5M13 11.5V13.75C13 14.5784 12.3284 15.25 11.5 15.25H6.25C5.42157 15.25 4.75 14.5784 4.75 13.75V8.5C4.75 7.67157 5.42157 7 6.25 7H8.5" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/>'),
    upload: svg('<path d="M14.6667 4H5.33333C4.59695 4 4 4.59695 4 5.33333V14.6667C4 15.403 4.59695 16 5.33333 16H14.6667C15.403 16 16 15.403 16 14.6667V5.33333C16 4.59695 15.403 4 14.6667 4Z" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/><path d="M7.99984 9.33366C8.73622 9.33366 9.33317 8.73671 9.33317 8.00033C9.33317 7.26395 8.73622 6.66699 7.99984 6.66699C7.26346 6.66699 6.6665 7.26395 6.6665 8.00033C6.6665 8.73671 7.26346 9.33366 7.99984 9.33366Z" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/><path d="M16 11.9995L13.9427 9.94214C13.6926 9.69218 13.3536 9.55176 13 9.55176C12.6464 9.55176 12.3074 9.69218 12.0573 9.94214L6 15.9995" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/>'),
    horizontalRule: svg('<rect fill="currentColor" height="1" width="12" x="4" y="9.5"/>'),
};

const PLACEHOLDER = "Start typing, or press '/' for commands...";

// ----------------------------------------------------------------------
// Selection helpers
// ----------------------------------------------------------------------
function everyBlock(selection, predicate) {
    const nodes = selection.getNodes();
    if (!nodes.length) {
        return false;
    }
    return nodes.every((node) => predicate(node) || predicate(node.getParent()) || predicate(node.getParent()?.getParent()));
}

function setBlocksType(editor, factory) {
    editor.update(() => {
        const selection = L.$getSelection();
        if (L.$isRangeSelection(selection)) {
            L.$setBlocksType(selection, factory);
        }
    });
}

// ----------------------------------------------------------------------
// Feature definitions (inline toolbar groups + slash menu items)
// ----------------------------------------------------------------------
function headingItems() {
    return ["h1", "h2", "h3", "h4", "h5", "h6"].map((tag, i) => ({
        key: tag,
        label: `Heading ${i + 1}`,
        icon: ICONS[tag],
        keywords: ["heading", tag],
        isActive: (sel) => everyBlock(sel, (n) => L.$isHeadingNode(n) && n.getTag() === tag),
        onSelect: (editor) => setBlocksType(editor, () => L.$createHeadingNode(tag)),
    }));
}

function listItem(key, label, icon, listType, command, keywords) {
    return {
        key,
        label,
        icon,
        keywords,
        isActive: (sel) => everyBlock(sel, (n) => L.$isListNode(n) && n.getListType() === listType),
        onSelect: (editor) => editor.dispatchCommand(command, undefined),
    };
}

export function textItems() {
    return [
        {
            key: "paragraph",
            label: "Normal Text",
            slashLabel: "Paragraph",
            icon: ICONS.text,
            keywords: ["normal", "paragraph", "p", "text"],
            isActive: (sel) => everyBlock(sel, (n) => L.$isParagraphNode(n)),
            onSelect: (editor) => setBlocksType(editor, () => L.$createParagraphNode()),
        },
        ...headingItems(),
        listItem("orderedList", "Ordered List", ICONS.orderedList, "number", L.INSERT_ORDERED_LIST_COMMAND, ["ordered list", "ol"]),
        listItem("unorderedList", "Unordered List", ICONS.unorderedList, "bullet", L.INSERT_UNORDERED_LIST_COMMAND, ["unordered list", "ul"]),
        listItem("checklist", "Check List", ICONS.checklist, "check", L.INSERT_CHECK_LIST_COMMAND, ["check list", "check", "checklist", "cl"]),
        {
            key: "blockquote",
            label: "Blockquote",
            icon: ICONS.blockquote,
            keywords: ["quote", "blockquote"],
            isActive: (sel) => everyBlock(sel, (n) => L.$isQuoteNode(n)),
            onSelect: (editor) => setBlocksType(editor, () => L.$createQuoteNode()),
        },
    ];
}

function alignItems() {
    return ["left", "center", "right", "justify"].map((align) => ({
        key: `align${align[0].toUpperCase()}${align.slice(1)}`,
        label: `Align ${align[0].toUpperCase()}${align.slice(1)}`,
        icon: ICONS[`align${align[0].toUpperCase()}${align.slice(1)}`],
        isActive: (sel) =>
            sel.getNodes().every((n) => {
                const el = L.$isElementNode(n) ? n : n.getParent();
                return el && el.getFormatType?.() === align;
            }),
        onSelect: (editor) => editor.dispatchCommand(L.FORMAT_ELEMENT_COMMAND, align),
    }));
}

const FORMATS = [
    ["bold", "Bold", "bold"],
    ["italic", "Italic", "italic"],
    ["underline", "Underline", "underline"],
    ["strikethrough", "Strikethrough", "strikethrough"],
    ["subscript", "Subscript", "subscript"],
    ["superscript", "Superscript", "superscript"],
    ["inlineCode", "Inline Code", "code"],
];

function toolbarGroups(host) {
    return [
        { key: "text", type: "dropdown", icon: ICONS.text, items: textItems() },
        { key: "align", type: "dropdown", icon: ICONS.alignLeft, items: alignItems() },
        {
            key: "indent",
            type: "buttons",
            items: [
                {
                    key: "indentDecrease",
                    label: "Decrease Indent",
                    icon: ICONS.indentDecrease,
                    isActive: () => false,
                    isEnabled: (sel) =>
                        sel.getNodes().some((n) => {
                            const block = L.$isElementNode(n) ? n : n.getParent();
                            return block && block.getIndent?.() > 0;
                        }),
                    onSelect: (editor) => editor.dispatchCommand(L.OUTDENT_CONTENT_COMMAND, undefined),
                },
                {
                    key: "indentIncrease",
                    label: "Increase Indent",
                    icon: ICONS.indentIncrease,
                    isActive: () => false,
                    onSelect: (editor) => editor.dispatchCommand(L.INDENT_CONTENT_COMMAND, undefined),
                },
            ],
        },
        {
            key: "format",
            type: "buttons",
            items: FORMATS.map(([key, label, format]) => ({
                key,
                label,
                icon: ICONS[key],
                isActive: (sel) => L.$isRangeSelection(sel) && sel.hasFormat(format),
                onSelect: (editor) => editor.dispatchCommand(L.FORMAT_TEXT_COMMAND, format),
            })),
        },
        {
            key: "features",
            type: "buttons",
            items: [
                {
                    key: "link",
                    label: "Link",
                    icon: ICONS.link,
                    isActive: (sel) => L.$isRangeSelection(sel) && Boolean(L.$findMatchingParent(sel.anchor.getNode(), $isPayloadLinkNode)),
                    isEnabled: (sel) => L.$isRangeSelection(sel) && sel.getTextContent().length > 0,
                    onSelect: (editor, isActive) => {
                        if (isActive) {
                            editor.dispatchCommand(L.TOGGLE_LINK_COMMAND, null);
                        } else {
                            host.createLink?.();
                        }
                    },
                },
            ],
        },
    ];
}

function slashGroups(host) {
    const text = textItems();
    const byKey = Object.fromEntries(text.map((i) => [i.key, i]));
    return [
        {
            key: "lists",
            label: "Lists",
            items: [byKey.unorderedList, byKey.orderedList, byKey.checklist],
        },
        {
            key: "basic",
            label: "Basic",
            items: [
                { ...byKey.paragraph, label: "Paragraph" },
                ...["h1", "h2", "h3", "h4", "h5", "h6"].map((h) => ({ ...byKey[h], key: `heading-${h[1]}` })),
                {
                    key: "relationship",
                    label: "Relationship",
                    icon: ICONS.relationship,
                    keywords: ["relationship", "relation", "rel"],
                    onSelect: () => host.openRelationshipDrawer?.({ replace: false }),
                },
                byKey.blockquote,
                {
                    key: "upload",
                    label: "Upload",
                    icon: ICONS.upload,
                    keywords: ["upload", "image", "file", "img", "picture", "photo", "media"],
                    onSelect: () => host.openUploadDrawer?.({ replace: false }),
                },
                {
                    key: "horizontalRule",
                    label: "Horizontal Rule",
                    icon: ICONS.horizontalRule,
                    keywords: ["hr", "horizontal rule", "line", "separator"],
                    onSelect: (editor) =>
                        editor.update(() => {
                            const sel = L.$getSelection();
                            if (L.$isRangeSelection(sel)) {
                                L.$insertNodeToNearestRoot($createHorizontalRuleNode());
                            }
                        }),
                },
            ],
        },
    ];
}

// ----------------------------------------------------------------------
// Markdown transformers (Payload's defaults, with Payload link / hr nodes)
// ----------------------------------------------------------------------
const HR_TRANSFORMER = {
    dependencies: [HorizontalRuleNode],
    export: (node) => ($isHorizontalRuleNode(node) ? "---" : null),
    regExp: /^(---|\*\*\*|___)\s?$/,
    replace: (parentNode, _children, _match, isImport) => {
        const line = $createHorizontalRuleNode();
        if (isImport || parentNode.getNextSibling() != null) {
            parentNode.replace(line);
        } else {
            parentNode.insertBefore(line);
        }
        line.selectNext();
    },
    type: "element",
};

const LINK_TRANSFORMER = {
    dependencies: [],
    export: () => null,
    importRegExp: /(?<!!)\[([^[]+)\]\(([^()\s]+)(?:\s"((?:[^"]*\\")*[^"]*)"\s*)?\)/,
    regExp: /(?<!!)\[([^[]+)\]\(([^()\s]+)(?:\s"((?:[^"]*\\")*[^"]*)"\s*)?\)$/,
    replace: (textNode, match) => {
        const [, text, url] = match;
        const link = $createPayloadLinkNode({ fields: { linkType: "custom", newTab: false, url } });
        const linkText = L.$createTextNode(text);
        linkText.setFormat(textNode.getFormat());
        link.append(linkText);
        textNode.replace(link);
        return linkText;
    },
    trigger: ")",
    type: "text-match",
};

const TRANSFORMERS = [
    L.HEADING,
    L.QUOTE,
    L.UNORDERED_LIST,
    L.ORDERED_LIST,
    L.CHECK_LIST,
    HR_TRANSFORMER,
    L.BOLD_ITALIC_STAR,
    L.BOLD_ITALIC_UNDERSCORE,
    L.BOLD_STAR,
    L.BOLD_UNDERSCORE,
    L.ITALIC_STAR,
    L.ITALIC_UNDERSCORE,
    L.STRIKETHROUGH,
    L.INLINE_CODE,
    LINK_TRANSFORMER,
].filter(Boolean);

/** Fill the keys Lexical expects (JSON written by other tools may omit them). */
function normalizeState(state) {
    const walk = (node) => {
        if (!node || typeof node !== "object") {
            return node;
        }
        const out = { ...node, version: node.version ?? 1 };
        if (Array.isArray(node.children)) {
            out.direction = node.direction === undefined ? null : node.direction;
            out.format = node.format ?? "";
            out.indent = node.indent ?? 0;
            out.children = node.children.map(walk);
            if (node.type === "paragraph") {
                out.textFormat = node.textFormat ?? 0;
                out.textStyle = node.textStyle ?? "";
            }
        } else if (node.type === "text") {
            out.detail = node.detail ?? 0;
            out.format = node.format ?? 0;
            out.mode = node.mode ?? "normal";
            out.style = node.style ?? "";
        }
        return out;
    };
    return { ...state, root: walk(state.root) };
}

// ----------------------------------------------------------------------
// DOM helpers
// ----------------------------------------------------------------------
function el(tag, className, attrs = {}) {
    const node = document.createElement(tag);
    if (className) {
        node.className = className;
    }
    for (const [k, v] of Object.entries(attrs)) {
        node.setAttribute(k, v);
    }
    return node;
}

function setFloatingElemPosition({ alwaysDisplayOnTop = false, anchorElem, anchorFlippedOffset = 0, floatingElem, horizontalOffset = 32, horizontalPosition = "left", specialHandlingForCaret = false, targetRect, verticalGap = 10 }) {
    const scrollerElem = anchorElem.parentElement;
    if (targetRect === null || scrollerElem == null) {
        floatingElem.style.opacity = "0";
        floatingElem.style.transform = "translate(-10000px, -10000px)";
        return 0;
    }
    const f = floatingElem.getBoundingClientRect();
    const a = anchorElem.getBoundingClientRect();
    const s = scrollerElem.getBoundingClientRect();
    let top = targetRect.top - f.height - verticalGap;
    let left = targetRect.left - horizontalOffset;
    if (horizontalPosition === "center") {
        left = targetRect.left + targetRect.width / 2 - f.width / 2;
    }
    let addedToTop = 0;
    if (!alwaysDisplayOnTop && top < s.top && !specialHandlingForCaret) {
        addedToTop = f.height + targetRect.height + verticalGap * 2;
        top += addedToTop;
    }
    if (horizontalPosition === "center") {
        if (left + f.width > s.right) {
            left = s.right - f.width - horizontalOffset;
        } else if (left < s.left) {
            left = s.left + horizontalOffset;
        }
    } else if (left + f.width > s.right) {
        left = s.right - f.width - horizontalOffset;
    }
    left -= a.left;
    floatingElem.style.opacity = "1";
    if (specialHandlingForCaret && anchorFlippedOffset !== 0) {
        top -= a.bottom - anchorFlippedOffset + f.height - 3;
        floatingElem.style.transform = `translate(${left}px, ${top}px) rotate(180deg)`;
    } else {
        top -= a.top;
        floatingElem.style.transform = `translate(${left}px, ${top}px)`;
    }
    return addedToTop;
}

// ----------------------------------------------------------------------
// The editor
// ----------------------------------------------------------------------
export class PayloadEditor {
    /**
     * @param {Object} opts
     * @param {HTMLElement} opts.contentEditable
     * @param {HTMLElement} opts.anchor       `.editor` element (floating anchor)
     * @param {HTMLElement} opts.placeholder  placeholder wrapper
     * @param {Object|null} opts.value        serialized Lexical state
     * @param {boolean} opts.readOnly
     * @param {Function} opts.onChange       (json) => void
     * @param {Object} opts.host             callbacks (drawers)
     */
    constructor(opts) {
        this.opts = opts;
        this.host = opts.host || {};
        this.cleanups = [];
        this.editor = L.createEditor({
            namespace: "lexical",
            theme: EDITOR_THEME,
            nodes: PAYLOAD_NODES,
            editable: !opts.readOnly,
            onError: (e) => console.error("[lexical]", e),
        });
        this.editor._payloadHost = this.host;
        this.editor.setRootElement(opts.contentEditable);
        this.loadValue(opts.value);
        this.registerCore();
        if (!opts.readOnly) {
            this.inlineToolbar = new InlineToolbar(this);
            if (opts.fixedToolbar) {
                this.fixedToolbar = new FixedToolbar(this);
            }
            this.slashMenu = new SlashMenu(this);
            this.handles = new BlockHandles(this);
            this.linkEditor = new FloatingLinkEditor(this);
        }
    }

    loadValue(value) {
        const editor = this.editor;
        if (value && value.root && Array.isArray(value.root.children) && value.root.children.length) {
            try {
                editor.setEditorState(editor.parseEditorState(normalizeState(value)));
                return;
            } catch (e) {
                console.error("[lexical] invalid state", e);
            }
        }
        editor.update(
            () => {
                const root = L.$getRoot();
                root.clear();
                root.append(L.$createParagraphNode());
            },
            { tag: "history-merge" }
        );
    }

    registerCore() {
        const editor = this.editor;
        const add = (fn) => fn && this.cleanups.push(fn);
        add(L.registerRichText(editor));
        add(L.registerHistory(editor, L.createEmptyHistoryState(), 1000));
        add(L.registerList(editor));
        add(L.registerCheckList?.(editor));
        if (!this.opts.readOnly) {
            add(L.registerMarkdownShortcuts(editor, TRANSFORMERS));
        }
        add(
            editor.registerCommand(
                L.TOGGLE_LINK_COMMAND,
                (payload) => {
                    $toggleLink(payload);
                    return true;
                },
                L.COMMAND_PRIORITY_LOW
            )
        );
        // Tab indentation (Lexical's TabIndentationPlugin)
        add(
            editor.registerCommand(
                L.KEY_TAB_COMMAND,
                (event) => {
                    const selection = L.$getSelection();
                    if (!L.$isRangeSelection(selection)) {
                        return false;
                    }
                    event.preventDefault();
                    return editor.dispatchCommand(event.shiftKey ? L.OUTDENT_CONTENT_COMMAND : L.INDENT_CONTENT_COMMAND, undefined);
                },
                L.COMMAND_PRIORITY_EDITOR
            )
        );
        // Paste a URL on selected text -> link
        add(
            editor.registerCommand(
                L.PASTE_COMMAND,
                (event) => {
                    const selection = L.$getSelection();
                    if (!L.$isRangeSelection(selection) || selection.isCollapsed() || !event.clipboardData) {
                        return false;
                    }
                    const text = event.clipboardData.getData("text");
                    try {
                        new URL(text);
                    } catch {
                        return false;
                    }
                    if (selection.getNodes().some((n) => L.$isElementNode(n))) {
                        return false;
                    }
                    editor.dispatchCommand(L.TOGGLE_LINK_COMMAND, { fields: { doc: null, linkType: "custom", newTab: false, url: text } });
                    event.preventDefault();
                    return true;
                },
                L.COMMAND_PRIORITY_LOW
            )
        );
        this.registerDecoratorSelection();
        // change listener + placeholder
        add(
            editor.registerUpdateListener(({ editorState, dirtyElements, dirtyLeaves, tags }) => {
                this.updatePlaceholder(editorState);
                if (dirtyElements.size === 0 && dirtyLeaves.size === 0) {
                    return;
                }
                if (tags.has("history-merge") && !this.touched) {
                    return;
                }
                this.touched = true;
                clearTimeout(this.changeTimer);
                this.changeTimer = setTimeout(() => this.opts.onChange?.(editorState.toJSON()), 150);
            })
        );
        this.updatePlaceholder(editor.getEditorState());
    }

    flush() {
        if (this.changeTimer) {
            clearTimeout(this.changeTimer);
            this.changeTimer = null;
            this.opts.onChange?.(this.editor.getEditorState().toJSON());
        }
    }

    updatePlaceholder(editorState) {
        const placeholder = this.opts.placeholder;
        if (!placeholder) {
            return;
        }
        const empty = editorState.read(() => {
            const root = L.$getRoot();
            const first = root.getFirstChild();
            return root.getChildrenSize() === 1 && L.$isParagraphNode(first) && first.getTextContentSize() === 0 && first.getChildrenSize() === 0;
        });
        placeholder.style.display = empty && !this.opts.readOnly ? "" : "none";
    }

    registerDecoratorSelection() {
        const editor = this.editor;
        const root = this.opts.contentEditable;
        const clear = () => root.querySelectorAll(".decorator-selected").forEach((e) => e.classList.remove("decorator-selected"));
        this.cleanups.push(
            editor.registerCommand(
                L.CLICK_COMMAND,
                (event) => {
                    clear();
                    const target = event.target;
                    const decoratorEl = target?.closest?.('[data-lexical-decorator="true"]');
                    if (!decoratorEl) {
                        return false;
                    }
                    if (target.closest("button, textarea, input, .react-select, [role=button], a")) {
                        return true;
                    }
                    const node = L.$getNearestNodeFromDOMNode(decoratorEl);
                    if (!node || !L.$isDecoratorNode(node)) {
                        return false;
                    }
                    const selection = L.$createNodeSelection();
                    selection.add(node.getKey());
                    L.$setSelection(selection);
                    decoratorEl.classList.add("decorator-selected");
                    return true;
                },
                L.COMMAND_PRIORITY_LOW
            ),
            editor.registerCommand(
                L.SELECTION_CHANGE_COMMAND,
                () => {
                    clear();
                    const selection = L.$getSelection();
                    if (L.$isNodeSelection(selection)) {
                        const nodes = selection.getNodes();
                        if (nodes.length === 1 && L.$isDecoratorNode(nodes[0])) {
                            editor.getElementByKey(nodes[0].getKey())?.classList.add("decorator-selected");
                            return true;
                        }
                    }
                    return false;
                },
                L.COMMAND_PRIORITY_LOW
            ),
            ...[L.KEY_DELETE_COMMAND, L.KEY_BACKSPACE_COMMAND].map((cmd) =>
                editor.registerCommand(
                    cmd,
                    (event) => {
                        const selection = L.$getSelection();
                        if (L.$isNodeSelection(selection)) {
                            event.preventDefault();
                            selection.getNodes().forEach((n) => n.remove());
                            return true;
                        }
                        return false;
                    },
                    L.COMMAND_PRIORITY_LOW
                )
            )
        );
    }

    /** Insert or replace an upload / relationship node. */
    insertDecorator(kind, data, replaceKey = null) {
        this.editor.update(() => {
            const node = kind === "upload" ? $createUploadNode({ data: { fields: null, ...data } }) : $createRelationshipNode({ data });
            if (replaceKey) {
                L.$getNodeByKey(replaceKey)?.replace(node);
                return;
            }
            let selection = L.$getSelection() || this.lastSelection?.clone();
            if (!selection) {
                L.$getRoot().append(node);
                return;
            }
            if (!L.$isRangeSelection(selection)) {
                L.$getRoot().append(node);
                return;
            }
            L.$setSelection(selection);
            const focusNode = selection.focus.getNode();
            const block = L.$isParagraphNode(focusNode) ? focusNode : focusNode.getTopLevelElement?.();
            L.$insertNodeToNearestRoot(node);
            if (block && L.$isParagraphNode(block) && block.getTextContentSize() === 0 && block.isAttached()) {
                block.remove();
            }
        });
    }

    /** Wrap the selection in a link and open the "Edit Link" drawer. */
    createLink() {
        const editor = this.editor;
        let text = "";
        editor.getEditorState().read(() => {
            const sel = L.$getSelection();
            text = L.$isRangeSelection(sel) ? sel.getTextContent() : "";
        });
        this.rememberSelection();
        editor.dispatchCommand(L.TOGGLE_LINK_COMMAND, { fields: { doc: null, linkType: "custom", newTab: false, url: "https://" }, text: null });
        setTimeout(() => this.linkEditor?.openDrawer(text), 0);
    }

    rememberSelection() {
        this.editor.getEditorState().read(() => {
            const selection = L.$getSelection();
            this.lastSelection = selection ? selection.clone() : null;
        });
    }

    destroy() {
        this.flush();
        this.inlineToolbar?.destroy();
        this.fixedToolbar?.destroy();
        this.slashMenu?.destroy();
        this.handles?.destroy();
        this.linkEditor?.destroy();
        for (const fn of this.cleanups) {
            try {
                fn();
            } catch {
                // ignore
            }
        }
        this.editor.setRootElement(null);
    }
}

// ----------------------------------------------------------------------
// Toolbars (shared by the inline toolbar and the FixedToolbarFeature)
// ----------------------------------------------------------------------
function addGroup(host) {
    return {
        key: "add",
        type: "dropdown",
        icon: '<svg fill="none" height="20" viewBox="0 0 20 20" width="20" xmlns="http://www.w3.org/2000/svg"><path d="M5 10h10" stroke="currentColor"/><path d="M10 15V5" stroke="currentColor"/></svg>',
        items: [
            { key: "relationship", label: "Relationship", icon: ICONS.relationship, isActive: () => false, onSelect: () => host.openRelationshipDrawer?.({ replace: false }) },
            { key: "upload", label: "Upload", icon: ICONS.upload, isActive: () => false, onSelect: () => host.openUploadDrawer?.({ replace: false }) },
            {
                key: "horizontalRule",
                label: "Horizontal Rule",
                icon: ICONS.horizontalRule,
                isActive: () => false,
                onSelect: (editor) =>
                    editor.update(() => {
                        if (L.$isRangeSelection(L.$getSelection())) {
                            L.$insertNodeToNearestRoot($createHorizontalRuleNode());
                        }
                    }),
            },
        ],
    };
}

class ToolbarBase {
    constructor(pe, { fixed }) {
        this.pe = pe;
        this.editor = pe.editor;
        this.fixed = fixed;
        const groups = toolbarGroups({ createLink: () => pe.createLink() });
        this.groups = fixed ? [addGroup(pe.host), ...groups] : groups;
        this.buttons = [];
        this.dropdowns = [];
        this.prefix = fixed ? "fixed-toolbar" : "inline-toolbar-popup";
    }

    /** Build the groups (buttons / dropdown triggers) into `root`. */
    buildGroups(root) {
        this.groups.forEach((group, gi) => {
            const g = el("div", `${this.prefix}__group ${this.prefix}__group-${group.key}`, { "data-toolbar-group-key": group.key });
            if (group.type === "dropdown") {
                const btn = el("button", `toolbar-popup__dropdown toolbar-popup__dropdown-${group.key}`, {
                    "aria-label": `${group.key} dropdown`,
                    "data-dropdown-key": group.key,
                    type: "button",
                });
                this.renderTrigger(btn, group, null);
                btn.addEventListener("mousedown", (e) => e.preventDefault());
                btn.addEventListener("click", (e) => {
                    e.preventDefault();
                    this.toggleDropdown(group, btn);
                });
                g.appendChild(btn);
                this.dropdowns.push({ group, btn });
            } else {
                for (const item of group.items) {
                    const btn = el("button", `toolbar-popup__button toolbar-popup__button-${item.key}`, {
                        "data-button-key": item.key,
                        type: "button",
                        title: item.label,
                    });
                    btn.innerHTML = item.icon;
                    btn.addEventListener("mousedown", (e) => e.preventDefault());
                    btn.addEventListener("click", (e) => {
                        e.preventDefault();
                        if (!btn.classList.contains("disabled")) {
                            this.run(item, btn.classList.contains("active"));
                        }
                    });
                    g.appendChild(btn);
                    this.buttons.push({ item, btn });
                }
            }
            if (gi < this.groups.length - 1) {
                g.appendChild(el("div", "divider"));
            }
            root.appendChild(g);
        });
    }

    renderTrigger(btn, group, activeItem) {
        const label = this.fixed && activeItem
            ? `<span class="toolbar-popup__dropdown-label">${activeItem.label.length > 25 ? `${activeItem.label.slice(0, 25)}...` : activeItem.label}</span>`
            : "";
        const html = `${activeItem ? activeItem.icon : group.icon}${label}<i class="toolbar-popup__dropdown-caret"></i>`;
        // Only touch the DOM when needed: replacing the content between mousedown
        // and mouseup would swallow the click event.
        if (btn._payloadHtml !== html) {
            btn._payloadHtml = html;
            btn.innerHTML = html;
        }
    }

    run(item, isActive) {
        this.editor.focus(() => {
            this.editor.update(() => L.$addUpdateTag?.("toolbar"));
            item.onSelect(this.editor, isActive);
        });
    }

    activeItem(group, sel) {
        return group.items.find((item) => {
            try {
                return item.isActive?.(sel);
            } catch {
                return false;
            }
        });
    }

    /** Refresh active / enabled states from a selection (inside a read). */
    updateStates(sel) {
        for (const { item, btn } of this.buttons) {
            let active = false;
            let enabled = true;
            try {
                active = item.isActive?.(sel) || false;
                enabled = item.isEnabled ? item.isEnabled(sel) : true;
            } catch {
                // ignore
            }
            btn.className = `toolbar-popup__button${enabled ? "" : " disabled"}${active ? " active" : ""} toolbar-popup__button-${item.key}`;
        }
        for (const { group, btn } of this.dropdowns) {
            if (this.openDropdown?.btn === btn) {
                continue;
            }
            this.renderTrigger(btn, group, this.activeItem(group, sel));
        }
    }

    toggleDropdown(group, btn) {
        if (this.openDropdown) {
            const same = this.openDropdown.group === group;
            this.closeDropdown();
            if (same) {
                return;
            }
        }
        const items = el("div", `toolbar-popup__dropdown-items${this.fixed ? " fixed-toolbar__dropdown-items" : ""}`);
        let active = null;
        this.editor.getEditorState().read(() => {
            const sel = L.$getSelection();
            active = sel ? this.activeItem(group, sel) : null;
        });
        for (const item of group.items) {
            const isActive = active === item;
            const b = el("button", `btn toolbar-popup__dropdown-item${isActive ? " active" : ""} toolbar-popup__dropdown-item-${item.key} btn--icon btn--icon-style-none btn--size-medium btn--icon-position-left btn--has-tooltip btn--withoutPopup btn--style-none btn--withoutPopup`, {
                type: "button",
                "aria-label": item.label,
                title: item.label,
                "data-item-key": item.key,
            });
            b.innerHTML = `<span class="btn__content"><span class="btn__label"><span class="text">${item.label}</span></span><span class="btn__icon">${item.icon}</span></span>`;
            b.addEventListener("mousedown", (e) => e.preventDefault());
            b.addEventListener("click", (e) => {
                e.preventDefault();
                this.closeDropdown();
                this.run(item, isActive);
            });
            items.appendChild(b);
        }
        document.body.appendChild(items);
        const rect = btn.getBoundingClientRect();
        items.style.top = `${rect.top + window.scrollY + btn.offsetHeight + 5}px`;
        items.style.left = `${Math.min(rect.left - 5, window.innerWidth - items.offsetWidth - 20)}px`;
        btn.classList.add("active");
        const onDocClick = (e) => {
            if (!btn.contains(e.target)) {
                this.closeDropdown();
            }
        };
        setTimeout(() => document.addEventListener("click", onDocClick), 0);
        this.openDropdown = { group, btn, items, onDocClick };
    }

    closeDropdown() {
        if (!this.openDropdown) {
            return;
        }
        const { btn, items, onDocClick } = this.openDropdown;
        document.removeEventListener("click", onDocClick);
        items.remove();
        btn.classList.remove("active");
        this.openDropdown = null;
    }
}

/** Payload's FixedToolbarFeature: toolbar pinned above the editor. */
class FixedToolbar extends ToolbarBase {
    constructor(pe) {
        super(pe, { fixed: true });
        this.el = pe.opts.fixedToolbar;
        this.el.innerHTML = "";
        this.buildGroups(this.el);
        const refresh = () =>
            this.editor.getEditorState().read(() => {
                const sel = L.$getSelection();
                if (sel) {
                    this.updateStates(sel);
                }
            });
        this.onMouseUp = refresh;
        document.addEventListener("mouseup", this.onMouseUp);
        this.unregister = L.mergeRegister(
            this.editor.registerUpdateListener(refresh),
            this.editor.registerCommand(
                L.SELECTION_CHANGE_COMMAND,
                () => {
                    refresh();
                    return false;
                },
                L.COMMAND_PRIORITY_LOW
            )
        );
        refresh();
    }

    destroy() {
        this.closeDropdown();
        document.removeEventListener("mouseup", this.onMouseUp);
        this.unregister();
        this.el.innerHTML = "";
    }
}

/** Payload's InlineToolbarFeature: floating toolbar over the text selection. */
class InlineToolbar extends ToolbarBase {
    constructor(pe) {
        super(pe, { fixed: false });
        this.anchor = pe.opts.anchor;
        const root = el("div", "inline-toolbar-popup");
        root.appendChild(el("div", "caret"));
        this.caret = root.firstChild;
        this.buildGroups(root);
        this.el = root;
        this.anchor.appendChild(root);
        this.onSelectionChange = () => this.update();
        this.onMouseUp = () => {
            this.el.style.pointerEvents = "auto";
            this.update();
        };
        this.onMouseMove = (e) => {
            if ((e.buttons === 1 || e.buttons === 3) && !this.el.contains(e.target) && this.el.style.opacity === "1") {
                this.el.style.opacity = "0";
                this.el.style.pointerEvents = "none";
            }
        };
        this.onResize = () => this.update();
        document.addEventListener("selectionchange", this.onSelectionChange);
        document.addEventListener("mouseup", this.onMouseUp);
        document.addEventListener("mousemove", this.onMouseMove);
        window.addEventListener("resize", this.onResize);
        this.unregister = L.mergeRegister(
            this.editor.registerUpdateListener(() => this.update()),
            this.editor.registerCommand(
                L.SELECTION_CHANGE_COMMAND,
                () => {
                    this.update();
                    return false;
                },
                L.COMMAND_PRIORITY_LOW
            )
        );
        this.hide();
    }

    hide() {
        this.el.style.opacity = "0";
        this.el.style.transform = "translate(-10000px, -10000px)";
        this.el.style.pointerEvents = "none";
        this.closeDropdown();
    }

    update() {
        const editor = this.editor;
        if (!editor.isEditable() || editor.isComposing()) {
            return;
        }
        editor.getEditorState().read(() => {
            const sel = L.$getSelection();
            const native = window.getSelection();
            const root = editor.getRootElement();
            if (!L.$isRangeSelection(sel) || !native || native.isCollapsed || !root || !root.contains(native.anchorNode)) {
                this.hide();
                return;
            }
            const text = sel.getTextContent();
            if (!text.replace(/\n/g, "") || !sel.getNodes().some((n) => L.$isTextNode(n))) {
                this.hide();
                return;
            }
            this.updateStates(sel);
            let rangeRect;
            if (native.anchorNode === root) {
                let inner = root;
                while (inner.firstElementChild) {
                    inner = inner.firstElementChild;
                }
                rangeRect = inner.getBoundingClientRect();
            } else {
                rangeRect = native.getRangeAt(0).getBoundingClientRect();
            }
            const linkVisible = this.pe.linkEditor?.el.style.opacity === "1";
            this.el.style.pointerEvents = "auto";
            const flipped = setFloatingElemPosition({
                alwaysDisplayOnTop: linkVisible,
                anchorElem: this.anchor,
                floatingElem: this.el,
                horizontalPosition: "center",
                targetRect: rangeRect,
            });
            setFloatingElemPosition({
                anchorElem: this.el,
                anchorFlippedOffset: flipped,
                floatingElem: this.caret,
                horizontalOffset: 5,
                horizontalPosition: "center",
                specialHandlingForCaret: true,
                targetRect: rangeRect,
                verticalGap: 8,
            });
        });
    }

    destroy() {
        this.closeDropdown();
        document.removeEventListener("selectionchange", this.onSelectionChange);
        document.removeEventListener("mouseup", this.onMouseUp);
        document.removeEventListener("mousemove", this.onMouseMove);
        window.removeEventListener("resize", this.onResize);
        this.unregister();
        this.el.remove();
    }
}

// ----------------------------------------------------------------------
// Slash menu
// ----------------------------------------------------------------------
const PUNCTUATION = "\\.,\\+\\*\\?\\$\\@\\|#{}\\(\\)\\^\\-\\[\\]\\\\/!%'\"~=<>_:;";
const VALID_CHARS = `[^/${PUNCTUATION}\\s]`;
const SLASH_RE = new RegExp(`(^|\\s|\\()([/]((?:${VALID_CHARS}){0,75}))$`);

class SlashMenu {
    constructor(pe) {
        this.pe = pe;
        this.editor = pe.editor;
        this.anchor = pe.opts.anchor;
        this.groups = slashGroups(pe.host);
        this.match = null;
        this.selectedIndex = 0;
        this.container = el("div", "", { id: "slash-menu", "aria-label": "Slash menu", role: "listbox" });
        this.container.style.cssText = "display:block;position:absolute";
        const E = this.editor;
        this.unregister = L.mergeRegister(
            E.registerUpdateListener(({ editorState }) => editorState.read(() => this.detect())),
            E.registerCommand(L.KEY_ARROW_DOWN_COMMAND, (e) => this.move(e, 1), L.COMMAND_PRIORITY_NORMAL),
            E.registerCommand(L.KEY_ARROW_UP_COMMAND, (e) => this.move(e, -1), L.COMMAND_PRIORITY_NORMAL),
            E.registerCommand(L.KEY_ENTER_COMMAND, (e) => this.enter(e), L.COMMAND_PRIORITY_NORMAL),
            E.registerCommand(L.KEY_TAB_COMMAND, (e) => this.enter(e), L.COMMAND_PRIORITY_NORMAL),
            E.registerCommand(
                L.KEY_ESCAPE_COMMAND,
                () => {
                    if (!this.isOpen) {
                        return false;
                    }
                    this.close();
                    return true;
                },
                L.COMMAND_PRIORITY_LOW
            )
        );
        this.onScroll = () => this.isOpen && this.position();
        document.addEventListener("scroll", this.onScroll, true);
    }

    get isOpen() {
        return Boolean(this.match);
    }

    detect() {
        const selection = L.$getSelection();
        if (!L.$isRangeSelection(selection) || !selection.isCollapsed()) {
            if (this.match && !this.match.forced) {
                this.close();
            }
            return;
        }
        const anchor = selection.anchor;
        if (anchor.type !== "text") {
            if (this.match?.forced) {
                return;
            }
            this.close();
            return;
        }
        const node = anchor.getNode();
        if (!node.isSimpleText()) {
            this.close();
            return;
        }
        const text = node.getTextContent().slice(0, anchor.offset);
        const m = SLASH_RE.exec(text);
        if (!m) {
            this.close();
            return;
        }
        const leadOffset = m.index + m[1].length;
        this.open({ leadOffset, matchingString: m[3], replaceableString: m[2] });
    }

    open(match, forced = false) {
        const changed = !this.match || this.match.matchingString !== match.matchingString;
        this.match = { ...match, forced };
        if (changed) {
            this.selectedIndex = 0;
        }
        this.render();
        if (!this.container.parentElement) {
            this.anchor.appendChild(this.container);
            this.editor.getRootElement()?.setAttribute("aria-controls", "slash-menu");
        }
        requestAnimationFrame(() => this.position());
    }

    openFromHandle() {
        this.open({ leadOffset: 0, matchingString: "", replaceableString: "" }, true);
    }

    close() {
        this.match = null;
        this.container.remove();
        this.editor.getRootElement()?.removeAttribute("aria-controls");
        this.editor.getRootElement()?.removeAttribute("aria-activedescendant");
    }

    filtered() {
        const q = this.match?.matchingString || "";
        if (!q) {
            return this.groups.map((g) => ({ ...g, items: g.items.filter(Boolean) }));
        }
        const nq = q.toLowerCase().replace(/[\s\-_]/g, "");
        let re;
        try {
            re = new RegExp(q, "i");
        } catch {
            re = null;
        }
        const matches = (s) => (re && re.test(s)) || s.toLowerCase().replace(/[\s\-_]/g, "").includes(nq);
        return this.groups
            .map((g) => ({ ...g, items: g.items.filter((i) => i && (matches(i.label) || (i.keywords || []).some(matches))) }))
            .filter((g) => g.items.length);
    }

    flat() {
        return this.filtered().flatMap((g) => g.items);
    }

    render() {
        const groups = this.filtered();
        this.container.innerHTML = "";
        if (!groups.length) {
            return;
        }
        const popup = el("div", "slash-menu-popup");
        let index = 0;
        for (const group of groups) {
            const g = el("div", `slash-menu-popup__group slash-menu-popup__group-${group.key}`);
            const title = el("div", "slash-menu-popup__group-title");
            title.textContent = group.label;
            g.appendChild(title);
            for (const item of group.items) {
                const i = index++;
                const selected = i === this.selectedIndex;
                const b = el("button", `slash-menu-popup__item slash-menu-popup__item-${item.key}${selected ? " slash-menu-popup__item--selected" : ""}`, {
                    "aria-selected": selected ? "true" : "false",
                    id: `slash-menu-popup__item-${item.key}`,
                    role: "option",
                    tabindex: "-1",
                    type: "button",
                });
                const label = item.label.length > 25 ? `${item.label.slice(0, 25)}...` : item.label;
                b.innerHTML = `${item.icon}<span class="slash-menu-popup__item-text">${label}</span>`;
                b.addEventListener("mouseenter", () => {
                    this.selectedIndex = i;
                    this.render();
                });
                b.addEventListener("mousedown", (e) => e.preventDefault());
                b.addEventListener("click", () => this.select(item));
                g.appendChild(b);
                if (selected) {
                    this.editor.getRootElement()?.setAttribute("aria-activedescendant", b.id);
                }
            }
            popup.appendChild(g);
        }
        this.container.appendChild(popup);
    }

    getRect() {
        const domSel = window.getSelection();
        if (!domSel || !domSel.anchorNode) {
            return null;
        }
        const range = document.createRange();
        try {
            if (domSel.anchorNode.nodeType === Node.TEXT_NODE) {
                range.setStart(domSel.anchorNode, Math.min(this.match.leadOffset, domSel.anchorNode.length));
                range.setEnd(domSel.anchorNode, Math.max(domSel.anchorOffset, 1));
            } else {
                range.selectNodeContents(domSel.anchorNode);
            }
        } catch {
            return null;
        }
        return range.getBoundingClientRect();
    }

    position() {
        const rect = this.getRect();
        if (!rect) {
            return;
        }
        const VERTICAL_OFFSET = 32;
        const a = this.anchor.getBoundingClientRect();
        let { left, top } = rect;
        const rawTop = top;
        top -= a.top + window.scrollY;
        left -= a.left + window.scrollX;
        const c = this.container;
        c.style.left = `${left + window.scrollX}px`;
        c.style.height = `${rect.height}px`;
        c.style.width = `${rect.width}px`;
        const menu = c.firstChild;
        if (menu) {
            const m = menu.getBoundingClientRect();
            const root = this.editor.getRootElement().getBoundingClientRect();
            if (rect.left + m.width > root.right) {
                c.style.left = `${root.right - m.width - a.left}px`;
            }
            const offBottom = rawTop + m.height + VERTICAL_OFFSET > window.innerHeight;
            const offTop = rawTop < 0;
            c.style.top = offBottom && !offTop ? `${top + VERTICAL_OFFSET - m.height + window.scrollY - (rect.height + 24)}px` : `${top + window.scrollY + VERTICAL_OFFSET}px`;
        }
    }

    move(event, delta) {
        if (!this.isOpen) {
            return false;
        }
        const items = this.flat();
        if (!items.length) {
            return false;
        }
        event?.preventDefault();
        event?.stopImmediatePropagation?.();
        this.selectedIndex = (this.selectedIndex + delta + items.length) % items.length;
        this.render();
        this.container.querySelector(".slash-menu-popup__item--selected")?.scrollIntoView({ block: "nearest" });
        return true;
    }

    enter(event) {
        if (!this.isOpen) {
            return false;
        }
        const item = this.flat()[this.selectedIndex];
        if (!item) {
            return false;
        }
        event?.preventDefault();
        event?.stopImmediatePropagation?.();
        this.select(item);
        return true;
    }

    select(item) {
        const match = this.match;
        this.close();
        this.editor.update(() => {
            if (!match || match.forced) {
                return;
            }
            const selection = L.$getSelection();
            if (!L.$isRangeSelection(selection) || !selection.isCollapsed()) {
                return;
            }
            const anchor = selection.anchor;
            if (anchor.type !== "text") {
                return;
            }
            const node = anchor.getNode();
            const end = anchor.offset;
            const start = end - match.replaceableString.length;
            if (start < 0) {
                return;
            }
            let target;
            if (start === 0) {
                [target] = node.splitText(end);
            } else {
                [, target] = node.splitText(start, end);
            }
            target?.remove();
        });
        setTimeout(() => {
            this.pe.rememberSelection();
            item.onSelect(this.editor, false);
        }, 0);
    }

    destroy() {
        document.removeEventListener("scroll", this.onScroll, true);
        this.unregister();
        this.close();
    }
}

// ----------------------------------------------------------------------
// Add-block "+" handle and draggable block handle
// ----------------------------------------------------------------------
class BlockHandles {
    constructor(pe) {
        this.pe = pe;
        this.editor = pe.editor;
        this.anchor = pe.opts.anchor;
        this.scroller = this.anchor.parentElement;
        this.add = el("button", "icon add-block-menu", { "aria-label": "Add block", type: "button" });
        this.add.innerHTML = '<div class="icon"></div>';
        this.drag = el("button", "icon draggable-block-menu", { "aria-label": "Drag to move", draggable: "true", type: "button" });
        this.drag.innerHTML = '<div class="icon"></div>';
        this.line = el("div", "draggable-block-target-line");
        for (const h of [this.drag, this.line, this.add]) {
            h.style.opacity = "0";
            h.style.transform = "translate(-10000px, -10000px)";
            this.anchor.appendChild(h);
        }
        this.hovered = null;
        this.onMouseMove = (e) => this.mouseMove(e);
        this.onDragOver = (e) => this.dragOver(e);
        this.onDrop = (e) => this.drop(e);
        document.addEventListener("mousemove", this.onMouseMove);
        document.addEventListener("dragover", this.onDragOver);
        document.addEventListener("drop", this.onDrop);
        this.add.addEventListener("mousedown", (e) => e.preventDefault());
        this.add.addEventListener("click", (e) => this.addClick(e));
        this.drag.addEventListener("dragstart", (e) => this.dragStart(e));
        this.drag.addEventListener("dragend", () => this.dragEnd());
    }

    get gutter() {
        return this.anchor.closest(".rich-text-lexical")?.classList.contains("rich-text-lexical--show-gutter");
    }

    blocks() {
        const root = this.editor.getRootElement();
        return root ? Array.from(root.children).filter((c) => c.nodeType === 1) : [];
    }

    blockAt(y) {
        const blocks = this.blocks();
        for (const block of blocks) {
            const r = block.getBoundingClientRect();
            const style = getComputedStyle(block);
            const top = r.top - parseFloat(style.marginTop || 0);
            const bottom = r.bottom + parseFloat(style.marginBottom || 0);
            if (y >= top && y <= bottom) {
                return block;
            }
        }
        return null;
    }

    nearestBlock(y) {
        const blocks = this.blocks();
        if (!blocks.length) {
            return null;
        }
        let best = null;
        let bestDist = Infinity;
        for (const block of blocks) {
            const r = block.getBoundingClientRect();
            const d = y < r.top ? r.top - y : y > r.bottom ? y - r.bottom : 0;
            if (d < bestDist) {
                bestDist = d;
                best = block;
            }
        }
        return best;
    }

    inRange(e, hBuf = 50, vBuf = 25) {
        const r = this.scroller.getBoundingClientRect();
        return !(e.clientY < r.top - vBuf || e.clientY > r.bottom + vBuf || e.clientX < r.left - hBuf || e.clientX > r.right + hBuf);
    }

    position(handle, block, leftOffset) {
        if (!block) {
            handle.style.opacity = "0";
            handle.style.transform = "translate(-10000px, -10000px)";
            return;
        }
        const t = block.getBoundingClientRect();
        const h = handle.getBoundingClientRect();
        const a = this.anchor.getBoundingClientRect();
        const isBlockStyle = ["LexicalEditorTheme__block", "LexicalEditorTheme__upload", "LexicalEditorTheme__relationship"].some(
            (c) => block.classList.contains(c) || block.firstElementChild?.classList.contains(c)
        );
        let top;
        if (!isBlockStyle && block.tagName !== "HR") {
            const lh = parseInt(getComputedStyle(block).lineHeight, 10) || 0;
            top = t.top + (lh - h.height) / 2 - a.top;
        } else {
            top = t.top + 8 - a.top;
        }
        handle.style.opacity = "1";
        handle.style.transform = `translate(${leftOffset}px, ${top}px)`;
    }

    mouseMove(e) {
        if (this.dragging) {
            return;
        }
        if (e.target?.closest?.(".draggable-block-menu, .add-block-menu")) {
            return;
        }
        if (!this.inRange(e)) {
            this.hovered = null;
            this.position(this.add, null);
            this.position(this.drag, null);
            return;
        }
        const block = this.blockAt(e.clientY);
        if (!block) {
            return;
        }
        this.hovered = block;
        const gutter = this.gutter;
        this.position(this.add, block, gutter ? 12 : -24);
        const isEmptyParagraph = block.tagName === "P" && !block.textContent;
        this.position(this.drag, isEmptyParagraph ? null : block, gutter ? -8 : -44);
    }

    addClick(e) {
        e.preventDefault();
        e.stopPropagation();
        const block = this.hovered;
        if (!block) {
            return;
        }
        let targetKey = null;
        this.editor.update(() => {
            const node = L.$getNearestNodeFromDOMNode(block);
            if (!node) {
                return;
            }
            const top = node.getTopLevelElementOrThrow ? node.getTopLevelElementOrThrow() : node;
            if (top.getType() !== "paragraph" || top.getTextContent() !== "") {
                const p = L.$createParagraphNode();
                top.insertAfter(p);
                targetKey = p.getKey();
                p.select();
            } else {
                targetKey = top.getKey();
                top.select();
            }
        });
        setTimeout(() => {
            this.editor.focus();
            const elem = targetKey && this.editor.getElementByKey(targetKey);
            if (elem) {
                this.hovered = elem;
                this.position(this.add, elem, this.gutter ? 12 : -24);
            }
            this.pe.slashMenu?.openFromHandle();
        }, 10);
    }

    dragStart(e) {
        const block = this.hovered;
        if (!block || !e.dataTransfer) {
            return;
        }
        let key = null;
        this.editor.getEditorState().read(() => {
            key = L.$getNearestNodeFromDOMNode(block)?.getTopLevelElementOrThrow?.().getKey() || L.$getNearestNodeFromDOMNode(block)?.getKey();
        });
        e.dataTransfer.setDragImage(block, 0, 0);
        e.dataTransfer.setData("application/x-lexical-drag-block", key || "");
        this.draggedKey = key;
        this.dragging = true;
    }

    dragOver(e) {
        if (!this.dragging) {
            return;
        }
        if (!this.inRange(e, 100, 50)) {
            this.line.style.opacity = "0";
            return;
        }
        const target = this.nearestBlock(e.clientY);
        if (!target) {
            return;
        }
        e.preventDefault();
        const r = target.getBoundingClientRect();
        const a = this.anchor.getBoundingClientRect();
        const style = getComputedStyle(target);
        const below = e.clientY >= r.top + r.height / 2;
        const lineTop = below ? r.bottom + parseFloat(style.marginBottom || 0) / 2 : r.top - parseFloat(style.marginTop || 0) / 2;
        const offset = this.gutter ? "3rem" : "0px";
        this.line.style.width = `calc(${a.width}px - ${offset})`;
        this.line.style.opacity = ".8";
        this.line.style.transform = `translate(0px, calc(${lineTop - a.top}px - 2px))`;
        this.dropTarget = { target, below };
    }

    drop(e) {
        if (!this.dragging || !this.dropTarget) {
            return;
        }
        e.preventDefault();
        const { target, below } = this.dropTarget;
        const key = this.draggedKey;
        this.editor.update(() => {
            const dragged = L.$getNodeByKey(key);
            const targetNode = L.$getNearestNodeFromDOMNode(target);
            const top = targetNode?.getTopLevelElementOrThrow?.() || targetNode;
            if (!dragged || !top || top.is(dragged)) {
                return;
            }
            if (below) {
                top.insertAfter(dragged);
            } else {
                top.insertBefore(dragged);
            }
        });
        this.dragEnd();
    }

    dragEnd() {
        this.dragging = false;
        this.dropTarget = null;
        this.line.style.opacity = "0";
        this.line.style.transform = "translate(-10000px, -10000px)";
    }

    destroy() {
        document.removeEventListener("mousemove", this.onMouseMove);
        document.removeEventListener("dragover", this.onDragOver);
        document.removeEventListener("drop", this.onDrop);
        this.add.remove();
        this.drag.remove();
        this.line.remove();
    }
}

// ----------------------------------------------------------------------
// Floating link editor
// ----------------------------------------------------------------------
class FloatingLinkEditor {
    constructor(pe) {
        this.pe = pe;
        this.editor = pe.editor;
        this.anchor = pe.opts.anchor;
        this.el = el("div", "link-editor");
        this.el.style.opacity = "0";
        this.el.style.transform = "translate(-10000px, -10000px)";
        this.anchor.appendChild(this.el);
        this.linkKey = null;
        this.unregister = L.mergeRegister(
            this.editor.registerUpdateListener(({ editorState }) => editorState.read(() => this.update())),
            this.editor.registerCommand(
                L.SELECTION_CHANGE_COMMAND,
                () => {
                    this.update();
                    return false;
                },
                L.COMMAND_PRIORITY_LOW
            ),
            this.editor.registerCommand(
                L.KEY_ESCAPE_COMMAND,
                () => {
                    if (this.el.style.opacity === "1") {
                        this.hide();
                        return true;
                    }
                    return false;
                },
                L.COMMAND_PRIORITY_HIGH
            )
        );
    }

    hide() {
        this.el.style.opacity = "0";
        this.el.style.transform = "translate(-10000px, -10000px)";
        this.linkKey = null;
    }

    update() {
        const selection = L.$getSelection();
        if (!L.$isRangeSelection(selection)) {
            this.hide();
            return;
        }
        const node = selection.isBackward() ? selection.focus.getNode() : selection.anchor.getNode();
        const link = L.$findMatchingParent(node, $isPayloadLinkNode);
        if (!link) {
            this.hide();
            return;
        }
        const others = selection.getNodes().filter((n) => !L.$isLineBreakNode?.(n));
        if (others.some((n) => {
            const p = L.$findMatchingParent(n, $isPayloadLinkNode);
            return !p || !p.is(link);
        })) {
            this.hide();
            return;
        }
        this.linkKey = link.getKey();
        const fields = link.getFields() || {};
        this.render(fields);
        const dom = this.editor.getElementByKey(link.getKey());
        if (!dom) {
            return;
        }
        const rect = dom.getBoundingClientRect();
        const target = { top: rect.top + 40, left: rect.left, right: rect.right, width: rect.width, height: rect.height };
        this.positionAt(target);
    }

    render(fields) {
        const editable = this.editor.isEditable();
        const wrap = el("div", "link-input");
        const a = el("a", "", { rel: "noopener noreferrer", target: "_blank" });
        if (fields.linkType === "internal" && fields.doc) {
            const collection = getCollection(fields.doc.relationTo);
            a.href = `/admin/collections/${fields.doc.relationTo}/${fields.doc.value}`;
            const doc = getCachedDoc(fields.doc.relationTo, fields.doc.value);
            a.textContent = `Linked to ${collection?.labels.singular || fields.doc.relationTo} - ${doc ? docTitle(collection, doc) : "Loading..."}`;
            if (!doc) {
                ensureDocs(fields.doc.relationTo, [fields.doc.value]).then(() => this.editor.getEditorState().read(() => this.update()));
            }
        } else {
            a.href = fields.url || "";
            a.textContent = fields.url || "";
        }
        if (fields.newTab) {
            a.insertAdjacentHTML("afterbegin", String(ICONS_EXTERNAL));
        }
        wrap.appendChild(a);
        if (editable) {
            const edit = el("button", "link-edit", { "aria-label": "Edit link", tabindex: "0", type: "button" });
            edit.innerHTML = EDIT_ICON;
            edit.addEventListener("mousedown", (e) => e.preventDefault());
            edit.addEventListener("click", (e) => {
                e.preventDefault();
                this.openDrawer();
            });
            const trash = el("button", "link-trash", { "aria-label": "Remove link", tabindex: "0", type: "button" });
            trash.innerHTML = CLOSE_ICON;
            trash.addEventListener("mousedown", (e) => e.preventDefault());
            trash.addEventListener("click", (e) => {
                e.preventDefault();
                this.editor.dispatchCommand(L.TOGGLE_LINK_COMMAND, null);
            });
            wrap.append(edit, trash);
        }
        this.el.innerHTML = "";
        this.el.appendChild(wrap);
    }

    positionAt(targetRect) {
        const floatingElem = this.el;
        const scrollerElem = this.anchor.parentElement;
        const a = this.anchor.getBoundingClientRect();
        const s = scrollerElem.getBoundingClientRect();
        const verticalGap = 10;
        const horizontalOffset = 5;
        let top = targetRect.top - verticalGap;
        let left = targetRect.left - horizontalOffset;
        floatingElem.style.width = "max-content";
        floatingElem.style.maxWidth = "none";
        const naturalWidth = floatingElem.scrollWidth;
        const availRight = s.right - left;
        const availLeft = left - s.left;
        let fr;
        if (naturalWidth <= availRight) {
            fr = floatingElem.getBoundingClientRect();
        } else {
            const useLeft = availLeft > availRight;
            const space = useLeft ? availLeft + targetRect.width : availRight;
            const w = Math.min(naturalWidth, space);
            if (w < naturalWidth) {
                floatingElem.style.width = `${w}px`;
                floatingElem.style.maxWidth = `${w}px`;
            }
            if (useLeft) {
                left = targetRect.right - w;
            }
            fr = floatingElem.getBoundingClientRect();
        }
        if (top < s.top) {
            top += fr.height + targetRect.height + verticalGap * 2;
        }
        if (left + fr.width > s.right) {
            left = s.right - fr.width - horizontalOffset;
        }
        top -= a.top;
        left -= a.left;
        floatingElem.style.opacity = "1";
        floatingElem.style.transform = `translate(${left}px, ${top}px)`;
    }

    async openDrawer(initialText) {
        const key = this.linkKey;
        let data = null;
        this.editor.getEditorState().read(() => {
            const link = key && L.$getNodeByKey(key);
            if (link) {
                data = { ...(link.getFields() || {}), id: link.getID(), text: initialText ?? link.getTextContent() };
            }
        });
        if (!data) {
            return;
        }
        this.pe.rememberSelection();
        const result = await this.pe.host.openLinkDrawer?.(data);
        if (!result) {
            return;
        }
        const { text, id, ...fields } = result;
        void id;
        this.editor.update(() => {
            const link = L.$getNodeByKey(key);
            if (!link) {
                return;
            }
            link.setFields(fields);
            if (text && text !== link.getTextContent()) {
                link.clear();
                link.append(L.$createTextNode(text));
            }
        });
    }

    destroy() {
        this.unregister();
        this.el.remove();
    }
}

const EDIT_ICON = '<svg class="icon icon--edit" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path class="stroke" d="M9.68531 4.62938H5.2634C4.92833 4.62938 4.60698 4.76248 4.37004 4.99942C4.13311 5.23635 4 5.5577 4 5.89278V14.7366C4 15.0717 4.13311 15.393 4.37004 15.63C4.60698 15.8669 4.92833 16 5.2634 16H14.1072C14.4423 16 14.7636 15.8669 15.0006 15.63C15.2375 15.393 15.3706 15.0717 15.3706 14.7366V10.3147M13.7124 4.39249C13.9637 4.14118 14.3046 4 14.66 4C15.0154 4 15.3562 4.14118 15.6075 4.39249C15.8588 4.6438 16 4.98464 16 5.34004C16 5.69544 15.8588 6.03629 15.6075 6.28759L9.91399 11.9817C9.76399 12.1316 9.57868 12.2413 9.37515 12.3008L7.56027 12.8314C7.50591 12.8472 7.44829 12.8482 7.39344 12.8341C7.33859 12.8201 7.28853 12.7915 7.24849 12.7515C7.20845 12.7115 7.17991 12.6614 7.16586 12.6066C7.15181 12.5517 7.15276 12.4941 7.16861 12.4397L7.69924 10.6249C7.75896 10.4215 7.86888 10.2364 8.01888 10.0866L13.7124 4.39249Z" stroke-linecap="square"/></svg>';
const CLOSE_ICON = '<svg class="icon icon--close-menu" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path class="stroke" d="M14 6L6 14M6 6L14 14" stroke-linecap="square"/></svg>';
const ICONS_EXTERNAL = '<svg class="icon icon--externalLink" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path class="stroke" d="M16 10.6667V14.6667C16 15.0203 15.8595 15.3594 15.6095 15.6095C15.3594 15.8595 15.0203 16 14.6667 16H5.33333C4.97971 16 4.64057 15.8595 4.39052 15.6095C4.14048 15.3594 4 15.0203 4 14.6667V5.33333C4 4.97971 4.14048 4.64057 4.39052 4.39052C4.64057 4.14048 4.97971 4 5.33333 4H9.33333M16 4L10 10M16 4H12M16 4V8" stroke-linecap="square"/></svg>';

export { PLACEHOLDER };
