> 💡 **本系列文章基于UE5.3**

# 概述

---

GameplayAbility(后面统一简称GA)通过GA蓝图创建配置和执行逻辑之后。首先通过
**UAbilitySystemComponent::GiveAbility**将GA赋予目标，然后才可以使用GA。

**执行流程简述**

1. 通过UAbilitySystemComponent::**GiveAbility赋予GA**

2. 尝试激活GA
触发GA执行的方式一般有以下几种:
    - 输入操作
    *(点击按钮或者按键操作调用*TryActivateAbility触发)
    - 给拥有者添加Tag触发
    *(配置**AbilityTriggers**，参照UAbilitySystemComponent::MonitoredTagChanged)*
    - 通过函数SendGameplayEventToActor
    (配置AbilityTriggers，*可以附带执行上下文信息参照)*
    - 直接调UAbilitySystemComponent::TryActivateAbility/TriggerAbilityFromGameplayEvent
        
        *(分别是不附带执行上下文和附带执行上下文版本)*
        
3. UAbilitySystemComponent::**InternalTryActivateAbility**实际执行GA的激活触发

4. UGameplayAbility::**CanActivateAbility**判断GA是否可以被激活

5. 成功激活GA后执行UGameplayAbility::**ActivateAbility**
会调用GA蓝图的ActivateAbility方便在GA蓝图里定制GA激活后具体要执行哪些操作(也可以在C++中的子类重载这个接口来定制GA激活后的执行逻辑)

6. 如果GA有消耗或者CD需要在执行UGameplayAbility::**ActivateAbility**时，首先调用UGameplayAbility::**CommitAbility**来提交GA的消耗或者CD之类的，执行消耗和CD之前会再次通过**CommitCheck**校验消耗和CD,不满足返回False(蓝图实现的ActivateAbility也是一样)

7. GA被移除(Remove)、取消激活(Cancel)、结束(End)都会通过UGameplayAbility::**EndAbility**来执行结束的处理。同时会调用GA蓝图EndAbility接口方便在蓝图中执行GA取消激活后的操作

# **FGameplayAbilitySpec**

---

**FGameplayAbilitySpec**是GA运行时的数据结构。每次赋予一个GA都会创建一份的对应的FGameplayAbilitySpec实例放入可激活的GA列表**ActivatableAbilities**中。包含了GA运行时实例，当前等级，绑定输入按键，是否被激活等数据。

继承自FFastArraySerializerItem，支持网络复制。

> 💡 如果GA是每次激活都创建一个新的实例，其在激活时创建的多个实例也是公用一份**FGameplayAbilitySpec**数据。创建的实例放在**FGameplayAbilitySpec**的GA实例数组中

```cpp
struct GAMEPLAYABILITIES_API FGameplayAbilitySpec : public FFastArraySerializerItem
{
...
}
```

## **FGameplayAbilitySpec字段说明**

---

**FGameplayAbilitySpecHandle Handle**

**FGameplayAbilitySpec的句柄**(全局唯一编号)

**TObjectPtr<UGameplayAbility> Ability**

**GA CDO实例**

*只读GA实例(配置数据模板)*

**int32   Level**

**GA当前等级**

**int32   InputID**

**GA绑定的触发按键**

**TWeakObjectPtr<UObject> SourceObject**

**GA赋予来源Object**

**uint8 ActiveCount**

**激活次数**

*激活计数+1，取消激活计数-1
对于每次激活都创建一个新的GA实例的，激活计数可以会超过1*

**uint8 InputPressed**

**绑定的按键是否按下**

**uint8 RemoveAfterActivation**

**GA结束后是否直接移除**

**uint8 PendingRemove**

**是否即将移除**

**uint8 bActivateOnce**

**是否是在赋予技能时就立即激活的**

**TSharedPtr<FGameplayEventData> GameplayEventData**

**激活GA时附带的上下文信息**

*激活GA时附加的信息*

**FGameplayAbilityActivationInfo  ActivationInfo**

**GA当前激活状态**

*在主控端激活、在主权端激活、主控端激活成功但主权端激活失败被拒绝之类的*

**FGameplayTagContainer DynamicAbilityTags**

**运行时动态添加的AbilityTags**

*运行时动态赋予GA的Tag标记*

