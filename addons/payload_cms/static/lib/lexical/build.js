/**
 * Script de build esbuild pour générer le bundle Lexical autonome pour Odoo.
 * Compile Lexical core, rich-text, list, link, history et utils en un seul fichier IIFE.
 */
const esbuild = require('esbuild');
const path = require('path');

const entryContent = `
export * from 'lexical';
export * from '@lexical/rich-text';
export * from '@lexical/list';
export * from '@lexical/link';
export * from '@lexical/history';
export * from '@lexical/utils';
export * from '@lexical/selection';
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
