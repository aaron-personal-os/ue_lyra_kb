---
id: 70-topics/game-feature-system
type: topic
status: current
language: zh
owner: ai
anchors:
  - path: Plugins/GameFeatures/ShooterCore/ShooterCore.uplugin
  - path: Source/LyraGame/GameModes/LyraExperienceDefinition.h
  - path: Source/LyraGame/GameModes/LyraExperienceManagerComponent.h
related:
  - "[[10-architecture/subsystems/experience-system]]"
  - "[[10-architecture/subsystems/modular-gameplay]]"
  - "[[10-architecture/overview]]"
  - "[[30-tutorials/game-feature/00-GameFeature系统从入门到实战]]"
sources:
  - "[[_raw/external/GameFeatures-基础]]"
last_synced: 2026-05-22
tags: [game-feature, modular, architecture, plugin]
---

# GameFeature 系统技术专题

> UE5 新一代模块化游戏架构，通过插件机制实现游戏功能的动态加载与卸载。

## 概述

GameFeature 是 UE5 引入的全新游戏架构模式，旨在解决传统游戏开发中功能耦合严重、难以复用、难以动态更新等问题。

**核心价值**：
- **模块化**：将游戏功能分解为独立的插件单元
- **动态性**：支持运行时动态加载/卸载功能
- **可复用**：功能模块可在多个项目间共享
- **团队协作**：不同团队成员可独立开发不同功能模块

**与 Lyra 的关系**：
Lyra 项目大量使用了 GameFeature 架构，通过 `ULyraExperienceDefinition` 定义不同的游戏体验，每个体验可以动态启用/禁用不同的 GameFeature 插件。

---

## 一、架构定位

### 1.1 GameFeature vs Plugin

| 特性 | Plugin | GameFeature |
|------|--------|-------------|
| 加载时机 | 启动时 | 运行时动态 |
| 依赖关系 | CoreGame 依赖 Plugin | GameFeature 依赖 CoreGame |
| 变更频率 | 低（基础功能） | 高（游戏玩法） |
| 复用性 | 跨项目基础功能 | 游戏玩法模块 |

### 1.2 生命周期状态

```
Installed → Registered → Activated → Deactivated → Uninstalled
```

- **Installed**：插件文件存在于 `Plugins/GameFeatures/` 目录
- **Registered**：插件已注册到 `UGameFeaturesSubsystem`
- **Activatd**：插件激活，所有 Actions 执行完毕
- **Deactivated**：插件停用，所有 Actions 反向清理

> 详细状态转换和 API 请参阅 [[30-tutorials/game-feature/03-生命周期与加载流程|课时 3：生命周期与加载流程]]。

---

## 二、Lyra 中的实践

### 2.1 Lyra GameFeature 插件列表

| 插件名称 | 功能描述 |
|---------|---------|
| **ShooterCore** | 射击游戏核心玩法（武器、射击、换弹等） |
| **TopDownArena** | 俯视角竞技场模式 |
| **ShooterExplorer** | 射击+探索混合模式（库存系统） |
| **ShooterMaps** | 射击游戏地图资源 |
| **ShooterTests** | 自动化测试套件 |

### 2.2 Experience System 与 GameFeature 的关系

Lyra 通过 **Experience Definition** 管理 GameFeature 的加载：

```
Experience Definition
  ├── GameFeaturesToEnable  → 要启用的插件列表
  ├── DefaultPawnData       → 默认 Pawn 数据
  ├── Actions                → 加载/激活时执行的操作
  └── ActionSets             → 可复用的操作集
```

**加载流程简述**：
1. `LyraExperienceManagerComponent::SetCurrentExperience(FPrimaryAssetId)` 启动加载
2. 异步加载 Experience Definition 资产
3. 遍历 `GameFeaturesToEnable`，调用 `LoadAndActivateGameFeaturePlugin()`
4. 所有插件激活后，执行 `Actions` 和 `ActionSets`
5. 广播 `OnExperienceLoaded` 委托（三优先级）

> 完整的加载流程代码和 `LyraExperienceManagerComponent` 详解，请参阅 [[30-tutorials/game-feature/04-Lyra中的ExperienceSystem实践|课时 4：Lyra 中的 Experience System 实践]]。

### 2.3 ULyraExperienceDefinition 关键属性

```cpp
UCLASS()
class ULyraExperienceDefinition : public UPrimaryDataAsset
{
    // 要启用的 Game Feature 插件列表
    UPROPERTY(EditDefaultsOnly, Category = "Gameplay")
    TArray<FString> GameFeaturesToEnable;

    // 默认 Pawn 数据
    UPROPERTY(EditDefaultsOnly, Category = "Gameplay")
    TObjectPtr<const ULyraPawnData> DefaultPawnData;

    // 加载/激活/停用/卸载时执行的操作
    UPROPERTY(EditDefaultsOnly, Instanced, Category = "Actions")
    TArray<TObjectPtr<UGameFeatureAction>> Actions;

    // 附加操作集（可复用）
    UPROPERTY(EditDefaultsOnly, Category = "Gameplay")
    TArray<TObjectPtr<ULyraExperienceActionSet>> ActionSets;
};
```

