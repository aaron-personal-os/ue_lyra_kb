---
id: 30-tutorials/config-ini/06-Lyra项目配置实例解读
title: Lyra项目配置实例解读
description: 逐段解读 Lyra 项目的实际 INI 文件，理解配置如何驱动 GAS、Experience、AssetManager 等核心系统。
type: tutorial
status: current
language: zh
owner: ai
series: config-ini
lesson_index: 6
difficulty: intermediate
prerequisites: ["[[30-tutorials/config-ini/05-UObject与Config系统集成]]"]
tags: [config, ini, lyra, defaultgame.ini, defaultengine.ini]
last_synced: 2026-05-17
last_verified: 2026-05-17
lyra_sources:
  - path: Config/DefaultGame.ini
    description: Lyra 游戏配置全解析
  - path: Config/DefaultEngine.ini
    description: Lyra 引擎配置全解析
  - path: Saved/Config/Windows/GameUserSettings.ini
    description: Lyra 用户设置配置（运行时生成）
  - path: Config/DefaultInput.ini
    description: Lyra 输入配置
---

# Lyra项目配置实例解读

> 逐段解读 Lyra 项目的实际 INI 文件，理解配置如何驱动 GAS、Experience、AssetManager 等核心系统。

## 概述

本课学完你将能：读懂 Lyra 所有 INI 文件的每一段配置，理解配置如何与 C++ 代码联动，并能借鉴 Lyra 的实践到自己的项目中。

## Lyra INI 文件总览

Lyra 项目 `Config/` 目录下的主要 INI 文件：

| 文件名 | 作用 | 关键配置段 |
|---|---|---|
| `DefaultGame.ini` | 游戏逻辑配置 | `AbilitySystemGlobals`、`AssetManagerSettings`、`LyraExperienceManagerComponent` |
| `DefaultEngine.ini` | 引擎配置 | `GameEngine`、`CollisionSettings`、`RendererSettings`、`EnhancedInputSettings` |
| `Saved/Config/{PLATFORM}/GameUserSettings.ini` | 用户设置（运行时生成） | `GameUserSettings` |
| `DefaultInput.ini` | 输入映射 | `EnhancedInputSettings` |

## DefaultGame.ini 逐段解析

### `/Script/EngineSettings.GeneralProjectSettings`

```ini
[/Script/EngineSettings.GeneralProjectSettings]
ProjectID=0537642E459369628A8717AB63363CBF
Description=Sample starter game for Unreal Engine 5
ProjectName=Lyra
```

**对应 C++ 类**：`UGeneralProjectSettings`

**说明**：项目基本信息，`ProjectName=Lyra` 会显示在窗口标题栏。

---

### `/Script/LyraGame.LyraPlayerController`

```ini
[/Script/LyraGame.LyraPlayerController]
InputYawScale=1.0
InputPitchScale=1.0
InputRollScale=1.0
ForceFeedbackScale=1.0
```

**对应 C++ 类**：`ALyraPlayerController`

**说明**：鼠标/手柄输入缩放系数。

---

### `/Script/GameplayAbilities.AbilitySystemGlobals`

```ini
[/Script/GameplayAbilities.AbilitySystemGlobals]
AbilitySystemGlobalsClassName=/Script/LyraGame.LyraAbilitySystemGlobals
bUseDebugTargetFromHud=True
GlobalGameplayCueManagerClass=/Script/LyraGame.LyraGameplayCueManager
+GameplayCueNotifyPaths=/Game/GameplayCueNotifies
+GameplayCueNotifyPaths=/Game/GameplayCues
```

**对应 C++ 类**：`UAbilitySystemGlobals`

**说明**：
- `AbilitySystemGlobalsClassName`：指定 `ULyraAbilitySystemGlobals` 作为 GAS 全局单例
- `GlobalGameplayCueManagerClass`：指定 `ULyraGameplayCueManager` 处理 GameplayCue
- `+GameplayCueNotifyPaths`：添加 GameplayCue 通知路径（数组追加）

