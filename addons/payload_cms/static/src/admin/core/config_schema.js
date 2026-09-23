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
        checkbox: [txt("defaultValue", "Default Value", { admin: { placeholder: "true / false" } })],
        date: [required()],
        select: [required([half(bool("hasMany", "Has Many"))]), options, txt("defaultValue", "Default Value", { admin: { description: "JSON value, e.g. \"draft\"" } })],
        radio: [required(), options, txt("defaultValue", "Default Value")],
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
