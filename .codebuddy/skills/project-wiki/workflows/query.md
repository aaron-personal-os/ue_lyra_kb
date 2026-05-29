# 工作流：query（查询项目知识库）

> v2.1（v1.1 集成后）：知识库已达 346 篇 / 2500+ wikilink / 280+ prerequisites / 416+ series-prev/next 边，
> 进入图谱 + FTS5 BM25 黄金区间。**统一入口走 `wiki_query.py`，已包含原 query.py 的全部 Tier 0 特性**。

## 检索引擎选择

| 入口 | 引擎 | 优势 | 何时用 |
|---|---|---|---|
| **`wiki_query.py`** ★ | **Tier 1: SQLite FTS5 BM25**（自动选 Tier） | 毫秒级；BM25 列权重；CJK 字符级中文匹配；多类型边邻居（related / prereq / wikilink / **series-prev/next** + 反向边）；**alias 词表扩展**（GAS ↔ Gameplay Ability System）；**anchors 命中**（代码反查 wiki）；可升级到 Tier 2 Hybrid | **统一入口**（v1.1 起涵盖原 query.py 全部能力） |
| `--engine grep` | Tier 0: 委托 query.py | body grep 命中行号详情；BODY-ONLY MATCHES 区块（调试用） | wiki.db 不可用 / 想看 body 行号详情 / 调试 BM25 是否漏页 |
| `rg` 兜底 | grep | — | 上面都不可用；单文件结构化统计 |

**首次使用前必须构建索引**（一次性 < 0.5s；Docs/ 变更后跑 incremental）：

```bash
python3 .codebuddy/skills/project-wiki/scripts/wiki_rebuild.py --incremental
# Docs/ 大量变更后退出码 1（--check 模式）即提示需要 rebuild
```

## 强制顺序：先 wiki，再代码

**任何技术问题**都按这个顺序：

1. 先走本工作流查 wiki
2. wiki 没有 / 不够 → 再去读源码
3. 源码与 wiki 矛盾 → 标记 wiki 页 `status: stale`，提示走 lint

## ★ 推荐路径：wiki_query.py 一击查询

```bash
# 关键词查询（CamelCase 自动拆分 + 中文 CJK 字符级匹配 + alias 词表扩展）
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "GAS GameplayTag 网络复制"

# 种子模式：多类型 1-hop 邻居（related / prereq / wikilink / series-prev/next + inverse-* 反向边）
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py --id 30-tutorials/gas/19-Tag网络复制

# 系列模式：列出某教程系列的全部课程 + 跨系列邻居
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py --series gas

# 限定 category / domain（软降权，不丢结果）
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "ability" --category 30-tutorials --domain gas

# 关闭 alias 扩展（精确查）
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "ability" --no-alias

# 强制 Tier（极少需要：仅诊断 / 调试用）
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "ability" --engine grep    # → 委托 query.py（body 行号详情）
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "ability" --engine sqlite  # → 强制 Tier 1
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "ability" --engine hybrid  # → Tier 2（需向量索引）

# JSON 输出（喂给 Agent / 下游工具）
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "ability" --json
```

输出包含：
- **TOP N 候选**（id / score / status / type / category / domain / series#lesson / related / prereq / why / status warnings）
- **Alias-expanded**（哪些同义词被自动扩展进 token 集，仅在 alias 真正命中时显示）
- **1-HOP NEIGHBORS**（标注边类型 `via:related / via:prerequisite / via:wikilink / via:series-prev / via:series-next / via:inverse-*`）
- **why 字段**：`fts5-bm25(raw=X.XX); anchor-hit:tokens(+X.XX); id-fulltoken:token(+X.XX); category-mismatch(...); status=stale(×0.5)` 等可解释信号
- **建议先读** + **Tier 标识**

## query.py 历史地位（v1.1 后）

