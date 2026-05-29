---
id: 30-tutorials/ue-framework/30-gamemode-layer/00-AGameModeBase详解
title: AGameModeBase详解
description: AGameModeBase 是游戏规则的制定者，负责管理游戏的逻辑规则（如玩家加入/退出、暂停、关卡切换等）。每个 UWorld 有且仅有一个 GameMode。AGameMode 是 AGameModeBase 的子类，增加了队友伤害、友军伤害等默认实现。
type: tutorial
status: current
language: zh
owner: ai
series: ue-framework
lesson_index: 300
difficulty: intermediate
prerequisites: [30-tutorials/ue-framework/20-world-layer/01-level]
anchors:
  - path: LyraStarterGame.uproject
related:
  - [[30-tutorials/ue-framework/20-world-layer/00-UWorld详解]]
  - [[30-tutorials/ue-framework/30-gamemode-layer/01-AGameStateBase详解]]
  - [[30-tutorials/ue-framework/20-world-layer/01-ULevel与LevelStreaming详解]]
tags: [AGameModeBase, AGameMode, GameMode, 游戏模式]
last_synced: 2026-05-16
last_verified: 2026-05-16
---

# AGameModeBase详解

## 概述

> `AGameModeBase` 是游戏规则的制定者，负责管理游戏的逻辑规则（如玩家加入/退出、暂停、关卡切换等）。每个 `UWorld` 有且仅有一个 `GameMode`。`AGameMode` 是 `AGameModeBase` 的子类，增加了队友伤害、友军伤害等默认实现。

---

## 核心概念

### GameMode 的职责

`AGameModeBase` 是游戏逻辑的总控，负责管理：

```mermaid
graph TD
    GM["AGameModeBase"]
    
    GM --> GS["GameState<br/>游戏状态"]
    GM --> PC["PlayerController<br/>玩家控制器"]
    GM --> PS["PlayerState<br/>玩家状态"]
    GM --> GMSC["GameSession<br/>游戏会话"]
    GM --> P["DefaultPawn<br/>默认 Pawn"]
    
    style GM fill:#ff9800
    style GS fill:#e1f5fe
    style PC fill:#f3e5f5
    style PS fill:#e8f5e9
    style GMSC fill:#fff3e0
    style P fill:#fce4ec
```

**核心职责**：
1. **游戏规则管理**：定义游戏的规则（如胜利条件、失败条件）
2. **玩家管理**：处理玩家加入/退出（Login/PostLogin）
3. **GameState 管理**：创建和管理 `GameState`
4. **Pawn 管理**：生成默认 Pawn（SpawnDefaultPawnAtTransform）
5. **游戏流程管理**：控制游戏开始/暂停/结束（StartMatch/SetGamePaused）

### GameMode 与 GameState 的关系

```mermaid
classDiagram
    class AGameModeBase {
        +GameStateClass: TSubclassOf~AGameStateBase~
        +PlayerControllerClass: TSubclassOf~APlayerController~
        +DefaultPawnClass: TSubclassOf~APawn~
        +PlayerStateClass: TSubclassOf~APlayerState~
        +InitGame()
        +Login()
        +PostLogin()
        +StartPlay()
        +StartMatch()
        +SetGamePaused()
    }
    
    class AGameStateBase {
        +PlayerArray: TArray~APlayerState*~
        +MatchState: FName
        +OnRep_MatchState()
    }
    
    AGameModeBase --> AGameStateBase : Creates
    AGameModeBase --> APlayerController : Creates
    AGameModeBase --> APlayerState : Creates
    AGameStateBase --> APlayerState : References
```

**关系说明**：
- `AGameModeBase` 创建 `AGameStateBase`（在 `InitGame()` 中）
- `AGameModeBase` 创建 `APlayerController`（在 `Login()` 中）
- `AGameModeBase` 创建 `APlayerState`（在 `PostLogin()` 中）
- `AGameStateBase` 引用所有 `APlayerState`（通过 `PlayerArray`）

---

## 架构解析

### AGameModeBase 类继承关系

