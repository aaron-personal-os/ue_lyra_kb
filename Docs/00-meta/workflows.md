# 工作流总览

> 记录本知识库的核心工作流：AI Agent 如何生产和维护知识，用户如何使用和贡献。

## 知识库工作流

本知识库由 10 种工作流驱动，分为三类：

### 知识消费（读）

| 工作流 | 触发 | 做什么 |
|--------|------|--------|
| **query** | "XX 在哪"、"为什么选 Y" | 三层漏斗检索 wiki，返回精确答案 |
| **teach** | "XX 是什么"、"帮我理解 XX" | 基于教程 + 源码，三层结构教学回答 |
| **source-trace** | "分析 XX 源码"、"trace 调用链" | 从 Lyra 追踪到引擎层，生成调用链分析 |

### 知识生产（写）

| 工作流 | 触发 | 做什么 |
|--------|------|--------|
| **create-series** | "创建 XX 技术专题" | 规划 + 创建完整教程系列（深度源码调研） |
| **evolve-series** | "优化 XX 教程"、"补一篇 XX" | 已有教程系列的迭代：补课时 / 更新 / 版本适配 |
| **ingest** | 给素材 / URL / "消化这篇" | 将外部素材结构化为 wiki 页 |
| **crystallize** | "沉淀进 wiki" | 将当前对话中的有价值知识存为 wiki 页 |
| **digest** | "深度分析 X"、"对比 X 和 Y" | 跨多页综合分析，输出结构化报告 |

### 知识维护（治理）

| 工作流 | 触发 | 做什么 |
|--------|------|--------|
| **lint** | "check 知识库" / pre-commit | 断链、缺字段、格式违规、anchor 漂移检查 |
| **init** | "初始化知识库" | 从零创建 Docs/ 骨架 |

## 工作流详情

每个工作流的完整定义在 `.codebuddy/skills/project-wiki/workflows/` 下：

```
workflows/
├── query.md          # 检索已有知识
├── teach.md          # 教学式问答
├── source-trace.md   # 源码追踪分析
├── create-series.md  # 创建教程系列
├── evolve-series.md  # 教程系列迭代演进
├── ingest.md         # 消化外部素材
├── crystallize.md    # 沉淀当前对话
├── digest.md         # 跨页综合分析
├── lint.md           # 知识库健康检查
└── init.md           # 初始化知识库
```

## 典型使用场景

### 场景 1：系统性学习一个技术领域

```
用户："我想学 GAS 能力系统"
  → AI 走 teach 工作流
  → 推荐从 [[00-meta/learning-paths]] 的路线 B 开始
  → 引导到 [[30-tutorials/gas/00-GAS系统总览]]
  → 逐篇跟读，有问题随时问
```

### 场景 2：快速查一个技术细节

```
用户："Lyra 的 ReplicationGraph 怎么配置的？"
  → AI 走 query 工作流
  → 定位 [[20-modules/cpp/ULyraReplicationGraph]]
  → 返回精确答案 + 教程链接
```

### 场景 3：深入理解源码实现

```
用户："帮我 trace GameplayAbility 的激活流程"
  → AI 走 source-trace 工作流
  → 从 ULyraGameplayAbility 追踪到引擎 UGameplayAbility
  → 输出调用链 mermaid 图 + 逐层解读
  → 建议 crystallize 为教程页
```

### 场景 4：消化一篇外部资料

```
用户：给了一个 UE 官方文档 URL
  → AI 走 ingest 工作流
  → 抓取内容 → 保存 _raw/external/
  → 生成结构化 wiki 页到 50-references/
  → 更新 index.md + log.md
```

### 场景 5：创建新的技术教程系列

```
用户："创建 UE 渲染管线技术专题"
  → AI 走 create-series 工作流
  → 设计大纲 → 创建 _series.yaml + 00-overview
  → 逐批生成课时文档
  → 更新 learning-paths.md
```

## 质量保障工具链

### wiki_lint.py

知识库健康检查脚本，检查 25+ 项规则：

```bash
# 快速检查（pre-commit 用，只报 ERROR）
python .codebuddy/skills/project-wiki/scripts/wiki_lint.py --check

# 全量检查（含 WARN + INFO）
python .codebuddy/skills/project-wiki/scripts/wiki_lint.py

# 自动修复安全项（补 last_synced / status）
python .codebuddy/skills/project-wiki/scripts/wiki_lint.py --fix

# 更新 anchor sha256 缓存
python .codebuddy/skills/project-wiki/scripts/wiki_lint.py --update-cache
```

关键检查项：

| 级别 | 检查 | 说明 |
|------|------|------|
| ERROR | `broken-link` | `[[wikilink]]` 指向不存在的页 |
| ERROR | `missing-fm` | 缺必填 frontmatter 字段 |
| ERROR | `id-mismatch` | frontmatter id ≠ 文件路径 |
| WARN | `asymm-link` | 单向 related 链接（A→B 但 B↛A） |
| WARN | `anchor-changed` | anchor 文件 sha256 变化，wiki 可能过期 |
| WARN | `ascii-art` | 代码块中出现 ASCII 制表符 |
| INFO | `orphan` | 页面无任何入站链接 |

### nav_inject.py

自动注入页间导航（上一页 / 索引 / 下一页）：

```bash
python .codebuddy/skills/project-wiki/scripts/nav_inject.py --apply
```

### rename_page.py

安全重命名（文件 + frontmatter id + 所有 wikilink 一次性改）：

```bash
# dry-run
python .codebuddy/skills/project-wiki/scripts/rename_page.py \
    --from 70-topics/old-topic --to 30-tutorials/gas/26-new-topic

# 实际执行
python .codebuddy/skills/project-wiki/scripts/rename_page.py \
    --from 70-topics/old-topic --to 30-tutorials/gas/26-new-topic --apply
```

## 人工贡献指南

### 如何阅读

1. 用 [Obsidian](https://obsidian.md/) 打开 `Docs/` 文件夹 → `[[wikilink]]` 自动互联
2. 或在 VS Code / GitHub 中直接浏览 markdown
3. 从 [[00-meta/learning-paths]] 选择学习路线

### 如何贡献

1. 遵循 [[00-meta/conventions]] 的命名和格式约定
2. 确保 frontmatter 完整（至少包含 `id` / `type` / `status` / `language` / `owner` / `last_synced` / `tags`）
3. 提交前跑 `wiki_lint.py --check` 确认 0 ERROR
4. 更新 `index.md`（如新增页面）

### 如何报告问题

- 发现断链 / 错误内容 → 直接修正并 commit
- 发现 stale 内容 → 标记 `status: stale` 或 re-verify 后更新
- 建议新教程主题 → 走 create-series 工作流

## 相关页面

- [[00-meta/ai-playbook]] - AI 协作手册
- [[00-meta/conventions]] - 项目约定
- [[00-meta/glossary]] - 项目术语表
- [[00-meta/learning-paths]] - 学习路线总览

---
> 最后更新：2026-05-17
