> 💡 **本系列文章基于UE5.3**

# 概述

---

UE提供了一套Task(任务)机制，可以通过Task机制管理一组游戏中定制的任务(行为)。比如AI行为树中的行为执行节点(AITask)，GA中使用的行为执行节点(AbilityTask)(GA可以理解为一个或多个Task的集合)。

- GameplayTask是Task的基类
- GameplayTasksComponent是Task管理组件的基类。
- AbilityTask继承自GameplayTask，是GAS模块专属Task。
- AbilitySystemComponent继承自GameplayTasksComponent，其功能之一就是管理AbilityTask。

**Task的特性**

- 可以添加、激活、取消
- 生命周期内会自动处理任务的开始、执行和结束
- 支持异步任务执行，允许任务在后台运行
- 通过状态管理任务的不同阶段（如等待激活、激活、暂停、完成）
- 支持回调机制，可以在任务完成或状态变化时通知其他系统或组件

# GameplayTask

---

GameplayTask是Task的基类，而且是纯虚类，无法直接使用其的实例。提供了Task基础的执行流程和状态管理。

## 执行流程

---

- **NewTask**:创建Task示例并调用Task初始接口

```cpp
    template <class T>
    T* UGameplayTask::NewTask(IGameplayTaskOwnerInterface& TaskOwner,
     FName InstanceName)
    {
    	T* MyObj = NewObject<T>();
    	MyObj->InstanceName = InstanceName;
    	MyObj->InitTask(TaskOwner, TaskOwner.GetGameplayTaskDefaultPriority());
    	return MyObj;
    }
```
    
>AbilityTask和AITask都有自己专属创建Task示例的接口，不要使用通用的NewTask来创建
>AbilityTask通过NewAbilityTask创建
>AITask通过NewAITask创建


- **InitTask**:初始化Task
Task状态置为AwaitingActivation(等待激活)
通知Task拥有者 Task初始化完毕
```cpp
    void UGameplayTask::InitTask(...)
    {
    	...
    	//Task状态置为AwaitingActivation(等待激活)
    	TaskState = EGameplayTaskState::AwaitingActivation;
    	
    	//通知Task拥有者 Task初始化完毕
    	InTaskOwner.OnGameplayTaskInitialized(*this);
    ...
    }
```

- **ReadyForActivation**:准备激活
有些Task需要考虑优先级或者资源占用要放入队列就行进一步判断
不要考虑则直接执行激活
    
```cpp
    void UGameplayTask::ReadyForActivation()
    {
    	if (UGameplayTasksComponent* TasksPtr = TasksComponent.Get())
    	{
    		if (RequiresPriorityOrResourceManagement() == false)
    		{
    			//不要考虑则直接执行激活
    			PerformActivation();
    		}
    		else
    		{
    			//需要考虑优先级或者资源占用要放入队列就行进一步判断
    			TasksPtr->AddTaskReadyForActivation(*this);
    		}
    	}
    	else
    	{
    		EndTask();
    	}
    }
```
    
- **PerformActivation**:执行激活 
状态置为激活 
调用执行激活的具体行为逻辑接口Activate
加入管理组件Task激活列表进行管理
    
```cpp
    void UGameplayTask::PerformActivation()
    {
    ....
    	TaskState = EGameplayTaskState::Active;
    
    	 //执行激活的具体行为逻辑
    	Activate();
    
    	//通知Task的管理组件 Task激活了 放入Task激活列表(需要执行Tick还需要放入Tick列表)
    	//如果Task是一次性的 执行完了就结束了 则没必要再放入列表了
    	if (IsFinished() == false)
    	{
    		TasksComponent->OnGameplayTaskActivated(*this);
    	}
    }
```
    
- **Activate**:执行激活的具体行为逻辑接口
各种Task根据自己需求重载，实现具体的行为逻辑
- **Pause**:Task的暂停(暂时失效)
状态置为Paused
通知Task的管理组件Task暂时失效(停止Tick之类)
    
