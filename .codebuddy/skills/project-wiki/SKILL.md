---
name: project-wiki
version: 1.0.0
description: UE 技术学习知识库系统。管理 Docs/ 下的技术教程、架构文档、模块说明、操作手册，为 AI Agent 提供结构化知识基座，支持系统性教学和技术问答。
---

# project-wiki — UE 技术学习知识库系统

> 让 AI Agent 基于结构化知识库进行技术教学，而不是每次从零推导。

## 知识库定位

本知识库是 **UE 技术学习知识库**，不是项目开发文档：

- **核心内容是教程** — `30-tutorials/` 包含 5 个系列 73 篇深度技术教程
- **以 Lyra 为锚** — 每个引擎概念对应 Lyra 项目中的真实实现
- **AI 写、人审、git 兜底** — 所有页面都是 markdown，diff 可读、可回滚
- **永远 git + markdown** — 规模超千页前不引入数据库或外部检索服务

## 核心理念

本 skill 基于 [karpathy/llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 的思路，针对**技术学习场景**做了工程化扩展：

- **三层架构**：Raw（`Docs/_raw/`）/ Wiki（`Docs/` 各目录）/ Schema（`Docs/.wiki-schema.md`）
- **教程为核心**：`30-tutorials/` 是知识库的主力内容，不是附属参考
- **学习路径驱动**：每个教程系列有 `_series.yaml` 定义由浅入深的阅读顺序
- **三层教学结构**：概念直觉 → 技术机制 → Lyra 实例

## 管辖范围

本 skill 统一管理 `Docs/` 下**所有知识**：

| 内容类型 | 目录 |
|---------|------|
| 技术教程系列（★ 核心） | `30-tutorials/` |
| Lyra 架构文档 | `10-architecture/` |
| Lyra 模块文档（C++ 类） | `20-modules/` |
| 操作手册 | `40-runbooks/` |
| 外部参考资料 | `50-references/` + `_raw/external/` |
| 决策记录 | `60-decisions/` |
| 横切主题 / 已知坑 / 快照 | `70-topics/` / `80-gotchas/` / `90-snapshots/` |
| 元规则与学习路线 | `00-meta/` |

## 每次会话**必读**入口文件

**以下文件每次会话开始时按顺序读取：**

1. `Docs/00-meta/ai-playbook.md` — AI 协作手册（检索优先级、教学约束、写 wiki 规范）
2. `Docs/overview.md` — 项目顶层概览
3. `Docs/.wiki-schema.md` — 知识库 schema（目录、type 枚举、frontmatter 字段）
4. `Docs/index.md` — 知识库全量目录（每次查询前必读）

## 工作流路由

> **根据用户意图，读取对应工作流文件**

### 知识消费（读）

| 用户意图 | 工作流 | 文件 |
|---------|--------|------|
| "XX 是什么"、"帮我理解 XX"、"讲讲 XX" | **teach** | `workflows/teach.md` |
| "分析 XX 源码"、"trace XX 调用链" | **source-trace** | `workflows/source-trace.md` |
| "项目里 X 是什么"、"为什么选 Y"、"在哪改 Z" | **query** | `workflows/query.md` |

### 知识生产（写）

| 用户意图 | 工作流 | 文件 |
|---------|--------|------|
| "创建 XX 技术专题"、"新增 XX 教程系列" | **create-series** | `workflows/create-series.md` |
| "优化 XX 教程"、"给 XX 系列补一篇"、"XX 教程需要更新" | **evolve-series** | `workflows/evolve-series.md` |
| 给 spec / PR / 设计文档 / "消化进知识库" | **ingest** | `workflows/ingest.md` |
| 给 URL / 外部文章 / UE 官方文档 / "消化这篇" | **ingest**（外部素材分支） | `workflows/ingest.md` |
| "把这次会话沉淀进 wiki"、"crystallize" | **crystallize** | `workflows/crystallize.md` |
| "深度分析 X"、"对比 X 和 Y"、"梳理 X 演化" | **digest** | `workflows/digest.md` |

### 知识维护

| 用户意图 | 工作流 | 文件 |
|---------|--------|------|
| "review XX 系列"、"检查教程质量"、"审查教程" | **review-series** | `workflows/review-series.md` |
| "check 知识库"、"lint" | **lint** | `workflows/lint.md` |
| "更新索引"、"重建索引"、"rebuild 检索"、"刷新数据库"、"构建向量索引" | **rebuild-index** | `workflows/rebuild-index.md` |
| "初始化项目知识库"、"project-wiki init" | **init** | `workflows/init.md` |

### 默认规则

- 用户给项目内素材但没说做什么 → 走 **ingest**
- 用户给 URL 或外部文章 → 走 **ingest（外部素材分支）**
- 用户问技术概念/原理 → 走 **teach**
- 用户要求分析源码实现 → 走 **source-trace**
- 用户要求改进/补充/更新已有教程 → 走 **evolve-series**
- 用户要求审查/检查教程质量 → 走 **review-series**
- **用户说"更新索引/重建索引"等模糊表述 → 走 rebuild-index 的增量模式（默认）**；只有用户**明确**说"全量/drop/from scratch"才走全量
- **teach / ingest / crystallize 中发现教程改进点** → 主动建议走 **evolve-series**（不自动执行，等用户确认）
- **create-series / evolve-series 大改完成后** → 主动建议走 **review-series**，并主动建议跑 **rebuild-index**（增量）让 wiki.db 同步（不自动执行，等用户确认）
- **任何写 wiki 的工作流收尾时**（ingest / crystallize / evolve-series / create-series / lint --fix）→ 主动建议 `wiki_rebuild.py --incremental` 让索引同步（不自动执行）

## 通用前置检查（除 init / lint / review-series 外）

1. 检查 `Docs/.wiki-schema.md` 是否存在
   - 不存在 → 提示"知识库未初始化，是否先 init？"
2. 读取 `.wiki-schema.md` 的目录结构、type 枚举、frontmatter 规范
3. 读取 `Docs/index.md` 做轻量定位
4. **★ 任何涉及"查 wiki / 找重 / 检索 / 收集来源 / 检查影响"的步骤，一律先用查询脚本**：

   **首选：Tier 1/2 引擎（`wiki_query.py`，FTS5 BM25 排序，毫秒级）**
   ```bash
   # 基础查询（CamelCase 自动拆分 + CJK 字符级匹配）
   python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "<keyword>"

   # 种子模式：以某 id 为种子，展开多类型 1-hop 邻居（related / prereq / wikilink + 反向边）
   python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py --id <page-id>

   # 系列模式：列出某教程系列的全部课程（按 lesson_index 排序）
   python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py --series <slug>

   # 限定 category / domain 软降权（不硬过滤）
   python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "ability" --category 30-tutorials --domain gas
   ```

   **次选：Tier 0 引擎（`query.py`，仅作诊断/降级 fallback）**
   ```bash
   # ★v1.1 起 wiki_query.py 已集成 alias / anchors / series-prev/next 全部 Tier 0 特性 ★
   # query.py 仅在以下场景使用：
   #   1. wiki.db 不存在（首次构建前的 fallback）
   #   2. 调试：想看 body grep 命中行号（L42, L88...）
   #   3. 想看 BODY-ONLY MATCHES 区块（grep 命中但 BM25 没强候选的页）
   #
   # 推荐通过 wiki_query.py 的统一入口委托（自动加 deprecation 提示）：
   python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "<keyword>" --engine grep
   ```

   **首次使用前需要构建索引**（一次性，毫秒级；Docs/ 变更后跑 `--incremental`）：
   ```bash
   python3 .codebuddy/skills/project-wiki/scripts/wiki_rebuild.py --incremental
   ```

   `rg` 仅作最后的 fallback（两个查询脚本都不可用，或单文件结构化统计场景）。
   依据：[query 工作流](./workflows/query.md)的"按问题形态选检索路径"，多页综合 / 决策性引用 / 创建新页 / 教程系列导航 / 检查影响**禁止跳过图层**。

## 检索引擎分层（Tier）

知识库检索引擎按规模渐进升级，由 `config.yaml` 的 `retrieval.engine` 控制（默认 `auto`）：

| Tier | engine 值 | 策略 | 依赖 | 适用规模 |
|---|---|---|---|---|
| Tier 0 | `grep` | `query.py` 文件扫描 + 启发式评分 + body grep 行号（**仅作诊断 fallback**；alias/anchors/series 已上移 Tier 1） | Python stdlib | wiki.db 不可用时 / **Tier 1/2 零候选/异常时自动 fallback** |
| Tier 1 ★ | `sqlite` | `wiki_query.py` FTS5 BM25 + 列权重 + 知识图谱 + alias 词表 + anchors 命中 + series-prev/next 隐式边 | Python stdlib（sqlite3 内置） | **本项目当前默认**（200 - 3000 页） |
| Tier 2 | `hybrid` | BM25 + Vector + RRF 融合 + 位置感知 | + `pip install sqlite-vec` + embedding API | 3000+ 页 |

**v1.1.2 自动 fallback**：`wiki_query.py` 在 Tier 1/2 执行**抛异常**或**关键词模式零候选**时，自动委托 Tier 0（query.py）兜底，无需用户手动切换。设 `PROJECT_WIKI_NO_AUTO_FALLBACK=1` 可禁用。

详细原理见 [`reference/retrieval-engine-design.md`](./reference/retrieval-engine-design.md)。
索引重建详见 [`rebuild-index 工作流`](./workflows/rebuild-index.md)（默认增量、毫秒级）。

## 全局反模式（所有工作流通用）

- ❌ **跳过查询脚本直接 `rg` 全 Docs/** — 在 346 页 + 2500+ wikilink 规模下噪音过高，会漏 ADR / 漏 series / 漏 prereq 链
- ❌ **引用 `status: stale / deprecated` 页面而不警告** — `wiki_query.py` / `query.py` 都已自动报警，忽略警告 = 反模式
- ❌ **多页综合 / 创建新页 / 检查影响等场景跳过图遍历** — 等价于裸 grep，丢失图谱价值
- ❌ **用关键词模糊指代不写 wikilink** — "如前所述"、"详见相关文档"必须替换为 `[[id]]`
- ❌ **`Docs/` 大批量改动后不跑 `wiki_rebuild.py --incremental`** — Tier 1/2 命中会失真（FTS5 索引滞后于 .md 真相源）
- ❌ **用户说"更新索引"就走全量重建** — 默认必须走增量（`--incremental`，毫秒级）；只有用户**明确**说"全量/drop/from scratch"才删库重建
