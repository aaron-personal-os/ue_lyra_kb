---
id: 30-tutorials/garbage-collection/04-UObject生命周期与GC交互
title: UObject生命周期与GC交互
description: 深入理解 UObject 从创建到销毁的完整生命周期，以及与 GC 的交互时机。
type: tutorial
status: current
language: zh
owner: ai
series: garbage-collection
lesson_index: 4
difficulty: intermediate
prerequisites: ["[[30-tutorials/garbage-collection/03-引用类型系统]]"]
related:
  - [[30-tutorials/garbage-collection/03-引用类型系统]]
  - [[30-tutorials/ue-framework/40-actor-system/01-AActor完整生命周期]]
tags: [gc, uobject, lifecycle, destroy, begin-destroy]
last_synced: 2026-05-17
engine_sources:
  - path: Engine/Source/Runtime/CoreUObject/Private/UObject/Object.cpp
    context: UObject::ConditionalBeginDestroy() 和销毁流程
  - path: Engine/Source/Runtime/CoreUObject/Public/UObject/Object.h
    context: UObject 生命周期相关方法声明
lyra_sources: []
---

# UObject生命周期与GC交互

> 深入理解 UObject 从创建到销毁的完整生命周期，以及与 GC 的交互时机。

## 本课目标

学完本课，你将能够：
1. 描述 UObject 的完整生命周期（创建 → 使用 → 销毁）
2. 理解 `BeginDestroy()`、`IsReadyForFinishDestroy()`、`FinishDestroy()` 的调用时机
3. 正确使用 `MarkAsGarbage()` 和 `ConditionalBeginDestroy()`
4. 避免在销毁后访问对象（野指针问题）
5. 使用 `IsValidLowLevel()` 和 `IsValidObject()` 安全检查

## 1. UObject 完整生命周期

### 1.1 生命周期阶段

UObject 的生命周期分为以下阶段：

```mermaid
flowchart TD
    A["1. 创建（Creation）"] --> B["NewObject() 或 LoadObject()"]
    B --> C["2. 初始化（Initialization）"]
    C --> D["PostInitProperties()、PostLoad()、PostActorCreated()"]
    D --> E["3. 使用中（In Use）"]
    E --> F["对象正常使用，被引用保持存活"]
    F --> G["4. 标记垃圾（Mark as Garbage）"]
    G --> H["MarkAsGarbage() 或 MarkPendingKill()"]
    H --> I["5. 开始销毁（Begin Destroy）"]
    I --> J["BeginDestroy() 被调用"]
    J --> K["6. 准备完成销毁（Ready for Finish Destroy）"]
    K --> L["IsReadyForFinishDestroy() 返回 true"]
    L --> M["7. 完成销毁（Finish Destroy）"]
    M --> N["FinishDestroy() 被调用"]
    N --> O["8. 内存回收（Memory Reclaimed）"]
    O --> P["GC 释放对象占用的内存"]
    
    style A fill:#e3f2fd,stroke:#1565c0,color:#000
    style E fill:#e8f5e9,stroke:#2e7d32,color:#000
    style G fill:#ffebee,stroke:#c62828,color:#000
    style O fill:#f3e5f5,stroke:#6a1b9a,color:#000
```

### 1.2 mermaid 图示：UObject 生命周期

```mermaid
stateDiagram-v2
    [*] --> 创建: NewObject()
    创建 --> 初始化: PostInitProperties()
    初始化 --> 使用中: 对象存活
    
    使用中 --> 标记垃圾: MarkAsGarbage()
    标记垃圾 --> 开始销毁: GC 触发<br/>BeginDestroy()
    
    开始销毁 --> 准备完成: IsReadyForFinishDestroy()<br/>返回 true
    准备完成 --> 完成销毁: FinishDestroy()
    
    完成销毁 --> 内存回收: GC 释放内存
    内存回收 --> [*]
    
    note right of 使用中
        - 被引用保持存活
        - 可以正常使用
    end note
    
    note right of 标记垃圾
        - 设置 RF_BeginDestroyed
        - 等待 GC 处理
    end note
```