```cpp
    void UGameplayTask::Pause()
    {
    	TaskState = EGameplayTaskState::Paused;
    	
    	//通知Task的管理组件 Task暂时失效
    	TasksComponent->OnGameplayTaskDeactivated(*this);
    }
```
    
- **Resume**:Task的恢复(重新生效)
状态置为Resume 
通知Task的管理组件 Task被激活了
(不会再次触发Activate接口)
    
```cpp
    void UGameplayTask::Resume()
    {
    	TaskState = EGameplayTaskState::Active;
    	if (TasksComponent.IsValid())
    	{
    		//通知Task的管理组件 Task被恢复
    		TasksComponent->OnGameplayTaskActivated(*this);
    	}
    }
    
```
    
- **EndTask**:Task结束 触发销毁Task
    
```cpp
    void UGameplayTask::EndTask()
    {
    	if (TaskState != EGameplayTaskState::Finished)
    	{
    		if (IsValid(this))
    		{
    			OnDestroy(false);
    		}
    	}
    }
```
    
- **OnDestory**：执行Task的销毁
    
```cpp
    void UGameplayTask::OnDestroy(bool bInOwnerFinished)
    {
    	TaskState = EGameplayTaskState::Finished;
    	if (UGameplayTasksComponent* TasksPtr = TasksComponent.Get())
    	{
    		TasksPtr->OnGameplayTaskDeactivated(*this);
    	}
    	MarkAsGarbage();
    }
```
    

## 子任务

---

Task可以绑定一个子任务ChildTask，**可以在主任务中操作子任务***(比如跟随主任务一起启动、暂停、恢复之类的)，***主任务结束会同时结束绑定的子任务**。

在创建一个Task时可以指定其Owner为另一个Task。
在初始化Task时会通知其Owner该Task已经初始化完成，如果Owner是一个Task则会将该新创建的Task设置为子任务ChildTask。

```cpp

void UGameplayTask::InitTask(...)
{
	InTaskOwner.OnGameplayTaskInitialized(*this);
}

void UGameplayTask::OnGameplayTaskInitialized(UGameplayTask& Task)
{
...
	ChildTask = &Task;
...
}
```

# GameplayTasksComponent

---

GameplayTasksComponent是Task管理组件的基类，提供了Task的管理和常用操作。比如Task的启动入口RunGameplayTask、Task管理列表、Task网络复制、Task的Tick驱动等。

GameplayTasksComponent维护四个Task列表:

- 优先级列表**TaskPriorityQueue**
- 已激活列表**KnownTasks**
- Tick列表**TickingTasks**
- 模拟端列表**SimulatedTasks**

## 优先级列表**TaskPriorityQueue**

---

当一个Task准备激活(**ReadyForActivation)**时，有些Task需要考虑执行优先级或者资源占用的判定，这种Task会先放入GameplayTasksComponent一个优先级队列**TaskPriorityQueue**(不要考虑上述执行条件的则直接通过PerformActivation执行激活)

```cpp
void UGameplayTask::ReadyForActivation()
{
	if (UGameplayTasksComponent* TasksPtr = TasksComponent.Get())
	{
		if (RequiresPriorityOrResourceManagement() == false)
		{
			//不要考虑则直接执行激活
			PerformActivation();
		}
		else
		{
			//需要考虑优先级或者资源占用要放入队列就行进一步判断
			TasksPtr->AddTaskReadyForActivation(*this);
		}
	}
}
```

优先级队列**TaskPriorityQueue**中Task在加入队列时会根据其配置的优先级找到对应的位置插入(**优先级越大越靠前，优先被执行**)。

优先级队列**TaskPriorityQueue**的Task可以配置激活必要的资源(RequiredResources)和激活后会持有的资源(ClaimedResources)。

- 当队列的Task被激活时，如果配置了持有资源，则会**标记当前这些资源被持有了**
- 当队列中一个Task**配置了必要的资源(RequiredResources)且激活时其中有资源被其他Task持有**,则无法被激活，激活了也会被暂停(低优先级Task持有资源不会阻碍高优先级的Task)

