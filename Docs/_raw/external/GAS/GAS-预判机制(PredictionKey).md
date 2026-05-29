> 💡 **本系列文章基于UE5.3**

# 概述

---

GAS提供了一套客户端预判机制，可以在客户端先做判断，判断通过后直接执行效果，然后再发包给服务器，如果服务器判定也通过则正常执行，如果服务器判定不通过，则打断客户端提前执行的逻辑。

> 💡
>
> 比如客户端释放技能时，为了表现的流畅性，一般会在客户端释放时预先做些判定，判定通过后直接预先播放动画和特效之类的表现，而不是等DS端校验成功回包后再播放。如果DS端拒绝执行，则会通知客户端预判失败，打断预先播放的动作和特效表现

GAS的客户端预判机制实现的基本思路是为每个预判操作生成一个凭证(PredictionKey 可以理解为一个自增编号)，执行预判操作后发送给DS端时会附带预判的凭证。DS端尝试执行操作时，会根据执行结果通知客户端预判操作是否能执行，如果被DS端拒绝了则需要打断客户端执行的预判操作。PredictionKey就是在客户端和DS端执行预判操作的凭证(关联两端的操作)。

# 预判凭证(PredictionKey)

---

在AbilitySystemComponent 中维护了一个FPredictionKey的实例ScopedPredictionKey。ScopedPredictionKey记录着执行预判操作时使用的预判凭证。

```cpp
class GAMEPLAYABILITIES_API UAbilitySystemComponent 
{
		FPredictionKey	ScopedPredictionKey;
}

struct GAMEPLAYABILITIES_API FPredictionKey
{
	int16	Current;
	int16	Base;
}
```

> 💡
>
> FPredictionKey的Base值记录的是起始操作凭证值，如果凭证就是起始操作，则Base值为就是0(一个预判操作可能嵌套的其他预判操作，形成一个操作链),Current值是一个自增的全局数(每生成过一个凭证就+1)

## FScopedPredictionWindow

---

ScopedPredictionKey的设置通过一个专门的结构FScopedPredictionWindow来设置，会在构造时设置ScopedPredictionKey新的值，并保留之前的值，在析构时还原之前的值。这样做的目的是为了在FScopedPredictionWindow实例生效区块(Scope代表函数或者代码块)设置一个新的操作凭证，在实例生效区域结束时(触发析构)，自动恢复之前的凭证。因为预判操作可能存在嵌套的情况，一个预判操作在执行过程中可能触发其他预判操作，形成一串预判操作链(Chain)，当嵌套的预判操作执行完成，自然要恢复上一层的预判凭证，因为上一层的预判操作还要继续执行。

```cpp
FScopedPredictionWindow::~FScopedPredictionWindow()
{
	if (UAbilitySystemComponent* OwnerPtr = Owner.Get())
	{
		if (ClearScopedPredictionKey)
		{
			//析构时恢复之前的凭证
			OwnerPtr->ScopedPredictionKey = RestoreKey;
		}
	}
}
```

> 💡
>
> 比如在客户端执行技能激活时，激活技能操作是一个预判操作需要生成一个预判操作凭证，在执行激活时，插入了一个新的预判操作需要新的凭证(比如下面的UAbilityTask_WaitInputPress)，但在新的预判操作执行完成时，需要恢复之前激活技能的操作凭证(因为其他地方可能需要继续用到这个激活技能的预判操作凭证)。

```cpp
bool UAbilitySystemComponent::InternalTryActivateAbility(...)
{
if (Ability->GetNetExecutionPolicy() == 
EGameplayAbilityNetExecutionPolicy::LocalPredicted)
	{
		//激活技能是执行的预判操作
		FScopedPredictionWindow ScopedPredictionWindow(this, true);
		ActivationInfo.SetPredicting(ScopedPredictionKey);
	}
}
```

```cpp
void UAbilityTask_WaitInputPress::OnPressCallback()
{
	FScopedPredictionWindow ScopedPrediction(ASC, IsPredictingClient());
	if (IsPredictingClient())
	{
		ASC->ServerSetReplicatedEvent(... ASC->ScopedPredictionKey);
	}
}
```

FScopedPredictionWindow的构造预判凭证有两种方式:

- 一种是生成新的预判凭证
- 一种是直接继承外部传入的凭证

**FScopedPredictionWindow生成新的预判凭证**

