# 项目知识库架构重构评估与设计方案

> **类型**：架构评估 & 重构设计  
> **日期**：2026-05-17  
> **状态**：待评审  
> **目标读者**：项目维护者

---

## 一、评估结论：需要重构，但是"演进式重构"而非推倒重来

**建议重构**。原因：当前架构的核心假设（"AI 写业务代码，wiki 跟踪代码变化"）与实际使用场景（"技术学习知识库，AI 辅助深度教学"）存在系统性偏差。但现有 157 页内容质量高、工作流机制成熟、lint 体系完善，不应丢弃——应做**架构适配**，保留骨架、调整定位。

**核心判断**：大约 70% 的基础设施可以复用，30% 需要调整或新增。

---

## 二、现状诊断：六大结构性错配

### 错配 1：主力内容被当作"二等公民"

| 目录 | 页数 | 行数 | 占比 | 架构定位 |
|------|------|------|------|----------|
| `50-references/` | 73 | 33,380 | **46.5%** | "外部知识"（参考资料） |
| `20-modules/` | 20 | 2,081 | 12.7% | "模块层"（核心） |
| `10-architecture/` | 6 | 1,671 | 3.8% | "架构层"（核心） |
| `_raw/` | 42 | 28,058 | — | 原始素材 |
| 其余 | ~15 | ~1,568 | 9.5% | 各层 |

**问题**：知识库近一半的内容（73 页技术教程）被放在 `50-references/`——一个定位为"外部参考资料"的目录里。实际上这些内容是精心编写的技术深度分析系列（GAS 教程 26 篇、网络同步 15 篇、UE 框架 16 篇、动画系统 8 篇、Niagara 8 篇），它们才是本知识库的**核心价值**。

**类比**：这就像一所大学把所有课程教材都放在"图书馆参考书"分类下，而把行政制度文件放在"核心教学"分类里。

### 错配 2：Anchor 机制水土不服

当前 schema 规定：
> *"v0.1 必填至少 1 条（adr 与 topic 可空）"*

这对"跟踪项目代码变更"的场景完全合理——通过 anchor sha256 检测代码变更 → 自动标记 wiki stale。

但对技术学习文档：
- GAS 教程系列的 26 篇文档→ anchor 是什么？UE 引擎源码路径？本项目没有引擎源码
- `conventions.md` 已经不得不引入 workaround：*"与项目代码无直接关联的 Wiki 文档，`anchors:` 使用 `LyraStarterGame.uproject` 作占位符"*
- 73 篇参考文档中绝大多数使用了 `anchors: []` 或 `path: LyraStarterGame.uproject`——说明 anchor 机制对这类文档毫无意义

### 错配 3：Type 系统覆盖不足

当前 type 枚举：`module | subsystem | adr | runbook | topic | source`

实际需要但缺少的类型：

| 实际内容形态 | 勉强用的 type | 应该有的 type |
|-------------|--------------|--------------|
| GAS 教程 01-25（系统化教学） | `topic` | `tutorial` / `lesson` |
| UE 框架概览（总论型） | `topic` | `guide` / `overview` |
| 动画系统深度分析 | `topic` | `deep-dive` / `analysis` |
| Lyra 案例研究 | `topic` | `case-study` |
| 学习路线导航页 | 不存在 | `learning-path` |

所有深度教学内容都被打上了 `topic`，丧失了区分度。

### 错配 4：缺少学习导航体系

原架构为"按需查阅"设计（AI 做任务前查 wiki），没有考虑"系统性阅读"场景：

- **无学习路径**：用户不知道应该先读哪篇、后读哪篇
- **无难度分级**：入门概览和源码级深度分析混在一起
- **无前置知识标注**：读 GAS 的 GE 网络复制前，需要先理解哪些概念？
- **无"示例项目代码 ↔ 引擎源码 ↔ 理论知识"三角导航**

### 错配 5：工作流缺少"教学内容生产"场景

现有 6 个工作流都围绕"项目开发协作"设计：

| 工作流 | 设计场景 | 学习知识库的对应需求 |
|--------|---------|-------------------|
| init | 初始化项目知识库 | ✅ 可复用 |
| ingest | 消化 spec/PR/会议 进 wiki | ⚠️ 部分复用（消化外部文档的部分） |
| query | 项目任务前查 wiki | ⚠️ 需扩展（教学问答模式） |
| crystallize | 沉淀当前会话 | ✅ 可复用 |
| digest | 跨页深度综合 | ✅ 可复用 |
| lint | 知识库健康检查 | ⚠️ 需适配（规则调整） |

