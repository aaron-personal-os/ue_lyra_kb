> 💡 **本系列文章基于UE5.3**

# 概述

---

本章节介绍UE的属性复制(Property Replication)和远程过程调用(RPC)机制的具体实现流程。

- UE中网络同步的基本单元主要是Actor，每个支持网络同步的Actor都会在网络连接中有一个对应的网络同步通道**ActorChannel**。

- 网络同步主要包含两类:**属性复制(Property Replicate)和RPC**
- **属性同步(Property Replicate)就是同步Actor及其关联且支持复制的SubObject上面变化的属性字段**
SubObject 指的是需要同步的组件UActorComponent和一些关联UObject  比如属性集UAttributeSet

- **RPC(Remote Function Call)主要是同步函数及其参数列表**
主控端上传DS的Server类型  DS端下发主控端的Client类型 DS广播的Multicast类型
****

# 属性复制流程

---

属性复制的核心逻辑:
**DS端比较当前需要网络复制的属性字段是否发生了变化，如果发生变化就将这个变动的字段数据同步给客户端**。

UE引擎底层已经实现了完整的属性对比(CompareProperties)和属性同步(SendProperties)机制，开发者无需手动编写对比和网络同步相关的代码即可实现属性网络复制功能。

实现原理基于反射机制和反射宏标记
**通过反射宏标记需要复制的字段，并为其维护历史数据。在每次检查时，将字段当前值与历史数据对比。如果发现变化，会将变动的字段序列化到网络数据缓存中，随后发送至客户端。**

## 属性复制使用步骤

---

> [!note]- 反射宏标记要网络复制的字段
> ```cpp
> UPROPERTY(Replicated)
>
> UPROPERTY(ReplicatedUsing = OnRep_XXXX)
>
> UPROPERTY(NoReplicated )
> ```
>
> > 💡 **Replicated/ReplicatedUsing** 宏标记属性是需要同步的
> >     (UObject的UPROPERTY字段默认不复制)
> >
> >     **NoReplicated** 复制时跳过改属性
> >     (仅对Struct属性有效 Struct的UPROPERTY字段默认复制)
>
> > 💡
> >
> >     如果启用了PusModel，则只会在字段MarkDirty后才进行对比检测，触发属性复制，可以指定哪些字段启用PusModel模式

> [!note]- 实现GetLifetimeReplicatedProps指定属性复制策略
> ```cpp
> void ACharacter::GetLifetimeReplicatedProps(...) const
> {
>     Super::GetLifetimeReplicatedProps( OutLifetimeProps );
>
>     //非PusModel 模式
>     DOREPLIFETIME_CONDITION( ACharacter, RepRootMotion,COND_SimulatedOnly );
>     DOREPLIFETIME_CONDITION( ACharacter, ReplicatedBasedMovement,   COND_SimulatedOnly );
>
>     //PusModel 模式
>     FDoRepLifetimeParams SharedParams;
>     SharedParams.bIsPushBased = true;
>
>     DOREPLIFETIME_WITH_PARAMS_FAST(UActorComponent, bIsActive, SharedParams);
>     DOREPLIFETIME_WITH_PARAMS_FAST(UActorComponent, bReplicates, SharedParams);
> }
> ```

> [!note]- 启用了PusModel 模式的字段 DS端在修改时需要 MarkDirty 才会进行对比检测 触发属性复制
> ```cpp
> void UActorComponent::SetIsReplicatedByDefault(const bool bNewReplicates)
> {
>     if (LIKELY(NeedsInitialization()))
>     {
>         bReplicates = bNewReplicates;
>         //启用了PusModel 模式的字段 在修改时需要 MarkDirty 才会进行对比检测 触发属性复制
>         MARK_PROPERTY_DIRTY_FROM_NAME(UActorComponent, bReplicates, this);
>     }
> }
> ```

