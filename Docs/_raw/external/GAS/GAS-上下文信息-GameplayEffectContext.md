> 💡 **本系列文章基于UE5.3**

# 概述

---

**FGameplayEffectContext**是GAS体系中用于传递**上下文信息**的结构，提供必要的上下文和附加数据支持。**主要用于GameplayAbility(GA)、GameplayEffect(GE)、GameplayCue(GC)的上下文信息传递**

FGameplayEffectContextHandle封装**FGameplayEffectContext**共享指针，通过Handle可以直接获取和操作FGameplayEffectContext实例

```cpp
struct GAMEPLAYABILITIES_API FGameplayEffectContextHandle
{
	TSharedPtr<FGameplayEffectContext> Data;
}
```

FGameplayEffectContextHandle在绝大多数情况下替代FGameplayEffectContext作为参数传递或者变量存放， 因为内部包含的是实例的共享指针而且支持网络复制。内部封装FGameplayEffectContext共享指针，自然可以存放子类实例。**可以通过创建FGameplayEffectContext的子类来扩展上下文信息，附加额外的信息。**

一般用法是在触发时创建上下文信息FGameplayEffectContext，在整个执行过程中可以通过FGameplayEffectContextHandle填充、修改、传递上下文信息。而GA、GE之间可以互相触发，GA和GE都可以触发GC，**所以上下文信息也可以通过FGameplayEffectContextHandle在GA、GE、GC之间传承下去**

- GameplayAbility(GA)通过**FGameplayEffectContext**传递上下文信息:
    
```cpp
    struct GAMEPLAYABILITIES_API FGameplayEventData
    {
    ...
    	FGameplayEffectContextHandle ContextHandle;
    ...
    }
    
    class GAMEPLAYABILITIES_API UGameplayAbility 
    {
    ...
    	FGameplayEventData CurrentEventData;
    ...
    }
```
    
> 💡 FGameplayEventData是GA在尝试激活可以传入的参数信息，激活成功后在GA的实例中保存了一份FGameplayEventData的数据。
>
>     FGameplayEventData包含了上下文信息FGameplayEffectContextHandle
    

- GameplayEffect(GE)通过**FGameplayEffectContext**传递上下文信息:
    
```cpp
    struct GAMEPLAYABILITIES_API FGameplayEffectSpec
    {
    ...
    	FGameplayEffectContextHandle EffectContext;
    ...
    }
```
    
> 💡 GameplayEffect(GE)的运行时数据中FGameplayEffectSpec直接保存了一份 FGameplayEffectContextHandle
    
- GameplayCue(GC)通过**FGameplayEffectContext**传递上下文信息:
    
```cpp
    virtual void InvokeGameplayCueExecuted(...
    FGameplayEffectContextHandle EffectContext);
    
    struct GAMEPLAYABILITIES_API FGameplayCueParameters
    {
    	UPROPERTY(BlueprintReadWrite, Category=GameplayCue)
    	FGameplayEffectContextHandle EffectContext;
    }
```
    
> 💡 在GameplayCue(GC)处理接口都附带了FGameplayEffectContextHandle 数据
>
>     有的是附带FGameplayCueParameters数据也包含了FGameplayEffectContextHandle
    

# Handle的用法解析

---

UE由很多XXXHandle的Struct，Handle一般称为句柄，本质上是可以通过其直接索引到关联的对象实例。

有些Handle只是简单的分配了一个全局唯一编号，分配后保存到关联的实例中。然后通过持有一个的编号去容器中查找匹配对应的实例。比如FGameplayAbilitySpecHandle

```cpp
struct FGameplayAbilitySpecHandle
{

private:
	UPROPERTY()
	int32 Handle;
}

void FGameplayAbilitySpecHandle::GenerateNewHandle()
{
	static int32 GHandle = 1;
	Handle = GHandle++;
}

```

有些Handle是包含一个实例的共享指针。这种Handle直接持有了实例的指针，可以直接访问关联的实例并且可以封装一些操作实例的接口。而且因为持有的是指针，自然也可以指向子类实例。**适用于那些需要在Handle关联的对象会因为定制化需求出现各种子类实例的情况。**

比如FGameplayEffectContextHandle通过Handle可以直接获取和操作其内部封装的实例，包括继承自FGameplayEffectContext子类实例。

```cpp
struct GAMEPLAYABILITIES_API FGameplayEffectContextHandle
{
	TSharedPtr<FGameplayEffectContext> Data;
}
```

此类Handle实例用于参数传递和其他数据结构中的变量，**具有多态特性**。(*实际上就是相当于一个基类指针，将子类实例赋给基类指针传递，使用时再转换成子类实例*)

