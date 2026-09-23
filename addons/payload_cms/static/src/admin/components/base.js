/** @odoo-module **/

import { Component, onMounted, onPatched, onWillUnmount, useRef, useState } from "@odoo/owl";
import { t } from "../core/i18n";
import { classNames, icon } from "../core/utils";

/**
 * Payload's <Button> (ui/src/elements/Button) with the exact class composition.
 */
export class Button extends Component {
    static template = "payload.Button";

    setup() {
        this.state = useState({ showTooltip: false });
        this.icon = icon;
    }

    get classes() {
        const p = this.props;
        const style = p.buttonStyle || "primary";
        const hasIcon = Boolean(p.icon);
        const hasLabel = Boolean(p.label) || Boolean(p.slots?.default);
        return classNames(
            "btn",
            p.className,
            hasIcon && "btn--icon",
            `btn--icon-style-${p.iconStyle || "without-border"}`,
            hasIcon && !hasLabel && "btn--icon-only",
            `btn--size-${p.size || "medium"}`,
            hasIcon && `btn--icon-position-${p.iconPosition || "right"}`,
            p.tooltip && "btn--has-tooltip",
            "btn--withoutPopup",
            p.margin === false && "btn--no-margin",
            `btn--style-${style}`,
            p.disabled && "btn--disabled",
            p.round && "btn--round",
            "btn--withoutPopup"
        );
    }

    get iconMarkup() {
        const name = this.props.icon;
        if (!name) {
            return "";
        }
        return typeof name === "string" ? icon(name) : name;
    }

    onClick(ev) {
        this.state.showTooltip = false;
        if (this.props.disabled) {
            ev.preventDefault();
            return;
        }
        this.props.onClick?.(ev);
    }
}

/** Payload's <Pill>. */
export class Pill extends Component {
    static template = "payload.Pill";

    setup() {
        this.icon = icon;
    }

    get classes() {
        const p = this.props;
        return classNames(
            "pill",
            `pill--style-${p.pillStyle || "light"}`,
            `pill--size-${p.size || "medium"}`,
            p.className,
            p.href && "pill--has-link",
            (p.href || p.onClick) && "pill--has-action",
            p.icon && "pill--has-icon",
            p.icon && `pill--align-icon-${p.alignIcon || "right"}`,
            p.rounded && "pill--rounded"
        );
    }
}

/**
 * Payload's <Popup>: trigger + content portalled into <body>, positioned in JS.
 * Slots: "button" (trigger content) and "default" (content, receives `close`).
 */
export class Popup extends Component {
    static template = "payload.Popup";

    setup() {
        this.state = useState({ active: false, top: 0, left: 0, caret: 0, vertical: "bottom" });
        this.triggerRef = useRef("trigger");
        this.contentRef = useRef("content");
        this.onDocMouseDown = (ev) => {
            if (!this.state.active) {
                return;
            }
            if (this.triggerRef.el?.contains(ev.target) || this.contentRef.el?.contains(ev.target)) {
                return;
            }
            this.close();
        };
        this.onKeyDown = (ev) => {
            if (ev.key === "Escape" && this.state.active) {
                this.close();
            }
        };
        this.onReposition = () => this.state.active && this.position();
        onMounted(() => {
            document.addEventListener("mousedown", this.onDocMouseDown, true);
            document.addEventListener("keydown", this.onKeyDown);
            window.addEventListener("resize", this.onReposition);
            window.addEventListener("scroll", this.onReposition, true);
        });
        onWillUnmount(() => {
            document.removeEventListener("mousedown", this.onDocMouseDown, true);
            document.removeEventListener("keydown", this.onKeyDown);
            window.removeEventListener("resize", this.onReposition);
            window.removeEventListener("scroll", this.onReposition, true);
        });
        onPatched(() => {
            if (this.state.active && !this._positioned) {
                this._positioned = true;
                this.position();
            }
        });
        this.close = this.close.bind(this);
    }

    get buttonClasses() {
        const p = this.props;
        return classNames(
            "popup-button",
            p.buttonClassName,
            `popup-button--${p.buttonType || "default"}`,
            !p.noBackground && "popup-button--background",
            p.buttonSize && `popup-button--size-${p.buttonSize}`,
            p.disabled && "popup-button--disabled"
        );
    }