> [!note]- 客户端响应属性变化的处理OnRep_XXXX(按需添加，不是每个复制的字段都需要添加响应)
> ```cpp
> void UActorComponent::OnRep_IsActive()
> {
>     SetComponentTickEnabled(IsActive());
> }
>
> void ULyraHealthSet::OnRep_Health(const FGameplayAttributeData& OldValue)
> {
> ....
> }
> ```


## **属性复制的执行入口**

---

**ReplicateActor**触发属性网络复制的执行入口，先检测Actor自身需要复制的字段，然后再检测Actor关联SubObject的属性复制，收集到所有需要复制的信息后写入网络发送缓存

```cpp
//Actor的属性同步
int64 UActorChannel::ReplicateActor()
{
	...
		// Actor自身属性的复制
		{
		    
	     if (UE::Net::bPushModelValidateSkipUpdate || !bCanSkipUpdate)
			{
				bWroteSomethingImportant |= 
				ActorReplicator->ReplicateProperties(Bunch, RepFlags);
			}
	  }

		// Actor关联SubObject的属性复制
		bWroteSomethingImportant |= DoSubObjectReplication(Bunch, RepFlags);
		
		//写入网络发送缓存
		if (bWroteSomethingImportant)
		{
			FPacketIdRange PacketRange = SendBunch( &Bunch, 1 );
		}
...
}

```

## PushModel

---

属性复制时，如果每帧都去执行属性的对比操作，比较浪费。所以引入了PushModel机制，可以手动标记(MarkDirty)字段被修改了，属性被MarkDirty才会触发对比复制

> [!note]- 需要在配置DefaultEngine.ini中开启PushModel(默认是关闭的)
> ```cpp
> [SystemSettings]
> net.IsPushModelEnabled=1
> ```
>
> ```cpp
>     //PushModel.cpp 默认是关闭的
>     bool bIsPushModelEnabled = false;
>     FAutoConsoleVariableRef CVarIsPushModelEnabled(
>         TEXT("Net.IsPushModelEnabled"),
>         bIsPushModelEnabled,
>         TEXT("Whether or not Push Model is enabled. This networking mode allows game code to notify the networking system of changes, rather than scraping.")
>     );
> ```


> [!note]- GetLifetimeReplicatedProps标记哪些字段启用PushModel
> ```cpp
> void UTestComponent::GetLifetimeReplicatedProps(..) const
> {
>
>
>     FDoRepLifetimeParams Params;
>     //启用PushModel
>     Params.bIsPushBased = true;
>
>     DOREPLIFETIME_WITH_PARAMS_FAST(UTestComponent,TestRepList, Params);
>
> }
>
> ```


> [!note]- 启用PushModel机制的字段在修改时需要手动置脏下
> ```cpp
> //手动MarkDirty
> MARK_PROPERTY_DIRTY_FROM_NAME(UTestComponent, TestRepList, this);
> ```

> [!note]- 属性对比时PushModel机制与非PushModel机制实现
> ```cpp
> static void CompareParentProperties(...)
> {
> #if WITH_PUSH_MODEL
>     //启用了 PushModel 只对比MarkDirty的属性 
>     if (SharedParams.PushModelState != nullptr)
>     {
>     ...
>     for (TConstSetBitIterator<> It = SharedParams.PushModelState->GetDirtyProperties();
>          It; ++It)
>         {
>             UE_RepLayout_Private::CompareParentPropertyHelper(...);
>         }
>
>         //对比完后 重置DirtyState
>         SharedParams.PushModelState->ResetDirtyStates();
>         return;
>     ...
>     }
> #endif // WITH_PUSH_MODEL
>
>     //未启用 PushModel 每次都对比所有需要复制的属性
> for (int32 ParentIndex = 0; ParentIndex < SharedParams.Parents.Num(); ++ParentIndex)
>     {
>         UE_RepLayout_Private::CompareParentPropertyHelper(...);
>     }
> }
> ```


## DS端发起属性复制