---

### `/Script/Engine.GameNetworkManager`

```ini
[/Script/Engine.GameNetworkManager]
TotalNetBandwidth=200000
MaxDynamicBandwidth=40000
MinDynamicBandwidth=20000
```

**对应 C++ 类**：`AGameNetworkManager`

**说明**：网络带宽配置，与 `DefaultEngine.ini` 中的 `ConfiguredInternetSpeed` 匹配。

---

### `/Script/GameFeatures.GameFeaturesSubsystemSettings`

```ini
[/Script/GameFeatures.GameFeaturesSubsystemSettings]
GameFeaturesManagerClassName=/Script/LyraGame.LyraGameFeaturePolicy
```

**对应 C++ 类**：`UGameFeaturesSubsystemSettings`

**说明**：指定 `ULyraGameFeaturePolicy` 作为 GameFeature 管理器。

---

### `/Script/LyraGame.LyraAssetManager`

```ini
[/Script/LyraGame.LyraAssetManager]
LyraGameDataPath=/Game/DefaultGameData.DefaultGameData
DefaultPawnData=/Game/Characters/Heroes/EmptyPawnData/DefaultPawnData_EmptyPawn.DefaultPawnData_EmptyPawn
```

**对应 C++ 类**：`ULyraAssetManager`（继承自 `UAssetManager`）

**说明**：
- `LyraGameDataPath`：指定 `ULyraGameData` 资产路径
- `DefaultPawnData`：默认 PawnData（Experience 系统使用）

---

### `/Script/Engine.AssetManagerSettings`

```ini
[/Script/Engine.AssetManagerSettings]
-PrimaryAssetTypesToScan=(PrimaryAssetType="Map",...)
+PrimaryAssetTypesToScan=(PrimaryAssetType="Map",...)
+PrimaryAssetTypesToScan=(PrimaryAssetType="LyraGameData",...)
+PrimaryAssetTypesToScan=(PrimaryAssetType="LyraExperienceDefinition",...)
```

**对应 C++ 类**：`UAssetManagerSettings`

**说明**：
- 先 `-PrimaryAssetTypesToScan=...` 移除基类的设置
- 然后 `+PrimaryAssetTypesToScan=...` 添加 Lyra 自己的设置
- 定义了 `LyraGameData`、`LyraExperienceDefinition`、`LyraUserFacingExperienceDefinition` 等资产类型

---

## DefaultEngine.ini 逐段解析

### `/Script/Engine.GameEngine`

```ini
[/Script/Engine.GameEngine]
GameEngine=/Script/LyraGame.LyraGameEngine
GameViewportClientClassName=/Script/LyraGame.LyraGameViewportClient
```

**对应 C++ 类**：`UGameEngine`

**说明**：指定 Lyra 自定义的 `ULyraGameEngine` 和 `ULyraGameViewportClient`。

---

### `/Script/Engine.Engine`

```ini
[/Script/Engine.Engine]
GameEngine=/Script/LyraGame.LyraGameEngine
UnrealEdEngine=/Script/LyraEditor.LyraEditorEngine
EditorEngine=/Script/LyraEditor.LyraEditorEngine
GameViewportClientClassName=/Script/LyraGame.LyraGameViewportClient
AssetManagerClassName=/Script/LyraGame.LyraAssetManager
WorldSettingsClassName=/Script/LyraGame.LyraWorldSettings
LocalPlayerClassName=/Script/LyraGame.LyraLocalPlayer
GameUserSettingsClassName=/Script/LyraGame.LyraSettingsLocal
NearClipPlane=3.000000
```

**对应 C++ 类**：`UEngine`

**说明**：
- 指定 Lyra 自定义的各种全局类
- `GameUserSettingsClassName` 指向 `ULyraSettingsLocal`（使用 `config=GameUserSettings`）

