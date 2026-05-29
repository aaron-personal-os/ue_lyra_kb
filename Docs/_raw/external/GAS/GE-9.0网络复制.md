> 💡 **本系列文章基于UE5.3**

# 概述

---

AbilitySystemComponent(ASC)的字段**ActiveGameplayEffects**是存放当前拥有的持续效果GE的容器(FActiveGameplayEffectsContainer)。这个容器是支持网络复制的。ActiveGameplayEffects的网络复制支持配置不同的复制策略(ReplicationMode)。

```cpp
class GAMEPLAYABILITIES_API UAbilitySystemComponent
{
	**//标记为可复制的**
	**UPROPERTY(Replicated)
	FActiveGameplayEffectsContainer ActiveGameplayEffects;
	
	EGameplayEffectReplicationMode ReplicationMode;**
}
```

ActiveGameplayEffects的网络复制策略(ReplicationMode)。

- **Minimal模式：** 
极简模式
只会复制GE赋予目标的Tag信息和GE触发的GameplayCue的信息给模拟端和主控端，不会复制效果容器ActiveGameplayEffects。
- **Full模式：**
全量模式
****完整复制ActiveGameplayEffects给模拟端和主控客户端
- **Mixed模式：**
混合模式
****完整复制ActiveGameplayEffects到主控客户端，复制给模拟端采用Minimal模式

官方推荐用法是**Mixed(混合)模式**

bUseReplicationConditionForActiveGameplayEffects配置决定ActiveGameplayEffects在执行复制时是否需要运行时根据条件动态决定是否复制。如果为False则是全部复制**(**COND_None**)**，如果为True则会在运行时根据ActiveGameplayEffects的网络复制策略(ReplicationMode)来决定如何复制。

```cpp
static bool bUseReplicationConditionForActiveGameplayEffects = true;
static FAutoConsoleVariableRef CVarUseReplicationConditionForActiveGameplayEffects(
TEXT("AbilitySystem.UseReplicationConditionForActiveGameplayEffects"), 
bUseReplicationConditionForActiveGameplayEffects, 
...);

```

```cpp
 
//bIsUsingReplicationCondition 为True
//则ActiveGameplayEffects网络复制时 标记COND_Dynamic
//在检测复制条件时会调用GetReplicatedCustomConditionState 进行动态判定
void UAbilitySystemComponent::GetLifetimeReplicatedProps(...) const
{
	Params.Condition = (bUseReplicationConditionForActiveGameplayEffects ? 
	COND_Dynamic : COND_None);
	
DOREPLIFETIME_WITH_PARAMS_FAST(UAbilitySystemComponent, ActiveGameplayEffects, Params);
}

//**GetReplicatedCustomConditionState最后调用**
//**FActiveGameplayEffectsContainer::GetReplicationCondition 进行复制条件判定**
void UAbilitySystemComponent::GetReplicatedCustomConditionState(...) const
{
	if (ActiveGameplayEffects.IsUsingReplicationCondition())
	{
		DOREPDYNAMICCONDITION_INITCONDITION_FAST(ThisClass, 
		**ActiveGameplayEffects**, 
		**ActiveGameplayEffects.GetReplicationCondition()**);
	}
}

//**GetReplicationCondition 根据配置的网络复制策略(ReplicationMode)来决定如何复制**
ELifetimeCondition FActiveGameplayEffectsContainer::GetReplicationCondition() const
{
	if (Owner)
	{
		const EGameplayEffectReplicationMode ReplicationMode = Owner->ReplicationMode;
		switch (ReplicationMode)
		{
			case EGameplayEffectReplicationMode::Minimal:
			{
				**//Minimal 模式不允许复制整个容器**
				return COND_Never;
			}

			case EGameplayEffectReplicationMode::Mixed:
			{
				**//Mixed 只允许复制整个容器给主控端**
				if (IsNetAuthority())
				{
					return COND_OwnerOnly;
				}
				else
				{
					return COND_ReplayOrOwner;
				}
			}

		 **//Full 模拟端和主控端都复制整个容器**
			case EGameplayEffectReplicationMode::Full:
			default:
			{
				return COND_None;
			}
		}
	}
	return COND_None;
}
```

