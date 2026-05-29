> 💡 **本系列文章基于UE5.3**

# 概述

---

上一章讲了GE的配置，通过蓝图配置的GE在运行时读取其CDO作为配置模板，应该视为只读数据。

**GE在运行时首先会构造一个运行时实例(类FGameplayEffectSpec对象)**。FGameplayEffectSpec包含了只读的GE配置模板(UGameplayEffect)、创建GE时传入的上下文信息(Context)及其他需要在运行时设置更改的数据(*等级、捕获的来源标记、捕获的目标标记等*)。

**创建好运行时实例后，尝试添加(Apply)给指定的目标**。此时会根据效果的时效性(*持续效果还是即时效果*)区分处理。

**添加(Apply)成功之后，对于持续效果会添加进统一的管理容器(FActiveGameplayEffectsContainer)进行统一管理**，**在其持续的生命周期内会经历添加、激活、抑制(取消激活)、移除**。**对于即时效果添加成功后立即执行，执行完即结束其使命**。

# FGameplayEffectSpec

---

**FGameplayEffectSpec**是在运行时创建和使用的。当需要添加(Apply)一个GameplayEffect时，它会首先创建一个FGameplayEffectSpec，再将其添加(Apply)到目标Actor上。了解GE执行流程前先了解下FGameplayEffectSpec都有哪些数据。

## **Def**

---

TObjectPtr<const UGameplayEffect> Def

**指向UGameplayEffect CDO的指针(只读)**

包含了这个效果的所有静态配置信息，例如效果的类型（即时、持续、周期性等）、基础强度、基础持续时间等。

## **Modifiers**

---

**TArray<FModifierSpec> Modifiers**

**GE属性修正器配置FGameplayModifierInfo对应的运行时数据结构**

将属性修正器配置(FGameplayModifierInfo)转换为最终的修正值。

属性修正器(FGameplayModifierInfo)配置时会有各种数据来源，在运行时就是通过配置的数据来源计算出一个最终的修正值存放到Modifiers中，方便后续逻辑读取修正值。

```cpp
struct FModifierSpec
{
	float GetEvaluatedMagnitude() const { return EvaluatedMagnitude; }
private:
	UPROPERTY()
	float EvaluatedMagnitude;

};
void FGameplayEffectSpec::Initialize(...)
{
	//初始化时已经设置好了数组大小 跟 GE配置的Modifiers一一对应
	Modifiers.SetNum(Def->Modifiers.Num());
}
void FGameplayEffectSpec::CalculateModifierMagnitudes(float EffectElpasedTime)
{
	for(int32 ModIdx = 0; ModIdx < Modifiers.Num(); ++ModIdx)
	{
		//**将GE配置的修正数据计算出结果存放到Modifiers(一一对应)**
		const FGameplayModifierInfo& ModDef = Def->Modifiers[ModIdx];
		FModifierSpec& ModSpec = Modifiers[ModIdx];
		if (false == ModDef.ModifierMagnitude.AttemptCalculateMagnitude(...))
		{
			ModSpec.EvaluatedMagnitude = 0.f;
		}
	}
}
```

## **ModifiedAttributes**

---

**TArray<FGameplayEffectModifiedAttribute> ModifiedAttributes**

**记录哪些属性(Attribute)被GE修改了以及修改了多少**

按属性类型，统计修正值

将属性修正器配置(FGameplayModifierInfo)转换最终的修正值存放到Modifiers后，按属性进行统计，方便获取某个属性累计被修正了多少(可能存在多个修正器修正同一个属性)。

```cpp

struct GAMEPLAYABILITIES_API FGameplayEffectModifiedAttribute
{
	GENERATED_USTRUCT_BODY(
	UPROPERTY()
	FGameplayAttribute Attribute;
	UPROPERTY()
	float TotalMagnitude;
};

FActiveGameplayEffect* FActiveGameplayEffectsContainer::ApplyGameplayEffectSpec(...)
{
....
	int32 ModifierIndex = -1;
	for (const FGameplayModifierInfo& Mod : AppliedEffectSpec.Def->Modifiers)
	{
		++ModifierIndex;
	
		
		float Magnitude = 0.0f;
		if (AppliedEffectSpec.Modifiers.IsValidIndex(ModifierIndex))
		{
			const FModifierSpec& ModSpec = AppliedEffectSpec.Modifiers[ModifierIndex];
			Magnitude = ModSpec.GetEvaluatedMagnitude();
		}
		
	
		FGameplayEffectModifiedAttribute* ModifiedAttribute = 
		AppliedEffectSpec.GetModifiedAttribute(Mod.Attribute);
		
		if (!ModifiedAttribute)
		{
			ModifiedAttribute = AppliedEffectSpec.AddModifiedAttribute(Mod.Attribute);
		}
		ModifiedAttribute->TotalMagnitude += Magnitude;
	}
...
}
```

## **Duration**

---

**float Duration**

**GE实例的持续时间**(持续效果才会有持续时间配置)

在GE添加时根据配置 (DurationMagnitude)初始化持续时间 
可以在运行时直接调用SetDuration设置持续时间进行覆盖

## **Period**

---

**float Period**

**GE实例的定时触发时间**

对于周期(定时触发)效果，这个值表示每次效果触发的间隔时间

## **CapturedSourceTags**

---

**FTagContainerAggregator CapturedSourceTags**

**用于描述GE的来源**
当一个GameplayEffect被应用时，系统会自动捕获所有相关的源标签(Tag)，并存储在CapturedSourceTags中。

- GE最终是通过ASC组件赋予目标的，会捕获ASC拥有的Tag集合作为来源Tag。
- 此外GE还可能是在GA或者GE中通过ASC赋予目标的，此时还会额外捕获来源GE和来源GA的Tag作为来源Tag。
- GE还可以赋予自身Tag来标记来源

**GE赋予的来源Tag**
GE赋予的来源Tag分为两种，一种是GE赋予自身的Tag(包括DynamicAssetTag)，另一种是这个GE是通过另外一个GE赋予的，则会继承来源GE捕获的来源Tag集合(CapturedSourceTags)

```cpp
**//GE赋予自身的Tag**
void FGameplayEffectSpec::Initialize(...)
{
	CapturedSourceTags.GetSpecTags().AppendTags(Def->GetAssetTags());
}
void FGameplayEffectSpec::AddDynamicAssetTag(...)
{
	CapturedSourceTags.GetSpecTags().AddTag(TagToAdd);
}
void FGameplayEffectSpec::AppendDynamicAssetTags(...)
{
	CapturedSourceTags.GetSpecTags().AppendTags(TagsToAppend);
}

//GE是通过另外一个GE赋予的，则会继承来源GE捕获的来源Tag集合(CapturedSourceTags)
void FGameplayEffectSpec::InitializeFromLinkedSpec(const UGameplayEffect* InDef, const FGameplayEffectSpec& OriginalSpec)
{
	//复制来源GE的来源Tag集合(CapturedSourceTags),
	//会移除来源GE赋予自身的Tag,这个是独属于GE自身的
	CapturedSourceTags = OriginalSpec.CapturedSourceTags;
	CapturedSourceTags.GetSpecTags().RemoveTags(OriginalSpec.Def->GetAssetTags());

	//Initialize继续捕获GE赋予自身的Tag
	Initialize(InDef, NewContextHandle, OriginalSpec.GetLevel());
}
```

**来源GA赋予的Tag**
从GA赋予的GE会捕获GA的Tag集合作为来源Tag集合

```cpp
**//来源GA 赋予的Tag**
void UGameplayAbility::ApplyAbilityTagsToGameplayEffectSpec(...) const
{
	FGameplayTagContainer& CapturedSourceTags = Spec.CapturedSourceTags.GetSpecTags();

	CapturedSourceTags.AppendTags(AbilityTags);
}
```

**来源Actor(实际是Actor持有的ASC组件)赋予的Tag**
直接通过ASC赋予的GE,会捕获ASC拥有的Tag集合作为来源Tag集合

```cpp
**//来源Actor 赋予的Tag**
void FGameplayEffectSpec::Initialize(...)
{
...
	CaptureDataFromSource();
...
}
void FGameplayEffectSpec::CaptureDataFromSource(...)
{
...
	if (!bSkipRecaptureSourceActorTags)
	{
		RecaptureSourceActorTags();
	}
...
}

void FGameplayEffectSpec::RecaptureSourceActorTags()
{
	CapturedSourceTags.GetActorTags().Reset();
	EffectContext.GetOwnedGameplayTags(CapturedSourceTags.GetActorTags(),
 CapturedSourceTags.GetSpecTags());
}
```

> 💡 CapturedSourceTags在捕获来源Actor和来源GA Tag时只包含在GameplayEffect被应用时捕获的源标签，不包含在效果持续期间添加的标签。

## **DynamicAssetTags**

---

**FGameplayTagContainer DynamicAssetTags**

**动态添加的赋予GE自身拥有的Tag**

```cpp
void FGameplayEffectSpec::AddDynamicAssetTag(...)
{
	CapturedSourceTags.GetSpecTags().AddTag(TagToAdd);
}
void FGameplayEffectSpec::AppendDynamicAssetTags(...)
{
	CapturedSourceTags.GetSpecTags().AppendTags(TagsToAppend);
}

void FGameplayEffectSpec::GetAllAssetTags(OUT FGameplayTagContainer& OutContainer) const
{
	OutContainer.AppendTags(GetDynamicAssetTags());
	if (Def)
	{
		OutContainer.AppendTags(Def->GetAssetTags());
	}
}
```

