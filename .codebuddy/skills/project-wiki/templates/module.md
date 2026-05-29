---
id: 20-modules/{{LAYER}}/{{NAME}}
type: module
status: draft
language: zh
owner: ai
anchors:
  - path: {{ANCHOR_PATH_1}}
  # - path: {{ANCHOR_PATH_2}}
related: []
sources: []
last_synced: {{DATE}}
last_verified: {{DATE}}
tags: []
---

# {{NAME}}

> 一句话说清这个模块做什么。

## What — 职责边界

- **属于**：[[10-architecture/subsystems/{{SUBSYSTEM}}]]
- **入口**：（主要类/函数/入口点）
- **不做**：（明确划清边界，避免和邻居模块混淆）

## How — 关键设计

（关键的内部结构、状态机、调用链。不要复制代码——code 才是真相，这里写**为什么这样设计**。）

## Why — 设计决策与权衡

- 为什么不用方案 A？
- 为什么不用方案 B？
- 当前方案的代价是什么？

如有正式决策记录 → 链 `[[60-decisions/NNNN-...]]`。

## Gotchas — 已知陷阱

- 容易踩的坑 1
- 容易踩的坑 2

如有专门页 → 链 `[[80-gotchas/...]]`。

## 与其他模块的依赖

- 依赖 [[20-modules/.../X]]：理由
- 被 [[20-modules/.../Y]] 依赖：理由

## 相关页面

- [[10-architecture/subsystems/{{SUBSYSTEM}}]]
- [[60-decisions/...]]
- [[80-gotchas/...]]