> 💡 比如以下示例中FLyraGameplayEffectContext是继承自FGameplayEffectContext的子类，通过传入的FGameplayEffectContextHandle，判定其内部是否封装的是子类FLyraGameplayEffectContext的实例，是的话直接从中提取出子类实例。

```cpp
FLyraGameplayEffectContext* FLyraGameplayEffectContext::ExtractEffectContext(...)
{
	FGameplayEffectContext* BaseEffectContext = Handle.Get();
	if ((BaseEffectContext != nullptr) && 
	BaseEffectContext->GetScriptStruct()->IsChildOf(FLyraGameplayEffectContext::StaticStruct()))
	{
	//类型判定通过 直接强转
		return (FLyraGameplayEffectContext*)BaseEffectContext;
	}
	return nullptr;
}
```

继承自FGameplayEffectContext的子类需要重载虚函数GetScriptStruct。这样可以基类指针通过调用GetScriptStruct获取实际类型信息。

```cpp
struct GAMEPLAYABILITIES_API FGameplayEffectContext
{
	virtual UScriptStruct* GetScriptStruct() const
	{
		return FGameplayEffectContext::StaticStruct();
	}
}

struct FLyraGameplayEffectContext : public FGameplayEffectContext
{
	virtual UScriptStruct* GetScriptStruct() const override
	{
		return FLyraGameplayEffectContext::StaticStruct();
	}
}
```

上述示例中的模板化版本

```cpp
template<typename T>
T* ExtractEffectContext(struct FGameplayEffectContextHandle Handle)
{
	FGameplayEffectContext* BaseEffectContext = Handle.Get();
	if ((BaseEffectContext != nullptr) && 
	BaseEffectContext->GetScriptStruct()->IsChildOf(T::StaticStruct()))
	{
		return (T*)BaseEffectContext;
	}

	return nullptr;
}
```

# 如何网络复制一个F类指针

---

为什么FGameplayEffectContext要封装成一个Handle结构而不是直接使用基类指针呢。因为涉及到了网络复制，F类(结构体或者不继承自UObject的原生类)是无法通过指针进行网络复制的，所以将其封装成一个Handle结构体，再通过实现Handle结构体的自定义网络序列化NetSerialize来达到网络复制的目的。

```cpp

template<>
struct TStructOpsTypeTraits<FGameplayEffectContextHandle> :
public TStructOpsTypeTraitsBase2<FGameplayEffectContextHandle>
{
	enum
	{
		WithCopy = true,
		WithNetSerializer = true,
		WithIdenticalViaEquality = true,
	};
};

```

> 💡 在UE中，Struct类型元数据UScriptStruct 提供了一种机制可以自定义结构体的一些特性。 
>
> UScriptStruct 有一个功能强大的接口 ICppStructOps，可以用来制定结构体在底层 C++ 代码中的操作。这些操作包括构造、析构、拷贝和序列化等。
>
> 也就是可以通过类似上述模板特化的代码，表明指定的结构体实现了自定义的构造、析构、复制和序列化。当执行此类操作时，会自动调用对应的自定义接口执行自定义行为。

```cpp
//如果Struct实现自定义网络序列化NetSerialize会通过ICppStructOps调用
//Struct实现的自定义网络序列化NetSerialize进行网络序列化操作
if (EnumHasAnyFlags(CachedRequestState.Struct->StructFlags, 
STRUCT_NetSerializeNative))
	{
		UScriptStruct::ICppStructOps* CppStructOps = 
		CachedRequestState.Struct->GetCppStructOps();
		
		check(CppStructOps);
		bool bSuccess = true;

		if (!CppStructOps->NetSerialize(Ar, Params.Map, bSuccess, Params.Data))
		{
			Params.bOutHasMoreUnmapped = true;
		}
	}
	
	
	template<class CPPSTRUCT>
	struct TCppStructOps final : public ICppStructOps
	{
			virtual bool NetSerialize(FArchive& Ar, class UPackageMap* Map, 
		bool& bOutSuccess, void *Data) override
			{
				if constexpr (TStructOpsTypeTraits<CPPSTRUCT>::WithNetSerializer)
				{
					return ((CPPSTRUCT*)Data)->NetSerialize(Ar, Map, bOutSuccess);
				}
				else
				{
					return false;
				}
			}
		
	}
```

**WithNetSerializer** = true表示定制了网络序列化。因为F类指针是无法直接网络复制的，网络序列化时会调用FGameplayEffectContextHandle实现的NetSerialize进行序列化和反序列化。

