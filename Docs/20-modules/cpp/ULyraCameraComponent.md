---
id: 20-modules/cpp/ULyraCameraComponent
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/Camera/LyraCameraComponent.h
  - path: Source/LyraGame/Camera/LyraCameraComponent.cpp
related:
  - "[[20-modules/cpp/ALyraCharacter]]"
sources: []
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [camera, character, local-presentation]
---

# ULyraCameraComponent

> Lyra 的角色相机组件，负责 CameraMode 栈和本地视角输出。

## 职责

- 继承 `UCameraComponent`。
- 维护 `ULyraCameraModeStack`。
- 通过 `DetermineCameraModeDelegate` 查询当前最佳 CameraMode。
- 在 `GetCameraView` 中更新并输出最终视角。
- 支持一帧内 FOV offset。

## 网络边界

`ULyraCameraComponent` 本身不是网络同步核心，它主要消费本地 Pawn/Controller 状态并输出视角。网络相关性在于：

- 依赖 `ALyraCharacter` / Controller / PlayerState 同步出的 gameplay 状态。
- 摄像机表现应尽量由本地预测和已复制状态驱动，不应反向成为服务端权威状态。

## 相关页面

- [[20-modules/cpp/ALyraCharacter]]

<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ULyraHealthComponent|ULyraHealthComponent]] · [[20-modules/cpp/ULyraAbilitySystemComponent|ULyraAbilitySystemComponent]] →

<!-- /nav:auto -->
