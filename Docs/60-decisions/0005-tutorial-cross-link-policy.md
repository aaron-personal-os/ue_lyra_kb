---
id: 60-decisions/0005-tutorial-cross-link-policy
type: adr
status: accepted
language: zh
owner: human
decided_at: 2026-05-23
decided_by: robert
anchors:
  - path: web-app/src/plugins/remark-wiki-links.ts
  - path: web-app/src/styles/typography.css
  - path: .codebuddy/skills/project-wiki/scripts/wiki_lint.py
supersedes: []
superseded_by: []
related: []
sources: []
last_synced: 2026-05-23
last_verified: 2026-05-23
tags: [adr, wikilink, web-app, knowledge-graph, tutorial-ext-ref, lint-policy, nav-strategy]
---

# ADR-0005：教程跨层引用策略（图谱完备性 vs 读者可达性的分层处理）

> **2026-05-24 v1.1.1 更新**：文中提到的 `query.py` 已合并入 `wiki_query.py`。
> 详见 [[_raw/specs/2026-05-24-merge-query-into-wiki-query-eval]]。

> 教程页可以在 frontmatter 的 `related / prerequisites / sources` 中引用外部 wiki 页（保留知识图谱完备性），但 web-app 渲染时把外部引用降级为不可点击文本，避免静态发布后 404；同时屏蔽 nav_inject 生成的「跨节提示行」。`wiki_lint` 的 `tutorial-ext-ref` 规则从 ERROR 降级为 WARN 并对 frontmatter 豁免。

## 背景 (Context)

### 双重诉求的冲突

[[60-decisions/0004-knowledge-graph-query]] 落地后，`query.py` 通过 `related / prerequisites` 等图边在 346 篇 wiki 之间做多跳推理。教程页指向 `10-architecture/`、`70-topics/`、`20-modules/` 等外部页是图谱完备性的关键——例如：

- `30-tutorials/gas/00-GAS系统总览.md` 应在 `related:` 中引 `[[10-architecture/subsystems/ability-system]]`
- `30-tutorials/modular-gameplay/02-核心类详解.md` 应在 `related:` 中引 `[[20-modules/cpp/ALyraCharacter]]`

**但** [[60-decisions/0001-knowledge-base-web-app]] 的 web-app 是静态发布站，content collection 仅 glob `Docs/30-tutorials/`：

- 外部页（10-architecture / 70-topics / 等）**不在 collection 里**
- 渲染时若把这些 wikilink 转成 `<a href="/...">`，打包发布后**点击全部 404**

### 触发本 ADR 的具体冲突点

`wiki_lint.py` 的 `tutorial-ext-ref` 规则（v1.2 引入）声明"教程不能引外部页"，与上面的图谱诉求**直接冲突**：

| 工具 / 规则 | 立场 |
|---|---|
| `query.py` / `fix_asymm.py` | 鼓励教程 ↔ 架构 ↔ 模块的双向边（保完备性） |
| `tutorial-ext-ref`（旧） | ERROR 禁止教程引外部（保读者体验） |
| `nav_inject.py --section-scope` | 生成 `_本节: ... · 上一节末页: [[80-gotchas/...]]_` 跨节提示，必然引外部 |

实测：[[60-decisions/0004-knowledge-graph-query]] 提交时已踩这个坑——`fix_asymm.py --apply` 给教程加 16 条回引，结果触发 18 个新 `tutorial-ext-ref` ERROR，被迫回滚。

### 历史 v1.2 设计的局限

v1.2 把"教程不能引外部"做成 ERROR 是为了**读者可达性**。但 v1.2 没区分两种引用：

| 引用位置 | 给 Agent 看（图谱）| 给读者看（web-app）|
|---|---|---|
| **frontmatter `related/prereq/sources`** | ✅ 有意义（图边）| 不渲染（默认就不显示） |
| **教程正文 `[[X]]`** | ✅ 有意义 | ❌ 渲染为 404 链接 |

正文与 frontmatter 的诉求不同。把它们一锅端 ERROR 是设计粗糙。

## 决策 (Decision)

**采用「图谱端保留 + 渲染端分层」策略，让 wiki 知识图谱与 web-app 阅读体验各自完备。**

### 三层落地

#### 1. wiki 端：保留外部引用

- `Docs/30-tutorials/*.md` 的 frontmatter `related / prerequisites / sources` **允许**引用外部页
- 教程**正文**仍提倡只引内部教程 + index/overview，但不再硬性 ERROR

#### 2. web-app 端：渲染期分层

`web-app/src/plugins/remark-wiki-links.ts` 增强 remark plugin：

