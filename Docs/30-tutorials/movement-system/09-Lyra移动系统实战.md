---
id: 30-tutorials/movement-system/09-Lyra移动系统实战
title: Lyra移动系统实战
description: 详解 Lyra 对 UCharacterMovementComponent 的三大扩展点，以及与 GAS 的深度集成。
type: tutorial
status: current
language: zh
owner: ai
series: movement-system
lesson_index: 9
difficulty: advanced
prerequisites: ["[[30-tutorials/movement-system/08-RootMotion机制]]"]
tags: [lyra, move]
last_synced: 2026-05-19
engine_sources:
  - path: Engine/Source/Runtime/Engine/Classes/GameFramework/CharacterMovementComponent.h
    context: CMC 基类参考
lyra_sources:
  - path: Source/LyraGame/Character/LyraCharacterMovementComponent.h
    context: Lyra CMC 扩展声明
  - path: Source/LyraGame/Character/LyraCharacterMovementComponent.cpp
    context: Lyra CMC 扩展实现（GetGroundInfo、GetMaxSpeed、GetDeltaRotation、SimulateMovement）
  - path: Source/LyraGame/Character/LyraCharacter.h
    context: FLyraReplicatedAcceleration、FSharedRepMovement、FastSharedReplication 声明
  - path: Source/LyraGame/Character/LyraCharacter.cpp
    context: UpdateSharedReplication()、OnRep_ReplicatedAcceleration() 实现
---

# Lyra移动系统实战

> 详解 Lyra 对 `UCharacterMovementComponent` 的三大扩展点，以及与 GAS 的深度集成。

## 概述

Lyra **没有自定义新的 MovementMode**，而是通过覆写 `UCharacterMovementComponent` 的三个关键函数，将移动控制权交给 **Gameplay Ability System（GAS）**。

学完本课你将能够：
- 列举 `ULyraCharacterMovementComponent` 的三大扩展点
- 解释 `Gameplay.MovementStopped` Tag 如何阻断移动
- 理解 `FSharedRepMovement` + `FastSharedReplication` 的带宽优化原理
- 在 Lyra 中实现"眩晕 3 秒无法移动"的 GE 配置

---

## 一、`ULyraCharacterMovementComponent` 三大扩展

### 1.1 `GetMaxSpeed()` — GAS 控制最高速度

```cpp
// Source/LyraGame/Character/LyraCharacterMovementComponent.cpp:L120-L131
float ULyraCharacterMovementComponent::GetMaxSpeed() const
{
    // [1] 查询 ASC 是否有 Gameplay.MovementStopped Tag
    if (UAbilitySystemComponent* ASC = UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(GetOwner()))
    {
        if (ASC->HasMatchingGameplayTag(TAG_Gameplay_MovementStopped))
        {
            return 0;  // [2] 有 Tag → 速度为 0（完全无法移动）
        }
    }
    
    // [3] 无 Tag → 使用默认逻辑（Super::GetMaxSpeed()）
    return Super::GetMaxSpeed();
}
```

**设计意图**：移动速度不再由 CMC 内部逻辑决定，而是**由 GAS 的 GameplayTag 动态控制**。施加一个 GE 添加 `Gameplay.MovementStopped` Tag，角色立刻停住。

### 1.2 `GetDeltaRotation()` — GAS 控制转向

```cpp
// Source/LyraGame/Character/LyraCharacterMovementComponent.cpp:L107-L118
FRotator ULyraCharacterMovementComponent::GetDeltaRotation(float DeltaTime) const
{
    // [1] 同样检查 Gameplay.MovementStopped Tag
    if (UAbilitySystemComponent* ASC = UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(GetOwner()))
    {
        if (ASC->HasMatchingGameplayTag(TAG_Gameplay_MovementStopped))
        {
            return FRotator(0, 0, 0);  // [2] 有 Tag → 不转向
        }
    }
    
    return Super::GetDeltaRotation(DeltaTime);  // [3] 无 Tag → 正常转向
}
```

