---
id: 20-modules/cpp/ULyraExperienceManagerComponent
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/GameModes/LyraExperienceManagerComponent.h
  - path: Source/LyraGame/GameModes/LyraExperienceManagerComponent.cpp
related:
  - "[[10-architecture/subsystems/experience-system]]"
  - "[[20-modules/cpp/ALyraGameState]]"
sources: []
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [experience, game-state, replication]
---

# ULyraExperienceManagerComponent

> GameState 组件，负责加载和激活当前 Experience。

## 职责

- 复制 `CurrentExperience`，客户端通过 `OnRep_CurrentExperience` 跟随服务端 Experience。
- 管理 Experience 加载状态机：加载资产、启用 GameFeature、执行 Actions、广播 Loaded。
- 提供高/普通/低优先级的 `CallOrRegister_OnExperienceLoaded` 回调。
- 实现 `ILoadingProcessInterface`，控制加载屏显示。

## 网络相关点

| 符号 | 说明 |
|---|---|
| `UPROPERTY(ReplicatedUsing=OnRep_CurrentExperience)` | 当前 Experience 的复制入口。 |
| `OnRep_CurrentExperience` | 客户端收到 Experience 后启动加载流程。 |
| `OnExperienceLoaded` delegates | PlayerState、Pawn 初始化等系统可等待 Experience 完成后继续。 |

## 相关页面

- [[10-architecture/subsystems/experience-system]]
- [[20-modules/cpp/ALyraGameState]]
- [[40-runbooks/how-to-create-new-experience]]

<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ULyraExperienceActionSet|ULyraExperienceActionSet]] · [[20-modules/cpp/ULyraPawnData|ULyraPawnData]] →

<!-- /nav:auto -->