- **教程内部 wikilink**（`30-tutorials/...`）→ 渲染为可点击 `<a href="/series/...">`
- **外部 wikilink** → 渲染为 `<span class="wiki-link-external">`（不可点击，灰色 dotted underline，📒 前缀，tooltip 说明"该页仅在项目知识库中可见"）
- **跨节提示行**（`_本节: ... · 上/下一节...: ..._`）→ 整个 paragraph 节点删除

CSS 在 `web-app/src/styles/typography.css` 给 `.wiki-link-external` 加灰色样式 + `cursor: not-allowed`。

#### 3. lint 端：规则降级 + frontmatter 豁免

`wiki_lint.py` 的 `tutorial-ext-ref` 规则从 ERROR 降级为 WARN（v1.3）：

- 仅扫教程**正文**（剥离 frontmatter 后扫 wikilink）
- 教程 frontmatter 的 `related / prerequisites / sources` 完全豁免

这样：
- pre-commit 不再硬阻断教程引外部（解决 R31 fix_asymm 踩坑）
- 但仍提示"web-app 渲染时会显示为不可点击文本"

## 备选方案 (Alternatives)

### 方案 A：删除所有教程 → 外部页的引用

- **优点**：lint / web-app / 读者三方都简单
- **缺点**：损失"教程↔架构↔模块"图边；query.py 多页综合查询会漏 ADR / 漏架构层；图谱完备性破坏
- **拒绝理由**：违反 [[60-decisions/0004-knowledge-graph-query]] 的"图谱完备性"前提

### 方案 B：把外部页也纳入 web-app collection

- **优点**：所有 wikilink 都可点击，无 404
- **缺点**：架构/模块/topic 等页面是给 Agent 而非给读者看的（无 hero、无系列导航、无学习路径）；强行渲染会破坏教程站的体验聚焦
- **拒绝理由**：web-app 定位是「教程阅读站」（[[60-decisions/0001-knowledge-base-web-app]]），不该承担 wiki 全量浏览职责

### 方案 C：保留 ERROR，只允许架构页 → 教程的单向引用

- **优点**：read-only nav，单向语义清晰
- **缺点**：`asymm-link` 警告无法消除（rule 要求双向）；教程页无法在 frontmatter 标注前置依赖；query.py 的"reverse prerequisites"反向边失效
- **拒绝理由**：与本项目的双向链接 schema（详见 [[60-decisions/0004-knowledge-graph-query]] §5.3.3）相违

### 方案 D（★ 选定）：分层策略 — 图谱保留 + 渲染降级 + 规则放宽

如上「决策」节描述。

## 实施 (Implementation)

### 一、`web-app/src/plugins/remark-wiki-links.ts`

```typescript
// 教程内部 → 可点击 <a>
if (isTutorialId(pageId)) {
  out.push({
    type: 'link',
    url: tutorialIdToUrl(pageId, anchor),
    children: [{ type: 'text', value: label }],
  });
} else {
  // 外部 → 不可点击 <span>，带 tooltip
  out.push({
    type: 'html',
    value: `<span class="wiki-link-external" title="该页仅在项目知识库中可见（${pageId}）">${label}</span>`,
  });
}
```

同 plugin 内删除「跨节提示」paragraph：

```typescript
function isCrossSectionHintParagraph(p: Paragraph): boolean {
  if (p.children.length !== 1) return false;
  const onlyChild = p.children[0];
  if (onlyChild.type !== 'emphasis') return false;
  // 收集 emphasis 内文本，匹配「本节」「上一节」「下一节」关键词
  return /本节|上一节|下一节/.test(collectText(onlyChild));
}
```

### 二、`web-app/src/styles/typography.css`

```css
.wiki-link-external {
  color: var(--text-secondary);
  opacity: 0.65;
  text-decoration: underline dotted;
  text-underline-offset: 2px;
  cursor: not-allowed;
  background: rgba(148, 163, 184, 0.06);
  padding: 0 2px;
  border-radius: 2px;
}
.wiki-link-external::before {
  content: "📒 ";
  font-size: 0.75em;
  opacity: 0.7;
}
```

### 三、`.codebuddy/skills/project-wiki/scripts/wiki_lint.py`

```python
def check_tutorial_internal_refs(pages: list[WikiPage]) -> list[Issue]:
    """v1.3：剥离 frontmatter 后再扫；severity = warn。"""
    for page in pages:
        if not _is_tutorial_page(page):
            continue
        # 剥离 frontmatter 行（豁免 related/prereq/sources 内的外部引用）
        body = "".join(text.splitlines(keepends=True)[page.fm_lines:]) if page.fm_lines else text
        clean = strip_code(body)
        for m in WIKILINK_RE.finditer(clean):
            target = m.group(1).strip()
            if target.startswith(TUTORIALS_SUBDIR) or target in {"index", "overview"}:
                continue
            issues.append(Issue(
                code="tutorial-ext-ref",
                severity="warn",  # v1.3 降级
                ...
            ))
```

