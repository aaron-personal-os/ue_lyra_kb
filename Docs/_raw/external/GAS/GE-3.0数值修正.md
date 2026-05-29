> 💡 **本系列文章基于UE5.3**

# 概述

---

GAS系统提供了一套数值计算机制，这套机制通过一个数值计算聚合器(**FAggregator**)来计算被多个修正器修正的数值的最终数值，**FAggregator**记录了数值的基础值(BaseValue)、修正值(Magnitude) 、修正方式(加、乘、除、覆盖)三部分，支持多种数值计算方式。

GE的属性修正就是通过这套机制进行计算的，每个修正的属性都绑定了一个数值计算聚合器(**FAggregator**)，对于非属性的数值同样适用，只是需要用一个Key将数值跟聚合器(**FAggregator**)进行关联，比如通过Tag关联。

FAggregator计算最终值的公式:

**FinalValue=((BaseValue + PreAdditive)*MultiplicitiveAdditive) / Division*MultiplicitiveComposite+PostAdditive**

> 💡
>
> PreAdditive是前置加法修正值的累计值 [P1+P2]
>
> MultiplicitiveAdditive是乘法修正值累计值(累计多个配置系数用加法 [1+(P1-1)+(P2-1)] )]
>
> MultiplicitiveComposite是乘法修正值累计值(累计多个配置系数用乘法 P1*P2]
>
> Division是除法修正值的累计值(累计多个配置系数用加法 [1+(P1-1)+(P2-1)] )
>
> PreAdditive是后置加法修正值的累计值 [P1+P2]

上面的公式是版本5.5的优化版本，5.3的版本是
FinalValue=((BaseValue + Additive)*Multiplicitive) / Division

还有种特殊得计算方式：覆盖(Override)

**最终值=修正值**(覆盖)
存在多个，则取第一个生效的

数值计算聚合器(**FAggregator**)是运行时的数据结构，运行时会将配置的修正数据进行计算、整合、分类放入聚合器(FAggregator)的修正器，这里的修正器记录的是修正方式和根据配置计算出来的修正值。 

数值修正的配置还需要一套额外的数据结构，用来配置修正值的来源(*直接设置、根据GE等级映射、基于捕获属性、外部传入、自定义计算规则等*)，不同的应该场景修正配置结构有些差异。

数值修正配置主要是定义:

- **要修正什么类型的值**(属性、持续时间、自定义效果执行类输入数值)
- **通过什么方式修正**(加、乘、除、覆盖 )
- **修正值怎么算出来**(直接设置、根据等级映射、根据指定属性计算、外部传入、自定义计算规则)

目前应用数值修正配置的场景主要有:属性修正、自定义效果执行类(UGameplayEffectExecutionCalculation)输入数值、持续时间配置。

**FGameplayEffectModifierMagnitude**是修正值配置，定义修正值应从什么途径获取，采用什么计算规则进行计算。

属性修正的数值修正配置:**FGameplayModifierInfo**

自定义效果数值修正配置:**FGameplayEffectExecutionScopedModifierInfo**

以上两者都包含了修正值配置FGameplayEffectModifierMagnitude

持续时间修正配置直接用FGameplayEffectModifierMagnitude

# 修正值配置

---

**修正值配置(FGameplayEffectModifierMagnitude)的计算方式分为以下几种**:

- **ScalableFloat** 直接设置固定值或者配置CurveTable根据等级映射一个值
- **AttributeBased** 基于指定的属性值再根据公式和配置计算出一个新的值
- **CustomCalculationClass** 自定义修正值的计算方式
- **SetByCaller** 创建GE时通过Tag或者FName传入一个值 计算时再通过Tag或者FName取出

修正值的计算方式分为:

- **ScalableFloat 
直接设置固定值或者配置CurveTable根据等级映射一个值**
- **AttributeBased 
基于指定的属性值再根据公式和配置计算出一个新的值**
- **CustomCalculationClass 
自定义修正值的计算方式**
- **SetByCaller 
创建GE时通过Tag或者FName传入一个值 计算时再通过Tag或者FName取出**

```cpp
struct GAMEPLAYABILITIES_API FGameplayEffectModifierMagnitude
{
		**//修正值的计算方式 
		//ScalableFloat  
		//AttributeBased 
		//CustomCalculationClass 
		//SetByCaller**
		EGameplayEffectMagnitudeCalculation MagnitudeCalculationType;
	
		**//来源是ScalableFloat的配置**
		FScalableFloat ScalableFloatMagnitude;
		
		**//来源是 AttributeBased 的配置**
		FAttributeBasedFloat AttributeBasedMagnitude;
		
		**//来源是 CustomCalculationClass 的配置**
		FCustomCalculationBasedFloat CustomMagnitude;
		
		**//来源是 SetByCaller的配置**
		FSetByCallerFloat SetByCallerMagnitude;
	}

```

### **ScalableFloat**

---

**直接设置固定值或者配置CurveTable根据等级映射一个值**

对应数据结构:**FScalableFloat** 

计算方法
**FScalableFloat::GetValueAtLevel**

