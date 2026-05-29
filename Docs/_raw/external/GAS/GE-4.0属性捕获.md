> 💡 **本系列文章基于UE5.3**

# 概述

---

属性捕获(**AttributeCapture)**是指在GE被添加(Apply)时(持续效果)，捕获并保存一些相关属性数值计

算聚合器FAggregator，再根据捕获的属性去计算新的数值(比如根据力量属性修正计算出攻击力属性

的修正值)。

属性捕获区分是否是快照捕获，快照捕获则创建一份属性聚合器的快照 (复制副本)，非快照则持有一

份属性聚合器的引用(封装的共享指针版本FAggregatorRef)

# 相关数据结构

---

**FGameplayEffectAttributeCaptureDefinition**

**定义需要捕获的属性以及捕获的方式**

属性捕获配置

![image.png](http://pic.xyyxr.cn/20260504111203365.png)

```cpp
//**定义需要捕获的属性以及捕获的方式**
struct GAMEPLAYABILITIES_API FGameplayEffectAttributeCaptureDefinition
{
	//捕获的属性类型
	UPROPERTY(EditDefaultsOnly, Category=Capture)
	FGameplayAttribute AttributeToCapture;

	//属性来源 是捕捉GE的来源者还是接收者
	UPROPERTY(EditDefaultsOnly, Category=Capture)
	EGameplayEffectAttributeCaptureSource AttributeSource;

	//是否是快照 快照则值会保留捕获时候的数值 后续发生变化也不会影响快照
	UPROPERTY(EditDefaultsOnly, Category=Capture)
	bool bSnapshot;
}
```

**FGameplayEffectAttributeCaptureSpec
属性捕获的运行时数据**

根据属性捕获配置找到对应的聚合器FAggregator)

```cpp

//**属性捕捉的运行时数据 根据定义捕获并保存属性的值**
struct GAMEPLAYABILITIES_API FGameplayEffectAttributeCaptureSpec
{
	//拷贝的属性捕获配置信息
	UPROPERTY()
	FGameplayEffectAttributeCaptureDefinition BackingDefinition;

	//捕获属性对应的属性计算聚合器引用(快照捕获会创建一个新的再拷贝)
	FAggregatorRef AttributeAggregator;
}
```

**FGameplayEffectAttributeCaptureSpecContainer**

**属性捕获容器** 

统一管理属性捕获

```cpp
//**属性捕获容器**
//属性类型相同 捕获来源相同 是否快照配置相同 则认为是同一捕获配置 容器中保留一份即可
struct GAMEPLAYABILITIES_API FGameplayEffectAttributeCaptureSpecContainer
{
	
	//存放 捕获GE来源者的属性捕获集合
	UPROPERTY()
	TArray<FGameplayEffectAttributeCaptureSpec> SourceAttributes;

	//存放 捕获GE接收方的属性捕获集合
	UPROPERTY()
	TArray<FGameplayEffectAttributeCaptureSpec> TargetAttributes;

	//是否存在 非快照的属性捕获
	UPROPERTY()
	bool bHasNonSnapshottedAttributes;
}
```

# **捕获流程**

---

要捕获一个属性,首先要收集GE都有哪些地方用到了属性捕获，在GE的运行时数据FGameplayEffectSpec初始化时，会通过FGameplayEffectSpec::SetupAttributeCaptureDefinition收集用到属性捕获的配置，根据属性捕获配置去效果激活容器FActiveGameplayEffectsContainer里查找到对应的属性聚合器，如果是快照捕获则创建一个聚合器复制副本，如果是非快照捕获则持有聚合器引用。

## **收集属性捕获信息**

---

支持属性捕获的有:

- 持续时间修正
- 属性修正配置
- 自定义效果执行类的输入数据配置