## 后果 (Consequences)

### 正面

- **图谱完备性保留**：query.py 的多页综合查询不再因为 lint 规则而被迫精简
- **fix_asymm.py 可正常工作**：不再因添加教程 frontmatter 回引而触发 ERROR
- **web-app 读者无 404**：外部 wikilink 视觉降级为不可点击文本，UX 明确
- **跨节提示行不污染教程页**：阅读体验聚焦本节内容
- **pre-commit 不再硬阻断**：tutorial-ext-ref WARN 不影响 commit
- **保留视觉提示**：📒 前缀让读者知道「该术语在 wiki 中有对应页，但不在教程站」

### 负面 / 代价

- **web-app remark plugin 复杂度↑**：从单一职责（处理 wikilink）变为双职责（含跨节提示删除）
- **lint 规则从 ERROR → WARN**：约束力下降，但 ADR 文档化决策弥补；若担心倒退可考虑加 hard rule "frontmatter 中外部引用必须用引号包裹的列表项"
- **额外的样式定义**：`.wiki-link-external` 需在 typography.css 维护，与 `.prose-tutorial` 样式系统耦合
- **跨节提示永久不可见**：未来若想让用户感知"上一节末页"，需要重新设计组件（普通文本提示 / 学习路径侧栏）

### 中性影响

- 现有 5 处教程正文外部 wikilink 已在 [[60-decisions/0004-knowledge-graph-query]] 修复阶段改为普通文本，本 ADR 后即便回退也不会立刻触发 WARN
- nav_inject.py 仍然生成 `_本节: 技术教程_` 等单纯标记行（无跨节链接也匹配关键词）→ 全部被删除，符合用户意图

## 验证 (Validation)

### 验证步骤

1. **wiki 端**：
   - `wiki_lint --check` 后 `tutorial-ext-ref` 不再出现在 ERROR 段（验证降级生效）
   - `fix_asymm.py --apply` 执行后无新 ERROR（验证规则放宽消解了冲突）

2. **web-app 端**：
   - `pnpm dev` 跑起来；打开任意教程页，验证：
     - 内部教程 wikilink → 可点击跳转
     - 外部 wikilink（如教程文末 `[[10-architecture/...]]`）→ 灰色不可点击
     - 跨节提示行（`_本节: 技术教程_` / `_本节: ... · 下一节首页: ..._`）→ 不渲染
   - `pnpm build && pnpm preview` 验证静态构建后行为一致

3. **lint 端**：
   ```bash
   python3 .codebuddy/skills/project-wiki/scripts/wiki_lint.py --check
   # 应为 0 errors（不再因 tutorial-ext-ref 报错）
   ```

### 后续 review 时机

- **web-app 静态构建验证**：跑一次 `pnpm build` 确认外部 wikilink HTML 输出正确
- **wiki 规模达 500 页**：复测 `tutorial-ext-ref` WARN 数量是否爆炸；若大量 WARN 影响信号 → 进一步降级为 INFO 或加白名单
- **新增工作流**：若有新工作流（如 `quiz` / `interactive-demo`）需要把外部页拉进 web-app，再评估是否扩展 collection

## R32 演进：导航分组策略简化（2026-05-23）

### 触发问题

ADR-0005 落地后实测发现 `nav_inject.py` 仍存在两个隐患：

1. **互斥模式静默切换**：脚本提供 `--section-scope` 与默认全局两种模式，nav 块输出格式不同。两次 `--apply` 之间若忘传 `--section-scope`，会**静默**地把 270+ 文件从一种模式切换到另一种，diff 噪音巨大且无警告
2. **`## ` 分组粒度过粗**：项目 index.md 的 `## 技术教程` 这一个 section 包含 23 个教程系列，section-scope 模式下 GAS 末页仍可能跨到 UMG 首页，达不到"系列内连续"的初衷

实例：
- `30-tutorials/gas/00-GAS系统总览` 的 prev 是 `30-tutorials/umg/09-UMG性能优化`（GAS 系列首页竟来自 UMG 系列末页）
- `30-tutorials/gas/26-Lyra综合案例死亡能力链` 的 next 是 `30-tutorials/movement-system/00`（GAS 系列末页跳到移动系统）

读者按 nav 翻页时跨教程系列乱跳，**学习路径噪音 > 浏览便利**。

### R32 决策

