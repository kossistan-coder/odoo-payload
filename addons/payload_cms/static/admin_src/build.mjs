/**
 * Builds static/dist/admin.css:
 *   - compiles Payload CMS v3.90.1 SCSS (MIT, vendored in payload-scss/) with sass
 *   - runs Tailwind CSS v4 over css/admin.css (which imports the compiled SCSS)
 * Usage: npm install && npm run build   (or: npm run watch)
 */
import { execFileSync, spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as sass from "sass";

const root = dirname(fileURLToPath(import.meta.url));
const watch = process.argv.includes("--watch");

function buildScss() {
    const result = sass.compile(join(root, "payload-scss/_all.scss"), {
        loadPaths: [join(root, "payload-scss")],
        style: "expanded",
        silenceDeprecations: ["import", "global-builtin", "color-functions", "slash-div"],
        quietDeps: true,
    });
    // Inline the handle icons referenced with relative URLs by the richtext-lexical SCSS.
    const svg = (s) => `url("data:image/svg+xml,${encodeURIComponent(s)}")`;
    const add = (c) => `<svg width="18" height="24" viewBox="0 0 18 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M5,12h8" stroke="${c}"/><path d="M9,16V8" stroke="${c}"/></svg>`;
    const drag = (c) => `<svg width="18" height="24" viewBox="0 0 18 24" fill="${c}" xmlns="http://www.w3.org/2000/svg"><circle cx="7" cy="8" r="1"/><circle cx="11" cy="8" r="1"/><circle cx="7" cy="12" r="1"/><circle cx="11" cy="12" r="1"/><circle cx="7" cy="16" r="1"/><circle cx="11" cy="16" r="1"/></svg>`;
    const css = result.css
        .replace("url(../../../ui/icons/Add/index.svg)", svg(add("#000000")))
        .replace("url(../../../ui/icons/Add/light.svg)", svg(add("#FFFFFF")))
        .replace("url(../../../ui/icons/DraggableBlock/index.svg)", svg(drag("#000000")))
        .replace("url(../../../ui/icons/DraggableBlock/light.svg)", svg(drag("#FFFFFF")));
    mkdirSync(join(root, ".build"), { recursive: true });
    writeFileSync(join(root, ".build/payload.css"), css);
    console.log(`payload.css: ${(result.css.length / 1024).toFixed(0)} KB`);
}

buildScss();
const args = ["-i", join(root, "css/admin.css"), "-o", join(root, "../dist/admin.css"), "--minify"];
if (watch) {
    spawn(join(root, "node_modules/.bin/tailwindcss"), [...args, "--watch"], { stdio: "inherit" });
} else {
    execFileSync(join(root, "node_modules/.bin/tailwindcss"), args, { stdio: "inherit" });
}
