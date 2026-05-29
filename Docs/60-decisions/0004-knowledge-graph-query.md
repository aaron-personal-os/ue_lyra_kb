---
id: 60-decisions/0004-knowledge-graph-query
type: adr
status: accepted
language: zh
owner: human
decided_at: 2026-05-23
decided_by: robert
anchors:
  - path: .codebuddy/skills/project-wiki/scripts/query.py
  - path: .codebuddy/skills/project-wiki/scripts/test_query.py
  - path: .codebuddy/skills/project-wiki/scripts/wiki_lint.py
  - path: .codebuddy/skills/project-wiki/SKILL.md
  - path: .codebuddy/skills/project-wiki/workflows/query.md
supersedes: []
superseded_by: []
# related 留空：ai-playbook / SKILL.md / workflows/* 是 meta 文档（无 frontmatter），按 schema 不在 wikilink 双向链接管辖范围；正文段落用普通引用
related: []
sources: []
last_synced: 2026-05-23
last_verified: 2026-05-23
tags: [adr, knowledge-graph, wikilink, query, project-wiki, retrieval, agent-workflow]
---

# ADR-0004：知识图谱化查询（query.py + 差异化规范）

> **2026-05-24 v1.1.1 更新**：本 ADR 描述的 `query.py` 已合并入 `wiki_query.py` 统一入口。
> 原 Tier 0 独有特性（alias 词表 / anchors 命中 / series-prev/next 隐式边）全部上移到 Tier 1，
> 详见 [[_raw/specs/2026-05-24-merge-query-into-wiki-query-eval]] 和
> [[_raw/specs/2026-05-24-tier0-features-into-tier1-eval]]。
> ADR 历史陈述保留不动；新代码请使用 `wiki_query.py`（旧 `query.py` CLI 仍可工作并显示 deprecation 提示）。

> 知识库规模达 346 篇 / 2533 处 wikilink，已进入 wikilink 双链图谱的 sweet spot。引入 `query.py` 一击查询工具与差异化检索规范，让 Agent 默认走"图谱优先 + grep 兜底"路径，同时把 8 个工作流的查询步骤统一接入。

## 背景 (Context)

### 问题

`Docs/` 在 v1.0 阶段已扩展到 **346 篇 markdown / 2533 处 wikilink / 257 处 prerequisites edge**。在原有 query 工作流的"三层漏斗（index → frontmatter → rg）"规范下，实测发现 Agent 的真实行为系统性偏差：

```text
✓ 加载 project-wiki skill
✓ 读 ai-playbook + wiki-schema + index.md
✗ 直接 rg 全 Docs/ 关键词     ← 跳过 frontmatter / related 邻居遍历
✗ 分段读命中文件，拼上下文      ← token 浪费 + 漏 ADR / 漏 prereq
```

按规范应该 L1 → L2 → L3，Agent 实际在做 L1 → L3，**跳过了"读候选页 frontmatter + related 做图遍历"这一关键层**。这不是 Agent 不守规矩，而是它在做合理但短视的局部最优——grep 是 LLM 的"肌肉记忆"，图遍历需要更刻意的结构化推理。

### Agent 偏好 grep 的根因（5 项）

| # | 根因 | 说明 |
|---|---|---|
| 1 | grep 是 LLM 肌肉记忆 | 训练中见过几百万次 `rg pattern dir/`，几乎是反射动作 |
| 2 | wiki 规模看似不大 | ~80-300 页时 grep 毫秒返回，从工具看没痛点 |
| 3 | 用户问题是关键词形态 | "spline procedural building" 是短语；map 到 wikilink id 多 1-2 步 |
| 4 | 图遍历需要先有种子节点 | 不先读 index 找候选就只能 grep 找种子；index 没被用作筛选工具 |
| 5 | 规范没显式禁止跳层 | 写的是"先 X 再 Y"，但缺"必须验证 L1/L2 不够才能下 L3"的硬性 gate |

**本质**：Agent 在做 token / 时间 / 推理成本的**局部最优**，但没看到图遍历在多页综合 / 抗幻觉 / 抗 stale 上的**全局收益**。

### 实测痛点（重构前裸 grep 流程）

| 场景 | grep 表现 |
|---|---|
| 单点查询 | 87 文件命中（噪音多），无 status / inbound 元数据 |
| 多页综合 | 154 文件淹没，无边类型，token 占用 ~460KB |
| 创建新页查重 | 13 文件需人工判断是否 ≥70% 重合，易产生重复页 |
| 抗 stale | **完全感知不到** `status: stale / deprecated`，照常引用 |

## 决策 (Decision)