---

属性复制首先是需要进行属性对比操作（CompareProperties_r），对比完成之后会更新历史数据和修改记录，然后根据修改记录将发送变动的字段进行序列化放入网络发生缓存(SendProperties_r)。

### **属性复制具体流程**

---

网络同步流程通过**UActorChannel⇒FObjectReplicator⇒FRepLayout**逐层下发执行。

1. **首先需要属性复制的Actor会在对应的网络连接中创建一个UActorChannel对象用于网络通信**
网络连接(NetConnection)会为每个关注的Actor(网络相关)创建一个ActorChannel负责传输该Actor及归属于该Actor且支持网络复制的SubObject(比如Component)的属性复制和RPC
**
2. **在ActorChannel内会维护多个FObjectReplicator实例用于管理Actor本身及其关联的UObject实例的复制操作。**
FObjectReplicator实例真正负责处理属性同步和RPC操作(大部分也是转发到对应的FRepLayout实例处理)。每个ActorChannel都会维护多个FObjectReplicator的实例,用于实际操作网络复制和RPC操作。
    
```cpp
    class UActorChannel : public UChannel
    {
    	//Actor本身对应的FObjectReplicator
    	TSharedPtr<FObjectReplicator> ActorReplicator;
    	//**Actor关联的UObject对应的**FObjectReplicator
    	TMap< UObject*, TSharedRef< FObjectReplicator > > ReplicationMap;
    }
```
    

1. **为每个需要属性复制的UObject(Actor或者Actor关联的UObject)创建一个FRepLayout对象**
FRepLayout维护某一类型的所有支持属性复制字段信息，是属性复制的核心模块。对于同一种类型，只会有一个对应的FReplayout实例，该类型的多个实例共享。里面存放的是需要复制的字段的内存偏移信息。根据内存偏移信息加上传入进来的类型实例，就可以获取到对应类型实例的复制字段数据。

2. **在UNetDriver上维护了一个UObject实例关联的历史数据和修改记录**
需要属性复制的UObject会在UNetDriver上维护一份历史数据和修改记录，同一UObject实例在不同网络连接中共享同一份历史数据和修改记录，在执行对比操作时如果发现有变动就更新历史数据和修改记录信息。
    
```cpp
    class UNetDriver : public UObject, public FExec
    {
    	//在UNetDriver上维护的历史数据和修改记录
    	TMap< UObject*, FReplicationChangelistMgrWrapper >	ReplicationChangeListMap;
    }
```
    
> 💡
>
>     历史数据放在NetDriver上，同一帧只需要其中一个连接执行一次了对比更新历史数据和修改记录即可，其他连接共享更新后的历史数据和修改记录信息*。*
    

有了复制字段的**内存偏移信息FRepLayout实例，需要复制的UObject实例**，**复制字段的历史数据**就可以完成属性复制流程。

> 💡
>
> 在执行属性复制时，根据传入的UObject实例和复制字段偏移新可以获取字段当前数据，再跟历史数据进行对比就可以知道有没有发生变动，变动了则进行序列化放入网络数据缓存中，等待发送。

### 历史记录和修改记录

---

NetDriver的维护的历史数据和修改记录ChangelistMgr，其中修改记录是一个列表(
FRepChangelistState)记录了所有的修改过的字段记录信息(*每次修改了哪几个字段，记录的字段的Handle,根据字段Handle可以获取字段最新数据*)。列表最大为64个，也就是会存放最近64次的修改记录。如果超过64次则会将最早的两次记录做一次合并(FRepLayout::MergeChangeList)。

通过修改记录可以知道都修改了哪些字段，在网络连接维护的FObjectReplicator实例中记录了一个该Object在当前连接中上次同步记录（LastChangelistIndex），在发送修改字段时，根据保存的上次同步记录和当前最新的修改记录对比可以得出本次应该发送哪些修改字段。