## **CapturedTargetTags**

---

**FTagContainerAggregator CapturedTargetTags**

**用于描述GameplayEffect的目标(应用于哪个角色)**

当一个GameplayEffect被应用(Apply)时，系统会自动捕获相关的目标标签(Tag)，并存储在CapturedTargetTags中。

```cpp
**//捕获目标 Tags**
FActiveGameplayEffect* FActiveGameplayEffectsContainer::ApplyGameplayEffectSpec(...)
{
...
	AppliedEffectSpec.CapturedTargetTags.GetActorTags().Reset();
	Owner->GetOwnedGameplayTags(AppliedEffectSpec.CapturedTargetTags.GetActorTags());
...
}

void FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom(...)
{
...
	SpecToUse.CapturedTargetTags.GetActorTags().Reset();
	Owner->GetOwnedGameplayTags(SpecToUse.CapturedTargetTags.GetActorTags());
...
}
```

> 💡 注意，CapturedTargetTags只包含在GameplayEffect被应用时捕获的目标标签，不包含在效果持续期间添加的标签，定时触发的效果会在每次触发时更新捕获的目标标签。

> 💡 有了捕获的来源/目标Tag就可以在某些应有场景对GE进行匹配筛选或者产生不同的效果
>
> 比如驱散光环或者免疫光环效果 需要匹配GE是否符合需求 就可能需要用到捕获的来源/目标Tag
>
> 比如属性修正效果的修正配置可以根据捕获的来源/目标Tag决定当前修正配置是否生效
>
> 比如赋予附加效果或者技能时可以根据捕获的来源/目标Tag决定是否赋予

> 💡 **FTagContainerAggregator**是聚合标签 用于聚合和管理一组标签(Tag)容器
>
> 参照
>
> [Tag-3.0集合容器](Tag-3.0%E9%9B%86%E5%90%88%E5%AE%B9%E5%99%A8.md)

## **DynamicGrantedTags**

---

**FGameplayTagContainer DynamicGrantedTags**

**动态添加的赋予拥有者的Tag** 

会跟GE配置的GrantedTags一起添加到拥有者身上

```cpp

**//赋予**
void FActiveGameplayEffectsContainer::AddActiveGameplayEffectGrantedTagsAndModifier(...)
{
...
Owner->UpdateTagMap(Effect.Spec.Def->GetGrantedTags(), 1);
Owner->UpdateTagMap(Effect.Spec.DynamicGrantedTags, 1);

**//复制Tag**
if (ShouldUseMinimalReplication())
{
	Owner->AddMinimalReplicationGameplayTags(Effect.Spec.Def->GetGrantedTags());
	Owner->AddMinimalReplicationGameplayTags(Effect.Spec.DynamicGrantedTags);
}

...
}

**//移除**
void FActiveGameplayEffectsContainer::RemoveActiveGameplayEffectGrantedTagsAndModifiers(...)
{
...
	Owner->UpdateTagMap(Effect.Spec.Def->GetGrantedTags(), -1);
	Owner->UpdateTagMap(Effect.Spec.DynamicGrantedTags, -1);

	**//复制Tag**
	if (ShouldUseMinimalReplication())
	{
		Owner->RemoveMinimalReplicationGameplayTags(Effect.Spec.Def->GetGrantedTags());
		Owner->RemoveMinimalReplicationGameplayTags(Effect.Spec.DynamicGrantedTags);
	}

...
}

//添加动态的GrantedTag
FGameplayEffectSpecHandle UAbilitySystemBlueprintLibrary::AddGrantedTag(...)
{
	FGameplayEffectSpec* Spec = SpecHandle.Data.Get();
	if (Spec)
	{
		Spec->DynamicGrantedTags.AddTag(NewGameplayTag);
	}
	return SpecHandle;
}
```

## **StackCount**

---

**int32 StackCount**

**当前效果的堆叠数量**

## **SetByCaller**

---

**TMap<FName, float>        SetByCallerNameMagnitudes**

**TMap<FGameplayTag, float>   SetByCallerTagMagnitudes**

**通过Tag或者FName传递的变量**

> 💡 在创建GE示例时可以通过Tag或者FName传递一些参数 然后在需要的用的时候在通过Tag取出来

```cpp
void FGameplayEffectSpec::SetSetByCallerMagnitude(...)
{
	if (DataName != NAME_None)
	{
		SetByCallerNameMagnitudes.FindOrAdd(DataName) = Magnitude;
	}
}

void FGameplayEffectSpec::SetSetByCallerMagnitude(...)
{
	if (DataTag.IsValid())
	{
		SetByCallerTagMagnitudes.FindOrAdd(DataTag) = Magnitude;
	}
}

float FGameplayEffectSpec::GetSetByCallerMagnitude(...) const
{
	float Magnitude = DefaultIfNotFound;
	const float* Ptr = nullptr;
	
	if (DataName != NAME_None)
	{
		Ptr = SetByCallerNameMagnitudes.Find(DataName);
	}
	
	if (Ptr)
	{
		Magnitude = *Ptr;
	}

	return Magnitude;
}

float FGameplayEffectSpec::GetSetByCallerMagnitude(...) const
{
	float Magnitude = DefaultIfNotFound;
	const float* Ptr = nullptr;

	if (DataTag.IsValid())
	{
		Ptr = SetByCallerTagMagnitudes.Find(DataTag);
	}

	if (Ptr)
	{
		Magnitude = *Ptr;
	}

	return Magnitude;
}
```

## **Level**

---

**float Level**

**GE实例的等级**

## **EffectContext**

---

**FGameplayEffectContextHandle EffectContext**

**GE上下文信息FGameplayEffectContext的结构体封装**

存放了一个FGameplayEffectContext的智能指针 通过Handle去引用**FGameplayEffectContext**

支持网络复制

详细说明参照 [GAS-上下文信息-**GameplayEffectContext**](GAS-%E4%B8%8A%E4%B8%8B%E6%96%87%E4%BF%A1%E6%81%AF-GameplayEffectContext.md) 

# GE流程简介

---

![Untitled](http://pic.xyyxr.cn/20260504111201407.png)

> [!note]- **通过添加接口尝试添加到目标身上(Apply)**
> **UAbilitySystemComponent::ApplyGameplayEffectSpecToSelf** 


> [!note]- **先检测是否被其他GE免疫**
> **UImmunityGameplayEffectComponent/GameplayEffectApplicationQueries**

> [!note]- **再检测GE本身是否有拦截添加的配置**
> **UGameplayEffect::CanApply**

> [!note]- **对于即时效果立即执行**
> **UAbilitySystemComponent::ExecuteGameplayEffect**


- **对于持续效果添加到激活容器里等待激活FActiveGameplayEffectsContainer::ApplyGameplayEffectSpec**

- **持续效果激活与抑制(Inhibit GE存在但不生效)**
**UAbilitySystemComponent::InhibitActiveGameplayEffect**

> [!note]- **持续效果时间到了或者被其他原因中断 则需要移除GE**
> **FActiveGameplayEffectsContainer::RemoveActiveGameplayEffect**


# **赋予GE**

---

UAbilitySystemComponent::ApplyGameplayEffectSpecToSelf是赋予(Apply)GE的入口，持续效果会存放到GE激活容器(FActiveGameplayEffectsContainer)进行统一管理，即时效果则立即执行。

## **赋予判定**

---

- 赋予GE时先判定是否有免疫效果拦截该GE
- 其次判定GE自身是否有配置拦截

```cpp
 //触发GE
FActiveGameplayEffectHandle UAbilitySystemComponent::ApplyGameplayEffectSpecToSelf(...)
{

...	
//判定GE 是否可以添加

**//免疫拦截判定**
//UAbilitySystemComponent可以绑定委托 用来判定是否可以添加指定的GE
//比如是否会被其他GE的免疫组件免疫
TArray<FGameplayEffectApplicationQuery> GameplayEffectApplicationQueries
for (const FGameplayEffectApplicationQuery& ApplicationQuery : 
**GameplayEffectApplicationQueries**)

{
	const bool bAllowed = ApplicationQuery.Execute(ActiveGameplayEffects, Spec);
	if (!bAllowed)
	{
		return FActiveGameplayEffectHandle();
	}
}

**//自身GE组件 拦截判定**
if (!Spec.Def->**CanApply**(ActiveGameplayEffects, Spec))
{
	return FActiveGameplayEffectHandle();
}

...
}
 
```

## **执行赋予操作**

---

- 持续性效果添加到管理容器**FActiveGameplayEffectsContainer**

```cpp

FActiveGameplayEffectHandle UAbilitySystemComponent::ApplyGameplayEffectSpecToSelf(...)
{
...
		if (Spec.Def->DurationPolicy != EGameplayEffectDurationType::Instant ||
		 bTreatAsInfiniteDuration)
		{
			AppliedEffect = **ActiveGameplayEffects.ApplyGameplayEffectSpec**(Spec,
			 PredictionKey,
			  bFoundExistingStackableGE);
			  
			if (!AppliedEffect)
			{
				return FActiveGameplayEffectHandle();
			}
		}
...
}

```

- 即时效果(Instant) 添加成功立即执行

```cpp
FActiveGameplayEffectHandle UAbilitySystemComponent::ApplyGameplayEffectSpecToSelf(...)
{
...
	if (Spec.Def->DurationPolicy == EGameplayEffectDurationType::Instant)
	{
		ExecuteGameplayEffect(*OurCopyOfSpec, PredictionKey);
	}
...
}
```

# 持续效果流程

---

**持续效果是指具备持续时长的效果(或者是永久性)，具备周期性(定时触发)、叠加、激活、抑制(冻结)等特性。**

持续效果会再次封装成激活效果实例**(类FActiveGameplayEffect对象)**其内包含效果运行时实例FGameplayEffectSpec对象)。将激活效果实例**(类FActiveGameplayEffect对象)**添加进激活容(**FActiveGameplayEffectsContainer**)统一管理

