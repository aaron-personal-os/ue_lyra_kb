> 💡 **本系列文章基于UE5.3**

# 概述

---

**GameplayEffect(**后面统一简称GE**)**用于描述一个游戏效果,即我们常说的**Buff/Debuff**。例如治疗、伤害、加攻、减速、驱散、免疫等。

UE通过GE模块提供了一个较为完备的、可扩展性强的解决方案用于实现游戏Buff相关的需求。

- 首先需要提供一个静态的**效果配置模板**(**UGameplayEffect**)。 使用时应该先创建一个继承自UGameplayeEffect或者其子类的蓝图来根据需求配置。该配置模板在运行时**只读不可更改**。直接使用UGameplayeEffect的CDO(ClassDefaultObject)。

- 运行时会创建一个**运行时的效果实例(FGameplayEffectSpec的实例)**，该实例包含配置类(**UGameplayeEffect**)的只读实例及其他运行时产生的数据。

> [!note]- 根据效果的时效性分为**持续效果**(*有持续时间 包括永久效果*)和**即时效果(***一次性的***)**。
> **持续效果在其生命周期内可以被重复激活(效果生效)或者抑制(Inhibited 效果存在但不生效)。在其生命周期结束时会被移除，其赋予的效果也跟随取消**。在添加成功后会加入效果管理容器(**FActiveGameplayEffectsContainer**)集中管理
>
> **即时效果是一次性的，在添加成功后立即赋予效果，然后就完成其使命**。与前者相比不存在一个持续的生命周期和取消赋予效果的能力，也不需要添加进效果管理容器。
>
> > 💡 持续效果中有一种定时触发效果，支持在指定的时间间隔(周期)内重复赋予相应的效果。实际就是在其生命周期内重复执行对应的即时效果。(最终执行赋予效果的接口都是同一个FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom)


- 根据效果的具体作用分为**属性修正、扩展效果