```mermaid
classDiagram
    class AActor {
        +BeginPlay()
        +Tick()
        +SetOwner()
    }
    
    class AInfo {
        +AActor
    }
    
    class AGameModeBase {
        +GameStateClass: TSubclassOf~AGameStateBase~
        +PlayerControllerClass: TSubclassOf~APlayerController~
        +DefaultPawnClass: TSubclassOf~APawn~
        +PlayerStateClass: TSubclassOf~APlayerState~
        +SpectatorClass: TSubclassOf~ASpectatorPawn~
        +GameSessionClass: TSubclassOf~AGameSession~
        +GameState: AGameStateBase*
        +InitGame()
        +PreInitializeComponents()
        +StartPlay()
        +Login()
        +PostLogin()
        +HandleStartingNewPlayer()
        +StartMatch()
        +EndMatch()
        +SetGamePaused()
        +RestartPlayer()
        +SpawnDefaultPawnAtTransform()
    }
    
    AActor <|-- AInfo
    AInfo <|-- AGameModeBase
    
    AGameModeBase --> AGameStateBase : Creates
    AGameModeBase --> APlayerController : Creates
    AGameModeBase --> APawn : Creates
```

### AGameMode 类继承关系

```mermaid
classDiagram
    class AGameModeBase {
        +GameStateClass
        +PlayerControllerClass
        +InitGame()
        +Login()
    }
    
    class AGameMode {
        +bUseSeamlessTravel: bool
        +DefaultPlayerName: FString
        +SetGamePaused()
        +RestartPlayer()
        +CanPlayerRestart()
        +GetDefaultPlayerName()
    }
    
    AGameModeBase <|-- AGameMode
    
    AGameMode --> AGameState : Uses
```

### 关键方法详解

#### InitGame() - 初始化游戏

**功能**：初始化游戏，创建 `GameState` 和 `GameSession`。

**执行流程**：

```mermaid
sequenceDiagram
    participant World as UWorld
    participant GM as AGameModeBase
    participant GS as AGameStateBase
    participant GSession as AGameSession
    
    World->>GM: InitGame(Options, ErrorMessage)
    GM->>GS: SpawnActor<AGameStateBase>(GameStateClass)
    GM->>GSession: SpawnActor<AGameSession>(GameSessionClass)
    GM->>GM: PreInitializeComponents()
    GM-->>World: 返回
```

**关键代码**：

```cpp
void AGameModeBase::InitGame(const FString& Options, FString& ErrorMessage)
{
    // 创建 GameState
    GameState = GetWorld()->SpawnActor<AGameStateBase>(GameStateClass);
    
    // 创建 GameSession
    GameSession = GetWorld()->SpawnActor<AGameSession>(GameSessionClass);
    
    // 预初始化组件
    PreInitializeComponents();
}
```

#### Login() - 玩家登录

**功能**：处理玩家登录请求，创建 `PlayerController`。

**执行流程**：

```mermaid
sequenceDiagram
    participant PC as APlayerController
    participant GM as AGameModeBase
    participant NewPC as New APlayerController
    participant PS as APlayerState
    
    PC->>GM: Login(Options, ErrorMessage)
    GM->>NewPC: SpawnActor<APlayerController>(PlayerControllerClass)
    NewPC->>PS: NewObject<APlayerState>(PlayerStateClass)
    PS->>PS: InitPlayerState()
    NewPC->>NewPC: OnRep_PlayerState()
    GM-->>PC: 返回 NewPC
```

**关键代码**：

```cpp
APlayerController* AGameModeBase::Login(const FString& Options, const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage)
{
    // 创建 PlayerController
    APlayerController* NewPlayerController = GetWorld()->SpawnActor<APlayerController>(PlayerControllerClass);
    
    // 创建 PlayerState
    NewPlayerController->PlayerState = NewObject<APlayerState>(PlayerStateClass);
    NewPlayerController->PlayerState->InitPlayerState();
    
    return NewPlayerController;
}
```

#### PostLogin() - 登录后处理

**功能**：在玩家登录后调用，将 `PlayerState` 添加到 `GameState`。

**执行流程**：

```mermaid
sequenceDiagram
    participant GM as AGameModeBase
    participant GS as AGameStateBase
    participant PC as APlayerController
    participant PS as APlayerState
    
    GM->>GS: AddPlayerState(PC->PlayerState)
    GS->>GS: PlayerArray.Add(PS)
    GM->>PC: HandleStartingNewPlayer()
    PC->>PC: SpawnDefaultPawn()
    GM-->>GM: 返回
```

**关键代码**：