    toggle() {
        if (this.props.disabled) {
            return;
        }
        this.state.active ? this.close() : this.open();
    }

    open() {
        this._positioned = false;
        this.state.active = true;
        this.props.onToggle?.(true);
    }

    close() {
        this.state.active = false;
        this.props.onToggle?.(false);
    }

    position() {
        const trigger = this.triggerRef.el?.getBoundingClientRect();
        const content = this.contentRef.el;
        if (!trigger || !content) {
            return;
        }
        const offset = 10;
        const w = content.offsetWidth;
        const h = content.offsetHeight;
        let vertical = this.props.verticalAlign || "bottom";
        let top;
        if (vertical === "bottom") {
            top = trigger.bottom + offset;
            if (top + h > window.innerHeight && trigger.top - h - offset > 0) {
                vertical = "top";
                top = trigger.top - h - offset;
            }
        } else {
            top = trigger.top - h - offset;
            if (top < 0) {
                vertical = "bottom";
                top = trigger.bottom + offset;
            }
        }
        const align = this.props.horizontalAlign || "left";
        let left = align === "right" ? trigger.right - w : align === "center" ? trigger.left + trigger.width / 2 - w / 2 : trigger.left;
        left = Math.max(10, Math.min(left, window.innerWidth - w - 10));
        const center = trigger.left + trigger.width / 2;
        this.state.caret = Math.max(12, Math.min(center - left, w - 12));
        this.state.top = top + window.scrollY;
        this.state.left = left + window.scrollX;
        this.state.vertical = vertical;
    }

    onContentClick(ev) {
        const target = ev.target.closest("button, a[href], [role=button], [role=menuitem]");
        if (target && !target.closest("[data-popup-prevent-close]") && this.contentRef.el?.contains(target)) {
            this.close();
        }
    }
}

/** Payload's PopupList.Button (popup-button-list__button). */
export class PopupButton extends Component {
    static template = "payload.PopupButton";
}

/**
 * Port of Payload's ReactSelect element (react-select with classNamePrefix "rs").
 */
export class Select extends Component {
    static template = "payload.Select";

    setup() {
        this.state = useState({ open: false, input: "", focused: -1, placement: "bottom", isFocused: false });
        this.rootRef = useRef("root");
        this.inputRef = useRef("input");
        this.icon = icon;
        this.t = t;
        this.onDocMouseDown = (ev) => {
            if (this.state.open && !this.rootRef.el?.contains(ev.target)) {
                this.closeMenu();
            }
        };
        onMounted(() => document.addEventListener("mousedown", this.onDocMouseDown, true));
        onWillUnmount(() => document.removeEventListener("mousedown", this.onDocMouseDown, true));
    }

    get isMulti() {
        return Boolean(this.props.isMulti);
    }

    get values() {
        const v = this.props.value;
        if (this.isMulti) {
            return Array.isArray(v) ? v : v === undefined || v === null || v === "" ? [] : [v];
        }
        return v === undefined || v === null || v === "" ? [] : [v];
    }

    get hasValue() {
        return this.values.length > 0;
    }

    labelOf(value) {
        if (this.props.getLabel) {
            return this.props.getLabel(value);
        }
        const opt = this.flatOptions.find((o) => o.value === value);
        return opt ? opt.label : String(value);
    }

    get flatOptions() {
        return (this.props.options || []).flatMap((o) => (o.options ? o.options : [o]));
    }

    get filteredOptions() {
        let options = this.flatOptions;
        if (this.isMulti) {
            options = options.filter((o) => !this.values.includes(o.value));
        }
        const q = this.state.input.trim().toLowerCase();
        if (q && !this.props.onInputChange) {
            const norm = (s) => String(s).normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
            options = options.filter((o) => norm(o.label).includes(norm(q)) || norm(o.value).includes(norm(q)));
        }
        if (this.props.isCreatable && q && !options.some((o) => String(o.label).toLowerCase() === q)) {
            options = [...options, { value: this.state.input.trim(), label: `Create "${this.state.input.trim()}"`, __create: true }];
        }
        return options;
    }

