/**
 * Script de build esbuild pour générer le bundle Lexical autonome pour Odoo.
 * Compile Lexical core, rich-text, list, link, history et utils en un seul fichier IIFE.
 */
const esbuild = require('esbuild');
const path = require('path');

// Names exported by several packages are ambiguous for export-star: they are re-exported explicitly.
const entryContent = `
export * from 'lexical';
export * from '@lexical/rich-text';
export * from '@lexical/list';
export * from '@lexical/link';
export * from '@lexical/history';
export * from '@lexical/utils';
export * from '@lexical/selection';
export * from '@lexical/markdown';
export * from '@lexical/clipboard';
export * from '@lexical/html';
export * from '@lexical/dragon';
export { $cloneWithProperties, $findMatchingParent, $getAdjacentSiblingOrParentSiblingCaret, $insertNodeToNearestRootAtCaret, $isBlockFullySelected, $selectAll, $splitNode, CAN_USE_BEFORE_INPUT, CAN_USE_DOM, IS_ANDROID, IS_ANDROID_CHROME, IS_APPLE, IS_APPLE_WEBKIT, IS_CHROME, IS_FIREFOX, IS_IOS, IS_SAFARI, addClassNamesToElement, getStyleObjectFromCSS, isBlockDomNode, isHTMLAnchorElement, isHTMLElement, isInlineDomNode, mergeRegister, removeClassNamesFromElement } from 'lexical';
export { eventFiles } from '@lexical/rich-text';
`;

esbuild.build({
  stdin: {
    contents: entryContent,
    resolveDir: __dirname,
    loader: 'js',
  },
  bundle: true,
  minify: true,
  format: 'iife',
  globalName: 'PayloadLexical',
  outfile: path.join(__dirname, 'lexical.bundle.js'),
  target: ['es2020'],
}).then(() => {
  console.log('✅ Bundle Lexical généré avec succès dans lexical.bundle.js');
}).catch((err) => {
  console.error('❌ Erreur de génération du bundle Lexical:', err);
  process.exit(1);
});
