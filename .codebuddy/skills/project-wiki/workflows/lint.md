# 工作流：lint（项目知识库健康检查）

> **v0.2 起已脚本化**：[`scripts/wiki_lint.py`](../scripts/wiki_lint.py)（~700 行 stdlib 单文件）。本工作流文档保留作为"检查项规范说明"，日常用脚本即可。
>
> - 项目根直接跑：`./lint_wiki.sh`（mac/linux）或 `lint_wiki.bat`（win）
> - pre-commit 自动跑：`bash .codebuddy/skills/project-wiki/scripts/install_pre_commit_hook.sh` 安装一次
> - **★v0.2★** 重算 anchor sha256：`./lint_wiki.sh --update-cache`（审过 wiki 后跑）
> - 详细使用 / 故障排除：[[40-runbooks/use-wiki-lint]]

## 检查项（v0.1）

### 1. wikilink 断链

```bash
# 找所有 [[xxx]] 引用
rg -o '\[\[([^\]]+)\]\]' -r '$1' Docs/ --no-filename | sort -u > /tmp/links.txt
# 找所有实际存在的 wiki id（由文件路径推导）
find Docs -name '*.md' -not -path 'Docs/_raw/*' | sed 's|^Docs/||; s|\.md$||' | sort -u > /tmp/pages.txt
# 差集即为断链
comm -23 /tmp/links.txt /tmp/pages.txt
```

每条断链产出建议：是该创建新页，还是修正 link？

### 2. 孤儿页

无任何 inbound link 的页面（`overview.md` / `index.md` / `00-meta/*` 不算孤儿）：

```bash
for page in $(find Docs/{10,20,30,40,50,60,70,80,90}-* -name '*.md' 2>/dev/null); do
  id=$(echo "$page" | sed 's|^Docs/||; s|\.md$||')
  count=$(rg -l "\\[\\[$id\\]\\]" Docs/ | wc -l)
  if [ "$count" -eq 0 ]; then
    echo "ORPHAN: $page"
  fi
done
```

孤儿页**未必要删**，但建议：
- 检查是否归类错误
- 检查 `index.md` 是否漏录
- 是否其实应该和其他页合并

### 3. 缺 frontmatter / 缺关键字段

每个 wiki 页（不含 `_raw/`、`00-meta/`、`index.md`、`log.md`、`overview.md`、`README.md`）必须有 frontmatter 且包含：

- `id`, `type`, `status`, `language`, `owner`
- `anchors`（至少 1 条，除非 type 是 `topic` 或 `adr`）
- `last_synced`

### 4. status 字段一致性

- `status: stale` 的页 → 收集列表，输出给用户决定 re-verify 或 deprecate
- `status: deprecated` 的页 → 检查是否还有 inbound link，有则警告"已弃用页仍被引用"
- `status: draft` 的页 → 报告"草稿数 N"

### 5. index.md 一致性

`index.md` 中列出的页面 vs 实际文件系统中的页面，找 diff：

- index 列了但实际没有的 → 报告"index 残留"
- 实际有但 index 没列的 → 报告"index 漏录"

### 6. 重复/近似页检测（轻量）

- 文件名 levenshtein 距离 < 3 的页面对 → 报告"疑似重复"
- 同一目录下 frontmatter `tags` 完全相同的页面对 → 报告"疑似重复"

## 输出格式

```markdown
# Lint 报告 — 2026-05-17

## 摘要
- 检查页数：N
- 严重问题：X 条
- 警告：Y 条
- 提示：Z 条

## 严重问题（必须修复）
- [ ] [BROKEN-LINK] `Docs/60-decisions/0001-project-knowledge-base.md` 引用了不存在的 `[[20-modules/cpp/ULyraAbilitySystemComponent]]`
- [ ] [MISSING-ANCHOR] `Docs/20-modules/cpp/ALyraCharacter.md` 缺 anchors 字段

## 警告（建议修复）
- [ ] [STALE] `Docs/30-tutorials/gas/02-ga-execution-flow.md` 距 last_synced 已 60+ 天

## 提示（可选处理）
- [ ] [ORPHAN] `Docs/70-topics/networking-and-synchronization.md` 无 inbound link
```

## 自动修复

询问用户："发现 N 个可自动修复的问题，是否一次性修复？（y/n）"

可自动修复的：
- 缺 `last_synced` → 补 `last_synced: <today>`
- 缺 `status` → 补 `status: draft`
- index 漏录 → 自动追加
- index 残留 → 自动删除

**不要**自动修复：
- 断链（需要决定是建新页还是改 link）
- 缺 anchor（需要人/AI 决定挂哪个文件）
- stale 标记（需要 re-verify）

## v0.1.5 已实现（2026-05-13）

详见 [`scripts/wiki_lint.py`](../scripts/wiki_lint.py) 模块 docstring。新增超过 v0.1 spec 的检查：

| 检查 | 严重级 | 触发 |
|---|---|---|
| `bad-anchor` | error / warn | frontmatter `anchors:` 路径在文件系统不存在；`Intermediate/` `Saved/` `LocalDevelop/` 等运行期生成路径降级为 warn |
| `id-mismatch` | error | frontmatter `id` 字段不等于文件路径推导的 id |
| `ascii-art` | warn | 代码块（无 lang 或 lang 不在白名单）含 box-drawing 字符或 `+---+` `|...|` `└──` 模式 |
| `asymm-link` | warn | A 在 frontmatter `related` 引了 B，但 B 没回引（双向链不闭环） |

> **注**：原 `variant-include` 检查（检测 `Source/ue_ai_demo/Variant_X/` 跨 Variant include）来自旧项目结构，LyraStarterGame 不使用 Variant 模式，已移除。

## v0.2 已实现（2026-05-14）

| 检查 | 严重级 | 触发 |
|---|---|---|
| `anchor-changed` | warn | anchor 文件 sha256 与 `.codebuddy/.../.cache/anchors.json` 不符 → wiki 可能漂移 |
| `version-drift` | warn | wiki 页提到的 `UE X.Y` 版本 ≠ `00-meta/project-versions.md` 权威值（`X.Y+` 最低版本声明豁免；`60-decisions/` `_raw/` `90-snapshots/` `log` `00-meta/project-versions` 自身豁免） |
| `cache-init` | info | 首次跑（cache 文件不存在）或 cache 有 stale 条目 → 提示跑 `--update-cache` |

新增子命令：

- `--update-cache`：重算所有 anchor sha256 → 写到 cache 文件（commit 进 git）
- `--show-cache`：打印 cache 概况（条目数 / top 10 引用最多的 anchor）

cache 文件位置：`.codebuddy/skills/project-wiki/.cache/anchors.json`（**必须 commit**，否则跨机协作无法检测漂移）

## v1.2 已实现（2026-05-21）

| 检查 | 严重级 | 触发 |
|---|---|---|
| `tutorial-ext-ref` | error | `30-tutorials/` 内文档的 wikilink `[[xxx]]` 引用了非 `30-tutorials/` 的外部页面（教程应自成体系，禁止引用 `70-topics/`、`10-architecture/` 等外部 wiki 页；`index`/`overview` 导航元文件豁免） |

## v0.3 计划新增

- 跨页同名实体冲突检测（同一个类 / 函数在多页有矛盾描述）
- 死代码检测（anchor 指向已删除/重命名的文件 → 自动建议 frontmatter 改）
- frontmatter `last_synced` 距今 N 天的"过期警告"
- GitHub Actions 集成（PR 触发自动跑 `--check`，红状态拦截合并）