客户端执行预判行为时，FScopedPredictionWindow构造一般会生成一个新凭证，这个新生成的凭证一般需要通过RPC带给DS，在DS对该操作凭证关联的操作进行判定。

```cpp
FScopedPredictionWindow::FScopedPredictionWindow(UAbilitySystemComponent* InAbilitySystemComponent, bool bCanGenerateNewKey)
{

	ClearScopedPredictionKey = false;
	SetReplicatedPredictionKey = false;

	if (bCanGenerateNewKey)
	{
		ClearScopedPredictionKey = true;
		//记录之前的凭证
		RestoreKey = InAbilitySystemComponent->ScopedPredictionKey;
		
		//生成新的凭证
		InAbilitySystemComponent->ScopedPredictionKey.GenerateDependentPredictionKey();		
	}
}

void FPredictionKey::GenerateDependentPredictionKey()
{
	if (bIsServerInitiated)
	{
		//bIsServerInitiated 表示是服务器创建的凭证 
		//不在这个接口创建 走CreateNewServerInitiatedKey
		return;
	}

  //一个预判操作在执行过程中可能会嵌套其他的预判操作 形成操作链
  //Current值是一个自增的全局数(每生成过一个凭证就+1)
  //操作链的生成起始操作凭证Base是0 
  //操作链的后续操作凭证Base值是操作链起始凭证的Current值
	KeyType Previous = Current;
	if (Base == 0)
	{
		Base = Current;
	}

	
	GenerateNewPredictionKey();

//当Base值和Current相差过大 说明操作链太长了 存在死循环风险
	ensureAlwaysMsgf((Base == 0) || (Current - Base < 20), TEXT("Deep PredictionKey Chain Detected.  It's likely there's circular logic that could stack overflow."));

}

void FPredictionKey::GenerateNewPredictionKey()
{
	static KeyType GKey = 1;
	//自增的全局数(每生成过一个凭证就+1)
	Current = GKey++;
	if (GKey < 0)
	{
		GKey = 1;
	}
	bIsStale = false;
}

```

**FScopedPredictionWindow继承外部传入的凭证**

有些FScopedPredictionWindow构造不会生成新的操作凭证，因为这个操作不会触发RPC上报给DS进行判定，或者这个操作本身就是客户端上报给DS端。

> 💡
>
> 比如GA的执行会触发消耗，这个消耗是通过GE扣除某个属性值，这时候GE的Apply的操作也是客户端的预判操作，这个操作不会触发RPC，所以这里GE的预判操作直接继承GA的操作凭证，当DS返回对GA操作凭证的处理时，会移除这个客户端附加的GE效果。这种通过客户端提前Apply GE提前扣除消耗的操作，可以让客户端的GA看起来执行没有延迟。

如果是在DS端使用FScopedPredictionWindow来使用客户端传入的操作凭证，InSetReplicatedPredictionKey 会被置为true，在析构时触发操作凭证的属性复制通知客户端操作被成功执行了。如果失败则一般通过RPC通知客户端，不会使用到FScopedPredictionWindow

```cpp
FScopedPredictionWindow::FScopedPredictionWindow(UAbilitySystemComponent* AbilitySystemComponent, FPredictionKey InPredictionKey, bool InSetReplicatedPredictionKey /*=true*/)
{
	if (AbilitySystemComponent == nullptr)
	{
		return;
	}

	//继承外部传入的凭证(DS端使用客户端凭证需要触发属性复制)
	if (AbilitySystemComponent->IsNetSimulating() == false)
	{
		Owner = AbilitySystemComponent;
		check(Owner.IsValid());
		RestoreKey = AbilitySystemComponent->ScopedPredictionKey;
		AbilitySystemComponent->ScopedPredictionKey = InPredictionKey;
		ClearScopedPredictionKey = true;
		SetReplicatedPredictionKey = InSetReplicatedPredictionKey;
	}
}

FScopedPredictionWindow::~FScopedPredictionWindow()
{
	if (UAbilitySystemComponent* OwnerPtr = Owner.Get())
	{
		if (SetReplicatedPredictionKey)
		{

			if (OwnerPtr->ScopedPredictionKey.IsValidKey())
			{
				const bool bServerInitiatedKey = 
				OwnerPtr->ScopedPredictionKey.IsServerInitiatedKey();
				
				const bool bAllowAckServerInitiatedKey = 
				UE::AbilitySystem::Private::CVarReplicateServerKeysAsAcknowledgedValue > 0;
				
				if (!bServerInitiatedKey || bAllowAckServerInitiatedKey)
				{
					//DS端使用客户端凭证需要触发属性复制
					OwnerPtr->ReplicatedPredictionKeyMap.ReplicatePredictionKey(
					OwnerPtr->ScopedPredictionKey);
				}
			}
		}
		
	}
}
```

