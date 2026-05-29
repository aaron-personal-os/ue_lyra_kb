---
id: 10-architecture/subsystems/ability-system
type: subsystem
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/AbilitySystem/LyraAbilitySystemComponent.h
  - path: Source/LyraGame/AbilitySystem/Abilities/LyraGameplayAbility.h
  - path: Source/LyraGame/AbilitySystem/LyraAbilitySet.h
related:
  - "[[10-architecture/overview]]"
  - "[[10-architecture/subsystems/modular-gameplay]]"
  - "[[20-modules/cpp/ALyraGameState]]"
  - "[[20-modules/cpp/ALyraPlayerState]]"
  - "[[20-modules/cpp/ULyraHealthComponent]]"
  - "[[40-runbooks/how-to-add-gameplay-ability]]"
  - "[[30-tutorials/gas/00-GAS系统总览]]"
sources: []
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [architecture, gas, ability-system, gameplay-ability]
---

# 游戏能力系统（GAS）

> Unreal Engine 的 Gameplay Ability System（GAS）在 Lyra 中的集成和使用。

## 概述

游戏能力系统（Gameplay Ability System，GAS）是 UE 提供的强大框架，用于实现技能、属性、效果等游戏逻辑。

**核心概念**：
- **Gameplay Ability**：可复用的技能逻辑
- **Attribute Set**：属性集（生命值、魔力值等）
- **Gameplay Effect**：效果（ buff、debuff、伤害等）
- **Gameplay Tags**：标签系统，用于标识和过滤
- **Ability System Component**：管理所有这些的核心组件

## 核心类

### ULyraAbilitySystemComponent

**继承自**：`UAbilitySystemComponent`

**职责**：Lyra 自定义的 Ability System Component

**关键功能**：
- 初始化 Attribute Sets
- 管理 Gameplay Tags
- 处理 Ability 激活和结束
- 与 Lyra 的 Pawn Components 集成

**Lyra 中的使用**：
```cpp
// ALyraCharacter 中包含 ULyraAbilitySystemComponent
UCLASS()
class ALyraCharacter : public AModularCharacter, 
                      public IAbilitySystemInterface
{
    // ...
    
    // 获取 Ability System Component
    virtual UAbilitySystemComponent* GetAbilitySystemComponent() const override
    {
        return GetLyraAbilitySystemComponent();
    }
    
    ULyraAbilitySystemComponent* GetLyraAbilitySystemComponent() const;
};
```

### ULyraGameplayAbility

**继承自**：`UGameplayAbility`

**职责**：Lyra 自定义的 Gameplay Ability

**关键功能**：
- 访问 Lyra 的 Pawn 和 Player Controller
- 集成 Lyra 的 Input 系统
- 支持 Ability 的网络复制

**关键属性**：
```cpp
UCLASS()
class ULyraGameplayAbility : public UGameplayAbility
{
    // 激活该 Ability 需要的 Gameplay Tags
    UPROPERTY(EditDefaultsOnly, Category = "Ability")
    FGameplayTagContainer ActivationOwnedTags;
    
    // 激活该 Ability 需要的 Attribute 值
    UPROPERTY(EditDefaultsOnly, Category = "Ability")
    TMap<FGameplayAttribute, float> ActivationRequiredAttributes;
    
    // 该 Ability 的 Input Tag（用于绑定输入）
    UPROPERTY(EditDefaultsOnly, Category = "Ability")
    FGameplayTag InputTag;
};
```

### ULyraAbilitySet

**继承自**：`UPrimaryDataAsset`

**职责**：Ability 集，定义一组 Ability、Attribute Set、Gameplay Effect 的组合

**关键属性**：
```cpp
USTRUCT()
struct FLyraAbilitySet_GameplayAbility
{
    // Ability 类
    UPROPERTY(EditDefaultsOnly)
    TSubclassOf<ULyraGameplayAbility> Ability = nullptr;
    
    // Ability 等级
    UPROPERTY(EditDefaultsOnly)
    int32 AbilityLevel = 1;
    
    // 激活该 Ability 需要的 Input Tag
    UPROPERTY(EditDefaultsOnly, Meta = (Categories = "InputTag"))
    FGameplayTag InputTag;
};

USTRUCT()
struct FLyraAbilitySet_GameplayEffect
{
    // Gameplay Effect 类
    UPROPERTY(EditDefaultsOnly)
    TSubclassOf<UGameplayEffect> GameplayEffect = nullptr;
};

USTRUCT()
struct FLyraAbilitySet_AttributeSet
{
    // Attribute Set 类
    UPROPERTY(EditDefaultsOnly)
    TSubclassOf<UAttributeSet> AttributeSet;
};

UCLASS()
class ULyraAbilitySet : public UPrimaryDataAsset
{
    // Abilities 列表
    UPROPERTY(EditDefaultsOnly, Category = "Gameplay Abilities")
    TArray<FLyraAbilitySet_GameplayAbility> Abilities;
    
    // Gameplay Effects 列表
    UPROPERTY(EditDefaultsOnly, Category = "Gameplay Effects")
    TArray<FLyraAbilitySet_GameplayEffect> GameplayEffects;
    
    // Attribute Sets 列表
    UPROPERTY(EditDefaultsOnly, Category = "Attribute Sets")
    TArray<FLyraAbilitySet_AttributeSet> AttributeSets;
};
```

## 集成流程

### 1. 初始化 Ability System Component

