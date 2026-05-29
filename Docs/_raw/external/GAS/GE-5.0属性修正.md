> 💡 **本系列文章基于UE5.3**

# 概述

---

属性修正是GE常见效果的一种。属性修正效果用于改变角色属性数值(*攻击、防御、当前血量之类*)。

**持续效果**和**即时效果**都支持配置属性修正。

![Untitled](http://pic.xyyxr.cn/20260504111203366.png)

> 💡
>
> 两者的区别:
>
> **持续效果**修正的属性在效果激活时赋予对应的数值修正，在效果失效时会取消其产生影响的
>
> 那部分数值(*修正可回退*)。不会直接修改属性的基础值(BaseValue)，而是在基础值只是叠加
>
> 修正影响算出新的数值。所有当修正影响取消时，还是会回退到初始状态(BaseValue)
>
> **即时效果**则是永久不可逆的。直接修改基础值(BaseValue)，即直接修改了属性的初始状态，无法回退
>
> (*一般用于修正当前血量之类的即时属性或者某些特殊需求需要永久性修改某一属性数值*)。

# 持续修正

---

持续且非定时触发(DurationAndNoPeriod) 的GE，在GE持续生效期间修正对应的属性，GE失效后

数值修正效果同步失效。

> [!note]- 叠加修正效果时
> $$
> CurrentValue=BaseValue+ModifyValue
> $$

> [!note]- 未叠加修正效果时
> $$
> CurrentValue=BaseValue
> $$
>
>
> > 💡
> >
> > 持续修正GE修改的ModifyValue部分,在当前基础值(BaseVaule)的之上叠加额外的修正数值
>
> > 💡
> >
> > 效果堆叠会根据堆叠数增强修正数值。

- 在GE赋予时，会先根据属性修正值配置计算出每个配置对应的修正结果值
    
> 💡
>
>     属性修正配置只是配置了修正值的来源，有可能是直接设置一个值，也有可能来自属性捕获、外部传入之类的
    

> [!note]- 再将计算出修正值的修正配置加入属性绑定的数值聚合器(FAggregator)，每个被修正属性都会分
> 配一个数值聚合器(FAggregator)，通过数值聚合器(FAggregator)计算出属性的当前值。
>
> > 💡
> >
> >     关于通过数值聚合器(FAggregator)计算数值修正参照 **[GE-3.0数值修正](GE-3.0%E6%95%B0%E5%80%BC%E4%BF%AE%E6%AD%A3.md)**


### 收集属性修正配置

---

添加(Apply)GE时，收集GE配置的属性修正配置(UGameplayEffect的Modifiers)，并计算出每个配置的

修正值大(CalculateModifierMagnitudes)存放到FGameplayEffectSpec的Modifiers。这两个Modifiers

一一对应。后者就是存放前者的运行时计算结果。

```cpp

void FGameplayEffectSpec::Initialize(...)
{
	//初始化时已经设置好了数组大小 跟 GE配置的Modifiers一一对应
	Modifiers.SetNum(Def->Modifiers.Num());
}

//根据修正值配置计算出最终的修正值 放到FGameplayEffectSpec的Modifiers
void FGameplayEffectSpec::CalculateModifierMagnitudes()
{
	for(int32 ModIdx = 0; ModIdx < Modifiers.Num(); ++ModIdx)
	{
		const FGameplayModifierInfo& ModDef = Def->Modifiers[ModIdx];
		FModifierSpec& ModSpec = Modifiers[ModIdx];

		if (ModDef.ModifierMagnitude.AttemptCalculateMagnitude(*this,
		 ModSpec.EvaluatedMagnitude) == false)
		 
		{
		...
		}
	}
}

FActiveGameplayEffect* FActiveGameplayEffectsContainer::ApplyGameplayEffectSpec(...)
{
	...
	  //根据修正值配置计算出最终的修正值 放到FGameplayEffectSpec的Modifiers
		AppliedEffectSpec.CalculateModifierMagnitudes();
	....
}
```

### 激活时赋予属性修正

---

GE激活时会为每个修正的属性分配一个计算聚合器FAggregator(*如果属性已经存在聚合器就直接取*)，将GE收集的修正配置添加到聚合器，触发聚合器重算然后更新属性当前值(CurrentValue)

```cpp
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

			//为属性分配一个计算聚合器FAggregator(*如果属性已经存在聚合器就直接取*)
			FAggregator* Aggregator = FindOrCreateAttributeAggregator
			(Effect.Spec.Def->Modifiers[ModIdx].Attribute).Get();
			
			if (ensure(Aggregator))
			{
			//为聚合器添加修正器
				Aggregator->AddAggregatorMod(EvaluatedMagnitude,
				 ModInfo.ModifierOp, 
				 ModInfo.EvaluationChannelSettings.GetEvaluationChannel(), 
				 &ModInfo.SourceTags, 
				 &ModInfo.TargetTags, 
				 Effect.PredictionKey.WasLocallyGenerated(), 
				 Effect.Handle);
			}
		}
	}
}

**//属性聚合器发生变动了 触发属性重算**
void FActiveGameplayEffectsContainer::OnAttributeAggregatorDirty(...)
{
...
	//重新评估/计算属性值
	const float NewValue = Aggregator->Evaluate(EvaluationParameters);
	if (EvaluationParameters.IncludePredictiveMods)
	{
		const float OldValue = Owner->GetNumericAttribute(Attribute);
	}
	//更新属性值
	InternalUpdateNumericalAttribute(Attribute, NewValue, nullptr, bFromRecursiveCall);
...
}
```

如果属性修正的GE存在堆叠，则堆叠数会影响修正数值，比如堆叠数为1时攻击力+10，堆叠10层攻击力就+100。

在激活效果时通过FGameplayEffectSpec::GetModifierMagnitude获取修正值会考虑堆叠数的修正因素。

```cpp
float FGameplayEffectSpec::GetModifierMagnitude(...) const
{
	const float SingleEvaluatedMagnitude = Modifiers[ModifierIdx].GetEvaluatedMagnitude();

	float ModMagnitude = SingleEvaluatedMagnitude;
	if (bFactorInStackCount)
	{
		ModMagnitude = GameplayEffectUtilities::ComputeStackedModifierMagnitude(...);
	}

	return ModMagnitude;
}

float GameplayEffectUtilities::ComputeStackedModifierMagnitude(...)
{
	const float OperationBias = GameplayEffectUtilities::GetModifierBiasByModifierOp(ModOp);

	StackCount = FMath::Clamp<int32>(StackCount, 0, StackCount);

	float StackMag = BaseComputedMagnitude;
	
	if (ModOp != EGameplayModOp::Override)
	{
		StackMag -= OperationBias;
		StackMag *= StackCount;
		StackMag += OperationBias;
	}

	return StackMag;
}
```

如果效果已经激活，堆叠数的发生了变化，则会通过FAggregator::UpdateAggregatorMod更新该GE对于对应属性的修正器，获取修正值时会根据当前堆叠数重新计算出一个新的修正值。

```cpp
void FActiveGameplayEffectsContainer::OnStackCountChange(...)
{
	MarkItemDirty(ActiveEffect);
	if (OldStackCount != NewStackCount)
	{
		UpdateAllAggregatorModMagnitudes(ActiveEffect);
	}

}

void FAggregator::UpdateAggregatorMod(...)
{
	//先移除原来的修正器
	ModChannels.RemoveAggregatorMod(ActiveHandle);

	//重新添加修正器
	for (int32 ModIdx = 0; ModIdx < Spec.Modifiers.Num(); ++ModIdx)
	{
		const FGameplayModifierInfo& ModDef = Spec.Def->Modifiers[ModIdx];
		if (ModDef.Attribute == Attribute)
		{
			FAggregatorModChannel& ModChannel = ModChannels.FindOrAddModChannel(...);
			
			//这里的GetModifierMagnitude 获取修正值时会考虑当前堆叠数
			ModChannel.AddMod(Spec.GetModifierMagnitude(ModIdx, true));
		}
	}

	
}
```

### GE失效时移除属性修正

---

GE移除或者被抑制从对应属性的聚合器里移除当前GE赋予的修正，触发聚合器重算，然后更新属性当前值(CurrentValue)*(参考上面激活重算)*

```cpp
void FActiveGameplayEffectsContainer::RemoveActiveGameplayEffectGrantedTagsAndModifiers()
{
....
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
	....
	}
	
```

# 即时修正

---

持续且定时触发(DurationAndPeriod) 效果或者即时效果(Instant)有两种方式触发即时修正，一种方式

通过GE属性修正配置执行即时修正，还有一种方式通过自定义效果返回结果执行即时修正。修正的

是都是属性基础值(BaseValue)

### 执行修正器

---

即时效果(Instant)和持续且定时触发效果(DurationAndPeriod) 都会触发ExecuteActiveEffectsFrom

- 根据GE的属性修正配置执行属性即时修正(InternalExecuteMod)
- 根据效果自定义执行类(FGameplayEffectExecutionDefinition)的返回结果执行属性即时修正(InternalExecuteMod)

```cpp
**//非持续(Instant)GE和持续且定时触发(DurationAndPeriod)GE 
//都会触发ExecuteActiveEffectsFrom
//非持续(Instant)GE 在Apply时生效
//持续且定时触发(DurationAndPeriod)GE 在定时触发时或者首次生效时触发**
void FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom(...)
{
	//如果配置了属性修正 则在此触发 修改的是属性的Base值
	for (int32 ModIdx = 0; ModIdx < SpecToUse.Modifiers.Num(); ++ModIdx)
	{
		const FGameplayModifierInfo& ModDef = SpecToUse.Def->Modifiers[ModIdx];
		
		//GetModifierMagnitude 会有堆叠的加成
		FGameplayModifierEvaluatedData EvalData(ModDef.Attribute, 
		ModDef.ModifierOp, SpecToUse.GetModifierMagnitude(ModIdx, true));
		
		ModifierSuccessfullyExecuted |= InternalExecuteMod(SpecToUse, EvalData);
	}
	
	//配置**效果自定义执行类** 且效果自定义执行类结果返回属性修改
	for (const FGameplayEffectExecutionDefinition& CurExecDef : SpecToUse.Def->Executions)
	{
	...
			ExecCDO->Execute(ExecutionParams, ExecutionOutput);
			for (FGameplayModifierEvaluatedData& CurExecMod : OutModifiers)
			{
				if (bApplyStackCountToEmittedMods && SpecStackCount > 1)
				{
					//是否需要启用堆叠数加成(有可能自定义效果已经计算过或者不需要)
					CurExecMod.Magnitude = GameplayEffectUtilities::ComputeStackedModifierMagnitude(
					CurExecMod.Magnitude, 
					SpecStackCount,
					 CurExecMod.ModifierOp);
					 
				}
				ModifierSuccessfullyExecuted |= InternalExecuteMod(SpecToUse, CurExecMod);
			}
		...
	}
}

bool FActiveGameplayEffectsContainer::InternalExecuteMod(...)
{
...
		if (AttributeSet->PreGameplayEffectExecute(ExecuteData))
		{
			float OldValueOfProperty = Owner->GetNumericAttribute(ModEvalData.Attribute);
			ApplyModToAttribute(ModEvalData.Attribute, 
			ModEvalData.ModifierOp, ModEvalData.Magnitude, &ExecuteData);
		
			AttributeSet->PostGameplayEffectExecute(ExecuteData);
		}
...
}
```

### 执行属性修正

---

**直接设置BaseValue值**

```cpp
//直接设置BaseValue值
void FActiveGameplayEffectsContainer::ApplyModToAttribute(...)
{
	CurrentModcallbackData = ModData;
	float CurrentBase = GetAttributeBaseValue(Attribute);
	
	float NewBase = FAggregator::StaticExecModOnBaseValue(CurrentBase, 
	ModifierOp, ModifierMagnitude);

	SetAttributeBaseValue(Attribute, NewBase);
}
```

# 属性触发重算

---

持续修正GE在生效期间内，如果某些数据发生改变时会触发其修正值的重算，继而触发其修正属性

的数值重算。

**持续修正GE在生效期间内生效内触发修正值重算的逻辑**:

- GE等级发生变化(*等级变化时自动触发重算*)
- GE堆叠发生变化(*堆叠变化时自动触发重算*)
- GE的SetByCaller传入的值发生变化(*更新SetByCaller值时自动触发重算*)
- GE自定义计算类(GameplayModMagnitudeCalculation)依赖的数据发生变化(*需要绑定委托，然后通过委托触发*)

**持续修正GE在生效期间内生效内触发修正值重算的通用操作**:

```cpp

//MarkDirty 触发网络复制操作
MarkItemDirty(Effect);
			
//重新计算修正值			
Effect.Spec.CalculateModifierMagnitudes();

//触发GE修正属性的数值重算
UpdateAllAggregatorModMagnitudes(Effect);
```

> 💡
>
> 注意堆叠变化时，不会触发修正值的重算 只会调用MarkItemDirty和UpdateAllAggregatorModMagnitudes

## GE等级发生变化

---

因为GE支持根据GE等级计算出GE的修正值，所有当GE的等级发生变化时，需要重新计算GE的修正

值。

```cpp
void FActiveGameplayEffectsContainer::SetActiveGameplayEffectLevel(...)
{
	for (FActiveGameplayEffect& Effect : this)
	{
		if (Effect.Handle == ActiveHandle)
		{
			if (Effect.Spec.GetLevel() != NewLevel)
			{
				Effect.Spec.SetLevel(NewLevel);
				MarkItemDirty(Effect);
			
				Effect.Spec.CalculateModifierMagnitudes();
				UpdateAllAggregatorModMagnitudes(Effect);
			}
			break;
		}
	}
}
```

## GE堆叠发生变化

---

GE属性修正在堆叠层级发生变化时，会影响对属性数值的计算，不同的计算方式在计算堆叠影响的

公式不一致，具体可以参照GameplayEffectUtilities::ComputeStackedModifierMagnitude，这个接口

定义了堆叠层级对不同计算方式施加的数值影响。

```cpp
void FActiveGameplayEffectsContainer::OnStackCountChange(...)
{

	MarkItemDirty(ActiveEffect);
	if (OldStackCount != NewStackCount)
	{
		// 堆叠层级发生变动是 只是触发属性值的重算 不会重算修正值
		// 因为堆叠数不是直接影响修正值计算结果 而是影响计算后的修正值的叠加效果
		// 比如计算出的修正值是10  一层是10 3层就是10*3
		UpdateAllAggregatorModMagnitudes(ActiveEffect);
	}
}
```

## GE的SetByCaller发生变化

---

GE在生效期内可以通过UpdateActiveGameplayEffectSetByCallerMagnitude和

UpdateActiveGameplayEffectSetByCallerMagnitudes(更新一个或者多个的区别)来更新SetByCaller传

入的值，在更新值后会触发修正值的重新计算。

```cpp
void FActiveGameplayEffectsContainer::UpdateActiveGameplayEffectSetByCallerMagnitude(...)
{
	if (FActiveGameplayEffect* Effect = GetActiveGameplayEffect(ActiveHandle))
	{
		Effect->Spec.SetSetByCallerMagnitude(SetByCallerTag, NewValue);
		Effect->Spec.CalculateModifierMagnitudes();
		MarkItemDirty(*Effect);

		UpdateAllAggregatorModMagnitudes(*Effect);
	}
}
```

## GE自定义计算类触发重算

---

某些复杂逻辑的修正值计算可以通过自定义计算类进行实现，计算过程中可能依赖其他数值。如果需

要在其他数值变动时，重算修正值，可以通过委托的方式进行操作。

> 💡
>
> 比如计算攻击力的修正依赖于当前玩家的技能加点数，技能加点数这个不是一个属性
>
> (GameplayAttribute)字段，那就需要通过委托的方式在技能加点数发生变动时触发修正值的
>
> 重算。(*属性字段可以通过属性捕获的方式绑定自动触发重算*)

其实现的逻辑如下:在GE生效或者失效的时候通过AddCustomMagnitudeExternalDependencies或者

RemoveCustomMagnitudeExternalDependencies添加移除依赖。

添加自定义计算依赖的前提是自定义计算类提供了一个用来绑定的委托，这委托需要自己定义，可以考虑在ASC或者其他地方定义委托变量，在自定义类的GetExternalModifierDependencyMulticast接口

返回，然后会将函数OnCustomMagnitudeExternalDependencyFire绑定到委托上。

当触发委托的BroadCast时，会执行OnCustomMagnitudeExternalDependencyFire触发修正值的重算

```cpp

void FActiveGameplayEffectsContainer::AddCustomMagnitudeExternalDependencies(...)
{
	const UGameplayEffect* GEDef = Effect.Spec.Def;
	if (GEDef)
	{
		const bool bIsNetAuthority = IsNetAuthority();

	
		for (const FGameplayModifierInfo& CurMod : GEDef->Modifiers)
		{
			TSubclassOf<UGameplayModMagnitudeCalculation> ModCalcClass = CurMod.ModifierMagnitude.GetCustomMagnitudeCalculationClass();
			if (ModCalcClass)
			{
				const UGameplayModMagnitudeCalculation* ModCalcClassCDO = ModCalcClass->GetDefaultObject<UGameplayModMagnitudeCalculation>();
				if (ModCalcClassCDO)
				{

					UWorld* World = Owner ? Owner->GetWorld() : nullptr;
					
					**//只有注册了依赖的的自定义类 才会执行添加操作**
					FOnExternalGameplayModifierDependencyChange* ExternalDelegate = 
					ModCalcClassCDO->GetExternalModifierDependencyMulticast(Effect.Spec, World);
					
					if (ExternalDelegate && (bIsNetAuthority || 
					ModCalcClassCDO->ShouldAllowNonNetAuthorityDependencyRegistration()))
					{
						FObjectKey ModCalcClassKey(*ModCalcClass);
						FCustomModifierDependencyHandle* ExistingDependencyHandle = CustomMagnitudeClassDependencies.Find(ModCalcClassKey);
						
					
						//将OnCustomMagnitudeExternalDependencyFired绑定到注册的委托上
						if (ExistingDependencyHandle)
						{
							ExistingDependencyHandle->ActiveEffectHandles.Add(Effect.Handle);
						}
						else
						{
							FCustomModifierDependencyHandle& NewDependencyHandle = 
							CustomMagnitudeClassDependencies.Add(ModCalcClassKey);
							
							NewDependencyHandle.ActiveDelegateHandle = ExternalDelegate->AddRaw(this, 
						&FActiveGameplayEffectsContainer::OnCustomMagnitudeExternalDependencyFired, 
						ModCalcClass);
						
							NewDependencyHandle.ActiveEffectHandles.Add(Effect.Handle);
						}
					}
				}
			}
		}
	}
}

//委托BroadCast时 会调用绑定的OnCustomMagnitudeExternalDependencyFired 执行重算逻辑
void FActiveGameplayEffectsContainer::OnCustomMagnitudeExternalDependencyFired(
TSubclassOf<UGameplayModMagnitudeCalculation> MagnitudeCalculationClass)
{
	if (MagnitudeCalculationClass)
	{
		FObjectKey ModCalcClassKey(*MagnitudeCalculationClass);
		FCustomModifierDependencyHandle* ExistingDependencyHandle = 
		CustomMagnitudeClassDependencies.Find(ModCalcClassKey);
		
		if (ExistingDependencyHandle)
		{
			const bool bIsNetAuthority = IsNetAuthority();
			const UGameplayModMagnitudeCalculation* CalcClassCDO = 
			MagnitudeCalculationClass->GetDefaultObject<UGameplayModMagnitudeCalculation>();
			
			const bool bRequiresDormancyFlush = CalcClassCDO ? 
			!CalcClassCDO->ShouldAllowNonNetAuthorityDependencyRegistration() : false;

			const TSet<FActiveGameplayEffectHandle>& HandlesNeedingUpdate = 
			ExistingDependencyHandle->ActiveEffectHandles;

			
			for (FActiveGameplayEffect& Effect : this)
			{
				**//将列表中 所有用到这个自定义计算的GE全部执行下重算逻辑**
				if (HandlesNeedingUpdate.Contains(Effect.Handle))
				{
					if (bIsNetAuthority)
					{
						AActor* OwnerActor = Owner ? Owner->GetOwnerActor() : nullptr;
						if (bRequiresDormancyFlush && OwnerActor)
						{
							OwnerActor->FlushNetDormancy();
						}

						MarkItemDirty(Effect);
					}

					Effect.Spec.CalculateModifierMagnitudes();
					UpdateAllAggregatorModMagnitudes(Effect);
				}
			}
		}
	}
}
```

# 属性修正预测

---

在GAS中，ApplyGameplayEffectToSelf这个接口可以使用预测凭证(FPredictionKey)在客户端预判执行GE效果。预判GE效果会在客户端直接添加并视为永久性效果(因为需要等待DS执行结果),这个预判操作发送给DS后，则会通过预判凭证(FPredictionKey)的网络复制通知客户端(执行成功和失败都会通知)，接受到预判操作执行结果后会在客户端移除之前添加的预判GE效果(服务器已经执行正式操作了，预判效果可以拿掉了)。

> 💡
>
> ApplyGameplayEffectToSelf 方法本身并不会直接发送到服务器的 RPC，使用过预判操作本身通知DS端，比如主控客户端执行的预判技能，这个预判操作可以会触发一个预判GE效果，然后这个技能本身会通知DS，DS会针对技能的预判操作发回预判结果。

用一个示例进行讲解，比如有一个冲刺技能，使用技能会消耗体力，体力消耗的实现是通过挂GE的方式实现(ApplyGameplayEffectToSelf)。这个技能时主控客户端预判执行的，发起技能之前会申请一个预判凭证(FPredictionKey)，在预判执行时，也会触发ApplyCost执行ApplyGameplayEffectToSelf操作，此时的GE赋予就是一个预判执行行为(相当于还未通知DS端之前就把体力值扣除了)。在执行ApplyGameplayEffectToSelf会传入一个预判凭证，有预判凭证会被视为永久效果(因为需要等待DS执行结果)，同时也会直接在客户端执行属性修正操作，相当于客户端预先扣除了(数值计算聚合器FAggregator的修正器FAggregatorMod中有一个标记IsPredicted来标记该修正是否来着客户的预判行为)。当DS也执行触发ApplyCost执行ApplyGameplayEffectToSelf操作时，才是真正扣除体力操作。

![image.png](http://pic.xyyxr.cn/20260504111153515.png)

在DS执行预判技能后不管成功或者失败都会通知客户端(参照上面技能的预判执行)，在ApplyGameplayEffectSpec中为该预判操作凭证绑定了一个委托，预判执行通过或者失败都会通过RemoveActiveGameplayEffect_NoReturn移除客户端赋予的预判GE。

```cpp
FActiveGameplayEffect* FActiveGameplayEffectsContainer::ApplyGameplayEffectSpec(...)
{
if (InPredictionKey.IsLocalClientKey() == false || IsNetAuthority())	
	{
		MarkItemDirty(*AppliedActiveGE);
	}
	else
	{
	
		MarkArrayDirty();
		
		//绑定 预判回调
		InPredictionKey.NewRejectOrCaughtUpDelegate(FPredictionKeyEvent::CreateUObject(Owner, &UAbilitySystemComponent::RemoveActiveGameplayEffect_NoReturn, AppliedActiveGE->Handle, -1));
		
	}
}
```

![image.png](http://pic.xyyxr.cn/20260504111153516.png)

> 💡
>
> 后续版本接口换成了 RemoveActiveGameplayEffect_AllowClientRemoval

> 💡
>
> UE提供了一个宏用于在属性复制到客户端(OnRep_XXX属性)时，重算属性值就是为了考虑客户端的GE预判操作的属性修改。有可能DS属性复制到客户端时,DS端还没执行预判GE的属性修改，这里重算会考虑客户端的预判行为，避免出现数值来回拉扯的问题
> GAMEPLAYATTRIBUTE_REPNOTIFY
>
> 还提供一个控制台指令在客户端执行GE(AbilitySystem.Effect.Apply),这个就纯粹时客户端单方面测试用，不会影响到DS端
>
> 当客户端存在预判属性修正效果时 可以通过该接口重算服务器复制的下来的属性
> SetBaseAttributeValueFromReplication

详细参考

[GAS-预判机制(PredictionKey)](GAS-%E9%A2%84%E5%88%A4%E6%9C%BA%E5%88%B6(PredictionKey)%209a2b062da6054c048006c6eee8ab821d.md) 

# 属性(Attribute)网络复制

---

属性(Attribute)可以直接走网络复制客户端， 除此之外，UE默认是会将持续时长的GE的复制到主控端，带有属性修正效果GE复制到主控端之后，同样也会跟DS走一样的逻辑流程触发属性重算机制。也就是对于主控客户端其实是有两个属性修改的通道。

> 💡
>
> GE同步的只是属性数值修正部分，属性基础值(BaseValue)还是走正常的网络复制同步下来

> [!note]- **属性复制(PropertyReplication)流程修改属性(**Attribute**)数值**
> 一般在OnRep_XXX属性复制的回调接口会通过宏GAMEPLAYATTRIBUTE_REPNOTIFY触发
> SetBaseAttributeValueFromReplication调用，这里是因为可能存在属性数值BaseValue的变化，需要根据客户端的属性修正重算下属性数值的当前值，如果存在客户端预测属性数值修改(参照上面的属性预测)，这里也会包含进行,避免出现数值来回拉扯的情况，**可以对DS同步属性数值进行修正，同时会触发属性数值变动的回调**。
>
> ![image.png](http://pic.xyyxr.cn/20260504111203367.png)

```cpp
    void FActiveGameplayEffectsContainer::SetBaseAttributeValueFromReplication(...)
    {
    
    	FAggregatorRef* RefPtr = AttributeAggregatorMap.Find(Attribute);
    	if (RefPtr && RefPtr->Get())
    	{
    		//如果属性存在修正部分 重算下
    		FAggregator* Aggregator = RefPtr->Get();
    		if (FGameplayAttribute::IsGameplayAttributeDataProperty(...))
    		{
    			const float ServerBaseValue = NewValue.GetBaseValue();
    			const float OldBaseValue = OldValue.GetBaseValue();
    			
    		
    			//现有旧的BaseValue算出旧的属性当前数值
    			//这里重算旧的值的意图有点没明白 存疑 
    			//而且用新的修正+旧的Base值计算出来的也不是原本旧的Value值
    			//触发属性修改回调用这个OldValue好像也不对
    			constexpr bool bDoNotExecuteCallbacksValue = false;
    			Aggregator->SetBaseValue(OldBaseValue, bDoNotExecuteCallbacksValue);
    			FAggregatorEvaluateParameters EvaluationParameters;
    			//这里包含了主控端预测数值修改
    			EvaluationParameters.IncludePredictiveMods = true;
    			float OldEvaluatedValue = Aggregator->Evaluate(EvaluationParameters);
    			Owner->SetNumericAttribute_Internal(Attribute, OldEvaluatedValue);
    
    			//将BaseValue改为新的
    			Aggregator->SetBaseValue(ServerBaseValue, bDoNotExecuteCallbacksValue);
    		}
    		//这里触发新的属性数值重算(这里标记为GlobalFromNetworkUpdate 会包含主控端预测数值修改)
    		FScopedAggregatorOnDirtyBatch::GlobalFromNetworkUpdate = true;
    		OnAttributeAggregatorDirty(Aggregator, Attribute);
    		FScopedAggregatorOnDirtyBatch::GlobalFromNetworkUpdate = false;
    	}
    	else
    	{
    		
    		//不存在修正部分 直接触发属性修改回调
    		if (FOnGameplayAttributeValueChange* Delegate = 
    		AttributeValueChangeDelegates.Find(Attribute))
    		{
    			FOnAttributeChangeData CallbackData;
    			CallbackData.Attribute = Attribute;
    			CallbackData.NewValue = NewValue.GetCurrentValue();
    			CallbackData.OldValue = OldValue.GetCurrentValue();
    			CallbackData.GEModData = nullptr;
    
    			Delegate->Broadcast(CallbackData);
    		}
    	}
    }
```
    
> [!note]- **修改属性(Attribute)数值的GE触发属性数值变化**
> GE通过FastArray的方式复制下来，然后跟DS一样走GE生效流程触发属性数值修正重算
>
> ![image.png](http://pic.xyyxr.cn/20260504111205264.png)
>
> GE的修改属性数值和直接的网络复制修改属性数值是在大多数情况下是在同一帧执行的，因为GE的变化会导致对应属性数值触发网络同步(*当然有的直接修改BaseVaule导致的网络复制不会有相关GE的同步，非属性数值修改的GE同步也不会有属性数值的同步*)，从下图所示的堆栈可以看到，在处理网络复制时，会对属性数值的重算进行加锁，只有等复制流程执行完成(PostNetReceive)解锁，然后完成属性数值的重算，这里是为了确保数值的完备性，等所有相关数值复制完成了再执行重算逻辑。
>
> ![image.png](http://pic.xyyxr.cn/20260504111205265.png)
>
> > 💡从下面代码可以看出在网络复制时，是先写入UAttribute的数据再写入UAbilitySystemComponent上的数据(UAttribute是UAbilitySystemComponent的SubObject)，读取时也是同样的数据，所以客户端读取时是先读取UAttribute的属性数值数据，再读取UAbilitySystemComponent上的GE同步数据，在读取UAttribute数据时已经加锁了，等所有数据(包括UAbilitySystemComponent上的)数据全部读取完了才会解锁(AttributeSet::PostNetReceive在读取完整个Actor的网络复制数据之后才执行的)
> > 
> > AttributeSet::PostNetReceive在读取完整个Actor的网络复制数据之后才执行的




![image.png](http://pic.xyyxr.cn/20260504111205266.png)
![image.png](http://pic.xyyxr.cn/20260504111205266.png)

```cpp
void UAttributeSet::PreNetReceive()
{
	//执行网络复制前会加锁操作
	FScopedAggregatorOnDirtyBatch::BeginNetReceiveLock();
}

void UAttributeSet::PostNetReceive()
{
	//执行属性复制操作之后解锁
	FScopedAggregatorOnDirtyBatch::EndNetReceiveLock();
}

void FScopedAggregatorOnDirtyBatch::EndLock()
{
	//解锁之后 继续之前阻挡属性重算逻辑
	GlobalBatchCount--;
	if (GlobalBatchCount == 0)
	{
		TSet<FAggregator*> LocalSet(MoveTemp(DirtyAggregators));
		for (FAggregator* Agg : LocalSet)
		{
			Agg->BroadcastOnDirty();
		}
		LocalSet.Empty();
	}
}
```

# 添加属性修正测试GE

---

可以参照GE的单元测试示例 GameplayEffectsTestSuite的Test_ManaBuff

```cpp
void Test_ManaBuff()
	{
			//New一个GamepalyEffect
			//这里New的GE 是动态创建的 不是一个CDO,默认只会在DS存在，不支持复制到客户端
			//所以客户端是无法查看到这个GE的 
			CONSTRUCT_CLASS(UGameplayEffect, DamageBuffEffect);
			//添加修正
			AddModifier(...);
			
			//设置时长
			DamageBuffEffect->DurationPolicy = EGameplayEffectDurationType::Infinite;
			
			//这里考虑为GE增加标记Tag 方便移除时查找

			//添加GE
			BuffHandle = SourceComponent->ApplyGameplayEffectToTarget(...);
		}

		
	}
```