**缺少的工作流**：
- `create-series`：创建一个新的技术专项教程系列（如"渲染管线系列"）
- `teach` / `explain`：基于知识库 + 源码，向用户进行教学式解答
- `source-trace`：从 Lyra 项目代码追溯到引擎源码，建立理解链路

### 错配 6：`ai-playbook.md` 的约束偏重"守护型"而非"教学型"

现有约束：
> *"先读后写"、"保持同步"、"标注来源"、"标记状态"*

这些是"项目知识管理"的约束。学习知识库还需要：
- **教学表达约束**：由浅入深、先总体后细节、结合示例
- **知识关联约束**：每个概念必须与 Lyra 实践建立映射
- **多层次解释约束**：同一技术提供"概念理解层"和"源码分析层"

---

## 三、重构设计方案

### 3.1 总体策略：保留骨架，升级定位

```
原架构（AI 开发助手的项目记忆）
          │
          │  演进式重构
          ▼
新架构（UE 技术学习知识库 + AI 教学助手的知识基座）
```

**保留**：
- `Docs/` 根目录 + markdown + git 的技术选型
- frontmatter 机制
- lint 脚本体系
- `_raw/` 原始素材层
- `index.md` / `log.md` / `overview.md` 元文件
- 工作流路由机制

**调整**：
- 目录结构重新划分
- Type 系统扩展
- Frontmatter 新增字段
- 工作流补充
- AI Playbook 增补教学约束

### 3.2 目录结构重构

#### 新目录树

```
Docs/
├── .wiki-schema.md              # 本文件（更新）
├── README.md                    # 给人看的入口
├── index.md                     # 全量目录（AI 维护）
├── log.md                       # 时间线日志
├── overview.md                  # 项目顶层概览（更新）
│
├── 00-meta/                     # 元规则（保留，微调）
│   ├── conventions.md
│   ├── glossary.md
│   ├── workflows.md
│   ├── ai-playbook.md           # 增补教学约束
│   └── learning-paths.md        # ★ 新增：学习路线总览
│
├── 10-architecture/             # Lyra 项目架构（保留）
│   ├── overview.md
│   ├── subsystems/
│   └── data-flow/
│
├── 20-modules/                  # Lyra 模块文档（保留）
│   └── cpp/
│
├── 30-tutorials/                # ★ 核心重构：技术教程系列
│   ├── README.md                # 教程系列导航
│   │
│   ├── ue-framework/            # 原 50-references/ue-framework/
│   │   ├── _series.yaml         # ★ 系列元数据（见下文）
│   │   ├── 00-overview.md
│   │   ├── 01-game-loop.md
│   │   ├── 10-engine-layer/
│   │   ├── 20-world-layer/
│   │   ├── 30-gamemode-layer/
│   │   ├── 40-actor-system/
│   │   ├── 50-player-system/
│   │   ├── 60-tick-system/
│   │   └── 70-lyra-case-study/
│   │
│   ├── gas/                     # 原 50-references/gas-tutorial/
│   │   ├── _series.yaml
│   │   ├── 00-overview.md
│   │   ├── 01-ga-overview.md
│   │   ├── ...
│   │   └── 25-attribute-set.md
│   │
│   ├── network-sync/            # 原 50-references/network-sync/
│   │   ├── _series.yaml
│   │   ├── 00-overview.md
│   │   ├── ...
│   │   └── iris/
│   │
│   ├── animation/               # 原 50-references/animation-system/
│   │   ├── _series.yaml
│   │   └── ...
│   │
│   └── niagara/                 # 原 50-references/niagara-system/
│       ├── _series.yaml
│       └── ...
│
├── 40-runbooks/                 # 操作手册（保留）
│
├── 50-references/               # ★ 瘦身：仅存放真正的"外部参考"
│   ├── ue-official/             # UE 官方文档摘要
│   ├── third-party/             # 第三方库
│   └── articles/                # 外部文章/博客
│
├── 60-decisions/                # 原 30-decisions/（保留，改编号）
│
├── 70-topics/                   # 横切主题（保留，改编号）
│
├── 80-gotchas/                  # 已知坑（保留，改编号）
│
├── 90-snapshots/                # 快照（保留，改编号）
│
└── _raw/                        # 原始素材（保留）
    ├── external/
    ├── chats/
    └── specs/
```

#### 核心变化说明

