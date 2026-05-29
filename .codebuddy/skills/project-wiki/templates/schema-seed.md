# 项目知识库 Schema（种子模板）

> 此文件是 `init` 工作流的种子模板。初始化时复制到 `Docs/.wiki-schema.md`，然后根据项目实际情况填充。

## 知识库信息

- 项目：{{PROJECT_NAME}}
- 创建日期：{{DATE}}
- 语言：中文（`language: zh`）
- 版本：1.0.0
- 定位：UE 技术学习知识库
- 维护 skill：[project-wiki](../.codebuddy/skills/project-wiki/)


## 目录结构

```
Docs/
├── .wiki-schema.md          # 本文件
├── README.md                # 给人看的入口
├── index.md                 # 内容目录（AI 维护）
├── log.md                   # 时间线日志（append-only）
├── overview.md              # 项目顶层概览
│
├── 00-meta/                 # 元规则
│   ├── conventions.md       # 命名/编码/文档约定
│   ├── glossary.md          # 项目术语表
│   ├── workflows.md         # 工作流总览
│   ├── ai-playbook.md       # ★ AI 协作手册（必读）
│   └── learning-paths.md    # 学习路线总览
│
├── 10-architecture/         # 项目架构层
│   ├── overview.md          # 模块依赖总图
│   ├── subsystems/          # 一个子系统一页
│   └── data-flow/           # 关键数据流
│
├── 20-modules/              # 模块层（C++ 类级文档）
│   ├── cpp/                 # 一个 C++ 类一页（PascalCase）
│   ├── blueprint/           # 蓝图资产
│   └── assets/              # 关键资产说明
│
├── 30-tutorials/            # ★ 技术教程系列（核心内容）
│   └── <series-slug>/       # 每个系列一个目录
│       ├── _series.yaml     # 系列元数据
│       ├── 00-overview.md   # 系列概览
│       └── NN-slug.md       # 具体课时
│
├── 40-runbooks/             # "如何做 X" 操作手册
│
├── 50-references/           # 外部参考资料
│   ├── ue-official/         # UE 官方文档摘要
│   ├── third-party/         # 第三方库笔记
│   └── articles/            # 外部文章/博客
│
├── 60-decisions/            # ADR（架构决策记录）
│   └── 0000-template.md
│
├── 70-topics/               # 横切主题（不归属单一模块）
├── 80-gotchas/              # 已知坑、bug 模式
├── 90-snapshots/            # 版本快照
│
└── _raw/                    # 原始素材（AI 只读）
    ├── chats/               # 关键 AI 对话沉淀
    ├── specs/               # 设计文档
    └── external/            # 抓取的外部素材
```

## 页面命名规范

- ID 即文件路径（不含 `Docs/` 前缀和 `.md` 后缀）：
  - 例：`Docs/20-modules/cpp/ALyraCharacter.md` → id `20-modules/cpp/ALyraCharacter`
  - 例：`Docs/30-tutorials/gas/02-ga-execution-flow.md` → id `30-tutorials/gas/02-ga-execution-flow`
- 命名风格：
  - `20-modules/cpp/` 下用 **PascalCase**（匹配 C++ 类名）
  - `30-tutorials/<slug>/` 下用 **NN-kebab-slug**（序号+短横线）
  - `60-decisions/` 下用 **NNNN-kebab-slug**（4 位数字+短横线）
  - 其余目录用 **kebab-case** 短 slug

## Type 枚举

| type | 用途 | 是否必须 anchors |
|------|------|-----------------|
| `tutorial` | 教程课时 | 否 |
| `guide` | 概览/导航页 | 否 |
| `case-study` | 案例分析 | 否 |
| `module` | C++ 类文档 | **是**（≥1） |
| `subsystem` | 子系统概览 | **是**（≥1） |
| `runbook` | 操作手册 | 建议有 |
| `reference` | 外部参考摘要 | 否 |
| `adr` | 决策记录 | 否 |
| `topic` | 横切主题 | 否 |
| `gotcha` | 已知坑 | 建议有 |

