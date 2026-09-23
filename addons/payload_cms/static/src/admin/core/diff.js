/** @odoo-module **/

/**
 * Small word/character diff producing Payload's HTMLDiff markup
 * (`<span data-match-type="create|delete">`).
 */
function escape(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function tokenize(text, byChar) {
    if (byChar) {
        return Array.from(text);
    }
    return text.match(/\s+|[^\s]+/g) || [];
}

/** LCS-based diff of two token arrays -> [{type: 'equal'|'delete'|'create', value}] */
function diffTokens(a, b) {
    const n = a.length;
    const m = b.length;
    if (n * m > 4_000_000) {
        return [
            { type: "delete", value: a.join("") },
            { type: "create", value: b.join("") },
        ];
    }
    const dp = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
    for (let i = n - 1; i >= 0; i--) {
        for (let j = m - 1; j >= 0; j--) {
            dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
        }
    }
    const ops = [];
    let i = 0;
    let j = 0;
    const push = (type, value) => {
        const last = ops[ops.length - 1];
        if (last && last.type === type) {
            last.value += value;
        } else {
            ops.push({ type, value });
        }
    };
    while (i < n && j < m) {
        if (a[i] === b[j]) {
            push("equal", a[i]);
            i++;
            j++;
        } else if (dp[i + 1][j] >= dp[i][j + 1]) {
            push("delete", a[i++]);
        } else {
            push("create", b[j++]);
        }
    }
    while (i < n) {
        push("delete", a[i++]);
    }
    while (j < m) {
        push("create", b[j++]);
    }
    return ops;
}

/** Returns {old, new} HTML strings, each wrapped in <p>. */
export function diffText(oldText, newText, { byChar = false, wrap = "p" } = {}) {
    const ops = diffTokens(tokenize(oldText ?? "", byChar), tokenize(newText ?? "", byChar));
    let oldHtml = "";
    let newHtml = "";
    for (const op of ops) {
        const v = escape(op.value);
        if (op.type === "equal") {
            oldHtml += v;
            newHtml += v;
        } else if (op.type === "delete") {
            oldHtml += `<span data-match-type="delete">${v}</span>`;
        } else {
            newHtml += `<span data-match-type="create">${v}</span>`;
        }
    }
    const open = wrap ? `<${wrap}>` : "";
    const close = wrap ? `</${wrap}>` : "";
    return { old: `${open}${oldHtml}${close}`, new: `${open}${newHtml}${close}` };
}

export { escape as escapeHtml };
