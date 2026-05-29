---
id: 20-modules/cpp/ULyraGameplayAbility
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/AbilitySystem/Abilities/LyraGameplayAbility.h
  - path: Source/LyraGame/AbilitySystem/Abilities/LyraGameplayAbility.cpp
related:
  - "[[10-architecture/subsystems/ability-system]]"
  - "[[20-modules/cpp/ULyraAbilitySystemComponent]]"
sources: []
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [gas, gameplay-ability, prediction]
---

# ULyraGameplayAbility

> Lyra 的 GameplayAbility 基类，封装 Lyra controller、character、camera mode、activation policy 等项目级能力行为。

## 职责

- 提供访问 Lyra ASC、Controller、Character 的便捷接口。
- 定义 `ELyraAbilityActivationPolicy`：输入触发、输入保持、OnSpawn。
- 定义 `ELyraAbilityActivationGroup`：Independent、Exclusive Replaceable、Exclusive Blocking。
- 支持 Ability 成本、失败表现、CameraMode 切换等 Lyra 扩展。
- 与 `ULyraAbilitySystemComponent` 的输入处理和激活组管理配合。

## 网络相关点

- Ability 的 `NetExecutionPolicy` / `NetSecurityPolicy` 仍由 GAS 基类控制。
- Lyra 输入触发链路由 ASC 收集 InputTag 后调用 `TryActivateAbility`。
- 对本地预测 Ability，应关注 PredictionKey、TargetData、CommitAbility 与服务器确认。

## 相关页面

- [[10-architecture/subsystems/ability-system]]
- [[30-tutorials/gas/01-GA简介与配置]]
- [[30-tutorials/gas/23-PredictionKey预判机制]]

<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ULyraAbilitySystemComponent|ULyraAbilitySystemComponent]] · [[20-modules/cpp/ULyraAbilitySet|ULyraAbilitySet]] →

<!-- /nav:auto -->
