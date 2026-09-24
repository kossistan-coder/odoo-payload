/** @odoo-module **/

/**
 * "Configuration" section of the admin (schema builder): collections, globals
 * and fields are edited with the same Payload list / edit views, through
 * virtual collections backed by /api/_admin/schema/*.
 */

const TYPE_LABELS = {
    text: "Text",
    textarea: "Textarea",
    email: "Email",
    number: "Number",
    checkbox: "Checkbox",
    date: "Date",
    select: "Select",
    radio: "Radio Group",
    richText: "Rich Text",
    upload: "Upload",
    relationship: "Relationship",
    json: "JSON",
    code: "Code",
    slug: "Slug",
    array: "Array",
    group: "Group",
    blocks: "Blocks",
    row: "Row",
    collapsible: "Collapsible",
    tabs: "Tabs",
};

export const FIELD_TYPE_OPTIONS = Object.entries(TYPE_LABELS).map(([value, label]) => ({ value, label }));

const txt = (name, label, extra = {}) => ({ name, type: "text", label, admin: {}, ...extra });
const num = (name, label, extra = {}) => ({ name, type: "number", label, admin: {}, ...extra });
const bool = (name, label, extra = {}) => ({ name, type: "checkbox", label, admin: {}, ...extra });
const half = (field) => ({ ...field, admin: { ...(field.admin || {}), width: "50%" } });

function adminCollapsible(type) {
    const fields = [
        {
            type: "row",
            fields: [
                half({
                    name: "position",
                    type: "select",
                    label: "Position",
                    defaultValue: type === "slug" ? "sidebar" : "main",
                    options: [
                        { value: "main", label: "Main" },
                        { value: "sidebar", label: "Sidebar" },
                    ],
                    admin: { isClearable: false },
                }),
                half(txt("width", "Width", { admin: { placeholder: "50%" } })),
            ],
        },
        txt("description", "Description"),
    ];
    if (!["row", "tabs", "group", "array", "blocks", "collapsible", "checkbox", "upload"].includes(type)) {
        fields.push(txt("placeholder", "Placeholder"));
    }
    fields.push({ type: "row", fields: [half(bool("readOnly", "Read only")), half(bool("hidden", "Hidden"))] });
    if (["array", "blocks", "collapsible"].includes(type)) {
        fields.push(bool("initCollapsed", "Initially collapsed"));
    }
    return { type: "collapsible", label: "Admin", admin: { initCollapsed: true }, fields };
}

