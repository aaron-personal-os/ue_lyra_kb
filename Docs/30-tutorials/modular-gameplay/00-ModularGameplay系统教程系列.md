---
id: 30-tutorials/modular-gameplay/00-ModularGameplay系统教程系列
title: ModularGameplay系统教程系列
description: "UE5 模块化游戏架构：用组件组合替代深层继承，让游戏功能像\"搭积木\"一样灵活组装。"
type: guide
status: current
language: zh
owner: ai
series: modular-gameplay
lesson_index: 0
difficulty: beginner
prerequisites: []
related:
  - [[30-tutorials/modular-gameplay/01-ModularGameplay是什么]]
  - [[30-tutorials/lyra-practical/02-ExperienceSystem详解]]
  - [[30-tutorials/game-feature/00-GameFeature系统从入门到实战]]
  - "[[30-tutorials/lyra-practical/00-Lyra项目架构与实战]]"
  - "[[10-architecture/subsystems/experience-system]]"
  - "[[10-architecture/subsystems/modular-gameplay]]"
tags: [modular-gameplay, overview, tutorial]
last_synced: 2026-05-17
last_verified: 2026-05-22
---

# ModularGameplay系统教程系列

> **UE5 模块化游戏架构**：用组件组合替代深层继承，让游戏功能像"搭积木"一样灵活组装。

## 系列概述

本系列将带你深入理解 UE5 的 **Modular Gameplay（模块化游戏玩法）** 架构：

| 核心价值 | 说明 |
|---------|------|
| **组合优于继承** | 用组件组合替代 `A → B → C → D` 的深层继承链 |
| **功能解耦** | 每个功能模块独立开发、测试、维护 |
| **动态组装** | 运行时通过 Experience 系统动态加载/卸载功能 |

### 你会学到什么

1. **Modular Gameplay 是什么** — 设计理念、与传统继承的对比
2. **核心类详解** — ModularCharacter、ModularGameMode、ModularGameState、PawnComponent
3. **组件生命周期** — 从注册到注销的完整流程
4. **Lyra 实战** — 看 Lyra 如何用 Modular Gameplay 构建可扩展的角色系统
5. **高级主题** — 自定义组件、最佳实践、性能优化

## 核心概念全景图

```mermaid
graph TB
    A[Modular Gameplay 架构] --> B[ModularCharacter]
    A --> C[ModularGameMode]
    A --> D[ModularGameState]
    
    B --> B1[PawnComponent]
    B1 --> B1a[ULyraPawnExtensionComponent]
    B1 --> B1b[ULyraHealthComponent]
    B1 --> B1c[ULyraCameraComponent]
    B1 --> B1d[ULyraHeroComponent]
    
    C --> C1[GameModeComponent]
    C1 --> C1a[自定义 GameMode 组件]
    
    D --> D1[GameStateComponent]
    D1 --> D1a[ULyraExperienceManagerComponent]
    
    A --> E[GameFeatureAction]
    E --> E1[AddComponents]
    E --> E2[AddAbilities]
    E --> E3[AddInputConfig]
    
    style A fill:#e1f5fe
    style B1 fill:#fff9c4
    style C1 fill:#fff9c4
    style D1 fill:#fff9c4
```

## 与 Lyra 项目的关系

Lyra 是 Modular Gameplay 的**最佳实践范例**：

```mermaid
flowchart TD
    subgraph ALyraCharacter ["ALyraCharacter (继承自 AModularCharacter)"]
        direction TD
        C1["ULyraPawnExtensionComponent<br/>(基础扩展)"]
        C2["ULyraHealthComponent<br/>(生命值)"]
        C3["ULyraCameraComponent<br/>(相机)"]
        C4["ULyraHeroComponent<br/>(英雄功能)"]
        C5["ULyraEquipmentManagerComponent<br/>(装备管理)"]
        C6["ULyraInventoryManagerComponent<br/>(库存管理)"]
    end
    
    ALyraCharacter ==> |"Experience 系统<br/>动态组装"| Experiences
    
    subgraph Experiences ["Experience 系统"]
        direction TD
        E1["ShooterCore Experience<br/>• 加载 ShooterCore GameFeature<br/>• 添加射击相关组件"]
        E2["TopDownArena Experience<br/>• 加载 TopDown GameFeature<br/>• 添加俯视角相关组件"]
    end
    
    style ALyraCharacter fill:#e3f2fd,stroke:#1976d2,color:#000
    style Experiences fill:#e8f5e9,stroke:#388e3c,color:#000
```

## 系列阅读指南

### 学习路径

```mermaid
flowchart LR
    A[00-overview] --> B[01-what-is]
    B --> C[02-core-classes]
    C --> D[03-lifecycle]
    D --> E[04-lyra-practice]
    E --> F[05-advanced]
    
    style A fill:#e1f5fe
    style F fill:#f9f,stroke:#333
```

### 课时导航

| 课时 | 标题 | 难度 | 核心内容 |
|------|------|------|----------|
| 00 | [系列概览](00-ModularGameplay系统教程系列.md) | 入门 | 系列导航、核心概念全景图 |
| 01 | [Modular Gameplay 是什么？](01-ModularGameplay是什么.md) | 入门 | 设计理念、与传统继承对比 |
| 02 | [核心类详解](02-核心类详解.md) | 中级 | ModularCharacter/GameMode/GameState |
| 03 | [组件生命周期](03-组件生命周期.md) | 中级 | 注册、初始化、回调、注销 |
| 04 | [Lyra 实战](04-Lyra实战.md) | 中高级 | Lyra 角色架构、Experience 集成 |
| 05 | [高级主题](05-ModularGameplay高级主题与最佳实践.md) | 高级 | 自定义组件、最佳实践、性能优化 |

### 前置知识

| 知识点 | 推荐教程 | 重要程度 |
|--------|----------|----------|
| Actor 与组件系统 | `30-tutorials/ue-framework/02-actor-and-component` | ⭐⭐⭐ |
| GameMode/GameState | `30-tutorials/ue-framework/05-game-framework` | ⭐⭐⭐ |
| GameFeature 系统 | `30-tutorials/game-feature/00-overview` | ⭐⭐ |
| 面向对象设计原则 | 外部资源 | ⭐⭐ |

## 相关页面

- [[30-tutorials/modular-gameplay/01-ModularGameplay是什么]] - Modular Gameplay 架构文档
- [[30-tutorials/lyra-practical/02-ExperienceSystem详解]] - Experience 系统（动态加载 Modular Gameplay）
- [[30-tutorials/game-feature/00-GameFeature系统从入门到实战]] - GameFeature 教程系列（协同工作）

---

> 建议从 **[01-ModularGameplay是什么](01-ModularGameplay是什么.md)** 开始学习。

<!-- nav:auto -->

---

**导航**: [[30-tutorials/modular-gameplay/01-ModularGameplay是什么|01-ModularGameplay是什么]] →

<!-- /nav:auto -->
