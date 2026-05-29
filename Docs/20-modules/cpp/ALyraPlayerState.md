---
id: 20-modules/cpp/ALyraPlayerState
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/Player/LyraPlayerState.h
  - path: Source/LyraGame/Player/LyraPlayerState.cpp
related:
  - "[[10-architecture/subsystems/networking-system]]"
  - "[[10-architecture/subsystems/ability-system]]"
  - "[[20-modules/cpp/ULyraAbilitySystemComponent]]"
  - "[[20-modules/cpp/ULyraPawnExtensionComponent]]"
sources: []
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [player-state, gas, replication, push-model]
---

# ALyraPlayerState

> Lyra 的玩家状态对象，是 ASC、PawnData、团队和玩家统计标签的主要复制承载点。

## 网络职责

- 持有并复制 `ULyraAbilitySystemComponent`。
- 将 ASC 复制模式设置为 `EGameplayEffectReplicationMode::Mixed`。
- 提高 `NetUpdateFrequency` 到 `100.0f`，满足 ASC 高同步需求。
- 用 PushModel 复制 `PawnData`、连接类型、团队、Squad、视角旋转等字段。
- 复制 `StatTags`，配合 GameplayTag 快速复制配置。
- 提供 unreliable Client RPC `ClientBroadcastMessage` 做玩家私有通知。

## 关键符号

| 符号 | 说明 |
|---|---|
| `AbilitySystemComponent->SetIsReplicated(true)` | ASC 参与复制。 |
| `SetReplicationMode(EGameplayEffectReplicationMode::Mixed)` | 主控客户端完整 GE，模拟端 minimal。 |
| `DOREPLIFETIME_WITH_PARAMS_FAST(..., SharedParams)` | PushModel 复制关键 PlayerState 字段。 |
| `MARK_PROPERTY_DIRTY_FROM_NAME` | 权威端修改 PushModel 字段后显式标脏。 |
| `ForceNetUpdate()` | 设置 PawnData 后立即推动复制。 |
| `StatTags` | 玩家统计标签复制容器。 |

## 相关页面

- [[10-architecture/subsystems/networking-system]]
- [[30-tutorials/gas/14-GE网络复制]]
- [[30-tutorials/network-sync/03-LegacyActor复制流程]]

<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ALyraGameState|ALyraGameState]] · [[20-modules/cpp/ULyraExperienceDefinition|ULyraExperienceDefinition]] →

<!-- /nav:auto -->