/** Builds the recursive field blocks (one block per Payload field type). */
export function buildFieldBlocks(collections) {
    const blocks = [];
    const nested = {
        name: "fields",
        type: "blocks",
        label: "Fields",
        labels: { singular: "Field", plural: "Fields" },
        blocks,
        admin: { initCollapsed: true, rowLabelField: "name", rowLabelFallback: "label" },
    };
    const identity = (type) => {
        if (type === "row") {
            return [];
        }
        const nameRequired = !["collapsible", "tabs"].includes(type);
        return [
            {
                type: "row",
                fields: [
                    half(txt("name", "Name", { required: nameRequired, admin: { placeholder: "e.g. heroImage", description: "Property name in the API (camelCase)." } })),
                    half(txt("label", "Label")),
                ],
            },
        ];
    };
    const required = (extra = []) => ({ type: "row", fields: [half(bool("required", "Required")), ...extra] });
    const options = {
        name: "options",
        type: "array",
        label: "Options",
        labels: { singular: "Option", plural: "Options" },
        fields: [{ type: "row", fields: [half(txt("value", "Value", { required: true })), half(txt("label", "Label"))] }],
        admin: {},
    };
    const badges = (checkbox) => ({
        name: "badges",
        type: "array",
        label: "Badges",
        labels: { singular: "Badge", plural: "Badges" },
        fields: [{
            type: "row",
            fields: [
                { ...(checkbox
                    ? { name: "value", type: "select", label: "Value", required: true, options: [{ value: "true", label: "Checked" }, { value: "false", label: "Unchecked" }], admin: { isClearable: false } }
                    : txt("value", "Value", { required: true })), admin: { width: "30%" } },
                { ...txt("label", "Text", { admin: { placeholder: checkbox ? "e.g. Active" : "Option label" } }), admin: { width: "35%" } },
                {
                    name: "color",
                    type: "select",
                    label: "Colour",
                    defaultValue: "success",
                    options: [["success", "Green"], ["danger", "Red"], ["warning", "Orange"], ["info", "Blue"], ["primary", "Purple"], ["muted", "Grey"]].map(([value, label]) => ({ value, label })),
                    admin: { width: "35%", isClearable: false },
                },
            ],
        }],
        admin: { description: "Shows the value as a coloured badge in the list and kanban views." },
    });
    const relationTo = (uploadOnly) => ({
        name: "relationTo",
        type: "select",
        label: "Relation To",
        required: true,
        options: collections.filter((c) => (uploadOnly ? c.upload : true)).map((c) => ({ value: c.slug, label: c.labels.plural })),
        admin: {},
    });
    const specific = {
        text: [required([half(bool("unique", "Unique"))]), txt("defaultValue", "Default Value")],
        textarea: [required(), txt("defaultValue", "Default Value")],
        email: [required([half(bool("unique", "Unique"))]), txt("defaultValue", "Default Value")],
        number: [required(), { type: "row", fields: [half(num("min", "Min")), half(num("max", "Max"))] }, txt("defaultValue", "Default Value")],
        checkbox: [txt("defaultValue", "Default Value", { admin: { placeholder: "true / false" } }), badges(true)],
        date: [required()],
        select: [required([half(bool("hasMany", "Has Many"))]), options, txt("defaultValue", "Default Value", { admin: { description: "JSON value, e.g. \"draft\"" } }), badges(false)],
        radio: [required(), options, txt("defaultValue", "Default Value"), badges(false)],
        richText: [required()],
        upload: [relationTo(true), required([half(bool("hasMany", "Has Many"))])],
        relationship: [relationTo(false), required([half(bool("hasMany", "Has Many"))])],
        json: [required()],
        code: [required()],
        slug: [txt("useAsSlug", "Use as slug", { defaultValue: "title", admin: { description: "Field the slug is generated from." } })],
        array: [required(), { type: "row", fields: [half(num("minRows", "Min Rows")), half(num("maxRows", "Max Rows"))] }, nested],
        group: [nested],
        row: [nested],
        collapsible: [nested],
        blocks: [
            required(),
            { type: "row", fields: [half(num("minRows", "Min Rows")), half(num("maxRows", "Max Rows"))] },
            {
                name: "blocks",
                type: "array",
                label: "Blocks",
                labels: { singular: "Block", plural: "Blocks" },
                fields: [
                    { type: "row", fields: [half(txt("slug", "Slug", { required: true })), half(txt("label", "Label"))] },
                    nested,
                ],
                admin: {},
            },
        ],
        tabs: [
            {
                name: "tabs",
                type: "array",
                label: "Tabs",
                labels: { singular: "Tab", plural: "Tabs" },
                fields: [
                    { type: "row", fields: [half(txt("label", "Label", { required: true })), half(txt("name", "Name", { admin: { description: "Optional: stores the tab fields in a nested object." } }))] },
                    txt("description", "Description"),
                    nested,
                ],
                admin: {},
            },
        ],
    };
    for (const [type, label] of Object.entries(TYPE_LABELS)) {
        blocks.push({
            slug: type,
            labels: { singular: label, plural: label },
            fields: [
                ...identity(type),
                ...specific[type],
                ...(["row", "tabs", "collapsible"].includes(type)
                    ? []
                    : [bool("localized", "Localized", { admin: { description: "Stores one value per locale (Configuration → Localization)." } })]),
                ...(type === "row" || type === "tabs" ? [] : [adminCollapsible(type)]),
            ],
        });
    }
    return nested;
}

const COMPONENT_LABELS = {
    text: "Text",
    textarea: "Textarea",
    richText: "Rich Text Editor",
    button: "Button",
    image: "Image",
    number: "Number",
    checkbox: "Checkbox",
    date: "Date",
    select: "Select",
    relationship: "Relationship",
    email: "Email",
    list: "List",
};