> ⚠️ v1.1 起，原 `scripts/query.py` 的全部独有特性已集成到 `wiki_query.py`：
> - ✅ alias 词表扩展（`--no-alias` 关闭）
> - ✅ anchors 路径命中（自动；查 LyraCharacter Top-1 命中模块文档）
> - ✅ series-prev/next 隐式边（自动；wiki_rebuild.py 构建时写入 links 表）
>
> `query.py` 仍保留为 Tier 0 fallback，仅在以下场景用：
> 1. **wiki.db 不可用**（首次构建前 / 损坏 / 手工清缓存）
> 2. **想看 body grep 命中行号** `L42, L88, L120`（调试 / 找 index.md 漏录）
> 3. **想看 BODY-ONLY MATCHES 区块**（grep 命中但 BM25 没强候选的页）
>
> 直接调用 `query.py` 会输出 stderr deprecation 提示。统一入口推荐 `wiki_query.py --engine grep`。

### v1.1.2 自动 fallback 链路（★新增★）

**`wiki_query.py` 现在有 4 条路径 fallback 到 Tier 0（query.py），用户无需手动切换**：

| # | 触发条件 | 行为 | stderr 提示 |
|---|---|---|---|
| 1 | 用户显式 `--engine grep` | 直接走 Tier 0 | （deprecation 提示） |
| 2 | `engine=auto` 且 wiki.db 不存在 | `determine_tier()` 返回 grep | （deprecation 提示） |
| 3 | `engine=sqlite/hybrid` 但 wiki.db 不存在 | `determine_tier()` 自动降级 | （deprecation 提示） |
| 4 | **Tier 1/2 执行抛异常或返回零候选**（keyword 模式） | **★ 自动委托 Tier 0 ★** | `[wiki_query] 自动 fallback → Tier 0` |

**禁用自动 fallback**（仅调试场景；正常使用不要禁用）：

```bash
PROJECT_WIKI_NO_AUTO_FALLBACK=1 python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "..."
```

**为什么 seed/series 模式不触发 fallback**：种子页 / 系列名找不到时，Tier 0 也找不到，重复一遍无意义（已在 main() 中显式排除）。

### 实际效果

```bash
# 极少命中的查询：Tier 1 BM25 零候选 → 自动 fallback Tier 0 body grep
$ python3 wiki_query.py "qzqzqzqzqz9999"
[wiki_query] Tier 1 零候选（BM25 未命中），尝试 Tier 0 启发式 + body grep 兜底
[wiki_query] 自动 fallback → Tier 0 (query.py)。如需禁用，设 PROJECT_WIKI_NO_AUTO_FALLBACK=1
[query.py deprecation] 推荐改用 wiki_query.py（...）
Query: 'qzqzqzqzqz9999'
⚠ No candidate hit. Falling back to body grep below.
...
```


## 按问题形态选检索路径

| 问题形态 | 必经路径 | 推荐入口 | 何时可跳过图层 |
|---|---|---|---|
| **单点关键词查询** | 查询脚本 | `wiki_query.py "<keyword>"` | wiki 关键词无歧义且只需一页时可裸 grep |
| **中文查询**（"封装层"/"网络复制"） | 必经 FTS5 CJK 预处理 | `wiki_query.py "<中文>"` | ❌ 不允许 grep 中文（unicode61 行为复杂） |
| **多页综合**（"X 演化"、"X vs Y"） | 查询脚本 → 沿 related / prereq 1-hop / 必要时 2-hop → 必要时 rg 兜底 | 任一查询脚本 | ❌ 不允许跳 |
| **决策性引用**（"我应该选 X 还是 Y"） | 查询脚本 → 检查每个引用页 status → 不引 stale / deprecated 不警告 | 任一查询脚本 | ❌ 不允许跳，必须验 status |
| **创建新页 / ingest 查重** | 查询脚本 → 找 ≥ 70% 重叠 → update 而非 create + 双向链接 | `wiki_query.py`（多 token 命中更准） | ❌ 不允许跳，否则产生重复页 |
| **教程系列导航**（"GAS 全套"、"网络同步学习路径"） | `--series <name>` | 任一查询脚本（推荐 wiki_query.py，按 lesson_index 严格排序） | 直接 ls 目录会丢 lesson_index 顺序 |
| **从代码反查 wiki**（"哪些 wiki 提到 LyraCharacter.cpp"） | 含 anchors 命中（v1.1 已上移 Tier 1） | `wiki_query.py "lyracharacter"`（自动 anchor-hit + id-fulltoken bonus） | 也可 `rg -l 'path:.*LyraCharacter\.cpp' Docs/` 兜底 |
| **alias / 同义词扩展**（"找 GAS 同义词页"） | 必经 alias 词表（v1.1 已上移 Tier 1） | `wiki_query.py "GAS"`（自动扩展 'gameplay ability system'） | `--no-alias` 关闭精确查 |