**关键点**：`GetDeltaRotation()` 在 `PhysWalking()` 和 `PhysFalling()` 中被调用来计算机身旋转。返回零旋转 = 角色面朝不变。

### 1.3 `SimulateMovement()` — 保留复制的加速度

```cpp
// Source/LyraGame/Character/LyraCharacterMovementComponent.cpp:L27-L40
void ULyraCharacterMovementComponent::SimulateMovement(float DeltaTime)
{
    if (bHasReplicatedAcceleration)  // [1] 如果有复制的加速度
    {
        const FVector OriginalAcceleration = Acceleration;  // [2] 保存
        Super::SimulateMovement(DeltaTime);        // [3] 执行模拟
        Acceleration = OriginalAcceleration;                 // [4] 恢复（不被 Super 覆盖）
    }
    else
    {
        Super::SimulateMovement(DeltaTime);
    }
}
```

**问题**：为什么需要保留 `Acceleration`？

`SimulateMovement()` 是**模拟代理（其他玩家）** 在客户端执行的函数。默认实现会**清空 `Acceleration`**（因为模拟代理不从本地输入读取）。但 Lyra 通过 `FLyraReplicatedAcceleration` 把**权威端的加速度复制了过来**，`bHasReplicatedAcceleration = true` 时应该保留这个值。

---

## 二、`FLyraReplicatedAcceleration` — 压缩加速度

### 2.1 为什么需要压缩？

| 方案 | 每帧字节数 | 说明 |
|------|-------------|------|
| `FVector Acceleration` | 12 字节（3 × float） | 完整精度，带宽消耗大 |
| `FLyraReplicatedAcceleration` | **3 字节** | 压缩到 uint8/int8 |

### 2.2 压缩算法

```cpp
// Source/LyraGame/Character/LyraCharacter.h:L36-L49
struct FLyraReplicatedAcceleration
{
    uint8 AccelXYRadians = 0;   // [1] 方向：0-255 映射 0-2π
    uint8 AccelXYMagnitude = 0; // [2] 大小：0-255 映射 0-MaxAcceleration
    int8 AccelZ = 0;              // [3] Z 轴：-127 到 127（有符号）
};
```

**精度损失评估**：
- 方向精度：`2π / 256 ≈ 1.4°`（足够）
- 大小精度：`MaxAcceleration / 256`（默认 `2048 / 256 = 8 cm/s²` 每档，足够）
- Z 轴精度：`255 档`（覆盖 `-MaxAcceleration` 到 `+MaxAcceleration`）

### 2.3 复制时机

```cpp
// Source/LyraGame/Character/LyraCharacter.cpp
void ALyraCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    // [1] 条件复制：只复制给模拟代理
    DOREPLIFETIME_COND(ALyraCharacter, ReplicatedAcceleration, COND_SimulatedOnly);
}

void ALyraCharacter::OnRep_ReplicatedAcceleration()
{
    // [2] 客户端接收后，解压并写入 CMC
    if (ULyraCharacterMovementComponent* LyraCMC = Cast<ULyraCharacterMovementComponent>(GetCharacterMovement()))
    {
        LyraCMC->SetReplicatedAcceleration(ReplicatedAcceleration);
    }
}
```

**为什么 `COND_SimulatedOnly`？**

权威端（服务器 + 本地玩家）**不需要**复制加速度——他们直接从输入计算。只给**模拟代理**（其他玩家）复制，节省带宽。

---

## 三、`FSharedRepMovement` + `FastSharedReplication`

### 3.1 FSharedRepMovement 结构