**采用差异化规范 + 工具化降本，让图谱在它真正发挥价值的场景（多页综合 / 决策性引用 / 创建新页查重 / 教程系列导航）变成 Agent 的第一选择，但不强制单点查询也走图谱。**

### 决策要点

1. **工具层**：新增 `scripts/query.py` 把"L1 index 预筛 + L2 frontmatter / anchors / tags + 1-hop 多类型图邻居 + L3 grep 兜底"折叠成单次工具调用。复用 `wiki_lint.py` 的 `parse_frontmatter / WIKILINK_RE / strip_code / collect_pages`，纯 stdlib 无外部依赖。

2. **规范层**：在 `workflows/query.md` 写入 6 类问题形态的路由表（详见"实施"），明确**多页综合 / 决策性引用 / 创建新页 / 教程系列导航 / 检查影响**这五类禁止跳过图层。

3. **传导层**：把 `query.py` 接入 8 个相关工作流（teach / source-trace / digest / ingest / crystallize / create-series / evolve-series + SKILL.md 顶层）。`init / lint / review-series` 是结构化统计/审查性质，按设计不接入。

4. **本项目特化**：`query.py` 不是通用模板的直接套用，针对本项目知识库的特征做了 8 项定制（教程系列 + prerequisites 边 + alias 词表等，详见"实施"）。

## 备选方案 (Alternatives)

### 方案 A：继续维持纯规范约束（现状）

- **优点**：零工具维护成本，只改 ai-playbook
- **缺点**：实测证明 Agent 仍习惯性跳层 grep；规范越长读得越浅
- **拒绝理由**：违反"看到 design ↔ behavior gap 时，先把对的路做得更省力"的工程模式

### 方案 B：硬强制图谱（一刀切禁 grep）

- **优点**：行为一致性强
- **缺点**：单点查询付 30%-50% 时间惩罚；遇到 query.py 边界情况时 Agent 无 fallback
- **拒绝理由**：实测表明单点查询 grep 仍优；"按场景路由"才是更精细的设计

### 方案 C：上向量库 RAG（embedding + ANN）

- **优点**：语义检索召回率高
- **缺点**：embedding 重算成本高、可解释性差（黑盒）、与 wikilink 抗幻觉机制冲突、千页以下不划算
- **拒绝理由**：项目规模（346 页）远未到 RAG sweet spot（千~万页）；wikilink 已提供更可解释的图结构索引

### 方案 D：图谱仅作 query 工作流升级（不传导其它工作流）

- **优点**：改动量小
- **缺点**：teach / digest / ingest / crystallize 等工作流仍教 Agent 用 rg，绕开 query.py，新工具形同虚设
- **拒绝理由**：工具升级必须配套全工作流改造，否则"对的路 = 最省力的路"原则失效

## 实施 (Implementation)

### 一、query.py 工具

#### 1. 三种使用模式

```bash
# 关键词查询（默认开启 alias 词表扩展，e.g. GAS ↔ Gameplay Ability System）
python3 .codebuddy/skills/project-wiki/scripts/query.py "GAS GameplayTag 网络复制"

# 种子模式（看某 id 的图邻居：related / prereq / inverse-prereq / series-prev/next）
python3 .codebuddy/skills/project-wiki/scripts/query.py --id 30-tutorials/gas/19-Tag网络复制

# 系列模式（列出某教程系列的全部课程，按 lesson_index 升序）
python3 .codebuddy/skills/project-wiki/scripts/query.py --series gas

# JSON 输出（喂给 Agent 解析 / 后续工具）
python3 .codebuddy/skills/project-wiki/scripts/query.py "log rollup" --json --no-body

# 关闭 alias 扩展（精确查）
python3 .codebuddy/skills/project-wiki/scripts/query.py "ability" --no-alias
```

#### 2. 评分算法（无 LLM 纯启发式）

```text
score = id-hit       × 3.0
      + desc-hit     × 1.5
      + tag-hit      × 1.0
      + anchor-hit   × 1.2          # 文件名命中 anchors[].path（从代码反查 wiki）
      + type-hit     × 0.6
      + core-type-boost              # tutorial 0.4 / topic 0.3 / adr 0.3 / guide 0.2 / module 0.1
      + min(body-hit, 5) × 0.5
      + min(inbound, 10) × 0.1

alias-only token: × W_ALIAS_DAMP (0.6)   # 别名扩展出的 token 命中权重打折
status_multiplier: current 1.0 / draft 0.7 / stale 0.5 / deprecated 0.2
final_score = (sum_of_signals) × status_multiplier
```

并列时**教程按 lesson_index 升序**（先讲基础），其余按 id。

#### 3. 多类型图边展开（1-hop）

