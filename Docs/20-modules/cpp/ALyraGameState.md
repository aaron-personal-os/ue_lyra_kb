---
id: 20-modules/cpp/ALyraGameState
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/GameModes/LyraGameState.h
  - path: Source/LyraGame/GameModes/LyraGameState.cpp
related:
  - "[[20-modules/cpp/ULyraExperienceManagerComponent]]"
  - "[[10-architecture/subsystems/ability-system]]"
  - "[[20-modules/cpp/ALyraGameMode]]"
sources: []
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [game-state, replication, experience, gas]
---

# ALyraGameState

> Lyra 的 GameState 基类，承载全局 ExperienceManager、全局 ASC 和全局消息复制。

## 职责

- 创建并持有 `ULyraExperienceManagerComponent`。
- 创建全局 `ULyraAbilitySystemComponent`，用于 game-wide gameplay cue 等能力系统需求。
- 复制 `ServerFPS` 和 replay recorder player state。
- 提供 multicast 消息函数向所有客户端广播通知。

## 网络相关点

| 符号 | 说明 |
|---|---|
| `MulticastMessageToClients` | unreliable NetMulticast，适合可丢弃通知。 |
| `MulticastReliableMessageToClients` | reliable NetMulticast，适合不可丢失通知，不能高频滥用。 |
| `ServerFPS` | replicated 全局服务器帧率。 |
| `RecorderPlayerState` | replay 场景下复制的跟随目标。 |
| `ExperienceManagerComponent` | 复制当前 Experience 的组件。 |

## 相关页面

- [[20-modules/cpp/ULyraExperienceManagerComponent]]
- [[10-architecture/subsystems/experience-system]]
- [[30-tutorials/network-sync/04-Legacy属性复制与RPC流程]]

<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ALyraGameMode|ALyraGameMode]] · [[20-modules/cpp/ALyraPlayerState|ALyraPlayerState]] →

<!-- /nav:auto -->