在优先级队列**TaskPriorityQueue**发生变动(添加或移除时)，会轮询下优先级队列**TaskPriorityQueue,**看下哪些Task需要被激活，哪些需要被暂停。
*(比如新增了一个Task除了尝试激活新增的Task，也可能会导致之前激活的有个Task被暂停，移除了一个Task可能会导致之前一个被暂停或者激活失败的Task恢复激活或者重新激活)*

```cpp
void UGameplayTasksComponent::UpdateTaskActivations()
{
	FGameplayResourceSet ResourcesClaimed;

	if (TaskPriorityQueue.Num() > 0)
	{
		TArray<UGameplayTask*> ActivationList;
		ActivationList.Reserve(TaskPriorityQueue.Num());

		FGameplayResourceSet ResourcesBlocked;
		for (int32 TaskIndex = 0; TaskIndex < TaskPriorityQueue.Num(); ++TaskIndex)
		{
			if (TaskPriorityQueue[TaskIndex])
			{
				//激活必要资源
				const FGameplayResourceSet RequiredResources = 
				TaskPriorityQueue[TaskIndex]->GetRequiredResources();
				
				//激活后会持有的资源
				const FGameplayResourceSet ClaimedResources = 
				TaskPriorityQueue[TaskIndex]->GetClaimedResources();
				
				//判定必要资源是否已经被持有
				if (RequiredResources.GetOverlap(ResourcesBlocked).IsEmpty())
				{
					//**标记当前这些资源被持有了**
					ActivationList.Add(TaskPriorityQueue[TaskIndex]);
					ResourcesClaimed.AddSet(ClaimedResources);
				}
				else
				{
					//**配置了必要的资源(RequiredResources)且激活时其中有资源被其他Task持有了**
					TaskPriorityQueue[TaskIndex]->PauseInTaskQueue();
				}

				//记录当前有哪些资源已经被持有了
				ResourcesBlocked.AddSet(ClaimedResources);
			}
		}
	}
	
}
```

> 💡 Task用到的资源配置(FGameplayResourceSet) 本质上就是一个16位Bit的标记，每个资源都会分配一个对应的资源ID(0~15),对应的就是uint16中的16个Bit位。所以一类Task最多支持配置16种资源(*比如AITask和AbilityTask属于不同类Task其资产类型可以分别定制*)。必要资源(RequiredResources)**，**持有的资源(ClaimedResources)的配置就是标记对应的Bit位。

```cpp
struct FGameplayResourceSet
{
	GENERATED_USTRUCT_BODY()

	typedef uint16 FFlagContainer;
	typedef uint8 FResourceID;

	enum
	{
		MaxResources = sizeof(FFlagContainer)* 8
	};

private:
	FFlagContainer Flags;
	
	bool IsEmpty() const
	{
		return Flags == 0;
	}
	
	FGameplayResourceSet& AddID(uint8 ResourceID)
	{
		ensure(ResourceID < MaxResources);
		Flags |= (1 << ResourceID);
		return *this;
	}
	FGameplayResourceSet& RemoveID(uint8 ResourceID)
	{
		ensure(ResourceID < MaxResources);
		Flags &= ~(1 << ResourceID);
		return *this;
	}
	
	bool HasID(uint8 ResourceID) const
	{
		ensure(ResourceID < MaxResources);
		return (Flags & (1 << ResourceID)) != 0;
	}
}
```

> 💡 UGameplayTaskResource是配置Task资源类型的基类，一个纯虚类，可以通过创建其子类来定制Task不同类型的资源。
>
> 在设置Task必要资源(RequiredResources)**，**持有的资源(ClaimedResources)时直接通过自定的UGameplayTaskResource子类进行配置，使用时直接使用子类的CDO，通过子类的CDO获取到资源对应的资源ID，然后将资源ID设置到对于的资源集合中(RequiredResources或者ClaimedResources)