---

### `/Script/IrisCore.ObjectReplicationBridgeConfig`

```ini
[/Script/IrisCore.ObjectReplicationBridgeConfig]
DefaultSpatialFilterName=Spatial
!FilterConfigs=ClearArray
+FilterConfigs=(ClassName=/Script/Engine.LevelScriptActor, DynamicFilterName=NotRouted)
+FilterConfigs=(ClassName=/Script/Engine.Actor, DynamicFilterName=None)
+FilterConfigs=(ClassName=/Script/Engine.Info, DynamicFilterName=None)
+FilterConfigs=(ClassName=/Script/Engine.PlayerState, DynamicFilterName=None)
+FilterConfigs=(ClassName=/Script/Engine.Pawn, DynamicFilterName=Spatial)
```

**对应 C++ 类**：`UObjectReplicationBridgeConfig`（Iris 复制系统）

**说明**：
- `!FilterConfigs=ClearArray` 先清空基类过滤器
- 然后重新添加 Lyra 的过滤器配置
- `DynamicFilterName=Spatial` 表示 Pawn 使用空间过滤（适合 FPS 游戏）

---

### `/Script/Engine.GameMapsSettings`

```ini
[/Script/Engine.GameMapsSettings]
GlobalDefaultGameMode=/Game/B_LyraGameMode.B_LyraGameMode_C
GameInstanceClass=/Game/B_LyraGameInstance.B_LyraGameInstance_C
GameDefaultMap=/Game/System/FrontEnd/Maps/L_LyraFrontEnd.L_LyraFrontEnd
EditorStartupMap=/Game/System/DefaultEditorMap/L_DefaultEditorOverview.L_DefaultEditorOverview
```

**对应 C++ 类**：`UGameMapsSettings`

**说明**：
- `GlobalDefaultGameMode`：**注意** — Lyra 实际通过 Experience 动态加载 GameMode，此处可能是备用值
- `GameInstanceClass`：指定 `ULyraGameInstance`
- `GameDefaultMap`：默认地图（前端地图）

---

### `/Script/Engine.Player`

```ini
[/Script/Engine.Player]
ConfiguredInternetSpeed=200000
ConfiguredLanSpeed=200000
```

**对应 C++ 类**：`UPlayer`

**说明**：网络速度配置（与 `GameNetworkManager` 的带宽设置匹配）。

---

### `/Script/Engine.RendererSettings`

```ini
[/Script/Engine.RendererSettings]
r.SkinCache.CompileShaders=True
r.DefaultFeature.AutoExposure.ExtendDefaultLuminanceRange=True
r.VirtualTextures=True
r.SupportMaterialLayers=True
r.CustomDepth=3
r.GenerateMeshDistanceFields=True
r.AllowStaticLighting=False
r.AntiAliasingMethod=4
r.VirtualShadowMaps=True
```

**对应 C++ 类**：`URendererSettings`

**说明**：渲染设置，Lyra 启用：
- Lumen 全局光照（`r.DynamicGlobalIlluminationMethod=1`）
- 虚拟纹理（`r.VirtualTextures=True`）
- 硬件光线追踪（部分设置）

---

### `/Script/Engine.CollisionProfile`

```ini
[/Script/Engine.CollisionProfile]
+Profiles=(Name="LyraPawnMesh",CollisionEnabled=QueryOnly,...))
+Profiles=(Name="LyraPawnCapsule",CollisionEnabled=QueryOnly,...))
+Profiles=(Name="Interactable_OverlapDynamic",...)
```

**对应 C++ 类**：`UCollisionProfileSettings`

**说明**：Lyra 自定义碰撞配置：
- `LyraPawnMesh`：角色网格体碰撞（仅查询，无物理）
- `LyraPawnCapsule`：角色胶囊体碰撞
- 使用 `+Profiles=` 追加（数组操作）

---

## INI 配置与 C++ 代码映射表

