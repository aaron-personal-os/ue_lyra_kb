---
id: 30-tutorials/modular-gameplay/01-ModularGameplay是什么
title: ModularGameplay是什么
description: "一句话概括：把游戏功能拆成一个个可插拔的\"组件\"，像搭积木一样组装角色和游戏逻辑。"
type: tutorial
status: current
language: zh
owner: ai
series: modular-gameplay
lesson_index: 1
difficulty: beginner
prerequisites: ["[[30-tutorials/ue-framework/40-actor-system/00-AActor架构概述]]"]
related:
  - [[30-tutorials/modular-gameplay/00-ModularGameplay系统教程系列]]
  - [[30-tutorials/game-feature/01-GameFeature是什么]]
  - "[[30-tutorials/game-feature/00-GameFeature系统从入门到实战]]"
  - "[[30-tutorials/lyra-practical/02-ExperienceSystem详解]]"
  - "[[30-tutorials/lyra-practical/03-GameFeature与ModularGameplay模块化架构]]"
  - "[[30-tutorials/modular-gameplay/03-组件生命周期]]"
  - "[[30-tutorials/modular-gameplay/04-Lyra实战]]"
  - "[[30-tutorials/modular-gameplay/05-ModularGameplay高级主题与最佳实践]]"
  - "[[30-tutorials/performance-optimization/06-Lyra性能实战]]"
  - "[[10-architecture/subsystems/modular-gameplay]]"
tags: [modular-gameplay, component, architecture]
last_synced: 2026-05-17
last_verified: 2026-05-22
engine_sources:
  - path: Engine/Source/Runtime/ModularGameplay/Public/Components/PawnComponent.h
    description: UPawnComponent 类定义
  - path: Engine/Source/Runtime/ModularGameplay/Public/GameFramework/ModularCharacter.h
    description: AModularCharacter 类定义
lyra_sources:
  - path: Source/LyraGame/Character/LyraCharacter.h
    description: ALyraCharacter 类定义（继承 AModularCharacter）
---

# ModularGameplay是什么

> **一句话概括**：把游戏功能拆成一个个可插拔的"组件"，像搭积木一样组装角色和游戏逻辑。

## 本课目标

学完这篇，你将能够：
1. 理解 **为什么需要 Modular Gameplay**（传统继承的痛点）
2. 掌握 **Modular Gameplay 的核心思想**（组合优于继承）
3. 对比 **传统方式 vs 模块化方式** 的差异
4. 了解 **Modular Gameplay 在 UE5 中的位置**

---

## 1. 传统继承的痛点

### 1.1 问题：继承链越来越深

假设你要做一个多人在线射击游戏，角色有多种能力：

```mermaid
classDiagram
    class ACharacter {
        <<UE 基类>>
    }
    class ALyraCharacter {
        <<Lyra 基础角色>>
    }
    class ALyraHero {
        <<英雄角色，有 GAS>>
    }
    class ALyraSoldier {
        <<士兵，能射击>>
    }
    class ALyraJetpack {
        <<有喷气包的士兵>>
    }
    class ALyraStealth {
        <<隐身士兵>>
    }
    
    ACharacter <|-- ALyraCharacter : 继承
    ALyraCharacter <|-- ALyraHero : 继承
    ALyraHero <|-- ALyraSoldier : 继承
    ALyraSoldier <|-- ALyraJetpack : 继承
    ALyraSoldier <|-- ALyraStealth : 继承
    
    note for ACharacter "❌ 传统继承方式的问题：\n• 类爆炸：每新增一个能力组合，就要新建一个子类\n• 代码重复：喷气包功能在多个子类中重复\n• 难以维护：修改基础类可能影响所有子类\n• 无法动态切换：运行时无法给角色'加装'喷气包"
    style ACharacter fill:#ffebee,stroke:#c62828
    style ALyraCharacter fill:#fff3e0,stroke:#e65100
    style ALyraHero fill:#e8f5e9,stroke:#2e7d32
    style ALyraSoldier fill:#e3f2fd,stroke:#1565c0
    style ALyraJetpack fill:#f3e5f5,stroke:#6a1b9a
    style ALyraStealth fill:#fce4ec,stroke:#ad1457
```

