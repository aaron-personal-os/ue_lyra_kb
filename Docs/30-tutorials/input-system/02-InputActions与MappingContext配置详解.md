---
id: 30-tutorials/input-system/02-InputActions与MappingContext配置详解
title: InputActions与MappingContext配置详解
description: 学会创建和配置 UInputAction、UInputMappingContext，掌握在编辑器中配置输入映射的完整工作流。
type: tutorial
status: current
language: zh
owner: ai
series: input-system
lesson_index: 2
difficulty: beginner
prerequisites: ["[[30-tutorials/input-system/01-EnhancedInput系统概览]]"]
related: ["[[30-tutorials/input-system/01-EnhancedInput系统概览]]"]
tags: [input-system, input-action, mapping-context, enhanced-input]
last_synced: 2026-05-18
engine_sources:
  - path: Plugins/EnhancedInput/Source/EnhancedInput/Public/InputAction.h
    context: UInputAction 核心类
  - path: Plugins/EnhancedInput/Source/EnhancedInput/Public/InputMappingContext.h
    context: UInputMappingContext 核心类
  - path: Plugins/EnhancedInput/Source/EnhancedInput/Public/EnhancedActionKeyMapping.h
    context: FEnhancedActionKeyMapping 映射条目
lyra_sources:
  - path: Source/LyraGame/Input/LyraInputConfig.h
    context: Lyra 输入配置数据资产
---

# InputActions与MappingContext配置详解

> 学会创建和配置 `UInputAction`、`UInputMappingContext`，掌握在编辑器中配置输入映射的完整工作流。

---

## 概述

`UInputAction` 和 `UInputMappingContext` 是 Enhanced Input 系统的两个核心**数据资产**，所有输入配置都围绕它们展开：

- **`UInputAction`** = "什么动作"（跳跃、开火、瞄准...）
- **`UInputMappingContext`** = "什么时候用这些动作"（战斗、驾驶、菜单...）

本课学完，你将能够：
1. 理解 `UInputAction` 的所有属性（`ValueType`、`Triggers`、`Modifiers`）
2. 创建 `UInputMappingContext` 并配置按键映射
3. 在 C++ 中加载并应用 `UInputMappingContext`
4. 看懂 Lyra 中 `ULyraInputConfig` 的配置方式

---

## 核心概念

### `UInputAction` —— 输入动作的抽象

**文件**：`Plugins/EnhancedInput/Source/EnhancedInput/Public/InputAction.h`

```cpp
UCLASS()
class UInputAction : public UDataAsset
{
    GENERATED_BODY()

    // [1] 动作描述（本地化文本）
    UPROPERTY(EditAnywhere, Category = "Input Action")
    FText ActionDescription;

    // [2] 值类型（决定动作输出什么类型的值）
    UPROPERTY(EditAnywhere, Category = "Input Action")
    EInputActionValueType ValueType;  // Digital / Axis1D / Axis2D / Axis3D

    // [3] 触发器数组（决定"何时触发"）
    UPROPERTY(EditAnywhere, Instanced, Category = "Input Action")
    TArray<UInputTrigger*> Triggers;

    // [4] 修饰器数组（决定"值如何被修饰"）
    UPROPERTY(EditAnywhere, Instanced, Category = "Input Action")
    TArray<UInputModifier*> Modifiers;

    // [5] 是否消费输入（阻止低优先级 Context 响应同一按键）
    UPROPERTY(EditAnywhere, Category = "Input Action")
    bool bConsumeInput = true;
};
```

**`EInputActionValueType` 枚举**（决定 C++ 中如何读取输入值）：

| 枚举值 | 输出类型 | C++ 读取方式 | 典型用途 |
|--------|---------|---------------|-----------|
| `Digital` | `bool` | `ActionValue.Get<bool>()` | 跳跃、开火（按下/释放） |
| `Axis1D` | `float` | `ActionValue.Get<float>()` | 油门、移动轴 |
| `Axis2D` | `FVector2D` | `ActionValue.Get<FVector2D>()` | 摇杆移动、鼠标位移 |
| `Axis3D` | `FVector` | `ActionValue.Get<FVector>()` | 六自由度移动（飞行） |

---

### `UInputMappingContext` —— 输入映射上下文

**文件**：`Plugins/EnhancedInput/Source/EnhancedInput/Public/InputMappingContext.h`

```cpp
UCLASS()
class UInputMappingContext : public UPrimaryDataAsset  // ← 注意：继承 UPrimaryDataAsset
{
    GENERATED_BODY()

    // [1] 上下文描述
    UPROPERTY(EditAnywhere, Category = "Context")
    FText ContextDescription;

    // [2] 默认按键映射（核心配置区）
    UPROPERTY(EditAnywhere, Category = "Context")
    TArray<FEnhancedActionKeyMapping> DefaultKeyMappings;

    // [3] 输入模式过滤（决定何时应用此上下文）
    UPROPERTY(EditAnywhere, Category = "Context")
    EMappingContextInputModeFilterOptions InputModeFilterOptions;
};
```