| 边类型 | 含义 |
|---|---|
| `related` | frontmatter `related:` 双向边 |
| `prereq` | frontmatter `prerequisites:` 教程前置依赖（A 依赖 B → B 是 A 的邻居） |
| `needed-by` | 反向 prereq（B 依赖 A → B 是 A 的邻居） |
| `series-prev` | 同 series 内 lesson_index - 1 |
| `series-next` | 同 series 内 lesson_index + 1 |

#### 4. 输出包含

- TOP N 候选（id / score / status / type / series#lesson_index / anchors / related / prereq / why / warnings）
- 1-HOP NEIGHBORS（候选页的多类型邻居，标注边类型 `via:related / via:prereq / via:needed-by / via:series-*`）
- BODY-ONLY MATCHES（grep 命中但 index 没强候选；自动跳过 `index / log / overview / README` 等 meta 文件）
- GLOBAL WARNINGS（候选含 stale / deprecated 时强制提示）
- 推荐先读 hint

#### 5. 相对通用 wiki 模板的本项目特化（8 项）

| # | 定制点 | 原因 |
|---|---|---|
| 1 | 修正 index.md 行格式 | 本项目用 `- [[id]] - desc`（无 `(type, status, date)` 元组），权威字段统一从 frontmatter 拿 |
| 2 | `prerequisites:` 升级为图边 | 本项目教程系列 257 处使用，是教程依赖的核心边 |
| 3 | inverse-prerequisites 反向边 | seed 模式能回答"哪些课依赖我" |
| 4 | 同 series + lesson_index 隐式边 | 73 篇教程的姊妹课程导航 |
| 5 | anchors 文件名命中加分 | 用户查 "lyracharacter" 能命中 `ALyraCharacter.md`（从代码反查 wiki） |
| 6 | alias 词表自动扩展 | 解析 `.wiki-schema.md` 的"别名词表"节，处理 GAS / Lyra / StateTree 等同义词 |
| 7 | 核心 type boost | tutorial / topic / adr / guide / module 小幅 boost，避免边缘 type 抢前排 |
| 8 | body grep 降噪 | 跳过 index / log / overview / README 等 meta 文件 |

### 二、按问题形态选检索路径（query.md 路由表）

| 问题形态 | 必经路径 | 何时可跳过图层 |
|---|---|---|
| **单点关键词查询** | `query.py "<keyword>"` | wiki 关键词无歧义且只需一页时可裸 grep |
| **多页综合**（"X 演化"、"X vs Y"） | `query.py` → 沿 related / prereq 1-hop / 必要时 2-hop | ❌ 不允许跳 |
| **决策性引用**（"我应该选 X 还是 Y"） | `query.py` → 检查每个引用页 status → 不引 stale / deprecated 不警告 | ❌ 不允许跳，必须验 status |
| **创建新页 / ingest 查重** | `query.py` → 找 ≥ 70% 重叠 → update 而非 create + 双向链接 | ❌ 不允许跳，否则产生重复页 |
| **教程系列导航**（"GAS 全套"） | `query.py --series <name>` | 直接 ls 目录会丢 lesson_index 顺序 |
| **从代码反查 wiki**（"哪些 wiki 提到 LyraCharacter.cpp"） | `query.py "lyracharacter"`（含 anchors 命中） | 可 `grep -rl 'path:.*LyraCharacter\.cpp' Docs/` 兜底 |

### 三、工作流接入（8 处）

| 工作流 | 接入点 |
|---|---|
| `SKILL.md` | 通用前置检查 #4 改为强制 query.py；新增 4 条全局反模式 |
| `workflows/query.md` | v1.0 重写为图谱优先 + 路由表 + fallback |
| `workflows/teach.md` | "定位相关教程"改 query.py；反模式补"直接 rg 跳过 query.py" |
| `workflows/source-trace.md` | "检索知识库"用 query.py 含 anchors 命中（替代 `rg path:`） |
| `workflows/digest.md` | "收集来源"必须走图谱（多页综合主战场） |
| `workflows/ingest.md` | 步骤 1 前置查重 + E5 近似查重均改 query.py |
| `workflows/crystallize.md` | **新增步骤 0 查重**（前置必做）+ 反模式补"跳过查重直接 create" |
| `workflows/create-series.md` | 1A.3 + 1B.4 知识库检索改 query.py |
| `workflows/evolve-series.md` | 步骤 6 "检查连锁影响"用 seed 模式（替代 `rg '\[\[X\]\]'`） |

**不接入（按设计）**：`init.md` / `lint.md` / `review-series.md` ——init 是初始化、lint/review 是结构化统计审查（rg / lesson_index 排序更合适）。

## 后果 (Consequences)

### 正面

