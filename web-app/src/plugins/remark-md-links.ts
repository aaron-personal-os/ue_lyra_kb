import type { Root, Link } from 'mdast';
import { visit } from 'unist-util-visit';
import path from 'node:path';

/**
 * Remark plugin: rewrite local relative Markdown links so they resolve against
 * the web-app's tutorial routes rather than the source `.md` file's URL on disk.
 *
 * Source markdown commonly contains links like:
 *   [文档标题](00-UE本地化与国际化概览.md)
 *   [下一篇](./04-PCG图表基础.md#anchor)
 *   [上一篇](../foo/02-x.md)
 *
 * In the source repo these resolve correctly via filesystem, but in the
 * deployed wiki the current page URL is `/series/<slug>/<lesson>` (no `.md`
 * suffix), so the browser rewrites a relative `00-xxx.md` link to
 * `/series/<slug>/00-xxx.md` and 404s.
 *
 * This plugin resolves the link target relative to the *source file* (not the
 * URL), then maps the resulting path back into a tutorial URL of the form
 * `/series/<slug>/<lesson>` (anchor preserved).
 *
 * Skipped (left untouched):
 *   - external URLs: http(s)://, mailto:, tel:, ftp:, etc.
 *   - protocol-relative or bare anchors: `#section`, `?query`
 *   - non-`.md` resources (images, source code references, …)
 *   - links whose resolved path falls outside `Docs/30-tutorials/`
 *     (those become broken relative links — same behaviour as before;
 *      out-of-scope cross-section links are surfaced by the upstream lint tool)
 *
 * Anchors and titles are preserved.
 */

const TUTORIALS_DIR_NAME = '30-tutorials';

const EXTERNAL_PROTO_RE = /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i;

interface VFileLike {
  path?: string;
  history?: string[];
  cwd?: string;
}

/** Posix-style join + normalize, given a file's absolute path & a relative href. */
function resolveAgainstFile(filePath: string, href: string): string {
  // Drop the source file's basename, then resolve the href against its dir.
  const fileDir = path.dirname(filePath);
  const abs = path.resolve(fileDir, href);
  // Normalize to forward slashes for posix-style matching below.
  return abs.split(path.sep).join('/');
}

/**
 * Given an absolute path that lives somewhere under `…/30-tutorials/<rest>`,
 * return `<rest>` (without the `.md` suffix). Returns null if the path is not
 * inside the tutorials directory or doesn't end with `.md`.
 */
function toTutorialEntryId(absPosix: string): string | null {
  const marker = `/${TUTORIALS_DIR_NAME}/`;
  const idx = absPosix.lastIndexOf(marker);
  if (idx === -1) return null;
  let rel = absPosix.slice(idx + marker.length);
  if (!rel.toLowerCase().endsWith('.md')) return null;
  rel = rel.slice(0, -3); // strip .md
  // Reject paths that escape via `..` segments after marker (shouldn't normally
  // happen because path.resolve already collapses them, but guard anyway).
  if (rel.startsWith('..') || rel.includes('/../')) return null;
  return rel;
}

/** Convert an entry id like "localization-i18n/00-foo" → "/series/localization-i18n/00-foo". */
function entryIdToUrl(entryId: string, anchor: string): string {
  const parts = entryId.split('/');
  const seriesSlug = parts[0];
  const lesson = parts.slice(1).join('/');
  let url = lesson ? `/series/${seriesSlug}/${lesson}` : `/series/${seriesSlug}`;
  if (anchor) url += anchor; // anchor already includes leading '#'
  return url;
}

/** Split an href into (path, suffix) where suffix is `#anchor` and/or `?query`. */
function splitSuffix(href: string): { pathPart: string; suffix: string } {
  // Find the first '#' or '?'. Handle either independently — query first then hash.
  const hashIdx = href.indexOf('#');
  const queryIdx = href.indexOf('?');
  const cuts: number[] = [];
  if (hashIdx !== -1) cuts.push(hashIdx);
  if (queryIdx !== -1) cuts.push(queryIdx);
  if (cuts.length === 0) return { pathPart: href, suffix: '' };
  const cut = Math.min(...cuts);
  return { pathPart: href.slice(0, cut), suffix: href.slice(cut) };
}

export function remarkMdLinks() {
  return (tree: Root, file: VFileLike) => {
    const filePath = file?.path || file?.history?.[file.history.length - 1];
    if (!filePath) return; // No source file context — bail (markdown not from disk).

    const filePathPosix = filePath.split(path.sep).join('/');

    visit(tree, 'link', (node: Link) => {
      const url = node.url;
      if (!url) return;

      // External or protocol-relative
      if (EXTERNAL_PROTO_RE.test(url)) return;
      // Pure in-page anchor
      if (url.startsWith('#')) return;
      // Absolute root path (already a real URL)
      if (url.startsWith('/')) return;

      const { pathPart, suffix } = splitSuffix(url);
      // Only rewrite when the target is a markdown file; leave other relative
      // links (images, source paths, etc.) alone so they fail visibly rather
      // than being silently mis-routed.
      if (!pathPart.toLowerCase().endsWith('.md')) return;

      const absTarget = resolveAgainstFile(filePathPosix, pathPart);
      const entryId = toTutorialEntryId(absTarget);
      if (!entryId) return; // Out of tutorials scope; do nothing.

      // Pull out anchor only (keep query as-is though tutorial pages don't use it)
      const hashIdx = suffix.indexOf('#');
      const anchor = hashIdx === -1 ? '' : suffix.slice(hashIdx);

      node.url = entryIdToUrl(entryId, anchor);
    });
  };
}