## Fallback：wiki_query.py 不可用时（手工 4 步）

仅当 `wiki_query.py` 报错或无法跑时使用（极少出现，因为 Tier 1 失败会自动 fallback 到 Tier 0）：

```bash
# L1: 读目录定位候选 id
cat Docs/index.md

# L2: 读候选页 frontmatter 拿 related / prerequisites / anchors / status
rg -l --multiline 'tags:.*GAS' Docs/30-tutorials/gas/

# L2.5: 1-hop 邻居（grep wikilink 入边）
rg '\[\[30-tutorials/gas/19-Tag网络复制\]\]' Docs/

# L3: 全文兜底（仅当前两层都没命中）
rg -i 'gameplay.?ability' Docs/
```

## 综合回答的规范

1. **必须标注引用**：每个技术结论后加 `(详见 [[wiki-id]])`，禁止使用"如前所述 / 详见相关文档"等无锚点指代
2. **如发现 stale**：在回答开头明示"⚠️ 相关 wiki 页 [[xxx]] 标记为 stale，已基于当前代码 re-verify"
3. **如发现 deprecated**：拒绝引用，找替代页（沿 related 跳到 status=current 的同类）
4. **如发现矛盾**：列出两个来源，请用户裁决
5. **如发现缺页**：回答末尾建议"建议为 X 创建 wiki 页（暂未存在）"
6. **教程类问题**：优先引用 `30-tutorials/<series>/` 下的页，按 lesson_index 顺序导读

## 把好答案存回去（crystallize 触发点）

如果本次 query 的答案：
- 是一份**有结构的对比 / 分析**（不是简单事实查询）
- 用户表示有用、想保留

→ **主动提议**走 **crystallize** 工作流把答案存为新 wiki 页。

## 反模式（禁止动作）

- ❌ **跳过 wiki_query.py 直接 `rg` 全 Docs/** — 在 346 页规模下噪音过高，会漏 ADR / 漏 series / 漏 prereq 链
- ❌ **跳过 wiki 直接 `rg` 全项目源码** — 违反"源码为信源但 wiki 为入口"原则
- ❌ **引用 `status: stale` 或 `status: deprecated` 的页面而不警告** — wiki_query.py 已自动报警，忽略警告 = 反模式
- ❌ **多页综合查询不沿 related / prereq / series-prev/next 遍历** — 等价于裸 grep，丢失图谱价值
- ❌ **用关键词模糊指代不写 wikilink** — "如前所述"、"详见相关文档"必须替换为 `[[id]]`
- ❌ **改 wiki 页内容**（query 是只读）— 要改请走 ingest / crystallize / lint
- ❌ **直接调用 `query.py`**（v1.1 起已 deprecated）— 用 `wiki_query.py [--engine grep]` 统一入口

## 为什么本项目必须走图谱

简要论据（详见 schema 5.3.4-5.3.5 节 / 项目实测）：

| 指标 | 实测值 | 含义 |
|---|---|---|
| Docs 总文档数 | 346 篇 | 已超 100 页阈值，进入图谱 sweet spot |
| wikilink 出现总数 | 2533 处 | 平均 7.3 边/页，密度足够 |
| 含 `related:` 双链的页 | 150 / 346 = 43% | 主图骨架成型 |
| 含 `prerequisites:` 教程边 | 257 处 | 教程系列依赖边数量超 related，本项目特色 |
| 教程系列规模 | 5 系列 73 篇 | 集中度最高的子图，必须支持系列内导航 |
| 同名概念歧义 | GAS / GameplayTag / Replication / Experience 等 | 多页综合查询场景非常多 |

裸 grep 在这个规模下会：漏 ADR、漏 series、漏 prereq 链；命中 stale 不报警；同名概念歧义不消解。`wiki_query.py` 全部解决。