- **抗 stale 质变能力**：grep 完全感知不到 `status: stale / deprecated`，query.py 强制 ⚠ 警告 + 自动把替代页顶到 TOP1
- **多页综合 token 节省 ~15×**：场景 B 实测 grep 命中 154 文件 ≈ 460KB，query.py 5 候选 + 11 邻居 ≈ 30KB
- **创建新页重复风险**：从"高"降到"极低"（score ≥ 6 自动判定 ≥70% 重合）
- **多类型边召回**：5 类边（related / prereq / needed-by / series-prev / series-next）一次展开
- **alias 自动扩展**：用户输入 "GAS" 自动覆盖 "Gameplay Ability System"，消歧能力提升
- **anchors 反查**：从代码文件名反查 wiki 路径变成一等公民
- **跨 Agent 协作一致**：通过 ADR-0001 / 0004 symlink 机制，Cursor / Claude Code / CodeBuddy / Codex 共享同一查询规范

### 负面 / 代价

- **单点查询时间增加 ~18×**：grep ~21M cycles vs query.py ~382M cycles（仍 < 1 秒，可接受）
- **维护成本**：query.py 与 wiki_lint.py 共享 frontmatter 解析；frontmatter schema 变更时需同步 review
- **学习曲线**：新 Agent 需要先理解 ai-playbook + schema 才能用好（已通过必读入口固定）
- **工作流改造扩散**：8 个工作流文件都加了 query.py 段落，文档量增加 ~15%

### 中性影响

- 在 200 页以下规模时 query.py 优势不明显（图密度过低 / grep 已够快）
- 千页规模后 1-hop 邻居可能爆炸，需要派生索引或迁移到 BM25+vector（v1.3+ 计划）

## 验证 (Validation)

### 单元测试

`scripts/test_query.py` 共 87 项断言，全部通过：

- tokenize / 别名扩展 / wikilink 归一化
- index.md 简化格式 + 兼容旧元组格式 + 去重
- 边收集（related / prerequisites / anchors / series / lesson_index）
- inverse-prerequisites / series_index 构建
- 评分（id / desc / tag / anchor / type / boost / alias 折扣）
- status_warning + STATUS_MULTIPLIER 单调性
- 真实 Docs/ 三种模式集成 smoke：keyword（含 alias 扩展）/ seed（多类型边）/ series

### 实测对比（4 场景）

| 场景 | grep 表现 | query.py 表现 | 结论 |
|---|---|---|---|
| **A. 单点查询**「Tag 网络复制」 | 87 命中（噪音） | TOP1 `[[30-tutorials/gas/19-Tag网络复制]]` score=11.8 锁定 | 单点 grep 时间快 18×，但 Agent 总成本反而更高 |
| **B. 多页综合**「GAS 网络复制 预测 演化」 | 154 命中淹没 | 5 候选 + 11 邻居（5 类边） | 噪音 30×、token 15×、含因果链 |
| **C. 创建新页查重**「想新建 Tag 网络复制教程」 | 13 命中需人工判 | TOP1 score=11.8 → 自动判定走 evolve-series | 重复页风险从"高"降到"极低" |
| **D. 抗 stale**（手工临时 stale 测试） | **完全感知不到** | ⚠ 警告 + 排序压低 + 替代页顶上 | 这是 grep 完全做不到的能力 |

### 后续 review 时机

- **wiki 规模达 500 页**：复测命中精度，看是否需要派生索引
- **wiki 规模达 1000 页**：评估迁移到 qmd（BM25+vector）或派生索引
- **新增重大 frontmatter 字段**（如 `lifecycle`、`audience`）：评估是否成为新一类图边
- **Agent 行为审计**：通过 `wiki_lint.py` 加 `query-without-citation` 规则（v1.1 P2）做反推

## 经验沉淀

> 看到 design ↔ behavior gap 时，**不要先想着加 enforcement，先想着把对的路做得更省力**。

| 反应 | 结果 |
|---|---|
| 加更多硬性约束 | Agent 表面遵守 / 实际偷工 / playbook 越写越读不进去 |
| ✅ **降低正确路径的成本** | Agent 自然走对的路，规范不必越写越长 |

`query.py` 是这条路径的具体落地——"对的路（图谱遍历）"和"最省力的路（一行命令）"重合，Agent 行为对齐。**ADR-0001 等之后的设计若再遇 design ↔ behavior gap，应优先复用此模式。**

<!-- nav:auto -->

---

**导航**: ← [[60-decisions/0003-dev-only-web-terminal|0003-dev-only-web-terminal]] · [[60-decisions/0005-tutorial-cross-link-policy|0005-tutorial-cross-link-policy]] →

<!-- /nav:auto -->
