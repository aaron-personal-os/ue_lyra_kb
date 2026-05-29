# 技术教程系列

> 本目录包含系统化的 UE 技术深度教程，是知识库的**核心内容**。
>
> 每个系列由浅入深、理论结合 Lyra 真实代码。详见 [`../00-meta/learning-paths.md`](../00-meta/learning-paths.md) 获取推荐学习路线。

## 教程系列总览（23 系列 / 220+ 篇）

> 每个系列入口为 `<slug>/00-XXX系列概览.md`（或 `00-overview.md`），含完整的 `_series.yaml` 元数据。

### 🏗️ 基础框架（必经之路）

| 系列 | 篇数 | 难度 | 入口 |
|---|---|---|---|
| **ue-framework** | 16 | beginner → intermediate | [`ue-framework/00-UE框架概述.md`](ue-framework/00-UE框架概述.md) |
| **ue-reflection** | 8 | beginner → intermediate | [`ue-reflection/00-反射系列概览.md`](ue-reflection/) |

### ⚔️ 核心玩法系统

| 系列 | 篇数 | 难度 | 入口 |
|---|---|---|---|
| **gas**（Gameplay Ability System）| 27 | intermediate → advanced | [`gas/00-GAS系统总览.md`](gas/00-GAS系统总览.md) |
| **modular-gameplay** | 6 | beginner → advanced | [`modular-gameplay/00-ModularGameplay系统教程系列.md`](modular-gameplay/) |
| **game-feature** | 6 | beginner | [`game-feature/00-GameFeature系统从入门到实战.md`](game-feature/) |
| **ai-behavior**（BT + StateTree） | 7 | beginner → advanced | [`ai-behavior/`](ai-behavior/) |

### 🌐 网络与同步

| 系列 | 篇数 | 难度 | 入口 |
|---|---|---|---|
| **network-sync** | 15 | intermediate → advanced | [`network-sync/00-UE网络通信总览.md`](network-sync/00-UE网络通信总览.md) |

### 💾 资源与内存

| 系列 | 篇数 | 难度 | 入口 |
|---|---|---|---|
| **resource-management** | 8 | beginner → advanced | [`resource-management/`](resource-management/) |
| **garbage-collection** | 8 | beginner → advanced | [`garbage-collection/`](garbage-collection/) |
| **config-ini** | 8 | beginner → advanced | [`config-ini/`](config-ini/) |

### 🏃 角色与运动

| 系列 | 篇数 | 难度 | 入口 |
|---|---|---|---|
| **movement-system** | 11 | beginner → advanced | [`movement-system/`](movement-system/) |
| **camera-system** | 11 | beginner → advanced | [`camera-system/`](camera-system/) |
| **input-system** | 7 | beginner → advanced | [`input-system/`](input-system/) |

### 🎨 视觉系统

| 系列 | 篇数 | 难度 | 入口 |
|---|---|---|---|
| **animation** | 11 | intermediate → advanced | [`animation/`](animation/) |
| **niagara**（粒子特效）| 8 | intermediate → advanced | [`niagara/`](niagara/) |
| **pcg**（程序化生成）| 11 | beginner → advanced | [`pcg/`](pcg/) |
| **mutable**（可定制角色）| 9 | beginner → advanced | [`mutable/`](mutable/) |

### 🖼️ UI 与工具

| 系列 | 篇数 | 难度 | 入口 |
|---|---|---|---|
| **umg** | 10 | — | [`umg/`](umg/) |
| **blueprint-system** | 9 | beginner → advanced | [`blueprint-system/`](blueprint-system/) |
| **editor-extension** | 9 | beginner → advanced | [`editor-extension/`](editor-extension/) |

### ⚡ 优化与本地化

| 系列 | 篇数 | 难度 | 入口 |
|---|---|---|---|
| **performance-optimization** | 7 | intermediate → advanced | [`performance-optimization/`](performance-optimization/) |
| **localization-i18n** | 8 | beginner → intermediate | [`localization-i18n/`](localization-i18n/) |

### 🎯 Lyra 项目实战

| 系列 | 篇数 | 难度 | 入口 |
|---|---|---|---|
| **lyra-practical** | 11 | beginner → advanced | [`lyra-practical/`](lyra-practical/) |

---

## 教程结构（每篇统一遵循）

```
🌱 概念直觉   一句话 + 类比，10 秒理解"是什么"
       ↓
🔬 技术机制   关键代码片段 + Mermaid 流程图 + API 解读
       ↓
🏗️ Lyra 实例  对应 Lyra 真实代码，理论落地
```

每篇 frontmatter 含：

- `series` / `lesson_index` — 系列内顺序
- `difficulty` — beginner / intermediate / advanced
- `prerequisites` — 前置课程（构成依赖图，由 `wiki_query.py` 利用做"沿因果链多跳推理"）
- `engine_sources` / `lyra_sources` — 锚到 UE 引擎与 Lyra 项目源码的具体路径

详见 [`../.wiki-schema.md`](../.wiki-schema.md) §页面格式。

## 学习建议

### 第一次接触 UE

1. 先读 [`../README.md`](../README.md) §9.1 第一周建议
2. 选 [`../00-meta/learning-paths.md`](../00-meta/learning-paths.md) 中**路线 A：UE 框架基础**
3. 按系列内 `_series.yaml` 的 `learning_path` 顺序读

### 想深入某主题

直接进对应系列的 `00-...系列概览.md`，往下按序号读即可。

### 不知道该学什么

跑 `wiki_query.py` 让它推荐：

```bash
python3 ../../.codebuddy/skills/project-wiki/scripts/wiki_query.py "你感兴趣的关键词"
python3 ../../.codebuddy/skills/project-wiki/scripts/wiki_query.py --series <slug>   # 看一整个系列
```

## 教程质量保障

每个系列大改后需通过 [`review-series` 工作流](../../.codebuddy/skills/project-wiki/workflows/review-series.md)审查，报告归档于 `../_raw/review-reports/`。

`wiki_lint.py` 对教程页有专项检查（`tutorial-fm`）：必须含 `lesson_index` / `difficulty` / `series` 等字段。

---

> 📌 持续更新中。如系列篇数 / 入口路径有调整，请同步更新本文。最后更新：2026-05-23。