**关键理解**：`UInputMappingContext` 继承自 `UPrimaryDataAsset`，因此它会被 `UAssetManager` 管理生命周期——这就是 Lyra 能随 Experience 动态加载/卸载输入映射的原因。

---

### `FEnhancedActionKeyMapping` —— 单条映射记录

**文件**：`Plugins/EnhancedInput/Source/EnhancedInput/Public/EnhancedActionKeyMapping.h`

```cpp
USTRUCT()
struct FEnhancedActionKeyMapping
{
    GENERATED_BODY()

    // [1] 关联的 Input Action
    UPROPERTY(EditAnywhere, Category = "Mapping")
    TObjectPtr<UInputAction> Action;

    // [2] 映射到的按键
    UPROPERTY(EditAnywhere, Category = "Mapping")
    FKey Key;

    // [3] 此映射覆盖的 Trigger（会覆盖 Action 上的 Triggers）
    UPROPERTY(EditAnywhere, Instanced, Category = "Mapping")
    TArray<UInputTrigger*> Triggers;

    // [4] 此映射覆盖的 Modifier（会覆盖 Action 上的 Modifiers）
    UPROPERTY(EditAnywhere, Instanced, Category = "Mapping")
    TArray<UInputModifier*> Modifiers;
};
```

---

## 实战：在编辑器中创建第一个输入映射

### 步骤 1：创建 `UInputAction`

1. Content Browser 右键 → **Input → Input Action**
2. 命名为 `IA_Jump`
3. 打开 `IA_Jump`，配置：
   - **Value Type** = `Digital`
   - **Triggers** = 留空（默认使用 "Pressed" 行为）
   - **bConsumeInput** = `true`（阻止其他 Context 同时响应空格键）

### 步骤 2：创建 `UInputMappingContext`

1. Content Browser 右键 → **Input → Input Mapping Context**
2. 命名为 `IMC_Default`
3. 打开 `IMC_Default`，在 **Default Key Mappings** 中添加条目：
   - **Action** = `IA_Jump`
   - **Key** = `Space Bar`

### 步骤 3：在 C++ 中应用 `IMC_Default`

```cpp
// MyPlayerController.h
class AMyPlayerController : public ACommonPlayerController
{
    GENERATED_BODY()

protected:
    virtual void OnPossess(APawn* InPawn) override;
};

// MyPlayerController.cpp
#include "EnhancedInputComponent.h"
#include "EnhancedInputLocalPlayerSubsystem.h"
#include "InputMappingContext.h"

void AMyPlayerController::OnPossess(APawn* InPawn)
{
    Super::OnPossess(InPawn);

    // 获取 Enhanced Input Subsystem（正确方式）
    if (ULocalPlayer* LocalPlayer = GetLocalPlayer())
    {
        UEnhancedInputLocalPlayerSubsystem* Subsystem =
            LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>();

        // 加载并应用 Mapping Context（Priority = 0）
        if (UInputMappingContext* IMC = LoadObject<UInputMappingContext>(
            nullptr, TEXT("/Game/Input/Mappings/IMC_Default.IMC_Default")))
        {
            Subsystem->AddMappingContext(IMC, /*Priority=*/ 0);
        }
    }
}
```

---

## 实战：在 C++ 中绑定 Input Action

### 方式 1：`BindAction`（推荐）

```cpp
// MyPlayerController.cpp
#include "EnhancedInputComponent.h"
#include "InputAction.h"

void AMyPlayerController::SetupInputComponent()
{
    Super::SetupInputComponent();

    UEnhancedInputComponent* EnhancedIC = Cast<UEnhancedInputComponent>(InputComponent);
    check(EnhancedIC);

    // 绑定到 IA_Jump 的 Triggered 事件
    if (UInputAction* IA_Jump = LoadObject<UInputAction>(
        nullptr, TEXT("/Game/Input/Actions/IA_Jump.IA_Jump")))
    {
        EnhancedIC->BindAction(
            IA_Jump,
            ETriggerEvent::Triggered,
            this,
            &AMyPlayerController::HandleJump
        );
    }
}

void AMyPlayerController::HandleJump(const FInputActionValue& ActionValue, float ElapsedTime)
{
    // Digital 类型 → 用 Get<bool>()
    bool bPressed = ActionValue.Get<bool>();
    UE_LOG(LogTemp, Log, TEXT("Jump pressed: %s"), bPressed ? TEXT("true") : TEXT("false"));
}
```

### 方式 2：`BindActionValue`（只获取值，不绑定委托）