**WithCopy** = true启用了WithCopy结构体会使用 Unreal 的内置机制来确保在复制时正确处理复杂对象和智能指针，自动生成拷贝构造函数和赋值运算符(FGameplayEffectContext有一个共享指针，启用WithCopy能保证共享指针的在结构体复制时能正确进行引用计数)
*不启用WithCopy时，结构体可能会缺乏合适的拷贝支持，尤其在涉及复杂类型时，可能会导致未定义的内存访问，特别是如果没有手动实现拷贝构造函数和赋值运算符。*

**WithIdenticalViaEquality** = true表示在通过Identical判定结构体是否发生修改时是通过==操作符进行判定
*(网络复制时，会通过Identical接口判定结构体数据是否修改过)
(FGameplayEffectContextHandle重载了==操作符)*

```cpp
bool operator==(FGameplayEffectContextHandle const& Other) const
{
	if (Data.IsValid() != Other.Data.IsValid())
	{
		return false;
	}
	if (Data.Get() != Other.Data.Get())
	{
		return false;
	}
	return true;
}
```

FGameplayEffectContextHandle重载的==操作符表明只要Handle持有的指针未发生变化就视为FGameplayEffectContextHandle未发生修改，所以如果需要修改FGameplayEffectContext实例的内容且在修改完之后需要认为FGameplayEffectContextHandle发生了改变，或者需要创建一份新的Handle实例副本通过Duplicate执行深拷贝操作。

```cpp
FGameplayEffectContextHandle Duplicate() const
{
	if (IsValid())
	{
		FGameplayEffectContext* NewContext = Data->Duplicate();
		return FGameplayEffectContextHandle(NewContext);
	}
	else
	{
		return FGameplayEffectContextHandle();
	}
}

virtual FGameplayEffectContext* Duplicate() const
{
	FGameplayEffectContext* NewContext = new FGameplayEffectContext();
	*NewContext = *this;
	if (GetHitResult())
	{
		// Does a deep copy of the hit result
		NewContext->AddHitResult(*GetHitResult(), true);
	}
	return NewContext;
}
```

有了上述基础之后，回归正题，要想将一个F类的实例指针进行网络序列化，需要**在接收端重新new 一个对应的结构体实例**，然后再**将通过网络传输的序列化的数据反序列化填充到新创建的实例中**。

创建新的实例需要知道实例的类型(因为有可能是子类类型)。所以需要在传输的数据中附带实例类型，但是不可能直接将类型的元数据UScriptStruct直接带过去。UE提供了一个全局的UAbilitySystemGlobals::Get().EffectContextStructCache会收集所有FGameplayEffectContext及其子类的类型信息，放入一个数组中(存放的是类型信息UScriptStruct指针)。客户端和DS端都执行相同的逻辑。这样在传输的数据中附带实例类型只需要附带EffectContextStructCache中的数组索引即可，只需要1个字节(uint8)即可在客户端还原类型信息。

收集FGameplayEffectContext及其子类的类型信息

> 💡 这里还有一个TargetDataStructCache对应的是FGameplayAbilityTargetData,跟FGameplayEffectContext是有同样的机制,同样也有个对应的FGameplayAbilityTargetDataHandle。

```cpp
void UAbilitySystemGlobals::InitTargetDataScriptStructCache()
{
 TargetDataStructCache.InitForType(FGameplayAbilityTargetData::StaticStruct());
	EffectContextStructCache.InitForType(FGameplayEffectContext::StaticStruct());
}

void FNetSerializeScriptStructCache::InitForType(UScriptStruct* InScriptStruct)
{
	ScriptStructs.Reset();
	for (TObjectIterator<UScriptStruct> It; It; ++It)
	{
		if (It->IsChildOf(InScriptStruct))
		{
			ScriptStructs.Add(*It);
		}
	}
	
	//按名字排序
	ScriptStructs.Sort([](const UScriptStruct& A, const UScriptStruct& B) { 
	return A.GetName().ToLower() > B.GetName().ToLower(); });
}
```

网络序列化时，只需要找到类型的数组索引进行序列化即可

```cpp
bool FNetSerializeScriptStructCache::NetSerialize(FArchive& Ar, UScriptStruct*& Struct)
{
	if (Ar.IsSaving())
	{
		int32 idx;
		if (ScriptStructs.Find(Struct, idx))
		{
			check(idx < (1 << 8));
			uint8 b = idx;
			Ar.SerializeBits(&b, 8);
			return true;
		}
		return false;
	}
	else
	{
		uint8 b = 0;
		Ar.SerializeBits(&b, 8);
		if (ScriptStructs.IsValidIndex(b))
		{
			Struct = ScriptStructs[b];
			return true;
		}
		return false;
	}
}
```