```cpp
UCLASS(Abstract, config = "Game", hidedropdown, MinimalAPI)
class UGameplayTaskResource : public UObject
{
	GENERATED_BODY()
	protected:
		UPROPERTY()
		int32 ManualResourceID;
	
	private:
		UPROPERTY()
		int8 AutoResourceID;
	
	public:
		UPROPERTY()
		uint32 bManuallySetID : 1;
}

//**通过子类的CDO获取到资源对应的资源ID，然后将资源ID设置到对于的资源集合中**
//(RequiredResources或者ClaimedResources)
void UGameplayTask::AddRequiredResource(TSubclassOf<UGameplayTaskResource> 
RequiredResource)
{
	check(RequiredResource);
	const uint8 ResourceID = UGameplayTaskResource::GetResourceID(RequiredResource);
	RequiredResources.AddID(ResourceID);	
}

void UGameplayTask::AddClaimedResource(TSubclassOf<UGameplayTaskResource> 
ClaimedResource)
{
	check(ClaimedResource);
	const uint8 ResourceID = UGameplayTaskResource::GetResourceID(ClaimedResource);
	ClaimedResources.AddID(ResourceID);
}

static uint8 GetResourceID(const TSubclassOf<UGameplayTaskResource>& RequiredResource)
{
	return RequiredResource->GetDefaultObject<UGameplayTaskResource>()->GetResourceID();
}
```

> 💡 GameplayTaskResource会在创建子类CDO实例时(*引擎初始化就会完成这部操作*)自动分配一个资源类型ID(AutoResourceID)，所以子类直接继承自UGameplayTaskResource就行，不需要在子类中再手动分配资源类型ID
> *比如UAIResource_Movement、UAIResource_Movement*
>
> 也可以通过设置bManuallySetID和ManualResourceID 手动为创建的子类分配资源类型ID 
>
> *比如 AITask和AbilityTask是两套完全独立的Task体系，有各自的Task管理组件，所以其Task资源可以是各自独立的。AITask直接使用了自动分配ID的方式创建Task资源，AbilityTask需要重新创建一套Task资源的话就可以选择使用手动分配的方式(否则就跟AITask共有了一套资源ID分配方案，共享16个资产类型额度)。*

```cpp
//子类直接继承自UGameplayTaskResource，自动分配ID不需要在子类中再手动分配资源类型ID
class UAIResource_Movement : public UGameplayTaskResource
{
	GENERATED_BODY()
};

//没有设置 手动分配的会自动分配资源类型ID
void UGameplayTaskResource::PostInitProperties()
{
	Super::PostInitProperties();
	if (bManuallySetID == false || ManualResourceID == INDEX_NONE)
	{
		UpdateAutoResourceID();
	}
}
	
void UGameplayTaskResource::UpdateAutoResourceID()
{
	static uint16 NextAutoResID = 0;

	if (AutoResourceID == INDEX_NONE)
	{
		AutoResourceID = static_cast<int8>(NextAutoResID++);
		
		if (AutoResourceID >= FGameplayResourceSet::MaxResources)
		{
			//资产类型最多16位
			UE_LOG(LogGameplayTasks, Error, TEXT("...."));
		}
	}
}
```

因为每次优先级队列**TaskPriorityQueue**发生变动时都可能触发新的Task激活，而在Task激活操作中可能激活一个新的Task插入优先队列中，这样就会出现递归调用，在添加或者移除过程中又去修改优先级队列的元素位置是存在风险的。

为了规避这个问题，这里在添加、移除优先级队列**TaskPriorityQueue**的元素时，并不是直接操作优先级队列就行修改，而是先将操作缓存起来放到一个操作列表**TaskEvents**中

- **如果当前操作列表为空且未标记正在处理操作，说明没有正在执行的操作，可以直接触发执行**
- **如果当前操作列表不为空，则先缓存起来，等当前的操作执行完了再执行**

