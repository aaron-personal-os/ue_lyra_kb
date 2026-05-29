---
id: 20-modules/cpp/ULyraHealthComponent
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/Character/LyraHealthComponent.h
  - path: Source/LyraGame/Character/LyraHealthComponent.cpp
related:
  - "[[20-modules/cpp/ALyraCharacter]]"
  - "[[10-architecture/subsystems/ability-system]]"
sources: []
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [health, gas, replication, character]
---

# ULyraHealthComponent

> 角色生命值组件，监听 GAS AttributeSet 并复制死亡状态。

## 职责

- 绑定 `ULyraAbilitySystemComponent` 和 `ULyraHealthSet`。
- 对外提供当前生命值、最大生命值、归一化生命值查询。
- 监听 Health / MaxHealth / OutOfHealth 变化。
- 广播生命值变化、死亡开始和死亡结束事件。
- 维护并复制 `ELyraDeathState`。

## 网络相关点

| 符号 | 说明 |
|---|---|
| `UPROPERTY(ReplicatedUsing=OnRep_DeathState) DeathState` | 死亡状态复制入口。 |
| `OnRep_DeathState` | 客户端根据死亡状态变化触发死亡流程事件。 |
| `InitializeWithAbilitySystem` | 绑定 ASC 和 HealthSet，接收属性变化。 |
| `StartDeath` / `FinishDeath` | 服务端/客户端死亡流程状态推进。 |

## 相关页面

- [[20-modules/cpp/ALyraCharacter]]
- [[10-architecture/subsystems/ability-system]]

<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ULyraPawnExtensionComponent|ULyraPawnExtensionComponent]] · [[20-modules/cpp/ULyraCameraComponent|ULyraCameraComponent]] →

<!-- /nav:auto -->