**TArray<TObjectPtr<UGameplayAbility>> NonReplicatedInstances**

**GA运行时创建的实例**(不需要网络复制的)
****

**TArray<TObjectPtr<UGameplayAbility>> ReplicatedInstances**

**GA运行时创建的实例**(需要网络复制的)

> 💡 在创建GA实例时会根据GA是否需要复制的配置(**ReplicationPolicy** )分别将创建的实例放入**NonReplicatedInstances**或者**ReplicatedInstances**列表中

**FActiveGameplayEffectHandle GameplayEffectHandle**

**通过GE赋予的GA其赋予GE的句柄**(全局唯一编号)

**TMap<FGameplayTag, float> SetByCallerTagMagnitudes**

**可以实现部分数据的在GA和GE直接进行传承**
*通过GE赋予的GA会将GE的SetByCallerTagMagnitude继承过来*

*通过GA赋予的GE会将GA的SetByCallerTagMagnitude继承过来*

# GA赋予&移除

---

**UAbilitySystemComponent::GiveAbility**将GA赋予目标，**赋予操作只能在主权端(DS端)执行**。赋予成功后会添加到可激活GA列表**ActivatableAbilities**中。该列表会复制到主控客户端。

> 💡 **GiveAbilityAndActivateOnce** 
> 对GiveAbility的封装  
> 先调用GiveAbility赋予GA再通过**InternalTryActivateAbility**立即尝试激活GA
> 激活失败则立即移除

```cpp
FGameplayAbilitySpecHandle UAbilitySystemComponent::GiveAbility(..)
{
	**//只有主权端才有赋予权限**
	if (!IsOwnerActorAuthoritative())
	{
			return FGameplayAbilitySpecHandle();
	}
	
	**//如有操作锁则先放入待赋予列表**
	if (AbilityScopeLockCount > 0)
	{
		AbilityPendingAdds.Add(Spec);
		return Spec.Handle;
	}
	
	**//添加到可激活GA列表中
	//操作锁**
	ABILITYLIST_SCOPE_LOCK();
	FGameplayAbilitySpec& OwnedSpec = 
	**ActivatableAbilities.Items[ActivatableAbilities.Items.Add(Spec)]**;
	
...
	
	OnGiveAbility(OwnedSpec);
	
	//InstancedPerActor类型的GA在赋予是创建实例
	if (OwnedSpec.Ability->GetInstancingPolicy() == 
	EGameplayAbilityInstancingPolicy::InstancedPerActor)
	{
		CreateNewInstanceOfAbility(OwnedSpec, Spec.Ability);
	}
....

	return OwnedSpec.Handle;
}
```

除了直接调用**GiveAbility**赋予GA之外，还有多种方式可以赋予GA。