配合操作锁FEventLock，在会在Task激活(添加)OnGameplayTaskActivated和取消激活(移除)
OnGameplayTaskDeactivated的时候加锁，在执行完成解锁
解锁时检测当前是否可以执行操作了(*操作锁计数为0了且正在处理操作的标记bInEventProcessingInProgress为False),*是则触发执行

*bInEventProcessingInProgress在执行操作的函数ProcessTaskEvents开始时标记为True,结束时标记为False*

```cpp
//添加、移除优先级队列**TaskPriorityQueue**的元素时，
//并不是直接操作优先级队列就行修改，而是先将操作缓存起来放到一个操作列表**TaskEvents**中
void UGameplayTasksComponent::AddTaskReadyForActivation(UGameplayTask& NewTask)
{
	TaskEvents.Add(FGameplayTaskEventData(EGameplayTaskEvent::Add, NewTask));

	//如果没有正在执行的操作，可以直接触发执行
	if (TaskEvents.Num() == 1 && CanProcessEvents())
	{
		ProcessTaskEvents();
	}
}

void UGameplayTasksComponent::RemoveResourceConsumingTask(UGameplayTask& Task)
{
	TaskEvents.Add(FGameplayTaskEventData(EGameplayTaskEvent::Remove, Task));
	
	//如果没有正在执行的操作，可以直接触发执行
	if (TaskEvents.Num() == 1 && CanProcessEvents())
	{
		ProcessTaskEvents();
	}
}

//解锁时触发缓存的操作执行(bInEventProcessingInProgress为False)
UGameplayTasksComponent::FEventLock::~FEventLock()
{
	if (Owner)
	{
		Owner->EventLockCounter--;

		if (Owner->TaskEvents.Num() && Owner->CanProcessEvents())
		{
			Owner->ProcessTaskEvents();
		}
	}
}

//判定是否能执行操作 操作锁计数为0了
//且正在处理操作的标记bInEventProcessingInProgress为False
FORCEINLINE bool CanProcessEvents() const { 
return !bInEventProcessingInProgress && (EventLockCounter == 0); }

```

> 💡 **ProcessTaskEvents**是负责执行操作列表中的操作的，每次都会将缓存的操作统一执行，执行完优先级队列**TaskPriorityQueue**添加移除之后，先将缓存操作清空，再通过**UpdateTaskActivations**去更新优先级队列，看哪些Task应该被激活，哪些应该被取消激活。
>
> 在**UpdateTaskActivations**执行过程中可能会触发新的操作添加到操作列表中TaskEvents，因为在ProcessTaskEvents开始执行时标记了bInEventProcessingInProgress为True表面当前正在处理操作，在ProcessTaskEvents执行期间不会因为新增操作而触发递归调用，而是在**UpdateTaskActivations**执行完成之后会检测在**UpdateTaskActivations**执行期间是否有产生新的操作,有则将新产生的操作执行一遍。(外层的While循环)

```cpp
void UGameplayTasksComponent::ProcessTaskEvents()
{
...
	static const int32 MaxIterations = 16;
	
	//标记正在处理 也是正在对操作进行加锁
	bInEventProcessingInProgress = true;
	

	int32 IterCounter = 0;
	
	//while会在**UpdateTaskActivations**执行完成之后
	//检测在**UpdateTaskActivations**执行期间是否有产生新的操作
	//有则将新产生的操作执行一遍
	while (TaskEvents.Num() > 0)
	{
		IterCounter++;
		if (IterCounter > MaxIterations)
		{
			TaskEvents.Reset();
			break;
		}
		
		//执行添加移除操作
		for (int32 EventIndex = 0; EventIndex < TaskEvents.Num(); ++EventIndex)
		{
					switch (TaskEvents[EventIndex].Event)
					{
					case EGameplayTaskEvent::Add:
						if (TaskEvents[EventIndex].RelatedTask.TaskState 
						!= EGameplayTaskState::Finished)
						{
							AddTaskToPriorityQueue(TaskEvents[EventIndex].RelatedTask);
						}
						break;
					case EGameplayTaskEvent::Remove:
						RemoveTaskFromPriorityQueue(TaskEvents[EventIndex].RelatedTask);
						break;
					}
			}
			
			//清空操作列表
			TaskEvents.Reset();
			
			//去更新优先级队列，看哪些Task应该被激活，哪些应该被取消激活。
			UpdateTaskActivations();
	}
	
	//取消正在处理标记
	bInEventProcessingInProgress = false;

...
}
```

