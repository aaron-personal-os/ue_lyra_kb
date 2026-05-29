> 💡 **本系列文章基于UE5.3**

# 概述

---

GAS中提供了一套GameplayEvent**事件通信机制**，可以通过发送一个Tag和一个GameplayEventData来完成一个事件通信，比如:

- 通过GameplayEvent信号告诉GAS尝试想激活一个GA
- 两个不同的GA通过GameplayEvent信号进行通信交互
- GA执行过程中将执行结果通过GameplayEvent信号通知外部
- GA执行过程中等待外部输入一个GameplayEvent信号触发后续行为

其中Tag是事件的标签，用以识别是什么事件，GameplayEventData是事件附带的参数信息(上下文信息)。

**GameplayEvent的发送接口:** 
UAbilitySystemBlueprintLibrary::**SendGameplayEventToActor**

UGameplayAbility::**SendGameplayEvent**

```cpp
void UAbilitySystemBlueprintLibrary::**SendGameplayEventToActor**(...)
{
	if (::IsValid(Actor))
	{
		UAbilitySystemComponent* AbilitySystemComponent = GetAbilitySystemComponent(Actor);
		if (AbilitySystemComponent != nullptr && IsValidChecked(AbilitySystemComponent))
		{
			AbilitySystemComponent->HandleGameplayEvent(EventTag, &Payload);
		}
	}
}
```

```cpp
void UGameplayAbility::**SendGameplayEvent**(...)
{
	
	if (AbilitySystemComponent)
	{
		AbilitySystemComponent->HandleGameplayEvent(EventTag, &Payload);
	}
}
```

**GameplayEvent的接收接口:**

UAbilitySystemComponent::**HandleGameplayEvent**

```cpp
int32 UAbilitySystemComponent::HandleGameplayEvent(...)
{
	int32 TriggeredCount = 0;
	FGameplayTag CurrentTag = EventTag;
	
	//GA通过GameplayEvent触发激活
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

//绑定指定Tag的事件委托
if (FGameplayEventMulticastDelegate* Delegate = 
GenericGameplayEventCallbacks.Find(EventTag))
	{

		FGameplayEventMulticastDelegate DelegateCopy = *Delegate;
		DelegateCopy.Broadcast(Payload);
	}
...
}
```

# GameplayEventData字段说明

---

FGameplayEventData是触发GameplayEvent附带的参数信息，提供了基本的字段，而且还可以根据需求进行定制扩展。

```cpp
struct GAMEPLAYABILITIES_API FGameplayEventData
{
	...
}
```

> [!note]- 字段说明(点击查看)
> **FGameplayTag EventTag**
>
> 触发事件的Tag
>
> **TObjectPtr<const AActor> Instigator**
>
> GameplayEvent的触发者
>
> **TObjectPtr<const AActor> Target**
>
> GameplayEvent的接收者
>
> **TObjectPtr<const UObject> OptionalObject**
>
> 附加UObject实例1
>
> **TObjectPtr<const UObject> OptionalObject2**
>
> 附加UObject实例2
>
> **FGameplayEffectContextHandle ContextHandle**
>
> 封装的FGameplayEffectContext是GAS体系中用于传递上下文信息的数据结构，**可以通过定制子类进行定制扩展**。
>
> *参照 [GAS-上下文信息-**GameplayEffectContext**](GAS-%E4%B8%8A%E4%B8%8B%E6%96%87%E4%BF%A1%E6%81%AF-GameplayEffectContext.md)* 
>
> **FGameplayTagContainer InstigatorTags**
>
> GameplayEvent的触发者触发GameplayEvent携带的Tag信息
>
> > 💡 *比如GA的配置项SourceRequiredTags\SourceBlockedTags可以在激活时通过传入的FGameplayEventData检测触发时触发者携带的Tag信息*
>
> **FGameplayTagContainer TargetTags**
>
> GameplayEvent的接受者接收GameplayEvent携带的Tag信息
>
> > 💡 *比如GA的配置项TargetRequiredTags\TargetBlockedTags可以在激活时通过传入的FGameplayEventData检测触发时接收者携带的Tag信息*
>
> **float EventMagnitude**
>
> 附加的一个float数据
>
> **FGameplayAbilityTargetDataHandle TargetData**
>
> 封装的FGameplayAbilityTargetData是用于存放生效的目标信息，**可以通过定制子类进行定制扩展**。
>
> *参照 [GA-5.0目标信息](GA-5.0%E7%9B%AE%E6%A0%87%E4%BF%A1%E6%81%AF.md)* 


# GameplayEvent激活GA

---