> [!note]- **通过配置DataAsset(数据资产)方式来赋予GA**
> UE提供了一个GameplayAbilitySet的数据资产来配置GA的赋予，可以指定GA及其绑定的输入。
>
> 运行时读取数据资产的配置，然后调用GiveAbilities进行GA的赋予。
>
> 也可以根据需要定制属于你自己的GA赋予数据资产。
>
> ![Untitled](http://pic.xyyxr.cn/20260504111151773.png)

```cpp
    void UGameplayAbilitySet::GiveAbilities(...) const
    {
    	for (const FGameplayAbilityBindInfo& BindInfo : Abilities)
    	{
    		if (BindInfo.GameplayAbilityClass)
    		{
    			AbilitySystemComponent->GiveAbility(FGameplayAbilitySpec(
    			BindInfo.GameplayAbilityClass,1, (int32)BindInfo.Command));
    		}
    	}
    }
```
    
> [!note]- **通过GE来赋予GA**
> GE的组件AbilitiesGameplayEffectComponent支持在GE激活时赋予GA
>
> GE效果被激活时会赋予拥有者额外的技能

```cpp
    void UAbilitiesGameplayEffectComponent::GrantAbilities(...) const
    {
    	
    	const TArray<FGameplayAbilitySpec>& AllAbilities = ASC->GetActivatableAbilities();
    	for (const FGameplayAbilitySpecConfig& AbilityConfig : GrantAbilityConfigs)
    	{
    		
    ...
    		FGameplayAbilitySpec AbilitySpec{ AbilityConfig.Ability, Level, 
    		AbilityConfig.InputID, ActiveGESpec.GetEffectContext().GetSourceObject() };
    		
    		AbilitySpec.SetByCallerTagMagnitudes = ActiveGESpec.SetByCallerTagMagnitudes;
    		AbilitySpec.GameplayEffectHandle = ActiveGEHandle;
    
    		ASC->GiveAbility(AbilitySpec);
    	...
    	}
    }
```
    
    GE效果失效或者移除时根据配置策略决定是否移除赋予技能
    
```cpp
    void UAbilitiesGameplayEffectComponent::RemoveAbilities(...) const
    {
    
    	for (const FGameplayAbilitySpecConfig& AbilityConfig : GrantAbilityConfigs)
    	{
    ...
    		switch (AbilityConfig.RemovalPolicy)
    		{
    			case EGameplayEffectGrantedAbilityRemovePolicy::CancelAbilityImmediately:
    			{
    				ASC->ClearAbility(AbilitySpecDef->Handle);
    				break;
    			}
    			case EGameplayEffectGrantedAbilityRemovePolicy::RemoveAbilityOnEnd:
    			{
    				ASC->SetRemoveAbilityOnEnd(AbilitySpecDef->Handle);
    				break;
    			}
    		}
    	...
    	}
```
    

UAbilitySystemComponent::**ClearAbility**执行GA的移除，**移除操作只能在主权端执行。**从可激活GA列表**ActivatableAbilities**移除

```cpp
void UAbilitySystemComponent::ClearAbility(const FGameplayAbilitySpecHandle& Handle)
{

//**移除操作只能在主权端执行**
	if (!IsOwnerActorAuthoritative())
	{
		return;
	}

	**//如果在待赋予列表中 直接移除**
	for (int Idx = 0; Idx < AbilityPendingAdds.Num(); ++Idx)
	{
		if (AbilityPendingAdds[Idx].Handle == Handle)
		{
			AbilityPendingAdds.RemoveAtSwap(Idx, 1, false);
			return;
		}
	}

	for (int Idx = 0; Idx < ActivatableAbilities.Items.Num(); ++Idx)
	{
		check(ActivatableAbilities.Items[Idx].Handle.IsValid());
		if (ActivatableAbilities.Items[Idx].Handle == Handle)
		{
			**//有操作锁 则先放入待移除列表**
			if (AbilityScopeLockCount > 0)
			{
				if (ActivatableAbilities.Items[Idx].PendingRemove == false)
				{
					ActivatableAbilities.Items[Idx].PendingRemove = true;
					AbilityPendingRemoves.Add(Handle);
				}
			}
			else
			{
					**//移除操作**
					//**操作锁**
					ABILITYLIST_SCOPE_LOCK();
					OnRemoveAbility(ActivatableAbilities.Items[Idx]);
					**ActivatableAbilities.Items.RemoveAtSwap(Idx);
					ActivatableAbilities.MarkArrayDirty();**

			}
			return;
		}
	}
}
```

## 操作锁

---

GA的赋予和移除都会增加操作锁**ABILITYLIST_SCOPE_LOCK**()，处理一些递归嵌套操作，同时可以规避死循环的递归风险。
*比如赋予GA时立即激活触发了一个GE,触发的GE又赋予了一个GA*

操作锁的逻辑就是在构造时计数+1，析构时计数-1。当计数位0，会将缓存在临时列表的GA执行赋予或者移除操作。(*在待赋予列表中的GA，如果在操作锁解锁之前就触发了移除会直接从待赋予列表中移除，不需要放入待移除列表*)

```cpp
#define ABILITYLIST_SCOPE_LOCK()	FScopedAbilityListLock ActiveScopeLock(*this);

struct GAMEPLAYABILITIES_API FScopedAbilityListLock
{
	FScopedAbilityListLock(UAbilitySystemComponent& InContainer);
	~FScopedAbilityListLock();

private:
	UAbilitySystemComponent& AbilitySystemComponent;
};

FScopedAbilityListLock::FScopedAbilityListLock(...)
{
	AbilitySystemComponent.IncrementAbilityListLock();
}

FScopedAbilityListLock::~FScopedAbilityListLock()
{
	AbilitySystemComponent.DecrementAbilityListLock();
}
```

```cpp
void UAbilitySystemComponent::IncrementAbilityListLock()
{
	AbilityScopeLockCount++;
}

void UAbilitySystemComponent::DecrementAbilityListLock()
{
	if (--AbilityScopeLockCount == 0 &&
		(AbilityPendingAdds.Num() > 0 || AbilityPendingRemoves.Num() > 0))
	{
		FAbilityListLockActiveChange ActiveChange(*this, AbilityPendingAdds, AbilityPendingRemoves);

//**执行赋予**
		for (FGameplayAbilitySpec& Spec : ActiveChange.Adds)
		{
			if (Spec.bActivateOnce)
			{
				GiveAbilityAndActivateOnce(Spec, Spec.GameplayEventData.Get());
			}
			else
			{
				GiveAbility(Spec);
			}
		}

//**执行移除**
		for (FGameplayAbilitySpecHandle& Handle : ActiveChange.Removes)
		{
			ClearAbility(Handle);
		}
	}
}
```

# GA激活

---

**UAbilitySystemComponent::InternalTryActivateAbility**是GA激活的入口

> 💡 **TryActivateAbility/TryActivateAbilitiesByTag/TryActivateAbilityByClass**
> 对InternalTryActivateAbility的封装
> 会根据GA配置的网络执行策略**NetExecutionPolicy**来决定直接调用InternalTryActivateAbility尝试激活或者需要通过RPC转发到对应的执行端再调用InternalTryActivateAbility尝试激活
>
> **TriggerAbilityFromGameplayEvent** 
> 对InternalTryActivateAbility的封装
> 附带了上下文信息FGameplayEventData调用InternalTryActivateAbility尝试激活GA
>
> **MonitoredTagChanged**
> 对InternalTryActivateAbility的封装
> 当GA的拥有者Tag变化时，会检测Tag是否符合
> AbilityTriggers的配置，决定是否调用InternalTryActivateAbility尝试激活GA

1. 先通过UGameplayAbility::**CanActivateAbility**判定GA是否可以被执行
    - 检测执行网络权限策略NetSecurityPolicy是否匹配
    (UGameplayAbility::**ShouldActivateAbility**)
    - 检测CD是否满足
    (UGameplayAbility::**CheckCooldown**)
    - 检测技能消耗是否满足
    (UGameplayAbility::**CheckCost**)
    - 检测是否Tag配置是否满足
    (UGameplayAbility::**DoesAbilitySatisfyTagRequirements**)
        
> 💡 主要是检测以下这些配置:
>         **AbilityTags**
>         是否被其他技能限制激活了
>
>         **ActivationRequiredTags\ActivationBlockedTags**
>         是否GA拥有者身上的Tag不满足激活限制
>
>         **SourceRequiredTags\SourceBlockedTags\TargetRequiredTags\TargetBlockedTags**
>         是否激活GA时按需传入的SourceTags和TargetTags不满足配置
        
    - GA绑定的按键是否被禁用
    (UAbilitySystemComponent::**IsAbilityInputBlocked**)
    - GA蓝图定制的激活限制
    (**K2_CanActivateAbility**)
    
> 💡 InternalTryActivateAbilit也会对网络执行策略NetExecutionPolicy进行校验，校验不通过则直接失败，通过TryActivateAbility调用才会根据网络执行策略进行RPC转发调用。
    

1. 检测通过后通过GA实例执行激活操作
    - 对于在DS(主权端)发起的激活，如果GA不只是在DS端执行(即网络执行策略NetExecutionPolicy配置为**ServerInitiated**的GA)则需要通过RPC通知主控客户端同步执行激活操作
    (UAbilitySystemComponent::**ClientActivateAbilitySucceed**/
    UAbilitySystemComponent::**ClientActivateAbilitySucceedWithEventData**)
    
    - 对于玩家在主控客户端发起的激活，如果GA不只是在主控端执行(即网络执行策略NetExecutionPolicy配置为**LocalPredicted**的GA)，则需要通过RPC通知DS端(UAbilitySystemComponent::**CallServerTryActivateAbility**/
    UAbilitySystemComponent::**ServerTryActivateAbilityWithEventData**)
    
    - 对于每次执行激活都需要创建实例的GA(InstancedPerExecution)还需创建新的GA实例
        
> 💡 对于InstancedPerActor配置的GA如果当前实例已经被激活则需要根据配置
>         **bRetriggerInstancedAbility**决定是直接激活失败还是将之实例结束再重新激活
        
    - 最后UGameplayAbility::**CallActivateAbility**执行激活操作
        
```cpp
        void UGameplayAbility::CallActivateAbility(...)
        {
        	PreActivate(...);
        	ActivateAbility(...);
        }
```
        
        **UGameplayAbility::PreActivate**执行操作前的一些处理
        
        - 标记GA已被激活
        - 缓存GA的拥有者信息CurrentActivationInfo
        - 缓存传入的上下文信息FGameplayEventData参数
        - 给GA拥有者附加Tag(ActivationOwnedTags)
        - 让BlockAbilitiesWithTag和CancelAbilitiesWithTag配置生效
        (UAbilitySystemComponent::ApplyAbilityBlockAndCancelTags)
        
        **UGameplayAbility::ActivateAbility**就是正真执行激活操作的地方了
        可以直接在C++中重载该接口或者直接在蓝图中实现该接口
        
    

**代码参考**

```cpp
bool UAbilitySystemComponent::InternalTryActivateAbility(...)
{

	//模拟端不会执行
	if (NetMode == ROLE_SimulatedProxy)
	{
		return false;
	}

	//网络执行策略**NetExecutionPolicy** 不满足直接失败
	if (!bIsLocal)
	{
		if (Ability->GetNetExecutionPolicy() == 
		EGameplayAbilityNetExecutionPolicy::LocalOnly || 
		(Ability->GetNetExecutionPolicy() == 
		EGameplayAbilityNetExecutionPolicy::LocalPredicted && 
		!InPredictionKey.IsValidKey()))
		{
			return false;
		}		
	}

	if (NetMode != ROLE_Authority && 
	(Ability->GetNetExecutionPolicy() == 
	EGameplayAbilityNetExecutionPolicy::ServerOnly || 
	Ability->GetNetExecutionPolicy() == 
	EGameplayAbilityNetExecutionPolicy::ServerInitiated))
	{
		return false;
	}
	
	//UGameplayAbility::CanActivateAbility判定GA是否可以被执行
	if (!CanActivateAbilitySource->CanActivateAbility(...))
	{
		return false;
	}
	
	
	//对于InstancedPerActor配置的GA如果当前实例已经被激活则需要根据配置
	//**bRetriggerInstancedAbility**决定是直接激活失败还是将之实例结束再重新激活
	if (Ability->GetInstancingPolicy() == 
	EGameplayAbilityInstancingPolicy::InstancedPerActor)
	{
		if (Spec->IsActive())
		{
			if (Ability->bRetriggerInstancedAbility && InstancedAbility)
			{
				InstancedAbility->EndAbility(...);
			}
			else
			{
				return false;
			}
		}
	}
	
	

	if (Ability->GetNetExecutionPolicy() == 
	EGameplayAbilityNetExecutionPolicy::LocalOnly 
	|| (NetMode == ROLE_Authority))
	{
		//对于玩家在DS(主权端)发起的激活，如果GA不是只在DS(主权端)执行
		//则需要通过RPC通知主控客户端同步执行激活操作
		if (!bIsLocal && Ability->GetNetExecutionPolicy() != 
		EGameplayAbilityNetExecutionPolicy::ServerOnly)
		{
				if (TriggerEventData)
				{
					ClientActivateAbilitySucceedWithEventData(...);
				}
				else
				{
					ClientActivateAbilitySucceed(...);
				}
			}
		}
		
		
	//对于玩家在主控客户端发起的激活，
	//如果GA不是只在主控端执行则需要通过RPC通知DS(主权端同步执行激活操作	
	else if (Ability->GetNetExecutionPolicy() == 
	EGameplayAbilityNetExecutionPolicy::LocalPredicted)
	{
	
		if (TriggerEventData)
		{
			ServerTryActivateAbilityWithEventData(...);
		}
		else
		{
			CallServerTryActivateAbility(...);
		}
	}
		
		
		
		
	//对于每次执行激活都需要创建实例的GA(InstancedPerExecution)还需创建新的GA实例
	//CallActivateAbility 执行激活操作
	if (Ability->GetInstancingPolicy() == 
	EGameplayAbilityInstancingPolicy::InstancedPerExecution)
	{
		InstancedAbility = CreateNewInstanceOfAbility(*Spec, Ability);
		InstancedAbility->CallActivateAbility();
	}
	else if (InstancedAbility)
	{
		InstancedAbility->CallActivateAbility();
	}
	else
	{
		Ability->CallActivateAbility();
	}
	
}

```

# GA结束

---

**UGameplayAbility::EndAbility**是GA结束的入口，在GA蓝图中可以直接通过EndAbility结束GA

**CancelAbility**最终是通过**UGameplayAbility::EndAbility**实现的GA的取消激活操作
区别在于通过**CancelAbility**触发的**EndAbility**被视为因为外部因素中断的GA的执行
GA内部直接调用**EndAbility**被视为GA正常执行结束

**UAbilitySystemComponent::CancelAbilitySpec**是GAS系统对外部暴露的取消入口，找到GA实例后再通过GA实例调用**CancelAbility**，被视为中断GA的执行。

> 💡
>
> **CancelAllAbilities** 
> 对CancelAbilitySpec的封装
> 调用CancelAbilitySpec取消激活所由激活的GA
>
> **CancelAbilities** 
> 对CancelAbilitySpec的封装
> 通过传入的Tag集合调用CancelAbilitySpec取消激活多个指定的GA
>
> **CancelAbilityHandle**
> 对CancelAbilitySpec的封装
> 通过传入的GAHandle调用CancelAbilitySpec取消激活指定GA
>
> **CancelAbility**  
> 对CancelAbilitySpec的封装
> 传入的GA实例调用CancelAbilitySpec取消激活指定的GA

```cpp
void UGameplayAbility::CancelAbility(...)
{
		**//需要通过RPC告诉主控客户端或者DS端同步执行取消操作**
		if (bReplicateCancelAbility && 
			ActorInfo && 
			ActorInfo->AbilitySystemComponent.IsValid())
		{
			ActorInfo->AbilitySystemComponent->ReplicateEndOrCancelAbility(...);
		}
	
		**//执行取消技能的回调**
		if (OnGameplayAbilityCancelled.IsBound())
		{
			OnGameplayAbilityCancelled.Broadcast();
		}
	
		//调用**EndAbility**执行取消激活操作
		
		//bReplicateEndAbility置为false
		//因为已经通过RPC通知对应的执行端了EndAbility就不需要再次通知了
		bool bReplicateEndAbility = false;
		
		//bWasCancelled置为true 标记因为中断导致的取消激活操作
		bool bWasCancelled = true;
		EndAbility(...bReplicateEndAbility, bWasCancelled);
}
```

**EndAbility**是实际执行GA的取消激活操作

1. 调用蓝图接口处理取消激活操作
2. 处理取消激活绑定的委托回调
3. 标记GA为非激活的
4. 清理GA启用的Task
5. **ReplicateEndOrCancelAbility**通知对应的端同步执行结束操作(Cancel触发的不会重复执行)
6. 移除附加给GA拥有者的Tag(**ActivationOwnedTags**)
7. 移除GA添加并且标记为GA结束时移除的GameplayCue(**TrackedGameplayCues**)
8. 移除BlockAbilitiesWithTag
9. 清空缓存的目标信息(TargetData)
10. 清空缓存的上下文信息FGameplayEventData

```cpp
void UGameplayAbility::EndAbility(...)
{
...
	//调用蓝图接口处理取消激活操作
	K2_OnEndAbility(bWasCancelled);
	
	//处理绑定的委托
	OnGameplayAbilityEnded.Broadcast(this);
	OnGameplayAbilityEnded.Clear();

	OnGameplayAbilityEndedWithData.Broadcast(...);
	OnGameplayAbilityEndedWithData.Clear();
	
	//标记GA为非激活的
	if (GetInstancingPolicy() != EGameplayAbilityInstancingPolicy::NonInstanced)
	{
		bIsActive = false;
		bIsAbilityEnding = false;
	}
	
	//清理GA启用的Task
	for (int32 TaskIdx = ActiveTasks.Num() - 1; 
	TaskIdx >= 0 && ActiveTasks.Num() > 0; 
	--TaskIdx)
	{
		UGameplayTask* Task = ActiveTasks[TaskIdx];
		if (Task)
		{
			Task->TaskOwnerEnded();
		}
	}
	ActiveTasks.Reset();
	
	
	{
	
		//**ReplicateEndOrCancelAbility**通知对应的段同步执行取消操作(Cancel触发的不会重复执行)
		if (bReplicateEndAbility)
		{
			AbilitySystemComponent->ReplicateEndOrCancelAbility(...);
		}
		

		// 移除附加给GA拥有者的Tag(ActivationOwnedTags)
		AbilitySystemComponent->RemoveLooseGameplayTags(ActivationOwnedTags);
		if (UAbilitySystemGlobals::Get().ShouldReplicateActivationOwnedTags())
		{
			AbilitySystemComponent->RemoveReplicatedLooseGameplayTags(ActivationOwnedTags);
		}

		// 移除GA添加并且标记为GA结束时移除的GameplayCue(**TrackedGameplayCues**)
		for (FGameplayTag& GameplayCueTag : TrackedGameplayCues)
		{
			AbilitySystemComponent->RemoveGameplayCue(GameplayCueTag);
		}
		TrackedGameplayCues.Empty();
		
		
		//移除BlockAbilitiesWithTag
		if (IsBlockingOtherAbilities())
		{
			AbilitySystemComponent->ApplyAbilityBlockAndCancelTags(AbilityTags, 
			this, false, BlockAbilitiesWithTag, false, CancelAbilitiesWithTag);
		}

		//清空缓存的目标信息(TargetData)
		AbilitySystemComponent->ClearAbilityReplicatedDataCache(Handle, 
		CurrentActivationInfo);

	
		AbilitySystemComponent->NotifyAbilityEnded(Handle, this, bWasCancelled);
	}

	//清空缓存的上下文信息FGameplayEventData
	if (IsInstantiated())
	{
		CurrentEventData = FGameplayEventData{};
	}
...
}
```

**UAbilitySystemComponent::ReplicateEndOrCancelAbility**是通过RPC通知对应的执行端同步执行Cancel或者End操作

- **主控客户端触发的就通过RPC通知DS端**
- **DS端触发的就通过RPC通知主控客户端**

> 💡 NetExecutionPolicy为LocalPredicted和ServerInitiated才会需要通过RPC通知另一端
>
> 主控客户端如果想通过RPC转发还行校验下网络权限策略NetSecurityPolicy是否满足(有的GA禁止被主控客户端打断)

```cpp
void UAbilitySystemComponent::ReplicateEndOrCancelAbility(...)
{
**//NetExecutionPolicy为LocalPredicted和ServerInitiated才会需要通过RPC通知另一端**
	if (Ability->GetNetExecutionPolicy() == 
	EGameplayAbilityNetExecutionPolicy::LocalPredicted 
	|| Ability->GetNetExecutionPolicy() == 
	EGameplayAbilityNetExecutionPolicy::ServerInitiated)
	{
				if (GetOwnerRole() == ROLE_Authority)
				{
					if (!AbilityActorInfo->IsLocallyControlled())
					{
						if (bWasCanceled)
						{
							**ClientCancelAbility**(Handle, ActivationInfo);
						}
						else
						{
							**ClientEndAbility**(Handle, ActivationInfo);
						}
					}
				}
				
				//主控客户端如果想通过RPC转发还行校验下网络权限策略NetSecurityPolicy是否满足
				//(有的GA禁止被主控客户端打断)
				else if(Ability->GetNetSecurityPolicy() != 
				EGameplayAbilityNetSecurityPolicy::ServerOnlyTermination && 
				Ability->GetNetSecurityPolicy() != 
				EGameplayAbilityNetSecurityPolicy::ServerOnly)
				{
					if (bWasCanceled)
					{
						**ServerCancelAbility**(Handle, ActivationInfo);
					}
					else
					{
						**CallServerEndAbility**(Handle, ActivationInfo, ScopedPredictionKey);
					}
				}
	}
}
```