```cpp
//在GE的FGameplayEffectSpec初始化时 收集所有定义了属性捕获的配置信息 
//放入属性捕获容器 FGameplayEffectAttributeCaptureSpecContainer
void FGameplayEffectSpec::SetupAttributeCaptureDefinitions()
{
if (Def->DurationPolicy == EGameplayEffectDurationType::HasDuration)
	{
//持续时间会受UAbilitySystemComponent的两个属性
//OutgoingDuration和IncomingDuration两个属性影响。
//所以对于持续效果需要捕获这两个属性
		CapturedRelevantAttributes.AddCaptureDefinition
(UAbilitySystemComponent::GetOutgoingDurationCapture());

		CapturedRelevantAttributes.AddCaptureDefinition
(UAbilitySystemComponent::GetIncomingDurationCapture());
	}

	TArray<FGameplayEffectAttributeCaptureDefinition> CaptureDefs;

	
	{
//持续时间配置支持从属性捕获获取计算值，所以如果持续时间的配置了属性捕获，需要捕获对应的属性
		CaptureDefs.Reset();
		Def->DurationMagnitude.GetAttributeCaptureDefinitions(CaptureDefs);
		for (const FGameplayEffectAttributeCaptureDefinition& CurDurationCaptureDef :
		 CaptureDefs)
		 
		{
			CapturedRelevantAttributes.AddCaptureDefinition(CurDurationCaptureDef);
		}
	}

	// 属性修正配置支持属性捕获配置，如果配置了属性捕获，需要捕获对应的属性
	for (int32 ModIdx = 0; ModIdx < Modifiers.Num(); ++ModIdx)
	{
		const FGameplayModifierInfo& ModDef = Def->Modifiers[ModIdx];
		const FModifierSpec& ModSpec = Modifiers[ModIdx];

		CaptureDefs.Reset();
		ModDef.ModifierMagnitude.GetAttributeCaptureDefinitions(CaptureDefs);
		
		for (const FGameplayEffectAttributeCaptureDefinition& CurCaptureDef : CaptureDefs)
		{
			CapturedRelevantAttributes.AddCaptureDefinition(CurCaptureDef);
		}
	}

	//自定义效果的参数传递配置支持属性捕获配置，如果配置了属性捕获，需要捕获对应的属性
	for (const FGameplayEffectExecutionDefinition& Exec : Def->Executions)
	{
		CaptureDefs.Reset();
		Exec.GetAttributeCaptureDefinitions(CaptureDefs);
	for (const FGameplayEffectAttributeCaptureDefinition& CurExecCaptureDef : CaptureDefs)
		{
			CapturedRelevantAttributes.AddCaptureDefinition(CurExecCaptureDef);
		}
	}
}
```

## **执行捕获操作**

---

遍历属性捕获容器(FGameplayEffectAttributeCaptureSpecContainer)收集到的属性捕获，为每个属性捕获执行捕获操作

捕获操作实际就是找到激活效果容器(FActiveGameplayEffectsContainer),根据捕获的目标是GE的来源方还是GE的接受方,找到对应的效果激活容器，激活容器存放属性聚合器Map，根据配置查找到对应计算聚合器(FAggregato),持有一份聚合器的引用或者创建快照(副本)

```cpp
//根据捕获的目标(是GE的来源方还是GE的接受方)遍历属性捕获容器
//(**FGameplayEffectAttributeCaptureSpecContainer**)收集到的属性捕获，
//为每个属性捕获执行捕获操作**(CaptureAttributeForGameplayEffect**)
void FGameplayEffectAttributeCaptureSpecContainer::CaptureAttributes(...)
{
	if (InAbilitySystemComponent)
	{
		const bool bSourceComponent = (InCaptureSource ==
		 EGameplayEffectAttributeCaptureSource::Source);
		 
		TArray<FGameplayEffectAttributeCaptureSpec>& AttributeArray = 
		(bSourceComponent ? SourceAttributes : TargetAttributes);

		for (FGameplayEffectAttributeCaptureSpec& CurCaptureSpec : AttributeArray)
		{
			InAbilitySystemComponent->CaptureAttributeForGameplayEffect(CurCaptureSpec);
		}
	}
}
```

```cpp
//捕获操作(**CaptureAttributeForGameplayEffect**)
//实际就是找到激活效果容器(FActiveGameplayEffectsContainer)
//存放属性属性的Map根据属性查找到对应计算聚合器(FAggregato),
//持有一份聚合器的引用或者创建快照(副本)再持有快照的引用
void FActiveGameplayEffectsContainer::CaptureAttributeForGameplayEffect(...)
{
	FAggregatorRef& AttributeAggregator = 
FindOrCreateAttributeAggregator
(OutCaptureSpec.BackingDefinition.AttributeToCapture);
	
	if (OutCaptureSpec.BackingDefinition.bSnapshot)
	{
		OutCaptureSpec.AttributeAggregator.TakeSnapshotOf(AttributeAggregator);
	}
	else
	{
		OutCaptureSpec.AttributeAggregator = AttributeAggregator;
	}
}
```

## 计算属性捕获值

---

有了属性修正的聚合器(**FAggregator**)引用,就可以通过聚合器获取对应的数值

```cpp
//获取最终值
bool AttemptCalculateAttributeMagnitude(...) const;
//根据指定通道获取最终值
bool AttemptCalculateAttributeMagnitudeUpToChannel(...) const;
//根据传入的Base获取最终值
bool AttemptCalculateAttributeMagnitudeWithBase(...) const;
//获取BaseValue
bool AttemptCalculateAttributeBaseValue(...) const;
//获取提升值 最终值-BaseValue
bool AttemptCalculateAttributeBonusMagnitude(...) const;

```

```cpp
bool FGameplayEffectAttributeCaptureSpec::AttemptCalculateAttributeMagnitude(...) const
{
	FAggregator* Agg = AttributeAggregator.Get();
	if (Agg)
	{
		OutMagnitude = Agg->Evaluate(InEvalParams);
		return true;
	}

	return false;
}
```