> 💡
>
> 对于UAbilitySystemComponent的效果容器ActiveGameplayEffects，不能直接使用Minimal模式复制，如果要使用Minimal模式需要修改下GE的流程相关源
>
> 举个例子:UAbilitySystemComponent上关于Tag的复制MinimalReplicationTags复制时标记为COND_SkipOwner，也就是只会复制到模拟端。主控客户端的Tag通过复制ActiveGameplayEffects触发的。使用Minimal模式这个逻辑就需要修改。

****

**GE至少需要复制赋予Target的Tag和触发GameplayCue的Tag(Minimal模式)**

```cpp
bool FActiveGameplayEffectsContainer::ShouldUseMinimalReplication()
{
	return IsNetAuthority() && (Owner->ReplicationMode ==
	EGameplayEffectReplicationMode::Minimal || 
	 Owner->ReplicationMode == EGameplayEffectReplicationMode::Mixed);
}

void FActiveGameplayEffectsContainer::AddActiveGameplayEffectGrantedTagsAndModifiers(...)
{
...
if (ShouldUseMinimalReplication())
{
	Owner->AddMinimalReplicationGameplayTags(Effect.Spec.Def->GetGrantedTags());
	Owner->AddMinimalReplicationGameplayTags(Effect.Spec.DynamicGrantedTags);
}
...
for (const FGameplayEffectCue& Cue : Effect.Spec.Def->GameplayCues)
{
	Owner->UpdateTagMap(Cue.GameplayCueTags, 1);

	if (bInvokeGameplayCueEvents)
	{
		Owner->InvokeGameplayCueEvent(Effect.Spec, EGameplayCueEvent::OnActive);
		Owner->InvokeGameplayCueEvent(Effect.Spec, EGameplayCueEvent::WhileActive);
	}

	if (ShouldUseMinimalReplication())
	{
		for (const FGameplayTag& CueTag : Cue.GameplayCueTags)
		{
			Owner->AddGameplayCue_MinimalReplication(CueTag,
			Effect.Spec.GetEffectContext());
		}
	}
}
...
}
```

# 复制流程

---

**效果容器ActiveGameplayEffects(FActiveGameplayEffectsContainer)的复制实际是复制一个FActiveGameplayEffect的数组**。通过FastArray复制到客户端(只会复制发生修改的数组元素，不会每次都复制整个数组)。

FActiveGameplayEffect的**PostReplicatedAdd**、**PostReplicatedChange、PreReplicatedRemove**分别对应复制到客户端的添加、修改、移除。

```cpp
struct GAMEPLAYABILITIES_API FActiveGameplayEffectsContainer :
 public **FFastArraySerializer**
{
	UPROPERTY()
	TArray<FActiveGameplayEffect>	GameplayEffects_Internal;
}
```

```cpp
struct GAMEPLAYABILITIES_API FActiveGameplayEffect : public **FFastArraySerializerItem**
{
	//复制到客户端的添加操作
	void PostReplicatedAdd(const struct FActiveGameplayEffectsContainer &InArray);
	
	//复制到客户端的修改操作
	void PostReplicatedChange(const struct FActiveGameplayEffectsContainer &InArray);
	
	//复制到客户端的移除操作
	void PreReplicatedRemove(const struct FActiveGameplayEffectsContainer &InArray);
}
```

**复制到客户端的添加操作**
最终调用的是InhibitActiveGameplayEffect跟DS的添加操作走同样的流程

```cpp
void FActiveGameplayEffect::PostReplicatedAdd(...)
{
	const_cast<FActiveGameplayEffectsContainer&>(InArray).
	InternalOnActiveGameplayEffectAdded(*this);	
}

void FActiveGameplayEffectsContainer::InternalOnActiveGameplayEffectAdded(...)
{
...
	Owner->InhibitActiveGameplayEffect(Effect.Handle, !bActive, bInvokeCuesIfEnabled);
...
}
```

**复制到客户端的修改操作**
可以是修改持续时间，堆叠数，或者修正属性发生变化了