```cpp
// Source/LyraGame/Character/LyraCharacter.h:L51-L78
struct FSharedRepMovement
{
    FRepMovement RepMovement;       // [1] 完整移动数据（位置、旋转、速度）
    float RepTimeStamp = 0.0f;       // [2] 时间戳（用于排序）
    uint8 RepMovementMode = 0;     // [3] MovementMode（压缩到 1 字节）
    bool bProxyIsJumpForceApplied;  // [4] 是否正在跳跃
    bool bIsCrouched;              // [5] 是否蹲伏
    
    // 自定义网络序列化（只序列化变化的部分）
    bool NetSerialize(FArchive& Ar, class UPackageMap* Map, bool& bOutSuccess);
};
```

### 3.2 FastSharedReplication 触发条件

```cpp
// Source/LyraGame/Character/LyraCharacter.cpp
bool ALyraCharacter::UpdateSharedReplication()
{
    FSharedRepMovement NewData;
    if (NewData.FillForCharacter(this))  // [1] 填充当前移动状态
    {
        // [2] 与上次发送的数据比较，只有变化时才发送
        if (!NewData.Equals(LastSharedReplication, this))
        {
            FastSharedReplication(NewData);  // [3] 发送 unreliable Multicast RPC
            LastSharedReplication = NewData;   // [4] 保存本次数据（用于下次比较）
            return true;
        }
    }
    return false;
}
```


**为什么用 unreliable RPC？**

移动快照是"可丢失"的——如果这一帧的快照丢了，下一帧的新快照会覆盖它。用 reliable RPC 反而会因为"重传"导致更严重的延迟。

### 3.3 与默认 `ReplicatedMovement` 的关系

| 路径 | 可靠性 | 带宽消耗 | 用途 |
|------|---------|-------------|------|
| `ReplicatedMovement`（默认） | Reliable | 高（~50 字节/帧） | 权威同步（兜底） |
| `FastSharedReplication` | **Unreliable** | 中（~30 字节/帧） | 模拟代理的移动表现优化 |

**Lyra 的做法**：**两者都启用**，但 `FastSharedReplication` 是"快路径"，用于模拟代理的平滑移动；`ReplicatedMovement` 是"兜底"，确保最终一致性。

---

## 四、GAS 与移动的集成实战

### 4.1 "眩晕 3 秒无法移动" 的 GE 配置

```cpp
// 在 Lyra 中创建 GE_Stun 的配置文件：
// 1. 添加 GameplayEffect 组件
ULyraGameplayEffect::StaticClass()

// 2. 添加 GameplayTag：
    GrantedTags: Gameplay.MovementStopped

// 3. 设置持续时间：
    DurationPolicy: HasDuration
    DurationMagnitude: 3.0  // 3 秒

// 4. 应用方式：
//    在 GAS 的 Skill Ability 中：
//    ActivateAbilityFromEvent() → ApplyGameplayEffectToSelf(GE_Stun)
```

**效果**：GE 激活后，`Gameplay.MovementStopped` Tag 被添加到 ASC → `GetMaxSpeed()` 返回 0 → 角色无法移动/转向 → 3 秒后 GE 结束 → Tag 移除 → 恢复移动。

### 4.2 "减速 50%" 的 GE 配置

```cpp
// 在 Lyra 中创建 GE_Slow 的配置文件：
// 1. 添加 Modifier：
    Attribute: ULyraCharacterMovementComponent::MaxWalkSpeedAttribute()
    ModifierMagnitude: -50%  // 减半

// 2. 可选：同时添加 Tag：
    GrantedTags: Gameplay.MovementSlowed

// 3. 效果：
//    MaxWalkSpeed 减半 → CalcVelocity() 中最高速度减半
//    （Acceleration 不变，但 Velocity 上限降低）
```

---

## 五、Death 序列与移动系统

### 5.1 Death 时的移动处理

