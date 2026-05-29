> 💡 **本系列文章基于UE5.3**

# 概述

---

GA可以绑定一个输入InputID，将这个InputID于输入系统进行绑定后，就可以通过对应按键或者点击按钮使用GA。

UE的输入系统的基本逻辑是:一个输入ActionName绑定一个执行行为Action。然后各种输入(鼠标点击、按键、触屏、按钮)去绑定这个ActionName。添加了中间层ActionName作为代理，而不是直接绑定Action，让输入的绑定更灵活方便，输入系统只需要绑定一个ActionName就能触发对应的Action。

GA绑定输入相应绑定的基本流程如下:

- 首先需要定制一个枚举用于定制GA的InputID值，所有的GA输入绑定都共用这个定制的枚举。
- 将枚举的名称转换成FName作为ActionName注册到输入系统，并绑定相应函数。同时将对应的枚举值作为InputID，如此就将InputID绑定了对应输入。
(*没必要为每个输入枚举都写个响应函数，所以GA输入枚举的所有枚举都是都是绑定同一个输入响应，枚举转换的InputID就是用以识别哪个输入被触发了*)
- 当对应的ActionName触发输入时执行输入响应时会传入ActionName对应的InputID，就可以遍历GA列表，将绑定该InputID的GA都激活

![image.png](http://pic.xyyxr.cn/20260504111151774.png)

  

> 💡 以下内容以旧版的输入系统为示例，目前UE提供了一个增强版的输入系统EnhancedInput，绑定操作有点区别，不过总体相差不大，可以参照旧版的重新实现下绑定操作。

# **定义输入ID枚举**

---

UE提供的一个示例**EGameplayAbilityInputBinds**

```cpp
UENUM(BlueprintType)
namespace EGameplayAbilityInputBinds
{
	enum Type : int
	{
		Ability1				UMETA(DisplayName = "Ability1 (LMB)"),
		Ability2				UMETA(DisplayName = "Ability2 (RMB)"),
		Ability3				UMETA(DisplayName = "Ability3 (Q)"),
		Ability4				UMETA(DisplayName = "Ability4 (E)"),
		Ability5				UMETA(DisplayName = "Ability5 (R)"),
		Ability6				UMETA(DisplayName = "Ability6 (Shift)"),
		Ability7				UMETA(DisplayName = "Ability7 (Space)"),
		Ability8				UMETA(DisplayName = "Ability8 (B)"),
		Ability9				UMETA(DisplayName = "Ability9 (T)"),
	};
}
```

# **绑定输入ID枚举**

---

将枚举值转换成ActionName，并绑定技能执行输入的统一接口UAbilitySystemComponent::AbilityLocalInputPressed

UAbilitySystemComponent::AbilityLocalInputReleased

```cpp
void ATestCharacter::SetupPlayerInputComponent(..)
{
	FTopLevelAssetPath EnumPathName = FTopLevelAssetPath(
	StaticEnum<EGameplayAbilityInputBinds>());
	
	ASC->BindAbilityActivationToInputComponent(PlayerInputComponent, 
	FGameplayAbilityInputBinds(
	"AbilityInputConfirm", 
	"AbilityInputCancel", 
	 EnumPathName))
}
```

BindToInputComponent/BindAbilityActivationToInputComponent是UE提供的注册输入绑定的接口，可以根据需求重载这个接口，注册绑定规则

```cpp
void UAbilitySystemComponent::BindAbilityActivationToInputComponent(...)
{
	UEnum* EnumBinds = BindInfo.GetBindEnum();

	SetBlockAbilityBindingsArray(BindInfo);

	//遍历枚举 绑定AbilityLocalInputPressed/AbilityLocalInputReleased
	for(int32 idx=0; idx < EnumBinds->NumEnums(); ++idx)
	{
		const FString FullStr = EnumBinds->GetNameStringByIndex(idx);
		
		// 按下事件
		{
			FInputActionBinding AB(FName(*FullStr), IE_Pressed);
			AB.ActionDelegate.GetDelegateForManualSet().BindUObject(this, 
			&UAbilitySystemComponent::AbilityLocalInputPressed, idx);
			InputComponent->AddActionBinding(AB);
		}

		// 松开事件
		{
			FInputActionBinding AB(FName(*FullStr), IE_Released);
			AB.ActionDelegate.GetDelegateForManualSet().BindUObject(this, 
			&UAbilitySystemComponent::AbilityLocalInputReleased, idx);
			InputComponent->AddActionBinding(AB);
		}
	}
}

```

# **执行输入**

---

当输入系统接收到对应的ActionName的按下和松开事件，会将ActionName在枚举中对应的枚举值作为InputID传入AbilityLocalInputPressed和AbilityLocalInputReleased。就可以与GA绑定的Input进行匹配，执行激活操作。

> 💡 按下操作优先尝试激活GA，如果GA已经被激活后再接受到按下操作则会通知GA有对应输入被按下，看是否需要处理。
> *(比如二段攻击技能，在激活后再次点击触发二段效果)*

```cpp
void UAbilitySystemComponent::AbilityLocalInputPressed(int32 InputID)
{
	...
	ABILITYLIST_SCOPE_LOCK();
	for (FGameplayAbilitySpec& Spec : ActivatableAbilities.Items)
	{
		if (Spec.InputID == InputID)
		{
			if (Spec.Ability)
			{
				Spec.InputPressed = true;
				if (Spec.IsActive())
				{
					if (Spec.Ability->bReplicateInputDirectly && 
					IsOwnerActorAuthoritative() == false)
					{
						ServerSetInputPressed(Spec.Handle);
					}

					AbilitySpecInputPressed(Spec);
					InvokeReplicatedEvent(EAbilityGenericReplicatedEvent::InputPressed, 
					Spec.Handle, Spec.ActivationInfo.GetActivationPredictionKey());					
				}
				else
				{
					TryActivateAbility(Spec.Handle);
				}
			}
		}
	}
}

```

> 💡 松开操作就直接通知GA 对应的输入被松开

```cpp
void UAbilitySystemComponent::AbilityLocalInputReleased(int32 InputID)
{
	ABILITYLIST_SCOPE_LOCK();
	for (FGameplayAbilitySpec& Spec : ActivatableAbilities.Items)
	{
		if (Spec.InputID == InputID)
		{
			Spec.InputPressed = false;
			if (Spec.Ability && Spec.IsActive())
			{
				if (Spec.Ability->bReplicateInputDirectly &&
				IsOwnerActorAuthoritative() == false)
				{
					ServerSetInputReleased(Spec.Handle);
				}

				AbilitySpecInputReleased(Spec);
				
				InvokeReplicatedEvent(EAbilityGenericReplicatedEvent::InputReleased, 
				Spec.Handle, 
				Spec.ActivationInfo.GetActivationPredictionKey());
			}
		}
	}
}
```

> 💡 UE提供了两个Task便于GA监听绑定输入的按下松开UAbilityTask_WaitInputPress/UAbilityTask_WaitInputRelease

# **通用的确认&取消操作**

---

除了通过枚举绑定GA专属输入之外，还支持配置两个通用的输入操作：
通用确认/取消操作。所有GA都可以按需监听这两个操作的输入。

通用确认/取消输入响应的接口分别是
UAbilitySystemComponent::**LocalInputConfirm**
UAbilitySystemComponent::**LocalInputCancel**

> 💡 比如投掷手雷的GA，在激活之后还需要选定目标，确认目标之后再释放，也可以取消操作。这时候就可以定制一个技能通用的确认输入、一个通用的取消输入。在手雷的GA监听这两个输入。

```cpp
void UAbilitySystemComponent::BindToInputComponent(UInputComponent* InputComponent)
{
	static const FName ConfirmBindName(TEXT("AbilityConfirm"));
	static const FName CancelBindName(TEXT("AbilityCancel"));

	// Pressed event
	{
		FInputActionBinding AB(ConfirmBindName, IE_Pressed);
		AB.ActionDelegate.GetDelegateForManualSet().BindUObject(this, 
		&UAbilitySystemComponent::LocalInputConfirm);
		
		InputComponent->AddActionBinding(AB);
	}

	// 
	{
		FInputActionBinding AB(CancelBindName, IE_Pressed);
		AB.ActionDelegate.GetDelegateForManualSet().BindUObject(this, 
		&UAbilitySystemComponent::LocalInputCancel);
		
		InputComponent->AddActionBinding(AB);
	}
}
```

> 💡 UE提供了两个Task便于GA监听通用的确认与取消输入
> **UAbilityTask_WaitConfirm**/**UAbilityTask_WaitCancel**

通用的确认/取消操作除了上面BindToInputComponent里实现的绑定方式，还可以直接在BindAbilityActivationToInputComponent实现，跟GA输入枚举一起处理而不是BindToInputComponent实现的跟GA输入枚举分别处理。

1. 一种方式是在GA输入绑定的枚举中同时定义确认和取消的枚举，再在构建FGameplayAbilityInputBinds时指定哪两个枚举值对应确认和取消。
    
> 💡 在GA输入绑定的枚举中同时定义确认和取消的枚举，则对应的ActionName被触发时同样会调用AbilityLocalInputPressed。这里判定InputID是ConfirmTargetInputID或者CancelTargetInputID，则转发到LocalInputConfirm/LocalInputCancel
    
```cpp
    void UAbilitySystemComponent::BindAbilityActivationToInputComponent(...)
    {
    ....
    	if (BindInfo.CancelTargetInputID >= 0)
    	{
    		GenericCancelInputID = BindInfo.CancelTargetInputID;
    	}
    	if (BindInfo.ConfirmTargetInputID >= 0)
    	{
    		GenericConfirmInputID = BindInfo.ConfirmTargetInputID;
    	}
    ....
    }
    
    void UAbilitySystemComponent::AbilityLocalInputPressed(int32 InputID)
    {
    	if (IsGenericConfirmInputBound(InputID))
    	{
    		LocalInputConfirm();
    		return;
    	}
    	if (IsGenericCancelInputBound(InputID))
    	{
    		LocalInputCancel();
    		return;
    	}
    }
```
    
2. 还有一种方式是在枚举中不定义确认和取消枚举，直接在构建FGameplayAbilityInputBinds时指定确认和取消的ActionName
    
```cpp
    void UAbilitySystemComponent::BindAbilityActivationToInputComponent(...)
    {
    ....
    	if (BindInfo.ConfirmTargetCommand.IsEmpty() == false)
    	{
    		FInputActionBinding AB(FName(*BindInfo.ConfirmTargetCommand), IE_Pressed);
    		AB.ActionDelegate.GetDelegateForManualSet().BindUObject(this, 
    		&UAbilitySystemComponent::LocalInputConfirm);
    		InputComponent->AddActionBinding(AB);
    	}
    	
    	if (BindInfo.CancelTargetCommand.IsEmpty() == false)
    	{
    		FInputActionBinding AB(FName(*BindInfo.CancelTargetCommand), IE_Pressed);
    		AB.ActionDelegate.GetDelegateForManualSet().BindUObject(this,
    		 &UAbilitySystemComponent::LocalInputCancel);
    		InputComponent->AddActionBinding(AB);
    	}
    ....
    }
```