/** Elementary components of the reusable blocks (Configuration → Blocks). */
function buildComponentBlocks(collections) {
    const blocks = [];
    const nested = {
        name: "components",
        type: "blocks",
        label: "Components",
        labels: { singular: "Component", plural: "Components" },
        blocks,
        admin: { initCollapsed: true, rowLabelField: "name", rowLabelFallback: "label" },
    };
    const identity = {
        type: "row",
        fields: [
            half(txt("name", "Name", { required: true, admin: { placeholder: "e.g. title", description: "Property name in the API (camelCase)." } })),
            half(txt("label", "Label")),
        ],
    };
    const flags = (localizable) => ({
        type: "row",
        fields: [
            half(bool("required", "Required")),
            localizable && half(bool("localized", "Localized", { admin: { description: "One value per locale." } })),
        ].filter(Boolean),
    });
    const relationTo = (uploadOnly) => ({
        name: "relationTo",
        type: "select",
        label: uploadOnly ? "Media collection" : "Relation To",
        required: true,
        defaultValue: uploadOnly ? collections.find((c) => c.upload)?.slug : undefined,
        options: collections.filter((c) => (uploadOnly ? c.upload : true)).map((c) => ({ value: c.slug, label: c.labels.plural })),
        admin: {},
    });
    const options = {
        name: "options",
        type: "array",
        label: "Options",
        labels: { singular: "Option", plural: "Options" },
        fields: [{ type: "row", fields: [half(txt("value", "Value", { required: true })), half(txt("label", "Label"))] }],
        admin: {},
    };
    const help = { type: "row", fields: [half(txt("description", "Help text")), half(txt("width", "Width", { admin: { placeholder: "50%" } }))] };
    const placeholder = txt("placeholder", "Placeholder");
    const defaultValue = (extra = {}) => txt("defaultValue", "Default Value", extra);
    const specific = {
        text: [flags(true), placeholder, defaultValue()],
        textarea: [flags(true), placeholder, defaultValue()],
        richText: [flags(true)],
        button: [
            flags(true),
            {
                type: "row",
                fields: [
                    half(txt("placeholder", "Text placeholder", { admin: { placeholder: "e.g. Learn more" } })),
                    half({
                        name: "appearance",
                        type: "select",
                        label: "Default appearance",
                        defaultValue: "primary",
                        options: ["primary", "secondary", "outline", "link"].map((v) => ({ value: v, label: v[0].toUpperCase() + v.slice(1) })),
                        admin: { isClearable: false },
                    }),
                ],
            },
        ],
        image: [relationTo(true), flags(false)],
        number: [flags(false), { type: "row", fields: [half(num("min", "Min")), half(num("max", "Max"))] }, defaultValue()],
        checkbox: [defaultValue({ admin: { placeholder: "true / false" } })],
        date: [flags(false)],
        select: [flags(false), bool("hasMany", "Has Many"), options, defaultValue()],
        relationship: [relationTo(false), flags(false), bool("hasMany", "Has Many")],
        email: [flags(false), placeholder, defaultValue()],
        list: [
            flags(false),
            { type: "row", fields: [half(txt("singular", "Item label", { admin: { placeholder: "e.g. Card" } })), half(bool("initCollapsed", "Initially collapsed"))] },
            { type: "row", fields: [half(num("minRows", "Min items")), half(num("maxRows", "Max items"))] },
            { ...nested, label: "Item components", admin: { ...nested.admin, description: "Components of each item of the list." } },
        ],
    };
    for (const [type, label] of Object.entries(COMPONENT_LABELS)) {
        blocks.push({ slug: type, labels: { singular: label, plural: label }, fields: [identity, ...specific[type], help] });
    }
    return nested;
}

/** "collection.field" of every blocks field (targets of the reusable blocks). */
function blocksFieldOptions(config) {
    const options = new Map();
    const walk = (entity, fields, kind) => {
        for (const field of fields || []) {
            if (field.type === "blocks" && field.name) {
                const value = `${entity.slug}.${field.name}`;
                const label = `${kind === "global" ? entity.label : entity.labels.plural} › ${field.label || field.name}`;
                options.set(value, { value, label });
                for (const block of field.blocks || []) {
                    if (!block.custom) {
                        walk(entity, block.fields, kind);
                    }
                }
            } else if (field.type === "tabs") {
                for (const tab of field.tabs || []) {
                    walk(entity, tab.fields, kind);
                }
            } else if (field.fields) {
                walk(entity, field.fields, kind);
            }
        }
    };
    for (const c of config?.collections || []) {
        walk(c, c.fields, "collection");
    }
    for (const g of config?.globals || []) {
        walk(g, g.fields, "global");
    }
    return [...options.values()];
}

