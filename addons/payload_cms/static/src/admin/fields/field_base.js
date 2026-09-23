/** @odoo-module **/

import { Component, reactive, status, useState } from "@odoo/owl";
import { t } from "../core/i18n";
import { currentLocale } from "../core/store";
import { fieldLabel, icon } from "../core/utils";

/**
 * Base class of every field component.
 *
 * Props: `field` (config), `data` (object owning the value), `path`,
 * `readOnly`, `parentIsSidebar`...
 * `this.env.form` is provided by the edit view (errors, submitted, onChange).
 */
export class FieldBase extends Component {
    setup() {
        this.t = t;
        this.icon = icon;
        this.fieldLabel = fieldLabel;
        this.form = useState(this.env.form.state);
        let scheduled = false;
        this._rerender = () => {
            if (scheduled) {
                return;
            }
            scheduled = true;
            Promise.resolve().then(() => {
                scheduled = false;
                if (status(this) === "mounted") {
                    this.render();
                }
            });
        };
    }

    /** Observe an object of the form data from this component. */
    observe(obj) {
        return obj && typeof obj === "object" ? reactive(obj, this._rerender) : obj;
    }

    get field() {
        return this.props.field;
    }

    get data() {
        return this.observe(this.props.data);
    }

    get value() {
        return this.data?.[this.field.name];
    }

    set value(v) {
        this.setValue(v);
    }

    setValue(v) {
        this.props.data[this.field.name] = v;
        this.env.form.onChange(this.props.path, v);
    }

    get label() {
        return fieldLabel(this.field);
    }

    get admin() {
        return this.field.admin || {};
    }

    /** "— English" after the label of localized fields (Payload's FieldLabel). */
    get localeSuffix() {
        if (!this.field.localized) {
            return "";
        }
        const locale = currentLocale();
        return locale ? `— ${locale.label || locale.code}` : "";
    }

    get readOnly() {
        return Boolean(this.props.readOnly || this.admin.readOnly || this.env.form.readOnly);
    }

    get error() {
        return this.form.submitted || this.form.serverErrors ? this.form.errors[this.props.path] : null;
    }

    get pathId() {
        return `field-${this.props.path.replaceAll(".", "__")}`;
    }

    get fieldStyle() {
        return this.admin.width ? `--field-width: ${this.admin.width}` : "flex: 1 1 auto";
    }

    /** Number of errors under this field's path (error pills). */
    errorCount(path = this.props.path) {
        if (!this.form.submitted && !this.form.serverErrors) {
            return 0;
        }
        return Object.keys(this.form.errors).filter((p) => p === path || p.startsWith(`${path}.`)).length;
    }
}