```cpp
void AGameModeBase::PostLogin(APlayerController* NewPlayer)
{
    // 将 PlayerState 添加到 GameState
    AGameStateBase* GameState = GetGameState<AGameStateBase>();
    GameState->AddPlayerState(NewPlayer->PlayerState);
    
    // 处理新玩家（生成 Pawn）
    HandleStartingNewPlayer(NewPlayer);
}
```

#### StartPlay() - 开始游戏

**功能**：开始游戏，调用 `StartMatch()`。

**执行流程**：

```mermaid
sequenceDiagram
    participant World as UWorld
    participant GM as AGameModeBase
    participant GS as AGameStateBase
    
    World->>GM: StartPlay()
    GM->>GS: SetMatchState(Playing)
    GM->>GM: StartMatch()
    GM-->>World: 返回
```

**关键代码**：

```cpp
void AGameModeBase::StartPlay()
{
    // 设置 MatchState 为 Playing
    AGameStateBase* GameState = GetGameState<AGameStateBase>();
    GameState->SetMatchState(MatchState::Playing);
    
    // 开始比赛
    StartMatch();
}
```

#### StartMatch() - 开始比赛

**功能**：开始比赛，通知所有客户端。

**关键代码**：

```cpp
void AGameModeBase::StartMatch()
{
    // 通知所有 PlayerController 比赛开始
    for (FConstPlayerControllerIterator It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
    {
        APlayerController* PC = It->Get();
        PC->ClientStartMatch();
    }
}
```

---

## 执行流程

### GameMode 完整生命周期

```mermaid
stateDiagram-v2
    [*] --> Created: SpawnActor<AGameModeBase>()
    Created --> Initialized: InitGame()
    Initialized --> Playing: StartPlay()
    Playing --> Paused: SetGamePaused(true)
    Paused --> Playing: SetGamePaused(false)
    Playing --> Finished: EndMatch()
    Finished --> [*]: 销毁
    
    note right of Created
        - 创建 GameMode 对象
        - 设置 GameStateClass
        - 设置 PlayerControllerClass
    end note
    
    note right of Initialized
        - 创建 GameState
        - 创建 GameSession
        - 预初始化组件
    end note
    
    note right of Playing
        - 设置 MatchState 为 Playing
        - 开始比赛
        - Tick 驱动
    end note
    
    note right of Paused
        - 设置 GamePaused = true
        - 暂停游戏逻辑
    end note
    
    note right of Finished
        - 设置 MatchState 为 Finished
        - 结束比赛
        - 清理资源
    end note
```

### Login → PostLogin 流程

```mermaid
sequenceDiagram
    participant World as UWorld
    participant GM as AGameModeBase
    participant PC as APlayerController
    participant GS as AGameStateBase
    participant PS as APlayerState
    participant Pawn as APawn
    
    World->>GM: Login(Options)
    GM->>PC: SpawnActor<APlayerController>()
    PC->>PS: NewObject<APlayerState>()
    PS->>PS: InitPlayerState()
    GM-->>World: 返回 PC
    
    World->>GM: PostLogin(PC)
    GM->>GS: AddPlayerState(PS)
    GS->>GS: PlayerArray.Add(PS)
    GM->>PC: HandleStartingNewPlayer()
    PC->>Pawn: SpawnDefaultPawn()
    Pawn->>PC: Possess(Pawn)
```

### 玩家加入完整流程

```mermaid
sequenceDiagram
    participant LP as ULocalPlayer
    participant World as UWorld
    participant GM as AGameModeBase
    participant PC as APlayerController
    participant GS as AGameStateBase
    participant Pawn as APawn
    
    LP->>World: SpawnPlayActor()
    World->>GM: Login()
    GM->>PC: SpawnActor<APlayerController>()
    PC->>PC: InitPlayerState()
    World->>GM: PostLogin(PC)
    GM->>GS: AddPlayerState(PC->PlayerState)
    GM->>PC: HandleStartingNewPlayer()
    PC->>Pawn: SpawnDefaultPawnAtTransform()
    PC->>PC: Possess(Pawn)
    World->>World: BeginPlay()
```

---

## 与其他模块的关系

`AGameModeBase` 作为游戏逻辑的总控，与以下系统紧密相关：