```cpp
// Source/LyraGame/Character/LyraCharacter.cpp
void ALyraCharacter::OnDeathStarted(AActor* OwningActor)
{
    // [1] 禁用移动和碰撞
    DisableMovementAndCollision();
    
    // [2] 切换到 Falling 模式（让角色"倒下"）
    if (UCharacterMovementComponent* CMC = GetCharacterMovement())
    {
        CMC->SetMovementMode(MOVE_Falling);
    }
}

void ALyraCharacter::DisableMovementAndCollision()
{
    if (UCharacterMovementComponent* CMC = GetCharacterMovement())
    {
        // [1] 清除加速度和速度
        CMC->Velocity = FVector::ZeroVector;
        CMC->Acceleration = FVector::ZeroVector;
        
        // [2] 禁用移动组件
        CMC->SetActive(false);
    }
    
    // [3] 禁用胶囊体碰撞
    if (UCapsuleComponent* Capsule = GetCapsuleComponent())
    {
        Capsule->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    }
}
```

### 5.2 为什么 Death 后要切换到 Falling？

**表现考虑**：让角色播放"倒下"动画时，身体可以自然下落（而不是僵硬地停在半空）。

**实现方式**：在 Death 动画蒙太奇中启用 Root Motion，让身体"向前扑倒"；同时 CMC 设为 `MOVE_Falling`，让重力自然把角色"拉到"地面。

---

## 六、常见问题与排查

### 6.1 "施加了 `Gameplay.MovementStopped` Tag，但角色还能移动？"

**排查清单**：
1. `GetMaxSpeed()` 的覆写是否被正确调用？（检查 `bHasMatchingGameplayTag` 的 Tag 名称是否正确）
2. `FLyraCharacterMovementComponent` 是否被正确设置到 `ACharacter::CharacterMovement`？（检查 Lyra 的构造函数）
3. GE 的持续时间是否为 0？（瞬间添加/瞬间移除 = 看不到效果）

### 6.2 "`FastSharedReplication` 没有效果？"

**可能原因**：
1. `bEnableFastSharedReplication` 未设为 `true`
2. `FSharedRepMovement::FillForCharacter()` 返回 `false`（数据未变化，不发送）
3. 模拟代理的 `bReplicatesMovement` 为 `false`（完全不接收网络同步）

### 6.3 "角色 Death 后还能移动？"

**原因**：`DisableMovementAndCollision()` 只在**服务器端** 执行。如果客户端预测了移动，需要在 `OnRep` 中同步。

**修复**：在 `OnRep_PlayerState()` 或 `OnRep_Controller()` 中检查 Death 状态，客户端也执行 `DisableMovementAndCollision()`。

---

## 总结

| 扩展点 | 函数 | 作用 | GAS 集成方式 |
|--------|------|------|--------------|
| **速度控制** | `GetMaxSpeed()` | 返回 0 则无法移动 | `Gameplay.MovementStopped` Tag |
| **转向控制** | `GetDeltaRotation()` | 返回零旋转则无法转向 | `Gameplay.MovementStopped` Tag |
| **加速度保留** | `SimulateMovement()` | 保留复制的加速度（不清除） | `bHasReplicatedAcceleration` 标志 |

| 网络优化 | 结构 | 可靠性 | 说明 |
|-----------|---------|---------|------|
| **压缩加速度** | `FLyraReplicatedAcceleration`（3 字节） | Reliable（`COND_SimulatedOnly`） | 只复制给模拟代理 |
| **移动快照** | `FSharedRepMovement` + `FastSharedReplication` | **Unreliable** | 快路径，允许丢包 |

---

## 相关页面

- [[30-tutorials/movement-system/08-RootMotion机制]] ← Root Motion 机制
- [[30-tutorials/gas/03-GA输入绑定]] - GA 输入绑定（Lyra 移动通过 GA 触发）
- Lyra CMC 模块文档（待创建）

<!-- nav:auto -->

---

**导航**: ← [[30-tutorials/movement-system/08-RootMotion机制|08-RootMotion机制]] · [[30-tutorials/movement-system/10-蹲伏-Crouch机制|10-蹲伏-Crouch机制]] →

<!-- /nav:auto -->
