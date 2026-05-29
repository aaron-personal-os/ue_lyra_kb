---
id: 20-modules/cpp/ULyraAbilitySystemComponent
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/AbilitySystem/LyraAbilitySystemComponent.h
  - path: Source/LyraGame/AbilitySystem/LyraAbilitySystemComponent.cpp
related:
  - "[[10-architecture/subsystems/ability-system]]"
  - "[[20-modules/cpp/ALyraPlayerState]]"
  - "[[20-modules/cpp/ULyraGameplayAbility]]"
sources: []
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [gas, ability-system, input, prediction]
---

# ULyraAbilitySystemComponent

> Lyra 的 ASC 派生类，负责输入驱动 Ability、激活组、Ability 失败通知和 TargetData 访问。

## 职责

- 在 avatar pawn 变化时通知 Ability 实例。
- 注册到 `ULyraGlobalAbilitySystem`。
- 处理按下/释放/持续输入标签并批量激活 Ability。
- 禁用 `bReplicateInputDirectly` 风格，使用 replicated events 支撑 `WaitInputPress/Release`。
- 管理 Lyra Ability Activation Group。
- 提供 `GetAbilityTargetData`，服务武器 TargetData 链路。

## 网络相关点

| 符号 | 说明 |
|---|---|
| `AbilitySpecInputPressed/Released` | 对已激活 Ability 调用 `InvokeReplicatedEvent`，支撑输入事件跨网络同步。 |
| `ProcessAbilityInput` | 每帧处理输入集合并调用 `TryActivateAbility`。 |
| `ClientNotifyAbilityFailed` | unreliable Client RPC，通知本地 Ability 激活失败表现。 |
| `GetAbilityTargetData` | 读取 Ability handle + activation info 对应 TargetData。 |

## 相关页面

- [[10-architecture/subsystems/ability-system]]
- [[30-tutorials/gas/23-PredictionKey预判机制]]
- [[20-modules/cpp/ALyraPlayerState]]

<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ULyraCameraComponent|ULyraCameraComponent]] · [[20-modules/cpp/ULyraGameplayAbility|ULyraGameplayAbility]] →

<!-- /nav:auto -->