> 💡
>
> 这种通过修改记录合并得出最终修改数据的设计是为了配合Actor的属性复制暂停功能。当属性复制恢复时，系统只需同步期间新增的修改记录即可，而无需对所有字段进行全量同步。
>
> 对于持续保持连接的情况，仅需发送最近一次属性对比中发生变化的字段。
>
> 如果属性复制被暂停，暂停期间该角色的属性可能经历了多次修改。再次恢复时，此时由于连接中缺少部分修改记录，则会将所有累积的修改记录去重并合并，作为一次完整的属性复制发送。

> 💡
>
> 当连接出现中断或首次建立时（比如角色断线重连或者首次进入客户端视野），则连接中没有同步记录，相当于把变动的属性数据全量复制一次。

FObjectReplicator在创建实例时会持有一份历史数据和修改记录的共享指针(ChangelistMgr)，用于执行字段对比和属性复制操作，还记录上次同步记录(RepState)。

```cpp
class FObjectReplicator
{
	//当前连接发送记录
	TUniquePtr<FRepState>  RepState;
	//历史数据和修改记录的共享指针
	TSharedPtr<class FReplicationChangelistMgr> ChangelistMgr;
}

//持有一份历史数据和修改记录的共享指针
void FObjectReplicator::StartReplicating(class UActorChannel * InActorChannel)
{
	if (WorldNetDriver && WorldNetDriver->IsServer())
		{
			ChangelistMgr = WorldNetDriver->GetReplicationChangeListMgr(Object);
		}
		else
		{
			ChangelistMgr = ConnectionNetDriver->GetReplicationChangeListMgr(Object);
		}
}

//上次同步记录
class FRepState : public FNoncopyable
{
private:

	friend FRepLayout;

	FRepState() {}

	//当前连接发发送记
	TUniquePtr<FSendingRepState> SendingRepState
}

class FSendingRepState : public FNoncopyable
{
	//上次发送时 最新修改记录的索引
	int32 LastChangelistIndex;
}
```

**修改数据的收集**

```cpp
bool FObjectReplicator::ReplicateProperties_r(FOutBunch& Bunch, FReplicationFlags RepFlags, FNetBitWriter& Writer)
{

//更新历史数据(根据属性对比结果更新 历史数据和修改记录)
	const ERepLayoutResult UpdateResult = FNetSerializeCB::UpdateChangelistMgr(*RepLayout,
 SendingRepState, 
 *ChangelistMgr ....);

	if (UNLIKELY(ERepLayoutResult::FatalError == UpdateResult))
	{
		Connection->SetPendingCloseDueToReplicationFailure();
		return false;
	}

	//收集和发送修改数据
	const bool bHasRepLayout = RepLayout->ReplicateProperties(SendingRepState, ....);

}

bool FRepLayout::ReplicateProperties(...) const
{
	//循环数组 已经超过一个循环了
	if (RepState->LastChangelistIndex <= RepChangelistState->HistoryStart)
	{
		RepState->LastChangelistIndex = RepChangelistState->HistoryStart;
	}
	
	const int32 PossibleNewHistoryIndex = 
	RepState->HistoryEnd % FSendingRepState::MAX_CHANGE_HISTORY;

	FRepChangedHistory& PossibleNewHistoryItem = 
	RepState->ChangeHistory[PossibleNewHistoryIndex];

	TArray<uint16>& Changed = PossibleNewHistoryItem.Changed;
	//合并历史修改记录
	//HistoryEnd其实是为下次对比预留的位置
	for (int32 i = RepState->LastChangelistIndex; i < RepChangelistState->HistoryEnd; ++i)
	{
		const int32 HistoryIndex = i % FRepChangelistState::MAX_CHANGE_HISTORY;

		FRepChangedHistory& HistoryItem = RepChangelistState->ChangeHistory[HistoryIndex];

		TArray<uint16> Temp = MoveTemp(Changed);
		MergeChangeList(Data, HistoryItem.Changed, Temp, Changed);
	}
	
	RepState->LastChangelistIndex = RepChangelistState->HistoryEnd;
	
	....
	if (Changed.Num() > 0)
	{
		SendProperties(...);
	}
}
```

