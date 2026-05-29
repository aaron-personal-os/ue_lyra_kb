---
id: 20-modules/cpp/ULyraPawnExtensionComponent
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/Character/LyraPawnExtensionComponent.h
  - path: Source/LyraGame/Character/LyraPawnExtensionComponent.cpp
related:
  - "[[20-modules/cpp/ALyraCharacter]]"
  - "[[20-modules/cpp/ALyraPlayerState]]"
  - "[[20-modules/cpp/ULyraPawnData]]"
  - "[[30-tutorials/modular-gameplay/03-组件生命周期]]"
sources: []
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [pawn, modular-gameplay, ability-system, replication]
---

# ULyraPawnExtensionComponent

> Pawn 初始化协调组件，负责把 PawnData、Controller、PlayerState 与 AbilitySystem 连接起来。

## 职责

- 实现 `IGameFrameworkInitStateInterface`，协调 Pawn 相关组件初始化状态。
- 复制 `PawnData`，并通过 `OnRep_PawnData` 触发默认初始化检查。
- 缓存当前 `ULyraAbilitySystemComponent`。
- 在 Controller / PlayerState / InputComponent 变化时通知相关组件。
- 将 Pawn 设置为 ASC 的 avatar actor，并在卸载时反初始化。

## 网络相关点

| 符号 | 说明 |
|---|---|
| `UPROPERTY(ReplicatedUsing=OnRep_PawnData) PawnData` | Pawn 配置数据复制入口。 |
| `OnRep_PawnData` | 客户端收到 PawnData 后继续初始化链。 |
| `InitializeAbilitySystem` | 将 ASC 与 Pawn avatar 绑定。 |
| `HandlePlayerStateReplicated` | `ALyraCharacter::OnRep_PlayerState` 后调用，保证客户端初始化 ASC。 |

## 相关页面

- [[20-modules/cpp/ALyraCharacter]]
- [[10-architecture/subsystems/ability-system]]
- [[10-architecture/subsystems/modular-gameplay]]

<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ULyraPawnData|ULyraPawnData]] · [[20-modules/cpp/ULyraHealthComponent|ULyraHealthComponent]] →

<!-- /nav:auto -->
