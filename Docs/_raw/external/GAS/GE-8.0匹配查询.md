> 💡 **本系列文章基于UE5.3**

# 概述

---

在GE使用过程，不可避免需要对GE进行匹配操作。典型的应用就是驱散和免疫效果，需要对满足条件的GE执行免疫或者驱散操作。GAS系统中**通过FGameplayEffectQuery来定义GE匹配操作。**支持通过来源、修正的属性类型、配置(UGameplayEffect)、Tag、自定义匹配规则等多种手段来匹配GE。

```cpp
struct GAMEPLAYABILITIES_API FGameplayEffectQuery
{
	**//自定义匹配规则**
	FActiveGameplayEffectQueryCustomMatch CustomMatchDelegate;

	**//自定义匹配规则(蓝图)**
	UPROPERTY(BlueprintReadWrite, Category = Query)
	FActiveGameplayEffectQueryCustomMatch_Dynamic CustomMatchDelegate_BP;

  **//匹配GE配置的Tag集合**:赋予GE自身的Tag集合和赋予目标的Tag集合(包括动态添加的DynamicTags)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Query)
	FGameplayTagQuery OwningTagQuery;

	**//匹配GE来源Tag:仅限来自赋予GE自身的Tag集合(包括DynamicAssetTags)**
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Query)
	FGameplayTagQuery EffectTagQuery;

	**//匹配GE来源Tag集合:仅限来自GE和GA赋予的来源Tag集合**
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Query, DisplayName = SourceSpecTagQuery)
	FGameplayTagQuery SourceTagQuery;

	**//匹配GE来源Tag集合:包括所有的来源Tag**
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Query)
	FGameplayTagQuery SourceAggregateTagQuery;

	**//匹配GE修正的属性类型**
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Query)
	FGameplayAttribute ModifyingAttribute;

	**//匹配GE的来源UObject(SourceObject)**
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Query)
	TObjectPtr<const UObject> EffectSource;

	**//匹配GE的配置蓝图(UGameplayEffect)**
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = Query)
	TSubclassOf<UGameplayEffect> EffectDefinition;

	**//忽略指定的GE** 
	TArray<FActiveGameplayEffectHandle> IgnoreHandles;
}
```

GE匹配应用场景举例:

- 免疫效果 需要指定具体能免疫哪些效果(免疫组件**UImmunityGameplayEffectComponent**)
- 驱散效果 需要指定具体能驱散哪些效果(驱散组件**URemoveOtherGameplayEffectComponent**)
- 移除激活效果容器(**FActiveGameplayEffectsContainer**)指定的效果
- 查找激活效果容器(**FActiveGameplayEffectsContainer**)指定的效果集合

```cpp
struct GAMEPLAYABILITIES_API FActiveGameplayEffectsContainer
{
	TArray<FActiveGameplayEffectHandle> GetActiveEffects(
	const FGameplayEffectQuery& Query) const;
	
	int32 RemoveActiveEffects(const FGameplayEffectQuery& Query, 
	int32 StacksToRemove);
	
	TArray<float> GetActiveEffectsDuration(const FGameplayEffectQuery& Query) const;
	
	TArray<float> GetActiveEffectsTimeRemaining(const FGameplayEffectQuery& Query) const;
	
	int32 GetActiveEffectCount(const FGameplayEffectQuery& Query...) const;
}
```

**匹配查询示例**
通过FGameplayEffectQuery::Matches进行匹配

```cpp
TArray<FActiveGameplayEffectHandle> FActiveGameplayEffectsContainer::GetActiveEffects(...) const
{
	
	TArray<FActiveGameplayEffectHandle> ReturnList;

	for (const FActiveGameplayEffect& Effect : this)
	{
		//**匹配查询(FGameplayEffectQuery::Matches)**
		**if (!Query.Matches(Effect))**
		{
			continue;
		}

		ReturnList.Add(Effect.Handle);
	}

	return ReturnList;
}
```

# 根据Tag进行匹配查询

---

可以根据**GE赋予的Tag集合**，**GE来源Tag集合**进行匹配

**GE来源Tag集合介绍参照**

[**CapturedSourceTags**](GE-2.0%E8%BF%90%E8%A1%8C%E6%B5%81%E7%A8%8B%E8%AF%A6%E8%A7%A3.md) 

