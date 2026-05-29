[虚幻四Gameplay Ability System入门学习合集_看不见的地平线的博客-CSDN博客](https://blog.csdn.net/m0_38110586/article/details/116212916)

[以虚幻GAS系统为核心的《原子之心》](https://zhuanlan.zhihu.com/p/348780717)

[](https://github.com/BillEliot/GASDocumentation_Chinese/blob/main/README.md#cae-nonstackingge)

[[UnrealOpenDay2020]深入GAS架构设计 | EpicGames 大钊_哔哩哔哩_bilibili](https://www.bilibili.com/video/BV1zD4y1X77M/)

> 💡 **本系列文章基于UE5.3**

# 概述

---

GAS(GameplayAbilitySystem)系统是UE提供的一套完备的，可扩展性强的能力系统。既可以实现传统意义上的技能(Skill)(主动施法技能、被动天赋技能)、BUFF玩法。也可以用于实现使用道具、跳跃、射击开火、开镜、换弹等通用能力(Ability)。

> [!note]- **AbilitySystemComponent**(ASC)
> GAS系统的管理组件，负责管理GAS模块对外接口，管理着**GameplayAbility**(GA)、**AbilityTask**(Task)、**GameplayEffect**(GE)、**GameplayTag**(Tag)、**GameplayCue**(GC)、**AttributeSet**(属性集)。

> [!note]- **GameplayAbility**(GA)
> 用于定义角色可以执行的各种技能和能力(如攻击、施法、跳跃、使用道具、射击等)。**本质上GA是一个或者多个行为(Task)的组合**

> [!note]- **AbilityTask**(Task)
> **封装好的行为节点。**GA通过组合一个或者多个AbilityTask来实现要执行的行为。


> [!note]- **GameplayEffect**(GE)
> **描述一个游戏效果**，**即我们常说的Buff**。例如治疗、伤害、加攻、减速、驱散、免疫等。


> [!note]- **GameplayTag**(Tag)
> **标签**，**用于标记状态和类别。**可以用来表示一个游戏对象的特性、状态、行为等信息。例如，*你可以用"Character.Type.Enemy", "Character.Type.Boss"等标签来描述一个敌人角色,用“Character.State.Jump”，“Character.State.Swimming”表明对象在跳跃或者游泳。*

> [!note]- **GameplayCue**(GC)
> **播放客户端表现。**特效、音效、材质效果、后处理之类的，可以通过DS端发起，广播到客户端，也可以直接在客户单独触发。

> [!note]- **AttributeSet**
> **属性集。**定义角色属性，比如攻击力、防御力、血量等，分为基础值和当前值，一般是通过GE在其基础值的基础上通过各种运算(加减乘除或者自定义运算规则)计算出当前值，GE失效了其修正部分也会被回退。
>
>
> > 💡
> >
> > GA可以触发各种GE、GC、Tag
> >
> > GE可以触发各种GC、Tag。也支持额外赋予目标一些GA，GE

# GAS启用

---

任意Actor都可以通过挂载AbilitySystemComponent(ASC)启用GAS功能。

- 继承下IAbilitySystemInterface并实现GetAbilitySystemComponent，表明这个Actor挂载了ASC组件同时提供获取ASC的接口。
- 在Actor的构造函数里创建ASC组件。
    
```cpp
    class ATestActor : public AActor, public IAbilitySystemInterface
    {
    }
    
    ATestActor ::ATestActor (const FObjectInitializer& ObjectInitializer)
    	: Super(ObjectInitializer)
    {
    
    TestASC = ObjectInitializer.CreateDefaultSubobject<UAbilitySystemComponent>(this, TEXT("TestASC "), false);
    }
    
    class GAMEPLAYABILITIES_API IAbilitySystemInterface
    {
    	GENERATED_IINTERFACE_BODY()
    	virtual UAbilitySystemComponent* GetAbilitySystemComponent() const = 0;
    };
```
    

ASC上主要接口介绍:

- **GiveAbility**是赋予GA的入口(GA要先赋予才能使用)，InternalTryActivateAbility是执行激活GA的接口
- **ApplyGameplayEffectSpecToSelf**是附加GE的接口
- **AddGameplayCue**/**ExecuteGameplayCue**/**RemoveGameplayCue** 是GameplayCue的操作接口
- **UpdateTagMap**是Tag的更新接口

```cpp
class GAMEPLAYABILITIES_API UAbilitySystemComponent : public UGameplayTasksComponent
{
	//可使用的GA列表
	UPROPERTY(ReplicatedUsing = OnRep_ActivateAbilities)
	FGameplayAbilitySpecContainer ActivatableAbilities;
	
	//Task列表(基类UGameplayTasksComponent属性字段)
	UPROPERTY()
	TArray<TObjectPtr<UGameplayTask>> TickingTasks;
	
	//激活的GE列表
	UPROPERTY(Replicated)
	FActiveGameplayEffectsContainer ActiveGameplayEffects;

  //激活的GC列表
	UPROPERTY(Replicated)
	FActiveGameplayCueContainer ActiveGameplayCues;
	
	//拥有的Tag列表
	FGameplayTagCountContainer GameplayTagCountContainer;
	UPROPERTY(Replicated)
	FMinimalReplicationTagCountMap MinimalReplicationTags;
	
	//**AttributeSet**(属性集)
	UPROPERTY(Replicated)
	TArray<TObjectPtr<UAttributeSet>>	SpawnedAttributes;
}
```

# GAS调试

---

GAS提供了两种调试信息的显示方式:

- 直接通过通用HUD的ShowDebugInfo显示调试信息。
- 定制了GAS调试信息专属HUD(**AbilitySystemDebugHUD**)显示调试信息

> 💡
>
> 推荐使用第一种ShowDebugInfo方式显示，UE提供的通用屏幕调试信息输出方。
>
> 不仅可以显示主控角色的信息，还可以通过快捷键PageDown/PageUp(或者直接在控制台输入指令NextDebugTarget/PreviousDebugTarget)切换调试目标，显示选中目标的调试信息。

## 通用HUD显示调试信息

---

![image.png](http://pic.xyyxr.cn/20260504111151778.png)

**控制台指令**

> 💡 **ShowDebug AbilitySystem** 开启/关闭 GAS的调试信息输出
>
> AbilitySystem.Debug.NextCategory 切换GAS调试信息输出类型
>
> 调试信息分为三类:
> Attributes(属性相关)
> Ability(GA相关)
> GameplayEffects(GE相关)
>
> 可以通过AbilitySystem.Debug.NextCategory指令在上述三类中切换显示

**效果展示**

![image.png](http://pic.xyyxr.cn/20260504111153508.png)

![image.png](http://pic.xyyxr.cn/20260504111153510.png)

![image.png](http://pic.xyyxr.cn/20260504111153511.png)

**绘制信息接口**

```cpp
void UAbilitySystemComponent::OnShowDebugInfo(...)
{
	if (DisplayInfo.IsDisplayOn(TEXT("AbilitySystem")))
	{
		UWorld* World = HUD->GetWorld();
		FASCDebugTargetInfo* TargetInfo = GetDebugTargetInfo(World);
	
		UAbilitySystemComponent* ASC = nullptr;

		if (UAbilitySystemGlobals::Get().bUseDebugTargetFromHud)
		{
			ASC = UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(
			HUD->GetCurrentDebugTargetActor());
		}
		else
		{
			ASC = GetDebugTarget(TargetInfo);
		}

		if (ASC)
		{
			...
			ASC->DisplayDebug(Canvas, LocalDisplayInfo, YL, YPos);
		}
	}
}
```

> 💡
>
> OnShowDebugInfo是绘制调试信息的入口，如果想绘制DebugTarget的调试信息需要开启配置**bUseDebugTargetFromHud**，可以自己定制切换调试目标的规则(切换
> FASCDebugTargetInfo的LastDebugTarget，默认是主控端角色)。

![image.png](http://pic.xyyxr.cn/20260504111153512.png)

**Debug_Internal**在屏幕中显示各种GAS相关的调试信息

```cpp
UAbilitySystemComponent::Debug_Internal(FAbilitySystemComponentDebugInfo& Info)
{
...
}
```

> 💡 可以通过重载虚函数UAbilitySystemComponent::Debug_Internal定制显示信息

> 💡
>
> ServerPrintDebug_Request 还可以通过RPC 获取DS端的调试信息 
> 然后在客户端打印显示出来

## 专属HUD显示调试信息

---

**AbilitySystemDebugHUD**是显示GAS系统调试信息的专属HUD。
AbilitySystemDebugHUD::**DrawDebugHUD**是负责绘制调试信息的入口函数。

**显示常用信息**

AbilitySystem.DebugBasicHUD 
打开/关闭显示当前主控角色的GAS一些常用信息的控制台指令

- AbilitySystemComponent信息
- 属性信息
- 激活的GE信息

> 💡 这个显示的信息有点少 而且没预留扩展

绘制信息函数
AbilitySystemDebugHUD::**DrawDebugAbilitySystemComponent**

![image.png](http://pic.xyyxr.cn/20260504111153513.png)

**显示扩展信息**

![image.png](http://pic.xyyxr.cn/20260504111153514.png)

除了上述一些基础信息，还可以通过定制一些继承自类UAbilitySystemDebugHUDExtension的扩展类来定制输出一些调试信息。这些扩展信息的显示方式如图所示，**是可以显示所有视野内的玩家信息并跟随玩家移动**

现有示例有

- UAbilitySystemDebugHUDExtension_Tags(Tag信息相关)
- UAbilitySystemDebugHUDExtension_Attributes(属性信息相关)
- UAbilitySystemDebugHUDExtension_BlockedAbilityTags(技能禁用Tag信息相关)

> 💡 **AbilitySystem.DebugAbilityTags** 
> 打开/关闭显示角色拥有的Tag信息的控制台指令
> *后面可以附加一个或者多个Tag名称(完整名称) 表示只显示指定的Tag信息 不附加则显示所有Tag信息*
>
> 对应绘制函数
> AbilitySystemDebugHUDExtension_Tags::GetDebugStrings

> 💡 **AbilitySystem.DebugAttribute** [AttributeName] [AttributeName]...
> 打开/关闭显示角色属性信息的控制台指令
> *后面需要附加一个多个属性名称
> (比如 AbilitySystem.DebugAttribute Health MaxHealth)*
>
> 对应绘制函数
> AbilitySystemDebugHUDExtension_Tags::GetDebugStrings
>
> **AbilitySystem.ClearDebugAttributes**
> 清除显示角色属性信息的控制台指令
>
> **AbilitySystem.DebugIncludeModifiers**
> 显示GE修改角色属性信息的控制台指令
> *需要先使用指令**AbilitySystem.DebugAttribute***

> 💡 **AbilitySystem.DebugBlockedAbilityTags**
> 显示角色的**BlockedAbilityTags**信息的控制台指令
> *哪些Tag的技能当前被禁用了*
>
> 对应绘制函数
> AbilitySystemDebugHUDExtension_BlockedAbilityTags::GetDebugStrings

**

AbilitySystemDebugHUD::**DrawAbilityDebugInfo**是绘制扩展信息的接口，首先遍历所有的AbilitySystemComponent组件，再遍历所有的扩展类，直接访问CDO实例，获取定制的调试信息(**GetDebugStrings**)然后绘制到屏幕上显示(**DisplayDebugStrings**)

```cpp
void AAbilitySystemDebugHUD::DrawAbilityDebugInfo(...) const
{
	for (TObjectIterator<UAbilitySystemComponent> ASCIt; ASCIt; ++ASCIt)
	{
		if (UAbilitySystemComponent* ASC = *ASCIt)
		{
			if (ASC->GetWorld() == PCWorld)
			{
				const AActor* AvatarActor = ASC->GetAvatarActor();
				
				float VerticalOffset = 0.f;
				for (TObjectIterator<UAbilitySystemDebugHUDExtension> 
				ExtIt(EObjectFlags::RF_NoFlags); ExtIt; ++ExtIt)
				{
					if (ExtIt->IsEnabled())
					{
						TArray<FString> DebugStrings;
						ExtIt->GetDebugStrings(AvatarActor, ASC, DebugStrings);
						DisplayDebugStrings(...);
					}
				}
			}
		}
}
```

## 其他

---

> 💡 通用的忽略技能消耗和CD的控制台指令
>
> AbilitySystem.IgnoreCooldowns 1
> AbilitySystem.IgnoreCosts 1

> 💡 log LogAbilitySystem VeryVerbose
> 修改LogAbilitySystem日志的输出等级 方便查看各个级别的日志信息
>
> 常用日志等级
> Fatal
> Error
> Warning
> Display
> Log
> Verbose
> VeryVerbose