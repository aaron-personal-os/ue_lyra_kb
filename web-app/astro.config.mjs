import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'url';
import path from 'path';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { remarkWikiLinks } from './src/plugins/remark-wiki-links.ts';
import { remarkMermaid } from './src/plugins/remark-mermaid.ts';
import { remarkMdLinks } from './src/plugins/remark-md-links.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  devToolbar: { enabled: false },
  integrations: [react()],
  vite: {
    plugins: [tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        '@components': path.resolve(__dirname, './src/components'),
        '@layouts': path.resolve(__dirname, './src/layouts'),
        '@lib': path.resolve(__dirname, './src/lib'),
      },
    },
    // Pre-bundle mermaid eagerly. Mermaid 11 lazy-imports each diagram
    // type (classDiagram, sequenceDiagram …) via hashed internal chunks.
    // If we don't list `mermaid` in `include`, Vite discovers it lazily on
    // first navigation, then re-optimizes deps on the next page that uses
    // a *different* diagram type — invalidating the hashes already served
    // to the browser and producing:
    //   "Failed to fetch dynamically imported module: …classDiagram-XXXX.js"
    // Forcing it into the initial dep-optimize pass keeps the chunk URLs
    // stable for the lifetime of the dev server.
    optimizeDeps: {
      include: ['mermaid'],
    },
  },
  markdown: {
    remarkPlugins: [remarkMath, remarkMermaid, remarkWikiLinks, remarkMdLinks],
    rehypePlugins: [rehypeKatex],
    shikiConfig: {
      // Dual themes: Shiki emits CSS variables for both, gated by
      // `[data-theme="dark"|"light"]` via `defaultColor: false`.
      // The selectors are wired in src/styles/global.css.
      themes: {
        dark: 'one-dark-pro',
        light: 'github-light',
      },
      defaultColor: false,
      langs: ['cpp', 'typescript', 'yaml', 'json', 'bash'],
    },
  },
});
