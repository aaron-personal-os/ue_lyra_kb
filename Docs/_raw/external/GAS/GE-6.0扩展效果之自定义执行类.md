> 💡 **本系列文章基于UE5.3**

# 概述

---

**扩展效果是指除属性修正之外的其他千奇百怪的效果，其中一种扩展方式就是通过配置效果自定义执行类**(**UGameplayEffectExecutionCalculation**)**。**

每次触发效果时(*即时效果或者定时触发效果*)，如果配置了效果自定义执行类，则会调用**UGameplayEffectExecutionCalculation的执行接口(Execute)**，所以只需要重载基类的执行接口(**Execute**)，在里面可以定制你需要的各种千奇百怪的效果。

调用**Execute**时会传入两个参数。一个是类型为**FGameplayEffectCustomExecutionParameters**的参数ExecutionParams，该参数存放了需要参与执行计算的输入数据，方便配置时从外部传入数据(输入数据)。另一个是类型为**FGameplayEffectCustomExecutionOutput**的参数ExecutionOutput，该参数是引用传递用来存放执行的结果（输出数据），如此便完成了一个逻辑闭环：输入⇒计算⇒输出。

```cpp
//**即时效果或者定时触发效果执行接口 会遍历配置的自定义执行类 调用执行类的Execute**
void FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom(...)
{
...
for (const FGameplayEffectExecutionDefinition& CurExecDef : SpecToUse.Def->Executions)
	{
		if (CurExecDef.CalculationClass)
		{
			**//获取执行类的CDO**
			const UGameplayEffectExecutionCalculation* ExecCDO = 
	CurExecDef.CalculationClass->GetDefaultObject<UGameplayEffectExecutionCalculation>();
			check(ExecCDO);

			**//构造自定义效果需要用到的参数配置**
			FGameplayEffectCustomExecutionParameters 
			ExecutionParams(SpecToUse, CurExecDef.CalculationModifiers, Owner, 
			CurExecDef.PassedInTags, PredictionKey);
			
			FGameplayEffectCustomExecutionOutput ExecutionOutput;
			
			**//执行自定义效果 并且将执行结果放入 ExecutionOutput**
			ExecCDO->Execute(ExecutionParams, ExecutionOutput);
	}
...
}
```

使用效果自定义执行类基本步骤:

- **创建一个继承自UGameplayEffectExecutionCalculation的C++类或者蓝图**
- **根据需求重载接口Execute，在该接口根据具体需求实现对应的逻辑。**
- **在GE配置里添加效果自定义执行类及其传入数据(*没有则不需要配置*)**

```cpp
class UGameplayEffectExecutionCalculation : public UGameplayEffectCalculation
{
//蓝图子类可以重载Execute
//ExecutionParams 输入数据
//OutExecutionOutput 输出数据
UFUNCTION(BlueprintNativeEvent, Category="Calculation")
void Execute(const FGameplayEffectCustomExecutionParameters& ExecutionParams, 
FGameplayEffectCustomExecutionOutput& OutExecutionOutput) const;
}
```

> 💡 配置的是一个UClass**，**在运行时使用的也是配置的UClass的CDO(ClassDefaultObject)。所以里面是无法存放运行时产生的数据的。跟UGameplayeEffect一样**只是一个只读的配置模板**。
>
> **此类效果只支持即时效果或者持续的定时触发效果配置**(定时触发效果实际也是定时触发一个即时效果)。
> 自定义效果执行类定位就是执行一些即时效果，执行接口(Execute)只会在触发即时效果时调用(*只在FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom里调用*)。

# **配置说明**

---

**FGameplayEffectExecutionDefinition**是配置GE时存放自定义执行配置的数据结构。GE执行列表Executions是一个**FGameplayEffectExecutionDefinition**类型的数组。

