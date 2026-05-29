> 💡 **本系列文章基于UE5.3**

# FGameplayAbilityTargetData

---

GA的使用很多情况下都需要一个或者多个释放目标，比如点击选择的目标、AOE(范围攻击)扫描筛选的目标、射击准星瞄准的目标、投掷手雷弹选中的投掷点

UE提供了FGameplayAbilityTargetData，用于存放GA的目标信息。FGameplayAbilityTargetData只是一个提供常用接口的基类。可以根据需求创建一个子类定制目标信息的存放、获取方式。

```cpp
struct GAMEPLAYABILITIES_API FGameplayAbilityTargetData
{
	//给选中的目标赋予GE
	TArray<FActiveGameplayEffectHandle> ApplyGameplayEffect(...);
	virtual TArray<FActiveGameplayEffectHandle> ApplyGameplayEffectSpec(...);
	
	//将目标信息放入上下文信息中
	virtual void AddTargetDataToContext(...) const;
	
	//获取和设置目标信息
	virtual TArray<TWeakObjectPtr<AActor>> GetActors() const
	virtual bool SetActors(TArray<TWeakObjectPtr<AActor>> NewActorArray)
	
	//通过射线检测命中的目标结果(比如准心瞄准的目标)
	virtual bool HasHitResult() const
	virtual const FHitResult* GetHitResult() const

	//获取施法的起始点位置信息(比如投掷手雷的起始点)
	virtual bool HasOrigin() const
	virtual FTransform GetOrigin() const
	
	//获取施法的目标点位置信息(比如投掷手雷的选择点)
	virtual bool HasEndPoint() const
	virtual FVector GetEndPoint() const
	virtual FTransform GetEndPointTransform() const
};
```

> 💡 参照子类
> FGameplayAbilityTargetData_ActorArray
> FGameplayAbilityTargetData_SingleTargetHit
>
> 上述两种就是比较常见的存放目标信息的数据结构

# FGameplayAbilityTargetDataHandle

---

FGameplayAbilityTargetDataHandle作为参数或者其他数据结构的成员变量来传递FGameplayAbilityTargetData信息。

FGameplayAbilityTargetDataHandle内部封装了一个基类FGameplayAbilityTargetData的智能指针数组，可以存放继承自FGameplayAbilityTargetData的各种子类实例，且支持网络复制传输。

```cpp
struct GAMEPLAYABILITIES_API FGameplayAbilityTargetDataHandle
{
	TArray<TSharedPtr<FGameplayAbilityTargetData>, TInlineAllocator<1> >	Data;
}

template<>
struct TStructOpsTypeTraits<FGameplayAbilityTargetDataHandle> : 
public TStructOpsTypeTraitsBase2<FGameplayAbilityTargetDataHandle>
{
	enum
	{
		WithCopy = true,
		WithNetSerializer = true,
		WithIdenticalViaEquality = true,
	};
};
```

> 💡 与FGameplayEffectContent机制类似，详细说明可以参照
>
> [GAS-上下文信息-**GameplayEffectContext**](GAS-%E4%B8%8A%E4%B8%8B%E6%96%87%E4%BF%A1%E6%81%AF-GameplayEffectContext.md)

# 目标筛选

---

**FGameplayTargetDataFilter**是负责提供筛选目标的机制，比如AOE通过扫描扫到一堆目标，需要设置筛选规则来筛选出哪些是符合需求的目标。FGameplayTargetDataFilter作为基类只是提供了一个初始模板，可以根据具体需求定制继承自FGameplayTargetDataFilter的子类，重载虚函数FilterPassesForActor。

```cpp
struct GAMEPLAYABILITIES_API FGameplayTargetDataFilter
{
	virtual bool FilterPassesForActor(const AActor* ActorToBeFiltered) const;
}
```

FGameplayTargetDataFilterHandle内部封装了一个基类FGameplayTargetDataFilter的智能指针，可以存放继承自FGameplayTargetDataFilter的各种子类实例。通过重载操作符()来便利的调用到FGameplayTargetDataFilter的筛选处理函数FilterPassesForActor

> 💡 重载 () 操作符称为函数调用运算符重载。该运算符允许你将一个对象看作是可调用的函数。

```cpp

struct GAMEPLAYABILITIES_API FGameplayTargetDataFilterHandle
{
	
	TSharedPtr<FGameplayTargetDataFilter> Filter;

	bool FilterPassesForActor(const AActor* ActorToBeFiltered) const
	{
		if (Filter.IsValid())
		{
			if (!Filter.Get()->FilterPassesForActor(ActorToBeFiltered))
			{
				return false;
			}
		}
		return true;
	}

	bool operator()(const AActor* ActorToBeFiltered) const
	{
		return FilterPassesForActor(ActorToBeFiltered);
	}
	bool operator()(const TWeakObjectPtr<AActor> ActorToBeFiltered) const
	{
		return FilterPassesForActor(ActorToBeFiltered.Get());
	}
};
```

**目标筛选示例**

```cpp
FGameplayAbilityTargetDataHandle UAbilitySystemBlueprintLibrary::FilterTargetData(...)
{
	FGameplayAbilityTargetDataHandle ReturnDataHandle;
	
	for (int32 i = 0; TargetDataHandle.IsValid(i); ++i)
	{
		const FGameplayAbilityTargetData* UnfilteredData = TargetDataHandle.Get(i);

		const TArray<TWeakObjectPtr<AActor>> UnfilteredActors = UnfilteredData->GetActors();
		
			**//因为FilterHandle重载了操作符() 可以直接用以数组元素的筛选(FilterByPredicate)
			//最终会调用到FGameplayTargetDataFilter的筛选处理函数FilterPassesForActor**
			TArray<TWeakObjectPtr<AActor>> FilteredActors = 
			UnfilteredActors.FilterByPredicate(FilterHandle);
			
			if (FilteredActors.Num() > 0)
			{
				**//重新创建一份目标信息**FGameplayAbilityTargetData
				//**用筛选出来的有效目标填充**
				const UScriptStruct* ScriptStruct = UnfilteredData->GetScriptStruct();
				
				FGameplayAbilityTargetData* NewData = 
				(FGameplayAbilityTargetData*)FMemory::Malloc(
				ScriptStruct->GetCppStructOps()->GetSize());
				
				ScriptStruct->InitializeStruct(NewData);
				ScriptStruct->CopyScriptStruct(NewData, UnfilteredData);
				ReturnDataHandle.Data.Add(TSharedPtr<FGameplayAbilityTargetData>(NewData));
				
				if (FilteredActors.Num() < UnfilteredActors.Num())
				{
					if (!NewData->SetActors(FilteredActors))
					{
						check(false);
					}
				}
			}
	}
	
	return ReturnDataHandle;
}
```