## 激活列表KnownTasks&Tick列表TickingTasks

---

**KnownTasks**是存放当前所有已激活Task的列表(激活后立即结束的Task不会放入)

**TickingTasks**是存放KnownTasks中所有需要执行Tick逻辑的Task

**KnownTasks、TickingTasks**在Task激活和取消激活时添加、移除

> 💡 只有在Task执行结束调用OnGameplayTaskDeactivated(取消激活)才会从KnownTasks移除
> 暂停触发的OnGameplayTaskDeactivated不会从KnownTasks移除

```cpp
void UGameplayTasksComponent::OnGameplayTaskActivated(UGameplayTask& Task)
{
	KnownTasks.Add(&Task);
	if (Task.IsTickingTask())
	{
		check(TickingTasks.Contains(&Task) == false);
		TickingTasks.Add(&Task);
	}
}

void UGameplayTasksComponent::OnGameplayTaskDeactivated(UGameplayTask& Task)
{
	if (Task.IsTickingTask())
	{
		TickingTasks.RemoveSingleSwap(&Task);
	}
	
	if (bIsFinished)
	{
		KnownTasks.RemoveSwap(&Task);
	}
}
```

**TickingTasks**中的Task都是有执行Tick逻辑需求的，在UGameplayTasksComponent::TickComponent中统一驱动(**TickTask**)

```cpp
void UGameplayTasksComponent::TickComponent(...)
{
	SCOPE_CYCLE_COUNTER(STAT_TickGameplayTasks);

	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	
	int32 NumTickingTasks = TickingTasks.Num();
	int32 NumActuallyTicked = 0;
	switch (NumTickingTasks)
	{
	case 0:
		break;
	case 1:
		{
			UGameplayTask* TickingTask = TickingTasks[0];
			if (IsValid(TickingTask))
			{
				TickingTask->TickTask(DeltaTime);
				NumActuallyTicked++;
			}
		}
		break;
	default:
		{
			static TArray<UGameplayTask*> LocalTickingTasks;
			LocalTickingTasks.Reset();
			LocalTickingTasks.Append(TickingTasks);
			for (UGameplayTask* TickingTask : LocalTickingTasks)
			{
				if (IsValid(TickingTask))
				{
					TickingTask->TickTask(DeltaTime);
					NumActuallyTicked++;
				}
			}
		}
		break;
	};

	// Stop ticking if no more active tasks
	if (NumActuallyTicked == 0)
	{
		TickingTasks.SetNum(0, false);
		UpdateShouldTick();
	}
}

```

> 💡 如果TickingTasks为空表明当前没有需要执行Tick的Task，GameplayTasksComponent的Tick直接会被关闭掉
>
> *GameplayTasksComponent的子类可以通过重载GetShouldTick来决定Component何时可以启用/停用Tick*

```cpp
void UGameplayTasksComponent::UpdateShouldTick()
{
	const bool bShouldTick = GetShouldTick();	
	if (IsActive() != bShouldTick)
	{
		SetActive(bShouldTick);
	}
}

```

## 模拟Task列表SimulatedTasks

---

SimulatedTasks是存放需要同步到模拟端的任务列表(模拟Task)，如果Task标记为需要同步到模拟端的则会放入该列表中，该列表支持网络复制(只复制到模拟端)。