| 变化 | 原 | 新 | 理由 |
|------|------|------|------|
| 教程系列提级 | `50-references/gas-tutorial/` | `30-tutorials/gas/` | 从"参考资料"变为"核心教学内容"，编号 30 体现其核心地位 |
| references 瘦身 | 73 页杂糅 | 仅真正的外部摘要 | 自创深度教程 ≠ 外部参考 |
| 决策记录后移 | `30-decisions/` | `60-decisions/` | 学习知识库中 ADR 不是主要内容 |
| 新增 learning-paths | 不存在 | `00-meta/learning-paths.md` | 提供系统化学习导航 |
| 系列元数据 | 不存在 | `_series.yaml` | 定义系列的学习路径、难度、前置条件 |

### 3.3 `_series.yaml` 系列元数据设计

每个教程系列目录下放一个 `_series.yaml`，描述系列整体信息：

```yaml
# 30-tutorials/gas/_series.yaml
name: GAS 系统教程
slug: gas
description: 基于 UE 5.7 的 Gameplay Ability System 完整教程系列
difficulty: intermediate → advanced   # 系列整体难度跨度
prerequisites:
  - series: ue-framework             # 建议先读的系列
    minimum: 00-overview             # 至少读到哪篇
  - concept: C++ 基础
  - concept: UE 蓝图基础
ue_version: "5.7"
total_lessons: 26
estimated_hours: 40                   # 预估学习时间

# 学习路径（定义阅读顺序和分段）
learning_path:
  - stage: 入门
    description: 理解 GAS 是什么、核心组件关系
    lessons:
      - 00-gas-overview
  - stage: GA（GameplayAbility）
    description: 技能/能力的创建、配置、执行
    lessons:
      - 01-ga-overview
      - 02-ga-execution-flow
      - 03-ga-input-binding
      - 04-ga-gameplay-event
      - 05-ga-target-info
  - stage: GE（GameplayEffect）
    description: 效果系统的运行、修正、网络复制
    lessons:
      - 06-ge-overview
      - 07-ge-execution-flow
      - 08-ge-modifier
      - 09-ge-attribute-capture
      - 10-ge-attribute-modifier
      - 11-ge-custom-execution
      - 12-ge-component
      - 13-ge-query
      - 14-ge-network-replication
  - stage: Tag 系统
    description: GameplayTag 的构建、查询、网络同步
    lessons:
      - 15-tag-overview
      - 16-tag-collection
      - 17-tag-container
      - 18-tag-query
      - 19-tag-network-replication
  - stage: 高级主题
    description: GameplayCue、AbilityTask、预判机制
    lessons:
      - 20-gc-overview
      - 21-gc-runtime
      - 22-ability-task
      - 23-prediction-key
      - 24-gameplay-effect-context
      - 25-attribute-set

# Lyra 项目关联（关键！将理论与实践连接）
lyra_connections:
  - tutorial: 00-gas-overview
    lyra_pages:
      - "[[10-architecture/subsystems/ability-system]]"
      - "[[20-modules/cpp/ULyraAbilitySystemComponent]]"
  - tutorial: 02-ga-execution-flow
    lyra_pages:
      - "[[20-modules/cpp/ULyraGameplayAbility]]"
  - tutorial: 25-attribute-set
    lyra_pages:
      - "[[20-modules/cpp/ULyraAbilitySet]]"

tags: [GAS, GameplayAbility, GameplayEffect, GameplayTag, UE5.7]
```

### 3.4 Frontmatter 扩展

#### 新增字段（仅 `30-tutorials/` 下的页面）

```yaml
---
id: 30-tutorials/gas/02-ga-execution-flow
type: tutorial                          # ★ 新 type
status: current
language: zh
owner: ai

# ★ 新增：教学相关字段
series: gas                             # 所属系列
lesson_index: 2                         # 系列内序号
difficulty: intermediate                # beginner | intermediate | advanced
prerequisites:                          # 前置知识
  - "[[30-tutorials/gas/01-GA简介与配置]]"
  - concept: UE Actor 生命周期

# ★ 新增：多层知识关联
engine_sources:                         # 引擎源码路径（替代 anchors 的概念）
  - path: Engine/Plugins/Runtime/GameplayAbilities/Source/GameplayAbilities/Private/Abilities/GameplayAbility.cpp
    description: GA 核心执行流程
  - path: Engine/Plugins/Runtime/GameplayAbilities/Source/GameplayAbilities/Private/AbilitySystemComponent_Abilities.cpp
    description: ASC 激活 GA 的入口
lyra_sources:                           # Lyra 项目源码路径
  - path: Source/LyraGame/AbilitySystem/Abilities/LyraGameplayAbility.cpp
    description: Lyra 对 GA 的扩展

related:
  - "[[20-modules/cpp/ULyraGameplayAbility]]"
  - "[[10-architecture/subsystems/ability-system]]"
sources:
  - "[[_raw/external/GAS/GA-2.0执行流程详解]]"
last_synced: 2026-05-17
last_verified: 2026-05-17
tags: [GAS, GameplayAbility, 执行流程]
---
```