## **FActiveGameplayEffect**

---

- 描述一个运行时的持续性效果
- 持有GE的运行时对象实例FGameplayEffectSpec
- 持有检测持续时间何时结束的计时器
- 持有检测定时触发何时执行的计时器
- 支持网络复制(FFastArraySerializerItem)

```cpp
struct GAMEPLAYABILITIES_API FActiveGameplayEffect : public FFastArraySerializerItem
{
	//唯一标识
	FActiveGameplayEffectHandle Handle;

	**//GE的运行时对象实例FGameplayEffectSpec
	UPROPERTY()
	FGameplayEffectSpec Spec;**
	
	//存放由GE 赋予的GA的Handle
	UPROPERTY()
	TArray<FGameplayAbilitySpecHandle> GrantedAbilityHandles;
	
	//开始时间
	UPROPERTY()
	float StartServerWorldTime;

	UPROPERTY(NotReplicated)
	float CachedStartServerWorldTime;

	UPROPERTY(NotReplicated)
	float StartWorldTime
	
	//是否被抑制了(暂时失效)
	UPROPERTY(NotReplicated)
	bool bIsInhibited;
	
	//检测定时触发的定时器
	FTimerHandle PeriodHandle;
	//检测过期的定时器
	FTimerHandle DurationHandle;
	
	//通过网络复制到客户端的处理
	void PreReplicatedRemove(const struct FActiveGameplayEffectsContainer &InArray);
	void PostReplicatedAdd(const struct FActiveGameplayEffectsContainer &InArray);
	void PostReplicatedChange(const struct FActiveGameplayEffectsContainer &InArray);
}
```

## **FActiveGameplayEffectsContainer**

---

- 持续效果(**FActiveGameplayEffect**)的容器
- 管理容器内持续效果的生命周期(**添加、激活、抑制、移除**)
- 管理容器内持续效果的堆叠规则
- 维护了持续效果对属性修正的计算聚合器(**FAggregator**)

> 💡
>
> **FActiveGameplayEffectsContainer** 支持网络复制(FastArray) 支持迭代器操作

```cpp
class GAMEPLAYABILITIES_API UAbilitySystemComponent
{
	**//标记为可复制的**
	UPROPERTY(Replicated)
	FActiveGameplayEffectsContainer ActiveGameplayEffects;
}
	

struct GAMEPLAYABILITIES_API FActiveGameplayEffectsContainer : 
public FFastArraySerializer
{

**//存放所有持续性GE的容器**
UPROPERTY()
TArray<FActiveGameplayEffect>	GameplayEffects_Internal;

**//属性计算的聚合器 GE对属性的影响**
TMap<FGameplayAttribute, FAggregatorRef>		AttributeAggregatorMap;

//支持迭代器
FORCEINLINE friend Iterator begin(FActiveGameplayEffectsContainer* Container)
 { return Container->CreateIterator(); }
 
FORCEINLINE friend Iterator end(FActiveGameplayEffectsContainer* Container) 
{ return Iterator(*Container, -1); }

FORCEINLINE friend ConstIterator begin(const FActiveGameplayEffectsContainer* Container)
 { return Container->CreateConstIterator(); }
 
FORCEINLINE friend ConstIterator end(const FActiveGameplayEffectsContainer* Container) 
{ return ConstIterator(*Container, -1); }
}
```

## **添加到激活容器(Apply)**

---

