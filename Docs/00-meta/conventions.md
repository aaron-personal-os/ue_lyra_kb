# 项目约定

> 记录本知识库和 Lyra 项目的命名、编码、文档约定。

## §1 Lyra 项目命名约定

### C++ 类命名

- 使用 PascalCase
- 前缀规则：
  - `A` — Actor 派生类（如 `ALyraCharacter`）
  - `U` — UObject 派生类（如 `ULyraAbilitySystemComponent`）
  - `F` — 结构体（如 `FLyraGameplayAbilityTargetData_SingleTargetHit`）
  - `I` — 接口（如 `IAbilitySystemInterface`）
  - `E` — 枚举（如 `ELyraAbilityActivationPolicy`）
  - `T` — 模板类

### 文件命名

- 头文件和源文件使用类名（去前缀）：`LyraCharacter.h` / `LyraCharacter.cpp`
- 内容资产使用 PascalCase：`BP_LyraCharacter`

## §2 Lyra 项目编码约定

### C++ 风格

- 遵循 [UE 官方编码规范](https://docs.unrealengine.com/5.0/zh-CN/epic-cplusplus-coding-standard-for-unreal-engine/)
- 缩进：Tab（UE 标准）
- 大括号：Allman 风格
- 成员变量前缀：`b` — bool

### Blueprint 规范

- 事件图用 `Event` 前缀命名自定义事件
- 函数图按功能分类折叠
- 变量分类放入 Category

## §3 知识库目录与命名

### 目录结构

```
Docs/
├── 00-meta/           # 元规则（约定、术语、工作流、AI 手册）
├── 10-architecture/   # Lyra 架构（子系统、数据流）
├── 20-modules/        # Lyra 模块（C++ 类级文档）
│   └── cpp/           # 一个类一页，PascalCase
├── 30-tutorials/      # ★ 技术教程系列（核心内容）
│   ├── <slug>/        # 一个系列一目录（kebab-case）
│   │   ├── _series.yaml
│   │   ├── 00-overview.md
│   │   └── NN-slug.md
├── 40-runbooks/       # 操作手册
├── 50-references/     # 外部参考
│   ├── ue-official/
│   ├── third-party/
│   └── articles/
├── 60-decisions/      # ADR（NNNN-kebab-slug）
├── 70-topics/         # 横切主题
├── 80-gotchas/        # 已知坑
├── 90-snapshots/      # 版本快照
└── _raw/              # 原始素材（AI 只读）
```

### 页面命名风格

| 目录 | 命名风格 | 示例 |
|------|---------|------|
| `20-modules/cpp/` | **PascalCase**（匹配 C++ 类名） | `ALyraCharacter.md` |
| `30-tutorials/<slug>/` | **NN-kebab-slug** | `02-ga-execution-flow.md` |
| `60-decisions/` | **NNNN-kebab-slug** | `0001-project-knowledge-base.md` |
| 其余 | **kebab-case** | `networking-and-synchronization.md` |

### 页面 ID

- ID = 文件路径（去 `Docs/` 前缀和 `.md` 后缀）
- 示例：`Docs/30-tutorials/gas/02-ga-execution-flow.md` → id `30-tutorials/gas/02-ga-execution-flow`

## §4 Frontmatter 规范

### 必填字段（所有 wiki 页，不含 `_raw/`、`00-meta/`、元文件）

```yaml
---
id: <页面 ID>
type: <type 枚举>
status: current | draft | stale | deprecated
language: zh
owner: ai | human | mixed
last_synced: YYYY-MM-DD
tags: [tag1, tag2]
---
```

### Type 枚举

| type | 用途 | 是否必须 anchors |
|------|------|-----------------|
| `tutorial` | 教程课时 | 否 |
| `guide` | 概览/导航页 | 否 |
| `case-study` | Lyra 案例分析 | 否 |
| `module` | Lyra C++ 类文档 | **是**（≥1） |
| `subsystem` | Lyra 子系统概览 | **是**（≥1） |
| `runbook` | 操作手册 | 建议有 |
| `reference` | 外部参考摘要 | 否 |
| `adr` | 决策记录 | 否 |
| `topic` | 横切主题 | 否 |
| `gotcha` | 已知坑 | 建议有 |

### 教程额外字段（`30-tutorials/` 下）

```yaml
series: gas                    # 所属系列 slug
lesson_index: 2                # 系列内序号
difficulty: intermediate       # beginner | intermediate | advanced
prerequisites:                 # 前置知识
  - "[[30-tutorials/gas/01-GA简介与配置]]"
  - concept: UE Actor 生命周期
engine_sources:                # 引擎源码参考（仅记录，不做 sha256）
  - path: Engine/Plugins/Runtime/GameplayAbilities/...
    description: GA 执行核心
lyra_sources:                  # Lyra 源码路径（可做 sha256 校验）
  - path: Source/LyraGame/AbilitySystem/...
    description: Lyra 的 GA 扩展
```

### anchors 字段规则

- `module` / `subsystem` 类型 → **必须**指向实际 Lyra 源码路径
- `tutorial` / `guide` / `reference` / `case-study` / `topic` / `adr` → **不要求** anchors
- 不再使用 `LyraStarterGame.uproject` 作占位符（旧约定已废弃）
- 教程页改用 `engine_sources` / `lyra_sources` 记录代码关联

## §5 提交规范

### Commit Message 格式

```
<type>(<scope>): <subject 中文>

<body 中文>
```

- `type` 英文：`feat` / `fix` / `docs` / `refactor` / `chore` / `test`
- `scope` 英文 slug：`wiki` / `tutorial` / `lint` / `architecture` / `modules`
- `subject` 中文（便于 review）
- 固定术语保留英文：ADR / lint / commit / branch / frontmatter 等
- 一条消息内 **整条中文** 或 **整条英文**，不前后混

**示例**：

```text
docs(tutorial): 新增 GAS 教程系列 — GA 执行流程详解

基于 UE 5.7 引擎源码分析 GameplayAbility 的完整执行流程。
包含 mermaid 流程图 + Lyra 项目中 ULyraGameplayAbility 的实践案例。
```

### 提交时机

- ✅ 完成一个教程文档 / 一批相关文档
- ✅ 完成一轮 lint 修复
- ✅ 完成知识库结构调整
- ❌ 文档写一半、lint 不通过
- ❌ 临时草稿

## §6 交叉引用

### Wikilink 格式

- 页面间用 `[[id]]`（Obsidian 兼容）
- 引用 raw 素材：`[[_raw/specs/2026-05-13-xxx]]`
- 引用外部 URL：普通 markdown `[text](url)`
- 带别名：`[[id|显示文本]]`
- 带锚点：`[[id#section]]`

### 双向链接

- 新页底部"相关页面"加 `[[other-id]]`
- **同时**在被链接页添加反向链接（lint 的 `asymm-link` 会检查）

## §7 术语别名

只收录项目内实际反复出现的同义词：

```
Lyra = LyraStarterGame = UE5 示例项目
GAS = Gameplay Ability System
GA = GameplayAbility
GE = GameplayEffect
GC = GameplayCue（GAS 系统）
UGC = Unreal Garbage Collection（UE 垃圾回收系统）
ASC = AbilitySystemComponent
StateTree = 状态树
Experience = Experience Definition
```

⚠️ **注意**：避免混淆 `GC` 的含义：
- 在 GAS 系列中，`GC` = `GameplayCue`（技能标签触发的特效）
- 在内存管理上下文中，`UGC` = `Unreal Garbage Collection`（垃圾回收机制）

为免歧义，垃圾回收系列使用目录名 `garbage-collection/`，而不使用 `gc/`。

发现新同义词 → 建议补充到此处和 [[00-meta/glossary]]。

## §8 教程系列约定

### 系列目录结构

```
30-tutorials/<slug>/
├── _series.yaml       # 系列元数据（必须）
├── 00-overview.md     # 系列概览（必须）
├── 01-xxx.md          # 第 1 课
├── 02-xxx.md          # 第 2 课
├── ...
└── NN-lyra-xxx.md     # Lyra 案例（推荐放末尾）
```

### 系列内编号

- `00` = 概览（type: `guide`）
- `01`-`99` = 具体课时（type: `tutorial`）
- 允许使用子目录分层：`10-engine-layer/00-engines.md`
- Lyra 案例分析推荐用 `70-` 前缀或独立子目录

### 教程编写原则

1. 每篇开头有"本课目标"一句话概括
2. 关键架构/流程必须有 mermaid 图示
3. 代码按"核心行 → 完整函数 → 调用链"渐进展示
4. 每篇结尾有"总结与要点"
5. 每篇结尾有"相关页面"链接

## §9 图示规范

- **必须**优先使用 `mermaid` 代码块
- **禁止**新增 ASCII art（制表符 / box-drawing 字符 / `+---+` 模式）
- lint 会自动检测并报 `ascii-art` 警告

**已知例外**（不报警）：
- 目录树展示（文件系统结构）
- 真实日志/终端输出引用
- 4 行以内的极简流程（如 `A → B → C`）
- 代码块已标注 `lang`（如 `text`、`bash`、`cpp`）

**Mermaid 类型选择**：

| 场景 | Mermaid 类型 |
|------|-------------|
| 系统架构 / 模块关系 | `graph TB` / `graph LR` |
| 类继承 / 组件组合 | `classDiagram` |
| 调用时序 | `sequenceDiagram` |
| 状态转换 | `stateDiagram-v2` |
| 生命周期 / 流程 | `flowchart TD` |

## 相关页面

- [[00-meta/ai-playbook]] - AI 协作手册
- [[00-meta/glossary]] - 项目术语表
- [[00-meta/learning-paths]] - 学习路线总览
- [[.wiki-schema]] - 知识库 schema

---
> 最后更新：2026-05-17