    get containerClasses() {
        return classNames(
            this.props.className,
            "react-select",
            this.props.showError && "react-select--error",
            this.props.disabled && "rs--is-disabled"
        );
    }

    onControlMouseDown(ev) {
        if (this.props.disabled || ev.target.closest(".clear-indicator, .multi-value-remove, .relationship--single-value__drawer-toggler, .relationship--multi-value-label__drawer-toggler")) {
            return;
        }
        if (this.props.onControlClick) {
            ev.preventDefault();
            this.props.onControlClick();
            return;
        }
        ev.preventDefault();
        if (this.state.open) {
            if (!ev.target.closest(".rs__input-container")) {
                this.closeMenu();
            }
        } else {
            this.openMenu();
        }
        this.inputRef.el?.focus();
    }

    openMenu() {
        if (this.props.disabled || this.state.open) {
            return;
        }
        const rect = this.rootRef.el?.getBoundingClientRect();
        this.state.placement = rect && window.innerHeight - rect.bottom < 320 && rect.top > 320 ? "top" : "bottom";
        this.state.open = true;
        this.state.focused = 0;
        this.props.onMenuOpen?.();
    }

    closeMenu() {
        this.state.open = false;
        this.state.focused = -1;
        if (this.state.input) {
            this.state.input = "";
            this.props.onInputChange?.("");
        }
    }

    select(option) {
        if (!option || option.isDisabled) {
            return;
        }
        if (this.isMulti) {
            this.props.onChange?.([...this.values, option.value], option);
            this.state.input = "";
            this.props.onInputChange?.("");
        } else {
            this.props.onChange?.(option.value, option);
            this.closeMenu();
        }
    }

    remove(value) {
        if (this.isMulti) {
            this.props.onChange?.(this.values.filter((v) => v !== value));
        } else {
            this.props.onChange?.(null);
        }
    }

    clear() {
        this.props.onChange?.(this.isMulti ? [] : null);
    }

    onInput(ev) {
        this.state.input = ev.target.value;
        this.state.focused = 0;
        if (!this.state.open) {
            this.openMenu();
        }
        this.props.onInputChange?.(ev.target.value);
    }

    onKeyDown(ev) {
        const options = this.filteredOptions;
        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            if (!this.state.open) {
                this.openMenu();
                return;
            }
            this.state.focused = Math.min(options.length - 1, this.state.focused + 1);
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            this.state.focused = Math.max(0, this.state.focused - 1);
        } else if (ev.key === "Enter" || (ev.key === "Tab" && this.props.isCreatable && this.state.input)) {
            if (this.state.open && options[this.state.focused]) {
                ev.preventDefault();
                this.select(options[this.state.focused]);
            }
        } else if (ev.key === "Escape") {
            this.closeMenu();
        } else if (ev.key === "Backspace" && !this.state.input && this.isMulti && this.values.length) {
            this.remove(this.values[this.values.length - 1]);
        }
    }

    onMenuScroll(ev) {
        const el = ev.target;
        if (el.scrollTop + el.clientHeight >= el.scrollHeight - 10) {
            this.props.onMenuScrollToBottom?.();
        }
    }
}

/** Payload's CheckboxInput. */
export class CheckboxInput extends Component {
    static template = "payload.CheckboxInput";

    setup() {
        this.icon = icon;
        this.uid = `checkbox-${Math.random().toString(36).slice(2, 9)}`;
    }

    onChange(ev) {
        if (!this.props.readOnly) {
            this.props.onToggle?.(ev.target.checked);
        }
    }
}

/** Payload's Thumbnail with the "file" fallback graphic. */
export class Thumbnail extends Component {
    static template = "payload.Thumbnail";

    setup() {
        this.state = useState({ error: false });
        this.icon = icon;
    }
}

/** Collapsible height animation wrapper (rah-static). */
export class AnimateHeight extends Component {
    static template = "payload.AnimateHeight";
}

/** Payload's static FieldError tooltip. */
export class FieldError extends Component {
    static template = "payload.FieldError";
}

export class ShimmerEffect extends Component {
    static template = "payload.ShimmerEffect";
}

export class Banner extends Component {
    static template = "payload.Banner";
}
