> 💡 **本系列文章基于UE5.3**

# 概述

---

UE封装了Tag容器**FGameplayTagContainer** 用来管理一组Tag集合，**FGameplayTagContainer** 存放了两个Tag列表**GameplayTags**和**ParentTags**

```cpp
struct FGameplayTagContainer
{
	TArray<FGameplayTag> GameplayTags;
	TArray<FGameplayTag> ParentTags;
}
```

- **GameplayTags** 列表存放了添加进容器Tag。
- **ParentTags** 列表存放了GameplayTags列表中Tag的所有父级Tag。

> 💡 举个例子:
> 将以下Tag加入一个Tag容器
> *Lyra.Player
> Movement.Mode.Walking*
>
> 则Tag容器的GameplayTags 存放的是加入容器的两个Tag: 
> *Lyra.Player
> Movement.Mode.Walking*
>
> 在添加Tag进容器的同时，会将Tag所有父级Tag加入ParentTags列表，也就是此时ParentTags存放的Tag是:
> *Lyra
> Movement
> Movement.Mode*

![Untitled](http://pic.xyyxr.cn/20260504111210753.png)

在添加Tag进容器时，可以通过Tag查找到其对应的Tag节点**FGameplayTagNode，**可以从**FGameplayTagNode**取出Tag的所有父级Tag。

```cpp
void FGameplayTagContainer::AddTag(const FGameplayTag& TagToAdd)
{
	if (TagToAdd.IsValid())
	{
		// Don't want duplicate tags
		GameplayTags.AddUnique(TagToAdd);

		AddParentsForTag(TagToAdd);
	}
	
}

FORCEINLINE_DEBUGGABLE void FGameplayTagContainer::AddParentsForTag(...)
{
	const FGameplayTagContainer* SingleContainer = 
	UGameplayTagsManager::Get().GetSingleTagContainer(Tag);
	if (SingleContainer)
	{
		// Add Parent tags from this tag to our own
		for (const FGameplayTag& ParentTag : SingleContainer->ParentTags)
		{
			ParentTags.AddUnique(ParentTag);
		}
	}
}
```

> 💡 因为Tag本质就是一个FName，而FName可以视为一个uint32。这里相当于用较小的内存开销换取Tag集合的管理操作效率。
>
> 比如要检验一个Tag是否在容器中，提供两种模式，一种是精确匹配，Tag必须在GameplayTags列表中。另一种是模糊匹配，容器管理的Tag只要父级Tag匹配也可以。

```cpp
	
 //精确匹配
	FORCEINLINE_DEBUGGABLE bool HasTagExact(const FGameplayTag& TagToCheck) const
	{
		if (!TagToCheck.IsValid())
		{
			return false;
		}
		// Only check check explicit tag list
		return GameplayTags.Contains(TagToCheck);
	}
	
	//模糊匹配
	FORCEINLINE_DEBUGGABLE bool HasTag(const FGameplayTag& TagToCheck) const
	{
		if (!TagToCheck.IsValid())
		{
			return false;
		}
		// Check explicit and parent tag list 
		return GameplayTags.Contains(TagToCheck) || ParentTags.Contains(TagToCheck);
	}
```

# **Tag容器**常用操作

---

| 函数名 | 函数说明 |
| --- | --- |
| **AddTag** | **添加Tag 同时会添加其所有的父级Tag** |
| **RemoveTag** | **移除Tag 会重新填充ParentTags列表** |
| **HasTag** | **检查容器中是否有指定的Tag(模糊匹配 可以用GameplayTags**和**ParentTags列表匹配)**  |
| **HasTagExact** | **检查容器中是否有指定的Tag(精确匹配 只用GameplayTags列表匹配)**  |
| **HasAny** | **检查容器中是否有传入的检查容器中的任意Tag(模糊匹配 可以用GameplayTags**和**ParentTags列表匹配)** |
| **HasAnyExact** | **检查容器中是否有传入的检查容器中的任意Tag(精确匹配 只用GameplayTags列表匹配)**  |
| **HasAll** | **检查容器中是否有传入的检查容器中的所有Tag(模糊匹配 可以用GameplayTags**和**ParentTags列表匹配)** |
| **HasAllExact** | **检查容器中是否有传入的检查容器中的所有Tag(精确匹配 只用GameplayTags列表匹配)**  |
| **MatchesQuery** | **用Tag的查询表达式FGameplayTagQuery来匹配容器是否满足条件**(后面章节会详细说明匹配逻辑) |
| **NetSerialize** | **网络复制的序列化/反序列化** |

# 其他常用容器

---

除了**FGameplayTagContainer**还封装了一些其他的聚合容器**，用于适用于不同的Tag管理应用场景。这些聚合容器包含多个FGameplayTagContainer。**

## 继承容器(**FInheritedTagContainer**)

---

用于继承合并自父类容器的Tag集合和自身新增Tag集合

- Tag集合**Removed**配置需要从父类继承的Tag集合中移除的Tag(支持模糊匹配)
- Tag集合**Added** 配置除继承父类Tag外自身额外自带的(如果Remove配置类相同的Tag则添加的Tag不会放入最终的组合Tag集合)
- Tag集合**CombinedTags**是经过Remove和Add后最终得到的Tag集合(不可编辑，显示当前Tag集合配置结果)

如下图所示，父类有两个Tag,子类在继承时，从父类移除了一个Tag并新增了一个Tag。

![image.png](http://pic.xyyxr.cn/20260504111207006.png)

![image.png](http://pic.xyyxr.cn/20260504111207007.png)

```cpp
struct GAMEPLAYABILITIES_API FInheritedTagContainer
{
	//需要从组合的Tag集合中排除的Tag
	//对父类继承的部分模糊匹配 对Added的部分则精准匹配 
	//比如配置 XX.Foo 则会过滤掉父类继承的所有XX.Foo及其子Tag XX.Foo.XXX  
	FGameplayTagContainer Removed;
	
	//除继承父类Tag外自身额外自带的
	//如果Remove配置类相同的Tag则添加的Tag不会放入最终的组合Tag集合(精准匹配)
	FGameplayTagContainer  Added 
	
	//组合后得Tag集合
	FGameplayTagContainer CombinedTags;
}

//合并Tag集合
void FInheritedTagContainer::UpdateInheritedTagProperties(...)
{

	CombinedTags.Reset();

	
	if (Parent)
	{
		**//从父类继承的Tag**
		for (auto Itr = Parent->CombinedTags.CreateConstIterator(); Itr; ++Itr)
		{
			**//需要排除的Tag 不继承 模糊匹配**
			if (!Itr->MatchesAny(Removed))
			{
				CombinedTags.AddTag(*Itr);
			}
		}
	}

	**//自身新增的Tag**
	for (auto Itr = Added.CreateConstIterator(); Itr; ++Itr)
	{
		**//需要排除的Tag不添加 精准匹配**
		if (!Removed.HasTagExact(*Itr))
		{
			CombinedTags.AddTag(*Itr);
		}
	}

}
```

## 聚合容器(**FTagContainerAggregator**)

---

通常用于管理捕获自角色的Tag集合(**CapturedActorTags**)、捕获自GA或GE的Tag集合(**CapturedSpecTags**)，包括静态Tag(例如定义在蓝图中的Tag)和动态Tag(例如运行时添加的Tag)。

通过使用**FTagContainerAggregator**，你可以更方便地管理和查询这些Tag，根据需求分别使用捕获自角色的**Tag**集合(**CapturedActorTags**)或者捕获自GA或GE的Tag集合(**CapturedSpecTags**)或者两者的聚合Tag集合(**CachedAggregator**)

```cpp
struct GAMEPLAYABILITIES_API FTagContainerAggregator
{
	//来自与Actor的tag集合
	UPROPERTY()
	FGameplayTagContainer CapturedActorTags;

	//来自与 GE Spec 或者 GA Spec的tag集合
	UPROPERTY()
	FGameplayTagContainer CapturedSpecTags;
	
	//CapturedActorTags和CapturedSpecTags聚合Tag集合
	mutable FGameplayTagContainer CachedAggregator;
	
	
	FGameplayTagContainer& GetActorTags();
	FGameplayTagContainer& GetSpecTags();
	const FGameplayTagContainer* GetAggregatedTags() const;
}
```

# 计数管理容器(FGameplayTagCountContainer)

---

GameplayTagCountContainer 是 Unreal Engine 中用于管理和跟踪 Gameplay Tag 计数的结构体，主要用于 Ability System 组件中。

**主要功能特性**：

- 跟踪、监听 Gameplay Tag 的添加/移除次数（计数变化）
- 支持层级 Tag 的自动处理（如添加Tag计数时会自动将其父层级Tag纳入计数统计中）
- 提供 Tag 匹配检查功能（HasMatchingGameplayTag、HasAllMatchingGameplayTags、HasAnyMatchingGameplayTags）
- 获取指定Tag的计数(GetTagCount)

**主要成员**

```cpp
struct GAMEPLAYABILITIES_API FGameplayTagCountContainer
{
	
	//存储 Tag 及其当前计数的映射
	TMap<FGameplayTag, int32> GameplayTagCountMap;

	//存储显式添加的 Tag（不包含层级继承）
	TMap<FGameplayTag, int32> ExplicitTagCountMap;
	
	//显式添加的 Tag 容器
	FGameplayTagContainer ExplicitTags;
	
	//指定Tag计数变化的监听委托
	TMap<FGameplayTag, FDelegateInfo> GameplayTagEventMap;

	//对容器中任一Tag 添加或者移除的监听
	FOnGameplayEffectTagCountChanged OnAnyTagChangeDelegate;

}
```

> 💡
>
> 显示添加就是直接通过添加Tag的接口直接添加的Tag，不会把对应Tag的父层级Tag(ParentTags)纳入统计

## 计数统计

---

FGameplayTagCountContainer有两个计数容器GameplayTagCountMap、ExplicitTagCountMap，两者区别在于 :

- **ExplicitTagCountMap**只统计通过添加接口加入的Tag计数，不会把Tag的父层级Tag(ParentTags)纳入统计
- **GameplayTagCountMap**则会统计添加接口加入的Tag及其父层级Tag(ParentTags)的计数

```cpp
bool FGameplayTagCountContainer::GatherTagChangeDelegates(...)
{
	
	//GameplayTagCountMap会统计Tag及其父层级Tag(ParentTags)计数
	FGameplayTagContainer TagAndParentsContainer = Tag.GetGameplayTagParents();
	bool CreatedSignificantChange = false;
	for (auto CompleteTagIt = TagAndParentsContainer.CreateConstIterator(); 
	CompleteTagIt; 
	++CompleteTagIt)
	{
		const FGameplayTag& CurTag = *CompleteTagIt;
		int32& TagCountRef = GameplayTagCountMap.FindOrAdd(CurTag);

		const int32 OldCount = TagCountRef;

		// 更新父层级Tag计数
		int32 NewTagCount = FMath::Max(OldCount + CountDelta, 0);
		TagCountRef = NewTagCount;
		}
}
```

> 💡
>
> 比如 添加以下两个Tag
>
> TestTag.Tag1
>
> TestTag.Tag1.TestTag.Tag11
>
> ExplicitTagCountMap中:
>
> TestTag.Tag1 计数1
>
> TestTag.Tag1.TestTag.Tag11 计数1
>
> GameplayTagCountMap中:
>
> TestTag 计数 2
>
> TestTag.Tag1 计数2
>
> TestTag.Tag1.TestTag.Tag11 计数1

**更新Tag计数的接口**:

- **UpdateTagMap_Internal**
- **UpdateTagMapDeferredParentRemoval_Internal**

```cpp
bool FGameplayTagCountContainer::UpdateTagMap_Internal(...)
{
	if (!UpdateExplicitTags(Tag, CountDelta, false))
	{
		return false;
	}

	TArray<FDeferredTagChangeDelegate> DeferredTagChangeDelegates;
	bool bSignificantChange = 
	GatherTagChangeDelegates(Tag, CountDelta, DeferredTagChangeDelegates);
	
	for (FDeferredTagChangeDelegate& Delegate : DeferredTagChangeDelegates)
	{
		Delegate.Execute();
	}

	return bSignificantChange;
}

bool FGameplayTagCountContainer::UpdateTagMapDeferredParentRemoval_Internal(...)
{
	if (!UpdateExplicitTags(Tag, CountDelta, true))
	{
		return false;
	}

	return GatherTagChangeDelegates(Tag, CountDelta, DeferredTagChangeDelegates);
}
```

> 💡
>
> 这两个更新计数的共同操作都是 
> 更新**ExplicitTagCountMap**计数(UpdateExplicitTags)
>
> 更新**GameplayTagCountMap**计数(GatherTagChangeDelegates中操作)
>
> 获取计数变化要触发的委托(GatherTagChangeDelegates中添加)
>
> 区别在于UpdateTagMap_Internal更新计数后直接直接触发委托
>
> UpdateTagMapDeferredParentRemoval_Internal将委托传递给外部调用的地方，由调用者决定何时触发委托。

## 计数变化监听

---

FGameplayTagCountContainer提供了三种监听Tag计数变化的方式

- **监听指定Tag的添加和移除(仅限添加和移除时触发)**(RegisterGameplayTagEvent)
- **监听指定Tag的计数变化(只要计数发生变化就触发)**(RegisterGameplayTagEvent)
- **监听任意Tag的添加和移除(只要容器中有Tag发生添加和移除就触发)**(RegisterGenericGameplayEvent)

```cpp
FOnGameplayEffectTagCountChanged& RegisterGenericGameplayEvent()
{
	return OnAnyTagChangeDelegate;
}

FOnGameplayEffectTagCountChanged& UAbilitySystemComponent::RegisterGameplayTagEvent(...)
{
	return GameplayTagCountContainer.RegisterGameplayTagEvent(Tag, EventType);
}
```

```cpp
bool FGameplayTagCountContainer::GatherTagChangeDelegates(...)
{
...
		//是否是新增或者移除
		const bool SignificantChange = (OldCount == 0 || NewTagCount == 0);
		
		if (SignificantChange)
		{
			//任意Tag新增或者移除 触发OnAnyTagChangeDelegate
			TagChangeDelegates.AddDefaulted();
			TagChangeDelegates.Last().BindLambda([Delegate = **OnAnyTagChangeDelegate**, CurTag, 
			NewTagCount]()
			{
				Delegate.Broadcast(CurTag, NewTagCount);
			});
		}

		FDelegateInfo* DelegateInfo = GameplayTagEventMap.Find(CurTag);
		if (DelegateInfo)
		{
			//指定Tag的计数发生变化 触发绑定的委托
			TagChangeDelegates.AddDefaulted();
			TagChangeDelegates.Last().BindLambda([Delegate = DelegateInfo->**OnAnyChange**, 
			CurTag, NewTagCount]()
			{
				Delegate.Broadcast(CurTag, NewTagCount);
			});

			if (SignificantChange)
			{
				//指定Tag的添加和移除 触发绑定的委托
				TagChangeDelegates.AddDefaulted();
				TagChangeDelegates.Last().BindLambda([Delegate = DelegateInfo->**OnNewOrRemove**, 
				CurTag, NewTagCount]()
				{
					Delegate.Broadcast(CurTag, NewTagCount);
				});
			}
		}
		....
}
```