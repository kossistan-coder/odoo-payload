/** @odoo-module **/

import { reactive } from "@odoo/owl";

/**
 * Admin theme, like Payload's ThemeProvider: the preference is "auto" (follow the OS),
 * "light" or "dark". An explicit choice is remembered per browser (localStorage + cookie
 * `payload-theme`, the cookie lets the server render the right `data-theme`); "auto"
 * removes both and follows `prefers-color-scheme`, live.
 * The resolved theme is set on <html data-theme="..."> (the inline script of the page
 * template already does it before the first paint, see views/admin_templates.xml).
 */
export const THEME_KEY = "payload-theme";
export const THEME_OPTIONS = ["auto", "light", "dark"];

const media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

function readPreference() {
    let value = null;
    try {
        value = window.localStorage.getItem(THEME_KEY);
    } catch {
        // Storage blocked: fall back on the cookie.
    }
    if (!value) {
        const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${THEME_KEY}=([^;]*)`));
        value = match && match[1];
    }
    return value === "light" || value === "dark" ? value : "auto";
}

function resolve(preference) {
    if (preference === "light" || preference === "dark") {
        return preference;
    }
    return media && media.matches ? "dark" : "light";
}

export const theme = reactive({ preference: readPreference(), current: "light" });

function apply() {
    theme.current = resolve(theme.preference);
    document.documentElement.setAttribute("data-theme", theme.current);
}

/** Sets the theme preference ("auto" | "light" | "dark") and applies it immediately. */
export function setTheme(preference) {
    preference = THEME_OPTIONS.includes(preference) ? preference : "auto";
    theme.preference = preference;
    try {
        if (preference === "auto") {
            window.localStorage.removeItem(THEME_KEY);
        } else {
            window.localStorage.setItem(THEME_KEY, preference);
        }
    } catch {
        // Storage blocked: the cookie still remembers the choice.
    }
    document.cookie = preference === "auto"
        ? `${THEME_KEY}=; path=/; max-age=0; SameSite=Lax`
        : `${THEME_KEY}=${preference}; path=/; max-age=31536000; SameSite=Lax`;
    apply();
}

/** Quick toggle of the nav: switches to the opposite of the theme currently displayed. */
export function toggleTheme() {
    setTheme(theme.current === "dark" ? "light" : "dark");
}

apply();
// "Automatic" follows the OS live.
media?.addEventListener?.("change", () => {
    if (theme.preference === "auto") {
        apply();
    }
});
// Other tabs (and the admin embedded in the Odoo web client) stay in sync.
window.addEventListener("storage", (ev) => {
    if (ev.key === THEME_KEY || ev.key === null) {
        theme.preference = readPreference();
        apply();
    }
});