FGameplayEffectContextHandle的网络复制序列化

```cpp
bool FGameplayEffectContextHandle::NetSerialize(...)
{
	//标记封装的实例是否是有效的 无效就是默认值了 不用处理
	bool ValidData = Data.IsValid();
	Ar.SerializeBits(&ValidData,1);

	if (ValidData)
	{
		TCheckedObjPtr<UScriptStruct> ScriptStruct = Data.IsValid() ?
		Data->GetScriptStruct() : nullptr;
		
//序列化FGameplayEffectContext类型信息 
//本质就是查找类型在全局数组EffectContextStructCache的索引进行序列化即可
		UAbilitySystemGlobals::Get().EffectContextStructCache.
		NetSerialize(Ar, ScriptStruct.Get());

		if (ScriptStruct.IsValid())
		{
			if (Ar.IsLoading())
			{
			
				if (!Data.IsValid() || (Data->GetScriptStruct() != ScriptStruct.Get()))
				{
				//在反序列化时 根据类型信息 创建新的封装实例
					FGameplayEffectContext* NewData = (FGameplayEffectContext*)
					FMemory::Malloc(ScriptStruct->GetStructureSize());
					ScriptStruct->InitializeStruct(NewData);

					Data = TSharedPtr<FGameplayEffectContext>(NewData, 
				FGameplayEffectContextDeleter());
				}
			}

			//将实例数据进行序列化与反序列化
			check(Data.IsValid());
			if (ScriptStruct->StructFlags & STRUCT_NetSerializeNative)
			{
				ScriptStruct->GetCppStructOps()->NetSerialize(Ar, Map, bOutSuccess, Data.Get());
			}
			
		}
	}

	bOutSuccess = true;
	return true;
}
```

解决了类型信息问题，就剩下填充FGameplayEffectContext及其子类实例数据了。所以Handle封装的FGameplayEffectContext及其子类也需要实现自定义网络序列化NetSerialize，将其字段信息转换成二进制流进行传输然后被反序列化。

```cpp
struct GAMEPLAYABILITIES_API FGameplayEffectContext
{
virtual bool NetSerialize(FArchive& Ar, class UPackageMap* Map, bool& bOutSuccess);
}

template<>
struct TStructOpsTypeTraits< FGameplayEffectContext > :
public TStructOpsTypeTraitsBase2< FGameplayEffectContext >
{
	enum
	{
		WithNetSerializer = true,
		WithCopy = true		
	};
};

```

> 💡 FGameplayEffectSpecHandle也跟FGameplayEffectContextHandle类似的包含了一个实例的共享指针，但是不支持网络复制(用不上机制也不支持，没有在全局缓存类型信息)，所以其实现的自定义网络接口NetSerialize直接报错并且Crash。如果通过网络复制FGameplayEffectSpecHandle会触发报错并且Crash

```cpp
bool FGameplayEffectSpecHandle::NetSerialize(...)
{
	ABILITY_LOG(Fatal, TEXT("FGameplayEffectSpecHandle should not be NetSerialized"));
	return false;
}
```

# **FGameplayEffectContext字段说明**

---

```cpp

struct GAMEPLAYABILITIES_API FGameplayEffectContext
{

	**//派发GE的Acotr(具备派发GE能力 拥有AbilitySystemComponent)**
	TWeakObjectPtr<AActor> Instigator;

	**//导致本次GE触发的Actor
	//不一定具备派发GE的能力 比如武器或者子弹导致了一个伤害效果 
	//**EffectCauser**是武器或者子弹
	//**Instigator**是实际派发效果玩家(武器或者子弹的拥有者)**
	UPROPERTY()
	TWeakObjectPtr<AActor> EffectCauser;

	**//触发GA的CDO(ClassDefaultObject)**
	UPROPERTY()
	TWeakObjectPtr<UGameplayAbility> AbilityCDO;

	**//触发GA的对象(不复制)**
	UPROPERTY(NotReplicated)
	TWeakObjectPtr<UGameplayAbility> AbilityInstanceNotReplicated;

	**//触发GA等级**
	UPROPERTY()
	int32 AbilityLevel;

	**//创建GE的U**Object
	UPROPERTY()
	TWeakObjectPtr<UObject> SourceObject;

	//**Instigator的AbilitySystemComponent**
	UPROPERTY(NotReplicated)
	TWeakObjectPtr<UAbilitySystemComponent> InstigatorAbilitySystemComponent;

	**//存放需要用到Actor参数**
	UPROPERTY()
	TArray<TWeakObjectPtr<AActor>> Actors;

	**//存放需要用到的碰撞信息**
	TSharedPtr<FHitResult>	HitResult;
}
```