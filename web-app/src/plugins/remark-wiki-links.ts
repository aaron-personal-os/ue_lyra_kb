import type { Root, Text, Link, Paragraph, Emphasis, PhrasingContent, RootContent, Html } from 'mdast';
import { visit } from 'unist-util-visit';

/**
 * Remark plugin to convert [[wikilink]] syntax for the web-app.
 *
 * Two responsibilities (kept in one plugin to avoid AST traversal duplication):
 *
 * 1. Wikilink classification（图谱完备性 vs 读者可达性的分层处理）：
 *    - Tutorial-internal id（30-tutorials/...）→ proper <a> link to /series/...
 *    - External id（10-architecture/, 20-modules/, 70-topics/, 80-gotchas/, 60-decisions/, ...）
 *      → non-clickable <span class="wiki-link-external"> with tooltip
 *    Reason: 教程页 frontmatter related/prereq 引用外部页是为了维持知识图谱完备性
 *    （详见 60-decisions/0005-tutorial-cross-link-policy.md），但 web-app 静态构建后
 *    外部页不在 collection 中，渲染为可点击链接会 404。
 *
 * 2. Strip cross-section nav hint（来自 nav_inject.py --section-scope）：
 *    匹配整段 italic 段落 `_本节: ... · 上/下一节...: ..._` → 删除 paragraph 节点。
 *    这些跨节提示在阅读教程时无意义，且常含外部 wikilink。
 *
 * Handled wikilink forms:
 *   [[30-tutorials/gas/01-overview]]
 *   [[30-tutorials/gas/01-overview|Custom Title]]
 *   [[30-tutorials/gas/01-overview#section]]
 *   [[10-architecture/subsystems/ability-system]]    ← rendered as external (灰色不可点)
 *   [[10-architecture/subsystems/ability-system|GAS]] ← 同上
 */

const TUTORIAL_PREFIX = '30-tutorials/';

// 跨节提示行匹配：以下划线开始结束的 italic，含「本节」「下一节」「上一节」关键词。
// 例：_本节: 技术教程  ·  下一节首页: [[40-runbooks/...]]_
//     _本节: Lyra 项目架构与实战  ·  上一节末页: ..._
const CROSS_SECTION_HINT_RE = /(本节|上一节|下一节)/;

interface WikiLinkParts {
  pageId: string;       // "30-tutorials/gas/01-overview" or "10-architecture/..."
  anchor: string;       // "" or "section-name" (without leading #)
  label: string;        // 用户提供的 alias，或自动从 id 派生
}

function parseWikilink(target: string, alias?: string): WikiLinkParts {
  // target 已是 [[ ]] 内部内容（不含括号）
  const [idPart, anchorPart] = target.split('#', 2);
  const pageId = idPart.trim();
  const anchor = (anchorPart || '').trim();
  const label =
    alias?.trim() ||
    pageId.split('/').pop()?.replace(/-/g, ' ') ||
    pageId;
  return { pageId, anchor, label };
}

function isTutorialId(pageId: string): boolean {
  return pageId.startsWith(TUTORIAL_PREFIX);
}

function tutorialIdToUrl(pageId: string, anchor: string): string {
  // "30-tutorials/gas/01-overview" → "/series/gas/01-overview"
  const parts = pageId.replace(TUTORIAL_PREFIX, '').split('/');
  const seriesSlug = parts[0];
  const lesson = parts.slice(1).join('/');
  let url = lesson ? `/series/${seriesSlug}/${lesson}` : `/series/${seriesSlug}`;
  if (anchor) url += `#${anchor}`;
  return url;
}

/**
 * 把单个 text 节点中的所有 [[wikilink]] 转成 link / html(span) 节点。
 * 返回拆分后的子节点数组（含原 text 片段）。如果没有命中，返回 null。
 */
function splitWikilinksInText(value: string): PhrasingContent[] | null {
  const regex = /\[\[([^\]|#]+)(?:#([^\]|]+))?(?:\|([^\]]+))?\]\]/g;
  let match: RegExpExecArray | null;
  const out: PhrasingContent[] = [];
  let lastIndex = 0;
  let hit = false;

  while ((match = regex.exec(value)) !== null) {
    hit = true;
    if (match.index > lastIndex) {
      out.push({ type: 'text', value: value.slice(lastIndex, match.index) });
    }

    const idPart = match[1].trim();
    const anchorPart = (match[2] || '').trim();
    const aliasPart = match[3]?.trim();
    const inner = anchorPart ? `${idPart}#${anchorPart}` : idPart;
    const { pageId, anchor, label } = parseWikilink(inner, aliasPart);

    if (isTutorialId(pageId)) {
      const url = tutorialIdToUrl(pageId, anchor);
      out.push({
        type: 'link',
        url,
        children: [{ type: 'text', value: label }],
      } as Link);
    } else {
      // 外部 wikilink：用 raw HTML 节点输出 <span>，不可点击。
      // tooltip 说明仅在 wiki 内可见。
      const safeLabel = escapeHtml(label);
      const safeId = escapeHtml(pageId + (anchor ? `#${anchor}` : ''));
      const html = `<span class="wiki-link-external" data-wiki-id="${safeId}" title="该页仅在项目知识库中可见（${safeId}），未包含在教程站">${safeLabel}</span>`;
      out.push({ type: 'html', value: html } as Html);
    }

    lastIndex = match.index + match[0].length;
  }

  if (!hit) return null;

  if (lastIndex < value.length) {
    out.push({ type: 'text', value: value.slice(lastIndex) });
  }
  return out;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * 判断一个 paragraph 是否是「跨节提示行」：
 *   _本节: ... · 上一节末页: ..._
 *   _本节: ... · 下一节首页: ..._
 * 结构：paragraph.children[0] === emphasis 节点，且 emphasis 内文本含关键词。
 * （remark 把 `_..._` 解析为 emphasis）
 */
function isCrossSectionHintParagraph(p: Paragraph): boolean {
  if (p.children.length !== 1) return false;
  const onlyChild = p.children[0];
  if (onlyChild.type !== 'emphasis') return false;
  const em = onlyChild as Emphasis;
  // 收集 emphasis 子节点的纯文本
  let text = '';
  for (const c of em.children) {
    if (c.type === 'text') text += (c as Text).value;
    else if (c.type === 'link') {
      // [[...]] 已被本插件转 link/html；保留文本以做关键词匹配
      const linkChildren = (c as Link).children;
      for (const lc of linkChildren) {
        if (lc.type === 'text') text += (lc as Text).value;
      }
    }
  }
  return CROSS_SECTION_HINT_RE.test(text);
}

export function remarkWikiLinks() {
  return (tree: Root) => {
    // Pass 1: 删除 root 下的「跨节提示」paragraph 节点
    // 必须在 wikilink 处理之前 / 之后都行，但放前面更清晰
    tree.children = tree.children.filter((node: RootContent) => {
      if (node.type !== 'paragraph') return true;
      return !isCrossSectionHintParagraph(node as Paragraph);
    });

    // Pass 2: 处理所有 text 节点中的 [[wikilink]]
    visit(tree, 'text', (node: Text, index, parent) => {
      if (!parent || index === undefined) return;
      const split = splitWikilinksInText(node.value);
      if (!split) return;
      // 替换原 text 节点为拆分结果
      // 注意：parent.children 类型可能是 PhrasingContent[] | BlockContent[]，
      // 这里只在 phrasing context 中替换（visit text 一定是 phrasing 上下文）
      (parent.children as PhrasingContent[]).splice(index, 1, ...split);
    });
  };
}