> 💡 FScalableFloat的数据结构有一个初始值  一个CurveTable  设定一个初始值 如果配置了CurveTable([CurveTable说明](https://docs.unrealengine.com/4.27/zh-CN/InteractiveExperiences/DataDriven/)) 则
> **修正值=根据等级读取CurveTable对应的值*初始值**
>
> 没配置CurveTable就**直接用设定的初始值**
>
> **CurveTable 可以是直接配置的曲线 也可以是根据CSV文件导入进来的**

![Untitled](http://pic.xyyxr.cn/20260504111201411.png)

![Untitled](http://pic.xyyxr.cn/20260504111201412.png)

```cpp
float FScalableFloat::GetValueAtLevel(float Level, const FString* ContextString) const
{
	float OutFloat;
	const FRealCurve* FoundCurve;
	static const FString DefaultContextString = TEXT("FScalableFloat::GetValueAtLevel");

	**//根据等级映射一个对应的值**
	EvaluateCurveAtLevel(OutFloat, 
	FoundCurve, Level, 
	ContextString != nullptr ? 
	*ContextString : DefaultContextString, ContextString != nullptr);

	return OutFloat;
}
```

### **AttributeBased**

---

**基于指定的属性值再根据公式和配置计算出一个新的值**

对应数据结构:·

计算方法
**FAttributeBasedFloat::CalculateMagnitude**

计算公式 
**Coefficient*(AttribValue+PreMultiplyAdditiveValue)+PostMultiplyAdditiveValue**

> 💡
>
> Coefficient:乘法系数 FScalableFloat类型
>
> PreMultiplyAdditiveValue:前置附加值 FScalableFloat类型
>
> PostMultiplyAdditiveValue:后置附加值 FScalableFloat类型
>
> AttribValue:通过属性捕获获得的属性值

> 💡 通过属性捕获获得AttribValue,还可以通过AttributeCalculationType指定对捕获属性值的获取方式
>
> AttributeCalculationType为**AttributeBaseValue** 则**AttribValue**为捕获属性的初始值(BaseVaue)
>
> AttributeCalculationType为**AttributeMagnitude** 则**AttribValue**为捕获属性的当前值(CurrentVaue)
>
> AttributeCalculationType为**AttributeBonusMagnitude**则**AttribValue**为捕获属性的修正值(CurrentVaue-BaseVaue)
>
> AttributeCalculationType为**AttributeMagnitudeEvaluatedUpToChannel** 只计算通道配置 ≤ FinalChannel的修正配置 (如果有些修正配置 开启了 通道配置 则可以通过通道配置 筛选出需要纳入计算的修正)
>
> 具体参照后续属性捕获说明

> 💡 **SourceTagFilter**: 
> 如果配置了该筛选Tag集合 则属性修正GE的**CapturedSourceTags**(捕获的GE来源Tag)需要匹配该Tag集合 才会被纳入计算
>
> **TargetTagFilter**: 
> 如果配置了该筛选Tag集合 则属性修正GE的**CapturedTargetTags**(捕获的GE目标Tag)需要匹配该Tag集合 才会被纳入计算
>
> (*比如 捕获的是攻击力属性 有多个GE都会修正攻击力 但有些修正攻击力的GE的Tag不符合筛选限制 则该GE的修正不会被纳入计算*)
>
> **AttributeCurve: AttribValue**可以通过配置**CurveTable**做二次映射修正

![Untitled](http://pic.xyyxr.cn/20260504111201413.png)

```cpp
float FAttributeBasedFloat::CalculateMagnitude(...) const
{

	float AttribValue = 0.f;

	// *AttributeCalculationType为**AttributeBaseValue** 
	//则**AttribValue**为捕获属性的初始值(BaseVaue)*
	if (AttributeCalculationType == 
	EAttributeBasedFloatCalculationType::AttributeBaseValue)
	
	{
		CaptureSpec->AttemptCalculateAttributeBaseValue(AttribValue);
	}
	else
	{
		FAggregatorEvaluateParameters EvaluationParameters;
		//加上Tag限制 筛选修正效果
		EvaluationParameters.SourceTags = InRelevantSpec.CapturedSourceTags.
		GetAggregatedTags();
		
		EvaluationParameters.TargetTags = InRelevantSpec.CapturedTargetTags.
		GetAggregatedTags();
		
		EvaluationParameters.AppliedSourceTagFilter = SourceTagFilter;
		EvaluationParameters.AppliedTargetTagFilter = TargetTagFilter;

		//*AttributeCalculationType为**AttributeMagnitude** 
		//则**AttribValue**为捕获属性的当前值(CurrentVaue)*
		if (AttributeCalculationType == 
		EAttributeBasedFloatCalculationType::AttributeMagnitude)
		{
			CaptureSpec->AttemptCalculateAttributeMagnitude(EvaluationParameters,
			 AttribValue);
		}
		else if (AttributeCalculationType == 
		EAttributeBasedFloatCalculationType::AttributeBonusMagnitude)
		{
		//*AttributeCalculationType为**AttributeBonusMagnitude
		//**则**AttribValue**为捕获属性的CurrentVaue-BaseVaue*
		CaptureSpec->AttemptCalculateAttributeBonusMagnitude(EvaluationParameters, 
		AttribValue);
		}
		else if (AttributeCalculationType == 
		EAttributeBasedFloatCalculationType::AttributeMagnitudeEvaluatedUpToChannel)
		{
				//*AttributeCalculationType为**AttributeMagnitudeEvaluatedUpToChannel**
			//只计算通道配置 ≤ FinalChannel的修正配置*
			//(*如果有些修正配置 开启了 通道配置 则可以通过通道配置 筛选出需要纳入计算的修正*)

			const bool bRequestingValidChannel = UAbilitySystemGlobals::Get().
			IsGameplayModEvaluationChannelValid(FinalChannel);
			
			ensure(bRequestingValidChannel);
			const EGameplayModEvaluationChannel ChannelToUse = bRequestingValidChannel ? 
			FinalChannel : EGameplayModEvaluationChannel::Channel0;

			CaptureSpec->AttemptCalculateAttributeMagnitudeUpToChannel(
			EvaluationParameters,
			 ChannelToUse, AttribValue);
		}
	}

	//AttribValue根据AttributeCurve二次映射修正
	static const FString CalculateMagnitudeContext(
	TEXT("FAttributeBasedFloat::CalculateMagnitude"));
	
	if (AttributeCurve.IsValid(CalculateMagnitudeContext))
	{
		AttributeCurve.Eval(AttribValue, &AttribValue, CalculateMagnitudeContext);
	}

//计算最终的结果
	const float SpecLvl = InRelevantSpec.GetLevel();
	FString ContextString = FString::Printf(
	TEXT("FAttributeBasedFloat::CalculateMagnitude from spec %s"), 
	*InRelevantSpec.ToSimpleString());
	
	return ((Coefficient.GetValueAtLevel(SpecLvl, &ContextString) * 
	(AttribValue + PreMultiplyAdditiveValue.GetValueAtLevel(SpecLvl,
	 &ContextString))) 
	+ PostMultiplyAdditiveValue.GetValueAtLevel(SpecLvl, &ContextString));
}
```

### **CustomCalculationClass**

---

**自定义计算规则，计算类继承自UGameplayModMagnitudeCalculation，直接使用配置类的CDO(ClassDefaultObject)进行计算**

对应数据结构: **FCustomCalculationBasedFloat** 

计算方法
**FCustomCalculationBasedFloat::CalculateMagnitude**

计算公式 
**Coefficient*(CustomBaseValue+PreMultiplyAdditiveValue)+PostMultiplyAdditiveValue**

> 💡
>
> Coefficient:乘法系数 FScalableFloat类型
>
> PreMultiplyAdditiveValue:前置附加值FScalableFloat类型
>
> PostMultiplyAdditiveValue:后置附加值 FScalableFloat类型
>
> CustomBaseValue  是自定义类计算出的结果

FinalValue还可以通过CurveTable配置FinalLookupCurve做一次映射修正

```cpp
float FCustomCalculationBasedFloat::CalculateMagnitude(...) const
{
	const UGameplayModMagnitudeCalculation* CalcCDO = 
	CalculationClassMagnitude->GetDefaultObject<UGameplayModMagnitudeCalculation>();
	
	check(CalcCDO);

	float CustomBaseValue = CalcCDO->CalculateBaseMagnitude(InRelevantSpec);

	const float SpecLvl = InRelevantSpec.GetLevel();
	

	float FinalValue = ((Coefficient.GetValueAtLevel(SpecLvl, &ContextString) * 
	(CustomBaseValue + PreMultiplyAdditiveValue.GetValueAtLevel(SpecLvl, &ContextString))) +PostMultiplyAdditiveValue.GetValueAtLevel(SpecLvl, &ContextString));
	
	if (FinalLookupCurve.IsValid(ContextString))
	{
		FinalValue = FinalLookupCurve.Eval(FinalValue, ContextString);
	}

	return FinalValue;
}
```

![image.png](http://pic.xyyxr.cn/20260504111201414.png)

### **SetByCaller**

---

**值由代码或者蓝图在创建GE时显示通过Tag或者FName的设置，然后再通过对应的Tag或者FName获取**

对应数据结构:  **FSetByCallerFloat**

**FGameplayEffectSpec::SetSetByCallerMagnitude** 

通过Tag或者FName设置值

**FGameplayEffectSpec::GetSetByCallerMagnitude**  

通过Tag或者FName获取值

```cpp
case EGameplayEffectMagnitudeCalculation::SetByCaller:
{
	if (SetByCallerMagnitude.DataTag.IsValid())
	{
		OutCalculatedMagnitude = InRelevantSpec.GetSetByCallerMagnitude(
		SetByCallerMagnitude.DataTag, WarnIfSetByCallerFail, DefaultSetbyCaller);
	}
	else
	{
		PRAGMA_DISABLE_DEPRECATION_WARNINGS

		OutCalculatedMagnitude = InRelevantSpec.GetSetByCallerMagnitude(
		SetByCallerMagnitude.DataName, WarnIfSetByCallerFail, DefaultSetbyCaller);

		PRAGMA_ENABLE_DEPRECATION_WARNINGS
	}
}
```

![Untitled](http://pic.xyyxr.cn/20260504111201415.png)

 

> 💡
>
> UAbilitySystemComponent::UpdateActiveGameplayEffectSetByCallerMagnitude支持在GE生效期间动态去调整SetByCaller传入的值，会触发属性重算

# 属性修正配置

---

**FGameplayModifierInfo定义属性修正的配置**

![Untitled](http://pic.xyyxr.cn/20260504111201416.png)

```cpp
struct GAMEPLAYABILITIES_API FGameplayModifierInfo
{
	UPROPERTY()
	FGameplayAttribute Attribute;

	UPROPERTY(EditDefaultsOnly, Category=GameplayModifier)
	TEnumAsByte<EGameplayModOp::Type> ModifierOp = EGameplayModOp::Additive;

	UPROPERTY(EditDefaultsOnly, Category=GameplayModifier)
	FGameplayEffectModifierMagnitude ModifierMagnitude;

	UPROPERTY(EditDefaultsOnly, Category=GameplayModifier)
	FGameplayModEvaluationChannelSettings EvaluationChannelSettings;

	UPROPERTY(EditDefaultsOnly, Category=GameplayModifier)
	FGameplayTagRequirements	SourceTags;

	UPROPERTY(EditDefaultsOnly, Category=GameplayModifier)
	FGameplayTagRequirements	TargetTags;
}
```

> [!note]- 配置字段说明
> FGameplayAttribute Attribute  
>
> **指定属性**(攻击力 防御力之类的)
>
> TEnumAsByte<EGameplayModOp::Type> ModifierOp 
>
> **属性修改方式** (加、减、乘、除、覆盖)
>
> FGameplayEffectModifierMagnitude ModifierMagnitude  
>
> **修正值的配置** 
>
> > 💡 参照上面的修正值配置说明
>
> FGameplayModEvaluationChannelSettings EvaluationChannelSettings  
>
> **评估通道设置**(默认不启用)
>
> > 💡 可以根据需求将属性修正分为不同的通道Channel
> >
> >     计算修正值时 就可以指定通道值进行计算 修改器设置的通道值小于或者等于指定的通道值的才会被统计进去(暂时没想到有什么用。。。)
> >     需要打开设置 bAllowGameplayModEvaluationChannels=true  和为每个通道设置一个别名
> >     在DefaultGame.ini里
> >
> >     **
> >
> >     ![Untitled](http://pic.xyyxr.cn/20260504111203358.png)
>
> FGameplayTagRequirements SourceTags  
>
> **计算修正值时传入的SourceTag集合需要满足的Tag配置才会生效**
> 需要有哪些Tag 不能有哪些Tag 满足配置才能生效(不配置则不做限制)
>
> FGameplayTagRequirements TargetTags  
>
> **计算修正值时传入的TargetTag集合 需要满足的Tag配置才会生效**
> 需要有哪些Tag 不能有哪些Tag 满足配置才能生效(不配置则不做限制)
>
> > 💡 如果修正器配置了 SourceTags  或者TargetTags ，则在计算修正时会按这个配置取匹配传入计算参数FAggregatorEvaluateParameters的里的Tag是否匹配，匹配则修正器会纳入计算，不匹配则不纳入计算
> >
> >     一般来说在计算玩家属性时SourceTags会传入GE捕获的来源Tag集合(CapturedSourceTags  GE效果来自谁 ) TargetTags会传入GE捕获的目标Tag集合(CapturedTargetTags GE给了谁)
> >
> >     也可以用作筛选属性修正用，比如统计装备系统对攻击力加成了多少，可以将来源于装备的修正器上附加上装备的Tag。 
> >     参照*UAbilitySystemComponent::GetFilteredAttributeValue这里用FAggregatorEvaluateParameters参数AppliedSourceTagFilter和AppliedTargetTagFilter更合适，不需要单独去配置每个修正器的Tag限制，直接限制来源Tag或者目标Tag*
>
> > 💡 **FGameplayTagRequirements**  主要是描述必须要有哪些Tag 和必须不能有哪些Tag(旧版) 及后来加入的更灵活的**FGameplayTagQuery** 配置(支持多重嵌套的类似逻辑运算符表达式的表达式配置方式 具体参照 [Tag-4.0匹配查询](Tag-4.0%E5%8C%B9%E9%85%8D%E6%9F%A5%E8%AF%A2.md)  ）


# 自定义**效果**执行类修正配置

---

GE的自定义执行类(UGameplayEffectExecutionCalculation) 可能需要在实现中用到外部传入的输入数据

可以是来源于属性捕获的值(支持对这个值二次修正、修正的是快照副本不影响原有的属性值)
也可以是一个非属性的修正值

**FGameplayEffectExecutionScopedModifierInfo定义自定义执行类输入数据数值的修正配置**

![Untitled](http://pic.xyyxr.cn/20260504111203359.png)

```cpp
struct FGameplayEffectExecutionScopedModifierInfo
{
	UPROPERTY(VisibleDefaultsOnly, Category=Execution)
	FGameplayEffectAttributeCaptureDefinition CapturedAttribute;

	UPROPERTY(VisibleDefaultsOnly, Category=Execution)
	FGameplayTag TransientAggregatorIdentifier;

	UPROPERTY(VisibleDefaultsOnly, Category=Execution)
	EGameplayEffectScopedModifierAggregatorType AggregatorType;

	UPROPERTY(EditDefaultsOnly, Category=Execution)
	TEnumAsByte<EGameplayModOp::Type> ModifierOp;

	UPROPERTY(EditDefaultsOnly, Category=Execution)
	FGameplayEffectModifierMagnitude ModifierMagnitude;

	UPROPERTY(EditDefaultsOnly, Category=Execution)
	FGameplayModEvaluationChannelSettings EvaluationChannelSettings;

	UPROPERTY(EditDefaultsOnly, Category=Execution)
	FGameplayTagRequirements SourceTags;

	UPROPERTY(EditDefaultsOnly, Category=Execution)
	FGameplayTagRequirements TargetTags;
}
```

> [!note]- 配置字段说明
> FGameplayEffectAttributeCaptureDefinition CapturedAttribute
>
> **修正的对象是捕获的属性**
>
> FGameplayTag TransientAggregatorIdentifier
>
> **修正的对象是一个用Tag标识临时变量**(TransientIdentifier) 
>
> TEnumAsByte<EGameplayModOp::Type> ModifierOp
>
> **修正方式 加、乘、除、覆盖**
>
> FGameplayEffectModifierMagnitude ModifierMagnitud
>
> **修正值配置** 
>
> > 💡 参照上面修正值配置说明
>
> FGameplayModEvaluationChannelSettings EvaluationChannelSettings
>
> **计算属性值的评估通道设置**(默认不设置)
>
> > 💡 可以根据需求将属性修正分为不同的评估通道Channel
> >
> >     计算修正值时 就可以指定通道值进行计算 修改器设置的通道值小于或者等于指定的通道值的才会被统计进去(暂时没想到有什么用。。。)
> >     需要打开设置 bAllowGameplayModEvaluationChannels=true  和为每个通道设置一个别名
> >     在DefaultGame.ini里
> >
> >     **
> >
> >     ![Untitled](http://pic.xyyxr.cn/20260504111203358.png)
>
> FGameplayTagRequirements SourceTags  
>
> **计算修正值时传入的SourceTag集合需要满足的Tag配置**
>
> (需要有哪些Tag 不能有哪些Tag 满足配置才能生效)(不配置则不做限制)
>
> FGameplayTagRequirements TargetTags  
>
> **计算修正值时传入的TargetTag集合 需要满足的Tag配置**
>
> (需要有哪些Tag 不能有哪些Tag 满足配置才能生效)(不配置则不做限制)


# 数值计算聚合器(FAggregator)

---

- 记录了**基础值(BaseValue)、修正值(Magnitude) 、修正方式(加、乘、除、覆盖)**三部分。
- 可以根据上述记录的三部分计算出**修正的最终值**

```cpp
struct GAMEPLAYABILITIES_API FAggregator : public TSharedFromThis<FAggregator>
{

	//计算的基础值
	float	BaseValue;
	FAggregatorModChannelContainer ModChannels;

	//属性发生变化 需要通知的GE 创建快照时 不会拷贝这些
	TArray<FActiveGameplayEffectHandle>	Dependents;
	int32 BroadcastingDirtyCount;
}

```

> [!note]- 字段说明
> BaseValue
>
> 基础值
>
> FAggregatorModChannelContainer ModChannels
>
> **修改器(Mod)的容器** 
> 会根据修改器的配置转换成运行是用到的Mod(**FAggregatorMod**) 并放到不同的分组(分三个维度)
>
> - 分组配置说明(点击展开)
>
> > 💡 第一维度 按Channel分配
> >         *(根据配置的Channel不同分配到不同的分组)
> >         (计算属性时可以根据Channel配置 指计算指定Channel修正)
> >         (大部分情况下只用默认Channel)*

```cpp
        struct GAMEPLAYABILITIES_API FAggregatorModChannelContainer
        {
        	TMap<EGameplayModEvaluationChannel, FAggregatorModChannel> ModChannelsMap;
        }
```
        
> 💡 第二维度按运算方式(加、乘、除、覆盖)分配
>         (相同Channel根据运算方式的不同分配到不同的分组)
        
```cpp
        struct GAMEPLAYABILITIES_API FAggregatorModChannel
        {
        	//二维数组
        	TArray<FAggregatorMod> Mods[EGameplayModOp::Max];
        }
        
```
        
> 💡 第三维度 记录真正的修正配置 FAggregatorMod
        
```cpp
        struct GAMEPLAYABILITIES_API FAggregatorMod
        {
        	//需要满足的Tag
        	const FGameplayTagRequirements*	SourceTagReqs;
        	const FGameplayTagRequirements*	TargetTagReqs;
        
        	//修正值
        	float EvaluatedMagnitude;		
        
        	//触发的GE
        	FActiveGameplayEffectHandle ActiveHandle;	
        	
        private:
        	//修正配置是否参与计算
        	mutable bool IsQualified;
        };
```
        
    
    **TArray<FActiveGameplayEffectHandle>	Dependents**
    
    **属性发生变化 需要通知的GE**
    
> 💡 有些效果配置了属性捕捉(根据某个指定的属性值计算出一个修正值)  需要添加进聚合器的这个列表
>
>     在聚合器有修改器发生变动时 需要通知这些依赖的GE重新根据捕获的属性值评估下修正值
    
```cpp
    //需要属性捕获GE会为向每个捕获属性的聚合器 添加依赖
    void FGameplayEffectAttributeCaptureSpecContainer::RegisterLinkedAggregatorCallbacks(...) const
    {
    	for (const FGameplayEffectAttributeCaptureSpec& CaptureSpec : SourceAttributes)
    	{
    		CaptureSpec.RegisterLinkedAggregatorCallback(Handle);
    	}
    
    	for (const FGameplayEffectAttributeCaptureSpec& CaptureSpec : TargetAttributes)
    	{
    		CaptureSpec.RegisterLinkedAggregatorCallback(Handle);
    	}
    }
    void FGameplayEffectAttributeCaptureSpec::RegisterLinkedAggregatorCallback(...) const
    {
    	if (BackingDefinition.bSnapshot == false)
    	{
    		// Its possible the linked Aggregator is already gone.
    		FAggregator* Agg = AttributeAggregator.Get();
    		if (Agg)
    		{
    			Agg->AddDependent(Handle);
    		}
    	}
    }
```
    

## **创建聚合器**

---

当某个数值需要被修正则会为该数值计算创建一个聚合器

比如属性会被某个GE修改或者捕获，则会为该属性创建一个聚合器用来获取或者修正属性值

```cpp
//**GE激活容器会为每个需要的属性(这个属性会被某个GE修改或者捕获)创建聚合器**
FAggregatorRef& FActiveGameplayEffectsContainer::FindOrCreateAttributeAggregator(...)
{
	FAggregatorRef* RefPtr = AttributeAggregatorMap.Find(Attribute);
	if (RefPtr)
	{
		return *RefPtr;
	}

	//创建新的属性聚合器
	float CurrentBaseValueOfProperty = Owner->GetNumericAttributeBase(Attribute);
	
	//用属性的基础值去构造聚合器
	FAggregator* NewAttributeAggregator = new FAggregator(CurrentBaseValueOfProperty);
	
	if (Attribute.IsSystemAttribute() == false)
	{
		NewAttributeAggregator->OnDirty.AddUObject(Owner, 
		&UAbilitySystemComponent::OnAttributeAggregatorDirty, Attribute, false);
		
		NewAttributeAggregator->OnDirtyRecursive.AddUObject(Owner, 
		&UAbilitySystemComponent::OnAttributeAggregatorDirty, Attribute, true);

		// Callback in case the set wants to do something
		const UAttributeSet* Set = Owner->GetAttributeSubobject(
		Attribute.GetAttributeSetClass());
		
		Set->OnAttributeAggregatorCreated(Attribute, NewAttributeAggregator);
	}

	return AttributeAggregatorMap.Add(Attribute, FAggregatorRef(NewAttributeAggregator));
}
```

需要创建聚合器快照时会重新生成一个新的聚合器，只拷贝基础值和修正器信息(里面放了计算好的修正值及Tag限制信息)

```cpp
//**创建聚合器的快照 也会重新生成一个聚合器**
void FAggregatorRef::TakeSnapshotOf(const FAggregatorRef& RefToSnapshot)
{
	if (RefToSnapshot.Data.IsValid())
	{
		FAggregator* SrcData = RefToSnapshot.Data.Get();

		Data = TSharedPtr<FAggregator>(new FAggregator());
		
		//快照 只拷贝基础值和修正器信息(*里面放了计算好的修正值及Tag限制信息*)
		Data->TakeSnapshotOf(*SrcData);
	}
	else
	{
		Data.Reset();
	}
}
```

## **将修改添加到聚合器**

---

在构建FAggregator的修正器FAggregatorMod，需要提供修正值(EvaluatedMagnitude)，修正计算方式(ModifierOp)，修正限制Tag(SourceTagReqs、TargetTagReqs),根据修正计算方式进行分组

```cpp
void FAggregator::AddAggregatorMod(....)
{
	FAggregatorModChannel& ModChannelToAddTo = ModChannels.FindOrAddModChannel(
	ModifierChannel);
	
	//根据Channel分组
	ModChannelToAddTo.AddMod(EvaluatedMagnitude, 
	ModifierOp, SourceTagReqs, TargetTagReqs, IsPredicted, ActiveHandle);

	BroadcastOnDirty();
}

void FAggregatorModChannel::AddMod(...)
{
	//根据计算方式分组
	TArray<FAggregatorMod>& ModList = Mods[ModOp];

	int32 NewIdx = ModList.AddUninitialized();
	FAggregatorMod& NewMod = ModList[NewIdx];

	//记录Tag限制
	NewMod.SourceTagReqs = SourceTagReqs;
	NewMod.TargetTagReqs = TargetTagReqs;
	
	//记录修正值的大小
	NewMod.EvaluatedMagnitude = EvaluatedMagnitude;
	
	//堆叠数(好像没用到)
	NewMod.StackCount = 0;
	//激活的GE
	NewMod.ActiveHandle = ActiveHandle;
	//是否是主控端预判
	NewMod.IsPredicted = bIsPredicted;
}
```

## **修改器发生变动触发重算**

---

修改器发生变动了(增加、删除、修改)将会触发聚合器重算，属性集的属性刷新也是在聚合器的重算里进行触发的。

同时聚合器的重算会通知依赖该聚合器的GE重新评估修正值，GE有非快照的属性捕获，当捕获的属性发生变化时，会触发修正值的重新评估，进而导致GE修正的属性触发重算。

```cpp
//添加新的修改器
void AddAggregatorMod(...);

//移除指定GE赋予的修改器
void RemoveAggregatorMod(...);

//更新指定GE赋予的修改器(先全部移除 再重新加一遍)
void UpdateAggregatorMod(...);

```

```cpp
//聚合器变动更新
void FAggregator::BroadcastOnDirty()
{
	BroadcastingDirtyCount++;
	
	//这里如果是修正玩家属性的聚合器
	//会调用 FActiveGameplayEffectsContainer::OnAttributeAggregatorDirty
	//刷新玩家身上的数值值
	OnDirty.Broadcast(this);

……
	TArray<FActiveGameplayEffectHandle> DependantsLocalCopy = Dependents;
	//这里先清空再添加 是因为在重新评估GE修正值时也可能会触发其他聚合器的变动从而触发递归调用
	//为了避免无限递归 第一次调用时先清空 递归完成新后再加回来
	//比如 **攻击力聚合器**变动导致**捕获攻击力修正伤害加成**的1号GE需要重算修正值 
	//重算后导致**伤害加成聚合**器发生变动 导致**依赖伤害加成修正攻击力**的2号GE需要重算修正值
	//2号GE的修正又导致了**攻击力的聚合器**发生变动 这里就触发递归了但因为1号GE已经从依赖里移除了
	//递归就不会再进行下去了(这种死循环只能强制断开了)
	Dependents.Empty();

	for (FActiveGameplayEffectHandle Handle : DependantsLocalCopy)
	{
		UAbilitySystemComponent* ASC = Handle.GetOwningAbilitySystemComponent();
		if (ASC)
		{
			ASC->OnMagnitudeDependencyChange(Handle, this);
			Dependents.Add(Handle);
		}
	}

	BroadcastingDirtyCount--;
}
```

```cpp
**//属性聚合器发生变动 触发属性集的属性刷新**
FAggregatorRef& FActiveGameplayEffectsContainer::FindOrCreateAttributeAggregator(...)
{
	NewAttributeAggregator->OnDirty.AddUObject(Owner, 
	&UAbilitySystemComponent::OnAttributeAggregatorDirty, Attribute, false);
}

void UAbilitySystemComponent::OnAttributeAggregatorDirty(...)
{
	ActiveGameplayEffects.OnAttributeAggregatorDirty(...);
}

void FActiveGameplayEffectsContainer::OnAttributeAggregatorDirty(...)
{
...

FAggregatorEvaluateParameters EvaluationParameters;
...
const float NewValue = Aggregator->Evaluate(EvaluationParameters);
InternalUpdateNumericalAttribute(Attribute, NewValue, nullptr, bFromRecursiveCall);
...
}
```

### 触发非快照的属性捕获重算

---

非快照的属性捕获，当捕获的属性发生变动时，会同时触发重算。

在捕获的属性重算时，会对捕获该属性的GE执行FActiveGameplayEffectsContainer::OnMagnitudeDependencyChange。在这个接口会执行捕获该属性的GE的修正重算。

```cpp
//非快照属性捕获 注册对捕获属性的依赖
void FGameplayEffectAttributeCaptureSpec::RegisterLinkedAggregatorCallback(...) const
{
	if (BackingDefinition.bSnapshot == false)
	{
		FAggregator* Agg = AttributeAggregator.Get();
		if (Agg)
		{
			Agg->AddDependent(Handle);
		}
	}
}

//聚合器变动更新
void FAggregator::BroadcastOnDirty()
{
		//对依赖的GE(捕获该属性的GE)执行OnMagnitudeDependencyChange
		for (FActiveGameplayEffectHandle Handle : DependantsLocalCopy)
			{
				UAbilitySystemComponent* ASC = Handle.GetOwningAbilitySystemComponent();
				if (ASC)
				{
					ASC->OnMagnitudeDependencyChange(Handle, this);
					Dependents.Add(Handle);
				}
			}
	}
	

```

```cpp
//执行对属性捕获GE的重算
void FActiveGameplayEffectsContainer::OnMagnitudeDependencyChange(...)
{
if (Handle.IsValid())
	{
	
		FActiveGameplayEffect* ActiveEffect = GetActiveGameplayEffect(Handle);
		if (ActiveEffect)
		{
		
			FGameplayEffectSpec& Spec = ActiveEffect->Spec;
			
			TSet<FGameplayAttribute> AttributesToUpdate;

			bool bMarkedDirty = false;
			
			for(int32 ModIdx = 0; ModIdx < Spec.Modifiers.Num(); ++ModIdx)
			{
				const FGameplayModifierInfo& ModDef = Spec.Def->Modifiers[ModIdx];
				FModifierSpec& ModSpec = Spec.Modifiers[ModIdx];

				float RecalculatedMagnitude = 0.f;
				if (ModDef.ModifierMagnitude.
				AttemptRecalculateMagnitudeFromDependentAggregatorChange(...))
				{
					
					if (!bMarkedDirty)
					{
						bMarkedDirty = true;
						AActor* OwnerActor = Owner ? Owner->GetOwnerActor() : nullptr;
						if (IsNetAuthority() && OwnerActor)
						{
							OwnerActor->FlushNetDormancy();
						}
						MarkItemDirty(*ActiveEffect);
					}
					ModSpec.EvaluatedMagnitude = RecalculatedMagnitude;
					if (MustUpdateAttributeAggregators)
					{
						AttributesToUpdate.Add(ModDef.Attribute);
					}
				}
			}
			UpdateAggregatorModMagnitudes(AttributesToUpdate, *ActiveEffect);
		}
	}
}
```

## **计算&获取需要的值**

---

聚合器创建完成后 就可以根据需求 获取对应的值

### 筛选修正器(Mod)

---

会传入一个评估参数**FAggregatorEvaluateParameters** 表明哪些Mod(修正器)需要纳入计算

```cpp
//聚合器计算传入的参数 筛选下哪些Mod需要纳入计算
struct GAMEPLAYABILITIES_API FAggregatorEvaluateParameters
{

	//用来筛选一些 不需要纳入计算的Mod 跟FAggregatorMod的 SourceTagReqs做匹配
	const FGameplayTagContainer* SourceTags;
	
	//用来筛选一些 不需要纳入计算的Mod 跟FAggregatorMod的 TargetTagReqs做匹配
	const FGameplayTagContainer* TargetTags;

	
	//用来筛选一些 不需要纳入计算的Mod  跟FAggregatorMod的ActiveHandle匹配
	TArray<FActiveGameplayEffectHandle> IgnoreHandles;

	//用来筛选一些 不需要纳入计算的Mod  跟触发GE的捕获的来源Tag集合匹配
	FGameplayTagContainer AppliedSourceTagFilter;

	//用来筛选一些 不需要纳入计算的Mod  跟触发GE的捕获的目标Tag集合匹配
	FGameplayTagContainer AppliedTargetTagFilter;

	//用来筛选一些 不需要纳入计算的Mod 跟FAggregatorMod的IsPredicted匹配
	bool IncludePredictiveMods;
};

```

**根据参入的评估参数去筛选修正器**

```cpp
//统计下哪些Mod需要纳入计算
void FAggregator::EvaluateQualificationForAllMods(...) const
{
		ModChannels.EvaluateQualificationForAllMods(Parameters);

	
	if (EvaluationMetaData && EvaluationMetaData->CustomQualifiesFunc)
	{
		EvaluationMetaData->CustomQualifiesFunc(Parameters, this);
	}
}

void FAggregatorMod::UpdateQualifies(...) const
{
	static const FGameplayTagContainer EmptyTagContainer;
	const FGameplayTagContainer& SrcTags = Parameters.SourceTags ? 
	*Parameters.SourceTags : EmptyTagContainer;
	
	const FGameplayTagContainer& TgtTags = Parameters.TargetTags ? 
	*Parameters.TargetTags : EmptyTagContainer;
	
	**//匹配SourceTagReqs  和 TargetTagReqs**
	bool bSourceMet = (!SourceTagReqs ||
	 SourceTagReqs->IsEmpty()) || 
	 SourceTagReqs->RequirementsMet(SrcTags);
	 
	bool bTargetMet = (!TargetTagReqs || 
	TargetTagReqs->IsEmpty()) || 
	TargetTagReqs->RequirementsMet(TgtTags);

	bool bSourceFilterMet = (Parameters.AppliedSourceTagFilter.Num() == 0);
	bool bTargetFilterMet = (Parameters.AppliedTargetTagFilter.Num() == 0);

	**//匹配IsPredicted**
	if (Parameters.IncludePredictiveMods == false && IsPredicted)
	{
		IsQualified = false;
		return;
	}

	**//匹配ActiveHandle**
	if (ActiveHandle.IsValid())
	{
		for (const FActiveGameplayEffectHandle& HandleToIgnore : Parameters.IgnoreHandles)
		{
			if (ActiveHandle == HandleToIgnore)
			{
				IsQualified = false;
				return;
			}
		}
	}
	
	**//匹配AppliedSourceTagFilter和AppliedTargetTagFilter**
	const UAbilitySystemComponent* HandleComponent = 
	ActiveHandle.GetOwningAbilitySystemComponent();
	
	if (HandleComponent)
	{
		if (!bSourceFilterMet)
		{
			const FGameplayTagContainer* SourceTags = HandleComponent->
			GetGameplayEffectSourceTagsFromHandle(ActiveHandle);
			
			bSourceFilterMet = (SourceTags && 
			SourceTags->HasAll(Parameters.AppliedSourceTagFilter));
		}

		if (!bTargetFilterMet)
		{
			const FGameplayTagContainer* TargetTags = HandleComponent->
			GetGameplayEffectTargetTagsFromHandle(ActiveHandle);
			
			bTargetFilterMet = (TargetTags && 
			TargetTags->HasAll(Parameters.AppliedTargetTagFilter));
		}
	}

	IsQualified = bSourceMet && bTargetMet && bSourceFilterMet && bTargetFilterMet;
}
```

### 计算出最终值

---

- **根据基础值去计算修正最终值**
    
```cpp
    float FAggregator::Evaluate(...) const
    {
    	//先筛选一遍
    	EvaluateQualificationForAllMods(Parameters);
    	//再根据基础值 去计算最终值
    	return ModChannels.EvaluateWithBase(BaseValue, Parameters);
    }
    
    float FAggregatorModChannel::EvaluateWithBase(...) const
    {
    	//有覆盖的 取最后一个 覆盖数据
    	for (const FAggregatorMod& Mod : Mods[EGameplayModOp::Override])
    	{
    		if (Mod.Qualifies())
    		{
    			return Mod.EvaluatedMagnitude;
    		}
    	}
    
    	//累加所有的 加法计算
    	float Additive = SumMods(Mods[EGameplayModOp::Additive], 
    	GameplayEffectUtilities::GetModifierBiasByModifierOp(EGameplayModOp::Additive), 
    	Parameters);
    	
    	//累加所有的 乘法计算 
    	float Multiplicitive = SumMods(Mods[EGameplayModOp::Multiplicitive], 
    	GameplayEffectUtilities::GetModifierBiasByModifierOp(EGameplayModOp::Multiplicitive),Parameters);
    	 
    
    	//累加所有的 除法计算
    	float Division = SumMods(Mods[EGameplayModOp::Division], 
    	GameplayEffectUtilities::GetModifierBiasByModifierOp(EGameplayModOp::Division), 
    	Parameters);
    
    	if (FMath::IsNearlyZero(Division))
    	{
    		ABILITY_LOG(Warning, TEXT("Division summation was 0.0f in FAggregatorModChann"));
    		Division = 1.f;
    	}
    
    	//最终计算公式
    	return ((InlineBaseValue + Additive) * Multiplicitive) / Division;
    }
```
    
> 💡
>
>     5.3这里的最终计算公式还不完善，没考虑乘法系数的累乘和后置加法。5.5版本已经做了优化。最终公式为
>
>     ((InlineBaseValue + PreAdditive)*MultiplicitiveAdditive) / Division*MultiplicitiveComposite+PostAdditive;
>
>     SumMods计算MultiplicitiveAdditive和Division叠加多个修正的累计系数:
>     累计系数=1+(P1-1)+(P2-1)+(P3-1) 
>
>     MultiplicitiveComposite的叠加多个修正的累计系数:
>
>     累计系数=P1*P2*P3
    
    考虑叠加多个百分比效果增强或者削弱属性(比如移动速度增加20%或者减速20%)，结合上面两个累计系数的计算方式，分别分析下增强和削弱的叠加计算：
    
    **叠加多个百分比的增强效果建议用MultiplicitiveAdditive**
    
    如果用MultiplicitiveComposite则是指数级增长，叠加收益过于夸张(下图是每次增加20%，叠加50次的对比)
    
    ![image.png](http://pic.xyyxr.cn/20260504111203360.png)
    
    ![image.png](http://pic.xyyxr.cn/20260504111203361.png)
    
    还有一种叠加增强公式 1-(1-P1)*(1-P2)*(1-P3) 在P1P2P3在区间0~1范围内，会从0增长到1且无限接近于1(这种计算方式UE未提供，与MultiplicitiveAdditive的线性增长，增长曲线更加平缓且只会无限趋近于1)
    
    ![image.png](http://pic.xyyxr.cn/20260504111203362.png)
    
    **叠加多个百分比的削弱效果建议用MultiplicitiveComposite或者Division**
    
    **MultiplicitiveComposite** 当P1P2P3均在0~1区间时，从1收敛到0且无限接近于0，前期叠加收益较大，叠加越多收益越来越来越低，后期无限趋近于无收益(衰减20% P1P2P3的值为0.8)
    
    **Division** 如果通过P1P2P3均大于1时，结合计算累计系数公式 累计系数=1+(P1-1)+(P2-1)+(P3-1) 
    
    修正值=基础值/(1+衰减累计值)(衰减20% P1P2P3的值为1.2)，这个计算方式效果跟上面的MultiplicitiveComposite ****类似，区别之处在于Division 的计算方式从1收敛到0的叠加次数需要更多，收敛更加的缓慢(参照下面对比图)
    
    **MultiplicitiveAdditive**线性衰减不太适合(很容易在前期直接衰减到0)
    
    (下图是每次衰减20%，叠加50次后两种计算方式的对比)
    
    ![image.png](http://pic.xyyxr.cn/20260504111203363.png)
    
    这里除法的应用场景举例，为避免叠加过多减速效果导致速度衰减过快，可以除法做减速叠加计算:叠加减速后速度=速度基础值/(1+减速叠加累计值) 
    

> [!note]- **获取其他计算值**
> 除了获取最终的修正值，还可以通过多种方式或者指定添加的计算值

```cpp
    //指定通道 计算值 配置通道值<=指定通道值的才参与计算
    float EvaluateToChannel(...) const;
    
    //根据最终值 去反向推导出Base值
    float ReverseEvaluate(...) const;
    
    //提升了多少 Final-Base
    float EvaluateBonus(...) const;
    
    //指定的GE 提升了多少(贡献了多少修正)
    float EvaluateContribution(...) const;
    
    //外部传入一个Base值 去计算新的最终值
    float EvaluateWithBase(...) const;
```
    

> 💡
>
> AbilitySystemComponent对外提供了一个捕获属性的接口UAbilitySystemComponent::CaptureAttributeForGameplayEffect
>
> 如果想实现类似只计算装备系统对属性的修正值这种需求的话，可以通过这个接口进行属性捕获，拿到属性对应的聚合器(FAggregator)，然后传入计算的筛选条件，只筛选来自装备属性修正GE赋予的修正。
>
> 可以参照接口UAbilitySystemComponent::GetFilteredAttributeValue的实现
>
> 属性捕获详见 [GE-4.0属性捕获](GE-4.0%E5%B1%9E%E6%80%A7%E6%8D%95%E8%8E%B7.md)

在UAbilitySystemBlueprintLibrary也封装了一堆工具函数，可以参考下

![image.png](http://pic.xyyxr.cn/20260504111203364.png)

### 自定义属性修正检查规则

---

```cpp
void FAggregator::EvaluateQualificationForAllMods(const FAggregatorEvaluateParameters& Parameters) const
{
	// First run our "Default" qualifies function
	ModChannels.EvaluateQualificationForAllMods(Parameters);

	// Then run custom func
	if (EvaluationMetaData && EvaluationMetaData->CustomQualifiesFunc)
	{
		EvaluationMetaData->CustomQualifiesFunc(Parameters, this);
	}
}
```

FAggregator评估(Evaluate)其中的修正器(Mod)是否是有效的修正，除了默认的评估规则EvaluateQualificationForAllMods，还支持自定义评估规则EvaluationMetaData，允许定制而外的评估规则，或者针对某些特殊属性做一些额外的检查。

FAggregatorEvaluateMetaData 可以绑定一个委托，在检测对应的聚合器FAggregator的修正器时，可以调用绑定的对应委托来执行。

```cpp
struct GAMEPLAYABILITIES_API FAggregatorEvaluateMetaData
{
	typedef TFunction< void(const FAggregatorEvaluateParameters&, const FAggregator*) > FCustomQualifiesFunc;

	FAggregatorEvaluateMetaData(FCustomQualifiesFunc InQualifierFunc) 
		: CustomQualifiesFunc(InQualifierFunc)
	{

	}

	FCustomQualifiesFunc CustomQualifiesFunc;
};
```

```cpp
FAggregatorRef& FActiveGameplayEffectsContainer::FindOrCreateAttributeAggregator(...)
{
	FAggregatorRef* RefPtr = AttributeAggregatorMap.Find(Attribute);
	if (RefPtr)
	{
		return *RefPtr;
	}

	FAggregator* NewAttributeAggregator = new FAggregator(CurrentBaseValueOfProperty);
	
	if (Attribute.IsSystemAttribute() == false)
	{
		...
		Set->OnAttributeAggregatorCreated(Attribute, NewAttributeAggregator);
		...
	}

	return AttributeAggregatorMap.Add(Attribute, FAggregatorRef(NewAttributeAggregator));
}
```

当属性增加GE修正为其创建FAggregator，会调用对应的属性集AttributeSet的接口OnAttributeAggregatorCreated,通知属性集为对应的属性创建了 FAggregator，可以在此时为创建的

FAggregator添加上自定义评估规则 FAggregatorEvaluateMetaData。

可以参照FAggregatorEvaluateMetaDataLibrary::MostNegativeMod_AllPositiveMods的实现。