**痛点**：
| 问题 | 说明 |
|------|------|
| **类爆炸** | 每新增一个能力组合，就要新建一个子类 |
| **代码重复** | 喷气包功能在 `ALyraJetpack` 和 `ALyraStealthJetpack` 中重复 |
| **难以维护** | 修改基础类可能影响所有子类 |
| **无法动态切换** | 运行时无法给角色"加装"喷气包 |

### 1.2 现实类比：乐高 vs 雕刻

| | 传统继承 | Modular Gameplay |
|--|----------|-----------------|
| **类比** | 雕刻（一刀下去改不了） | 乐高（随时拆装） |
| **扩展方式** | 新建子类 | 添加/移除组件 |
| **灵活性** | 编译时固定 | 运行时动态组装 |

---

## 2. Modular Gameplay 的核心思想

### 2.1 设计原则：组合优于继承

```mermaid
graph LR
    A[Modular Gameplay] --> B[组合优于继承]
    A --> C[功能解耦]
    A --> D[动态组装]
    
    B --> B1[组件 = 功能单元]
    B --> B2[运行时可插拔]
    
    C --> C1[独立开发]
    C --> C2[独立测试]
    C --> C3[独立维护]
    
    D --> D1[Experience 系统]
    D --> D2[GameFeature 加载]
    
    style A fill:#e1f5fe
    style B fill:#fff9c4
    style C fill:#fff9c4
    style D fill:#fff9c4
```

### 2.2 核心类一览

UE5 的 Modular Gameplay 提供了以下基类：

| 基类 | 作用 | Lyra 中的使用 |
|------|------|---------------|
| `AModularCharacter` | 模块化的 Character | `ALyraCharacter` 继承自它 |
| `AModularPlayerState` | 模块化的 PlayerState | Lyra 使用 |
| `AModularGameState` | 模块化的 GameState | `ALyraGameState` 继承自它 |
| `AModularGameModeBase` | 模块化的 GameMode | `ALyraGameMode` 继承自它 |
| `UPawnComponent` | Pawn 组件基类 | `ULyraPawnExtensionComponent` 等 |
| `UGameStateComponent` | GameState 组件基类 | `ULyraExperienceManagerComponent` |

### 2.3 组件类型

```mermaid
classDiagram
    class AActor {
        +TArray~UActorComponent~ Components
    }
    
    class AModularCharacter {
        +GetPawnComponents()
        +RegisterPawnComponent()
        +UnregisterPawnComponent()
    }
    
    class UPawnComponent {
        +GetPawn()
        +HandleControllerChanged()
        +HandlePlayerStateChanged()
    }
    
    class UGameStateComponent {
        +GetGameState()
    }
    
    AActor <|-- AModularCharacter
    AActor <|-- AModularGameState
    UActorComponent <|-- UPawnComponent
    UActorComponent <|-- UGameStateComponent
    
    AModularCharacter --> UPawnComponent : 包含
    AModularGameState --> UGameStateComponent : 包含
```

---

## 3. 实例对比：传统 vs 模块化

### 3.1 场景：给角色添加"喷气包"功能

#### 传统继承方式（❌）

```cpp
// 方案 1：修改 ALyraCharacter（影响所有角色）
class ALyraCharacter : public ACharacter {
    UPROPERTY()
    UJetpackComponent* Jetpack;  // 所有角色都有喷气包？❌
};

// 方案 2：新建子类（类爆炸）
class ALyraCharacterWithJetpack : public ALyraCharacter {
    // 只有这个子类有喷气包
    // 但如果要"隐身+喷气包"又要新建一个类...
};
```

#### Modular Gameplay 方式（✅）

