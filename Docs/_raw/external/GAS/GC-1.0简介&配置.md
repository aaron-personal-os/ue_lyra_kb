> 💡 **本系列文章基于UE5.3**

# 概述

---

**GameplayCue是用来播放客户端表现**(特效、音效、动画、材质效果、后处理之类的)

**GameplayCue的特性**：

- **解耦逻辑和表现**
通过 GameplayCue，可以将游戏逻辑与表现分开，使得逻辑更清晰，表现更容易调整。
- **灵活性和可扩展性**
可以定义各种不同类型的 Cue，根据需要调整和扩展效果。
- **通过GameplayTag触发GameplayCue**
每个GameplayCue都绑定了一个对应的GameplayTag

可以在菜单栏 ****工具-GameplayeCue编辑器 窗口查看GameplayCue和GameplayTag的绑定

![Untitled](http://pic.xyyxr.cn/20260504111153517.png)

## **GameplayCue的状态**

---

**OnActive**
对于具有生命周期的持续效果，激活(Add)表现效果(首次激活时触发)
*对应GameplayCue的OnActive接口*

**WhileActive**
对于具有生命周期的持续效果，激活(Add)表现效果(每次复制到客户端都会触发 即使不是刚刚激活)
*对应GameplayCue的WhileActive接口*

**Removed**
对于具有生命周期的持续效果，移除表现效果。
*对应GameplayCue的OnRemove接口*
****

**Executed**
对于一次性的即时效果，执行表现效果。
*对应GameplayCue的OnExecute接口*
****

> 💡
>
> WhileActive大部分情况下等同于OnActive，但有一种情况只会调用WhileActive不会调用OnActive。当一个持续的表现效果激活后因为网络裁切或者断线重连消失在玩家视野或者激活因为裁切不在视野内，然后重新进入视野时重新在客户端触发激活(Add)表现效果。
>
> 再次进入视野时从DS复制下来的表现效果因为不是首次触发激活，不会在执行*OnActive*
>
> 比如下面实例代码，一个附加GC表现效果的GE,在通过网络复制添加到客户时，如果GE激活时间在3s内会视为GE刚被激活，触发GC的OnActive,超过3s则认为不是刚被激活从而不触发GC的OnActive。但WhileActive是总是会被触发
>
> 还有就是除了GE上的附加的GC效果，其他的可持续的GC效果走的GC容器的属性复制下发给客户端。OnActive只会在加入GC容器时触发，而WhileActive则是每次复制到客户端都会触发(*加入容器、断线重连、离开网络裁切范围都会触发复制到客户端*)
>
> 根据具体需求决定用哪个接口处理。**大部分情况应该用WhileActive更合适**

```cpp
void FActiveGameplayEffect::PostReplicatedAdd(...)
{
		static const float MAX_DELTA_TIME = 3.f;
		float DeltaServerWorldTime = ServerWorldTime - StartServerWorldTime;
		
		if (ShouldInvokeGameplayCueEvents)
		{
			//在3s内会视为GE刚被激活，触发GC的OnActive,
			//超过3s则认为不是刚被激活从而不触发GC的OnActiv
				bPendingRepOnActiveGC = (ServerWorldTime > 0 && 
				FMath::Abs(DeltaServerWorldTime) < MAX_DELTA_TIME);
		}
		
		if (ShouldInvokeGameplayCueEvents)
		{
			//WhileActive是总是会被触发
			bPendingRepWhileActiveGC = true;
		}
	
}

//OnActive只会在加入GC容器时触发
//而WhileActive则是每次复制到客户端都会触发(*加入容器和断线重连都会触发复制到客户端*)
void UAbilitySystemComponent::AddGameplayCue_Internal(...)
{
...
	ForceReplication();
	//添加到容器
	GameplayCueContainer.AddCue(...);
	
	//激活事件OnActive单独通过广播RPC触发
	if (IAbilitySystemReplicationProxyInterface* ReplicationInterface =
	 GetReplicationInterface())
		{
			ReplicationInterface->Call_InvokeGameplayCueAdded_WithParams(GameplayCueTag,
			 PredictionKeyForRPC, GameplayCueParameters);
		}

...
}

void FActiveGameplayCue::PostReplicatedAdd(...)
{
	if (!InArray.Owner)
	{
		return;
	}

	InArray.Owner->UpdateTagMap(GameplayCueTag, 1);

	if (PredictionKey.IsLocalClientKey() == false)
	{
		//网络复制下来时 都会调用的WhileActive(不仅限于首次触发)
		InArray.Owner->InvokeGameplayCueEvent(..., EGameplayCueEvent::WhileActive);
	}
}

```

```cpp
namespace EGameplayCueEvent
{

	enum Type : int
	{
		/** Called when a GameplayCue with duration is first activated, 
		this will only be called if the client witnessed the activation */
		//在首次激活时调用，客户端见证激活时触发。
		OnActive,

		/** Called when a GameplayCue with duration is first seen as active,
		 even if it wasn't actually just applied (Join in progress, etc) */
		 //在持续活跃时调用，即使不是刚刚激活（比如中途加入游戏）
		WhileActive,

		/** Called when a GameplayCue is executed, 
		this is used for instant effects or periodic ticks */
		//执行时调用，用于瞬时效果或周期性触发。
		Executed,

		/** Called when a GameplayCue 
		with duration is removed */
		//移除时调用。
		Removed
	};
}
```

```cpp
void UGameplayCueNotify_Static::HandleGameplayCue(...)
{
...
		K2_HandleGameplayCue(MyTarget, EventType, Parameters);

		switch (EventType)
		{
		case EGameplayCueEvent::OnActive:
			OnActive(MyTarget, Parameters);
			break;

		case EGameplayCueEvent::WhileActive:
			WhileActive(MyTarget, Parameters);
			break;

		case EGameplayCueEvent::Executed:
			OnExecute(MyTarget, Parameters);
			break;

		case EGameplayCueEvent::Removed:
			OnRemove(MyTarget, Parameters);
			break;
		};
...
}

void AGameplayCueNotify_Actor::HandleGameplayCue(...)
{
...
K2_HandleGameplayCue(MyTarget, EventType, Parameters);
switch (EventType)
{
case EGameplayCueEvent::OnActive:
	OnActive(MyTarget, Parameters);
	bHasHandledOnActiveEvent = true;
	break;

case EGameplayCueEvent::WhileActive:
	WhileActive(MyTarget, Parameters);
	bHasHandledWhileActiveEvent = true;
	break;

case EGameplayCueEvent::Executed:
	OnExecute(MyTarget, Parameters);
	break;

case EGameplayCueEvent::Removed:
	bHasHandledOnRemoveEvent = true;
	OnRemove(MyTarget, Parameters);
	break;
};
...
}
```

## **GameplayCue的触发方式**

---

**GE配置GameplayCue关联的GameplayTag**

![Untitled](http://pic.xyyxr.cn/20260504111153518.png)

**GA调用对应的接口触发**

![Untitled](http://pic.xyyxr.cn/20260504111155840.png)

**调用对应静态函数触发**

![Untitled](http://pic.xyyxr.cn/20260504111155841.png)

# 配置

---

GameplayCue可以通过创建蓝图的方式来创建，蓝图的基类可以选择

- **UGameplayCueNotify_Static**
- **AGameplayCueNotify_Actor**
- **UGameplayCueNotify_Burst(**GCN Burst**)**
- **AGameplayCueNotify_BurstLatent**(GCN Burst Latent)
- **AGameplayCueNotify_Looping**(GCN Looping)。

可以根据具体需求在上述基类中派生具体的子类来扩展。

![Untitled](http://pic.xyyxr.cn/20260504111155842.png)

**创建完后，为其关联Tag。**

![Untitled](http://pic.xyyxr.cn/20260504111155843.png)

GameplayCue主要分为两类

- **GameplayCueNotify_Static**
- **GameplayCueNotify_Actor**

**GameplayCueNotify_Static**

继承自UObject使用时直接用CDO对象，触发表现效果时不会产生单独的实例对象。

**GameplayCueNotify_Actor**

继承自Actor，触发表现效果时会产生一个Actor实例对象。(会有对象池管理)

在这两个基类的基础上提供了几个通用的子类，方便配置一些常用的表现效果。比如GameplayCueNotify_Burst(GCN Burst)

GameplayCueNotify_BurstLatent(GCN Burst Latent)

GameplayCueNotify_Looping(GCN Looping)

> 💡
>
> 这几个子类都提供了一些常见的表现配置，可以直接通过配置就实现一些表现效果，不需要写额外的处理逻辑。
>
> 推荐用法是从GameplayCueNotify_Burst(GCN Burst)、GameplayCueNotify_BurstLatent(GCN Burst Latent)、
>
> GameplayCueNotify_Looping(GCN Looping)三个通用子类进行派生
>
> GameplayCueNotify_BurstLatent、GameplayCueNotify_BurstLatent一般用于播放一次性的即时表现效果
>
> GameplayCueNotify_Looping一般用于持续性的循环表现效果

> 💡 **一次性的即时表现效果：**
> 固定时长的表现效果，时间到了效果会自动结束，比如一个持续5s的粒子特效，一个持续1s的摄像机效果，时间到了效果会自动结束，一般不支持手动提前结束。GC只负责触发表现，不关注触发后的处理
>
> **持续性的循环表现效果:**
> 可以是一个固定时长的表现效果，也可以是一直循环播放的效果，支持手动提前结束。需要关注表现的该何时结束或者中断。

****

## **GameplayCueNotify_Static**

---

继承自UObject 使用时直接用CDO对象(只读 全局共享对象) 不会产生单独的实例对象，所以不要在蓝图里存放变量。因为不需要每次都创建一个实例且继承自UObject ，**开销会较小**，**适用于不需要创建单独的实例的表现效果**，比如一个持续5s的粒子特效，一个持续1s的摄像机效果，只负责触发播放，不用关心后续操作，效果会自动结束。

一般实现OnExecute接口(一次性触发)。

```cpp
bool UGameplayCueSet::HandleGameplayCueNotify_Internal(...)
{	
	....
	
		if (UGameplayCueNotify_Static* NonInstancedCue = 
Cast<UGameplayCueNotify_Static>(**CueData.LoadedGameplayCueClass->ClassDefaultObject**))
		{
		  //UGameplayCueNotify_Static直接用CDO对象
			if (NonInstancedCue->HandlesEvent(EventType))
			{
				NonInstancedCue->HandleGameplayCue(TargetActor, EventType, Parameters);
				bReturnVal = true;
				
				if (!NonInstancedCue->IsOverride)
				{
				**//如果IsOverride标记为False 则会触发父级Tag关联的GameplayCue
				//比如该GameplayCue 关联的Tag是 Damage.Physical.Slash
				//则还会触发Tag Damage.Physical关联的GameplayCue**
					HandleGameplayCueNotify_Internal(TargetActor, CueData.ParentDataIdx,
					 EventType, Parameters);
				}
			}
			else
			{
				//Didn't even handle it, so IsOverride should not apply.
				HandleGameplayCueNotify_Internal(TargetActor, 
				CueData.ParentDataIdx, EventType, Parameters);
			}
		}
	
....
	return bReturnVal;
}
```

### 配置字段

---

```cpp
class GAMEPLAYABILITIES_API UGameplayCueNotify_Static : public UObject
{
...
	//关联的Tag
	UPROPERTY(EditDefaultsOnly)
	FGameplayTag	GameplayCueTag;

	//默认为True 
	//如果这个值标记为False 则会触发父级Tag关联的GameplayCue
	//比如该GameplayCue 关联的Tag是 Damage.Physical.Slash
	//如果为False 则还会触发Tag Damage.Physical关联的GameplayCue
	UPROPERTY(EditDefaultsOnly, Category = GameplayCue)
	bool IsOverride;
...
}
```

- **GameplayCueTag**
关联的Tag
- **IsOverride**
默认为True ，如果这个值标记为False 则会触发父级Tag关联的GameplayCue
    
> 💡
>
>     比如该GameplayCue 关联的Tag是 Damage.Physical.Slash
>     如果为False 则还会触发Tag Damage.Physical关联的GameplayCue
    

## **GameplayCueNotify_Actor**

---

继承自Actor 使用时会产生一个Actor实例对象。相当于在场景内创建了一个Actor对象。**适用于那些复杂些的持续表现效果**，可能需要一个维护生命周期和状态信息。**一般在表现效果添加时执行OnActive接口，表现效果移除时执行OnRemove接口。**

```cpp
bool UGameplayCueSet::HandleGameplayCueNotify_Internal(...)
{	
	....
	
		if (AGameplayCueNotify_Actor* InstancedCue = Cast<AGameplayCueNotify_Actor>
		(CueData.LoadedGameplayCueClass->ClassDefaultObject))
		{
			if (InstancedCue->HandlesEvent(EventType))
			{
				if (TargetActor)
				{
					//AGameplayCueNotify_Actor 会生成一个Actor实例对象
					AGameplayCueNotify_Actor* SpawnedInstancedCue = 
					CueManager->GetInstancedCueActor(TargetActor, 
					CueData.LoadedGameplayCueClass, Parameters);
					
					if (ensure(SpawnedInstancedCue))
					{
						SpawnedInstancedCue->HandleGameplayCue(TargetActor, EventType, Parameters);
						bReturnVal = true;
						if (!SpawnedInstancedCue->IsOverride)
						{
							**//如果IsOverride标记为False 则会触发父级Tag关联的GameplayCue
							//比如该GameplayCue 关联的Tag是 Damage.Physical.Slash
							//则还会触发Tag Damage.Physical关联的GameplayCue**
							HandleGameplayCueNotify_Internal(TargetActor, CueData.ParentDataIdx, 
							EventType, Parameters);
						}
					}
				}
			}
		}
....
	return bReturnVal;
}
```

**支持将GameplayCueNotify_Actor对象放到一个对象池维护，便于复用(默认开启对象池)**

> 💡 实例有可能是放到一个对象池维护的，所以在表现效果移除时(OnRemove)，记得重置存放的变量信息

```cpp
int32 GameplayCueActorRecycle = 1;

static FAutoConsoleVariableRef CVarGameplayCueActorRecycle(
TEXT("AbilitySystem.GameplayCueActorRecycle"), 
GameplayCueActorRecycle, T
EXT("Allow recycling of GameplayCue Actors"), ECVF_Default );

bool UGameplayCueManager::IsGameplayCueRecylingEnabled()
{
	return GameplayCueActorRecycle > 0;
}
```

### 配置字段

![Untitled](http://pic.xyyxr.cn/20260504111155844.png)

---

- **GameplayCueTag**
关联的Tag
- **IsOverride**
默认为True ，如果这个值标记为False 则会触发父级Tag关联的GameplayCue
比如该GameplayCue 关联的Tag是 Damage.Physical.Slash
如果为False 则还会触发Tag Damage.Physical关联的GameplayCue
- **bAutoDestroyOnRemove**
是否在移除效果时，自动销毁或者回收Actor对象
- **AutoDestroyDelay**
bAutoDestroyOnRemove为True时,自动销毁或者回收Actor对象的延迟时间
- **WarnIfTimelineIsStillRunning**
在回收Actor对象时 如果还有Timeline在播放 是否打印警告日志
- **WarnIfLatentActionIsStillRunning**
在回收Actor对象时 如果还有延迟委托存在 是否打印警告日志
- **bAutoAttachToOwner**
是否自动Attach到Owner
- **bUniqueInstancePerInstigator**
如果GameplayCue是同一个(UClass相同 即同一个蓝图资源)	 
同样的触发Actor(Instigator)是否共用同一个GameplayCue实例
比如:A触发了两次一样的GameplayCue,触发Actor(Instigator)都是A 是否共用同一个GameplayCue实例
- **bUniqueInstancePerSourceObject**
如果GameplayCue是同一个(UClass相同 即同一个蓝图资源)	 
同样的来源Object(SourceObject)是否共用同一个GameplayCue实例
比如:A触发了两次一样的GameplayCue,来源Object(SourceObject)都是A 是否共用同一个GameplayCue实例

> 💡
>
> 在添加GC时会将GC对于的Tag加到ASC上计数+1，移除时计数-1。默认情况下，触发GC的移除事件，如果对于Tag计数未减为0，则会无视这次的移除事件。
>
> ```cpp
> void AGameplayCueNotify_Actor::HandleGameplayCue(...)
> {
> 	if (GameplayCueNotifyTagCheckOnRemove > 0 && 
> 	EventType == EGameplayCueEvent::Removed)
> 	{
> 		if (IGameplayTagAssetInterface* TagInterface = 
> 		Cast<IGameplayTagAssetInterface>(MyTarget))
> 		{
> 			if (TagInterface->HasMatchingGameplayTag(Parameters.MatchedTagName))
> 			{
> 				return;
> 			}			
> 		}
> 	}
> }
> ```
>
> 默认情况下，同一个GC在同一个目标身上只会存在一个实例(**推荐做法**)。bUniqueInstancePerInstigator和bUniqueInstancePerSourceObject都是false，Active可以被重复触发。如果不同触发来源需要创建不同的Actor实例，则需要考虑Remove只会在计数减为0触发的情况(比如在Actor自己处理何时结束GC)。
>
> ```cpp
> AGameplayCueNotify_Actor* UGameplayCueManager::FindExistingCueOnActor(...) const
> {
> 	for (AActor* Child : TargetActor.Children)
> 	{
> 		if (IsValid(Child) && Child->IsA(CueClass))
> 		{
> 			AGameplayCueNotify_Actor* ChildNotify = 
> 			CastChecked<AGameplayCueNotify_Actor>(Child);
> 			....
> 			const bool bInstigatorMatches =!ChildNotify->bUniqueInstancePerInstigator || ChildNotify->CueInstigator == Parameters.GetInstigator();
>
> 			const bool bSourceMatches =  !ChildNotify->bUniqueInstancePerSourceObject || ChildNotify->CueSourceObject == Parameters.GetSourceObject();
>
> 			if (bInstigatorMatches && bSourceMatches)
> 			{
> 				return ChildNotify;
> 			}
> 		}
> 	}
>
> 	return nullptr;
> }
> ```

- **bAllowMultipleOnActiveEvents**
同一个GameplayCue实例 是否运行多次触发OnActive事件
- **bAllowMultipleWhileActiveEvents**
同一个GameplayCue实例 是否允许多次触发WhileActive事件
- **NumPreallocatedInstance**
对象池的池子预分配大小

```cpp
class GAMEPLAYABILITIES_API AGameplayCueNotify_Actor : public AActor
{
	
	//关联的Tag
	UPROPERTY(EditDefaultsOnly, Category = GameplayCue, meta=(Categories="GameplayCue"))
	FGameplayTag	GameplayCueTag;

	//默认为True 
	//如果这个值标记为False 则会触发父级Tag关联的GameplayCue
	//比如该GameplayCue 关联的Tag是 Damage.Physical.Slash
	//如果为False 则还会触发Tag Damage.Physical关联的GameplayCue
	UPROPERTY(EditDefaultsOnly, Category = GameplayCue)
	bool IsOverride;
	
	//是否在移除效果时，自动销毁或者回收Actor对象
	UPROPERTY(EditDefaultsOnly, Category = Cleanup)
	bool bAutoDestroyOnRemove;

	//bAutoDestroyOnRemove为True时,自动销毁或者回收Actor对象的延迟时间
	UPROPERTY(EditAnywhere, Category = Cleanup)
	float AutoDestroyDelay;

	//在回收Actor对象时 如果还有Timeline在播放 是否打印警告日志
	UPROPERTY(EditAnywhere, Category = Cleanup)
	bool WarnIfTimelineIsStillRunning;

	//在回收Actor对象时 如果还有延迟委托存在 是否打印警告日志
	UPROPERTY(EditAnywhere, Category = Cleanup)
	bool WarnIfLatentActionIsStillRunning;
	

	//是否自动Attach到Owner
  UPROPERTY(EditDefaultsOnly, Category = GameplayCue)
	bool bAutoAttachToOwner;

	//如果GameplayCue是同一个(UClass相同 即同一个蓝图资源)	 
	//同样的触发Actor(Instigator)是否共用同一个GameplayCue实例
	//A触发了两次一样的GameplayCue,触发Actor(Instigator)都是A 是否共用同一个GameplayCue实例
	UPROPERTY(EditDefaultsOnly, Category = GameplayCue)
	bool bUniqueInstancePerInstigator;

	//如果GameplayCue是同一个(UClass相同 即同一个蓝图资源)	 
	//同样的来源Object(SourceObject)是否共用同一个GameplayCue实例
	//A触发了两次一样的GameplayCue,来源Object(SourceObject)都是A 是否共用同一个GameplayCue实例
	UPROPERTY(EditDefaultsOnly, Category = GameplayCue)
	bool bUniqueInstancePerSourceObject;

	//同一个GameplayCue实例 是否运行多次触发OnActive事件 
	UPROPERTY(EditDefaultsOnly, Category = GameplayCue)
	bool bAllowMultipleOnActiveEvents;

	//同一个GameplayCue实例 是否允许多次触发WhileActive事件
	UPROPERTY(EditDefaultsOnly, Category = GameplayCue)
	bool bAllowMultipleWhileActiveEvents;

	//对象池的池子预分配大小
	UPROPERTY(EditDefaultsOnly, Category = GameplayCue)
	int32 NumPreallocatedInstances;
}
```

### 对象池

---

**获取或者创建对象**

- 如果播放该表现效果的目标上有个同样的效果且配置了共用实例(bUniqueInstancePerInstigator或者bUniqueInstancePerSourceObject)，直接返回已有的效果对象
- 启用了对象池则尝试从池子里取出来
- 池子里没有或者没启用池子则新建一个

```cpp
AGameplayCueNotify_Actor* UGameplayCueManager::GetInstancedCueActor(...)
{

	//**如果播放该表现效果的目标上有个同样的效果且配置了共用实例**
	//(bUniqueInstancePerInstigator或者bUniqueInstancePerSourceObject)，
	//直接返回已有的效果对象
	AGameplayCueNotify_Actor* ExistingCueOnActor = FindExistingCueOnActor(*TargetActor, 
	CueClass, Parameters);
	
	if (ExistingCueOnActor)
	{
		ExistingCueOnActor->CueInstigator = Parameters.GetInstigator();
		ExistingCueOnActor->CueSourceObject = Parameters.GetSourceObject();
		return ExistingCueOnActor;
	}
	
	**//启用了对象池 则尝试从池子里取出来**
	if (bUseActorRecycling)
	{
		if (AGameplayCueNotify_Actor* RecycledCue = FindRecycledCue(CueClass, *World))
		{
			RecycledCue->bInRecycleQueue = false;
			RecycledCue->SetOwner(TargetActor);
			RecycledCue->SetActorLocationAndRotation(TargetActor->GetActorLocation(), 
			TargetActor->GetActorRotation());
			
			RecycledCue->ReuseAfterRecycle();
			RecycledCue->CueInstigator = Parameters.GetInstigator();
			RecycledCue->CueSourceObject = Parameters.GetSourceObject();

			return RecycledCue;
		}
	}
	
	**//池子里没有或者没启用池子则新建一个**
	FActorSpawnParameters SpawnParams;
	SpawnParams.Owner = TargetActor;
	SpawnParams.OverrideLevel = World->PersistentLevel;
	
	AGameplayCueNotify_Actor* SpawnedCue = World->SpawnActor<AGameplayCueNotify_Actor>
	(CueClass, TargetActor->GetActorLocation(), TargetActor->GetActorRotation(),
	 SpawnParams);
	 
	SpawnedCue->CueInstigator = Parameters.GetInstigator();
	SpawnedCue->CueSourceObject = Parameters.GetSourceObject();

	
	return SpawnedCue;
}
```

**回收对象**

- 启用了对象池则回收回对象池(不销毁)
- 没启用对象池或者回收失败则直接销毁

```cpp
void UGameplayCueManager::NotifyGameplayCueActorFinished(...)
{
...
	bool UseActorRecycling = (GameplayCueActorRecycle > 0);

	**//启用了对象池则回收回对象池(不销毁)**
	if (UseActorRecycling)
	{
	...
		if (CDO && Actor->Recycle())
		{
			...
			if (PreAllocatedList.Actors.Contains(Actor) ==false)
			{
				PreAllocatedList.Actors.Push(Actor);
			}
			...
			return;
		}
	...
	}
	
	//**没启用对象池或者回收失败则直接销毁**
	Actor->Destroy();
...
}
```

## **GameplayCueNotify_Burst**

---

即**GCN Burst**，继承自**UGameplayCueNotify_Static。封装了一些通用的一次性的即时效果的GameplayCue**。

提供了一套通用的配置，可以配置**表现效果生效检测条件、 表现效果的位置信息、粒子特效，音效，震屏效果(CameraShake)、摄像机效果(CameraLenEffect)、Decal效果**等。对于一些简单的表现，直接配置即可。

蓝图子类可以重载OnBurst扩展额外的表现效果。

```cpp
bool UGameplayCueNotify_Burst::OnExecute_Implementation(...) const
{
	UWorld* World = (Target ? Target->GetWorld() : GetWorld());

	FGameplayCueNotify_SpawnContext SpawnContext(World, Target, Parameters);
	SpawnContext.SetDefaultSpawnCondition(&DefaultSpawnCondition);
	SpawnContext.SetDefaultPlacementInfo(&DefaultPlacementInfo);

	//检测生效条件
	if (DefaultSpawnCondition.ShouldSpawn(SpawnContext))
	{
		FGameplayCueNotify_SpawnResult SpawnResult;
		
		//触发表现效果
		BurstEffects.ExecuteEffects(SpawnContext, SpawnResult);

		//蓝图触发额外的表现效果
		OnBurst(Target, Parameters, SpawnResult);
	}

	return false;
}
```

![Untitled](http://pic.xyyxr.cn/20260504111155845.png)

### 配置字段

---

- **DefaultSpawnCondition**
默认生效检测条件
配置列表可以单独配置覆盖默认配置
- **DefaultPlacementInfo**
默认位置信息(播放表现是可能需要用到位置信息)
配置列表可以单独配置覆盖默认配置
    
    ![Untitled](http://pic.xyyxr.cn/20260504111155846.png)
    
- **BurstEffects**
触发的表现效果配置列表(粒子特效，音效，震屏效果(CameraShake)、摄像机效果(CameraLenEffect)、Decal效果等)，触发效果时，根据配置列表播放对象的表现效果
    
    ![Untitled](http://pic.xyyxr.cn/20260504111155847.png)
    
    **配置列表可以配置单独的检测条件和位置信息覆盖默认配置**
    
    ![Untitled](http://pic.xyyxr.cn/20260504111155848.png)
    
    ![Untitled](http://pic.xyyxr.cn/20260504111155849.png)
    

```cpp
UCLASS(Blueprintable, Meta = (ShowWorldContextPin, DisplayName = "**GCN Burst**", )
class GAMEPLAYABILITIES_API UGameplayCueNotify_Burst : public UGameplayCueNotify_Static
{
protected:

	//GameplayCue 执行接口
	virtual bool OnExecute_Implementation(AActor* Target, 
	const FGameplayCueParameters& Parameters) const override;

	//蓝图子类可以重载OnBurst扩展额外的表现效果
	UFUNCTION(BlueprintImplementableEvent)
	void OnBurst(AActor* Target, const FGameplayCueParameters& Parameters,
	 const FGameplayCueNotify_SpawnResult& SpawnResults) const;

protected:

	//默认的生效检测条件(配置列表可以单独配置覆盖默认配置)
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "GCN Defaults")
	FGameplayCueNotify_SpawnCondition DefaultSpawnCondition;

	// 默认的位置信息(配置列表可以单独配置覆盖默认配置)
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "GCN Defaults")
	FGameplayCueNotify_PlacementInfo DefaultPlacementInfo;

	// 触发的表现效果配置列表
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "GCN Effects")
	FGameplayCueNotify_BurstEffects BurstEffects;
};
```

## **GameplayCueNotify_BurstLatent**

---

即**GCN Burst Latent**，继承自A**GameplayCueNotify_Actor。封装了一些通用的一次性即时表现效果的GameplayCue，**会自动回收结束表现效果。

**与上面的GameplayCueNotify_Burst类似**，区别在于该表现效果是一个独立的Acotr对象，可以在其生命周期内实现扩展逻辑，该效果会启动一个计时器自动结束其生命周期并回收(默认5s)，并且在会维护表现效果执行结果列表**BurstSpawnResults，**在回收时会重置**BurstSpawnResults**清空表现效果。

```cpp
class GAMEPLAYABILITIES_API AGameplayCueNotify_BurstLatent :
 public AGameplayCueNotify_Actor
{
	GENERATED_BODY()

public:

	AGameplayCueNotify_BurstLatent();

protected:

	virtual bool Recycle() override;

	virtual bool OnExecute_Implementation(...) override;

	UFUNCTION(BlueprintImplementableEvent)
	void OnBurst(...);

protected:

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "GCN Defaults")
	FGameplayCueNotify_SpawnCondition DefaultSpawnCondition;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "GCN Defaults")
	FGameplayCueNotify_PlacementInfo DefaultPlacementInfo;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "GCN Effects")
	FGameplayCueNotify_BurstEffects BurstEffects;

	UPROPERTY(BlueprintReadOnly, Category = "GCN Effects")
	FGameplayCueNotify_SpawnResult BurstSpawnResults;
};
```

```cpp
struct FGameplayCueNotify_SpawnResult
{
...
	void Reset()
	{
		FxSystemComponents.Reset();
		AudioComponents.Reset();
		CameraShakes.Reset();
		CameraLensEffects.Reset();
		ForceFeedbackComponent = nullptr;
		ForceFeedbackTargetPC = nullptr;
		DecalComponent = nullptr;
	}
	
	UPROPERTY(BlueprintReadOnly, Transient, Category = GameplayCueNotify)
	TArray<TObjectPtr<UFXSystemComponent>> FxSystemComponents;

	UPROPERTY(BlueprintReadOnly, Transient, Category = GameplayCueNotify)
	TArray<TObjectPtr<UAudioComponent>> AudioComponents;

	UPROPERTY(BlueprintReadOnly, Transient, Category = GameplayCueNotify)
	TArray<TObjectPtr<UCameraShakeBase>> CameraShakes;

	UPROPERTY(BlueprintReadOnly, Transient, Category = GameplayCueNotify)
	TArray<TScriptInterface<ICameraLensEffectInterface>> CameraLensEffects;

	UPROPERTY(BlueprintReadOnly, Transient, Category = GameplayCueNotify)
	TObjectPtr<UForceFeedbackComponent> ForceFeedbackComponent;

	UPROPERTY(Transient)
	TObjectPtr<APlayerController> ForceFeedbackTargetPC;

	UPROPERTY(BlueprintReadOnly, Transient, Category = GameplayCueNotify)
	TObjectPtr<UDecalComponent> DecalComponent;
}
```

```cpp
bool AGameplayCueNotify_BurstLatent::OnExecute_Implementation(...)
{
	UWorld* World = GetWorld();

	FGameplayCueNotify_SpawnContext SpawnContext(World, Target, Parameters);
	SpawnContext.SetDefaultSpawnCondition(&DefaultSpawnCondition);
	SpawnContext.SetDefaultPlacementInfo(&DefaultPlacementInfo);

	if (DefaultSpawnCondition.ShouldSpawn(SpawnContext))
	{
		BurstEffects.ExecuteEffects(SpawnContext, BurstSpawnResults);

		OnBurst(Target, Parameters, BurstSpawnResults);
	}

	
	//启动自动回收计时器 AutoDestroyDelay和DefaultBurstLatentLifetime(默认5s)取大的
	if (World)
	{
		const float Lifetime = FMath::Max<float>(AutoDestroyDelay, 
		DefaultBurstLatentLifetime);
		
		World->GetTimerManager().SetTimer(FinishTimerHandle, this, 
		&AGameplayCueNotify_Actor::GameplayCueFinishedCallback, Lifetime);
	}

	return false;
}
```

## GameplayCueNotify_Looping

---

即**GCN Looping**，继承自A**GameplayCueNotify_Actor。封装了一些通用的表现效果的GameplayCue，支持配置持续性的循环表现效果**。

上面的**GameplayCueNotify_Burst**和**GameplayCueNotify_BurstLatent一般用来播放一次性的即时效果。而GameplayCueNotify_Looping可以配置一次性的即时表现效果也可以配置持续性的循环播放表现效果**。

 

```cpp
class GAMEPLAYABILITIES_API AGameplayCueNotify_Looping : public AGameplayCueNotify_Actor
{
	GENERATED_BODY()

public:

	AGameplayCueNotify_Looping();

protected:

	virtual bool OnActive_Implementation(...) override;
	virtual bool WhileActive_Implementation(...) override;
	virtual bool OnExecute_Implementation(...) override;
	virtual bool OnRemove_Implementation(...) override;

	UFUNCTION(BlueprintImplementableEvent)
	void OnApplication(...);

	UFUNCTION(BlueprintImplementableEvent)
	void OnLoopingStart(...);

	UFUNCTION(BlueprintImplementableEvent)
	void OnRecurring(...);

	UFUNCTION(BlueprintImplementableEvent)
	void OnRemoval(...);

	void RemoveLoopingEffects();

protected:

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
	FGameplayCueNotify_SpawnCondition DefaultSpawnCondition;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
	FGameplayCueNotify_PlacementInfo DefaultPlacementInfo;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
	FGameplayCueNotify_BurstEffects ApplicationEffects;

	UPROPERTY(BlueprintReadOnly, Category)
	FGameplayCueNotify_SpawnResult ApplicationSpawnResults;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
	FGameplayCueNotify_LoopingEffects LoopingEffects;

	UPROPERTY(BlueprintReadOnly)
	FGameplayCueNotify_SpawnResult LoopingSpawnResults;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
	FGameplayCueNotify_BurstEffects RecurringEffects;

	UPROPERTY(BlueprintReadOnly)
	FGameplayCueNotify_SpawnResult RecurringSpawnResults;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
	FGameplayCueNotify_BurstEffects RemovalEffects;

	UPROPERTY(BlueprintReadOnly)
	FGameplayCueNotify_SpawnResult RemovalSpawnResults;

	bool bLoopingEffectsRemoved;
};
```

GameplayCueNotify_Looping支持在**GameplayCue所有状态触发节点(**OnActive，WhileActive，OnRemove，OnExecute)配置不同的表现效果

- **OnActive**
具有生命周期的持续效果添加时播放**ApplicationEffects**配置列表配置的一次性即时效果(**FGameplayCueNotify_BurstEffects**)
蓝图可以通过重载**OnApplication**接口进行扩展
    
    ![Untitled](http://pic.xyyxr.cn/20260504111157835.png)
    

- **WhileActive**
具有生命周期的持续效果激活时播放**LoopingEffects**配置列表配置的持续性循环表现效果(**FGameplayCueNotify_LoopingEffects**)
蓝图可以通过重载**OnLoopingStart**接口进行扩展，会在移除时停止循环效果
    
    ![Untitled](http://pic.xyyxr.cn/20260504111157836.png)
    
    ![Untitled](http://pic.xyyxr.cn/20260504111157837.png)
    

- **OnRemove**
具有生命周期的持续效果移除时，播放**RemovalEffects**配置列表配置的一次性即时效果(**FGameplayCueNotify_BurstEffects**)
蓝图可以通过重载**OnRemoval**接口进行扩展
    
    ![Untitled](http://pic.xyyxr.cn/20260504111157838.png)
    
- **OnExecute**
一次性的即时性效果触发时，播放**RecurringEffects**配置列表配置的一次性即时效果(**FGameplayCueNotify_BurstEffects**)
蓝图可以通过重载**OnRecurring**接口进行扩展
    
    ![Untitled](http://pic.xyyxr.cn/20260504111157839.png)