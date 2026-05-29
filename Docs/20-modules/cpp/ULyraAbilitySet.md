---
id: 20-modules/cpp/ULyraAbilitySet
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/AbilitySystem/LyraAbilitySet.h
  - path: Source/LyraGame/AbilitySystem/LyraAbilitySet.cpp
related:
  - "[[10-architecture/subsystems/ability-system]]"
  - "[[20-modules/cpp/ULyraEquipmentManagerComponent]]"
sources: []
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [gas, ability-set, equipment]
---

# ULyraAbilitySet

> Lyra 的能力集合数据资产，用于一次性授予 Ability、GameplayEffect 和 AttributeSet。

## 职责

- 描述要授予的 `ULyraGameplayAbility`、`UGameplayEffect` 和 `UAttributeSet`。
- `GiveToAbilitySystem` 将配置授予指定 `ULyraAbilitySystemComponent`。
- `FLyraAbilitySet_GrantedHandles` 记录授予句柄，便于装备卸下或状态移除时回收。

## 网络相关点

- AbilitySet 本身是数据资产，不直接复制运行时状态。
- 授予结果写入 ASC，ASC 的 AbilitySpec、GE、Attribute 等按 GAS 复制规则同步。
- Equipment 通过 `FLyraAppliedEquipmentEntry::GrantedHandles` 保存 authority-only 句柄，卸装时调用 `TakeFromAbilitySystem` 回收。

## 相关页面

- [[10-architecture/subsystems/ability-system]]
- [[20-modules/cpp/ULyraEquipmentManagerComponent]]
- [[40-runbooks/how-to-add-gameplay-ability]]

<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ULyraGameplayAbility|ULyraGameplayAbility]] · [[20-modules/cpp/ULyraInventoryManagerComponent|ULyraInventoryManagerComponent]] →

<!-- /nav:auto -->