#### Type 系统扩展

| type | 适用场景 | 目录 |
|------|---------|------|
| `module` | Lyra 项目类/模块文档 | `20-modules/` |
| `subsystem` | Lyra 子系统概览 | `10-architecture/subsystems/` |
| `tutorial` | **★ 新增**：教程系列中的课时 | `30-tutorials/` |
| `guide` | **★ 新增**：概览/导航型文档 | `30-tutorials/*/00-overview.md` |
| `case-study` | **★ 新增**：Lyra 案例分析 | `30-tutorials/*/XX-lyra-*` |
| `runbook` | 操作手册 | `40-runbooks/` |
| `reference` | 外部文档摘要 | `50-references/` |
| `adr` | 决策记录 | `60-decisions/` |
| `topic` | 横切主题 | `70-topics/` |
| `gotcha` | 已知坑 | `80-gotchas/` |

### 3.5 Anchor 机制适配

#### 问题回顾

原 anchor 机制假设：wiki 页锚定到项目代码文件 → sha256 检测变更 → 自动标 stale。

技术教程的真实锚点：

| 教程类型 | 真正的"锚" | 原 anchor 机制能覆盖？ |
|---------|-----------|---------------------|
| Lyra 模块分析 | Lyra 项目源码 | ✅ 完全覆盖 |
| 引擎框架教程 | UE 引擎源码 | ❌ 引擎源码不在项目仓库 |
| GAS 教程 | 引擎 GAS 插件源码 | ❌ 同上 |
| 概念讲解 | 无代码锚点 | ❌ 不适用 |

#### 适配方案：双轨 anchor

```yaml
# 方案：将 anchors 拆分为 lyra_sources 和 engine_sources

# 对于 20-modules/ 下的 Lyra 模块文档（保持原样）
anchors:
  - path: Source/LyraGame/Character/LyraCharacter.h
  - path: Source/LyraGame/Character/LyraCharacter.cpp

# 对于 30-tutorials/ 下的教程文档（新增字段）
engine_sources:                         # 引擎源码路径（仅记录，不做 sha256 校验）
  - path: Engine/Source/Runtime/Engine/Private/Actor.cpp
    description: Actor 生命周期核心
lyra_sources:                           # Lyra 源码路径（可做 sha256 校验）
  - path: Source/LyraGame/Character/LyraCharacter.cpp
    description: Lyra 对 Character 的实现
```

**关键设计决策**：
- `lyra_sources`：指向本项目代码，**可以**做 sha256 漂移检测
- `engine_sources`：指向引擎源码路径（用户机器上的路径），**仅作为阅读指引**，不做自动校验
- 纯概念讲解类文档：两个字段均可为空，lint 不报错

### 3.6 新增工作流

#### 工作流 1：`create-series`（创建技术教程系列）

**触发**：用户说"创建XX技术专题"、"新增XX教程系列"

**步骤**：
1. 明确系列主题、目标读者、UE 版本
2. 收集相关资料（引擎源码路径、外部文档、Lyra 实现代码）
3. 设计系列大纲（由浅入深、先总后分的结构）
4. 创建 `_series.yaml` 定义学习路径
5. 创建系列概览页（`00-overview.md`）
6. 逐篇创建教程页面（可分批完成）
7. 建立与 Lyra 模块文档的交叉引用
8. 更新 `00-meta/learning-paths.md`
9. 更新 `index.md` + `log.md`

#### 工作流 2：`teach`（教学式问答）

**触发**：用户问"XX是什么"、"XX怎么工作的"、"帮我理解XX"

**与 query 的区别**：

| | query | teach |
|---|---|---|
| 目标 | 定位已有信息 | 组织信息进行教学 |
| 回答风格 | 简洁、引用式 | 由浅入深、举例、类比 |
| 是否结合源码 | 可选 | 鼓励（理论+代码双线） |
| 知识库更新 | 只读 | 发现知识缺口 → 建议新增文档 |