![Untitled](http://pic.xyyxr.cn/20260504111201408.png)

在GE通过容器添加接口(FActiveGameplayEffectsContainer::ApplyGameplayEffectSpec)尝试添加进容器时，**先判定是否存在堆叠效果，存在则按配置处理堆叠，如果不存在堆叠则会重新创建一个新的持续效果实例放入容器。**

### **堆叠判定&处理**

---

首先要做的就是判定是否存在堆叠(FindStackableActiveGameplayEffect)，存在堆叠的条件

- **配置模板Def(UGameplayEffect)相同**
- **开启了堆叠配置**
- **堆叠判定类型是AggregateByTarget 则满足配置模板相同即可**
- **堆叠判定类型是AggregateBySource 则还需要满足触发的组件(ASC)相同**

```cpp
FActiveGameplayEffect* FActiveGameplayEffectsContainer::ApplyGameplayEffectSpec(...)
{
...
	**//先查找是否有堆叠的GE**
	FActiveGameplayEffect* ExistingStackableGE = FindStackableActiveGameplayEffect(Spec);
...
}

**//堆叠判定**
FActiveGameplayEffect* FActiveGameplayEffectsContainer::FindStackableActiveGameplayEffect(...)
{
...
	**//即将添加的GE支持堆叠配置**
	if ((StackingType != EGameplayEffectStackingType::None) && 
	(GEDef->DurationPolicy != EGameplayEffectDurationType::Instant))
	{	
		**//遍历容器(容器支持迭代器)**
		for (FActiveGameplayEffect& ActiveEffect: this)
		{
			//存在堆叠的条件
			//**配置模板Def(UGameplayEffect)相同
			//堆叠判定类型是AggregateByTarget 则满足配置模板相同即可**
			**//堆叠判定类型是AggregateBySource 则还需要满足触发的组件(ASC)相同**
			if (ActiveEffect.Spec.Def == Spec.Def && 
			((StackingType == EGameplayEffectStackingType::AggregateByTarget) || 
			(SourceASC && 
			SourceASC == ActiveEffect.Spec.GetContext().GetInstigatorAbilitySystemComponent())))
			{
				StackableGE = &ActiveEffect;
				break;
			}
		}
	}

	return StackableGE;
}
```

如果判定触发了堆叠效果，则需要进行堆叠处理，不会再创建新的激活效果(FActiveGameplayEffect)实例。

- **是否堆叠溢出**(*当前堆叠数已经达到了配置的堆叠上限*)
    - **堆叠溢出时是否直接堆叠失败(***直接返回null不再往下执行了***)**
    - **堆叠溢出时是否直接堆叠失败并且移除效果(***直接返回null并移除之前附加的效果***)**
    - **堆叠溢出时是否赋予额外的效果(***不直接返回会继续执行***)**

- **如果堆叠添加成功**
    - **更新堆叠效果**
    - **根据配置决定是否刷新堆叠效果持续时间计时(***重新开始计时***)**
    - **根据配置决定是否刷新堆叠效果的定时触发计时(***重新开始计时***)**

> 💡 堆叠生效时会用新的堆叠数据(GE的运行时对象实例FGameplayEffectSpec)更新之前存在的堆叠效果,但如果效果赋予了技能，赋予的技能信息不会被覆盖。

```cpp
FActiveGameplayEffect* FActiveGameplayEffectsContainer::ApplyGameplayEffectSpec(...)
{
...
if (ExistingStackableGE)
{
		**//存在堆叠的处理**
		
		//**堆叠溢出(堆叠数超过上限了)的处理
		//是否堆叠溢出时直接堆叠失败(此处直接返回null不再往下执行了)
		//是否堆叠溢出时直接堆叠失败并且移除效果(此处直接返回null并移除之前附加的效果)
		//是否堆叠溢出赋予额外的效果(此处不直接返回会继续执行)**
		if (ExistingSpec.GetStackCount() == ExistingSpec.Def->StackLimitCount)
		{
			if (!HandleActiveGameplayEffectStackOverflow(...))
			{
				return nullptr;
			}
		}
		
		
		**//有堆叠的GE存在 则不需要重新创建新的FActiveGameplayEffect
		//更新下Spec(FGameplayEffectSpec) 但GrantedAbilitySpecs不更新**
		TArray<FGameplayAbilitySpecDef>	
		GrantedSpecTempArray(MoveTemp(ExistingStackableGE->Spec.GrantedAbilitySpecs));
		
		ExistingStackableGE->Spec = Spec;
		ExistingStackableGE->Spec.GrantedAbilitySpecs = MoveTemp(GrantedSpecTempArray);
		**//再更新堆叠数**
		ExistingStackableGE->Spec.SetStackCount(NewStackCount);
		
		//返回的**FActiveGameplayEffect 为更新之后的**ExistingStackableGE
		AppliedActiveGE = ExistingStackableGE;
		
		**//堆叠更新 是否需要刷新持续时间和定时触发时间**
		if (GEDef->StackDurationRefreshPolicy == 
		EGameplayEffectStackingDurationPolicy::NeverRefresh)
		{
			//如果堆叠规则 新增堆叠不需要刷新持续时间 则bSetDuration 设置成False
			bSetDuration = false;
		}
		else
		{
			RestartActiveGameplayEffectDuration(*ExistingStackableGE);
		}
		if (GEDef->StackPeriodResetPolicy == 
		EGameplayEffectStackingPeriodPolicy::NeverReset)
		{
			//如果堆叠规则 新增堆叠不需要刷新定时触发时间 则bSetPeriod 设置成False
			bSetPeriod = false;
		}
}
...
}

//对堆叠溢出的处理
bool FActiveGameplayEffectsContainer::HandleActiveGameplayEffectStackOverflow(...)
{
	const UGameplayEffect* StackedGE = OldSpec.Def;
	
	//是否在堆叠溢出时直接堆叠失败
	const bool bAllowOverflowApplication = !(StackedGE->bDenyOverflowApplication);

	//溢出需要赋予额外的效果
	for (TSubclassOf<UGameplayEffect> OverflowEffect : StackedGE->OverflowEffects)
	{
		if (const UGameplayEffect* CDO = OverflowEffect.GetDefaultObject())
		{
			FGameplayEffectSpec NewGESpec;
			NewGESpec.InitializeFromLinkedSpec(CDO, OverflowingSpec);
			Owner->ApplyGameplayEffectSpecToSelf(NewGESpec);
		}
	}

  //配置溢出移除GE且溢出时堆叠失败 则直接移除效果
	if (!bAllowOverflowApplication && StackedGE->bClearStackOnOverflow)
	{
		Owner->RemoveActiveGameplayEffect(ActiveStackableGE.Handle);
	}

	return bAllowOverflowApplication;
}
```

### 新增激活效果实例

---

不存在堆叠 则创建一个新的FActiveGameplayEffect放入容器FActiveGameplayEffectsContainer

```cpp
FActiveGameplayEffectsContainer::FActiveGameplayEffectsContainer()
{
	PendingGameplayEffectNext = &PendingGameplayEffectHead;
}
```

```cpp
FActiveGameplayEffect* FActiveGameplayEffectsContainer::ApplyGameplayEffectSpec(...)
{
GAMEPLAYEFFECT_SCOPE_LOCK();
...
if (ExistingStackableGE)
{
		....
}
else
{
	//创建新的FActiveGameplayEffect 并添加到容器
	
	**//先为FActiveGameplayEffect 生成一个唯一标识Handle** 
	FActiveGameplayEffectHandle NewHandle = 
	FActiveGameplayEffectHandle::GenerateNewHandle(Owner);
	

	if (ScopedLockCount > 0 && GameplayEffects_Internal.GetSlack() <= 0)
	{
		**//容器被锁定了且没有空余 则先放到一个临时队列(链表) 暂时不加入容器 (其他逻辑继续执行)**
		check(PendingGameplayEffectNext);
		if (*PendingGameplayEffectNext == nullptr)
		{
			**//链表的下一个节点 没有分配内存 则new 一个链接上**
			AppliedActiveGE = new FActiveGameplayEffect(NewHandle, 
			Spec, GetWorldTime(), GetServerWorldTime(), InPredictionKey);
			
			*PendingGameplayEffectNext = AppliedActiveGE;
		}
		else
		{
			**//下一个节点已经分配内存 直接覆盖**
			**PendingGameplayEffectNext = FActiveGameplayEffect(NewHandle, 
			Spec, GetWorldTime(), GetServerWorldTime(), InPredictionKey);
			
			AppliedActiveGE = *PendingGameplayEffectNext;
		}

		//继续准备链表的下一个节点 AppliedActiveGE->PendingNext 指向的内存
		PendingGameplayEffectNext = &AppliedActiveGE->PendingNext;
	}
	else
	{
		**//如何有空余位置 直接创建放入容器**
		AppliedActiveGE = new(GameplayEffects_Internal) FActiveGameplayEffect(NewHandle,
		 Spec, GetWorldTime(), GetServerWorldTime(), InPredictionKey);
	}
}
...
}

```

> [!note]- **容器锁**(点击展开)
> 因为容器支持迭代操作，而在迭代过程中如果出现添加/移除将会导致扩容或者交换现有元素位置，改变数组元素的内存地址会导致迭代出错
>
> 为避免这种情况会在需要的地方加上容器锁 GAMEPLAYEFFECT_SCOPE_LOCK
>
> 宏GAMEPLAYEFFECT_SCOPE_LOCK会使ScopedLockCount计数+1，在离开作用域时析构时ScopedLockCount计数-1
>
> ScopedLockCount >0 计数表明容器被锁定  不要移除或者添加(扩容)元素
> (如果添加时 容器还有空闲位置 则可以无视容器锁 因为这种操作不会影响现有元素)
>
> > 💡 在容器操作锁计数减为0时 
> >
> >     将临时链表的元素加到容器  
> >
> >     将待移除元素移除

```cpp
    //GAMEPLAYEFFECT_SCOPE_LOCK 离开作用域 触发析构 操作锁计数-1
    void FActiveGameplayEffectsContainer::DecrementLock()
    {
    
    	**//链表头**
    	FActiveGameplayEffect* PendingGameplayEffect = PendingGameplayEffectHead;
    	**//链表尾**
    	FActiveGameplayEffect* Stop = *PendingGameplayEffectNext;
    	if (--ScopedLockCount == 0)
    	{
    		while (PendingGameplayEffect != Stop)
    		{
    			if (!PendingGameplayEffect->IsPendingRemove)
    			{
    				**//添加进容器**
    				GameplayEffects_Internal.Add(MoveTemp(*PendingGameplayEffect));
    				ModifiedArray = true;
    			}
    			else
    			{
    			**//元素 已经被标记为移除了 就不用加进容器了 移除计数也可以-1**
    				PendingRemoves--;
    			}
    			PendingGameplayEffect = PendingGameplayEffect->PendingNext;
    		}
    
    	
    	 **//重置链表**
    		PendingGameplayEffectNext = &PendingGameplayEffectHead;
    
    	
    	  **//移除元素 
    	  //用**RemoveAtSwap直接交换元素位置 将移除元素放到待分配位置且不收缩容器内存
    		for (int32 idx=GameplayEffects_Internal.Num()-1; idx >= 0 && PendingRemoves > 0;
    		 --idx)
    		 
    		{
    			FActiveGameplayEffect& Effect = GameplayEffects_Internal[idx];
    
    			if (Effect.IsPendingRemove)
    			{
    				GameplayEffects_Internal.RemoveAtSwap(idx, 1, false);
    				ModifiedArray = true;
    				PendingRemoves--;
    			}
    		}
    
    		**//检验下是否移除完成了**
    		if (!ensure(PendingRemoves == 0))
    		{
    			PendingRemoves = 0;
    		}
    
    		if (ModifiedArray)
    		{
    			MarkArrayDirty();
    		}
    	}
    }
```
    

### **设置持续时间**

---

添加成功后需要设置持续时间，并启动检测计时器

- 持续时间先根据配置计算出一个基础值(BaseValue)
- 然后根据捕获持续时间修正计算出持续时间最终值
- 得到最终持续时间之后启动计时器来检查何时结束效果

```cpp
FActiveGameplayEffect* FActiveGameplayEffectsContainer::ApplyGameplayEffectSpec(...)
{
...
float DefCalcDuration = 0.f;

**//根据配置计算出来初始的持续时间**
if (AppliedEffectSpec.AttemptCalculateDurationFromDef(DefCalcDuration))
{
	AppliedEffectSpec.SetDuration(DefCalcDuration, false);
}
else if (AppliedEffectSpec.Def->DurationMagnitude.GetMagnitudeCalculationType() 
== EGameplayEffectMagnitudeCalculation::SetByCaller)
{
	AppliedEffectSpec.Def->DurationMagnitude.AttemptCalculateMagnitude(...);
}
const float DurationBaseValue = AppliedEffectSpec.GetDuration();

if (DurationBaseValue > 0.f)
{
	/**/计算最终的持续时间值
	//有可能存在其他效果修正持续时间(具体参照下面说明)**
	float FinalDuration = AppliedEffectSpec.CalculateModifiedDuration();
	....
	**//这里设置持续时间后 将会被锁定(如果被其他地方提前锁定了 则这里不会覆盖之前的设置)**
	AppliedEffectSpec.SetDuration(FinalDuration, true);
	...
	**//启动个计时器 用来检测是否持续到了该结束了
	//堆叠效果如果设置bSetDuration=False 则不重置持续时间计时器**
	if (Owner && bSetDuration)
	{
		FTimerManager& TimerManager = Owner->GetWorld()->GetTimerManager();
		FTimerDelegate Delegate = FTimerDelegate::CreateUObject(Owner, 
		&UAbilitySystemComponent::**CheckDurationExpired**, AppliedActiveGE->Handle);
		
		TimerManager.SetTimer(AppliedActiveGE->DurationHandle, Delegate, **FinalDuration**, false);
		if (!ensureMsgf(AppliedActiveGE->DurationHandle.IsValid(), TEXT("Invalid Duration Handle after attempting to set duration for GE %s @ %.2f"), 
			*AppliedActiveGE->GetDebugString(), FinalDuration))
		{
			TimerManager.SetTimerForNextTick(Delegate);
		}
	}
}

void FGameplayEffectSpec::SetDuration(float NewDuration, bool bLockDuration)
{
	**//如果被锁定了 则无法被再次修改**
	if (!bDurationLocked)
	{
		Duration = NewDuration;
		bDurationLocked = bLockDuration;
	}
}
```

在计算持续时间时，首先调用了FGameplayEffectModifierMagnitude::AttemptCalculateMagnitude根据GE的配置算出一个持续时间，然后再调用了FGameplayEffectSpec::CalculateModifiedDuration进行持续时间的修正，得出最终的持续时间。

```cpp

//根据捕获的**IngoingDuration和OutgoingDuration 检查下是否有匹配的持续时长修正效果**
float FGameplayEffectSpec::CalculateModifiedDuration() const
{
	FAggregator DurationAgg;
....
	**//最终通过聚合器计算出修正后的结果**
	return DurationAgg.EvaluateWithBase(GetDuration(), Params);
}
```

持续时间修正用到了数值计算聚合器(FAggregator)，数值计算聚合器的思路是提供一个基础值(BaseValue)和一堆修正器(Modify)，然后计算出一个最终值(详见[GE-3.0数值修正](GE-3.0%E6%95%B0%E5%80%BC%E4%BF%AE%E6%AD%A3.md))，这里的基础值就是通过GE配置算出来的一个持续时间值。那修正值又是什么呢？

考虑一个应该场景，赋予玩家一个GE效果对自身发出的某个或者某类GE的持续时间提升10%，或者对于接受到的某个或者某类GE效果的持续时间降低10%。要实现此类效果就需要用到GE持续时间修正。也就是在玩家发出或者接收到某个持续GE时，需要去玩家身上获取一个数值修正该GE的持续时间。

这里涉及到了属性捕获和数值聚合器，具体可以参照 [GE-3.0数值修正](GE-3.0%E6%95%B0%E5%80%BC%E4%BF%AE%E6%AD%A3.md)。其实现思路是在UAbilitySystemComponent 组件上放了两个字段OutgoingDuration、IncomingDuration分别代表的对发出GE持续时间的修正(OutgoingDuration)和接收GE持续时间的修正(IncomingDuration)。这两个字段被标记为系统属性字段(SystemGameplayAttribute),可以在GE配置属性修正时看到。

如果需要对GE的持续时间进行修正，就可以配置一个GE对这两个字段进行属性修正配置，这个GE的目的是提供各种对持续时间修正的修正器以供其他GE计算持续时间时捕获。

```cpp
**//UAbilitySystemComponent 用来修正持续时长的属性**
class GAMEPLAYABILITIES_API UAbilitySystemComponent 
{
	UPROPERTY(meta=(SystemGameplayAttribute="true"))
	float OutgoingDuration;
	
	UPROPERTY(meta = (SystemGameplayAttribute = "true"))
	float IncomingDuration;
}
```

![image.png](http://pic.xyyxr.cn/20260504111201409.png)

当计算GE持续时间时，会从GE的来源方捕获属性OutgoingDuration的修正，同时会从GE的接收方捕获属性IncomingDuration的修正，这里的属性捕获的目的就是为了获取这两个属性配置的修正器。拿到这些修正器之后就可以把这些捕获的修正器加到计算当前GE的持续时间的数值计算聚合器(FAggregator )算出最终的持续时间。

因为修正器支持配置来源方Tag和接收方Tag用于筛选修正器是否生效。这样就可以从捕获的修正器中根据Tag筛选出满足条件的修正器，达到对指定GE修正持续时间的目的。

```cpp

//根据捕获的**IngoingDuration和OutgoingDuration 检查下是否有匹配的持续时长修正效果**
float FGameplayEffectSpec::CalculateModifiedDuration() const
{
	FAggregator DurationAgg;

	**//从效果的来源方捕获的修正器(OutgoingDuration) 并加入聚合器中**
	const FGameplayEffectAttributeCaptureSpec* OutgoingCaptureSpec = 
	CapturedRelevantAttributes.FindCaptureSpecByDefinition
	(UAbilitySystemComponent::GetOutgoingDurationCapture(), true);
	
	if (OutgoingCaptureSpec)
	{
		OutgoingCaptureSpec->AttemptAddAggregatorModsToAggregator(DurationAgg);
	}

	**//从效果的接受方捕获的修正器(**Incomin**gDuration) 并加入聚合器中**
	const FGameplayEffectAttributeCaptureSpec* IncomingCaptureSpec = 
	CapturedRelevantAttributes.FindCaptureSpecByDefinition
	(UAbilitySystemComponent::GetIncomingDurationCapture(), true);
	
	if (IncomingCaptureSpec)
	{
		IncomingCaptureSpec->AttemptAddAggregatorModsToAggregator(DurationAgg);
	}

	**//分别匹配来源Tag和目标Tag需求 筛选修正器**
	FAggregatorEvaluateParameters Params;
	Params.SourceTags = CapturedSourceTags.GetAggregatedTags();
	Params.TargetTags = CapturedTargetTags.GetAggregatedTags();
	
	**//最终通过聚合器计算出修正后的结果**
	return DurationAgg.EvaluateWithBase(GetDuration(), Params);
}
```

UAbilitySystemComponent提供了OutgoingDuration和IncomingCaptureSpec的属性捕获接口

```cpp
**//从接受方捕获IngoingDuration(非快照 会在用的时候取当时最新的数据)**
const FGameplayEffectAttributeCaptureDefinition& UAbilitySystemComponent::
GetIncomingDurationCapture()

{
	static FGameplayEffectAttributeCaptureDefinition IncomingDurationCapture(
	GetIncomingDurationProperty(), 
	EGameplayEffectAttributeCaptureSource::**Target**, false);
	return IncomingDurationCapture;
}

**//从来源方捕获OutgoingDuration(快照 只取捕捉那一刻的数据)**
const FGameplayEffectAttributeCaptureDefinition& UAbilitySystemComponent::
GetOutgoingDurationCapture()

{
	static FGameplayEffectAttributeCaptureDefinition OutgoingDurationCapture
	(GetOutgoingDurationProperty(), EGameplayEffectAttributeCaptureSource::**Source**, true);
	return OutgoingDurationCapture;

}

//设置属性捕获
void FGameplayEffectSpec::Initialize(...)
{
...
SetupAttributeCaptureDefinitions();
...
}
void FGameplayEffectSpec::SetupAttributeCaptureDefinitions()
{
	**//如果是持续效果 则分别捕获IngoingDuration和OutgoingDuration**
	if (Def->DurationPolicy == EGameplayEffectDurationType::HasDuration)
	{
		CapturedRelevantAttributes.
		AddCaptureDefinition(UAbilitySystemComponent::GetOutgoingDurationCapture());
		
		CapturedRelevantAttributes.
		AddCaptureDefinition(UAbilitySystemComponent::GetIncomingDurationCapture());
	}
}
```

### **设置定时触发**

---

对应持续且会定时触发的GE,除了设置持续时间之外还需要设置定时触发时间(Period)

- 根据配置计算出触发间隔时间
- 启动计时器按间隔时间持续触发效果
- 如果配置了bExecutePeriodicEffectOnApplication则会在添加时就尝试首次触发(否则需要等间隔时间到了才能首次触发)

```cpp
FActiveGameplayEffect* FActiveGameplayEffectsContainer::ApplyGameplayEffectSpec(...)
{
...
	//**bSetPeriod 为True才会重置计时器**
	if (bSetPeriod &&
		 Owner && 
		(AppliedEffectSpec.GetPeriod() > UGameplayEffect::NO_PERIOD))
	{
		FTimerManager& TimerManager = Owner->GetWorld()->GetTimerManager();
		
		FTimerDelegate Delegate = FTimerDelegate::CreateUObject(Owner, 
		&UAbilitySystemComponent::ExecutePeriodicEffect, AppliedActiveGE->Handle);
			
		**//配置了添加即触发**
		if (AppliedEffectSpec.Def->bExecutePeriodicEffectOnApplication)
		{
			TimerManager.SetTimerForNextTick(Delegate);
		}

		**//启动计时器**
		TimerManager.SetTimer(AppliedActiveGE->PeriodHandle, Delegate, 
		AppliedEffectSpec.GetPeriod(), 
		true);
	}
...
}
```

### **尝试激活新增效果**

---

```cpp
FActiveGameplayEffect* FActiveGameplayEffectsContainer::ApplyGameplayEffectSpec(...)
{
...
if (ExistingStackableGE)
	{
		OnStackCountChange(*ExistingStackableGE, StartingStackCount, NewStackCount);
	}
	else
	{
	//**新增效果添加完成尝试激活效果**
		InternalOnActiveGameplayEffectAdded(*AppliedActiveGE);
	}
...
}
```

## 激活(Active)&抑制(Inhibit)

---

持续效果GE在添加(Apply)到GE激活容器之后，还需要激活GE才能真正赋予GE所带的效果，否则只是持有了GE但不会赋予GE对应的效果。而且在其生命周期内可以被反复的激活和抑制，抑制就是取消GE赋予的效果，但不会移除GE，相当于让GE暂时失效。

- **激活(Active):**应用GE所赋予的效果
- **抑制(Inhibit):**GE赋予的效果暂时失效,但不会从容器移除,可以被再次激活

![Untitled](http://pic.xyyxr.cn/20260504111201410.png)

### 尝试激活

---

首次添加到容器时，会尝试立即激活，但需要轮询先配置的组件是否有配置阻止效果激活

```cpp
void FActiveGameplayEffectsContainer::InternalOnActiveGameplayEffectAdded(...)
{

	GAMEPLAYEFFECT_SCOPE_LOCK();
	
	constexpr bool bInvokeCuesIfEnabled = false;
	**//轮询GEComponents 是否可以激活**
	const bool bActive = EffectDef->OnAddedToActiveContainer(*this, Effect);
	**//默认是冻结**
	Effect.bIsInhibited = true;
	Owner->InhibitActiveGameplayEffect(Effect.Handle, !bActive, bInvokeCuesIfEnabled);

}

**//轮询GEComponents 是否可以激活**
bool UGameplayEffect::OnAddedToActiveContainer(...) const
{
	bool bShouldBeActive = true;
	for (const UGameplayEffectComponent* GEComponent : GEComponents)
	{
		if (GEComponent)
		{
			bShouldBeActive = GEComponent->OnActiveGameplayEffectAdded(ActiveGEContainer,
			 ActiveGE) && bShouldBeActive;
		}
	}
	return bShouldBeActive;
}
```

UAbilitySystemComponent::InhibitActiveGameplayEffect是负责处理GE激活与抑制状态切换的接口。

```cpp
//激活或者抑制GE
void UAbilitySystemComponent::InhibitActiveGameplayEffect(...)
{
	**//抑制状态发生了变化**
	if (ActiveGE->bIsInhibited != bInhibit)
	{
		ActiveGE->bIsInhibited = bInhibit;

		FScopedAggregatorOnDirtyBatch	AggregatorOnDirtyBatcher;
		if (bInhibit)
		{
			**//抑制效果**
			ActiveGameplayEffects.RemoveActiveGameplayEffectGrantedTagsAndModifiers(*ActiveGE,
			 bInvokeGameplayCueEvents);
		}
		else
		{
			**//激活效果**
			ActiveGameplayEffects.AddActiveGameplayEffectGrantedTagsAndModifiers(*ActiveGE,
			 bInvokeGameplayCueEvents);
		}

		ActiveGE->EventSet.OnInhibitionChanged.Broadcast(ActiveGEHandle, 
		ActiveGE->bIsInhibited);
	}
}
```

**以GE组件UTargetTagRequirementsGameplayEffectComponent为例介绍下GE的激活与抑制切换**:

组件UTargetTagRequirementsGameplayEffectComponent可以配置OngoingTagRequirements要求GE的拥有者需要有指定的Tag或者不能有指定的Tag才能激活效果，则在GE拥有者在Tag发生变化时，需要重新评估下效果应该时激活还是抑制。

```cpp
void UTargetTagRequirementsGameplayEffectComponent::OnTagChanged(...) const
{
...
	const FActiveGameplayEffect* ActiveGE = 
Owner->GetActiveGameplayEffect(ActiveGEHandle);

	if (ensure(ActiveGE) && !ActiveGE->IsPendingRemove)
	{
		FGameplayTagContainer OwnedTags;
		Owner->GetOwnedGameplayTags(OwnedTags);

		if (bRemovalRequirementsMet)
		{
		...
		}
		else
		{
			//**OngoingTagRequirements配置用于匹配接受者身上Tag**
			**//拥有者身上的Tag满足OngoingTagRequirements配置则激活效果 
			//不满足则抑制效果
			//OngoingTagRequirements 未配置则不会出现冻结效果的情况**
			constexpr bool bInvokeCuesIfStateChanged = true;
			const bool bOngoingRequirementsMet = OngoingTagRequirements.IsEmpty() || 
			OngoingTagRequirements.RequirementsMet(OwnedTags);
			
			Owner->InhibitActiveGameplayEffect(ActiveGEHandle, 
			!bOngoingRequirementsMet, bInvokeCuesIfStateChanged);
		}
	...
	}
}
```

### 激活效果

---

**GE效果被成功激活时**:

- 对于非周期(定时触发)效果则会赋予属性修正效果(如果配置了)
- 对于周期(定时触发)效果则会根据配置重新触发定时器(根据配置决定是否重置计时器)
- 将配置的GrantedTags/DynamicGrantedTags赋予接收者
- 将配置的BlockedAbilityTags赋予接受者(用于阻拦GA)
- 将配置的GrantedAbility赋予接受者(附加的GA)
- 激活表现效果GameplayCue(如果在添加的时候激活过则不需要再激活了)

在激活效果的容器FActiveGameplayEffectsContainer维护了一个属性修正的数值计算聚合器(FAggregator)的Map，每个被修正的属性都会绑定一个聚合器(FAggregator)。聚合器包含了属性的基础值和修正值配置，当触发属性重算时，会根据属性基础值和修正配置计算出属性新的最终值
具体参照 [GE-3.0数值修正](GE-3.0%E6%95%B0%E5%80%BC%E4%BF%AE%E6%AD%A3.md) 

FActiveGameplayEffectsContainer::AddActiveGameplayEffectGrantedTagsAndModifiers负责处理GE激活的处理逻辑

```cpp
void FActiveGameplayEffectsContainer::AddActiveGameplayEffectGrantedTagsAndModifiers(...)
{
	
	GAMEPLAYEFFECT_SCOPE_LOCK();
	
	if (Effect.Spec.GetPeriod() <= UGameplayEffect::NO_PERIOD)
	{
		**//对于非周期性(定时触发)效果 则会赋予属性修正效果(如果配置了)**
		for (int32 ModIdx = 0; ModIdx < Effect.Spec.Modifiers.Num(); ++ModIdx)
		{
			//为修正属性创建计算聚合器 已经存在了就不再创建
			FAggregator* Aggregator = FindOrCreateAttributeAggregator(
			Effect.Spec.Def->Modifiers[ModIdx].Attribute).Get();
			
			if (ensure(Aggregator))
			{
				//添加修正并触发属性重算
				Aggregator->AddAggregatorMod(EvaluatedMagnitude, 
				ModInfo.ModifierOp, 
				ModInfo.EvaluationChannelSettings.GetEvaluationChannel(), 
				&ModInfo.SourceTags, &ModInfo.TargetTags, 
				Effect.PredictionKey.WasLocallyGenerated(), Effect.Handle);
				
			}
		}
	}
	else
	{
		**//根据配置决定是否重置定时触发计时器(不重置就是按之前的节奏继续执行)**
		//(抑制期间计时器不会停止 只是不会触发对应的效果)
		if (Effect.Spec.Def->PeriodicInhibitionPolicy != 
		EGameplayEffectPeriodInhibitionRemovedPolicy::NeverReset && 
		Owner && 
		Owner->IsOwnerActorAuthoritative())
		{
			FTimerManager& TimerManager = Owner->GetWorld()->GetTimerManager();
			FTimerDelegate Delegate = FTimerDelegate::CreateUObject(Owner, 
			&UAbilitySystemComponent::ExecutePeriodicEffect, Effect.Handle);
	
			//是否在激活时当即触发一次
			//这里有个问题会跟添加时当即触发 重复触发
			if (Effect.Spec.Def->PeriodicInhibitionPolicy == 
			EGameplayEffectPeriodInhibitionRemovedPolicy::ExecuteAndResetPeriod)
			{
				TimerManager.SetTimerForNextTick(Delegate);
			}
			//重置计时器
			TimerManager.SetTimer(Effect.PeriodHandle, 
			Delegate, Effect.Spec.GetPeriod(), true);
			
		}
	}

	**//更新对应的Tag**
	Owner->UpdateTagMap(Effect.Spec.Def->GetGrantedTags(), 1);
	Owner->UpdateTagMap(Effect.Spec.DynamicGrantedTags, 1);
	Owner->BlockAbilitiesWithTags(Effect.Spec.Def->GetBlockedAbilityTags());
	//需要支持网络复制的Tag
	if (ShouldUseMinimalReplication())
	{
		Owner->AddMinimalReplicationGameplayTags(Effect.Spec.Def->GetGrantedTags());
		Owner->AddMinimalReplicationGameplayTags(Effect.Spec.DynamicGrantedTags);
	}

	**//赋予额外的技能**
	if (IsNetAuthority() && !Owner->bSuppressGrantAbility)
	{
		for (FGameplayAbilitySpecDef& AbilitySpecDef : Effect.Spec.GrantedAbilitySpecs)
		{
			if (AbilitySpecDef.AssignedHandle.IsValid() == false)
			{
			...
				Owner->GiveAbility( FGameplayAbilitySpec(AbilitySpecDef,
				 Effect.Spec.GetLevel(), Effect.Handle) );
			...
			}
		}	
	}

	**//激活表现效果GameplayCue(如果在添加的时候激活过则不需要再激活了)**
	if (!Owner->bSuppressGameplayCues)
	{
		for (const FGameplayEffectCue& Cue : Effect.Spec.Def->GameplayCues)
		{
			Owner->UpdateTagMap(Cue.GameplayCueTags, 1);

			if (bInvokeGameplayCueEvents)
			{
				Owner->InvokeGameplayCueEvent(Effect.Spec, EGameplayCueEvent::OnActive);
				Owner->InvokeGameplayCueEvent(Effect.Spec, EGameplayCueEvent::WhileActive);
			}

		}
	}
}
```

### 抑制效果

---

**效果被抑制时:**

- 对于非周期(定时触发)效果则移除赋予属性修正效果(如果配置了)
- 对于周期(定时触发)效果抑制期间计时器依然生效但是不会触发效果
- 将赋予的GrantedTags/DynamicGrantedTags从接收者移除
- 将赋予的BlockedAbilityTags从接受者移除(用于阻拦GA)
- 将赋予的GrantedAbility从接受者移除(附加的GA)
- 停止表现效果GameplayCue(如果在添加的时候激活过则不需要再激活了)

> 💡 效果被移除之前也需要走一次抑制流程,通过切换到抑制状态来移除GE赋予的效果。

```cpp
void FActiveGameplayEffectsContainer::RemoveActiveGameplayEffectGrantedTagsAndModifiers(...)
{
	**//从属性计算聚合器移除本效果赋予的修正 并触发属性重算**
	if (Effect.Spec.GetPeriod() <= UGameplayEffect::NO_PERIOD)
	{
		for(const FGameplayModifierInfo& Mod : Effect.Spec.Def->Modifiers)
		{
			if(Mod.Attribute.IsValid())
			{
				FAggregatorRef* RefPtr = AttributeAggregatorMap.Find(Mod.Attribute);
				if(RefPtr)
				{
					RefPtr->Get()->RemoveAggregatorMod(Effect.Handle);
				}
			}
		}
	}

	**// 移除对应的Tag**
	Owner->UpdateTagMap(Effect.Spec.Def->GetGrantedTags(), -1);
	Owner->UpdateTagMap(Effect.Spec.DynamicGrantedTags, -1);
	Owner->UnBlockAbilitiesWithTags(Effect.Spec.Def->GetBlockedAbilityTags());
	if (ShouldUseMinimalReplication())
	{
		Owner->RemoveMinimalReplicationGameplayTags(Effect.Spec.Def->GetGrantedTags());
		Owner->RemoveMinimalReplicationGameplayTags(Effect.Spec.DynamicGrantedTags);
	}

	**//移除赋予的技能**
	if (IsNetAuthority())
	{
		for (const FGameplayAbilitySpecDef& AbilitySpecDef : Effect.Spec.GrantedAbilitySpecs)
		{
			if (AbilitySpecDef.AssignedHandle.IsValid())
			{
				switch(AbilitySpecDef.RemovalPolicy)
				{
				case EGameplayEffectGrantedAbilityRemovePolicy::CancelAbilityImmediately:
					{
						Owner->ClearAbility(AbilitySpecDef.AssignedHandle);
						break;
					}
				case EGameplayEffectGrantedAbilityRemovePolicy::RemoveAbilityOnEnd:
					{
						Owner->SetRemoveAbilityOnEnd(AbilitySpecDef.AssignedHandle);
						break;
					}
				default:
					{
						// Do nothing to granted ability
						break;
					}
				}
			}
		}
	}

	**//停止表现效果**
	if (!Owner->bSuppressGameplayCues)
	{
		for (const FGameplayEffectCue& Cue : Effect.Spec.Def->GameplayCues)
		{
			Owner->UpdateTagMap(Cue.GameplayCueTags, -1);

			if (bInvokeGameplayCueEvents)
			{
				Owner->InvokeGameplayCueEvent(Effect.Spec, EGameplayCueEvent::Removed);
			}
		}
	}
}
```

## 定时触发

---

- 定时触发效果在首次激活或者冻结后再次激活时会启动一个计时器定时执行操作。触发间隔为配置的触发时间**Period**
- 定时触发效果本质上就是重复执行一个即时效果。最终跟即时效果调用的是同一处理函数**ExecuteActiveEffectsFrom**
- 定时触发效果在抑制期间 不会执行效果触发

**计时器启动**

```cpp
void FActiveGameplayEffectsContainer::InternalExecutePeriodicGameplayEffect(...)
{
...
FTimerManager& TimerManager = Owner->GetWorld()->GetTimerManager();
FTimerDelegate Delegate = FTimerDelegate::CreateUObject(Owner, 
&UAbilitySystemComponent::ExecutePeriodicEffect, Effect.Handle);
if (Effect.Spec.Def->PeriodicInhibitionPolicy == 
EGameplayEffectPeriodInhibitionRemovedPolicy::ExecuteAndResetPeriod)

{
	TimerManager.SetTimerForNextTick(Delegate);
}
TimerManager.SetTimer(Effect.PeriodHandle, Delegate, Effect.Spec.GetPeriod(), true);
...
}
```

**跟即时效果调用同一触发接口**

```cpp
//**即时效果**的处理流程
FActiveGameplayEffectHandle UAbilitySystemComponent::ApplyGameplayEffectSpecToSelf(...)
{
...
	if (bTreatAsInfiniteDuration)
	{
	...
	}
	else if (Spec.Def->DurationPolicy == EGameplayEffectDurationType::Instant)
	{
		ExecuteGameplayEffect(*OurCopyOfSpec, PredictionKey);
	}
...
}
void UAbilitySystemComponent::ExecuteGameplayEffect(...)
{
...
	ActiveGameplayEffects.ExecuteActiveEffectsFrom(Spec, PredictionKey);
...
}

//**定时触发效果**执行流程
void FActiveGameplayEffectsContainer::InternalExecutePeriodicGameplayEffect(...)
{
...
//定时触发效果 在冻结期间 不会执行效果触发
if (!ActiveEffect.bIsInhibited)
{
	ExecuteActiveEffectsFrom(ActiveEffect.Spec);
}
...
}
```

## 移除

---

- 持续效果在持续时间到了后会触发移除
- 被其他原因强制移除
- 触发移除时如果容器被锁定了则先标记为待删除接触锁定后再统一移除(*参照上面容器锁说明*)

### 持续时间触发移除

---

持续时间到了，对于效果有多种策略:

- 直接移除
- 堆叠数-1 重置持续时间 堆叠数减为0则移除
- 仅刷新时间(实际就是个永久效果了)

> 💡 持续时间到了导致效果移除的在移除前会移除定时触发的计时器，在移除前如果触发时间也满足了并且处于激活状态会触发最后一次。

```cpp
//检测持续时间
void FActiveGameplayEffectsContainer::CheckDuration(FActiveGameplayEffectHandle Handle)
{
...
for (int32 ActiveGEIdx = 0; ActiveGEIdx < GameplayEffects_Internal.Num(); ++ActiveGEIdx)
	{
		FActiveGameplayEffect& Effect = GameplayEffects_Internal[ActiveGEIdx];
		if (Effect.Handle == Handle)
		{
			if (Effect.IsPendingRemove)
			{
				//待移除的 不用处理了
				break;
			}

			//持续时间到了
			if (Duration > 0.f && 
(((Effect.StartWorldTime + Duration) < CurrentTime) || 
FMath::IsNearlyZero(CurrentTime - Duration - Effect.StartWorldTime, KINDA_SMALL_NUMBER)))
			{
				
				switch(Effect.Spec.Def->GetStackExpirationPolicy())
				{
				//时间到了直接移除
				case EGameplayEffectStackingExpirationPolicy::ClearEntireStack:
					StacksToRemove = -1; // Remove all stacks
					CheckForFinalPeriodicExec = true;					
					break;
				//堆叠数-1 重置持续时间
				case EGameplayEffectStackingExpirationPolicy::RemoveSingleStackAndRefreshDuration:
					
					StacksToRemove = 1;
					CheckForFinalPeriodicExec = (Effect.Spec.GetStackCount() == 1);
					RefreshStartTime = true;
					RefreshDurationTimer = true;
					break;
				 //仅重置时间
				case EGameplayEffectStackingExpirationPolicy::RefreshDuration:
					RefreshStartTime = true;
					RefreshDurationTimer = true;
					break;
				};					
			}
			else
			{
				//时间尚未到 需要再次根据剩余时间启动一次计时器
				//（可能是计时器起点后，持续时间发生了变化）
				RefreshDurationTimer = true;
			}

			
			//检测下 移除前是否还需要执行下最后一次定时触发
			//（处于激活状态且定时触发的时间也到了）
			if (CheckForFinalPeriodicExec)
			{
				if (Effect.PeriodHandle.IsValid() && 
TimerManager.TimerExists(Effect.PeriodHandle))
				{
					float PeriodTimeRemaining = TimerManager.GetTimerRemaining(Effect.PeriodHandle);
					if (PeriodTimeRemaining <= KINDA_SMALL_NUMBER && !Effect.bIsInhibited)
					{
						InternalExecutePeriodicGameplayEffect(Effect);

						if ( Effect.IsPendingRemove )
						{
							break;
						}
					}

					TimerManager.ClearTimer(Effect.PeriodHandle);
				}
			}

			//移除操作
			if (StacksToRemove >= -1)
			{
				InternalRemoveActiveGameplayEffect(ActiveGEIdx, StacksToRemove, false);
			}

			//重置持续时间
			if (RefreshStartTime)
			{
				RestartActiveGameplayEffectDuration(Effect);
			}

			if (RefreshDurationTimer)
			{
				FTimerDelegate Delegate = FTimerDelegate::CreateUObject(Owner, 
				&UAbilitySystemComponent::CheckDurationExpired, Effect.Handle);

				float NewTimerDuration = (Effect.StartWorldTime + Duration) - CurrentTime;
				TimerManager.SetTimer(Effect.DurationHandle, Delegate, NewTimerDuration, false);

				if (Effect.DurationHandle.IsValid() == false)
				{
					if (!Effect.IsPendingRemove)
					{
						InternalRemoveActiveGameplayEffect(ActiveGEIdx, -1, false);
					}
					check(Effect.IsPendingRemove);
				}
			}

			break;
...
}
```

### 执行移除操作

---

移除操作可能是直接把GE移除或者只是减堆叠数(*传入的堆叠数为-1或者大于现有堆叠数 则直接移除*)

直接移除的处理:

- 执行抑制逻辑移除GE赋予的效果
- 清除定时触发的计时器和持续时间计时器
- 标记为待移除状态
- 如果容器被锁定 则待移除计数+1 等解锁后再统一从容器移除

```cpp
bool FActiveGameplayEffectsContainer::InternalRemoveActiveGameplayEffect(...)
{
	//容器是否被锁定
	bool IsLocked = (ScopedLockCount > 0);	

	if (ensure(Idx < GetNumGameplayEffects()))
	{
		FActiveGameplayEffect& Effect = *GetActiveGameplayEffect(Idx);
		if (!ensure(!Effect.IsPendingRemove))
		{
	   //已经是待移除状态了
			return true;
		}

		if (StacksToRemove > 0 && Effect.Spec.GetStackCount() > StacksToRemove)
		{
			//只是减堆叠数 不移除
			int32 StartingStackCount = Effect.Spec.GetStackCount();
			Effect.Spec.SetStackCount(StartingStackCount - StacksToRemove);
			OnStackCountChange(Effect, StartingStackCount, Effect.Spec.GetStackCount());
			return false;
		}

		
		//执行移除前的处理
		//取消效果激活 标记效果为待移除
		InternalOnActiveGameplayEffectRemoved(Effect,
		 ShouldInvokeGameplayCueEvent, GameplayEffectRemovalInfo);

		//清除定时触发的计时器和持续时间计时器
		if (UWorld* World = Owner->GetWorld())
		{
			if (Effect.DurationHandle.IsValid())
			{
				World->GetTimerManager().ClearTimer(Effect.DurationHandle);
			}
			if (Effect.PeriodHandle.IsValid())
			{
				World->GetTimerManager().ClearTimer(Effect.PeriodHandle);
			}
		}

		//移除
		if (IsLocked)
		{
			//锁定了 待移除计数+1 解锁后统一移除
			PendingRemoves++;
		}
		else
		{
			//未锁定直接移除
			check(Idx < GameplayEffects_Internal.Num());

			GameplayEffects_Internal.RemoveAtSwap(Idx);
			ModifiedArray = true;
		}

	
		
		return ModifiedArray;
	}
	return false;
}
```

```cpp
void FActiveGameplayEffectsContainer::InternalOnActiveGameplayEffectRemoved(...)
{
	
	//标记效果为待移除状态
	Effect.IsPendingRemove = true;

	//取消效果激活状态(抑制)
	if (Effect.Spec.Def)
	{
		if (!Effect.bIsInhibited)
		{
			RemoveActiveGameplayEffectGrantedTagsAndModifiers(Effect, bInvokeGameplayCueEvents);
		}
	}

	//委托通知
	Effect.EventSet.OnEffectRemoved.Broadcast(GameplayEffectRemovalInfo);

	OnActiveGameplayEffectRemovedDelegate.Broadcast(Effect);
}
```

## GameplayCue添加&移除

---

GameplayCue主要是用来触发客户端表现效果，比如特效，音效、材质效果之类的。如果GE效果想要搭配一些客户端表现效果，可以在GE配置对应的GameplayCue(通过绑定GameplayCue对应的Tag)。

**持续效果会在效果激活时激活配置的GameplayCue。在效果抑制或者移除时也会移除对应的GameplayCue**

**效果激活时激活配置的GameplayCue**

```cpp
void FActiveGameplayEffectsContainer::AddActiveGameplayEffectGrantedTagsAndModifiers(...)
{
...
// Update GameplayCue tags and events
	if (!Owner->bSuppressGameplayCues)
	{
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
					Owner->AddGameplayCue_MinimalReplication(CueTag, Effect.Spec.GetEffectContext());
				}
			}
		}
	}
...
}
```

**效果抑制或者移除时移除对应的GameplayCue**

```cpp
void FActiveGameplayEffectsContainer::RemoveActiveGameplayEffectGrantedTagsAndModifiers(..)
{
...
if (!Owner->bSuppressGameplayCues)
	{
		for (const FGameplayEffectCue& Cue : Effect.Spec.Def->GameplayCues)
		{
			Owner->UpdateTagMap(Cue.GameplayCueTags, -1);

			if (bInvokeGameplayCueEvents)
			{
				Owner->InvokeGameplayCueEvent(Effect.Spec, EGameplayCueEvent::Removed);
			}

			if (ShouldUseMinimalReplication())
			{
				for (const FGameplayTag& CueTag : Cue.GameplayCueTags)
				{
					Owner->RemoveGameplayCue_MinimalReplication(CueTag);
				}
			}
		}
	}
...
}
```

# 即时效果流程

---

即时效果(Instant)在添加(Apply)成功后直接执行ExecuteGameplayEffect触发GE效果，然后当帧就结束了，是一个即时操作，非持续行为，也不会添加激活效果容器FActiveGameplayEffectsContainer中。

## 添加成功立即执行

---

```cpp

FActiveGameplayEffectHandle UAbilitySystemComponent::ApplyGameplayEffectSpecToSelf(...)
{
...
	if (Spec.Def->DurationPolicy == EGameplayEffectDurationType::Instant)
		{
			ExecuteGameplayEffect(*OurCopyOfSpec, PredictionKey);
		}
...
}
```

## 执行属性修正

---

即时效果可以对属性进行一次性修正，与持续效果不同，持续效果修正的是属性在效果解除时修正的部分会被回退恢复到修正之前值(属性的**CurrentValue**不会影响基础值**BaseValue**)。即时效果直接修改的是属性基础值BaseValue(修改Base值会触发属性重新计算)，无法回退。

一般用于修改一些类似当前血量之类的即时属性，或者某些情况下需要覆写修正属性的基础值(**BaseValue**)。

```cpp
void FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom(...)
{
...
	SpecToUse.CalculateModifierMagnitudes();
	bool ModifierSuccessfullyExecuted = false;

	**//这里直接对属性的Base值进行修正**
	for (int32 ModIdx = 0; ModIdx < SpecToUse.Modifiers.Num(); ++ModIdx)
	{
		const FGameplayModifierInfo& ModDef = SpecToUse.Def->Modifiers[ModIdx];
		FGameplayModifierEvaluatedData EvalData(ModDef.Attribute, 
		ModDef.ModifierOp, SpecToUse.GetModifierMagnitude(ModIdx, true));
		
		ModifierSuccessfullyExecuted |= InternalExecuteMod(SpecToUse, EvalData);
	}

...
}
```

## 执行自定义效果执行类

---

除了属性修正等直接配置的效果，还可以执行一些定制的效果比如伤害、治疗之类。配置自定义效果执行类**(UGameplayEffectExecutionCalculation)。**重载基类的执行接口(**Execute**)，在里面可以定制你需要的各种千奇百怪的效果。

> 💡
>
> 只有即时效果(Instant)和定时触发效果才支持自定义效果
>
> (*定时触发效果本质上就是重复触发即时效果)*

> 💡 执行自定义效果时还可以附加额外的效果

```cpp
void FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom(...)
{
...
	for (const FGameplayEffectExecutionDefinition& CurExecDef : 
	SpecToUse.Def->Executions)
	
	{
		if (CurExecDef.CalculationClass)
		{
		...
			FGameplayEffectCustomExecutionParameters ExecutionParams(SpecToUse,
			 CurExecDef.CalculationModifiers, Owner, CurExecDef.PassedInTags, PredictionKey);
			 
			FGameplayEffectCustomExecutionOutput ExecutionOutput;
			**//执行效果**
			**ExecCDO->Execute(ExecutionParams, ExecutionOutput);**
			
			bRunConditionalEffects = ExecutionOutput.ShouldTriggerConditionalGameplayEffects();
			
			**//收集需要附加的额外效果**
			if (bRunConditionalEffects)
			{
				for (const FConditionalGameplayEffect& ConditionalEffect :
				 CurExecDef.ConditionalGameplayEffects)
				 
				{
					if (ConditionalEffect.CanApply(SpecToUse.CapturedSourceTags.GetActorTags(),
					 SpecToUse.GetLevel()))
					 
					{
						FGameplayEffectSpecHandle SpecHandle = ConditionalEffect.CreateSpec(
						SpecToUse.GetEffectContext(), 
						SpecToUse.GetLevel());
						
						if (SpecHandle.IsValid())
						{
							ConditionalEffectSpecs.Add(SpecHandle);
						}
					}
				}
			}
		...
			}
	}
	
	
	
	//赋予额外的效果
	for (const FGameplayEffectSpecHandle& TargetSpec : ConditionalEffectSpecs)
	{
		if (TargetSpec.IsValid())
		{
			Owner->ApplyGameplayEffectSpecToSelf(*TargetSpec.Data.Get(), PredictionKey);
		}
	}
...
}
```

## 执行表现效果GameplayCue

---

即时效果触发的GameplayCue 执行的是Execute接口

```cpp
void FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom(...)
{
	if (InvokeGameplayCueExecute && SpecToUse.Def->GameplayCues.Num())
	{
		UAbilitySystemGlobals::Get().GetGameplayCueManager()->
		InvokeGameplayCueExecuted_FromSpec(Owner, SpecToUse, PredictionKey);
		
	}
}

```