> 此类的完整属性说明请参阅 [[30-tutorials/game-feature/01-GameFeature是什么#ULyraExperienceDefinition 关键属性]]。

---

## 三、核心机制速查

### 3.1 GameFeaturePlugin

- 必须放在 `Plugins/GameFeatures/` 目录下
- `.uplugin` 文件中 `Category` 必须为 `"Game Features"`，`CanContainContent` 必须为 `true`
- 必须包含同名的 `GameFeatureData` 资产

### 3.2 GameFeatureData

- 定义 GameFeature 要执行的操作列表（Actions）
- 必须与插件同名（如 `ShooterCore` → `ShooterCore_GameFeatureData`）
- 需要在 `Project Settings` → `Asset Manager` 中配置 `Primary Asset Types`

### 3.3 GameFeatureAction

内置类型：`AddComponent`、`AddAbilities`、`AddInputBinding`、`AddWidget`、`AddGameplayCuePath`。

自定义 Action 需继承 `UGameFeatureAction_WorldActionBase`，重写：
- `OnGameFeatureActivating(FGameFeatureActivatingContext& Context)`
- `OnGameFeatureDeactivating(FGameFeatureDeactivatingContext& Context)`
- `AddToWorld(const FWorldContext&, const FGameFeatureStateChangeContext&)`

> 自定义 Action 的完整示例请参阅 [[30-tutorials/game-feature/05-GameFeature高级主题与最佳实践#一、自定义 GameFeatureAction|课时 5：自定义 Action]]。

---

## 四、与 Modular Gameplay 的协同

GameFeature 的 `AddComponent` Action 需要配合 Modular Gameplay 的 Receiver 机制才能生效：

- Actor 需在 `PreInitializeComponents()` 中调用 `UGameFrameworkComponentManager::AddGameFrameworkComponentReceiver(this)`
- 或在 `BeginPlay()` 中调用 `SendGameFrameworkComponentExtensionEvent(this, NAME_GameActorReady)`
- `AModularCharacter` 已自动完成上述注册，推荐继承自此类

> 详细的协同机制和代码示例请参阅 [[30-tutorials/game-feature/01-GameFeature是什么#四、与 Modular GamePlay 的关系|课时 1：Modular GamePlay 协同]]。

---

## 五、最佳实践速查

| 实践 | 要点 |
|------|------|
| **合理划分** | 每个 GameFeature 只负责一个独立功能，避免耦合 |
| **Experience 管理** | 通过 Experience Definition 管理，不要硬编码 |
| **异步加载** | 使用 `CallOrRegister_OnExperienceLoaded*()` 或 `UAsyncAction_ExperienceReady` |
| **Receiver 注册** | Actor 必须注册为 Receiver，`AddComponent` 才能生效 |
| **名称匹配** | GameFeatureData 名称必须与插件名称一致 |
| **AssetManager** | 必须配置 `Primary Asset Types`，否则无法加载 |

> 完整的最佳实践和常见陷阱请参阅 [[30-tutorials/game-feature/02-核心机制详解#六、最佳实践|课时 2：最佳实践]] 和 [[30-tutorials/game-feature/05-GameFeature高级主题与最佳实践#三、常见陷阱|课时 5：常见陷阱]]。

---

## 六、相关页面

- [[30-tutorials/game-feature/00-GameFeature系统从入门到实战|GameFeature 系列概览]] — 系列入口
- [[30-tutorials/game-feature/01-GameFeature是什么|课时 1：GameFeature 是什么？]]
- [[30-tutorials/game-feature/02-核心机制详解|课时 2：核心机制详解]]
- [[30-tutorials/game-feature/03-生命周期与加载流程|课时 3：生命周期与加载流程]]
- [[30-tutorials/game-feature/04-Lyra中的ExperienceSystem实践|课时 4：Lyra 中的 Experience System 实践]]
- [[30-tutorials/game-feature/05-GameFeature高级主题与最佳实践|课时 5：高级主题与最佳实践]]
- [[10-architecture/subsystems/experience-system|Experience System 架构]]
- [[10-architecture/subsystems/modular-gameplay|Modular Gameplay 架构]]

---
> 最后更新：2026-05-22（重构：去除与教程系列的重复内容，改为 wikilink 引用）

<!-- nav:auto -->

---

**导航**: [[70-topics/networking-and-synchronization|networking-and-synchronization]] →

<!-- /nav:auto -->
