import type { Root, Code, Html } from 'mdast';
import { visit } from 'unist-util-visit';

/**
 * Remark plugin: convert ```mermaid code blocks into raw HTML nodes
 * BEFORE Astro/Shiki touches them.
 *
 * Why: Astro's built-in rehype-shiki rewrites every fenced code block,
 * tokenizing the source into <span> nodes and replacing
 * `class="language-mermaid"` with `class="astro-code"`. After that
 * pass, the original Mermaid source can no longer be reliably
 * recovered from the DOM.
 *
 * By emitting a raw HTML node here, Shiki skips the block entirely
 * and the client-side renderer can read the original text from
 * <pre class="mermaid"> ... </pre>.
 */
function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function remarkMermaid() {
  return (tree: Root) => {
    visit(tree, 'code', (node: Code, index, parent) => {
      if (!parent || index === undefined) return;
      if (node.lang !== 'mermaid') return;

      const value = node.value || '';
      const html: Html = {
        type: 'html',
        value: `<pre class="mermaid-source"><code class="language-mermaid">${escapeHtml(value)}</code></pre>`,
      };
      parent.children.splice(index, 1, html);
    });
  };
}