function blockFields(config) {
    const collections = config?.collections || [];
    return [
        { type: "row", fields: [half(txt("label", "Label", { required: true, admin: { placeholder: "e.g. Hero" } })), half(txt("labelPlural", "Plural Label"))] },
        { name: "description", type: "textarea", label: "Description", admin: { description: "Shown to the editors when they add the block." } },
        {
            name: "targets",
            type: "select",
            label: "Available in",
            hasMany: true,
            defaultValue: ["pages.layout"],
            options: blocksFieldOptions(config),
            admin: { description: "Blocks fields where editors can add this block (e.g. the layout of Pages)." },
        },
        bool("sectionHeader", "Section header", { defaultValue: true, admin: { description: "Starts the block with a title (required), a subtitle and a description." } }),
        { ...buildComponentBlocks(collections), admin: { initCollapsed: false, rowLabelField: "name", rowLabelFallback: "label", description: "Elementary components assembled in the block, in display order." } },
        txt("slug", "Slug", { required: true, admin: { position: "sidebar", placeholder: "e.g. hero", description: "blockType stored in the rows. Renaming it detaches the rows already written." } }),
        bool("active", "Active", { defaultValue: true, admin: { position: "sidebar", description: "Archived blocks can no longer be added." } }),
        num("componentCount", "Components", { admin: { position: "sidebar", readOnly: true } }),
        num("usageCount", "Used by documents", { admin: { position: "sidebar", readOnly: true } }),
    ];
}

function collectionFields(kind, collections) {
    const fieldsBlocks = { ...buildFieldBlocks(collections), label: "Fields" };
    const tabs = [
        { label: "Fields", fields: [fieldsBlocks] },
        {
            label: "Admin",
            fields: [
                kind === "collection" && { type: "row", fields: [half(txt("labelSingular", "Singular Label", { admin: { placeholder: "e.g. Post" } })), half(txt("adminGroup", "Navigation Group", { admin: { placeholder: kind === "global" ? "Globals" : "Collections" } }))] },
                kind === "global" && txt("adminGroup", "Navigation Group", { admin: { placeholder: "Globals" } }),
                { name: "description", type: "textarea", label: "Description", admin: { description: "Shown under the title of the list and edit views." } },
                kind === "collection" && txt("useAsTitle", "Use as Title", { defaultValue: "title", admin: { description: "Field used as the document title (admin.useAsTitle)." } }),
                kind === "collection" && txt("defaultColumns", "Default Columns", { admin: { placeholder: "title,slug,updatedAt,_status" } }),
                kind === "collection" && txt("listSearchableFields", "List Searchable Fields", { admin: { placeholder: "title,slug" } }),
                kind === "collection" && { type: "row", fields: [half(txt("defaultSort", "Default Sort", { defaultValue: "-updatedAt" })), half(num("defaultLimit", "Default Limit", { defaultValue: 10 }))] },
                bool("hidden", "Hide from navigation"),
            ].filter(Boolean),
        },
        {
            label: "Versions & Drafts",
            fields: [
                bool("versions", "Enable versions", { defaultValue: kind === "collection" }),
                bool("drafts", "Enable drafts", { admin: { description: "Draft / published workflow (versions.drafts)." } }),
                { type: "row", fields: [half(bool("autosave", "Autosave drafts")), half(num("autosaveInterval", "Autosave interval (ms)", { defaultValue: 2000 }))] },
                num("maxVersions", "Max versions per document", { defaultValue: 100, admin: { description: "0 = unlimited" } }),
            ],
        },
        kind === "collection" && {
            label: "Upload",
            fields: [
                bool("upload", "Upload collection", { admin: { description: "Documents of this collection are files (media)." } }),
                txt("mimeTypes", "Mime Types", { defaultValue: "image/*", admin: { placeholder: "image/*,application/pdf" } }),
                {
                    name: "imageSizes",
                    type: "array",
                    label: "Image Sizes",
                    labels: { singular: "Image Size", plural: "Image Sizes" },
                    fields: [{ type: "row", fields: [{ ...txt("name", "Name", { required: true }), admin: { width: "34%" } }, { ...num("width", "Width"), admin: { width: "33%" } }, { ...num("height", "Height"), admin: { width: "33%" } }] }],
                    admin: {},
                },
                { type: "row", fields: [half(bool("focalPoint", "Focal point", { defaultValue: true })), half(bool("crop", "Crop", { defaultValue: true }))] },
            ],
        },
        {
            label: "Preview",
            fields: [
                txt("previewUrl", "Preview URL", { admin: { description: "Placeholders: {slug}, {id}, {collection}. Empty = built-in preview page.", placeholder: "https://my-site.com/{slug}" } }),
                bool("livePreview", "Enable Live Preview"),
                txt("livePreviewUrl", "Live Preview URL", { admin: { description: "Empty = built-in preview page.", placeholder: "http://localhost:3000/{slug}" } }),
            ],
        },
        {
            label: "Access",
            fields: [
                bool("publicRead", "Public read", { defaultValue: true, admin: { description: "Anonymous API clients can read published documents." } }),
                kind === "collection" && bool("publicCreate", "Public create", { admin: { description: "Anonymous API clients can create documents (e.g. form submissions)." } }),
                bool("multiTenant", "Scoped per site (multisite)", { admin: { description: "Each document belongs to a site; the API filters by the current site (Configuration → Multisite)." } }),
            ].filter(Boolean),
        },
    ].filter(Boolean);
    return [
        txt("label", kind === "global" ? "Label" : "Label (plural)", { required: true, admin: { placeholder: kind === "global" ? "e.g. Header" : "e.g. Posts" } }),
        { type: "tabs", tabs },
        txt("slug", "Slug", { required: true, admin: { position: "sidebar", description: kind === "global" ? "API: /api/globals/{slug}" : "API: /api/{slug}", placeholder: "e.g. posts" } }),
        num("fieldCount", "Fields", { admin: { position: "sidebar", readOnly: true } }),
        txt("codeModule", "Defined in module", { admin: { position: "sidebar", readOnly: true, condition: { field: "codeModule", exists: true }, description: "The fields are defined in the Python class of this module (payload_cms.payload): changes made here to the fields are ignored." } }),
        kind === "collection" && num("documentCount", "Documents", { admin: { position: "sidebar", readOnly: true } }),
    ].filter(Boolean);
}