### 1.3 代码示例：完整的生命周期

```cpp
// 1. 创建对象
UMyObject* MyObj = NewObject<UMyObject>();

// 2. 使用对象
MyObj->DoSomething();

// 3. 标记对象为垃圾（告诉 GC 可以回收）
MyObj->MarkAsGarbage();

// 4. GC 会在适当时候触发，自动调用：
//    - BeginDestroy()
//    - IsReadyForFinishDestroy()
//    - FinishDestroy()

// 5. 内存被回收
```

## 2. 销毁流程详解

### 2.1 三个关键方法

UObject 的销毁流程涉及三个可重写的虚函数：

| 方法 | 调用时机 | 用途 |
|------|---------|------|
| `BeginDestroy()` | GC 开始销毁对象时 | 启动异步销毁操作（如销毁渲染资源） |
| `IsReadyForFinishDestroy()` | 每帧检查 | 返回 true 时，才调用 `FinishDestroy()` |
| `FinishDestroy()` | `IsReadyForFinishDestroy()` 返回 true 后 | 完成销毁，清理剩余资源 |

### 2.2 代码示例：重写销毁方法

```cpp
UCLASS()
class UMyObjectWithResource : public UObject
{
    GENERATED_BODY()
    
private:
    // 假设有一个需要异步销毁的资源
    FAsyncResource* AsyncResource;
    
public:
    // 1. 开始销毁：启动异步操作
    virtual void BeginDestroy() override
    {
        Super::BeginDestroy();
        
        // 启动异步销毁（如通知渲染线程释放资源）
        if (AsyncResource)
        {
            AsyncResource->ReleaseAsync();
        }
        
        UE_LOG(LogTemp, Log, TEXT("MyObject: BeginDestroy() called"));
    }
    
    // 2. 检查是否可以完成销毁
    virtual bool IsReadyForFinishDestroy() override
    {
        // 等待异步资源释放完成
        if (AsyncResource && !AsyncResource->IsReleased())
        {
            return false;  // 还没准备好，等待下一帧
        }
        
        return Super::IsReadyForFinishDestroy();
    }
    
    // 3. 完成销毁：清理剩余资源
    virtual void FinishDestroy() override
    {
        // 清理剩余资源
        if (AsyncResource)
        {
            delete AsyncResource;
            AsyncResource = nullptr;
        }
        
        UE_LOG(LogTemp, Log, TEXT("MyObject: FinishDestroy() called"));
        
        Super::FinishDestroy();
    }
};
```

### 2.3 mermaid 图示：销毁流程

```mermaid
sequenceDiagram
    participant GC as GC 线程
    participant Obj as UMyObject
    participant Res as 异步资源
    
    GC->>Obj: 1. MarkAsGarbage()
    Note over Obj: 对象被标记为垃圾
    
    GC->>Obj: 2. BeginDestroy()
    Obj->>Res: 启动异步释放
    Note over Res: 异步释放中...
    
    GC->>Obj: 3. IsReadyForFinishDestroy()?
    Obj-->>GC: false（还没准备好）
    
    Note over Res: 异步释放完成！
    
    GC->>Obj: 4. IsReadyForFinishDestroy()?
    Obj-->>GC: true（可以完成了）
    
    GC->>Obj: 5. FinishDestroy()
    Obj->>Res: 清理剩余资源
    Obj->>GC: 销毁完成
    
    GC->>GC: 6. 回收内存
```

## 3. 正确使用销毁 API

### 3.1 MarkAsGarbage() vs ConditionalBeginDestroy()

| API | 用途 | 线程安全 | 推荐度 |
|-----|------|----------|--------|
| `MarkAsGarbage()` | 告诉 GC 此对象是垃圾，等待 GC 自动回收 | ✅ 线程安全 | ✅ **推荐**（UE5） |
| `MarkPendingKill()` | UE4 遗留，功能同 `MarkAsGarbage()` | ✅ 线程安全 | ⚠️ 已废弃，不推荐 |
| `ConditionalBeginDestroy()` | 立即开始销毁流程 | ❌ 只能在 GameThread | ⚠️ 谨慎使用 |