```cpp
void UGameplayTasksComponent::OnGameplayTaskActivated(UGameplayTask& Task)
{
...
	if (Task.IsSimulatedTask())
	{
		const bool bWasAdded = AddSimulatedTask(&Task);
		check(bWasAdded == true);
	}

...
}

void UGameplayTasksComponent::GetLifetimeReplicatedProps(...) const
{
	const FDoRepLifetimeParams Params{ COND_SkipOwner, REPNOTIFY_Always, true };
	DOREPLIFETIME_WITH_PARAMS_FAST(UGameplayTasksComponent, SimulatedTasks, Params);
}
```

> 💡
>
> bSimulatedTask标记该Task是否需要在模拟端执行,为True说明该Task支持网络复制
> bIsSimulating标记该Task是在模拟端执行执行的模拟Task

```cpp
class UGameplayTask : public UObject, public IGameplayTaskOwnerInterface
{
	virtual bool IsSupportedForNetworking() const override { return bSimulatedTask; }
}

UAbilityTask_MoveToLocation::UAbilityTask_MoveToLocation(...)
: Super(ObjectInitializer)
{
	bSimulatedTask = true;
}
```

> 💡
>
> Task是由主控端或者主权端(DS端)拉起执行的，如果Task需要在主控端和主权端都执行，一般是单独创建独立执行，Task本身不会网络复制，如果有Task状态需要同步通过Owner发送RPC进行通信(参照UAbilityTask_NetworkSyncPoint)
>
> 需要在模拟端执行的模拟Task则是通过DS端同步到模拟端（需要设置bSimulatedTask 为True），会复制Task本身，一般用于移动相关表现(参照UAbilityTask_MoveToLocation)。

# AbilityTask

---

AbilityTasks继承自GameplayTask，是GAS系统的专用Task的基类。 提供了一些常用的Task的节点。

![image.png](http://pic.xyyxr.cn/20260504111149381.png)

> 💡
>
> 创建AbilityTask的蓝图节点类UK2Node_LatentGameplayTaskCall

有些AbilityTask可能在主控端和DS端都需要执行，一般都是在双端各自创建Task，然后再通过ASC提供的一套RPC接口进行内部事件同步。

AbilityTargetDataMap是以AbilityHandle，PredictionKey作为Key的Map,映射到一个处理事件的委托。通过上传的AbilityHandle，PredictionKey查找到对应的处理委托进行事件的触发。

比如等待技能按键的按下和松开，技能确认释放和取消释放事件(*类似仍手雷之类的投掷操作按下技能按钮后可能需要确认投掷坐标再释放技能或者取消技能释放*)。此类事件可能在主控端或者DS端都需要监听，但是收到事件触发的只在其中的一端，收到事件触发后就需要通过RPC转发下。

> 💡
>
> 模拟Task不支持此类操作,具体实现可以参看
> UAbilityTask_WaitInputPress
>
> UAbilityTask_WaitInputRelease
>
> UAbilityTask_WaitCancel
>
> UAbilityTask_WaitConfirm

```cpp
FGameplayAbilityReplicatedDataContainer AbilityTargetDataMap;
	
struct FGameplayAbilityReplicatedDataContainer

private:

	typedef TPair<FGameplayAbilitySpecHandleAndPredictionKey, TSharedRef<FAbilityReplicatedDataCache>> FKeyDataPair;

	TArray<FKeyDataPair> InUseData;
	TArray<TSharedRef<FAbilityReplicatedDataCache>> FreeData;
};
```

```cpp
namespace EAbilityGenericReplicatedEvent
{
	enum Type : int
	{	
		GenericConfirm = 0,
		GenericCancel,
		InputPressed,	
		InputReleased,
		GenericSignalFromClient,
		GenericSignalFromServer,
		GameCustom1,
		GameCustom2,
		GameCustom3,
		GameCustom4,
		GameCustom5,
		GameCustom6,
		MAX
	};
}
```

```cpp
UFUNCTION(Server, reliable, WithValidation)
void ServerSetReplicatedEvent(...);

UFUNCTION(Client, reliable)
void ClientSetReplicatedEvent(...);

bool InvokeReplicatedEvent(...);
```