```cpp
// 1. 定义喷气包组件（一次定义，到处使用）
UCLASS()
class UJetpackComponent : public UPawnComponent {
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable)
    void ActivateJetpack();
    
    UFUNCTION(BlueprintCallable)
    void DeactivateJetpack();
};

// 2. 需要喷气包的角色：添加组件即可
ALyraCharacter* Hero = Cast<ALyraCharacter>(GetPawn());
UJetpackComponent* Jetpack = NewObject<UJetpackComponent>(Hero);
Hero->RegisterPawnComponent(Jetpack);  // 运行时动态添加！

// 3. 不需要时移除
Hero->UnregisterPawnComponent(Jetpack);  // 动态移除
```

### 3.2 在 Lyra 中的实际应用

Lyra 的角色系统完全基于 Modular Gameplay：

```mermaid
graph TB
    A[ALyraCharacter] --> B[ULyraPawnExtensionComponent]
    A --> C[ULyraHealthComponent]
    A --> D[ULyraCameraComponent]
    A --> E[ULyraHeroComponent]
    A --> F[ULyraEquipmentManagerComponent]
    
    B --> B1[基础扩展：初始化、输入绑定]
    C --> C1[生命值管理]
    D --> D1[相机控制]
    E --> E1[英雄特有功能]
    F --> F1[装备管理]
    
    style A fill:#e1f5fe
    style B fill:#fff9c4
    style C fill:#fff9c4
    style D fill:#fff9c4
```

**优势体现**：
- `ULyraHealthComponent` 可以在任何 Pawn 上复用
- `ULyraCameraComponent` 可以根据 Experience 动态加载
- 新增功能只需写新组件，不影响现有代码

---

## 4. Modular Gameplay 在 UE5 架构中的位置

### 4.1 与 GameFeature 的关系

```mermaid
graph LR
    A[GameFeature] -->|激活时| B[加载 GameFeatureData]
    B --> C[执行 GameFeatureActions]
    C --> D[AddComponents Action]
    D --> E[注册组件到 Actor]
    E --> F[Modular Gameplay 生效]
    
    style A fill:#e1f5fe
    style F fill:#f9f,stroke:#333
```

**分工**：
| 系统 | 职责 |
|------|------|
| **GameFeature** | 管理功能的"加载/卸载"生命周期 |
| **Modular Gameplay** | 提供"组件"作为功能载体 |
| **Experience System** | 定义"当前游戏需要哪些 GameFeatures" |

### 4.2 在 Lyra 中的完整流程

```
1. 玩家选择 Experience（如 ShooterCore）
   ↓
2. Experience 定义需要加载的 GameFeatures
   ↓
3. GameFeature 激活，执行 Actions
   ↓
4. AddComponents Action 注册组件到 Character/GameState
   ↓
5. Modular Gameplay 接管组件生命周期
   ↓
6. 玩家获得完整游戏功能
```

---

## 5. 总结与要点

### 核心要点

1. **Modular Gameplay = 组件组合架构**
   - 替代深层继承链
   - 功能解耦，易于维护

2. **核心类**
   - `AModularCharacter` — 可附加 Pawn 组件的 Character
   - `UPawnComponent` — Pawn 组件基类
   - `UGameStateComponent` — GameState 组件基类

3. **与传统方式对比**
   - 传统：继承链深、类爆炸、难以维护
   - 模块化：组件复用、动态组装、易于扩展

4. **与 GameFeature 协同**
   - GameFeature 负责"加载/卸载"
   - Modular Gameplay 负责"组件生命周期"

### 下一步

下一课 **[02-核心类详解](02-核心类详解.md)** 将深入学习 Modular Gameplay 的核心类。

## 相关页面

- [[30-tutorials/modular-gameplay/01-ModularGameplay是什么]] - Modular Gameplay 架构文档
- [[30-tutorials/game-feature/02-核心机制详解]] - GameFeature 核心机制
- [[30-tutorials/ue-framework/40-actor-system/00-AActor架构概述]] - AActor 架构概述

---

> 下一课：**[02-核心类详解](02-核心类详解.md) — 核心类详解**

<!-- nav:auto -->

---

**导航**: ← [[30-tutorials/modular-gameplay/00-ModularGameplay系统教程系列|00-ModularGameplay系统教程系列]] · [[30-tutorials/modular-gameplay/02-核心类详解|02-核心类详解]] →

<!-- /nav:auto -->