> 💡
>
> 每次申请新的预判凭证，ScopedPredictionKey Current就会+1

## FPredictionKeyDelegates

---

FPredictionKeyDelegates为每个预判凭证PredictionKey绑定执行成功和失败的委托，在收到执行成功或者失败的反馈时可以做对应的处理。

```cpp
struct FPredictionKeyDelegates
{

public:
	//绑定执行失败的委托
	static FPredictionKeyEvent&	NewRejectedDelegate(FPredictionKey::KeyType Key);
	
	//绑定执行成功的委托
	static FPredictionKeyEvent&	NewCaughtUpDelegate(FPredictionKey::KeyType Key);

	//执行失败的回调处理
	static void Reject(FPredictionKey::KeyType Key);
	
	//执行成功的回调处理
	static void CatchUpTo(FPredictionKey::KeyType Key);

};
```

对应类似上面例子中在技能激活的预判操作中再插入一个Task的预判操作，Task插入的操作是依赖于技能操作的，这种存在依赖关系的预判操作，会跟随被依赖的操作一同执行成功或者失败。

当技能预判的激活被拒绝时，依赖于这个操作的其他预判操作都会触发执行失败的回调，这样就可以将相关的操作自动终止。

在预判激活技能时预判执行动画或者GameplayCue播放特效之类的操作时，也可以直接用激活技能的预判凭证，而不生成新的凭证，将失败的处理绑定在激活技能的预判凭证上，当凭证被拒绝执行时，自动会调用对应的终止操作。

> 💡
>
> 对于多个操作形成的操作链(多个操作嵌套在起始操作内部)，如果起始操作执行成功或失败都会影响到嵌套的操作执行。

```cpp
void FPredictionKey::GenerateDependentPredictionKey()
{
	...
	KeyType Previous = Current;
	if (Base == 0)
	{
		Base = Current;
	}

	
	GenerateNewPredictionKey();

  //操作链的后续嵌套操作 依赖起始操作的成功或者失败
	if (Previous > 0)
	{
		FPredictionKeyDelegates::AddDependency(Current, Previous);
	}
}

//对于多个操作形成的操作链(多个操作嵌套在起始操作内部)
//如果起始操作执行成功或失败都会影响到嵌套的操作执行
void FPredictionKeyDelegates::AddDependency(...)
{
	NewRejectedDelegate(DependsOn).BindStatic(&FPredictionKeyDelegates::Reject, ThisKey);
	NewCaughtUpDelegate(DependsOn).BindStatic(&FPredictionKeyDelegates::CatchUpTo, ThisKey);
}

```

## 预判凭证的网络复制

---

大部分预判凭证(FPredictionKey)是由客户端生成，通过RPC上传到DS，如果执行失败，则凭证会跟随通知执行失败的RPC下发给客户端，客户当根据凭证绑定的委托回调执行失败清理操作。如果执行成功则会统一走属性复制下发给客户端，客户端收到属性复制下发的凭证，凭证表示对应的操作执行成功了，可以根据绑定的委托回调执行对应的处理。

**技能预判执行失败，会通过RPC通知客户端执行对应的回调处理**

```cpp
void UAbilitySystemComponent::InternalServerTryActivateAbility(...)
{
....
if (InternalTryActivateAbility(....))
	{
		
	}
	else
	{
	
		//执行失败通过RPC 通知客户端端

		ClientActivateAbilityFailed(Handle, PredictionKey.Current);
		Spec->InputPressed = false;

		MarkAbilitySpecDirty(*Spec);
	}
...
}

UFUNCTION(Client, Reliable)
void	ClientActivateAbilityFailed(...);

void UAbilitySystemComponent::ClientActivateAbilityFailed_Implementation(...)
{
	// 通知操作执行失败了
	if (PredictionKey > 0)
	{
		FPredictionKeyDelegates::BroadcastRejectedDelegate(PredictionKey);
	}
	
	//终止技能的执行
	for (UGameplayAbility* Ability : Instances)
	{
		if (Ability->CurrentActivationInfo.GetActivationPredictionKey().Current == 
		PredictionKey)
		{
			Ability->CurrentActivationInfo.SetActivationRejected();
			Ability->K2_EndAbility();
		}
	}
}
```