## 页面格式（强制 frontmatter）

每个 wiki 页（不含 `_raw/`、`index.md`、`log.md`、`overview.md`、`README.md`、`00-meta/` 下文档）**必须**有 frontmatter。

### 通用 frontmatter 示例

```yaml
---
id: 20-modules/cpp/ALyraCharacter
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/Character/LyraCharacter.h
  - path: Source/LyraGame/Character/LyraCharacter.cpp
related:
  - "[[10-architecture/subsystems/modular-gameplay]]"
sources: []
last_synced: {{DATE}}
last_verified: {{DATE}}
tags: [character, pawn, modular]
---
```

### 教程 frontmatter 示例

```yaml
---
id: 30-tutorials/gas/02-ga-execution-flow
type: tutorial
status: current
language: zh
owner: ai
series: gas
lesson_index: 2
difficulty: intermediate
prerequisites:
  - "[[30-tutorials/gas/01-ga-overview]]"
engine_sources:
  - path: Engine/Plugins/Runtime/GameplayAbilities/Source/.../GameplayAbility.cpp
    description: GA 执行核心
lyra_sources:
  - path: Source/LyraGame/AbilitySystem/Abilities/LyraGameplayAbility.cpp
    description: Lyra 的 GA 扩展
anchors: []
related:
  - "[[20-modules/cpp/ULyraGameplayAbility]]"
last_synced: {{DATE}}
last_verified: {{DATE}}
tags: [GAS, GameplayAbility, 执行流程]
---
```

### 字段说明

- `type`：决定模板与 lint 规则（见 Type 枚举）
- `status`：`stale` / `deprecated` 的页**不准被引用**而不警告
- `anchors`：`module` / `subsystem` 类型必填（≥1），教程类不要求
- `engine_sources` / `lyra_sources`：教程页记录引擎和项目源码关联（仅参考）
- `series` / `lesson_index` / `difficulty`：教程页的系列信息
- `prerequisites`：前置知识（wikilink 或自然语言）
- `last_synced`：最后一次内容与代码同步的时间
- `last_verified`：最后一次人工/AI 实际复核的日期

## 交叉引用

- 页面间用 `[[id]]` wikilink（Obsidian 兼容）
- 带别名：`[[id|显示文本]]`
- 带锚点：`[[id#section]]`
- 引用 raw 素材：`[[_raw/specs/2026-05-16-xxx]]`
- 引用外部 URL：普通 markdown `[text](url)`

## 别名词表（Alias Table）

只收录项目内**实际反复出现的同义词**：

```
GAS = Gameplay Ability System
GA = GameplayAbility
GE = GameplayEffect
GC = GameplayCue
ASC = AbilitySystemComponent
StateTree = 状态树（UE 5.x 新行为树）
Experience = Experience Definition
```

ingest 发现新同义词关系时 → AI 主动建议补充。

## 规则摘要

### Ingest 规则
详见 `workflows/ingest.md`。要点：先查重 → 选层级 → 挂 anchor → 更新 index + log

### Query 规则
详见 `workflows/query.md`。要点：三层漏斗（index → frontmatter → 全文搜索）→ 标注引用

### Teach 规则
详见 `workflows/teach.md`。要点：三层回答（概念直觉 → 技术机制 → Lyra 实例）

### Lint 规则
详见 `workflows/lint.md`。25+ 项检查，ERROR 级必须修复。

## 演进路线

| 版本 | 能力 | 状态 |
|---|---|---|
| v0.1 | 骨架 + 工作流契约 | ✅ 已完成 |
| v0.2 | anchor sha256 + stale 自动检测 | ✅ 已完成 |
| **v1.0**（当前） | 技术学习知识库架构重构 | ✅ 已完成 |
| v1.1 | 教程 frontmatter 全量补充 | 待执行 |
| v1.2 | `.indexes/` 派生索引（by-tag / by-series） | 页数超 200 |
| v1.3 | qmd 本地检索集成 | 页数超 1000 |