属性修正效果是指通过GE的属性修正配置直接修正角色属性数值(攻击、防御、当前血量)的效果**。持续效果和即时效果都支持配置属性修正。区别在于持续效果修正的属性在效果激活时赋予对应的数值修正，在效果失效时会取消其产生影响的那部分数值(修正可回退)。而**即时效果的修正则是永久性的不可逆的**。(*一般用于修正当前血量之类的即时属性或者某些特殊需求需要永久性修改某一属性数值*)。
    
    ![Untitled](http://pic.xyyxr.cn/20260504111159671.png)
    
    **扩展效果用是指除属性修正之外的其他千奇百怪的效果。**一般来说有两种扩展方式:
    
    **一种是通过配置效果自定义执行类(UGameplayEffectExecutionCalculation)。**重载基类的执行接口(**Execute**)，在里面可以定制你需要的各种千奇百怪的效果。
    
> 💡 此类效果直接配置的是一个基类为UGameplayEffectExecutionCalculation的UClass，在运行时使用的也是配置的UClass的CDO(ClassDefaultObject)。所以里面是无法存放运行时产生的数据的。跟UGameplayeEffect一样只是一个只读的配置模板。
>
>     **此类效果只支持即时效果或者持续的定时触发效果配置**(定时触发效果实际也是定时触发一个即时效果)。因为效果自定义执行类的执行接口(Execute)只会在触发即时效果调用(
>     参照FActiveGameplayEffectsContainer::ExecuteActiveEffectsFrom)。
>
>     UE把效果自定义执行类(UGameplayEffectExecutionCalculation)定义为对即时效果的一种扩展。
    
    ![Untitled](http://pic.xyyxr.cn/20260504111159672.png)
    
    **另一种是通过配置GE组件实现**。诸如免疫光环、驱散光环、状态标记之类的效果 *。*GE组件的基类是UGameplayEffectComponent，用于对效果配置模板(UGameplayEffect)配置的一个灵活扩展。其基本思路是在效果准备对目标进行赋予(CanGameplayEffectApply)、赋予成功(OnGameplayEffectApplied)、添加进效果容器(OnActiveGameplayEffectAdded)、执行即时效果(OnGameplayEffectExecuted)等**GE各个关键节点通知GE组件，回调对应的函数，给关键节点定制化需求预留了口子。**可以根据需求重载对应的回调函数自定义的GE组件中对效果进行扩展**。持续性效果、即时效果都可以通过GE组件的方式进行扩展**(*详细见后面有关GE组件的介绍*)。
    
    ![Untitled](http://pic.xyyxr.cn/20260504111159673.png)
    
```cpp
    class GAMEPLAYABILITIES_API UGameplayEffectComponent : public UObject
    {
    	virtual bool CanGameplayEffectApply(...) const { return true; }
    	virtual void OnGameplayEffectApplied(...) const {}
    	virtual bool OnActiveGameplayEffectAdded(...) const { return true; }
    	virtual void OnGameplayEffectExecuted(...) const {}
    }
```
    

# 配置字段说明

---

GE配置需要**创建一个继承UGameplayEffect或者其子类的蓝图**。根据需求在创建的蓝图中配置GE的各项数据。

![Untitled](http://pic.xyyxr.cn/20260504111159674.png)

## **GEComponents**

---

**TArray<TObjectPtr<UGameplayEffectComponent>>** **GEComponents**

**配置继承自UGameplayEffectComponent的GE组件**

5.3新增特性，GE执行流程各个节点会回调GE组件对应的接口，可以根据需求在这些回调函数中定制一些逻辑。

> 💡
>
> *比如免疫组件(UImmunityGameplayEffectComponent) 重载了OnActiveGameplayEffectAdded接口。在配有该组件的效果成功添加到激活容器后调用OnActiveGameplayEffectAdded绑定了拦截GE效果的委托。
>
> 如果有匹配的GE尝试添加且拥有该组件的效果处于激活(生效)状态,则会触发绑定的委托执行拦截。从而达到免疫指定效果的目的*

> 💡 *在5.3之前GE的配置项有点繁杂，在5.3版本增加**GameplayEffectComponent**特性之后，将大部分非必要配置封装成对应的GE组件，按需添加。隐藏非必要字段，减少了GE配置的复杂度。*

## **DurationPolicy**

---

**EGameplayEffectDurationType DurationPolicy**

**持续时间的策略** 

即时(Instant 无持续时长) 

永久(Infinite)

指定持续时长(HasDuration)

## **DurationMagnitude**

---

**FGameplayEffectModifierMagnitude DurationMagnitude**

**配置持续时长**

提供多种方式计算出持续时长 *参照 [](https://www.notion.so/89ebb41a4c23403cba2604af206dcafa?pvs=21)[修正值配置](https://www.notion.so/29456c71ec3e4ac88cab17082f42661f?pvs=21)* 

## **Period**

---

**FScalableFloat Period**

**周期(定时触发)间隔**

FScalableFloat类型可以 直接指定一个固定值或者通过CurveTable跟GE等级进行绑定映射

## **bExecutePeriodicEffectOnApplication**

---

**bool bExecutePeriodicEffectOnApplication**

**是否在首次生效时就触发定时效果**

为True则周期(定时触发)效果在GE生效和每次间隔到了会触发效果  

为False只在每次间隔到了才会触发操作

## **PeriodicInhibitionPolicy**

---

**EGameplayEffectPeriodInhibitionRemovedPolicy PeriodicInhibitionPolicy**

**GE暂时失效后重新激活时Period的重置策略**

> 💡 **NeverReset**  维持之前定时触发节奏不变(*GE处于非激活状态 计时器依然在生效 只是时间到了 不会触发效果*)
>
> **ResetPeriod**  重新开始计时(之前的定时触发计时重置)
>
> **ExecuteAndResetPeriod** 重新激活后 先立即触发一次 再重新开始计时

> 💡 GE支持通过Tag使GE暂时失效**Inhibition** 仍然在激活容器里但不起作用 有效时间内可以被重新激活生效

> 💡 ExecuteAndResetPeriod和bExecutePeriodicEffectOnApplication 效果存在重叠，不要同时配置。  如果两个都配置了的话首次激活GE时会执行两次(因为首次激活和解除暂时失效的激活是走同一个接口，而在首次激活流程里还有bExecutePeriodicEffectOnApplication设置的触发)

## **Modifiers**

---

**TArray<FGameplayModifierInfo> Modifiers**

**GE修改属性的配置列表**

配置每个属性该如何修正，修正多少

*具体参照 [](https://www.notion.so/89ebb41a4c23403cba2604af206dcafa?pvs=21)[](GE-3.0%E6%95%B0%E5%80%BC%E4%BF%AE%E6%AD%A3.md)* 

## **Executions**

---

**TArray<FGameplayEffectExecutionDefinition> Executions**

**GE自定义执行类配置列表**

*具体参照[自定义**效果**执行类修正配置 ](GE-3.0%E6%95%B0%E5%80%BC%E4%BF%AE%E6%AD%A3.md)* 

## **StackingType**

---

**EGameplayEffectStackingType StackingType**

**叠加规则配置**

None 不支持叠加 每次都创建一个新的GE实例
AggregateBySource   按GE的来源叠加(GE相同且触发的技能组件相同会触发叠加)
AggregateByTarget   按GE的目标叠加(目标身上有相同的GE会触发叠加)

## **StackLimitCount**

---

**int32 StackLimitCount**

**叠加数限制**

最多可以叠加多少层

## **OverflowEffects**

---

**TArray<TSubclassOf<UGameplayEffect>> OverflowEffects** 

**GE的叠加数溢出时赋予额外GE效果**

超过最大叠加数时会给GE的拥有者赋予额外的效果

## **bDenyOverflowApplication**

---

**bool bDenyOverflowApplication** 

**GE叠加数已经达到最大时 新增的GE是否直接忽略**
True  则在叠加数达到最大后新增的GE 直接返回忽略后续操作(会触发上面的**OverflowEffects** )
False 则新增的GE还可以触发后续持续时间刷新之类的操作

## bClearStackOnOverflow

---

**bool bClearStackOnOverflow**

**GE达到最大叠加数后再叠加 是否直接移除GE效果**
前提条件bDenyOverflowApplication为False

## **StackDurationRefreshPolicy**

---

**EGameplayEffectStackingDurationPolicy StackDurationRefreshPolicy**

**触发叠加时对持续时间的影响策略**

RefreshOnSuccessfulApplication  重置持续时间
NeverReset 不做任何操作

## **StackPeriodResetPolicy**

---

**EGameplayEffectStackingPeriodPolicy StackPeriodResetPolicy**

**触发叠加时对定时触发时间的影响策略**

ResetPeriod 重置持续时间(计时器重新计时)
ExecuteAndResetPeriod 重置持续时间并当即触发一次效果
NeverReset 不做任何操作

## **StackExpirationPolicy**

---

**EGameplayEffectStackingExpirationPolicy StackExpirationPolicy**

**GE的持续时间到了(过期)以后 叠加的GE处理策略**

ClearEntireStack 直接将GE移除
RemoveSingleStackAndRefreshDuration GE 叠加数-1 并重置持续时间(如果叠加数超过1)
RefreshDuration 只是重置持续时间 不操作叠加数(本质上是持续时间无限 可以在其他地方操作叠加数的变化)

> 💡 *堆叠相关的具体实现参照**[**堆叠处理**](https://www.notion.so/e80480bd149b4acb825185ce8555522f?pvs=21)***

## **bRequireModifierSuccessToTriggerCues**

---

**bool bRequireModifierSuccessToTriggerCues** 

**是否需要属性修正或者自定义效果成功执行了才触发GameplayeCue**

对定时触发或者即时效果生效

## **bSuppressStackingCues**

---

**bool bSuppressStackingCues**  

**是否只在第一次添加GE时触发GameplayeCue**

后续叠加不再触发

## **GameplayCues**

---

T**Array<FGameplayEffectCue>  GameplayCues**

客户端表现效果(播放特效、音效、材质效果之类的 可以在GameplayCue的蓝图里按需实现)