**GE赋予的Tag集合介绍参照**

[**CapturedTargetTags**](GE-2.0%E8%BF%90%E8%A1%8C%E6%B5%81%E7%A8%8B%E8%AF%A6%E8%A7%A3.md) 

**这里的Tag匹配用到FGameplayTagQuery，是UE提供的一种强大的Tag匹配机制，支持配置灵活复杂的匹配规则。**

通过一套类似逻辑运算符(与、或、非)组成的表达式机制，可以灵活定制各种查询条件，用来查询指定的Tag集合(FGameplayTagContainer)是否满足筛选、限制条件(应该有哪些Tag、不能有哪些Tag)**。**

> 💡
>
> 比如下图所示的配置: 转换成表达式
> (!HasTag(Tag1)) &&
> ( **(HasTag(Tag5)||(HasTag(Tag6)** ) && ( **(HasTag(Tag7)||(HasTag(Tag8))**  )&&
> ( HasTag(Tag2)|| HasTag(Tag3) || HasTag(Tag4) )
>
> 即匹配的Tag容器需要同时满足以下三个条件是: 
> 1.不能有Tag1
> 2.Tag5、Tag6 之中至少要有一个并且Tag7、Tag8 之中至少要有一个
> 3.Tag2、Tag3、Tag4 之中至少要有一个

![image.png](http://pic.xyyxr.cn/20260504111207009.png)

**详细介绍参照**

[Tag-4.0匹配查询](Tag-4.0%E5%8C%B9%E9%85%8D%E6%9F%A5%E8%AF%A2.md) 

## **匹配GE配置的Tag集合**

---

赋予GE自身的Tag集合和赋予目标的Tag集合(包括动态添加的DynamicTags)

```cpp
bool FGameplayEffectQuery::Matches(const FGameplayEffectSpec& Spec) const
{
...
	//匹配赋予的Tag集合(包括赋予GE本身的Tag和赋予拥有GE的Actor的Tag)
	if (**OwningTagQuery**.IsEmpty() == false)
	{
		check(IsInGameThread());
		static FGameplayTagContainer TargetTags;
		TargetTags.Reset();
		//自带Tag集合
		Spec.GetAllAssetTags(TargetTags);
		//赋予拥有者Actor的Tag集合
		Spec.GetAllGrantedTags(TargetTags);
		
		**//通过FGameplayTagQuery 来匹配Tag集合**
		**if (OwningTagQuery.Matches(TargetTags) == false)**
		{
			return false;
		}
	}
...
}
```

## 匹配**GE来源Tag集合**

---

- **匹配GE来源Tag:仅限来自赋予GE自身的Tag集合(包括DynamicAssetTags)**
    
```cpp
    bool FGameplayEffectQuery::Matches(const FGameplayEffectSpec& Spec) const
    {
    ...
    	//匹配自带的Tag集合(赋予GE本身的SourceObject)
    	if (EffectTagQuery.IsEmpty() == false)
    	{
    		check(IsInGameThread());
    		static FGameplayTagContainer GETags;
    		GETags.Reset();
    
    		Spec.**GetAllAssetTags**(GETags);
    
    		**//通过FGameplayTagQuery 来匹配Tag集合**
    		if (EffectTagQuery.Matches(GETags) == false)
    		{
    			return false;
    		}
    	}
    
    ...
    }
    
    void FGameplayEffectSpec::GetAllAssetTags(...) const
    {
     //获取GE自身自带的Tag集合，包括DynamicAssetTags
    	OutContainer.AppendTags(GetDynamicAssetTags());
    	if (Def)
    	{
    		OutContainer.AppendTags(Def->GetAssetTags());
    	}
    }
```
    
- **匹配GE来源Tag集合:仅限来自GE和GA赋予的来源Tag集合**
    
```cpp
    bool FGameplayEffectQuery::Matches(const FGameplayEffectSpec& Spec) const
    {
    ...
    	//匹配来源tag集合 仅Spec(GA和GE)
    	if (SourceTagQuery.IsEmpty() == false)
    	{
    		FGameplayTagContainer const& SourceSpecTags = Spec.CapturedSourceTags.GetSpecTags();
    		
    		**//通过FGameplayTagQuery 来匹配Tag集合**
    		if (SourceTagQuery.Matches(SourceSpecTags) == false)
    		{
    			return false;
    		}
    	}
    
    ...
    }
```
    
- **匹配GE来源Tag集合:包括所有的来源Tag**
    
```cpp
    bool FGameplayEffectQuery::Matches(const FGameplayEffectSpec& Spec) const
    {
    ...
    	//匹配来源聚合tag集合 包括Actor和Spec(GA和GE)
    	if (SourceAggregateTagQuery.IsEmpty() == false)
    	{
    		FGameplayTagContainer const& SourceAggregateTags = 
    		*Spec.CapturedSourceTags.GetAggregatedTags();
    		
    		**//通过FGameplayTagQuery 来匹配Tag集合**
    		if (SourceAggregateTagQuery.Matches(SourceAggregateTags) == false)
    		{
    			return false;
    		}
    	}
    
    ...
    }
```
    

# 匹配修正的属性类型

---

```cpp
bool FGameplayEffectQuery::Matches(const FGameplayEffectSpec& Spec) const
{
...
	// 根据GE修改的属性进行匹配
	if (ModifyingAttribute.IsValid())
	{
		bool bEffectModifiesThisAttribute = false;

		for (int32 ModIdx = 0; ModIdx < Spec.Modifiers.Num(); ++ModIdx)
		{
			const FGameplayModifierInfo& ModDef = Spec.Def->Modifiers[ModIdx];
			const FModifierSpec& ModSpec = Spec.Modifiers[ModIdx];

			if (ModDef.Attribute == ModifyingAttribute)
			{
				bEffectModifiesThisAttribute = true;
				break;
			}
		}
		if (bEffectModifiesThisAttribute == false)
		{
			return false;
		}
	}

...
}

```

# 匹配GE来源UObject

---

```cpp
bool FGameplayEffectQuery::Matches(const FGameplayEffectSpec& Spec) const
{
...
	// 根据来源Object匹配  SourceObject
	if (EffectSource != nullptr)
	{
		if (Spec.GetEffectContext().GetSourceObject() != EffectSource)
		{
			return false;
		}
	}
...
}

```

# 匹配GE配置模板

---

```cpp
bool FGameplayEffectQuery::Matches(const FGameplayEffectSpec& Spec) const
{
...
	// 根据指定GE数据模板(配置的GE资产)进行匹配
	if (EffectDefinition != nullptr)
	{
		if (Spec.Def != EffectDefinition.GetDefaultObject())
		{
			return false;
		}
	}
...
}

```

# 自定义匹配规则

---

除了常规的匹配规则，还允许定制自定义匹配规则(绑定判定委托)

```cpp
bool FGameplayEffectQuery::Matches(const FActiveGameplayEffect& Effect) const
{
	//指定忽略的GE实例 跳过
	if (IgnoreHandles.Contains(Effect.Handle))
	{
		return false;
	}

	//自定义委托的判定
	if (CustomMatchDelegate.IsBound())
	{
		if (CustomMatchDelegate.Execute(Effect) == false)
		{
			return false;
		}
	}

	if (CustomMatchDelegate_BP.IsBound())
	{
		bool bDelegateMatches = false;
		CustomMatchDelegate_BP.Execute(Effect, bDelegateMatches);
		if (bDelegateMatches == false)
		{
			return false;
		}
	}
	
	//常规匹配规则
	return Matches(Effect.Spec);

}
```

**应用示例**

```cpp
int32 UAbilitySystemComponent::GetGameplayEffectCount(...) const
{
	int32 Count = 0;

	if (SourceGameplayEffect)
	{
		FGameplayEffectQuery Query;
		
		**//绑定匹配判定委托**
		**Query.CustomMatchDelegate.BindLambda**([&](
		const FActiveGameplayEffect& CurEffect)
		{
			bool bMatches = false;

	
			if (CurEffect.Spec.Def && SourceGameplayEffect == 
			CurEffect.Spec.Def->GetClass())
			{
		
				if (OptionalInstigatorFilterComponent)
				{
					bMatches = (OptionalInstigatorFilterComponent == 
					CurEffect.Spec.GetEffectContext().GetInstigatorAbilitySystemComponent());
				}
				else
				{
					bMatches = true;
				}
			}

			return bMatches;
		});

		Count = ActiveGameplayEffects.GetActiveEffectCount(Query, bEnforceOnGoingCheck);
	}

	return Count;
}
```