> 💡 **本系列文章基于UE5.3**

# 概述

---

GE组件是UE5.3引入一个新的概念，其基类是**UGameplayEffectComponent**，GE组件设计定位是通过组件定义GE的行为，好比ActorComponet于Actor的意义，用组合的思路去优化复杂的设计。

最直观的一个改变就是引入组件概念之前打开GE会看到一大堆配置项，看着就觉得很复杂，引入GE组件后，配置项大大减少，只留下必要的配置，其他的配置全部以组件的形式进行封装，按需取用。

同时GE组件也是扩展效果的一种实现途径，上一章介绍了通过自定义执行类来扩展GE效果，但那种方式只能对即时效果(包括定时触发)进行定制，非定时触发的持续效果是不支持的，但通过GE组件扩展效果，持续效果、即时效果都支持。可以实现诸如免疫光环、驱散光环之类的扩展效果 **

其扩展思路是在GE准备赋予给目标、赋予成功、添加进GE激活容器、执行即时效果时都会通知GE组件。**可以根据需求重载GE组件对应的回调接口，通过定制这些关键节点的逻辑达到对GE效果进行扩展的目的**。

GE组件直接是在UGameplayEffect配置时进行添加的，每个GE蓝图都会New一份新的GE组件实例，但因为GE蓝图本身在运行时是作为只读配置直接使用CDO，所有使用该GE蓝图的GE运行时实例(FGameplayEffectSpec实例)都共用一份，所以GE蓝图持有的GE组件实例也应该在运行时视为只读配置，不要在里面存放些运行时产生的数据。

```cpp
protected:
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
	TArray<TObjectPtr<UGameplayEffectComponent>> GEComponents;
```