**删除互斥模式，统一为「目录段分组」单一模式**。规则：

- nav 分组键 = page_id **目录路径**的前两级（末段视为文件名，不计入分组）
- prev/next **绝不跨组**：组首页 prev=None，组末页 next=None
- 不再产生 `_本节: ... · 上一节末页: ..._` 跨段提示行

分组示例：

| page_id | nav_group |
|---|---|
| `30-tutorials/gas/00-GAS系统总览` | `30-tutorials/gas` |
| `30-tutorials/network-sync/iris/00-Iris总览` | `30-tutorials/network-sync` |
| `20-modules/cpp/ALyraCharacter` | `20-modules/cpp` |
| `10-architecture/overview` | `10-architecture` |
| `10-architecture/subsystems/ability-system` | `10-architecture/subsystems` |
| `40-runbooks/how-to-add-gameplay-ability` | `40-runbooks` |
| `60-decisions/0005-tutorial-cross-link-policy` | `60-decisions` |
| `80-gotchas/networking-ue57-review-checklist` | `80-gotchas` |

### 实施

1. **`nav_inject.py` 重构**：
   - 删除 `IndexSection` / `parse_index_with_sections` / `run_section_scope` / `section_ctx` / `--section-scope` argparse
   - 新增 `nav_group(page_id)` 函数 + `build_position_map` 不跨组逻辑
   - 共减少约 90 行代码

2. **全量 nav 重生成**：跑 `nav_inject.py --apply` 一次，270+ 文件统一切换到新分组规则
   - 教程系列首页 prev=∅，系列末页 next=∅
   - 子目录页（如 `network-sync/iris/`）正确归属父系列
   - 单层目录（runbooks / decisions / gotchas / topics）内连续翻页

3. **保留 web-app remark plugin 的「跨节提示行删除」逻辑作为 dead-code 兜底**：
   - 该逻辑（`isCrossSectionHintParagraph` + `paragraph` 删除节点）在 R32 后失去 input source（脚本不再产生该行）
   - 但保留可防御 git 历史回退 / 旧分支恢复带来的脏数据
   - 维护成本极低（约 10 行 TypeScript）

### 后果

| 类型 | 影响 |
|---|---|
| ✅ 正面 | nav 噪音消失（GAS 末页不再跳 movement-system）；脚本简化（少 90 行）；不再有"模式静默切换"陷阱 |
| ✅ 正面 | wiki_lint `tutorial-ext-ref` warn 归零（旧的 nav 跨节链接是该警告的最大来源） |
| ⚠️ 中性 | 部分孤儿组（如 `10-architecture/overview` 单页成组）prev/next 都为空，但符合 overview 类页面的导航定位 |
| ⚠️ 中性 | 简单的"前两级目录"规则不可调整；若未来出现需要更细粒度（如 `30-tutorials/gas/lessons/` vs `30-tutorials/gas/case-study/`）须额外讨论 |
| ❌ 代价 | nav_inject 脚本 R27 引入的所有 section-scope 复杂度被废弃；这是必要的简化 |

### 经验：避免"开关式互斥模式"

`--section-scope` 当时引入是想"先保留旧行为，新行为靠 flag 渐进迁移"。**实际效果是制造了静默状态切换的隐患**。教训：**项目级、影响所有页的格式选择，不应该靠 CLI flag 让用户在每次调用时选择**。要么彻底切换，要么干脆放弃。这条经验同样适用于未来其他全量改写工具（`fix_asymm` / `rename_page` / `wiki_lint` 等）。

## 经验沉淀

> **当两个工具的硬规则相互冲突，往往意味着设计层面缺失了一条「分层抽象」**。

| 反应 | 结果 |
|---|---|
| 只让一方让步（删边或忽略检查） | 系统性地损失某一边的能力 |
| ✅ **分清楚两方真正服务的对象** | wiki 服务 Agent / 图谱完备性；web-app 服务读者 / 可达性。两层各自完备。lint 规则在两层之间做"翻译" |

本次冲突还揭示出本项目独有的「knowledge graph 与 reader-facing 静态站」双层架构——后续若再有类似工具间冲突（例如 `wiki_lint` 的某规则与 `nav_inject` 的输出冲突），可参照本 ADR 的「图谱端保留 + 渲染端分层 + 规则降级豁免」三段式套路处理。

相关：[[60-decisions/0001-knowledge-base-web-app]]（web-app 基础架构）、[[60-decisions/0004-knowledge-graph-query]]（知识图谱化查询的工具与规范）。

<!-- nav:auto -->

---

**导航**: ← [[60-decisions/0004-knowledge-graph-query|0004-knowledge-graph-query]]

<!-- /nav:auto -->