**步骤**：
1. 走 query L1-L3 定位相关教程页
2. 如果教程已覆盖 → 基于教程内容 + 源码组织教学回答
3. 如果教程未覆盖 → 基于源码 + 外部资料回答，并建议通过 crystallize 沉淀
4. 回答遵循"先给概念直觉 → 再给技术细节 → 最后给 Lyra 代码实例"的三层结构

#### 工作流 3：`source-trace`（源码追踪分析）

**触发**：用户说"帮我分析XX的源码实现"、"trace XX的调用链"

**步骤**：
1. 确认分析目标（类名/函数名/流程名）
2. 在 Lyra 项目源码中定位入口
3. 追踪调用链到引擎层（需要用户提供引擎源码路径或使用 WebSearch）
4. 生成分析文档，标注各层调用关系
5. 与已有教程建立交叉引用
6. 可选：crystallize 为新的教程页面

### 3.7 `learning-paths.md` 设计

```markdown
# 学习路线总览

## 学习路线图

### 路线 A：UE 框架基础（推荐首先学习）
- 目标：理解 UE 游戏框架的整体架构
- 难度：入门 → 中级
- 预计时间：20 小时
- 系列：[[30-tutorials/ue-framework/00-UE框架概述]]
- 前置知识：C++ 基础、了解游戏引擎基本概念

### 路线 B：GAS 能力系统
- 目标：掌握 GAS 的完整使用和内部原理
- 难度：中级 → 高级
- 预计时间：40 小时
- 系列：[[30-tutorials/gas/00-overview]]
- 前置知识：路线 A（至少读完 Actor 和 Component）

### 路线 C：网络同步与复制
- 目标：理解 UE 的网络架构和 Lyra 的网络实现
- 难度：中级 → 高级
- 预计时间：30 小时
- 系列：[[30-tutorials/network-sync/00-overview]]
- 前置知识：路线 A

### 路线 D：动画系统
- 目标：理解动画蓝图、状态机、IK 和 Lyra 动画实现
- 难度：中级 → 高级
- 预计时间：15 小时
- 系列：[[30-tutorials/animation/01-Lyra动画系统框架深度分析-概览]]
- 前置知识：路线 A（Actor/Component 部分）

### 路线 E：Niagara 粒子系统
- 目标：理解 Niagara 框架设计和 Lyra 中的应用
- 难度：中级 → 高级
- 预计时间：15 小时
- 系列：[[30-tutorials/niagara/01-Niagara系统框架深度分析-概览]]
- 前置知识：路线 A

## 推荐学习顺序

A（UE 框架基础）→ B（GAS）或 C（网络）→ D / E（按兴趣）

## 每个系列与 Lyra 项目的关联

| 系列 | Lyra 中的对应实现 | 关键模块文档 |
|------|-----------------|-------------|
| UE 框架 | GameMode/GameState/Character | [[20-modules/cpp/ALyraGameMode]] 等 |
| GAS | AbilitySystem/Abilities | [[20-modules/cpp/ULyraAbilitySystemComponent]] 等 |
| 网络同步 | ReplicationGraph/武器同步 | [[20-modules/cpp/ULyraReplicationGraph]] 等 |
| 动画 | 角色动画系统 | [[10-architecture/overview]] |
| Niagara | 特效系统 | [[10-architecture/overview]] |
```

### 3.8 AI Playbook 增补

在现有 `ai-playbook.md` 增加"教学约束"章节：

```markdown
## 教学表达约束（学习知识库专用）

### 文档编写原则

1. **由浅入深**：每篇文档先给概念直觉（"是什么、为什么"），再给技术细节（"怎么实现"）
2. **先总后分**：先给系统全景图，再逐个拆解子模块
3. **理论+实践双线**：
   - 每个引擎概念 → 对应 Lyra 项目中的实际使用
   - 每个 Lyra 实现 → 追溯到引擎层的设计理由
4. **渐进式代码展示**：
   - 先展示关键 3-5 行（核心逻辑）
   - 再展示完整函数（上下文理解）
   - 最后展示调用链（系统理解）

### 教学问答约束

1. **三层回答结构**：
   - 第一层：概念直觉（一句话 + 类比）
   - 第二层：技术机制（关键代码 + 流程图）
   - 第三层：Lyra 实例（项目中的真实代码）
2. **引用知识库**：每个技术点标注 `(详见 [[教程页]])`
3. **发现缺口**：如果知识库未覆盖用户的问题领域，主动建议创建新教程
```