UAbilitySystemComponent::**TriggerAbilityFromGameplayEvent**是通过GameplayEvent尝试激活一个GA的统一入口。在激活GA的流程中，会传入一个GameplayEventData的参数，可以携带一些激活的附加参数信息。

有两种方式使用GameplayEvent激活GA，一种是能获取到GA的FGameplayAbilitySpecHandle实例则直接调用UAbilitySystemComponent::**TriggerAbilityFromGameplayEvent**进行触发。另一种是

通过UAbilitySystemBlueprintLibrary::**SendGameplayEventToActor**直接向一个指定的Actor（具备UAbilitySystemComponent组件）发送指定的Tag的FGameplayEventData。 GameplayEvent的响应接口UAbilitySystemComponent::**HandleGameplayEvent**会在可激活GA列表查找是否有GA的**AbilityTriggers**配置跟传入的Tag匹配。如果有则对匹配的GA执行UAbilitySystemComponent::**TriggerAbilityFromGameplayEvent。**这种方式不要事先查找到GA的Handle，只需要要指定的个Tag去匹配

```cpp
void UAbilitySystemBlueprintLibrary::**SendGameplayEventToActor**(....)
{
	if (::IsValid(Actor))
	{
		UAbilitySystemComponent* AbilitySystemComponent = 
		GetAbilitySystemComponent(Actor);
		
		if (AbilitySystemComponent != nullptr && 
		IsValidChecked(AbilitySystemComponent))
		{
			AbilitySystemComponent->HandleGameplayEvent(EventTag, &Payload);
		}
	}
}
```

```cpp
int32 UAbilitySystemComponent::HandleGameplayEvent(...)
{

**//尝试激活GA**
	while (CurrentTag.IsValid())
	{
		if (GameplayEventTriggeredAbilities.Contains(CurrentTag))
		{
			TArray<FGameplayAbilitySpecHandle> TriggeredAbilityHandles = 
			GameplayEventTriggeredAbilities[CurrentTag];

			for (const FGameplayAbilitySpecHandle& AbilityHandle : TriggeredAbilityHandles)
			{
				if (TriggerAbilityFromGameplayEvent(AbilityHandle, 
				AbilityActorInfo.Get(), EventTag, Payload, *this))
				{
					TriggeredCount++;
				}
			}
		}

		CurrentTag = CurrentTag.RequestDirectParent();
	}
```

> 💡 GameplayEventTriggeredAbilities是在赋予GA时，根据GA的**AbilityTriggers**配置构建的。如果GA的**AbilityTriggers**配置触发方式是GameplayEvent，则会将触发Tag跟对应的FGameplayAbilitySpecHandle实例进行绑定。
>
> 同一个触发Tag可以绑定多个FGameplayAbilitySpecHandle实例

```cpp
void UAbilitySystemComponent::OnGiveAbility(FGameplayAbilitySpec& Spec)
{
	for (const FAbilityTriggerData& TriggerData : Spec.Ability->AbilityTriggers)
	{
		FGameplayTag EventTag = TriggerData.TriggerTag;

		auto& TriggeredAbilityMap = (TriggerData.TriggerSource == 
		EGameplayAbilityTriggerSource::GameplayEvent) ? 
		GameplayEventTriggeredAbilities : OwnedTagTriggeredAbilities;

		if (TriggeredAbilityMap.Contains(EventTag))
		{
			TriggeredAbilityMap[EventTag].AddUnique(Spec.Handle);
		}
		else
		{
			TArray<FGameplayAbilitySpecHandle> Triggers;
			Triggers.Add(Spec.Handle);
			TriggeredAbilityMap.Add(EventTag, Triggers);
		}
}
```

如果GA触发激活时传入了FGameplayEventData数据，则会在整个激活流程及生效期间进行传递。

- 可以通过FGameplayAbilityTargetData传入的参数信息进行是否激活的判定
- 在激活成功后缓存在GA实例中
- 取消激活时清除

FGameplayEventData可以视为GA执行过程的上下文信息，在GA激活流程和生效期间可以随时按需读取。

```cpp
struct GAMEPLAYABILITIES_API FGameplayEventData
{
	**FGameplayEffectContextHandle ContextHandle;
		
	FGameplayAbilityTargetDataHandle TargetData;**
}
```

FGameplayEventData中的FGameplayEffectContextHandle封装的FGameplayEffectContext是GAS体系中用于传递上下文信息的数据结构。

FGameplayEventData中的FGameplayAbilityTargetDataHandle封装的FGameplayAbilityTargetData是用于存放GA释放时筛选的目标信息。

- 激活前针对FGameplayAbilityTargetData判定
    
