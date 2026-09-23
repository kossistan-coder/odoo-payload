/** @odoo-module **/

import { reactive } from "@odoo/owl";

/**
 * Form context shared with every field component through `env.form`
 * (Payload's Form provider: errors, submitted state, change notifications).
 */
export function createForm({ onChange, readOnly = false } = {}) {
    const form = {
        state: reactive({ errors: {}, submitted: false, serverErrors: false }),
        listeners: new Set(),
        readOnly,
        onChange(path, value) {
            if (form.state.errors[path]) {
                delete form.state.errors[path];
            }
            for (const listener of form.listeners) {
                listener(path, value);
            }
            onChange?.(path, value);
        },
    };
    return form;
}