```mermaid
graph TD
    GM["AGameModeBase<br/>(本文档)"]
    World["UWorld<br/>(20-world-layer/00-world)"]
    GS["AGameStateBase<br/>(30-gamemode-layer/01-gamestate)"]
    PC["APlayerController<br/>(50-player-system/01-controller)"]
    PS["APlayerState<br/>(50-player-system/02-playerstate)"]
    Pawn["APawn<br/>(50-player-system/00-pawn)"]
    GSession["AGameSession"]
    
    World -->|Creates| GM
    GM -->|Creates| GS
    GM -->|Creates| PC
    GM -->|Creates| PS
    GM -->|Creates| Pawn
    GM -->|Creates| GSession
    
    style GM fill:#ff9800,stroke:#333,stroke-width:4px
    style World fill:#e1f5fe
    style GS fill:#f3e5f5
    style PC fill:#e8f5e9
    style PS fill:#fff3e0
    style Pawn fill:#fce4ec
    style GSession fill:#e0f7fa
```

**关系说明**：

| 相关模块 | 关系 | 说明 |
|----------|------|------|
| **UWorld** | 创建 GameMode | `UWorld::SetGameMode()` 中创建 `GameMode` |
| **AGameStateBase** | 被 GameMode 创建 | `AGameModeBase::InitGame()` 中创建 `GameState` |
| **APlayerController** | 被 GameMode 创建 | `AGameModeBase::Login()` 中创建 `PlayerController` |
| **APlayerState** | 被 GameMode 创建 | `AGameModeBase::Login()` 中创建 `PlayerState` |
| **APawn** | 被 GameMode 创建 | `AGameModeBase::SpawnDefaultPawnAtTransform()` 中创建 `Pawn` |
| **AGameSession** | 被 GameMode 创建 | `AGameModeBase::InitGame()` 中创建 `GameSession` |

---

## 常见陷阱与最佳实践

### ⚠️ 常见陷阱

1. **在错误的时机访问 GameMode**
   - ❌ 错误：在 `UWorld::InitializeNewWorld()` 中尝试访问 `GameMode`
   - ✅ 正确：`GameMode` 在 `UWorld::SetGameMode()` 中创建，只能在之后访问

2. **不理解 GameMode 的生命周期**
   - ❌ 错误：认为 `GameMode` 会在 World 切换时销毁
   - ✅ 正确：`GameMode` 在 `World` 销毁时销毁

3. **混淆 GameMode 和 GameState**
   - ❌ 错误：在 `GameMode` 中存储需要复制的状态
   - ✅ 正确：`GameMode` 只在服务器存在，`GameState` 会复制到所有客户端

### ✅ 最佳实践

1. **使用 GameMode 管理游戏规则**
   - 游戏规则（如胜利条件、失败条件） → 放在 `GameMode` 中
   - 游戏状态（如当前分数、玩家列表） → 放在 `GameState` 中

2. **使用 GameState 同步游戏状态**
   - 需要同步到所有客户端的状态 → 放在 `GameState` 中
   - 使用 `UPROPERTY(Replicated)` 标记需要复制的属性

3. **理解 Login → PostLogin 流程**
   - 玩家加入 → `Login()` 创建 `PlayerController` 和 `PlayerState`
   - 登录后 → `PostLogin()` 将 `PlayerState` 添加到 `GameState`，生成 `Pawn`

---

## 参考资料

### UE 官方文档
- [UE5 官方文档](https://docs.unrealengine.com/5.0/zh-CN/)
- [GameMode 官方文档](https://docs.unrealengine.com/5.0/zh-CN/gamemode-in-unreal-engine/)
- [GameState 官方文档](https://docs.unrealengine.com/5.0/zh-CN/gamestate-in-unreal-engine/)

### 内部文档
- [[30-tutorials/ue-framework/00-UE框架概述|UE 框架概述]]
- [[30-tutorials/ue-framework/01-UE游戏主循环详解|游戏主循环详解]]
- [[30-tutorials/ue-framework/20-world-layer/00-UWorld详解|UWorld 详解]]
- [[30-tutorials/ue-framework/30-gamemode-layer/01-AGameStateBase详解|AGameStateBase 详解]]

### 原文档
- 

---

**文档版本**：v1.0  
**最后更新**：2026-05-16  
**维护者**：AI Agent（按项目规范维护）

<!-- nav:auto -->

---

**导航**: ← [[30-tutorials/ue-framework/20-world-layer/01-ULevel与LevelStreaming详解|01-ULevel与LevelStreaming详解]] · [[30-tutorials/ue-framework/30-gamemode-layer/01-AGameStateBase详解|01-AGameStateBase详解]] →

<!-- /nav:auto -->
