> 💡 **本系列文章基于UE5.3**

# 概述

---

GameplayAbility（后面统一简称GA）是Gameplay Ability System (GAS) 中的核心类，用于定义角色可以执行的各种**技能和能力**(如攻击、施法、跳跃、使用道具、射击等)。通过与GameplayEffect(GE)、GameplayCue(GC)、AttributeSet(属性集合)搭配使用搭建UE的能力体系 (GAS系统)。

> 💡 GA不单指传统意义上的技能，其他操作(能力)也可以通过GA实现，比如跳跃、使用道具、射击游戏的开火、换弹、开镜之类的。

# 配置字段说明

---

GA配置需要创建一个继承**UGameplayAbility**或者其子类的蓝图。根据需求在创建的蓝图中配置GA的各项数据。

![Untitled](http://pic.xyyxr.cn/20260504111151772.png)

## **AbilityTags**

---

**AbilityTags** 

**该GA拥有的标记(GameplayeTags)集合。**

*用于标记该GA，比如获取到一个GA的实例，可以通过判断其AbilityTag来确定是否是目标GA*

## **CancelAbilitiesWithTag**

---

**CancelAbilitiesWithTag**  

**用于配置GA之间的打断关系**。已激活的GA列表中如果有GA的AbilityTags配置跟该GA配置的**CancelAbilitiesWithTag**匹配，则当前该GA激活时，GA列表中匹配的GA会被打断。

*比如开火GA打断使用物品的GA，则可以在使用物品GA的AbilityTags配置Tag Ability.UseItem,同时将Tag Ability.UseItem配置到开火GA的CancelAbilitiesWithTag中，则开火GA激活时就会被打断使用物品的GA。*

## **BlockedAbilityTags**

---

**BlockedAbilityTags**  

**用于配置GA之间的互斥关系。**该GA激活时，会阻止后续AbilityTags中拥有**BlockedAbilityTags**集合中任一Tag的GA激活。

*比如开火GA执行期间无法执行使用物品的GA，则可以在使用物品GA的AbilityTags配置Tag Ability.UseItem,同时将Tag Ability.UseItem配置到开火GA的BlockedAbilityTags中，则开火GA执行期间无法执行使用物品的GA。*

## **ActivationOwnedTags**

---

**ActivationOwnedTags**

**该GA激活时会给GA的拥有者附加的Tag**

*GA取消激活时会移除附加的Tag*

## **ActivationRequiredTags**

---

**ActivationRequiredTags** 

**想要该GA能被激活 GA的拥有者必须要有的Tag集合**

*GA的拥有者必须要有ActivationRequiredTags指定的所有Tag*

## **ActivationBlockedTags**

---

**ActivationBlockedTags**  

**想要该GA能被激活 GA的拥有者必需不能有的Tag集合**

*GA的拥有者必须不能有ActivationBlockedTags指定的任一Tag*

## **SourceRequiredTags**

---

**SourceRequiredTags**     

**想要该GA能被激活** **SourceTags集合(*激活GA时按需传入的参数*)必须要有的Tag集合**

*SourceTags集合必须要有*SourceRequiredTags*指定的所有Tag(可以用来检测来源身上的Tag)*

## **SourceBlockedTags**

---

**SourceBlockedTags**     

**想要该GA能被激活 SourceTags集合(*激活GA时按需传入的参数*)必需不能有的Tag集合**

 *SourceTags集合必须不能有SourceBlockedTags 指定的任一Tag(可以用来检测来源身上的Tag)*

## **TargetRequiredTags**

---

**TargetRequiredTags**     

**想要该GA能被激活** **TargetTags集合(*激活GA时按需传入的参数*)必须要有的Tag集合**

 Target*Tags必须要有TargetRequiredTags指定的所有Tag(可以用来检测目标身上的Tag)*

## **TargetBlockedTags**

---

**TargetBlockedTags**     

**想要该GA能被激活TargetTags集合(*激活GA时按需传入的参数*)必需不能有的Tag集合**

 Target*Tags必须不能有TargetBlockedTags指定的任一Tag(可以用来检测目标身上的Tag)*

> 💡 **BlockedAbilityTags\ActivationRequiredTags\ActivationBlockedTags\SourceRequiredTags\SourceBlockedTags\TargetRequiredTags\TargetBlockedTags 参照**
>
> UGameplayAbility::DoesAbilitySatisfyTagRequirements

> 💡 SourceTags和TargetTags一般不会用到，有一个应用场景就是如果通过GE触发了一个GA，而GE是可以捕获到GE来源的Tags集合（SourceTags）和GE目标的Tags集合（TargetTags）。可以将其传给GA，再在GA激活时通过**SourceRequiredTags\SourceBlockedTags\TargetRequiredTags\TargetBlockedTags**进行判定。

## **bReplicateInputDirectly**

---

**bReplicateInputDirectly**  

**是否总是将GA的输入事件(技能键的按下/松开)通过RPC上报给DS**

## **ReplicationPolicy**

---

**ReplicationPolicy**   

**GA网络复制策略** 

> 💡 ***Do Not Replicate** 不复制 (DS和主控端各自创建GA实例)
>
> **Replicate** 复制给技能的拥有者的客户端(主控端)*

```cpp
class GAMEPLAYABILITIES_API UAbilitySystemComponent 
{
	UPROPERTY(ReplicatedUsing = OnRep_ActivateAbilities)
	FGameplayAbilitySpecContainer ActivatableAbilities;
}

struct GAMEPLAYABILITIES_API FGameplayAbilitySpecContainer : public FFastArraySerializer
{
    UPROPERTY()
		TArray<FGameplayAbilitySpec> Items;
}

struct GAMEPLAYABILITIES_API FGameplayAbilitySpec : public FFastArraySerializerItem
{
  UPROPERTY(NotReplicated)
	TArray<TObjectPtr<UGameplayAbility>> NonReplicatedInstances;

	UPROPERTY()
	TArray<TObjectPtr<UGameplayAbility>> ReplicatedInstances;
}
```

简单说明下网络复制策略:

- 赋予角色的GA都会放入可激活GA列表ActivatableAbilities中(*FGameplayAbilitySpecContainer的实例*)，ActivatableAbilities是开启了属性复制的，可以进行网络同步。
- FGameplayAbilitySpecContainer存放的是GA运行时数据结构FGameplayAbilitySpec实例数组
- FGameplayAbilitySpec包含了一个支持网络复制的GA实例列表ReplicatedInstances和不支持网络复制的GA实例列表NonReplicatedInstances。
- 创建GA实例时，会根据GA配置的网络复制策略决定GA实例放到ReplicatedInstances或者NonReplicatedInstances中。在对ActivatableAbilities进行网络同步时，只会同步ReplicatedInstances中的数据

根据GA的网络复制策略配置来决定GA实例是如何在客户端和DS端进行创建的。如果GA配置的网络策略是Do Not Replicate，则在客户端和DS端分别独立创建GA实例，GA实例上的数据不会同步。
如果GA配置的网络策略是Replicate，在GA实例在DS端(主权端)创建，并通过网络复制到客户端(主控客户端)，GA实例上的数据支持网络同步。

*参照FGameplayAbilitySpec::PostReplicatedAdd，在复制FGameplayAbilitySpec时，客户端会调用OnGiveAbility，这里会有个处理如果当前的GA是不支持网络复制的且尚未创建GA实例则会在这里创建一个新的实例(支持网络复制的会在主权端执行GiveAbility时就创建了并通过网络复制同步下来，这里不需要重新创建。主权端的非网络复制的实例也是在GiveAbility创建的)*

```cpp
void FGameplayAbilitySpec::PostReplicatedAdd(...)
{
	if (InArraySerializer.Owner)
	{
		InArraySerializer.Owner->OnGiveAbility(*this);
	}
}
```

```cpp
void UAbilitySystemComponent::OnGiveAbility(FGameplayAbilitySpec& Spec)
{
...
	if (SpecAbility->GetInstancingPolicy() == 
	EGameplayAbilityInstancingPolicy::InstancedPerActor &&
SpecAbility->GetReplicationPolicy() == 
EGameplayAbilityReplicationPolicy::ReplicateNo)
	{
		if (Spec.NonReplicatedInstances.Num() == 0)
		{
			CreateNewInstanceOfAbility(Spec, SpecAbility);
		}
	}
	...
}
```

```cpp

FGameplayAbilitySpecHandle UAbilitySystemComponent::GiveAbility(...)
{
if (OwnedSpec.Ability->GetInstancingPolicy() == 
EGameplayAbilityInstancingPolicy::InstancedPerActor)
	{
		CreateNewInstanceOfAbility(OwnedSpec, Spec.Ability);
	}
}
```

## **InstancingPolicy**

---

**InstancingPolicy** 

**GA的实例化策略** 

> 💡 ***NonInstanced**  不实例化直接用CDO(只读)*
>
> ***InstancedPerActor**  在赋予时实例化
> (激活不再创建新的实例 每个*GameplayAbilitySpec*只会创建一个GA实例)*
>
> ***InstancedPerExecution** 每次激活都实例化一次
> (每个*GameplayAbilitySpec可能创建多个GA实例*)
>
> GameplayAbilitySpec是GA运行时的数据结构。每次赋予一个GA都会创建一份的对应的GameplayAbilitySpec实例放入可激活的GA列表中*

## **bServerRespectsRemoteAbilityCancellation**

---

**bServerRespectsRemoteAbilityCancellation**

**是否能被客户端取消激活(打断)GA**  

*默认设置为True*

## **bRetriggerInstancedAbility**

---

**bRetriggerInstancedAbility**

**如果该GA已经被激活 再次触发激活时是否重新终止原有的GA实例 重新激活**

*仅限实例化策略为InstancedPerActor的GA,其他策略用不到这个配置，为False则已经激活时再次触发激活则激活失败*

## **NetExecutionPolicy**

---

**NetExecutionPolicy**  

**GA的网络执行策略**

*设置由哪个执行端(主控客户端或者DS端)拉取GA的激活流程及GA逻辑在双端都执行还是只在其中一个端执行*

> 💡 **LocalPredicted** 
> **由主控端拉起GA激活流程(取消可以在主控端和DS端发起，GA逻辑在双端执行)**
> 主控客户端触发技能激活，可以在主控端先做一些预判，预判通过后先在主控客户端激活技能效果，然后发给DS端，DS端如果没使用成功则再通知客户端使用失败，回滚之前的激活效果(停止动作、取消特效表现等   参照ClientActivateAbilityFailed)，校验成功也会通知客户端校验成功
>
> **ServerInitiated 
> 由DS端(主权端)拉取GA的执行流程(取消可以在主控端和DS端发起，GA逻辑在双端执行)**
>
> **LocalPredicted和ServerInitiated都会在双端(主控客户端和DS端执行)GA逻辑**
>
> **区别在于:**
>
> **LocalPredicted是由主控端拉取GA激活流程**
>
> **ServerInitiated是由DS端拉取GA激活流程**
>
> **LocalOnly  
> 只会在主控端执行GA逻辑(GA逻辑只在主控端执行)**
>
> **ServerOnly 
> 只会DS端(主权端)执行GA逻辑(GA逻辑只在主权端执行)**

> 💡
>
> **策略LocalPredicted 和 ServerInitiated激活成功双端执行流程**
>
> *策略LocalPredicted主控客户端拉起激活成功时，通知服务器开始激活(服务器校验通过了才能真正执行，校验不过就执行失败)*
>
> *(参照UAbilitySystemComponent::InternalServerTryActivateAbility)*
>
> *策略ServerInitiated主权端的拉起激活成功时，主控客户端一定会执行激活逻辑*
>
> *(参照UAbilitySystemComponent::ClientActivateAbilitySucceedWithEventData)*
>
> **策略LocalPredicted 和 ServerInitiated取消激活双端执行流程**
>
> *主权端的发起取消时，主控客户端一定会执行取消。主控客户端发起取消时，需要有取消权限才会让主权端同时执行取消*
>
> *(参照UAbilitySystemComponent::ReplicateEndOrCancelAbility)*

**如果通过TryActivateAbility接口拉起GA激活，如果当前端不符合网络执行策略，则会通过RPC转发给对应的端执行(***其他接口会直接执行失败***)**

```cpp
bool UAbilitySystemComponent::TryActivateAbility(...)
{
...

//非主控客户端(DS端)想激活**网络执行策略为**LocalOnly和LocalPredicted的GA,通过RPC转发到主控客户端
if (!bIsLocal && 
(Ability->GetNetExecutionPolicy() == EGameplayAbilityNetExecutionPolicy::LocalOnly ||
Ability->GetNetExecutionPolicy() == EGameplayAbilityNetExecutionPolicy::LocalPredicted))
{
if (bAllowRemoteActivation)
{
	ClientTryActivateAbility(AbilityToActivate);
	return true;
}
return false;
}

//非DS端(主控客户端)想激活**网络执行策略为**ServerOnly和ServerInitiated的GA,
//通过RPC转发到DS端
if (NetMode != ROLE_Authority && 
(Ability->GetNetExecutionPolicy()== EGameplayAbilityNetExecutionPolicy::ServerOnly || 
Ability->GetNetExecutionPolicy()== EGameplayAbilityNetExecutionPolicy::ServerInitiated))
	{
		if (bAllowRemoteActivation)
		{
			FScopedCanActivateAbilityLogEnabler LogEnabler;
			if (Ability->CanActivateAbility(...))
			{
				CallServerTryActivateAbility(...);
				return true;
			}
		}

}
```

## **NetSecurityPolicy**

---

**NetSecurityPolicy** 

**GA的网络权限策略**

***主控客户端是否有对GA发起激活或者发起取消激活的权限**
对NetExecutionPolicy的补充说明(对网络执行策略LocalPredicted 和 ServerInitiated补充说明)*

> 💡 **ClientOrServer** 
> 主控客户端和DS(主权端)**都有权限执行激活和取消激活(终止/中断)**
>
> **ServerOnlyExecution**
> **只有DS(主权端)有权限执行激活**。
> 主控客户端和DS(主权端)**都有权限执行取消激活(终止/中断)**
>
> **ServerOnlyTermination** 
> **只有DS(主权端)有权限执行取消激活(终止/中断)**
> 主控客户端和DS(主权端)**都有权限执行激活**
>
> **ServerOnly** 
> **只有DS(主权端)有权限执行激活和取消激活(终止/中断)**

**可以通过权限禁止主控客户端通过RPC拉取网络执行策略(NetExecutionPolicy)为ServerInitiated的GA的激活**

> 💡
>
> 网络执行策略(NetExecutionPolicy)为ServerInitiated的GA,虽然指定只能由DS端触发GA的激活，但如果NetSecurityPolicy没有禁止主控端的激活权限，主控客户端如果通过TryActivateAbility接口拉起GA激活，如果当前端不符合网络执行策略(NetExecutionPolicy)，则会自动通过RPC转发给对应的端执行，如果禁用了激活权限，则不会自动通过RPC转发请求。

**也可以通过权限禁止主控客户端通过RPC结束(中断)网络执行策略(NetExecutionPolicy)为ServerInitiated和LocalPredicted的GA**。

如果通过TryActivateAbility接口拉起GA激活，如果当前端不符合网络执行策略，则会通过RPC转发给对应的端执行，主控端如果想通过RPC转发给DS端拉取GA激活还得有个前提就是网络权限策略(NetSecurityPolicy )配置允许，就是有拉取的权限。

```cpp
bool UAbilitySystemComponent::TryActivateAbility(...)
{
...
//非DS端(主控客户端)想激活**网络执行策略为**ServerOnly和ServerInitiated的GA,
//通过RPC转发到DS端
//CanActivateAbility这里会预判下是否满足执行条件 其中就有对执行权限的判定
if (NetMode != ROLE_Authority && 
(Ability->GetNetExecutionPolicy()== EGameplayAbilityNetExecutionPolicy::ServerOnly || 
Ability->GetNetExecutionPolicy()== EGameplayAbilityNetExecutionPolicy::ServerInitiated))
	{
		if (bAllowRemoteActivation)
		{
			FScopedCanActivateAbilityLogEnabler LogEnabler;
			if (Ability->CanActivateAbility(...))
			{
				CallServerTryActivateAbility(...);
				return true;
			}
		}
}

bool UGameplayAbility::CanActivateAbility(...) const
{
	AActor* const AvatarActor = ActorInfo ? ActorInfo->AvatarActor.Get() : nullptr;
	if (AvatarActor == nullptr || !ShouldActivateAbility(AvatarActor->GetLocalRole()))
	{
		return false;
	}
....
}

bool UGameplayAbility::ShouldActivateAbility(ENetRole Role) const
{
	return Role != ROLE_SimulatedProxy && 		
	(Role == ROLE_Authority ||
	(NetSecurityPolicy != EGameplayAbilityNetSecurityPolicy::ServerOnly && 
	NetSecurityPolicy != EGameplayAbilityNetSecurityPolicy::ServerOnlyExecution));
}
```

当GA执行结束(中断)时，会调用UAbilitySystemComponent::ReplicateEndOrCancelAbility尝试通知另一端执行结束(中断)逻辑，只有网络执行策略(NetExecutionPolicy)为ServerInitiated和LocalPredicted的GA才会需要通过RPC通知另一端。而且主控客户端想要发起RPC还需要有执行结束的权限。

```cpp
void UAbilitySystemComponent::ReplicateEndOrCancelAbility(...)
{

//只有网络执行策略(NetExecutionPolicy)为ServerInitiated和LocalPredicted的GA才会需要通过RPC通知另一端
if (Ability->GetNetExecutionPolicy()==EGameplayAbilityNetExecutionPolicy::LocalPredicted ||Ability->GetNetExecutionPolicy()==EGameplayAbilityNetExecutionPolicy::ServerInitiated)
	{
		
		//DS端通过RPC通知主控客户端
		if (GetOwnerRole() == ROLE_Authority)
		{
			if (!AbilityActorInfo->IsLocallyControlled())
			{
				if (bWasCanceled)
				{
					ClientCancelAbility(Handle, ActivationInfo);
				}
				else
				{
					ClientEndAbility(Handle, ActivationInfo);
				}
			}
		}
		
		//主控客户端通过RPC通知DS端
		//需要判定下是否有有执行结束的权限
else if(
Ability->GetNetSecurityPolicy()!=EGameplayAbilityNetSecurityPolicy:ServerOnlyTermination && 
Ability->GetNetSecurityPolicy() != EGameplayAbilityNetSecurityPolicy::ServerOnly)
		{
			if (bWasCanceled)
			{
				ServerCancelAbility(Handle, ActivationInfo);
			}
			else
			{
				CallServerEndAbility(Handle, ActivationInfo, ScopedPredictionKey);
			}
		}
	}
}
```

> 💡
>
> 网络执行策略(NetExecutionPolicy)和网络权限策略(NetSecurityPolicy )，**只针对联网模式下玩家用到的GA才需要关注**，对于DS端的NPC(AI)用到的GA不需要关注(包括跟玩家共有的GA也只需要考虑玩家用到时的策略)。因为对应AI来说主控端和DS端(主权端)是一样的。

## **CostGameplayEffectClass**

---

**CostGameplayEffectClass**

**处理技能消耗的GE**

*参照UGameplayAbility::CheckCost/UGameplayAbility::ApplyCost*

## **AbilityTriggers**

---

**AbilityTriggers**

 **配置通过Tag来激活或者取消激活GA**

在赋予GA的接口OnGiveAbility中会根据AbilityTriggers配置将配置的Tag和对应的GA Handle绑定。这样就可以通过Tag在GA列表查找到对应的GA。支持一个Tag绑定多个GA。

根据Tag的触发方式分为:

- GameplayEvent:通过SendGameplayEventToActor的方式触发
(参照UAbilitySystemComponent::HandleGameplayEvent)
- OwnedTagAdded:通过添加Tag的方式触发，只负责触发
(参照UAbilitySystemComponent::MonitoredTagChanged)
- OwnedTagPresent:通过添加Tag的方式触发并且在Tag移除时会中断GA
(参照UAbilitySystemComponent::MonitoredTagChanged)

```cpp
void UAbilitySystemComponent::OnGiveAbility(FGameplayAbilitySpec& Spec)
{
	for (const FAbilityTriggerData& TriggerData : Spec.Ability->AbilityTriggers)
	{
		FGameplayTag EventTag = TriggerData.TriggerTag;
   
   //根据Tag的触发方式放到不同的绑定列表
	 auto& TriggeredAbilityMap = 
	 (TriggerData.TriggerSource==EGameplayAbilityTriggerSource::GameplayEvent) ?
	 **GameplayEventTriggeredAbilities** : **OwnedTagTriggeredAbilities**;

		if (TriggeredAbilityMap.Contains(EventTag))
		{
			//支持一个Tag绑定多个GA。
			TriggeredAbilityMap[EventTag].AddUnique(Spec.Handle);
		}
		else
		{
			TArray<FGameplayAbilitySpecHandle> Triggers;
			Triggers.Add(Spec.Handle);
			TriggeredAbilityMap.Add(EventTag, Triggers);
		}

		if (TriggerData.TriggerSource != EGameplayAbilityTriggerSource::GameplayEvent)
		{
			//如果需要监听Tag添加移除事件 在这里处理 绑定处理接口MonitoredTagChanged
			FOnGameplayEffectTagCountChanged& CountChangedEvent = 
			RegisterGameplayTagEvent(EventTag);
			if (!CountChangedEvent.IsBoundToObject(this))
			{
				MonitoredTagChangedDelegateHandle = 
			CountChangedEvent.AddUObject(this, &UAbilitySystemComponent::MonitoredTagChanged);
			}
		}
	}
}
```

SendGameplayEventToActor触发，通过HandleGameplayEvent进行处理

```cpp
void UAbilitySystemBlueprintLibrary::SendGameplayEventToActor(...)
{
	if (::IsValid(Actor))
	{
		UAbilitySystemComponent* AbilitySystemComponent = GetAbilitySystemComponent(Actor);
		if (AbilitySystemComponent != nullptr && IsValidChecked(AbilitySystemComponent))
		{
			FScopedPredictionWindow NewScopedWindow(AbilitySystemComponent, true);
			AbilitySystemComponent->HandleGameplayEvent(EventTag, &Payload);
		}
	}
}

int32 UAbilitySystemComponent::HandleGameplayEvent(...)
{
	int32 TriggeredCount = 0;
	FGameplayTag CurrentTag = EventTag;
	ABILITYLIST_SCOPE_LOCK();
	while (CurrentTag.IsValid())
	{
		if (**GameplayEventTriggeredAbilities**.Contains(CurrentTag))
		{
	...
			for (const FGameplayAbilitySpecHandle& AbilityHandle : TriggeredAbilityHandles)
			{
				if (TriggerAbilityFromGameplayEvent(...))
				{
					TriggeredCount++;
				}
			}
		}

	 //这里还会触发父Tag绑定的GA 
	 //比如 Tag.A和Tag.A.B都绑定了一个GA。则Tag.A.B会同时触发Tag.A.B和Tag.A绑定的GA
		CurrentTag = CurrentTag.RequestDirectParent();
	}

...
}
```

 通过添加Tag触发的

```cpp
void UAbilitySystemComponent::MonitoredTagChanged(...)
{
	ABILITYLIST_SCOPE_LOCK();

	int32 TriggeredCount = 0;
	if (**OwnedTagTriggeredAbilities**.Contains(Tag))
	{
	...
		for (auto AbilityHandle : TriggeredAbilityHandles)
		{
			FGameplayAbilitySpec* Spec = FindAbilitySpecFromHandle(AbilityHandle);

			if (Spec->Ability)
			{
			TArray<FAbilityTriggerData> AbilityTriggers = Spec->Ability->AbilityTriggers;
				for (const FAbilityTriggerData& TriggerData : AbilityTriggers)
				{
					FGameplayTag EventTag = TriggerData.TriggerTag;
					if (EventTag == Tag)
					{
						if (NewCount > 0)
						{
							FGameplayEventData EventData;
							EventData.EventMagnitude = NewCount;
							EventData.EventTag = EventTag;
							EventData.Instigator = GetOwnerActor();
							EventData.Target = EventData.Instigator;
							InternalTryActivateAbility(...);
						}
						else if (NewCount == 0 && 
						TriggerData.TriggerSource == EGameplayAbilityTriggerSource::OwnedTagPresent)
						{
							//OwnedTagPresent 会在Tag移除时中断GA
							CancelAbilitySpec(*Spec, nullptr);
						}
					}
				}
			}
		}
	}
}
```

## **CooldownGameplayEffectClass**

---

**CooldownGameplayEffectClass**

**标记CD的GE**

*一个带有持续时间和标记的GE，通过判定是否持有GE附加的Tag来判定是否处于CD之中。*
*参照UGameplayAbility::CheckCooldown/UGameplayAbility::ApplyCooldown*

# 关于Ability的思考

---

GA作为GAS系统中的主体部分，用于描述一个能力(**Ability**)具体要执行哪些行为。以GA最典型的应用:技能为例。简单技能如火球术，发射一个火球攻击目标。拆分下这个技能需要执行行为，播放一个施法动作、一个施法特效和音效、创建一个火球子弹。播放动作、特效、音效、创建子弹都是一个个独立的行为，将这些行为进行组合就能拼装成一个GA所代表的能力(**Ability**)。

所以**Ability**可以理解成一个个独立的行为节点的拼装组合，GAS系统提供了一套AbilityTask用于定制各种Task(任务，行为)节点，可以将一些常用的行为封装成Task节点然后在GA的蓝图进行组装。GA本身就是一个蓝图，自然可以直接在蓝图写逻辑，**蓝图逻辑搭配Task节点使用兼顾了定制化的灵活性和模板化的可复用性**。

*再举一个复杂一点技能描述：释放后增加30%移动速度持续10秒，移除自身的减速效果，且疾跑期间减少50%受到的减速效果，脱战时额外增加20%的移速。*

将上面的技能描述进行拆解，发现这里的部分行为有个前置条件(疾跑状态，脱战)，类似代码的if条件分支，以此完善下对能力(Ability)的归纳总结:**能力(Ability)就是收到某个触发事件后(Trigger)**(*点击按钮释放*)**执行一系列行为(Actions)***(派发伤害、增加攻击)*，行为节点(Actions)可设置依赖条件(Conditions)(目标血量低于XXX,目标处于XXX状态)来控制节点是否执行(类似if-else/switch-case)*。* 即**Ability=Conditions+Actions**

在GA中，封装的Task或者直接通过蓝图实现的行为即**Actions,**蓝图中的一些if分支即**Conditions。**

此外，UE还有一套非官方的Ability插件**Able Ability System**，其基本思路就是就是将能力(Ability)拆解成一个个行为节点(AblAbilityTask)，并且在时间轴上就行组装，将Conditions和Actions部分以一种更加直观的方式展现出来。提供了一种兼顾可扩展、高复用、直观化、易编辑的Ability解决方案。**插件Able Ability System搭配着GAS系统一起使用效果更佳**。