> 💡 **本系列文章基于UE5.3**

# 概述

---

- GameplayCueManager是GameplayCue的管理器。游戏启动时会创建一个全局的管理器
- 创建GameplayCueManager时会创建一个GameplayCueSet实例用于存放了所有收集到GameplayCue信息。
- GameplayCueSet承担了主要的管理逻辑，GameplayCueManager主要是负责与其他功能模块的对接。

> 💡 GameplayCue 后续简称GC

# 管理器GameplayCueManager

---

游戏启动时会创建一个全局的GameplayCueManager类型变量GlobalGameplayCueManager负责管理所有的GameplayCue(存放在UAbilitySystemGlobals里)。

会扫描指定路径的所有GameplayCue，将扫描到的信息收集整理放到GameplayCueSet实例中。大部分管理执行逻辑会转发到GameplayCueSet进行执行。

可以新建一个管理类继承自**UGameplayCueManager**，方便根据需求对管理器进行定制化修改。需要修改在DefaultGame.ini的配置的GameplayCue管理器类型信息(C++类或者是一个蓝图)

![Untitled](http://pic.xyyxr.cn/20260504111157840.png)

![Untitled](http://pic.xyyxr.cn/20260504111157841.png)

# 集合GameplayCueSet

---

首次创建GameplayCueManager时，会创建一个UGameplayCueSet对象，GameplayCueSet是存放了所有的GameplayCue信息，并为GameplayTag和GameplayCue建立映射表。

```cpp
class GAMEPLAYABILITIES_API UGameplayCueSet : public UDataAsset
{

	TArray<FGameplayCueNotifyData> GameplayCueData;

	TMap<FGameplayTag, int32> GameplayCueDataMap;

}
```

- **GameplayCueData**
FGameplayCueNotifyData对象数组。FGameplayCueNotifyData存放了一个FGameplayTag及其关联的GameplayCue信息。
所有的GameplayTag和GameplayCue的对应信息都放在这个数组里。

FGameplayCueNotifyData还有个字段ParentDataIdx，这个索引值是指的当前GameplayTag的直接父级GameplayTag对应的FGameplayCueNotifyData在该数组里的索引
    
```cpp
    struct FGameplayCueNotifyData
    {
    	UPROPERTY(EditAnywhere, Category=GameplayCue)
    	FGameplayTag GameplayCueTag;
    
    	UPROPERTY(...)
    	FSoftObjectPath GameplayCueNotifyObj;
    
    	UPROPERTY(transient)
    	TObjectPtr<UClass> LoadedGameplayCueClass;
    
    	int32 ParentDataIdx;
    };
```
    
> 💡 GameplayCue支持通过子Tag触发直接父级Tag所管理的效果，比如Tag.A.A1 支持同时触发 Tag.A.A1关联的GameplayCue及其父级Tag.A关联的GameplayCue。这里就得知道其父级Tag所对应的映射信息是哪个。
    
- **GameplayCueDataMap** 
这个是为了根据GameplayTag快速查找到对应的GameplayCue建立的一个映射表。

在初始化时开始通过**UGameplayCueManager::InitializeRuntimeObjectLibrary()**收集配置的GameplayCue资源。

```cpp
void UGameplayCueManager::InitializeRuntimeObjectLibrary()
{

	RuntimeGameplayCueObjectLibrary.Paths = GetAlwaysLoadedGameplayCuePaths();
	
	if (RuntimeGameplayCueObjectLibrary.CueSet == nullptr)
	{
		RuntimeGameplayCueObjectLibrary.CueSet = 
		NewObject<UGameplayCueSet>(this, TEXT("GlobalGameplayCueSet"));
	}

	RuntimeGameplayCueObjectLibrary.CueSet->Empty();
	RuntimeGameplayCueObjectLibrary.bHasBeenInitialized = true;
	
	RuntimeGameplayCueObjectLibrary.bShouldSyncScan = 
	ShouldSyncScanRuntimeObjectLibraries();
	
	RuntimeGameplayCueObjectLibrary.bShouldSyncLoad = 
	ShouldSyncLoadRuntimeObjectLibraries();
	
	RuntimeGameplayCueObjectLibrary.bShouldAsyncLoad = 
	ShouldAsyncLoadRuntimeObjectLibraries();

	InitObjectLibrary(RuntimeGameplayCueObjectLibrary);
}
```

**GetAlwaysLoadedGameplayCuePaths**获取在DefaultGame.ini配置GameplayCue默认加载路径，可以配置多个路径，**GameplayCue必须放在这些指定的目录中，否则无法被加载**。

![Untitled](http://pic.xyyxr.cn/20260504111157842.png)

![Untitled](http://pic.xyyxr.cn/20260504111157843.png)

也可以通过代码去添加配置路径（UGameplayCueManager::AddGameplayCueNotifyPath），添加后需要触发下**InitializeRuntimeObjectLibrary()**收集新增配置路径的GameplayCue。

![Untitled](http://pic.xyyxr.cn/20260504111157844.png)

![Untitled](http://pic.xyyxr.cn/20260504111159665.png)

> 💡 如果GameplayCue配置指定目录之外，会有提示是个无效的GameplayCue路径。

![Untitled](http://pic.xyyxr.cn/20260504111159666.png)

**InitObjectLibrary**开始扫描收集所有的GC信息

```cpp
TSharedPtr<FStreamableHandle> UGameplayCueManager::InitObjectLibrary(...Lib)
{

...
	//分别加载Actor类型和Static类型的GC
	{
		Lib.ActorObjectLibrary->LoadBlueprintAssetDataFromPaths
		(Lib.Paths, Lib.bShouldSyncScan);
	}
	{
		Lib.StaticObjectLibrary->LoadBlueprintAssetDataFromPaths
		(Lib.Paths, Lib.bShouldSyncScan);
	}
	
	//将收集的信息填充到UGameplayCueSet示例
	BuildCuesToAddToGlobalSet(ActorAssetDatas, 
	GET_MEMBER_NAME_CHECKED(AGameplayCueNotify_Actor, GameplayCueName), 
	CuesToAdd, AssetsToLoad, Lib.ShouldLoad);
	
	BuildCuesToAddToGlobalSet(StaticAssetDatas, 
	GET_MEMBER_NAME_CHECKED(UGameplayCueNotify_Static, GameplayCueName), 
	CuesToAdd, AssetsToLoad, Lib.ShouldLoad);

	UGameplayCueSet* SetToAddTo = Lib.CueSet;
	if (!SetToAddTo)
	{
		SetToAddTo = RuntimeGameplayCueObjectLibrary.CueSet;
	}
	check(SetToAddTo);
	SetToAddTo->AddCues(CuesToAdd);
	
}

```

构造FGameplayCueNotifyData对象数组**GameplayCueData**和根据GameplayTag快速查找到对应的GameplayCue建立的映射表**GameplayCueDataMap** 

```cpp

void UGameplayCueSet::AddCues(const TArray<FGameplayCueReferencePair>& CuesToAdd)
{
	if (CuesToAdd.Num() > 0)
	{
		//构造FGameplayCueNotifyData对象数组**GameplayCueData和**
		for (const FGameplayCueReferencePair& CueRefPair : CuesToAdd)
		{
			const FGameplayTag& GameplayCueTag = CueRefPair.GameplayCueTag;
			const FSoftObjectPath& StringRef = CueRefPair.StringRef;
			...
			FGameplayCueNotifyData NewData;
			NewData.GameplayCueNotifyObj = StringRef;
			NewData.GameplayCueTag = GameplayCueTag;

			GameplayCueData.Add(NewData);
		}
	
		//构造快速根据GameplayTag查找到对应的GameplayCue建立的一个映射表**GameplayCueDataMap** 
		BuildAccelerationMap_Internal();
	}
}

//构造快速根据GameplayTag查找到对应的GameplayCue建立的一个映射表**GameplayCueDataMap**
void UGameplayCueSet::BuildAccelerationMap_Internal()
{
	
	GameplayCueDataMap.Empty();
	GameplayCueDataMap.Add(BaseGameplayCueTag()) = INDEX_NONE;

	for (int32 idx = 0; idx < GameplayCueData.Num(); ++idx)
	{
		GameplayCueDataMap.FindOrAdd(GameplayCueData[idx].GameplayCueTag) = idx;
	}

	FGameplayTagContainer AllGameplayCueTags = 
	UGameplayTagsManager::Get().RequestGameplayTagChildren(BaseGameplayCueTag());

	//为子Tag关联父Tag对应的GC
	// Create entries for children.
	// E.g., if "a.b" notify exists but "a.b.c" does not, 
	//point "a.b.c" entry to "a.b"'s notify.
	for (FGameplayTag ThisGameplayCueTag : AllGameplayCueTags)
	{
		if (GameplayCueDataMap.Contains(ThisGameplayCueTag))
		{
			continue;
		}

		FGameplayTag Parent = ThisGameplayCueTag.RequestDirectParent();

		int32 ParentValue = GameplayCueDataMap.FindChecked(Parent);
		GameplayCueDataMap.Add(ThisGameplayCueTag, ParentValue);
	}

	// 填充构造FGameplayCueNotifyData实例中的ParentDataIdx 
	for (FGameplayCueNotifyData& Data : GameplayCueData)
	{
		FGameplayTag Parent = Data.GameplayCueTag.RequestDirectParent();
		while (Parent != BaseGameplayCueTag() && Parent.IsValid())
		{
			int32* idxPtr = GameplayCueDataMap.Find(Parent);
			if (idxPtr)
			{
				Data.ParentDataIdx = *idxPtr;
				break;
			}
			Parent = Parent.RequestDirectParent();
			if (Parent.GetTagName() == NAME_None)
			{
				break;
			}
		}
	}

}
```

# 激活容器ActiveGameplayCueContainer

---

- DS上用于存放当前激活的**持续性表现**效果(GC)的容器。
- FastArray类型，通过属性复制将容器复制到客户端
- 容器复制到客户端后再触发对应的GC事件

> 💡
>
> 对于那些存在生命周期的持续性表现效果(Add/Remove)，会放入一个管理容器ActiveGameplayCueContainer中，这样就算在表现效果期间出现断线重连或者网络裁切导致客户端角色重建，也能通过容器中保存的表现效果在角色重建时恢复表现效果

# GC执行流程

---

- 可以通过在GE上配置或者直接调用对应的触发接口来触发表现效果
- 可以直接在客户端触发并播放表现效果((只在自己的客户端播放))
- 可以在DS端触发再通过网络在客户端播放表现

## 触发方式

---

**GE配置GameplayCue关联的GameplayTag**

![Untitled](http://pic.xyyxr.cn/20260504111153518.png)

**GA调用对应的接口触发**

![Untitled](http://pic.xyyxr.cn/20260504111155840.png)

**调用对应静态函数触发**

![Untitled](http://pic.xyyxr.cn/20260504111155841.png)

> 💡 一次性的即时效果GC，一般是通过Execute接口触发，而具有生命周期的持续效果，一般是通过Add接口触发，Remove执行移除。

## 多端触发

---

**在客户端直接添加播放GC**

```cpp
//添加持续表现
void UGameplayCueManager::AddGameplayCue_NonReplicated(...)
{
	if (UAbilitySystemComponent* ASC =
	 UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(Target))
	{
		ASC->AddLooseGameplayTag(GameplayCueTag);
	}

	if (UGameplayCueManager* GCM = UAbilitySystemGlobals::Get().GetGameplayCueManager())
	{
		GCM->HandleGameplayCue(...EGameplayCueEvent::OnActive);
		GCM->HandleGameplayCue(...EGameplayCueEvent::WhileActive);
	}
}

//移除持续表现
void UGameplayCueManager::RemoveGameplayCue_NonReplicated(...)
{
	if (UAbilitySystemComponent* ASC = 
	UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(Target))
	{
		ASC->RemoveLooseGameplayTag(GameplayCueTag);
	}

	if (UGameplayCueManager* GCM = UAbilitySystemGlobals::Get().GetGameplayCueManager())
	{
		GCM->HandleGameplayCue(..., GameplayCueTag, EGameplayCueEvent::Removed);
	}
}

//执行一次性即时表现
void UGameplayCueManager::ExecuteGameplayCue_NonReplicated(...)
{
	if (UGameplayCueManager* GCM = UAbilitySystemGlobals::Get().GetGameplayCueManager())
	{
		GCM->HandleGameplayCue(..., EGameplayCueEvent::Executed);
	}
}
```

**在DS端添加GC再通过网络播放**

> [!note]- **添加持续表现**
> 对于网络同步的持续表现效果，DS端会维护一个激活效果容器**ActiveGameplayCueContainer**。该容器支持网络复制。
>
> > 💡
> >
> >     OnActive只会在加入GC容器时触发(广播RPC)，而WhileActive则是每次复制到客户端都会触发(*加入容器、断线重连、离开网络裁切范围都会触发复制到客户端*)

```cpp
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
    	//WhileActive则在下面 GC走复制流程下发到客户端时 PostReplicatedAdd里触发
    	//OnActive只会在首次进入GC容器是触发
    	//WhileActive则是在首次进入容器和后续网络重连时再次下发给客户端时都会触发
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
    

- **移除持续表现**
移除也是直接移除容器**ActiveGameplayCueContainer**中的元素，然后通过网络复制在客户端触发对应的事件。
    
```cpp
    void UAbilitySystemComponent::RemoveGameplayCue_Internal(...)
    {
    	if (IsOwnerActorAuthoritative())
    	{
    		GameplayCueContainer.RemoveCue(GameplayCueTag);
    	}
    }
    
    void FActiveGameplayCue::PreReplicatedRemove(...)
    {
    	if (!InArray.Owner)
    	{
    		return;
    	}
    
    	if (bPredictivelyRemoved == false)
    	{
    		InArray.Owner->UpdateTagMap(GameplayCueTag, -1);
    		InArray.Owner->InvokeGameplayCueEvent(..., EGameplayCueEvent::Removed);
    	}
    }
```
    
- **执行一次性即时表现**
首先ExecuteGameplayCue将需要触发的效果先放到一个临时的缓冲列表**PendingExecuteCues**中，然后在FlushPendingCues通过广播RPC进行触发。
    
```cpp
    void UAbilitySystemComponent::ExecuteGameplayCue(...)
    {
    	UAbilitySystemGlobals::Get().GetGameplayCueManager()->
    	InvokeGameplayCueExecuted(...);
    }
    
    void UGameplayCueManager::InvokeGameplayCueExecuted(...)
    {
    	if (OwningComponent)
    	{
    		FGameplayCuePendingExecute PendingCue;
    		PendingCue.PayloadType = EGameplayCuePayloadType::CueParameters;
    		PendingCue.GameplayCueTags.Add(GameplayCueTag);
    		PendingCue.OwningComponent = OwningComponent;
    		....
    		AddPendingCueExecuteInternal(PendingCue);
    	}
    }
    
    void UGameplayCueManager::FlushPendingCues()
    {
    ...
    if (bHasAuthority)
    {
    ...
    	RepInterface->Call_InvokeGameplayCueExecuted_WithParams(...);
    ...
    }
    ...
    }
```
    

> 💡 跟直接通过调用对应的函数触发CG相比，通过GE配置的GC触发方式有一点不同。
>
> 对于持续性的表现效果：
> 因为对应持续性表现效果的持续性GE也会通过网络复制到客户端(一般只复制到主控端)，所以对于配置在持续性GE上的GC，不需要再在DS上放到GC的激活容器中，但由于持续性GE一般是只复制到主控客户端的，对应模拟端的GC表现则是通过一个额外的GC的激活容器进行复制，该容器只复制到模拟端。
>
> 主控端通过GE复制到客户端时(ActiveGameplayEffectsContainer::PostReplicatedReceive)触发管理GC（AbilitySystemComponent::HandleDeferredGameplayCues）
>
> 模拟端因为默认不会复制GE,需要额外通过复制属性MinimalReplicationGameplayCues(仅复制到模拟端)来触发管理GC（AbilitySystemComponent::AddGameplayCue_MinimalReplication）
>
> 对于一次性即时表现：
> 通过GameplayCueManager::InvokeGameplayCueExecuted_FromSpec调用广播RPC触发。

## GC事件执行

---

**执行堆栈**

![Untitled](http://pic.xyyxr.cn/20260504111159667.png)

1. 其他模块通过最终调用到**GameplayCueManager::HandleGameplayCue**开始触发GC事件执行流程
    
```cpp
    void UGameplayCueManager::HandleGameplayCue(...)
    {
    ...
    	if (!(Options & EGameplayCueExecutionOptions::IgnoreTranslation))
    	{
    		TranslateGameplayCue(GameplayCueTag, TargetActor, Parameters);
    	}
    	RouteGameplayCue(TargetActor, GameplayCueTag, EventType, Parameters, Options);
    ...
    }
```
    

1. GameplayCueManager再调用到GameplayCueSet的HandleGameplayCueNotify_Internal。
先根据Tag在GameplayCueSet存放所有GC配置信息的数组中找到对应GC配置数据，如果是Static类型的则直接使用CDO执行，如果是Actor类型的，找到对应的GC实例。
    
> 💡 Actor类型的实例查找:根据触发者和接收者现在对象池这查找是否有已经存在的实例，有则返回存在的实例，无则重对象池中取出一个新的实例
    
```cpp
    
    bool UGameplayCueSet::HandleGameplayCue(...)
    {
    	//根据Tag 快速查到到对应的数组索引
    	int32* Ptr = GameplayCueDataMap.Find(GameplayCueTag);
    	if (Ptr && *Ptr != INDEX_NONE)
    	{
    		int32 DataIdx = *Ptr;
    		FGameplayCueParameters writableParameters = Parameters;
    		return HandleGameplayCueNotify_Internal(...);
    	}
    }
    
    bool UGameplayCueSet::HandleGameplayCueNotify_Internal(...)
    {
    	UGameplayCueManager* CueManager = 
    	UAbilitySystemGlobals::Get().GetGameplayCueManager();
    	
    	if (!ensure(CueManager))
    	{
    		return false;
    	}
    
    	if (DataIdx != INDEX_NONE)
    	{
    		//根据索引 取出GC数据
    		FGameplayCueNotifyData& CueData = GameplayCueData[DataIdx];
    
    		//如果是Static类型的则直接使用CDO执行
    		if (UGameplayCueNotify_Static* NonInstancedCue = 
    		Cast<UGameplayCueNotify_Static>(CueData.LoadedGameplayCueClass
    		->ClassDefaultObject))
    		{
    			if (NonInstancedCue->HandlesEvent(EventType))
    			{
    				NonInstancedCue->**HandleGameplayCue**(TargetActor, EventType, Parameters);
    			}
    		}
    		//如果是Actor类型的，对象池中找到对应的实例
    		else if (AGameplayCueNotify_Actor* InstancedCue = 
    		Cast<AGameplayCueNotify_Actor>(CueData.LoadedGameplayCueClass->C
    		lassDefaultObject))
    		{
    			bool bShouldDestroy = false;
    			if (InstancedCue->HandlesEvent(EventType))
    			{
    				if (TargetActor)
    				{
    					TSubclassOf<AGameplayCueNotify_Actor> InstancedClass = 
    					InstancedCue->GetClass();
    	
    					AGameplayCueNotify_Actor* SpawnedInstancedCue = 
    					CueManager->GetInstancedCueActor(TargetActor, 
    					InstancedClass, Parameters);
    					
    					if (ensure(SpawnedInstancedCue))
    					{
    						SpawnedInstancedCue->**HandleGameplayCue**(TargetActor,
    						 EventType, Parameters);
    					}
    				}
    			}	
    }
```
    

1. GC事件最终执行的函数是**HandleGameplayCue**（以GameplayCueNotify_Actor为例）,根据触发的事件类型调用对应的执行接口。
    
```cpp
    void AGameplayCueNotify_Actor::HandleGameplayCue(...)
    {
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
    		};
    }
```
    

# Tag转换GameplayCueTranslationManager

---

GameplayCue提供一套转换机制，可以将一个GameplayTag根据特定的规则自动则转换成多个不同的GameplayTag。

比如以下Tag分别对应不同英雄的升级表现。如果要实现不同的英雄播放不同的升级表现。
GameplayCue.Hero1.LevUp

GameplayCue.Hero2.LevUp

GameplayCue.Hero3.LevUp

常规操作是在播放表现时判定不同的英雄触发不同的GameplayTag。

还有一种通过GameplayCueTranslation机制实现的方式，就是定制一个转换规则，将一个指定的字符串根据转化规则映射成不同的字符串。

在这个示例中可以定制一个规则: 根据不同的英雄将Tag中的字符串HeroTemplate分别替换成Hero1或者Hero2。这样在播放升级特效时，只需要指定效果Tag为**GameplayCue.HeroTemplate.LevUp 不需要再在播放效果时判定英雄**。在触发GC时会根据定制的规则自动将GameplayCue.HeroTemplate.LevUp替换成GameplayCue.Hero1.LevUp或者GameplayCue.Hero2.LevUp。

有了上述规则后，类似的效果都可以实现自动转换。比如死亡效果有多个，可以直接指定效果Tag为**GameplayCue.HeroTemplate.Dead**就会自动转换。

GameplayCue.Hero1.Dead

GameplayCue.Hero2.Dead

GameplayCue.Hero3.Dead

> 💡 替换规则可以是一个字符串对应替换目标Tag中的多个部分，比如上述GameplayCue.HeroSkillEffectTemplate.LevUp 中的HeroSkillEffectTemplate可以替换GameplayCue.Hero1.Skill.Effect.LevUp中的Hero1.Skill.Effect。
>
> HeroSkillEffectTemplate替换了Tag中的Hero1、Skill、Effect三个部分

> [!note]- 构建转换规则
> 在 UGameplayCueManager::InitObjectLibrary收集GameplayCue结束之后会触发转换规则的构建。

```cpp
    TSharedPtr<FStreamableHandle> UGameplayCueManager::InitObjectLibrary(...)
    {
    ...
    	TranslationManager.BuildTagTranslationTable();
    	...
    }
    void FGameplayCueTranslationManager::BuildTagTranslationTable()
    {
    
    	//收集转换规则
    	RefreshNameSwaps();
    
    	TArray<FName> SplitNames;
    	SplitNames.Reserve(10);
    	
    	// 根据现有的规则构建转换链表
    	for (const FGameplayTag& Tag : AllGameplayCueTags)
    	{
    		SplitNames.Reset();
    		TagManager->SplitGameplayTagFName(Tag, SplitNames);
    
    		BuildTagTranslationTable_r(Tag.GetTagName(), SplitNames);
    	}
    
    }
```
    
    首先**RefreshNameSwaps**会收集所有继承自转换规则基类UGameplayCueTranslator的子类，获取其对应的CDO，从收集所有规则的转换映射。
    
```cpp
    
    //收集转换规则
    void FGameplayCueTranslationManager::RefreshNameSwaps()
    {
    	AllNameSwaps.Reset();
    	TArray<UGameplayCueTranslator*> CDOList;
    
    	//收集所有继承自转换规则基类UGameplayCueTranslator的子类，获取其对应的CDO
    	for( TObjectIterator<UClass> It ; It ; ++It )
    	{
    		UClass* Class = *It;
    		if( !Class->HasAnyClassFlags(CLASS_Abstract | CLASS_Deprecated) )
    		{
    			if( Class->IsChildOf(UGameplayCueTranslator::StaticClass()) )
    			{
    				UGameplayCueTranslator* CDO = 
    				Class->GetDefaultObject<UGameplayCueTranslator>();
    				
    				if (CDO->IsEnabled())
    				{
    					CDOList.Add(CDO);
    				}
    			}
    		}
    	}
    
    	// Sort and get translated names
    	CDOList.Sort([](const UGameplayCueTranslator& A, const UGameplayCueTranslator& B) 
    	{ return (A.GetPriority() > B.GetPriority()); });
    
    	for (UGameplayCueTranslator* CDO : CDOList)
    	{
    		//收集转换映射
    		FNameSwapData& Data = AllNameSwaps[AllNameSwaps.AddDefaulted()];
    		CDO->GetTranslationNameSpawns(Data.NameSwaps);
    		if (Data.NameSwaps.Num() > 0)
    		{
    			Data.ClassCDO = CDO;
    		}
    		else
    		{
    			AllNameSwaps.Pop(false);
    		}
    	}
    ....
    }
```
    
    转换规则示例
    
```cpp
    class UGameplayCueTranslator_Test : public UGameplayCueTranslator
    {
    	GENERATED_BODY()
    
    public:
    
     //构建规则的映射关系(多个转换映射)
    	virtual void GetTranslationNameSpawns() const override
    	{
    		{
    			FGameplayCueTranslationNameSwap Temp;
    			Temp.FromName = FName(TEXT("**HeroTemplate**"));
    			//ToNames可以是多个
    			Temp.ToNames.Add( FName(TEXT("**Hero1**")) );
    			SwapList.Add(Temp);
    		}
    		{
    			FGameplayCueTranslationNameSwap Temp;
    			Temp.FromName = FName(TEXT("**HeroTemplate**"));
    			Temp.ToNames.Add( FName(TEXT("**Hero2**")) );
    			SwapList.Add(Temp);
    		}
    		{
    			FGameplayCueTranslationNameSwap Temp;
    			Temp.FromName = FName(TEXT("**HeroTemplate**"));
    			Temp.ToNames.Add( FName(TEXT("**Hero3**")) );
    			SwapList.Add(Temp);
    		}
    	}
    
    	//根据目标是哪个英雄 决定使用哪个转换映射
    	virtual int32 GameplayCueToTranslationIndex(...) const
    	{
    			return 	GeTranslationIndexByHeroType(TargetActor);
    	}
    
    	// 是否启用该规则
    	virtual bool IsEnabled() const override { return false; }
```
    
    **BuildTagTranslationTable_r**会递归的将构建一个转换链表(多叉树)，先遍历所有的GameplayCue关联的Tag，将Tag拆分(比如GameplayCue.Hero1.LevUp拆分成 GameplayCue Hero1 LevUp 三个字符串)。将拆分的字符串去跟映射规则里匹配。比如按上面转换规则示例中，Hero1会被匹配到。
    
    ![Untitled](http://pic.xyyxr.cn/20260504111159668.png)
    
    将Hero1用**HeroTemplate**替换后得到新的Tag GameplayCue.**HeroTemplate**.LevUp。这个就是该规则转换的根节点，该转换规则下可以链接了3个子节点GameplayCue.Hero1.LevUp\GameplayCue.Hero2.LevUp\GameplayCue.Hero3.LevUp对应的节点。
    
```cpp
    bool FGameplayCueTranslationManager::BuildTagTranslationTable_r(...)
    {
    }
    
```
    
> 💡 根节点 GameplayCue.**HeroTemplate**.LevUp可以链接多个规则的子节点，规则之间有优先级的概念。
    
    ![Untitled](http://pic.xyyxr.cn/20260504111159669.png)
    
> 💡 转换机制支持多个部分的转换。比如要实现不同英雄不同等级段的升级表现。则模板Tag可以是GameplayCue.**HeroTemplate**.**LevTemplate.**LevUp 可以映射的GameplayCue Tag示例如下
>
>     GameplayCue.Hero1.Lev1_10.LevUp
>
>     GameplayCue.Hero1.Lev11_20.LevUp
>
>     GameplayCue.Hero1.Lev21_30.LevUp
>
>     GameplayCue.Hero2.Lev1_10.LevUp
>     GameplayCue.Hero2.Lev11_20.LevUp
>
>     GameplayCue.Hero2.Lev21_30.LevUp
>
>     GameplayCue.Hero3.Lev1_10.LevUp
>     GameplayCue.Hero3.Lev11_20.LevUp
>
>     GameplayCue.Hero3.Lev21_30.LevUp
>
>     上述示例中需要自动转换的有两部分**HeroTemplate、LevTemplate。**这种情况下就需要递归构造了。
>
>     先推导 GameplayCue.**HeroTemplate**.Lev1_10**.**LevUp，发现这个组合的Tag是不存在的，则递归执行推导出GameplayCue.**HeroTemplate**.**LevTemplate.**LevUp
    

在触发GC直接会先检测是否需要通过转换机制对传入的Tag进行转化。

```cpp
void UGameplayCueManager::HandleGameplayCue(...)
{
	if (!(Options & EGameplayCueExecutionOptions::IgnoreTranslation))
	{
		TranslateGameplayCue(GameplayCueTag, TargetActor, Parameters);
	}
	RouteGameplayCue(TargetActor, GameplayCueTag, EventType, Parameters, Options);
}

bool FGameplayCueTranslationManager::TranslateTag_Internal(...)
{
...
}
```

# 调试指令

---

![Untitled](http://pic.xyyxr.cn/20260504111159670.png)

```cpp
int32 DisplayGameplayCues = 0;
static FAutoConsoleVariableRef CVarDisplayGameplayCues(
TEXT("AbilitySystem.DisplayGameplayCues"),	
DisplayGameplayCues, TEXT("Display GameplayCue events in world as text."), 
ECVF_Default	);

int32 DisableGameplayCues = 0;
static FAutoConsoleVariableRef CVarDisableGameplayCues(
TEXT("AbilitySystem.DisableGameplayCues"),	
DisableGameplayCues, TEXT("Disables all GameplayCue events in the world."), 
ECVF_Default );

float DisplayGameplayCueDuration = 5.f;
static FAutoConsoleVariableRef CVarDurationeGameplayCues(
TEXT("AbilitySystem.GameplayCue.DisplayDuration"),	
DisplayGameplayCueDuration, 
TEXT("Disables all GameplayCue events in the world."), ECVF_Default );
```