技能执行在DS端成功了，会在FScopedPredictionWindow 通过ReplicatePredictionKey触发凭证的属性复制，客户端接受到属性复制后触发凭证对应的执行成功回调。

```cpp
bool UAbilitySystemComponent::InternalTryActivateAbility(...)
{
	if (NetMode == ROLE_Authority))
	{
		
		//这里将技能附带的凭证信息 设置到ScopedPredictionKey
		if (InPredictionKey.IsValidKey())
		{
			ActivationInfo.ServerSetActivationPredictionKey(InPredictionKey);
		}
		
		FScopedPredictionWindow ScopedPredictionWindow(this, 
		ActivationInfo.GetActivationPredictionKey());
	}
}

//在析构上面设置的凭证时 会触发一个网络复制ReplicatedPredictionKeyMap，
//表明DS端完成了一个预判凭证的执行
FScopedPredictionWindow::~FScopedPredictionWindow()
{
	if (UAbilitySystemComponent* OwnerPtr = Owner.Get())
	{
		if (SetReplicatedPredictionKey)
		{
			
			if (OwnerPtr->ScopedPredictionKey.IsValidKey())
			{
				//在UAbilitySystemComponent 上有一个凭证容器ReplicatedPredictionKeyMap
				//存放着客端上传的凭证
				//这里用属性复制可以减少RPC的调用且可以一次下发多个凭证数据
				OwnerPtr->ReplicatedPredictionKeyMap.ReplicatePredictionKey(
				OwnerPtr->ScopedPredictionKey);
			}
		}

	}
}
	

//触发属性复制
void FReplicatedPredictionKeyMap::ReplicatePredictionKey(FPredictionKey Key)
{	
	int32 Index = (Key.Current % KeyRingBufferSize);
	
	//这里存在一个隐患
	//断线重连时 DS有可能出现复用之前连接的Key 导致 Key不会正确复制到客户端
	//(断线重连后，客户端上传的凭证是重新开始计数的,这些计数可能还在DS上的容器存放着,
	//此时调用MarkItemDirty会因为FastArray元素内部的PredictionKey并未发生变化
	//而不会触发PredictionKey的复制)
	//可以考虑这里做下处理(如果发现客户端上传凭证计数一致，但连接对象不一致，
	//重置下ReplicationID 这样MarkItemDirty是会视为这是一个新元素而执行PredictionKey的复制)
	if (!Key.bIsServerInitiated &&
		Key == PredictionKeys[Index].PredictionKey &&
		Key.GetPredictiveConnectionKey() != 
		PredictionKeys[Index].PredictionKey.GetPredictiveConnectionKey())
	{
		PredictionKeys[Index].ReplicationID = INDEX_NONE;
		PredictionKeys[Index].ReplicationKey = INDEX_NONE;
		PredictionKeys[Index].MostRecentArrayReplicationKey = INDEX_NONE;
	}
	
	PredictionKeys[Index].PredictionKey = Key;
	MarkItemDirty(PredictionKeys[Index]);
	
}	
	
void FReplicatedPredictionKeyItem::OnRep()
{
	//客户端接收到复制消息时 会触发凭证执行成功的回调
	FPredictionKeyDelegates::CatchUpTo(PredictionKey.Current);
}
```

## Server生成的凭证

---

如果技能时由DS端发起的激活，也会生成一个DS端的凭证，作为DS发起该操作的一个凭证。这个凭证会有个标识来表示这个是DS端创建的凭证。