### 属性对比

---

属性复制的流程会分成两种类型进行处理，**一种是通用流程，一种是类似FastArray的自定义增量复制流程**。

```cpp

bool FObjectReplicator::ReplicateProperties_r(...)
{
//通用属性复制流程
//更新历史记录(根据属性对比结果更新 历史数据和修改记录)
 const ERepLayoutResult UpdateResult = FNetSerializeCB::UpdateChangelistMgr(...);
//对变动字段执行属性复制操作
const bool bHasRepLayout = RepLayout->ReplicateProperties(...);

//自定义增量复制流程
//FastArray这种标记为IsCustomDelta的字段 不会再标记为IsLifetime
//在上面的通用属性复制流程中会被跳过
ReplicateCustomDeltaProperties(Writer, RepFlags, bSkippedPropertyCondition);
}
```

```cpp
//FastArray这种标记为IsCustomDelta的字段 不会再标记为IsLifetime
//在通用属性复制流程中会被跳过
void FRepLayout::InitFromClass(...)
{
	if (!EnumHasAnyFlags(Parents[ParentIndex].Flags, ERepParentFlags::IsCustomDelta))
	{
		Parents[ParentIndex].Flags |= ERepParentFlags::IsLifetime;
	}
}
static bool CompareParentProperty(...)
{
	const bool bIsLifetime = EnumHasAnyFlags(Parent.Flags, ERepParentFlags::IsLifetime);
	bool bShouldSkip = !bIsLifetime || !bIsActive;
}
```

**属性对比：通用流程**

---