![image.png](http://pic.xyyxr.cn/20260504111205273.png)

# GE流程中对组件的回调

---

- **GE准备对目标进行赋予**
调用CanGameplayEffectApply判定是否可以赋予
- **赋予成功**
调用OnGameplayEffectApplied通知组件GE已经成功完成对目标赋予
- **添加进GE激活容器**
调用OnActiveGameplayEffectAdded通知组件GE(持续效果)已经添加进了激活效果容器
- **执行即时效果**
调用OnGameplayEffectExecuted通知组件即时效果成功触发时执行时回调
(包括定时触发的效果执行即时效果)

![image.png](http://pic.xyyxr.cn/20260504111207005.png)

```cpp
class GAMEPLAYABILITIES_API UGameplayEffectComponent : public UObject
{
//**GE是否可以对目标进行赋予**
virtual bool CanGameplayEffectApply(...) const { return true; }

//**GE首次Apply成功时回调**(即时效果和持续效果都会在赋予目标成功时触发)
virtual void OnGameplayEffectApplied(...) const {}

//**持续效果GE成功加入激活列表时回调**
virtual bool OnActiveGameplayEffectAdded(...) const { return true; }

//**即时效果成功触发时执行时回调**
virtual void OnGameplayEffectExecuted(...) const {}

}
```

> 💡
>
> 配合一些GE自带的委托，还可以监听流程中其他节点的回调

```cpp
bool UTestGameplayEffectComponent::OnActiveGameplayEffectAdded(...) const
{
//效果移除的回调
ActiveGE.EventSet.OnEffectRemoved.AddUObject(this, &UTestGameplayEffectComponent::OnActiveGameplayEffectRemoved);

//效果激活状态发生变化的回调
ActiveGE.EventSet.OnInhibitionChanged.AddUObject(this, &UTestGameplayEffectComponent::OnInhibitionChanged);
	
//效果堆叠发生的回调
ActiveGE.EventSet.OnStackChanged.AddUObject(this, &UTestGameplayEffectComponent::OnStackChanged);
	
//效果持续时间发生的回调
ActiveGE.EventSet.OnTimeChanged.AddUObject(this, &UTestGameplayEffectComponent::OnDurationChange);

return true;
}
```

### 判定GE是否可以赋予

---

**CanGameplayEffectApply**

**赋予GE前会轮询所有组件，判定是否有组件拦截对目标的赋予**
**所有的 GEComponent的CanGameplayEffectApply 返回True 才会成功对目标赋予GE**

```cpp
FActiveGameplayEffectHandle UAbilitySystemComponent::ApplyGameplayEffectSpecToSelf(...)
{
...
	if (!Spec.Def->CanApply(ActiveGameplayEffects, Spec))
	{
		return FActiveGameplayEffectHandle();
	}
...
}

bool UGameplayEffect::CanApply(...) const
{
	for (const UGameplayEffectComponent* GEComponent : GEComponents)
	{
		if (GEComponent && !GEComponent->CanGameplayEffectApply(ActiveGEContainer, GESpec))
		{
			return false;
		}
	}
	return true;
}
```

### GE被成功赋予的回调

---

**OnGameplayEffectApplied**

**在成功赋予(Apply)GE后会调用所有组件的OnGameplayEffectApplied**

**通知组件GE已经被成功赋予(Apply)**

```cpp

FActiveGameplayEffectHandle UAbilitySystemComponent::ApplyGameplayEffectSpecToSelf(...)
{
...
	Spec.Def->OnApplied(ActiveGameplayEffects, *OurCopyOfSpec, PredictionKey);
...
}

void UGameplayEffect::OnApplied(...) const
{
	for (const UGameplayEffectComponent* GEComponent : GEComponents)
	{
		if (GEComponent)
		{
			GEComponent->OnGameplayEffectApplied(ActiveGEContainer, GESpec, PredictionKey);
		}
	}
}
```

### **成功加入激活容器的回调**

---

**OnActiveGameplayEffectAdded**

**持续效果成功加到激活容器后会调用所有组件的OnActiveGameplayEffectAdded
通知组件GE已经被成功添加到激活容器了
同时组件可以在该接口决定是否允许在GE添加进容器时立即激活**

```cpp
void FActiveGameplayEffectsContainer::InternalOnActiveGameplayEffectAdded(...)
{
...
const bool bActive = EffectDef->OnAddedToActiveContainer(*this, Effect);
...
}

bool UGameplayEffect::OnAddedToActiveContainer(...) const
{
	bool bShouldBeActive = true;
	for (const UGameplayEffectComponent* GEComponent : GEComponents)
	{
		if (GEComponent)
		{
			bShouldBeActive = GEComponent->OnActiveGameplayEffectAdded(...) 
			&& bShouldBeActive;
		}
	}

	return bShouldBeActive;
}
```

### 即时效果执行时的回调

---

**OnGameplayEffectExecuted**

**即时效果成功触发后会调用所有组件的OnGameplayEffectExecuted**

**通知组件GE效果已经被成功触发(执行)**

> 💡 持续效果中的定时触发效果，在时间到了触发效果时也会触发该逻辑
>
> 定时触发实际就是重复触发即时效果

```cpp

void FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom(...)
{
...
	Spec.Def->OnExecuted(*this, Spec, PredictionKey);
...
}
void UGameplayEffect::OnExecuted(...) const
{
...
	for (const UGameplayEffectComponent* GEComponent : GEComponents)
	{
		if (GEComponent)
		{
			GEComponent->OnGameplayEffectExecuted(ActiveGEContainer, GESpec, PredictionKey);
		}
	}
	...
	}
	

```

### **GE配置发生变化的回调**

---

OnGameplayEffectChanged

**当部分GE配置发生变化时(在编辑器编辑) 需要通知GE，可能需要重新生成部分配置。**

> 💡 比如组件 UAssetTagsGameplayEffectComponent 用于配置GE自带的Tag。在编辑器修改后，需要通知GE重新收集Tag

```cpp
void UAssetTagsGameplayEffectComponent::PostEditChangeProperty(...)
{
...
Owner->OnGameplayEffectChanged();
...
}

**//重新填充GE的CachedAssetTags**
void UGameplayEffect::OnGameplayEffectChanged()
{
...
CachedAssetTags.Reset();
for (UGameplayEffectComponent* GEComponent : GEComponents)
{
	if (GEComponent)
	{
		GEComponent->ConditionalPostLoad();
		GEComponent->OnGameplayEffectChanged();
	}
}
...
}

void UAssetTagsGameplayEffectComponent::OnGameplayEffectChanged() const
{
	Super::OnGameplayEffectChanged();
	ApplyAssetTagChanges();
}

void UAssetTagsGameplayEffectComponent::ApplyAssetTagChanges() const
{
	UGameplayEffect* Owner = GetOwner();
	InheritableAssetTags.ApplyTo(Owner->CachedAssetTags);
}
```

# 常用GE组件说明

---

简单介绍下常用的GE组件，可以参考这些常用组件的实现定制自己的GE扩展组件。

## 赋予GE自身Tag的组件

---

**UAssetTagsGameplayEffectComponent**

- 赋予GE自身拥有的Tag  (仅用于标记GE自身)
- 可以选择性的继承父类的Tag 并添加新的Tag
- 最终将结果拷贝到GE 的字段CachedAssetTags

组件配置Tag类型是**FInheritedTagContainer**(继承标签容器)

**继承标签容器用于继承合并自父类Tag集合和自身新增Tag集合

- Tag集合**Removed**配置需要从父类继承的Tag集合中移除的Tag(支持模糊匹配)
- Tag集合**Added** 配置除继承父类Tag外自身额外自带的(如果Remove配置类相同的Tag则添加的Tag不会放入最终的组合Tag集合)
- Tag集合**CombinedTags**是经过Remove和Add后最终得到的Tag集合(不可编辑，显示当前Tag集合配置结果)

如下图所示，父类有两个Tag,子类在继承时，从父类移除了一个Tag并新增了一个Tag。

![image.png](http://pic.xyyxr.cn/20260504111207006.png)

![image.png](http://pic.xyyxr.cn/20260504111207007.png)

> 💡 这些Tag可以标记效果来源哪一个或者哪一类的GE。在某些需要匹配GE的场景会需要这些来源标记。比如有一个免疫光环效果，免疫所有减速效果。则可以通过Tag来识别哪些是减速效果。

- **在构造时会尝试去找到父类继承部分Tag**

```cpp
void UAssetTagsGameplayEffectComponent::PostInitProperties()
{
	Super::PostInitProperties();
	**//构造时 尝试查找父类GE的AssetTags 组件
	//如果有 则继承父类GE的Tag**
	const UAssetTagsGameplayEffectComponent* Parent = FindParentComponent(*this);
	InheritableAssetTags.UpdateInheritedTagProperties(Parent ? 
	&Parent->InheritableAssetTags : nullptr);
}
```

- **编辑组件时更新InheritableAssetTags并通知GE有改动**

```cpp
**//编辑组件时更新InheritableAssetTags并通知GE有改动**
#if WITH_EDITOR
void UAssetTagsGameplayEffectComponent::PostEditChangeProperty(...)
{
	Super::PostEditChangeProperty(PropertyChangedEvent);

	if (PropertyChangedEvent.GetMemberPropertyName()  == GetInheritableAssetTagsName())
	{
		**//重新设置InheritableAssetTags** 
		SetAndApplyAssetTagChanges(InheritableAssetTags);
		
		**//通知GE有改动 需要刷新缓存**
		UGameplayEffect* Owner = GetOwner();
		Owner->OnGameplayEffectChanged();
	}
}
#endif

**//重新设置InheritableAssetTags** 
void UAssetTagsGameplayEffectComponent::SetAndApplyAssetTagChanges(...)
{
	InheritableAssetTags = TagContainerMods;
	const UAssetTagsGameplayEffectComponent* Parent = FindParentComponent(*this);
	InheritableAssetTags.UpdateInheritedTagProperties(Parent ? 
	&Parent->InheritableAssetTags : nullptr);
	
	ApplyAssetTagChanges();
}
```

> [!note]- **最终将组件上的InheritableAssetTags拷贝到GE的CachedAssetTags**
> 将结果汇总到GE缓存起来，同时也时为了兼容旧版逻辑


```cpp
//**最终将组件上的InheritableAssetTags拷贝到GE的CachedAssetTags**
void UAssetTagsGameplayEffectComponent::OnGameplayEffectChanged() const
{
	Super::OnGameplayEffectChanged();
	ApplyAssetTagChanges();
}
void UAssetTagsGameplayEffectComponent::ApplyAssetTagChanges() const
{
	UGameplayEffect* Owner = GetOwner();
	InheritableAssetTags.ApplyTo(Owner->CachedAssetTags);
}
```

## 赋予GE拥有者Tag的组件

---

**UTargetTagsGameplayEffectComponent**

- 赋予GE拥有者的Tag
- 在GE生效时赋予GE拥有者
*(给GE的拥有者打上各种标签 比如在飞行 在游泳)*
- 在GE失效时从GE拥有者移除
- 最终将结果拷贝到GE 的字段CachedGrantedTags

**会将配置结果汇总到GE缓存起来，同时也时为了兼容旧版逻辑。与上面的UAssetTagsGameplayEffectComponent类似**

**将CachedGrantedTags赋予GE拥有者**

```cpp
void FActiveGameplayEffectsContainer::AddActiveGameplayEffectGrantedTagsAndModifiers(...)
{
...
	**//激活GE时 将GrantedTags 赋予拥有者 Owner(UAbilitySystemComponent)**
	Owner->UpdateTagMap(Effect.Spec.Def->GetGrantedTags(), 1);
	Owner->UpdateTagMap(Effect.Spec.DynamicGrantedTags, 1);
...
}

void FActiveGameplayEffectsContainer::RemoveActiveGameplayEffectGrantedTagsAndModifiers(...)
{
...
	**//GE失效时 将GrantedTags 从拥有者 Owner(UAbilitySystemComponent) 移除**
	Owner->UpdateTagMap(Effect.Spec.Def->GetGrantedTags(), -1);
	Owner->UpdateTagMap(Effect.Spec.DynamicGrantedTags, -1);
...
}
```

## 赋予GE拥有者**BlockedAbilityTags**的组件

---

**UBlockAbilityTagsGameplayEffectComponent**

- BlockedAbilityTags用于阻挡带有对应Tag的GA激活
- GE移除时会从BlockedAbilityTags移除对应的Tag
- 最终将结果拷贝到GE 的字段CachedBlockedAbilityTags

**会将配置结果汇总到GE缓存起来，同时也时为了兼容旧版逻辑。与上面的UAssetTagsGameplayEffectComponent类似**

GE生效时会将配置Tag加到 UAbilitySystemComponent的BlockedAbilityTags，GE失效时会将配置Tag从 UAbilitySystemComponent的BlockedAbilityTags移除

```cpp
void FActiveGameplayEffectsContainer::AddActiveGameplayEffectGrantedTagsAndModifiers(FActiveGameplayEffect& Effect, bool bInvokeGameplayCueEvents)
{
...
//GE 添加时 增加Block Tag
Owner->BlockAbilitiesWithTags(Effect.Spec.Def->GetBlockedAbilityTags());
...
}

void FActiveGameplayEffectsContainer::RemoveActiveGameplayEffectGrantedTagsAndModifiers(const FActiveGameplayEffect& Effect, bool bInvokeGameplayCueEvents)
{
...
	//GE 移除时 移除对应的Tag
	Owner->UnBlockAbilitiesWithTags(Effect.Spec.Def->GetBlockedAbilityTags());
...
}

```

## 检测GE拥有者Tags的组件

---

**UTargetTagRequirementsGameplayEffectComponent**

**用于配置GE的拥有者应该有哪些Tag 不能有哪些Tag**

**ApplicationTagRequirements 
如果配置了则GE的拥有者身上的Tag必须满足该配置 否则GE无法被添加(Apply)**

**OngoingTagRequirements   
如果配置了则GE的拥有者身上的Tag必须满足该配置 否则会抑制(Inhibit)GE效果**
*(GE仍在拥有者身上 但是GE附加的效果会临时失效  解除了抑制GE效果会重新生效)*

**RemovalTagRequirements 
如果配置了则GE的拥有者身上的Tag如果满足该配置 则会移除GE**
*(同时也会阻止GE的添加)*

```cpp
class GAMEPLAYABILITIES_API UTargetTagRequirementsGameplayEffectComponent : public UGameplayEffectComponent
{
	//GE的拥有者身上的Tag必须满足该配置 否则GE无法被添加
	**FGameplayTagRequirements** ApplicationTagRequirements;

	//GE的拥有者身上的Tag必须满足该配置 否则会抑制GE效果
	**FGameplayTagRequirements** OngoingTagRequirements;

	//GE的拥有者身上的Tag如果满足该配置 则会移除GE
	FGameplayTagRequirements RemovalTagRequirements;
	}
```

> 💡 ***FGameplayTagRequirements**  封装了对Tag的匹配操作(应该有哪些Tag 不能有哪些Tag)
> 参照
> [Tag-3.0集合容器](Tag-3.0%E9%9B%86%E5%90%88%E5%AE%B9%E5%99%A8.md)*

- **检测ApplicationTagRequirements和RemovalTagRequirements配置判定GE是否可以被添加(Apply)**
    
```cpp
    //**检测GE 是否可以被添加**
    bool UTargetTagRequirementsGameplayEffectComponent::CanGameplayEffectApply(...) const
    {
    	FGameplayTagContainer Tags;
    	ActiveGEContainer.Owner->GetOwnedGameplayTags(Tags);
    	
    	**//不满足ApplicationTagRequirements配置 则不能添加**
    	if (ApplicationTagRequirements.RequirementsMet(Tags) == false)
    	{
    		return false;
    	}
    	
    	**//满足RemovalTagRequirements配置 则不能添加**
    	if (!RemovalTagRequirements.IsEmpty() && 
    	RemovalTagRequirements.RequirementsMet(Tags) == true)
    	{
    		return false;
    	}
    
    	return true;
    }
```
    

- **当拥有该组件的GE被成功添加进激活容器时监听Tag变化
并检测OngoingTagRequirements看GE添加后是否能立即生效**
    
```cpp
    **//当拥有该组件的GE被添加进激活容器时
    //监听所有OngoingTagRequirements和RemovalTagRequirements关联的Tag
    //并在首次添加时检测OngoingTagRequirements 看GE添加后是否能立即生效**
    bool UTargetTagRequirementsGameplayEffectComponent::OnActiveGameplayEffectAdded(...) const
    {
    
    ...
    		AppendUnique(GameplayTagsToBind, 
    		OngoingTagRequirements.IgnoreTags.GetGameplayTagArray());
    		AppendUnique(GameplayTagsToBind, 
    		OngoingTagRequirements.RequireTags.GetGameplayTagArray());
    		AppendUnique(GameplayTagsToBind, 
    		OngoingTagRequirements.TagQuery.GetGameplayTagArray());
    		
    		AppendUnique(GameplayTagsToBind, 
    		RemovalTagRequirements.IgnoreTags.GetGameplayTagArray());
    		AppendUnique(GameplayTagsToBind, 
    		RemovalTagRequirements.RequireTags.GetGameplayTagArray());
    		AppendUnique(GameplayTagsToBind, 
    		RemovalTagRequirements.TagQuery.GetGameplayTagArray());
    		
    		for (const FGameplayTag& Tag : GameplayTagsToBind)
    		{
    			FOnGameplayEffectTagCountChanged& OnTagEvent = ASC->RegisterGameplayTagEvent
    			(Tag, EGameplayTagEventType::NewOrRemoved);
    			
    			FDelegateHandle Handle = OnTagEvent.AddUObject
    			(this, &UTargetTagRequirementsGameplayEffectComponent::OnTagChanged, ActiveGEHandle);
    			
    			AllBoundEvents.Emplace(Tag, Handle);
    		}
    	...
    	}
    
    	FGameplayTagContainer TagContainer;
    	ASC->GetOwnedGameplayTags(TagContainer);
    
    	return OngoingTagRequirements.RequirementsMet(TagContainer);
    }
```
    

- **Tag发生了变动检测下RemovalTagRequirements和OngoingTagRequirements配置是否匹配**
    
> 💡 满足RemovalTagRequirements则移除GE
>
>     满足OngoingTagRequirements配置则GE可以解除抑制(Inhibit)状态(重新激活)
>
>     不满足OngoingTagRequirements配置则GE进入抑制(Inhibit)状态(取消激活)
    
```cpp
    **//Tag 发生了变动则需要检测下是否满足RemovalTagRequirements和OngoingTagRequirements**
    void UTargetTagRequirementsGameplayEffectComponent::OnTagChanged(...) const
    {
    	UAbilitySystemComponent* Owner = ActiveGEHandle.GetOwningAbilitySystemComponent();
    	if (!Owner)
    	{
    		return;
    	}
    
    	const FActiveGameplayEffect* ActiveGE = Owner->GetActiveGameplayEffect(ActiveGEHandle);
    	if (ensure(ActiveGE) && !ActiveGE->IsPendingRemove)
    	{
    		FGameplayTagContainer OwnedTags;
    		Owner->GetOwnedGameplayTags(OwnedTags);
    
    		const bool bRemovalRequirementsMet = !RemovalTagRequirements.IsEmpty() 
    		&& RemovalTagRequirements.RequirementsMet(OwnedTags);
    		
    		if (bRemovalRequirementsMet)
    		{
    			**// 满足RemovalTagRequirements 则移除GE**
    				Owner->RemoveActiveGameplayEffect(ActiveGEHandle);
    		}
    		else
    		{
    			**//满足OngoingTagRequirements配置则GE可以解除抑制(Inhibit 非激活状态)状态(重新激活)
    			//不满足OngoingTagRequirements配置则GE进入抑制(Inhibit 非激活状态)状态(取消激活)
    			//第二个参数 为False表示解除冻结(抑制)状态**
    			const bool bOngoingRequirementsMet = OngoingTagRequirements.IsEmpty() 
    			|| OngoingTagRequirements.RequirementsMet(OwnedTags);
    			Owner->InhibitActiveGameplayEffect(ActiveGEHandle, 
    			!bOngoingRequirementsMet, bInvokeCuesIfStateChanged);
    		}
    	}
    }
```
    

## 配置GE添加(Apply)概率的组件

---

**UChanceToApplyGameplayEffectComponent**

**配置一个GE添加成功的概率(FScalableFloat)类型**

> 💡 *FScalableFloat 类型可以配置一个固定值或者从CurveTable根据等级映射一个值*

- **根据配置的概率判定是否可以添加（Apply）**

```cpp
**//根据配置的概率判定是否可以添加（Apply）**
bool UChanceToApplyGameplayEffectComponent::CanGameplayEffectApply(const FActiveGameplayEffectsContainer& ActiveGEContainer, const FGameplayEffectSpec& GESpec) const
{
	const FString ContextString = GESpec.Def->GetName();
	const float CalculatedChanceToApplyToTarget = ChanceToApplyToTarget.GetValueAtLevel(GESpec.GetLevel(), &ContextString);

	if ((CalculatedChanceToApplyToTarget < 1.f - SMALL_NUMBER) && 
	(FMath::FRand() > CalculatedChanceToApplyToTarget))
	{
		return false;
	}

	return true;
}
```

## 配置拦截GE添加(Apply)的自定义规则的组件

---

**UCustomCanApplyGameplayEffectComponent**

**如果对GE添加还有其他千奇百怪的限制规则 则可以通过该组件配置自定义规则**

- **根据配置的自定义规则判定是否可以添加（Apply）**

> 💡
>
> *可以配置多个继承自**UGameplayEffectCustomApplicationRequirement**(或其子类)的类
>
> 按需实现接口CanApplyGameplayEffect* 
>
> *判定时直接用CDO(ClassDefaultObject)进行判定*

```cpp

TArray<TSubclassOf<**UGameplayEffectCustomApplicationRequirement**>> ApplicationRequirements;

bool UCustomCanApplyGameplayEffectComponent::CanGameplayEffectApply(...) const
{
	for (const TSubclassOf<UGameplayEffectCustomApplicationRequirement>& AppReq : ApplicationRequirements)
	{
	
		if (*AppReq && AppReq->GetDefaultObject<UGameplayEffectCustomApplicationRequirement>()
		->CanApplyGameplayEffect(GESpec.Def, GESpec, ActiveGEContainer.Owner) == false)
		{
			return false;
		}
	}

	return true;
}
```

## 赋予GE拥有者额外技能的组件

---

**UAbilitiesGameplayEffectComponent**

**GE效果被激活时(包括被抑制后重新激活) 会赋予拥有者额外的技能**

**GE效果失效或者移除时(包括被抑制后取消激活)  根据配置策略决定是否移除赋予技能**

- **当GE被添加进激活容器时监听GE抑制状态的变化(激活/取消激活) 同时也监听GE是否被移除**

```cpp
**//当GE 被添加进激活容器时 
//监听效果抑制状态的变化(激活/失效)
//监听GE是否被移除**
bool UAbilitiesGameplayEffectComponent::OnActiveGameplayEffectAdded(...) const
{
	if (ActiveGEContainer.IsNetAuthority())
	{
		ActiveGE.EventSet.OnEffectRemoved.AddUObject(this, 
		&UAbilitiesGameplayEffectComponent::OnActiveGameplayEffectRemoved);
		
		ActiveGE.EventSet.OnInhibitionChanged.AddUObject(this, 
		&UAbilitiesGameplayEffectComponent::OnInhibitionChanged);
	}

	return true;
}
```

- **抑制状态的变化(激活/取消激活) 尝试赋予或者移除技能**

```cpp
**//抑制状态的变化(激活/失效) 尝试赋予或者移除技能**
void UAbilitiesGameplayEffectComponent::OnInhibitionChanged(...) const
{
	if (bIsInhibited)
	{
		RemoveAbilities(ActiveGEHandle);
	}
	else
	{
		GrantAbilities(ActiveGEHandle);
	}
}
```

- **GE被移除尝试移除技能**

```cpp
**//GE被移除尝试移除技能**
void UAbilitiesGameplayEffectComponent::OnActiveGameplayEffectRemoved(...) const
{
	const FActiveGameplayEffect* ActiveGE = RemovalInfo.ActiveEffect;
	if (!ensure(ActiveGE))
	{
		return;
	}

	RemoveAbilities(ActiveGE->Handle);
}
```

- **赋予的GA配置**

> 💡 *可以指定赋予GA的等级和GE失效或者移除时赋予的GA如何处理(立即移除/等技能结束后再移除/不做处理)*

```cpp
struct FGameplayAbilitySpecConfig
{
	GENERATED_BODY()

	**//赋予的GA**
	UPROPERTY(EditDefaultsOnly, Category = "Ability Definition")
	TSubclassOf<UGameplayAbility> Ability;

	**//赋予的GA配置**
	UPROPERTY(EditDefaultsOnly, Category = "Ability Definition", DisplayName = "Level", meta=(UIMin=0.0))
	FScalableFloat LevelScalableFloat = FScalableFloat{ 1.0f };

	**//赋予的GA触发输入配置**
	UPROPERTY(EditDefaultsOnly, Category = "Ability Definition")
	int32 InputID = INDEX_NONE;

	**//GE失效或者移除时 赋予的GA如何处理(立即移除/等技能结束后再移除/不做处理)**
	UPROPERTY(EditDefaultsOnly, Category = "Ability Definition")
	EGameplayEffectGrantedAbilityRemovePolicy RemovalPolicy = EGameplayEffectGrantedAbilityRemovePolicy::CancelAbilityImmediately;
};
```

- **赋予GA**

```cpp
void UAbilitiesGameplayEffectComponent::GrantAbilities(...) const
{
	
	const TArray<FGameplayAbilitySpec>& AllAbilities = ASC->GetActivatableAbilities();
	for (const FGameplayAbilitySpecConfig& AbilityConfig : GrantAbilityConfigs)
	{
		
...
		FGameplayAbilitySpec AbilitySpec{ AbilityConfig.Ability, Level, 
		AbilityConfig.InputID, ActiveGESpec.GetEffectContext().GetSourceObject() };
		
		AbilitySpec.SetByCallerTagMagnitudes = ActiveGESpec.SetByCallerTagMagnitudes;
		AbilitySpec.GameplayEffectHandle = ActiveGEHandle;

		ASC->GiveAbility(AbilitySpec);
	...
	}
}

```

- **移除赋予的GA**

> 💡
>
> *根据配置的移除规则在尝试移除赋予的GA有三种操作*
>
> **CancelAbilityImmediately 立即移除
>
> RemoveAbilityOnEnd 等GA执行完了再移除
>
> DoNothing 什么也不干**(只负责赋予不负责移除)

```cpp
void UAbilitiesGameplayEffectComponent::RemoveAbilities(FActiveGameplayEffectHandle ActiveGEHandle) const
{

	for (const FGameplayAbilitySpecConfig& AbilityConfig : GrantAbilityConfigs)
	{
...
		switch (AbilityConfig.RemovalPolicy)
		{
			case EGameplayEffectGrantedAbilityRemovePolicy::CancelAbilityImmediately:
			{
				ASC->ClearAbility(AbilitySpecDef->Handle);
				break;
			}
			case EGameplayEffectGrantedAbilityRemovePolicy::RemoveAbilityOnEnd:
			{
				ASC->SetRemoveAbilityOnEnd(AbilitySpecDef->Handle);
				break;
			}
			default:
			{
				// Do nothing to granted ability
				break;
			}
		}
	...
	}
```

## 赋予GE拥有者额外效果的组件

---

**UAdditionalEffectsGameplayEffectComponent**

- **GE在添加(Apply)成功时赋予拥有者额外的GE**
- **GE在结束时赋予赋予拥有者额外的GE***(不管是以何种方式结束都赋予 )*
- **GE在正常结束时赋予赋予拥有者额外的GE***(持续时间到了而结束的 )*
- **GE在非正常结束时赋予赋予拥有者额外的GE***(持续时间未到就被移除了)*

> 💡 *赋予的GE时可以通过GE的来源Tag进行一次是否赋予的判定* **FConditionalGameplayEffect**

- **GE被添加进激活容器时绑定对移除事件的监听**

```cpp
**//GE 被添加进激活容器时绑定对移除事件的监听**
bool UAdditionalEffectsGameplayEffectComponent::OnActiveGameplayEffectAdded(FActiveGameplayEffectsContainer& ActiveGEContainer, FActiveGameplayEffect& ActiveGE) const
{
	
	if (ActiveGEContainer.IsNetAuthority())
	{
		ActiveGE.EventSet.OnEffectRemoved.AddUObject(this, 
		&UAdditionalEffectsGameplayEffectComponent::OnActiveGameplayEffectRemoved, 
		&ActiveGEContainer);
	}

	return true;
}
```

- **GE在添加(Apply)成功时赋予拥有者额外的GE**

```cpp
**//GE在添加(Apply)成功时赋予拥有者额外的GE**
void UAdditionalEffectsGameplayEffectComponent::OnGameplayEffectApplied(...) const
{

	for (const FConditionalGameplayEffect& ConditionalEffect : OnApplicationGameplayEffects)
	{
		const UGameplayEffect* GameplayEffectDef = ConditionalEffect.EffectClass.
		GetDefaultObject();
		
		if (!GameplayEffectDef)
		{
			continue;
		}

		 **//匹配Tag条件**
		if (ConditionalEffect.CanApply(GESpec.CapturedSourceTags.GetActorTags(), GELevel))
		{
			FGameplayEffectSpecHandle SpecHandle;
			if (bOnApplicationCopyDataFromOriginalSpec)
			{
				//拷贝GE的相关数据用来初始化额外赋予的GE
				SpecHandle = FGameplayEffectSpecHandle(new FGameplayEffectSpec());
				SpecHandle.Data->InitializeFromLinkedSpec(GameplayEffectDef, GESpec);
			}
			else
			{
				//重新创建
				SpecHandle = ConditionalEffect.CreateSpec(GEContextHandle, GELevel);
			}

			if (ensure(SpecHandle.IsValid()))
			{
				TargetEffectSpecs.Add(SpecHandle);
			}
		}
	}

	UAbilitySystemComponent& AppliedToASC = *ActiveGEContainer.Owner;
	for (const FGameplayEffectSpecHandle& TargetSpec : TargetEffectSpecs)
	{
		if (TargetSpec.IsValid())
		{
			AppliedToASC.ApplyGameplayEffectSpecToSelf(*TargetSpec.Data.Get(), PredictionKey);
		}
	}
}
```

- **GE在移除时赋予拥有者额外的GE**

```cpp
**//GE被移除时 需要赋予的额外GE**
void UAdditionalEffectsGameplayEffectComponent::OnActiveGameplayEffectRemoved(...) const
{
	**//是否是时间到了而移除的**
	const TArray<TSubclassOf<UGameplayEffect>>& ExpiryEffects = 
	(RemovalInfo.bPrematureRemoval ? OnCompletePrematurely : OnCompleteNormal)
	
	TArray<TSubclassOf<UGameplayEffect>> AllGameplayEffects{ ExpiryEffects };
	
	**//不管是否是正常移除 都需要赋予的**
	AllGameplayEffects.Append(OnCompleteAlways);

	for (const TSubclassOf<UGameplayEffect>& CurExpiryEffect : AllGameplayEffects)
	{
		if (const UGameplayEffect* CurExpiryCDO = CurExpiryEffect.GetDefaultObject())
		{
			FGameplayEffectSpec NewSpec;
			NewSpec.InitializeFromLinkedSpec(CurExpiryCDO, ActiveGE->Spec);
			ASC->ApplyGameplayEffectSpecToSelf(NewSpec);
		}
	}
}

```

- **赋予GE的Tag限制配置**

```cpp
**//GE被添加时赋予的GE(支持配置Tag条件限制)(FConditionalGameplayEffect)

struct GAMEPLAYABILITIES_API FConditionalGameplayEffect
{
	
	bool CanApply(const FGameplayTagContainer& SourceTags, float SourceLevel) const;
	TSubclassOf<UGameplayEffect> EffectClass;
	FGameplayTagContainer RequiredSourceTags;
};

bool FConditionalGameplayEffect::CanApply(...) const
{
	return SourceTags.HasAll(RequiredSourceTags);
}**
```

## 免疫组件

---

**UImmunityGameplayEffectComponent**

- **配置能免疫哪些符合条件的GE**
- **在配置了免疫组件的GE生效后 符合免疫条件的GE会被拦截无法被添加**

![Untitled](http://pic.xyyxr.cn/20260504111207008.png)

> 💡 在拥有免疫组件的GE成功添加到激活效果容器时 会向UAbilitySystemComponent的**GameplayEffectApplicationQueries**绑定委托
> (该委托用于判定新增GE是否可以被添加)
>
> 移除拥有免疫组件的GE时解除委托绑定

- **在GE添加进激活容器时绑定拦截委托 并在移除时解除拦截委托**

```cpp
bool UImmunityGameplayEffectComponent::OnActiveGameplayEffectAdded(...) const
{
	**//在拥有免疫组件的GE成功添加到激活容器时
	//会向UAbilitySystemComponent的GameplayEffectApplicationQueries绑定委托
	//每个GE添加前都需要执行下GameplayEffectApplicationQueries来决定是否可以添加
	//这样这个组件就可以干涉后续GE添加判定了达到筛选指定GE的目的**
	FGameplayEffectApplicationQuery& BoundQuery = 
	OwnerASC->GameplayEffectApplicationQueries.AddDefaulted_GetRef();
	
	BoundQuery.BindUObject(this, 
	&UImmunityGameplayEffectComponent::AllowGameplayEffectApplication, 
	ActiveGEHandle);

	**//移除时GE时 解除GameplayEffectApplicationQueries委托绑定**
	ActiveGE.EventSet.OnEffectRemoved.AddLambda([OwnerASC, 
	QueryToRemove = BoundQuery.GetHandle()]
	(const FGameplayEffectRemovalInfo& RemovalInfo)
		{
			if (ensure(IsValid(OwnerASC)))
			{
				TArray<FGameplayEffectApplicationQuery>& GEAppQueries =
				 OwnerASC->GameplayEffectApplicationQueries;
				 
				for (auto It = GEAppQueries.CreateIterator(); It; ++It)
				{
					if (It->GetHandle() == QueryToRemove)
					{
						It.RemoveCurrentSwap();
						break;
					}
				}
			}
		});
	return true;
}

FActiveGameplayEffectHandle UAbilitySystemComponent::ApplyGameplayEffectSpecToSelf(...)
{
...
	 **//添加GE 需要执行委托GameplayEffectApplicationQueries进行判定 是否可以添加**
	for (const FGameplayEffectApplicationQuery& ApplicationQuery : 
	**GameplayEffectApplicationQueries**)
	
	{
		const bool bAllowed = ApplicationQuery.Execute(ActiveGameplayEffects, Spec);
		if (!bAllowed)
		{
			return FActiveGameplayEffectHandle();
		}
	}
...
}
```

- **免疫判定**

> 💡 **主要是通过ImmunityQueries匹配筛选符合条件的GE**
>
> ***ImmunityQueries**是一组**FGameplayEffectQuery配置**(专门用来匹配筛选GE)*
>
> *参照*
>
> [GE-8.0匹配查询](GE-8.0%E5%8C%B9%E9%85%8D%E6%9F%A5%E8%AF%A2.md)

```cpp
bool UImmunityGameplayEffectComponent::AllowGameplayEffectApplication(...) const
{
	
	const UAbilitySystemComponent* ASC = ActiveGEContainer.Owner;
	if (ASC != ImmunityActiveGEHandle.GetOwningAbilitySystemComponent())
	{
	return false;
	}

  **//免疫GE被冻结(处于非激活状态)**
	const FActiveGameplayEffect* ActiveGE = 
	ASC->GetActiveGameplayEffect(ImmunityActiveGEHandle);
	
	if (!ActiveGE || ActiveGE->bIsInhibited)
	{
		return true;
	}

	**//进行免疫判定**
	for (const FGameplayEffectQuery& ImmunityQuery : ImmunityQueries)
	{
		**//通过 FGameplayEffectQuery::Matches(const FGameplayEffectSpec& Spec) 进行免疫判定**
		if (!ImmunityQuery.IsEmpty() && ImmunityQuery.Matches(GESpecToConsider))
		{
			ASC->OnImmunityBlockGameplayEffectDelegate.Broadcast(GESpecToConsider, 
			ActiveGE);
			
			return false;
		}
	}
	return true;
}

```

## 驱散组件

---

**URemoveOtherGameplayEffectComponent**

**当GE添加时移除符合条件的GE(驱散)**

- **在GE被成功添加(Apply)时执行驱散操作**

> 💡 **主要是通过RemoveGameplayEffectQueries 匹配筛选符合条件的GE**
>
> **RemoveGameplayEffectQueries**是一组**FGameplayEffectQuery***(专门用来匹配筛选GE )*
>
> 参照
>
> [GE-8.0匹配查询](GE-8.0%E5%8C%B9%E9%85%8D%E6%9F%A5%E8%AF%A2.md)

```cpp
void URemoveOtherGameplayEffectComponent::OnGameplayEffectApplied(...) const
{
	if (!ActiveGEContainer.OwnerIsNetAuthority)
	{
		return;
	}

	FGameplayEffectQuery FindOwnerQuery;
	FindOwnerQuery.EffectDefinition = GetOwner() ? GetOwner()->GetClass() : nullptr;

	**//排除自身**
	TArray<FActiveGameplayEffectHandle> ActiveGEHandles = 
	ActiveGEContainer.GetActiveEffects(FindOwnerQuery);

	constexpr int32 RemoveAllStacks = -1;
	for (const FGameplayEffectQuery& RemoveQuery : RemoveGameplayEffectQueries)
	{
		if (!RemoveQuery.IsEmpty())
		{
			if (ActiveGEHandles.IsEmpty())
			{
				ActiveGEContainer.RemoveActiveEffects(RemoveQuery, RemoveAllStacks);
			}
			else
			{
				FGameplayEffectQuery MutableRemoveQuery = RemoveQuery;
				MutableRemoveQuery.IgnoreHandles = MoveTemp(ActiveGEHandles);

				ActiveGEContainer.RemoveActiveEffects(MutableRemoveQuery, RemoveAllStacks);
			}
		}
	}
}

int32 FActiveGameplayEffectsContainer::RemoveActiveEffects(...)
{
	GAMEPLAYEFFECT_SCOPE_LOCK();
	int32 NumRemoved = 0;

	for (int32 idx = GetNumGameplayEffects() - 1; idx >= 0; --idx)
	{
		const FActiveGameplayEffect& Effect = *GetActiveGameplayEffect(idx);
		if (Effect.IsPendingRemove == false && Query.Matches(Effect))
		{
			InternalRemoveActiveGameplayEffect(idx, StacksToRemove, true);
			++NumRemoved;
		}
	}
	return NumRemoved;
}
```