```cpp
    bool UAbilitySystemComponent::InternalTryActivateAbility(...)
    {
    ...
    	if (TriggerEventData)
    	{
    		if (!AbilitySource->ShouldAbilityRespondToEvent(ActorInfo, TriggerEventData))
    		{
    			return false;
    		}
    	}
    ....
    }
    
    //可以在GA蓝图实现具体的判定逻辑或者C++中重载ShouldAbilityRespondToEvent
    bool UGameplayAbility::ShouldAbilityRespondToEvent(...) const
    {
    	if (bHasBlueprintShouldAbilityRespondToEvent)
    	{
    		if (K2_ShouldAbilityRespondToEvent(*ActorInfo, *Payload) == false)
    		{
    				return false;
    		}
    	}
    
    	return true;
    }
```
    
- 激活成功后缓存在GA实例中
    
```cpp
    void UGameplayAbility::PreActivate(...)
    {
    	if (TriggerEventData && IsInstantiated())
    	{
    		CurrentEventData = *TriggerEventData;
    	}
    }
```
    
- 取消激活时清除
    
```cpp
    void UGameplayAbility::EndAbility(...)
    {
    		if (IsInstantiated())
    		{
    			CurrentEventData = FGameplayEventData{};
    		}
    }
```
    

# GameplayEvent通信

---

除了通过GameplayEvent激活GA，还可以为指定Tag的GameplayEvent绑定一个委托，当指定Tag的GameplayEvent触发时，执行对应的逻辑。这样就可以通过GameplayEvent在不同的GA，不同的模块进行通信，以GA的Task **UAbilityTask_WaitGameplayEvent**为例展示**GameplayEvent**另一种接收用法，在Task中监听指定Tag的GameplayEvent，当接收到指定的GameplayEvent来时会触发GA定制的后续逻辑。通过GA也可以通过发送指定的GameplayEvent告诉其他GA或者其他模块GA的执行结果

- 在Task添加是绑定指定Tag和对应的委托
    
```cpp
    void UAbilityTask_WaitGameplayEvent::Activate()
    {
    	UAbilitySystemComponent* ASC = GetTargetASC();
    	if (ASC)
    	{
    		if (OnlyMatchExact)
    		{
    			MyHandle = ASC->GenericGameplayEventCallbacks.FindOrAdd(Tag).AddUObject(this, &UAbilityTask_WaitGameplayEvent::GameplayEventCallback);
    		}
    		else
    		{
    			MyHandle = ASC->AddGameplayEventTagContainerDelegate(FGameplayTagContainer(Tag), FGameplayEventTagMulticastDelegate::FDelegate::CreateUObject(this, &UAbilityTask_WaitGameplayEvent::GameplayEventContainerCallback));
    		}	
    	}
    
    	Super::Activate();
    }
```
    

- 在UAbilitySystemComponent::**HandleGameplayEvent**收到Tag时会触发绑定的回调
    
```cpp
    int32 UAbilitySystemComponent::HandleGameplayEvent(...)
    {
    ...
    	if (FGameplayEventMulticastDelegate* Delegate = 
    	GenericGameplayEventCallbacks.Find(EventTag))
    	{
    		FGameplayEventMulticastDelegate DelegateCopy = *Delegate;
    		DelegateCopy.Broadcast(Payload);
    	}
    
    	
    	TArray<TPair<FGameplayTagContainer, FGameplayEventTagMulticastDelegate>> 
    	LocalGameplayEventTagContainerDelegates = GameplayEventTagContainerDelegates;
    	for (TPair<FGameplayTagContainer, 
    	FGameplayEventTagMulticastDelegate>& SearchPair : 
    	LocalGameplayEventTagContainerDelegates)
    	{
    		if (SearchPair.Key.IsEmpty() || EventTag.MatchesAny(SearchPair.Key))
    		{
    			SearchPair.Value.Broadcast(EventTag, Payload);
    		}
    	}
    ...
    }
```
    
> 💡 GenericGameplayEventCallbacks和GameplayEventTagContainerDelegates都是通过Tag绑定GameplayEvent的委托。
>
>     区别在于GenericGameplayEventCallbacks是单个Tag对应一个委托回调
>     GameplayEventTagContainerDelegates是多个Tag(Tag集合TagContainer)对应一个委托回调


```cpp
    	TMap<FGameplayTag, FGameplayEventMulticastDelegate> 
    	**GenericGameplayEventCallbacks**;
    	
    	
    	TArray<TPair<FGameplayTagContainer, FGameplayEventTagMulticastDelegate>> 
    	**GameplayEventTagContainerDelegates**;
```