![image.png](http://pic.xyyxr.cn/20260504111205268.png)

```cpp
TArray<FGameplayEffectExecutionDefinition> Executions;
```

```cpp
struct GAMEPLAYABILITIES_API FGameplayEffectExecutionDefinition
{
//**配置自定义执行类**
UPROPERTY(EditDefaultsOnly, Category=Execution)
TSubclassOf<UGameplayEffectExecutionCalculation> CalculationClass;

//**配置自定义执行类输入数据中的数值修正**
UPROPERTY(EditDefaultsOnly, Category = Execution)
TArray<FGameplayEffectExecutionScopedModifierInfo> CalculationModifiers;

//**配置自定义执行类输入数据中的Tag标记
//**需要选中的执行类CalculationClass开启 **bRequiresPassedInTags** 才能看到该配置
UPROPERTY(EditDefaultsOnly, Category = Execution)
FGameplayTagContainer PassedInTags;

//**配置给当前GE拥有者附加额外的带限制条件的GE效果**
UPROPERTY(EditDefaultsOnly, Category = Execution)
TArray<FConditionalGameplayEffect> ConditionalGameplayEffects;
}
```

**FGameplayEffectExecutionDefinition的字段说明如下**

**TSubclassOf<UGameplayEffectExecutionCalculation> CalculationClass**

**配置自定义执行类**
直接用的是类的CDO(ClassDefaultObject)不能存放运行时的动态数据。在重载的Execute接口实现定制逻辑运算

**TArray<FGameplayEffectExecutionScopedModifierInfo> CalculationModifiers**

**配置自定义执行类输入数据中的数值修正**

自定义效果的部分数据在不同的应用场景(配置在不同的GE或者由不同的玩家触发)可能存在差异化，这里提供配置支持，允许在配置时设置数据的来源或者直接设置数据，并可以对数据进行各种修正(加、减、乘、除)，计算时根据配置读取数据参与计算。

**FGameplayTagContainer  PassedInTags**

**配置自定义执行类输入数据中的Tag标记(状态)**

自定义效果可以根据传入的不同Tag标记(状态)执行不同的逻辑

> 💡 需要选中的执行类CalculationClass开启 **bRequiresPassedInTags** 才能看到该配置

**TArray<FConditionalGameplayEffect> ConditionalGameplayEffects**

**配置给当前GE拥有者附加额外的带限制条件的GE效果**

比如要实现一个定时回体力的效果，可以先配置一个回体力的即时效果GE_RecoverStamina,然后再配置一个定时触发效果GE_RecoverStamina_Period。在GE_RecoverStamina_Period的ConditionalGameplayEffects配置上GE_RecoverStamina，就会定时给目标上回体力效果GE_RecoverStamina。

支持通过配置RequiredSourceTags来限制是否执行效果附加，只有GE来源Tag(SourceTag)中有指定的Tag才会执行附加额外GE的操作

如果配置了CalculationClass需要CalculationClass执行成功，也可以不配置CalculationClass只配置附加的GE

# **输入数据**

---

为了运行时效率自定义效果配置的执行类仅是一个UClass，运行时直接用的是其CDO。作为一个只读的CDO，其内部是不适合存放或者直接配置运行时差异化数据的，但执行类不可避免的需要根据不同的应用场景传入不同的数据参与运算，比如一个自定义效果类在计算时需要用到数据A,用在GE1中可能是10，用在GE2中可能是100，那就需要一个额外的数据结构存放这些输入数据，在执行效果时作为参数传递进去。

**FGameplayEffectCustomExecutionParameters就是存放输入数据的数据结构。**在执行自定义效果时作为函数参数传入。

```cpp
class GAMEPLAYABILITIES_API UGameplayEffectExecutionCalculation 
{
void Execute(const FGameplayEffectCustomExecutionParameters& ExecutionParams,...) const;
}
```

**自定义效果类如果需要用到输入数据(外部传入额外数据)，则在定义时会先实现声明下需要外部提供哪些数据，配置时根据声明进行数据配置，然后运行时将配置信息转化成输入数据实例中存放(*FGameplayEffectCustomExecutionParameters实例*)。**

**输入数据的提供方式目前有三种方式，基本可以覆盖常用的应用场景。第一种是通过属性捕获来获取相关属性的数值，第二种是非属性捕获直接提供一个数值，第三种是传入一个Tag集合作为标记。**

## 声明输入数据

---

在效果自定义执行类UGameplayEffectExecutionCalculation，可以声明需要配置那些输入数据。下图所示是蓝图子类的配置界面，如果是C++类直接在构造时进行设置即可。

![Untitled](http://pic.xyyxr.cn/20260504111205269.png)

**声明输入数据配置的相关字段说明**

**TArray<FGameplayEffectAttributeCaptureDefinition> RelevantAttributesToCapture**

**配置需要捕获的属性**

继承自基类UGameplayEffectCalculation的配置

配置捕获哪个属性、是发送方还是接收方，是否是快照捕获

> 💡
>
> 可以从GE发生者身上捕获，可以从GE接收者身上捕获，可以设置是否启用属性快照(*不管是否设置了快照捕获，对捕获属性的修正是不会影响原有属性数值的，快照与否的区别在于是直接取捕获那一刻的数值，还是取捕获后最新的实时数据*)

**TArray<FGameplayEffectAttributeCaptureDefinition> InvalidScopedModifierAttributes**

**配置不需要二次修正的捕获属性**

在InvalidScopedModifierAttributes配置的属性不会出现在配置修正器的选项中(*不可以用于二次修正，直接使用捕获的数值*)

**FGameplayTagContainer ValidTransientAggregatorIdentifiers**

**配置需要通过Tag传递的数值**

这里配置的Tag集合会出现在上图那个配置修正器的选项中

通过Tag配置的修正值，在执行自定义效果时会根据Tag取出来参与计算

> 💡
>
> ValidTransientAggregatorIdentifiers仅Editor环境下有效，如果通过代码设置需要注意下。
>
> FGameplayEffectExecutionScopedModifierInfo自定义了编辑方式，在编辑该变量时，将ValidTransientAggregatorIdentifiers中选中的Tag赋值给FGameplayEffectExecutionScopedModifierInfo的TransientAggregatorIdentifier。
>
> ValidTransientAggregatorIdentifiers仅是在编辑提示可以通过哪些Tag传递值(下拉选择框的选项)。

![image.png](http://pic.xyyxr.cn/20260504111205270.png)

![image.png](http://pic.xyyxr.cn/20260504111205271.png)

**bool bRequiresPassedInTags**

**配置是否需传入Tag参数**
如果CalculationClass(效果自定义执行类)需要根据传入的Tag做差异化 则开启该配置

开启后才能在自定义效果的配置里看到Tag的配置字段**PassedInTags**

## 配置输入数据

---

**FGameplayEffectExecutionScopedModifierInfo是自定义效果执行类输入数据的配置数据结构。用于配置数值计算聚合器(FAggregator)的修正器。**

![image.png](http://pic.xyyxr.cn/20260504111205272.png)

```cpp
struct FGameplayEffectExecutionScopedModifierInfo
{

//捕获属性配置
UPROPERTY(VisibleDefaultsOnly, Category=Execution)
FGameplayEffectAttributeCaptureDefinition CapturedAttribute;

//非属性的 关联的Tag
UPROPERTY(VisibleDefaultsOnly, Category=Execution)
FGameplayTag TransientAggregatorIdentifier;

//修正器的类型(属性还是非属性)
UPROPERTY(VisibleDefaultsOnly, Category=Execution)
EGameplayEffectScopedModifierAggregatorType AggregatorType;

//修正器计算方式
UPROPERTY(EditDefaultsOnly, Category=Execution)
TEnumAsByte<EGameplayModOp::Type> ModifierOp;

//修正值
UPROPERTY(EditDefaultsOnly, Category=Execution)
FGameplayEffectModifierMagnitude ModifierMagnitude;
}
```

GAS系统提供了一套数值计算机制，这套机制通过一个数值计算聚合器(**FAggregator**)来计算被多个修正器修正的数值的最终数值，**FAggregator**记录了基础值(BaseValue)、修正值(Magnitude) 、修正方式(加、减、乘、除、覆盖)三部分，支持多种数值计算方式。GE的属性修正就是通过这套机制进行计算的，每个修正的属性都绑定了一个数值计算聚合器(**FAggregator**)，对于非属性修正的数值同样适用，只是需要用一个Key将数值跟聚合器(**FAggregator**)进行关联，Tag就是一个比较适合的Key。所以在提供自定义效果类的输入数据数值配置时就直接用了数值计算聚合器(**FAggregator**)机制

这里的配置就是提供数值计算聚合器(**FAggregator**)修正器配置。

> 💡
>
> 数值修正机制具体可以参照数值修正说明部分[GE-3.0数值修正](GE-3.0%E6%95%B0%E5%80%BC%E4%BF%AE%E6%AD%A3.md)

## 传入输入数据

---

**FGameplayEffectCustomExecutionParameters 是自定义效果执行类输入数据的运行时数据结构**

```cpp
struct GAMEPLAYABILITIES_API FGameplayEffectCustomExecutionParameters
{

//**用于捕获属性二次修正的计算聚合器**
TMap<FGameplayEffectAttributeCaptureDefinition, FAggregator> **ScopedModifierAggregators**;

//**用于存放非属性计算的聚合器(Tag关联)**
TMap<FGameplayTag, FAggregator> **ScopedTransientAggregators**;

//用于存放标记集合
FGameplayTagContainer **PassedInTags**;

}
```

在构造运行时输入数据结构FGameplayEffectCustomExecutionParameters实例时，会根据配置数据结构FGameplayEffectExecutionScopedModifierInfo进行数据填充**。**

首先找到对应的计算聚合器(FAggregator)，捕获属性的二次修正会先找到对应的捕获聚合器创建聚合器的快照，非属性的 直接通过Tag找到对应的聚合器。找到后直接将配置的修正器添加到聚合器中。PassedInTags则是直接拷贝一份即可。

```cpp
FGameplayEffectCustomExecutionParameters::FGameplayEffectCustomExecutionParameters(....)
, **PassedInTags(InPassedInTags)**
{
//**根据配置信息FGameplayEffectExecutionScopedModifierInfo进行数据填充**
for (const FGameplayEffectExecutionScopedModifierInfo& CurScopedMod : InScopedMods)
	{
		FAggregator* ScopedAggregator = nullptr;

		if (CurScopedMod.AggregatorType == EGameplayEffectScopedModifierAggregatorType::CapturedAttributeBacked)
		{
		**//捕获属性的二次修正会先找到对应的捕获聚合器创建聚合器的快照**
			ScopedAggregator = ScopedModifierAggregators.Find(CurScopedMod.CapturedAttribute);
			if (!ScopedAggregator)
			{
				const FGameplayEffectAttributeCaptureSpec* CaptureSpec = InOwningSpec.CapturedRelevantAttributes.FindCaptureSpecByDefinition(CurScopedMod.CapturedAttribute, true);
				
				**//创建聚合器的快照 并加入列表中**
				FAggregator SnapshotAgg;
				if (CaptureSpec && CaptureSpec->AttemptGetAttributeAggregatorSnapshot(..))
				{
					ScopedAggregator = &(ScopedModifierAggregators.Add(CurScopedMod.CapturedAttribute, SnapshotAgg));
				}
			}
		}
		else
		{
		**//非属性的 直接通过Tag找到对应的聚合器(没有就新建一个)**
			ScopedAggregator = &ScopedTransientAggregators.FindOrAdd(CurScopedMod.TransientAggregatorIdentifier);
		}

**//将修正器加入聚合器中**
		float ModEvalValue = 0.f;
		if (ScopedAggregator && CurScopedMod.ModifierMagnitude.AttemptCalculateMagnitude(InOwningSpec, ModEvalValue))
		{
			ScopedAggregator->AddAggregatorMod(...);
		}
}
```

在计算时想要获取对应的输入数据，对于捕获属性如果有二次修正则在ScopedModifierAggregators中查找对应的聚合器进行最终数值计算，如果没有二次修正计算，则直接通过属性捕获聚合器进行数值计算。

```cpp
bool FGameplayEffectCustomExecutionParameters::AttemptCalculateCapturedAttributeMagnitude(...) const
{
	check(OwningSpec);

	const FAggregator* CalcAgg = ScopedModifierAggregators.Find(InCaptureDef);
	if (CalcAgg)
	{
		OutMagnitude = CalcAgg->Evaluate(InEvalParams);
		return true;
	}
	else
	{
		const FGameplayEffectAttributeCaptureSpec* CaptureSpec = OwningSpec->CapturedRelevantAttributes.FindCaptureSpecByDefinition(InCaptureDef, true);
		if (CaptureSpec)
		{
			return CaptureSpec->AttemptCalculateAttributeMagnitude(...);
		}
	}

	return false;
}
```

对应非属性的数值计算,直接通过Tag查找对应的聚合器进行最终值计算。(*还提供一个指定BaseValue的版本，默认BaseValue为0*)

```cpp
bool FGameplayEffectCustomExecutionParameters::AttemptCalculateTransientAggregatorMagnitude(...) const
{
	const FAggregator* CalcAgg = ScopedTransientAggregators.Find(InAggregatorIdentifier);
	if (CalcAgg)
	{
		OutMagnitude = CalcAgg->Evaluate(InEvalParams);
		return true;
	}
	
	return false;
}

bool FGameplayEffectCustomExecutionParameters::AttemptCalculateTransientAggregatorMagnitudeWithBase(...) const
{
	const FAggregator* CalcAgg = ScopedTransientAggregators.Find(InAggregatorIdentifier);
	if (CalcAgg)
	{
		OutMagnitude = CalcAgg->EvaluateWithBase(InBaseValue, InEvalParams);
		return true;
	}

	return false;
}
```

# 输出数据

---

有的自定义效果需要关注执行结果。所以在执行自定义效果时，会返回一个输出数据的参数FGameplayEffectCustomExecutionOutput。

```cpp
void Execute(const FGameplayEffectCustomExecutionParameters& ExecutionParams, FGameplayEffectCustomExecutionOutput& OutExecutionOutput) const;
```

目前主要用于执行后需要修改的属性值OutputModifiers，和是否触发额外附加效果bTriggerConditionalGameplayEffects。这里修正的属性直接是修改属性的BaseValue，一般用于即时属性的修改(当前血量，当前体力之类)

```cpp
struct GAMEPLAYABILITIES_API FGameplayEffectCustomExecutionOutput
{
	UPROPERTY()
	TArray<FGameplayModifierEvaluatedData> OutputModifiers;

	UPROPERTY()
	uint32 bTriggerConditionalGameplayEffects : 1;
}

```

```cpp
void FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom(...)
{

//如果没有配置CalculationClass bRunConditionalEffects 默认设为True
//配置了CalculationClass则取决于执行的返回结果
bool bRunConditionalEffects = true; 

for (const FGameplayEffectExecutionDefinition& CurExecDef : SpecToUse.Def->Executions)
{
	if (CurExecDef.CalculationClass)
	{
...
		FGameplayEffectCustomExecutionOutput ExecutionOutput;
		
		**//执行自定义效果 并且将执行结果放入 ExecutionOutput**
		ExecCDO->Execute(ExecutionParams, ExecutionOutput);
		
		//是否触发额外附加效果bTriggerConditionalGameplayEffects。
	bRunConditionalEffects = ExecutionOutput.ShouldTriggerConditionalGameplayEffects();

		// 执行属性修改
		TArray<FGameplayModifierEvaluatedData>& OutModifiers = ExecutionOutput.GetOutputModifiersRef();

		for (FGameplayModifierEvaluatedData& CurExecMod : OutModifiers)
		{
			if (bApplyStackCountToEmittedMods && SpecStackCount > 1)
			{
				CurExecMod.Magnitude = GameplayEffectUtilities::ComputeStackedModifierMagnitude(CurExecMod.Magnitude, SpecStackCount, CurExecMod.ModifierOp);
			}
			ModifierSuccessfullyExecuted |= InternalExecuteMod(SpecToUse, CurExecMod);
		}
}
	
	
//触发额外附加效果ConditionalGameplayEffects。
if (bRunConditionalEffects)
	{
		for (const FConditionalGameplayEffect& ConditionalEffect : 
		CurExecDef.ConditionalGameplayEffects)
		{
			if (ConditionalEffect.CanApply(...))
			{
				FGameplayEffectSpecHandle SpecHandle = ConditionalEffect.CreateSpec(...);
				if (SpecHandle.IsValid())
				{
					ConditionalEffectSpecs.Add(SpecHandle);
				}
			}
		}
	}
	
}
```

# 执行流程

---

总结下自定义效果的执行流程

> [!note]- 执行前需要根据配置构造执行参数**FGameplayEffectCustomExecutionParameters**(输入数据)
> 主要是收集下效果自定义执行类执行逻辑需要用到输入数据

- 通过执行类的CDO调用执行接口**Execute**触发效果

- 执行完成之后会返回一个执行结果数据**FGameplayEffectCustomExecutionOutput**(输出数据)(是否成功，是否产生了属性更改操作等)

- 如果需要附加额外效果在执行完成后收集下附加效果配置 在所有执行类执行完成后统一进行附加操作

```cpp
void FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom(...)
{
...
for (const FGameplayEffectExecutionDefinition& CurExecDef : SpecToUse.Def->Executions)
	{
		//如果没有配置CalculationClass bRunConditionalEffects 默认设为True
		//配置了CalculationClass则取决于执行的返回结果
		bool bRunConditionalEffects = true; 

		if (CurExecDef.CalculationClass)
		{
			**//获取执行类的CDO**
			const UGameplayEffectExecutionCalculation* ExecCDO = 
	CurExecDef.CalculationClass->GetDefaultObject<UGameplayEffectExecutionCalculation>();
			check(ExecCDO);

			**//构造自定义效果需要用到的参数配置 和 返回结果**
			FGameplayEffectCustomExecutionParameters 
			ExecutionParams(SpecToUse, CurExecDef.CalculationModifiers, Owner, 
			CurExecDef.PassedInTags, PredictionKey);
			
			FGameplayEffectCustomExecutionOutput ExecutionOutput;
			
			**//执行自定义效果 并且将执行结果放入 ExecutionOutput**
			ExecCDO->Execute(ExecutionParams, ExecutionOutput);

			**//执行结果是否产生了属性修正 有则在执行属性修正逻辑**
			for (FGameplayModifierEvaluatedData& CurExecMod : OutModifiers)
			{
				//可以根据叠加数加强属性修正效果
				if (bApplyStackCountToEmittedMods && SpecStackCount > 1)
				{
					CurExecMod.Magnitude = 
					GameplayEffectUtilities::ComputeStackedModifierMagnitude(...);
					
				}
				ModifierSuccessfullyExecuted |= InternalExecuteMod(SpecToUse, CurExecMod);
			}

			**// 是否已经执行过了GameplayCue**
			if (ExecutionOutput.AreGameplayCuesHandledManually())
			{
				GameplayCuesWereManuallyHandled = true;
			}
			
			...
			//**配置了CalculationClass bRunConditionalEffects 取决于执行的返回结果**
		bRunConditionalEffects = ExecutionOutput.ShouldTriggerConditionalGameplayEffects();
			
			**//如果需要附加额外GE 尝试下给效果拥有者 附加额外的GE**
			if (bRunConditionalEffects)
			{
				for (const FConditionalGameplayEffect& ConditionalEffect : 
				CurExecDef.ConditionalGameplayEffects)
				{
				...
						if (SpecHandle.IsValid())
						{
							ConditionalEffectSpecs.Add(SpecHandle);
						}
					...
					}
			
			}
		}
	}
	....
	
	**//统一附加额外效果**
	for (const FGameplayEffectSpecHandle& TargetSpec : ConditionalEffectSpecs)
	{
		if (TargetSpec.IsValid())
		{
			Owner->ApplyGameplayEffectSpecToSelf(*TargetSpec.Data.Get(), PredictionKey);
		}
	}
}
```

> 💡 下面是一个实现一个回血效果的示例
> 根据捕获的属性BaseHealDef的计算出一个修正量 然后恢复对应的血量(比如恢复10%的血量)

```cpp
void ULyraHealExecution::Execute_Implementation(...) const
{
#if WITH_SERVER_CODE
	const FGameplayEffectSpec& Spec = ExecutionParams.GetOwningSpec();

	const FGameplayTagContainer* SourceTags = Spec.CapturedSourceTags.GetAggregatedTags();
	const FGameplayTagContainer* TargetTags = Spec.CapturedTargetTags.GetAggregatedTags();

	FAggregatorEvaluateParameters EvaluateParameters;
	EvaluateParameters.SourceTags = SourceTags;
	EvaluateParameters.TargetTags = TargetTags;

	//这里捕获了属性BaseHealDef 可以基于捕获的属性做二次修正 
	//比如BaseHealDef*0.1 表示恢复10%的基础血量
	float BaseHeal = 0.0f;
	ExecutionParams.AttemptCalculateCapturedAttributeMagnitude(HealStatics().BaseHealDef, EvaluateParameters, BaseHeal);

	const float HealingDone = FMath::Max(0.0f, BaseHeal);

	if (HealingDone > 0.0f)
	{
		**//这里在执行的返回结果中放入了一个属性修正配置
		//在执行完后 会根据属性修正配置 执行属性修正逻辑**
		OutExecutionOutput.AddOutputModifier(
		FGameplayModifierEvaluatedData(ULyraHealthSet::GetHealingAttribute(), 
		EGameplayModOp::Additive, HealingDone));
	}
#endif // #if WITH_SERVER_CODE
}

```