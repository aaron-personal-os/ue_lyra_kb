---
id: 20-modules/cpp/ULyraWeaponInstance
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/Weapons/LyraWeaponInstance.h
  - path: Source/LyraGame/Weapons/LyraWeaponInstance.cpp
  - path: Source/LyraGame/Weapons/LyraRangedWeaponInstance.h
  - path: Source/LyraGame/Weapons/LyraRangedWeaponInstance.cpp
related:
  - "[[20-modules/cpp/ULyraEquipmentManagerComponent]]"
  - "[[20-modules/cpp/ULyraWeaponStateComponent]]"
sources: []
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [weapon, equipment, networking]
---

# ULyraWeaponInstance

> Lyra 武器装备实例，继承自 `ULyraEquipmentInstance`，负责武器装备/卸下表现、开火时间和远程武器扩展状态。

## 职责

- 在装备/卸下时应用或移除动画层、输入设备反馈等表现。
- 记录最近装备和开火时间。
- `ULyraRangedWeaponInstance` 扩展射击参数、散布、后坐力、弹丸追踪等远程武器状态。
- 作为 EquipmentInstance 子对象的一类，依赖 EquipmentManager 复制生命周期。

## 网络相关点

- `ULyraWeaponInstance` 本身继承 `ULyraEquipmentInstance` 的 SubObject 网络能力。
- 装备列表通过 `ULyraEquipmentManagerComponent` 的 FastArray 同步。
- WeaponStateComponent 负责 TargetData 命中确认；WeaponInstance 负责当前武器参数和表现状态。

## 相关页面

- [[20-modules/cpp/ULyraEquipmentManagerComponent]]
- [[20-modules/cpp/ULyraWeaponStateComponent]]
- [[40-runbooks/how-to-add-new-weapon]]

<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ULyraEquipmentManagerComponent|ULyraEquipmentManagerComponent]] · [[20-modules/cpp/ULyraWeaponStateComponent|ULyraWeaponStateComponent]] →

<!-- /nav:auto -->