let cache = { config: null, collections: {} };

/** Returns the virtual config collection for `_config_collections|globals|fields`. */
export function configCollection(slug, config) {
    if (cache.config !== config) {
        cache = { config, collections: {} };
    }
    if (cache.collections[slug]) {
        return cache.collections[slug];
    }
    const collections = config?.collections || [];
    const section = slug.replace("_config_", "");
    let result = null;
    const base = {
        slug,
        virtual: true,
        apiPath: `/_admin/schema/${section}`,
        adminPath: `/admin/config/${section}`,
        versions: { enabled: false, drafts: false },
        upload: false,
        defaultLimit: 25,
    };
    if (section === "collections" || section === "globals") {
        const kind = section === "globals" ? "global" : "collection";
        result = {
            ...base,
            labels: kind === "global" ? { singular: "Global", plural: "Globals" } : { singular: "Collection", plural: "Collections" },
            label: kind === "global" ? "Globals" : "Collections",
            defaultSort: "label",
            admin: {
                useAsTitle: "label",
                defaultColumns: kind === "global" ? ["label", "slug", "fieldCount", "drafts", "updatedAt"] : ["label", "slug", "fieldCount", "documentCount", "drafts", "upload", "updatedAt"],
                listSearchableFields: ["label", "slug"],
                description: kind === "global"
                    ? "Globals are single documents (header, footer, settings…) exposed on /api/globals/{slug}."
                    : "Collections are groups of documents sharing the same fields, exposed on /api/{slug}.",
            },
            fields: collectionFields(kind, collections),
        };
    } else if (section === "blocks") {
        result = {
            ...base,
            labels: { singular: "Block", plural: "Blocks" },
            label: "Blocks",
            defaultSort: "label",
            admin: {
                useAsTitle: "label",
                defaultColumns: ["label", "slug", "targets", "componentCount", "usageCount", "updatedAt"],
                listSearchableFields: ["label", "slug"],
                description: "Reusable blocks assembled from elementary components (text, rich text, button, image, list…), used to build the sections of the pages.",
            },
            fields: blockFields(config),
        };
    } else if (section === "fields") {
        result = {
            ...base,
            labels: { singular: "Field", plural: "Fields" },
            label: "Fields",
            noCreate: true,
            noSelect: true,
            defaultSort: "collection",
            hrefFor: (doc) => `/admin/config/${doc.kind === "global" ? "globals" : "collections"}/${doc.collectionId}`,
            admin: {
                useAsTitle: "path",
                defaultColumns: ["path", "label", "type", "collection", "required", "relationTo"],
                listSearchableFields: ["name", "label", "collection"],
                description: "Every field of every collection and global. Fields are edited from their collection.",
            },
            fields: [
                txt("path", "Path"),
                txt("label", "Label"),
                { name: "type", type: "select", label: "Type", options: FIELD_TYPE_OPTIONS.concat([{ value: "block", label: "Block" }, { value: "tab", label: "Tab" }]), admin: {} },
                txt("collection", "Collection"),
                bool("required", "Required"),
                txt("relationTo", "Relation To"),
                txt("position", "Position"),
            ],
        };
    }
    cache.collections[slug] = result;
    return result;
}