```cpp
// 适合需要在 Tick 中轮询输入的场景
EnhancedIC->BindActionValue(
    IA_Move,
    this,
    &AMyPlayerController::HandleMoveValue
);

void AMyPlayerController::HandleMoveValue(const FInputActionValue& ActionValue)
{
    // Axis2D 类型 → 用 Get<FVector2D>()
    FVector2D MoveInput = ActionValue.Get<FVector2D>();
    // MoveInput.X = 横向输入，MoveInput.Y = 纵向输入
}
```

---

## Lyra 实践：`ULyraInputConfig`

**文件**：`Source/LyraGame/Input/LyraInputConfig.h`

Lyra 没有直接在 C++ 中写 `BindAction`，而是用数据资产 **`ULyraInputConfig`** 把输入配置完全数据驱动：

```cpp
UCLASS()
class ULyraInputConfig : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    // [1] 原生输入动作（直接绑定到 C++ 函数）
    UPROPERTY(EditDefaultsOnly, Category = "Input")
    TArray<FLyraInputAction> NativeInputActions;

    // [2] 能力输入动作（绑定到 Gameplay Ability）
    UPROPERTY(EditDefaultsOnly, Category = "Input")
    TArray<FLyraInputAction> AbilityInputActions;
};

USTRUCT()
struct FLyraInputAction
{
    GENERATED_BODY()

    // 对应的 Input Action 资产
    UPROPERTY(EditDefaultsOnly, Category = "Input")
    TObjectPtr<UInputAction> InputAction;

    // 关联的 GameplayTag（用于路由到 GAS）
    UPROPERTY(EditDefaultsOnly, Category = "Input")
    FGameplayTag InputTag;
};
```

**设计意图**：`InputTag` 是 Lyra 输入系统的**路由枢纽**——当 `IA_Jump` 触发时，带着 `InputTag.Jump` 去找所有监听此 Tag 的 Gameplay Ability，决定激活还是取消。

---

## 常见问题与陷阱

### 陷阱 1：`IMC` 继承自 `UPrimaryDataAsset` 导致打包后加载失败

**现象**：编辑器中正常，打包后 `LoadObject<UInputMappingContext>` 返回 `nullptr`。

**原因**：`UInputMappingContext` 是 Primary Asset，需要在 `DefaultEngine.ini` 中注册：

```ini
[/Script/Engine.AssetManagerSettings]
+PrimaryAssetTypes=(PrimaryAssetType="InputMappingContext",AssetBaseClass="/Script/EnhancedInput.InputMappingContext",bHasBlueprintClasses=False,bIsEditorOnly=False,Directories=((Path="/Game/Input/Mappings")),Rules=(Priority=-1,ChunkId=-1,bApplyRecursively=True,CookRule=AlwaysCook))
```

### 陷阱 2：`Priority` 导致输入被"吞掉"

**现象**：添加了 `IMC_UI`（Priority=1）后，`IMC_Default`（Priority=0）的按键不再响应。

**原因**：`bConsumeInput = true` 时，高 Priority 的 Context 会**消费输入**，低 Priority 的 Context 收不到。

**解决**：
```cpp
// 方式 1：降低 IMC_UI 的 Priority
Subsystem->AddMappingContext(IMC_UI, /*Priority=*/ -1);

// 方式 2：在 IMC_UI 的映射中设置 bConsumeInput = false
```

### 陷阱 3：`ValueType` 与 C++ 读取方式不匹配

| ValueType | 正确读取方式 | 错误读取方式 |
|-----------|----------------|---------------|
| `Digital` | `ActionValue.Get<bool>()` | `ActionValue.Get<float>()` ❌ |
| `Axis1D` | `ActionValue.Get<float>()` | `ActionValue.Get<bool>()` ❌ |
| `Axis2D` | `ActionValue.Get<FVector2D>()` | `ActionValue.Get<FVector>()` ❌ |

---

## 总结

| 要点 | 说明 |
|------|------|
| `UInputAction` | "什么动作"——定义值类型、触发器、修饰器 |
| `UInputMappingContext` | "何时用"——持有按键映射列表，可动态加载/卸载 |
| `Priority` | 数字越大越先响应，高 Priority 可消费输入 |
| `ULyraInputConfig` | Lyra 的数据驱动输入配置，通过 `InputTag` 路由到 GAS |
| 绑定方式 | `BindAction(Action, TriggerEvent, Object, Method)` |

---

## 相关页面

- [[30-tutorials/input-system/01-EnhancedInput系统概览|← 01 Enhanced Input 概览]]
- [[30-tutorials/input-system/03-Trigger与Modifier详解|03 Trigger 与 Modifier →]]
- [[30-tutorials/gas/01-GA简介与配置|GAS 系列（理解 InputTag 的前置知识）]]

<!-- nav:auto -->

---

**导航**: ← [[30-tutorials/input-system/01-EnhancedInput系统概览|01-EnhancedInput系统概览]] · [[30-tutorials/input-system/03-Trigger与Modifier详解|03-Trigger与Modifier详解]] →

<!-- /nav:auto -->