```cpp
bool UAbilitySystemComponent::InternalTryActivateAbility(...)
{
	if (NetMode == ROLE_Authority))
	{
		
		bool bCreateNewServerKey = NetMode == ROLE_Authority &&
			(!InPredictionKey.IsValidKey() ||
			 (Ability->GetNetExecutionPolicy() == 
			 EGameplayAbilityNetExecutionPolicy::ServerInitiated ||
			  Ability->GetNetExecutionPolicy() == 
			  EGameplayAbilityNetExecutionPolicy::ServerOnly));
			  
		if (bCreateNewServerKey)
		{
			ActivationInfo.ServerSetActivationPredictionKey(
			FPredictionKey::CreateNewServerInitiatedKey(this));
		}
	}
}

FPredictionKey FPredictionKey::CreateNewServerInitiatedKey(...)
{
	FPredictionKey NewKey;
	
	if (OwningComponent->GetOwnerRole() == ROLE_Authority)
	{
		NewKey.GenerateNewPredictionKey();
		NewKey.bIsServerInitiated = true;
	}
	return NewKey;
}

```

有些AbilityTask可能在主控端和DS端都需要执行，两端的Task执行过程中，可能需要通过RPC进行通信， 一般都是在双端各自创建Task，然后再通过ASC提供的一套RPC接口进行内部事件同步，AbilityTargetDataMap是以AbilityHandle，PredictionKey作为Key的Map,映射到一个处理事件的委托。RPC通信过程中可以通过AbilityHandle，PredictionKey查找到本次操作对应的处理委托进行事件的触发。具体可以参考UAbilityTask_NetworkSyncPoint的实现

> 💡
>
> UAbilityTask_NetworkSyncPoint是一个等待服务器或者客户端执行结果的节点，如果服务器触发的GA且执行了UAbilityTask_NetworkSyncPoint等待客户端的执行结果，服务器就需要为GA操作生成一个操作凭证作为本次操作的识别依据，当客户端RPC上来时才能找到对应的回调进行执行。

```cpp
UFUNCTION(Server, reliable, WithValidation)
void ServerSetReplicatedEvent(...);

void UAbilitySystemComponent::ServerSetReplicatedEvent_Implementation(...)
{
	FScopedPredictionWindow ScopedPrediction(this, CurrentPredictionKey);

	InvokeReplicatedEvent(...);
}

UFUNCTION(Client, reliable)
void ClientSetReplicatedEvent(....);

void UAbilitySystemComponent::ClientSetReplicatedEvent_Implementation(...)
{
	InvokeReplicatedEvent(...);
}

bool UAbilitySystemComponent::InvokeReplicatedEvent(...)
{
	TSharedRef<FAbilityReplicatedDataCache> ReplicatedData = 
	AbilityTargetDataMap.FindOrAdd(FGameplayAbilitySpecHandleAndPredictionKey(
	AbilityHandle, AbilityOriginalPredictionKey));

	ReplicatedData->GenericEvents[(uint8)EventType].bTriggered = true;
	ReplicatedData->PredictionKey = CurrentPredictionKey;

	if (ReplicatedData->GenericEvents[EventType].Delegate.IsBound())
	{
		ReplicatedData->GenericEvents[EventType].Delegate.Broadcast();
		return true;
	}
	else
	{
		return false;
	}
}
```

# 技能的预判执行

---

以技能客户端预判执行为示例，介绍下预判的执行流程

- 首先生成激活预判凭证，将凭证记录到Ability中，RPC时带上该凭证
    
```cpp
    bool UAbilitySystemComponent::InternalTryActivateAbility(...)
    {
    if (Ability->GetNetExecutionPolicy() == 
    EGameplayAbilityNetExecutionPolicy::LocalPredicted)
    	{
    		//激活技能是执行的预判操作
    		FScopedPredictionWindow ScopedPredictionWindow(this, true);
    		
    		//将凭证记录到Ability中
    		ActivationInfo.SetPredicting(ScopedPredictionKey);
    		
    		//RPC时带上该凭证
    		CallServerTryActivateAbility(Handle, Spec->InputPressed, ScopedPredictionKey);
    	}
    }
```
    
- 如果执行失败触发凭证的失败回调，同时也会直接结束客户激活的技能
    
    
- 如果执行了动画的预判执行，会绑定凭证执行失败的回调处理(GameplayCue也是类似)
    
```cpp
    float UAbilitySystemComponent::PlayMontage()
    {
    	FPredictionKey PredictionKey = GetPredictionKeyForNewAction();
    	if (PredictionKey.IsValidKey())
    	{
    		PredictionKey.NewRejectedDelegate().BindUObject(this, 
    		&UAbilitySystemComponent::OnPredictiveMontageRejected, NewAnimMontage);
    	}
    }
```
    

- 执行成功的话，会在DS通过属性复制的方式通知给客户端

# GE的预判执行

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