---

## 四、迁移计划

### Phase 1：目录结构迁移（低风险，机械操作）

```
50-references/ue-framework/  →  30-tutorials/ue-framework/
50-references/gas-tutorial/  →  30-tutorials/gas/
50-references/network-sync/  →  30-tutorials/network-sync/
50-references/animation-system/  →  30-tutorials/animation/
50-references/niagara-system/  →  30-tutorials/niagara/
30-decisions/  →  60-decisions/
60-topics/  →  70-topics/
70-gotchas/  →  80-gotchas/
80-snapshots/  →  90-snapshots/
```

**影响**：
- 所有 frontmatter `id` 需要更新
- 所有 `[[wikilink]]` 需要更新
- `index.md` 需要重写
- lint 脚本需要适配新路径

**风险控制**：编写迁移脚本一次性完成，git 提供回滚保障。

### Phase 2：元数据增强（中风险，需逐页处理）

- 为教程页面添加 `series`, `lesson_index`, `difficulty`, `prerequisites` 字段
- 为教程页面添加 `engine_sources`, `lyra_sources` 字段（替代 `anchors`）
- 创建每个系列的 `_series.yaml`
- 创建 `00-meta/learning-paths.md`

### Phase 3：Schema & 工作流更新（低风险，文档更新）

- 更新 `.wiki-schema.md` 反映新架构
- 新增 `create-series`, `teach`, `source-trace` 工作流
- 更新 `ai-playbook.md` 增补教学约束
- 更新 lint 规则适配新 type 和新字段

### Phase 4：内容质量提升（持续进行）

- 逐个系列审核，补充学习导航（前一篇/后一篇链接）
- 补充 `lyra_sources` 和 `engine_sources`
- 补充前置知识标注

### 预估工作量

| Phase | 工作量 | 可自动化比例 |
|-------|--------|------------|
| Phase 1 | 2-3 小时 | 90%（迁移脚本） |
| Phase 2 | 4-6 小时 | 60%（批量更新脚本 + 人工填充） |
| Phase 3 | 2-3 小时 | 20%（主要是文档编写） |
| Phase 4 | 持续 | 低（需要人工审核） |

---

## 五、风险与权衡

### 采纳风险

| 风险 | 严重度 | 缓解措施 |
|------|--------|---------|
| 迁移过程中 wikilink 大面积断链 | 中 | 编写迁移脚本一次性替换 + lint 验证 |
| 新架构增加维护复杂度 | 低 | `_series.yaml` 是可选的增量功能 |
| 与原始 project-wiki skill 不兼容 | 中 | skill 本身需要同步更新 |

### 不采纳风险

| 风险 | 严重度 | 说明 |
|------|--------|------|
| 核心教程内容持续"委屈"在 references 下 | 高 | 新贡献者难以理解知识库结构 |
| anchor 机制持续产生无意义噪音 | 中 | lint 报告中的假阳性影响可信度 |
| 缺少学习导航导致知识库利用率低 | 高 | 157 页文档但没有阅读指引 |

---

## 六、备选方案对比

### 方案 A：本文档的完整重构（推荐）

- 目录结构调整 + type 系统扩展 + 新增工作流 + 学习路径
- 优点：一步到位，架构完全匹配定位
- 代价：一次性工作量较大

### 方案 B：最小化调整

仅做以下改动：
- `50-references/` 改名为 `30-tutorials/`
- 不改 type 系统和 frontmatter
- 不新增工作流
- 优点：改动最小
- 缺点：治标不治本，anchor/type/工作流的错配依然存在

### 方案 C：不重构，在现有架构上打补丁

- 在 `50-references/` 下加 README 说明"这其实是教程"
- 在 `00-meta/` 下加 `learning-paths.md` 做导航
- 优点：零迁移成本
- 缺点：架构认知负担持续存在，新加的补丁文档只会增加混乱

**推荐方案 A**：一次性投入换来长期架构清晰。157 页的规模做迁移完全可控。

---

## 七、决策请求

请评估以上方案，确认：

1. **是否采纳重构？**（推荐：是）
2. **如果采纳，选择哪个方案？**（推荐：方案 A）
3. **是否有目录编号偏好调整？**（如 30-tutorials 改为其他编号）
4. **是否有其他关注点需要补充讨论？**

等待您的决策后，可以立即开始 Phase 1 的迁移脚本编写。