### 3.2 代码示例：正确使用

```cpp
UMyObject* MyObj = NewObject<UMyObject>();

// ✅ UE5 推荐方式：标记为垃圾，等待 GC 回收
MyObj->MarkAsGarbage();

// ⚠️ UE4 遗留方式（不推荐）
// MyObj->MarkPendingKill();

// ⚠️ 立即销毁（谨慎使用，可能线程不安全）
// MyObj->ConditionalBeginDestroy();
```

### 3.3 常见错误

```cpp
// ❌ 错误 1：销毁后继续访问
UMyObject* MyObj = NewObject<UMyObject>();
MyObj->MarkAsGarbage();
MyObj->DoSomething();  // ❌ 危险！对象可能已被销毁

// ✅ 正确：销毁后清除指针
UMyObject* MyObj = NewObject<UMyObject>();
MyObj->MarkAsGarbage();
MyObj = nullptr;  // ✅ 清除指针

// ❌ 错误 2：手动 delete UObject
UMyObject* MyObj = NewObject<UMyObject>();
delete MyObj;  // ❌ 错误！应该让 GC 管理

// ✅ 正确：让 GC 管理
MyObj->MarkAsGarbage();
```

## 4. 安全检查

### 4.1 检查对象是否有效

```cpp
UMyObject* MyObj = NewObject<UMyObject>();

// 方法 1：IsValidLowLevel()（快速检查）
if (MyObj && MyObj->IsValidLowLevel())
{
    // 对象可能还有效（但不保证一定未被 GC）
}

// 方法 2：使用 TWeakObjectPtr（推荐）
TWeakObjectPtr<UMyObject> WeakPtr(MyObj);

if (WeakPtr.IsValid())
{
    // ✅ 对象一定未被 GC
    UMyObject* Obj = WeakPtr.Get();
    Obj->DoSomething();
}

// 方法 3：IsValidObject()（UE 宏）
if (IsValidObject(MyObj))
{
    // 对象有效
}
```

### 4.2 代码示例：安全的对象使用

```cpp
UCLASS()
class AMyActor : public AActor
{
    GENERATED_BODY()
    
private:
    // ✅ 使用 TWeakObjectPtr 安全引用
    TWeakObjectPtr<UMyObject> MyObjWeak;
    
public:
    void SetMyObj(UMyObject* Obj)
    {
        MyObjWeak = TWeakObjectPtr<UMyObject>(Obj);
    }
    
    void UseMyObj()
    {
        // ✅ 安全：先检查再使用
        if (UMyObject* Obj = MyObjWeak.Get())
        {
            Obj->DoSomething();
        }
        else
        {
            UE_LOG(LogTemp, Warning, TEXT("MyObj has been destroyed"));
        }
    }
};
```

## 5. 与 Actor 生命周期的关系

### 5.1 Actor 的特殊性

Actor 是 UObject 的派生类，但有额外的生命周期管理：

```mermaid
flowchart LR
    subgraph UObject生命周期 ["UObject 生命周期"]
        direction TB
        U1["1. NewObject()"]
        U2["2. 使用中"]
        U3["3. MarkAsGarbage()"]
        U4["4. BeginDestroy()"]
        U5["5. FinishDestroy()"]
        U7["6. 内存回收"]
    end
    
    subgraph Actor生命周期 ["Actor 特有生命周期"]
        direction TB
        A1["1. SpawnActor()"]
        A2["2. BeginPlay()、Tick()"]
        A3["3. Destroy()<br/>（标记 Actor 为待销毁）"]
        A4["4. EndPlay()、OnDestroyed()"]
        A5["5. ..."]
        A6["6. 内存回收"]
    end
    
    U1 ==> A1
    U2 ==> A2
    U3 ==> A3
    U4 ==> A4
    U5 ==> A5
    U7 ==> A6
    
    style UObject生命周期 fill:#e3f2fd,stroke:#1565c0,color:#000
    style Actor生命周期 fill:#e8f5e9,stroke:#2e7d32,color:#000
```