| INI Section | 对应 C++ 类 | 说明 |
|---|---|---|
| `/Script/Engine.GameSession` | `AGameSession` | 游戏会话设置 |
| `/Script/GameplayAbilities.AbilitySystemGlobals` | `UAbilitySystemGlobals` | GAS 全局设置 |
| `/Script/Engine.AssetManagerSettings` | `UAssetManagerSettings` | AssetManager 设置 |
| `/Script/LyraGame.LyraExperienceManagerComponent` | `ULyraExperienceManagerComponent` | Experience 管理器 |
| `/Script/Engine.GameEngine` | `UGameEngine` | 游戏引擎设置 |
| `/Script/Engine.Engine` | `UEngine` | 引擎全局设置 |
| `/Script/EnhancedInput.EnhancedInputSettings` | `UEnhancedInputSettings` | 增强输入设置 |
| `/Script/LyraGame.LyraSettingsLocal` | `ULyraSettingsLocal` | 用户设置（`config=GameUserSettings`） |

## Lyra 配置最佳实践

### 实践 1：使用 Experience 驱动 GameMode

Lyra **不直接指定** `DefaultGameMode`，而是通过 Experience 动态加载：

```ini
# DefaultGame.ini 中没有直接指定 GameMode
# 而是在 Experience 资产中指定：
# /Game/System/Experiences/ExP_ShooterGame.ExP_ShooterGame_C
#   → DefaultGameMode = /Game/LyraExampleContent/Experiences/ExP_ShooterGame.ExP_ShooterGame_C
```

### 实践 2：AssetManager 路径配置

正确配置 `PrimaryAssetTypesToScan` 以优化资源加载：

```ini
[/Script/Engine.AssetManagerSettings]
+PrimaryAssetTypesToScan=(PrimaryAssetType="LyraExperienceDefinition",AssetBaseClass="/Script/LyraGame.LyraExperienceDefinition",bHasBlueprintClasses=True,bIsEditorOnly=False,Directories=((Path="/Game/System/Experiences")),SpecificAssets=...,Rules=(Priority=-1,...,CookRule=AlwaysCook))
```

### 实践 3：使用 `!` 和 `+` 组合替换数组

Lyra 常用的模式：

```ini
!FilterConfigs=ClearArray          ← 先清空数组
+FilterConfigs=(...)             ← 再重新添加
```

## 常见配置问题排查

### 问题 1：配置不生效

**排查步骤**：
1. 检查 INI 文件是否在正确层级（`Default*.ini` vs `Platform*.ini`）
2. 使用 `GConfig->GetString()` 打印值，确认加载来源
3. 检查是否有更高层级覆盖（如 `Saved/Config/`）

### 问题 2：平台配置未加载

**原因**：平台目录名称不匹配（如 `Win64/` 而不是 `Windows/`）

**解决**：确认 `{PLATFORM}` 宏展开值（Windows 平台是 `Windows`）

## 小结

- Lyra 的 INI 文件展示了正确的配置组织方式
- 使用 `!Key=ClearArray` + `+Key=...` 模式替换数组
- Experience 系统让 GameMode 等配置可以动态加载
- `config=GameUserSettings` 让 `ULyraSettingsLocal` 从 `DefaultGameUserSettings.ini` 加载

## 相关页面

- [[30-tutorials/config-ini/05-UObject与Config系统集成|← 上一课：UObject 与 Config 系统集成]]
- [[30-tutorials/config-ini/07-ConfigINI高级主题|下一课：高级主题 →]]
- [[30-tutorials/lyra-practical/02-ExperienceSystem详解|Experience 系统架构]]

<!-- nav:auto -->

---

**导航**: ← [[30-tutorials/config-ini/05-UObject与Config系统集成|05-UObject与Config系统集成]] · [[30-tutorials/config-ini/07-ConfigINI高级主题|07-ConfigINI高级主题]] →

<!-- /nav:auto -->
