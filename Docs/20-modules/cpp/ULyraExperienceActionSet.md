---
id: 20-modules/cpp/ULyraExperienceActionSet
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/GameModes/LyraExperienceActionSet.h
  - path: Source/LyraGame/GameModes/LyraExperienceActionSet.cpp
related:
  - "[[20-modules/cpp/ULyraExperienceDefinition]]"
  - "[[10-architecture/subsystems/experience-system]]"
sources: []
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [experience, action-set, game-feature]
---

# ULyraExperienceActionSet

> Experience 的动作集合数据资产，用于复用一组 GameFeature actions。

## 职责

- 保存一组 `UGameFeatureAction`。
- 保存需要启用的 GameFeature 插件列表。
- 被 `ULyraExperienceDefinition` 引用，参与 Experience 加载和执行。

## 网络相关点

ActionSet 本身是配置资产，不直接复制运行时状态；它影响 Experience 加载后的组件注入、输入、能力授予、UI 扩展等系统，因此会间接影响联网对局中各端初始化是否一致。

## 相关页面

- [[20-modules/cpp/ULyraExperienceDefinition]]
- [[10-architecture/subsystems/experience-system]]

<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ULyraExperienceDefinition|ULyraExperienceDefinition]] · [[20-modules/cpp/ULyraExperienceManagerComponent|ULyraExperienceManagerComponent]] →

<!-- /nav:auto -->