```cpp
void FActiveGameplayEffect::PostReplicatedChange(...)
{
	if (CachedStartServerWorldTime != StartServerWorldTime)
	{
		RecomputeStartWorldTime(InArray);
		CachedStartServerWorldTime = StartServerWorldTime;

		const_cast<FActiveGameplayEffectsContainer&>(InArray).OnDurationChange(*this);
	}
	
	int32 StackCount = Spec.GetStackCount();
	if (ClientCachedStackCount != StackCount)
	{
		const_cast<FActiveGameplayEffectsContainer&>(InArray).
		OnStackCountChange(*this, ClientCachedStackCount, StackCount);
		ClientCachedStackCount = StackCount;
	}
	else
	{
		const_cast<FActiveGameplayEffectsContainer&>(InArray).
		UpdateAllAggregatorModMagnitudes(*this);
	}
}
```

**复制到客户端的移除操作**
先标记为待移除，如果效果处于被激活状态则还需要取消激活（RemoveActiveGameplayEffectGrantedTagsAndModifiers）跟DS流程类似

```cpp
void FActiveGameplayEffect::PreReplicatedRemove(...)
{
...
	const_cast<FActiveGameplayEffectsContainer&>(InArray).
	InternalOnActiveGameplayEffectRemoved(*this, !bIsInhibited, GameplayEffectRemovalInfo);
...
}

void FActiveGameplayEffectsContainer::InternalOnActiveGameplayEffectRemoved(...)
{
...
**Effect.IsPendingRemove = true;**
if (Effect.Spec.Def)
	{
		if (!Effect.bIsInhibited)
		{
			RemoveActiveGameplayEffectGrantedTagsAndModifiers(Effect, bInvokeGameplayCueEvents);
		}

		RemoveCustomMagnitudeExternalDependencies(Effect);
	}
...
}
```

# 属性修正的复制

---

大多数属性修正的GE都是持续效果，会通过FActiveGameplayEffectsContainer复制到主控端。然后在主控端重新构建属性对应的数值聚合器(FAggregator)(不需要直接复制聚合器到主控端)

属性字段本身就很通过属性组件复制到客户端，这里构建的聚合器可以在主控端根据不同需要重算属性值(类似装备系统加成之类的需求)，还有就是主控客户端预判的修正属性。

```cpp
	struct GAMEPLAYABILITIES_API FActiveGameplayEffectsContainer 
	{
	 //属性关联的聚合器字段 不会复制到主控端
		TMap<FGameplayAttribute, FAggregatorRef>		AttributeAggregatorMap;
	}

```

```cpp
//FActiveGameplayEffect复制主控客户端时，
//会调用AddActiveGameplayEffectGrantedTagsAndModifiers
//在这里重新构建属性关联的计算聚合器FAggregator
//Spec(FGameplayEffectSpec)计算的修正值是通过网络复制下来了
void FActiveGameplayEffectsContainer::AddActiveGameplayEffectGrantedTagsAndModifiers(....)
{
	if (Effect.Spec.GetPeriod() <= UGameplayEffect::NO_PERIOD)
	{
		**//添加修正到对应的属性聚合器(FAggregator)**
		**for (int32 ModIdx = 0; ModIdx < Effect.Spec.Modifiers.Num(); ++ModIdx)**
		{
			if (Effect.Spec.Def->Modifiers.IsValidIndex(ModIdx) == false)
			{
					continue;
			}

			//这两个Modifiers一一对应
			const FGameplayModifierInfo &ModInfo = Effect.Spec.Def->Modifiers[ModIdx];

			if (!Owner || Owner->HasAttributeSetForAttribute(ModInfo.Attribute) == false)
			{
				continue;
			}

			float EvaluatedMagnitude = Effect.Spec.GetModifierMagnitude(ModIdx, true);	

			//在这里重新构建属性关联的计算聚合器FAggregator
			FAggregator* Aggregator = FindOrCreateAttributeAggregator
			(Effect.Spec.Def->Modifiers[ModIdx].Attribute).Get();
			
			if (ensure(Aggregator))
			{
			//为聚合器添加修正器
				Aggregator->AddAggregatorMod(EvaluatedMagnitude,
				 ModInfo.ModifierOp, 
				 ModInfo.EvaluationChannelSettings.GetEvaluationChannel(), 
				 &ModInfo.SourceTags, 
				 &ModInfo.TargetTags, E
				 ffect.PredictionKey.WasLocallyGenerated(), 
				 Effect.Handle);
			}
		}
	}
}
```