### 5.2 代码示例：Actor 销毁

```cpp
// Actor 的销毁方式不同
AMyActor* MyActor = GetWorld()->SpawnActor<AMyActor>();

// ✅ 正确：使用 Destroy()（而不是 MarkAsGarbage()）
MyActor->Destroy();

// Destroy() 内部会：
// 1. 调用 EndPlay()
// 2. 从 World 移除
// 3. 标记 UObject 为垃圾（MarkAsGarbage()）
// 4. 等待 GC 回收
```

## Lyra 中的实践

Lyra 项目中的 UObject 生命周期管理遵循 UE5 的最佳实践。理解生命周期对于正确管理 Lyra 中的对象至关重要。

### Lyra 中的生命周期管理

1. **AbilitySystemComponent 生命周期**：
   - `ULyraAbilitySystemComponent` 在 `ALyraCharacter` 创建时初始化
   - 在 Character 销毁时，`BeginDestroy()` 会被调用，清理 GrantedAbilities
   - 使用 `UPROPERTY()` 保持 AbilitySet 引用，确保 GC 不回收

2. **Experience 生命周期**：
   - `ULyraExperienceDefinition` 通常设为 `RF_Standalone`，确保整个游戏会话期间不被 GC 回收
   - 切换 Experience 时，旧 Experience 的引用被清除，相关对象在下次 GC 时被回收

3. **Inventory 生命周期**：
   - `ULyraInventoryManagerComponent` 使用 `TArray<TWeakObjectPtr<ULyraInventoryItemDefinition>>` 避免循环引用
   - 物品销毁时，从数组中移除引用，允许 GC 回收

### Lyra 代码示例：安全的生命周期管理

```cpp
// Lyra 示例：重写 BeginDestroy() 清理引用
UCLASS()
class ULyraAbilitySystemComponent : public UAbilitySystemComponent
{
    GENERATED_BODY()

public:
    // ✅ 使用 UPROPERTY() 防止 GC 回收
    UPROPERTY()
    TArray<TObjectPtr<ULyraGameplayAbility>> GrantedAbilities;

    // 重写 BeginDestroy() 清理引用
    virtual void BeginDestroy() override
    {
        // 清理引用
        GrantedAbilities.Empty();

        Super::BeginDestroy();
    }
};
```

**要点**：
- Lyra 中的 UObject 派生类都应通过 `UPROPERTY()` 引用，确保 GC 正确管理生命周期
- 在 `BeginDestroy()` 中清理引用，避免悬空指针
- 使用 `TWeakObjectPtr` 打破潜在循环引用

## 总结与要点

| 知识点 | 核心内容 | 记住这个 |
|--------|----------|----------|
| **生命周期** | 创建 → 使用 → 标记垃圾 → 销毁 → 回收 | 6 个阶段 |
| **三个关键方法** | `BeginDestroy()`、`IsReadyForFinishDestroy()`、`FinishDestroy()` | 异步销毁流程 |
| **正确销毁** | `MarkAsGarbage()`（UE5 推荐） | 不要 `delete` UObject |
| **安全检查** | `TWeakObjectPtr::IsValid()` | 使用前先检查 |
| **Actor 特殊性** | 使用 `Destroy()` 而不是 `MarkAsGarbage()` | Actor 有额外生命周期 |

## 相关页面

- [[30-tutorials/garbage-collection/03-引用类型系统]] - 上一课：引用类型系统
- [[30-tutorials/garbage-collection/05-GC触发时机与收集流程]] - 下一课：GC 触发时机与收集流程
- [[30-tutorials/ue-framework/40-actor-system/01-AActor完整生命周期]] - UE 框架：Actor 生命周期

---


> 最后更新：2026-05-17

<!-- nav:auto -->

---

**导航**: ← [[30-tutorials/garbage-collection/03-引用类型系统|03-引用类型系统]] · [[30-tutorials/garbage-collection/05-GC触发时机与收集流程|05-GC触发时机与收集流程]] →

<!-- /nav:auto -->
