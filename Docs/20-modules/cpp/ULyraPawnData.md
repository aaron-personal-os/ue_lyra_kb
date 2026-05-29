---
id: 20-modules/cpp/ULyraPawnData
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/Character/LyraPawnData.h
  - path: Source/LyraGame/Character/LyraPawnData.cpp
related:
  - "[[20-modules/cpp/ULyraExperienceDefinition]]"
  - "[[20-modules/cpp/ULyraPawnExtensionComponent]]"
sources: []
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [pawn-data, experience, ability-set]
---

# ULyraPawnData

> Pawn 配置数据资产，定义 Pawn class、input、camera、AbilitySets 等初始化数据。

## 职责

- 为 Experience / GameMode 提供默认 Pawn 配置。
- 描述 Pawn class、InputConfig、DefaultCameraMode。
- 列出要授予 ASC 的 AbilitySets。
- 被 `ULyraPawnExtensionComponent` 复制并用于 Pawn 初始化。

## 网络相关点

`ULyraPawnData` 本身是数据资产，不是运行时复制状态；但它通常通过 `PawnData` 字段被 PlayerState/PawnExtension 复制到客户端，随后驱动客户端初始化 Ability、Input 和表现。

## 相关页面

- [[20-modules/cpp/ULyraExperienceDefinition]]
- [[20-modules/cpp/ULyraPawnExtensionComponent]]

<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ULyraExperienceManagerComponent|ULyraExperienceManagerComponent]] · [[20-modules/cpp/ULyraPawnExtensionComponent|ULyraPawnExtensionComponent]] →

<!-- /nav:auto -->