![Untitled](http://pic.xyyxr.cn/20260504161051768.png)

**属性对比：自定义增量复制流程(FastArray**)

---

![Untitled](http://pic.xyyxr.cn/20260504161051769.png)

**字段数据发送：通用流程**

---

![Untitled](http://pic.xyyxr.cn/20260504161051770.png)

**字段数据发送：自定义增量复制流程(FastArray**)

---

![Untitled](http://pic.xyyxr.cn/20260504161051771.png)

> 💡
>
> Actor上有个字段NetUpdateFrequency可以控制该Actor属性同步的频率

## 客户端收到属性复制

---

客户端收到属性复制的消息包之后，经过FObjectReplicator::ReceivedBunch的分发，最终在**ReceivePropertyHelper**进行处理，也分成**通用流程和自定义增量复制流程(FastArray**)

**收包处理：通用流程**

---

![Untitled](http://pic.xyyxr.cn/20260504161051772.png)

**收包处理：自定义增量复制流程(FastArray**)

---

![Untitled](http://pic.xyyxr.cn/20260504161051773.png)

在执行完属性复制之后，会触发属性复制绑定的OnRep函数(如果绑定了)

```cpp
void FObjectReplicator::PostReceivedBunch()
{
...
	// Call RepNotifies
	CallRepNotifies(true);
...
}
```

# RPC调用流程

---

RPC(Remote Function Call)是通过网络进行函数的调用，发送端通过网络发送调用数据，接收端解析调用数据执行调用逻辑。

## 发送端发起RPC调用

---

![Untitled](http://pic.xyyxr.cn/20260504161051774.png)

在UObject上存在一个RPC调用处理函数**CallRemoteFunction**，在处理UObject的UFunction函数函数时，如果有Remote标记，则会调用CallRemoteFunction通过网络进行RPC调用(UNetDriver::ProcessRemoteFunctionForChannelPrivate)

```cpp
void UObject::ProcessEvent( UFunction* Function, void* Parms )
{
	if ((Function->FunctionFlags & FUNC_Native) != 0)
	{
		int32 FunctionCallspace = GetFunctionCallspace(Function, NULL);
		if (FunctionCallspace & FunctionCallspace::Remote)
		{
			CallRemoteFunction(Function, Parms, NULL, NULL);
		}
	}
}
```

> 💡
>
> 这里有个需要注意的地方,如果在蓝图中一个标记为CallInEditor的蓝图函数并且通过蓝图的Details面板的按钮来执行这个函数,此时如果试图在这个蓝图函数中调用一个RPC函数，则无法触发RPC流程。因为标记为CallInEditor的蓝图函数可以在非PIE时执行，此时都没有网络环境，所以UE直接将通过蓝图的Details面板的按钮来执行函数(CallInEditor)，在其堆栈中调用的函数(包括标记为RPC的)统一视为本地(Local)调用。

![image.png](http://pic.xyyxr.cn/20260504161054382.png)

![image.png](http://pic.xyyxr.cn/20260504161054383.png)

> 💡
>
> 通过蓝图的Details面板的按钮来执行一个CallInEditor函数函数时，触发函数调用的地方是 GetFunctionCallWidgets中的一个Lambda函数OnExecute，可以看到在执行ProcessEvent之前定义了一个FEditorScriptExecutionGuard，这个结构会设置GAllowActorScriptExecutionInEditor为True。也就是在这函数执行的堆栈中所有的通过ProcessEvent执行的函数都会视为本地执行，也就走不到CallRemoteFunction流程。

![image.png](http://pic.xyyxr.cn/20260504161054384.png)

![image.png](http://pic.xyyxr.cn/20260504161054386.png)

```cpp
FEditorScriptExecutionGuard::FEditorScriptExecutionGuard()
	: bOldGAllowScriptExecutionInEditor(GAllowActorScriptExecutionInEditor)
{
	//构造是职位True 并换出之前的状态到bOldGAllowScriptExecutionInEditor
	GAllowActorScriptExecutionInEditor = true;

	if( GIsEditor && !FApp::IsGame() )
	{
		GInitRunaway();
	}
}

FEditorScriptExecutionGuard::~FEditorScriptExecutionGuard()
{
 //析构时恢复之前的状态
	GAllowActorScriptExecutionInEditor = bOldGAllowScriptExecutionInEditor;
}
```

```cpp
int32 AActor::GetFunctionCallspace( UFunction* Function, FFrame* Stack )
{
	if (GAllowActorScriptExecutionInEditor)
	{
		//如果GAllowActorScriptExecutionInEditor 设置为True 都视为本地调用
		DEBUG_CALLSPACE(TEXT("GetFunctionCallspace ScriptExecutionInEditor: %s"), 
		*Function->GetName());
		return FunctionCallspace::Local;
	}
}
```

RPC调用需要发送函数信息和参数列表，也是通过构造FRepLayout实例进行的，

```cpp
void UNetDriver::ProcessRemoteFunctionForChannelPrivate(...)
{
...
	//查找或者创建对应的FRepLayout实例
	TSharedPtr<FRepLayout> RepLayout = GetFunctionRepLayout(Function);
	
	//打包要发送的数据
	RepLayout->SendPropertiesForRPC(Function, Ch, TempWriter, Parms);
	
	//将数据放入 网络缓存中
	if (QueueBunch)
	{
		Ch->QueueRemoteFunctionBunch(TargetObj, Function, Bunch);
	}
	else
	{
		Ch->SendBunch(&Bunch, true);
	}
...
}
```

> [!note]- **RPC函数标记**
> ```cpp
> //DS端调用主控端的 RPC(DS调用 主控端执行)
> UFUNCTION(unreliable, Client)
> void RPC_ClientTest()
>
> //主控端调用DS的RPC(主控端调用 DS端执行)
> UFUNCTION(unreliable, Server)
> void RPC_ServerTest()
>
> //广播RPC(DS端调用 DS端和所有客户端执行)
> UFUNCTION(unreliable, NetMulticast)
> void RPC_MulticastTest()
> ```


> [!note]- **Actor、ActorComponent、GameplayAbility对CallRemoteFunction的实现**
> ```cpp
>
> bool AActor::CallRemoteFunction(...)
> {
>     bool bProcessed = false;
>
>     if (UWorld* MyWorld = GetWorld())
>     {
>         if (FWorldContext* const Context = GEngine->GetWorldContextFromWorld(MyWorld))
>         {
>             for (FNamedNetDriver& Driver : Context->ActiveNetDrivers)
>             {
>                 if (Driver.NetDriver != nullptr && 
>                 Driver.NetDriver->ShouldReplicateFunction(this, Function))
>                 {
>                     Driver.NetDriver->ProcessRemoteFunction(...);
>                     bProcessed = true;
>                 }
>             }
>         }
>     }
>
>     return bProcessed;
> }
>
> bool UActorComponent::CallRemoteFunction(...)
> {
>     bool bProcessed = false;
>
>     if (AActor* MyOwner = GetOwner())
>     {
>         FWorldContext* const Context = GEngine->GetWorldContextFromWorld(GetWorld());
>         if (Context != nullptr)
>         {
>             for (FNamedNetDriver& Driver : Context->ActiveNetDrivers)
>             {
>                 if (Driver.NetDriver != nullptr && 
>                 Driver.NetDriver->ShouldReplicateFunction(MyOwner, Function))
>                 {
>                     Driver.NetDriver->ProcessRemoteFunction(...);
>                     bProcessed = true;
>                 }
>             }
>         }
>     }
>
>     return bProcessed;
> }
>
> bool UGameplayAbility::CallRemoteFunction(...)
> {
>     check(!HasAnyFlags(RF_ClassDefaultObject));
>     check(GetOuter() != nullptr);
>
>     AActor* Owner = CastChecked<AActor>(GetOuter());
>
>     bool bProcessed = false;
>
>     FWorldContext* const Context = GEngine->GetWorldContextFromWorld(GetWorld());
>     if (Context != nullptr)
>     {
>         for (FNamedNetDriver& Driver : Context->ActiveNetDrivers)
>         {
>             if (Driver.NetDriver != nullptr &&
>              Driver.NetDriver->ShouldReplicateFunction(Owner, Function))
>             {
>                 Driver.NetDriver->ProcessRemoteFunction(...);
>                 bProcessed = true;
>             }
>         }
>     }
>
>     return bProcessed;
> }
> ```


> [!note]- **RPC数据写入网络数据包缓存**
> CallRemoteFunction调用网络处理RPC的接口UNetDriver::ProcessRemoteFunction将RPC调用的相关的数据写入网络数据包缓存中。
>
> ![Untitled](http://pic.xyyxr.cn/20260504161054387.png)
>
> ![Untitled](http://pic.xyyxr.cn/20260504161054388.png)

> [!note]- **UNetConnection::FlushNet**将网络缓存中的数据进行推送(Tick里执行或者代码中手动调用)
> ![Untitled](http://pic.xyyxr.cn/20260504161054389.png)

- **UNetConnection::LowLevelSend**负责将收集数据通过网络发送出去

## **接受端收到RPC调用**

---

**UIpNetDriver::TickDispatch**负责处理每帧接收的网络消息包数据，如果是RPC调用的消息包。
会分发到对应的UObject,通过ProcessEvent进行处理。

![Untitled](http://pic.xyyxr.cn/20260504161054390.png)

```cpp
bool FObjectReplicator::ReceivedRPC(...)
{
	UObject* Object = GetObject();
	
	//解析数据
	TSharedPtr<FRepLayout> FuncRepLayout = Connection->Driver->
	GetFunctionRepLayout(LayoutFunction);
	FuncRepLayout->ReceivePropertiesForRPC(...);
	
	//执行调用	
	Object->ProcessEvent(Function, Parms);
}
```