```cpp
// ALyraCharacter::PossessedBy()
void ALyraCharacter::PossessedBy(AController* NewController)
{
    Super::PossessedBy(NewController);
    
    // 初始化 Ability System Component（服务器）
    if (ULyraAbilitySystemComponent* ASC = GetLyraAbilitySystemComponent())
    {
        ASC->InitAbilityActorInfo(this, this);
    }
}

// ALyraCharacter::OnRep_PlayerState()
void ALyraCharacter::OnRep_PlayerState()
{
    Super::OnRep_PlayerState();
    
    // 初始化 Ability System Component（客户端）
    if (ULyraAbilitySystemComponent* ASC = GetLyraAbilitySystemComponent())
    {
        ASC->InitAbilityActorInfo(this, this);
    }
}
```

### 2. 授予 Ability Set

```cpp
// 通过 ULyraPawnData 授予 Ability Set
UCLASS()
class ULyraPawnData : public UPrimaryDataAsset
{
    // 要应用的 Ability Sets
    UPROPERTY(EditDefaultsOnly, Category = "Abilities")
    TArray<TObjectPtr<ULyraAbilitySet>> AbilitySets;
};

// 在 ULyraHeroComponent 中授予 Ability Set
void ULyraHeroComponent::OnPawnReadyToInitialize()
{
    if (ULyraAbilitySystemComponent* ASC = GetAbilitySystemComponent())
    {
        // 授予 Pawn Data 中定义的所有 Ability Sets
        for (ULyraAbilitySet* AbilitySet : PawnData->AbilitySets)
        {
            ASC->GrantAbilitySet(AbilitySet);
        }
    }
}
```

### 3. 绑定 Input 到 Ability

```cpp
// ULyraInputComponent 中绑定 Input
void ULyraInputComponent::AbilityInputTagPressed(const FGameplayTag InputTag)
{
    if (ULyraAbilitySystemComponent* ASC = GetAbilitySystemComponent())
    {
        // 激活具有匹配 Input Tag 的 Ability
        FGameplayTagContainer TagContainer(InputTag);
        ASC->TryActivateAbilitiesByTag(TagContainer);
    }
}

void ULyraInputComponent::AbilityInputTagReleased(const FGameplayTag InputTag)
{
    if (ULyraAbilitySystemComponent* ASC = GetAbilitySystemComponent())
    {
        // 结束具有匹配 Input Tag 的 Ability
        FGameplayTagContainer TagContainer(InputTag);
        ASC->CancelAbilitiesByTag(TagContainer);
    }
}
```

## 网络复制

### 1. Ability System Component 复制

```cpp
// ULyraAbilitySystemComponent 支持网络复制
UCLASS()
class ULyraAbilitySystemComponent : public UAbilitySystemComponent
{
    // 复制 Gameplay Tags
    UPROPERTY(Replicated)
    FGameplayTagCountContainer GameplayTagCountContainer;
    
    // 复制 Attribute Sets
    UPROPERTY(Replicated)
    TArray<UAttributeSet*> SpawnedAttributes;
    
    // 复制 Active Abilities
    UPROPERTY(Replicated)
    TArray<FGameplayAbilitySpecHandle> ActiveAbilities;
};
```

### 2. 属性复制

```cpp
// ULyraHealthSet 示例
UCLASS()
class ULyraHealthSet : public UAttributeSet
{
    // 生命值（复制）
    UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_Health, Category = "Health")
    FGameplayAttributeData Health;
    
    // 最大生命值（复制）
    UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_MaxHealth, Category = "Health")
    FGameplayAttributeData MaxHealth;
    
    // 生命值变化时的回调
    UFUNCTION()
    void OnRep_Health(const FGameplayAttributeData& OldHealth);
    
    UFUNCTION()
    void OnRep_MaxHealth(const FGameplayAttributeData& OldMaxHealth);
    
    // 属性复制宏
    GAMEPLAYATTRIBUTE_PROPERTY_GETTER(ULyraHealthSet, Health);
    GAMEPLAYATTRIBUTE_PROPERTY_GETTER(ULyraHealthSet, MaxHealth);
};
```

## 最佳实践

### 1. 使用 Ability Set 组织 Ability

- 将相关的 Ability、Attribute Set、Gameplay Effect 组织到 Ability Set 中
- 通过 `ULyraPawnData` 授予 Ability Set
- 支持动态添加/移除 Ability Set

### 2. 使用 Gameplay Tags 标识 Ability

- 为每个 Ability 定义唯一的 Gameplay Tag
- 使用 Gameplay Tags 激活/结束 Ability
- 使用 Gameplay Tags 过滤 Ability（如：不能在特定状态下激活）

### 3. 支持网络复制

- 确保所有 Attribute 都正确设置复制
- 使用 `ReplicatedUsing` 处理属性变化
- 在 Server 上激活 Ability，自动复制到 Client

### 4. 调试 GAS

- 使用 `showdebug abilitysystem` 命令显示调试信息
- 使用 `GameplayPrediction` 插件预测客户端操作
- 使用 `AbilitySystemGlobals` 配置全局设置

## 相关页面

- [[10-architecture/overview]] - 架构概览
- [[10-architecture/subsystems/modular-gameplay]] - 模块化游戏玩法
- [[20-modules/cpp/ULyraAbilitySystemComponent]] - Ability System Component 详解
- [[20-modules/cpp/ULyraGameplayAbility]] - Gameplay Ability 详解
- [[20-modules/cpp/ULyraAbilitySet]] - Ability Set 详解

---
> 最后更新：2026-05-16

<!-- nav:auto -->

---

**导航**: ← [[10-architecture/subsystems/modular-gameplay|modular-gameplay]] · [[10-architecture/subsystems/networking-system|networking-system]] →

<!-- /nav:auto -->
