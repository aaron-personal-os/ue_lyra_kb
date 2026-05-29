[UE4属性同步（一）服务器同步属性 - 知乎 (zhihu.com)](https://zhuanlan.zhihu.com/p/412517987)

> 💡 **本系列文章基于UE5.3**

# 概述

---

之前一章简单介绍了下网络同步的流程，本章详细介绍下网络同步涉及的概念及其实现细节。

- 同步通道--UActorChannel
- 同步执行类--FObjectReplicator
- 属性复制信息类--FRepLayout
- 历史记录--FReplicationChangelistMgr
- 序列化和反序列化

> 💡
>
> **网络同步流程通过UActorChannel⇒FObjectReplicator⇒FRepLayout逐层下发执行**

# UActorChannel

---

ActorChannel是UE网络通信的主要通道，**UE的网络同步主要是基于Actor的，每个支持网络的同步的Actor都会在相关的网络连接(NetConnection)中创建一个ActorChannel**，负责执行Actor及其关联的UObject(Actor上支持复制的组件和其他UObject，比如UGameplayAbility)的网络同步(属性复制和RPC)

```cpp
class UActorChannel : public UChannel
{
	//ActorChannel绑定的Actor指针
	TObjectPtr<AActor> Actor;
	
	//ActorChannel绑定的Actor对应的FObjectReplicator实例
	TSharedPtr<FObjectReplicator> ActorReplicator;
	
	//ActorChannel的FObjectReplicator实例列表 
	//与Actor关联的每个支持网络同步的UObject都会创建一个对应的FObjectReplicator实例
	TMap< UObject*, TSharedRef< FObjectReplicator > > ReplicationMap;
	
	//收包处理
	ENGINE_API virtual void ReceivedBunch( FInBunch& Bunch ) override;
	
	//发包处理
	ENGINE_API virtual FPacketIdRange SendBunch(FOutBunch* Bunch, bool Merge);

}
```

## **为网络连接创建ActorChannel**

---

网络连接(NetConnection)会为每个与该连接网络相关的Actor创建一个ActorChannel用于网络同步

```cpp
Channel = (UActorChannel*)Connection->CreateChannelByName( NAME_Actor, 
EChannelCreateFlags::OpenedLocally );

if ( Channel )
{
	Channel->SetChannelActor(Actor, ESetChannelActorFlags::None);
}

void UActorChannel::SetChannelActor(AActor* InActor, ESetChannelActorFlags Flags)
{
	//绑定Actor
	Actor = InActor;
	if (Actor)
	{
		//将新创建的ActorChannel加入网络连接的Channel列表
		Connection->AddActorChannel(Actor, this);
	}
	
	//创建Actor对应的 FObjectReplicator实例
	if (!EnumHasAnyFlags(Flags, ESetChannelActorFlags::SkipReplicatorCreation))
	{
		ActorReplicator = FindOrCreateReplicator(Actor);
	}
}
```

## **Acotr执行属性复制**

---

UActorChannel::ReplicateActor作为执行Actor及其关联Object(SubObject)的属性复制入口，**实际执行复制流程是Actor自身关联的FObjectReplicator实例ActorReplicator和SubObject关联的FObjectReplicator实例。**

```cpp
int64 UActorChannel::ReplicateActor()
{

	//通过Actor对应的FObjectReplicator实例执行Actor上的属性复制流程
	if (UE::Net::bPushModelValidateSkipUpdate || !bCanSkipUpdate)
	{
		bWroteSomethingImportant |= ActorReplicator->ReplicateProperties(Bunch, RepFlags);
	}
  
  //复制关联UObject上的属性复制
	bWroteSomethingImportant |= DoSubObjectReplication(Bunch, RepFlags);
	
	//数据放入网络缓存中
	if (bWroteSomethingImportant)
	{
		SendBunch(&Bunch, 1);
	}
}
```

## SubObject执行复制

---

SubObject(Actor关联的网络复制UObject)的属性复制是直接调用AActor::ReplicateSubobjects，Actor上支持复制的组件(Component)和组件上绑定的支持复制的UObject，最终支持复制的SubObject都会调用 UActorChannel::ReplicateSubobject执行该Object的属性复制流程。

> 💡 可以根据需求重载Actor和 UActorComponent上ReplicateSubobjects接口添加需要支持属性复制的UObject。

> [!note]- Actor收集支持复制的UObject网络复制数据。
> ```cpp
> bool UActorChannel::DoSubObjectReplication(...)
> {
>     //从Actor上收集支持网络复制的Subobject上的复制数据
>     bWroteSomethingImportant |= Actor->ReplicateSubobjects(this, &Bunch, &OutRepFlags);
> }
>
> //Actor上绑定的支持网络同步的UObject
> bool AActor::ReplicateSubobjects(..)
> {
>     //基类默认收集支持复制的组件上的复制数据
>     //继承的子类有其他需要关联的UObject可以重载这接口添加
>     for (UActorComponent* ActorComp : ReplicatedComponents)
>     {
>         if (ActorComp && ActorComp->GetReplicationCondition() != COND_Never)
>         {
>             //如果组件上还有需要有其他需要关联的UObject可以实现组件上ReplicateSubobjects添加
>             WroteSomething |= ActorComp->ReplicateSubobjects(Channel, Bunch, RepFlags);
>
>             //开始收集组件自身的复制数据     
>             WroteSomething |= Channel->ReplicateSubobject(ActorComp, *Bunch, *RepFlags);    
>         }
>     }
>     return WroteSomething;
> }
>
> //组件上绑定的支持网络同步UObject
> //以AbilitySystemComponent绑定的属性类为例
> bool UAbilitySystemComponent::ReplicateSubobjects(...)
> {
>     bool WroteSomething = Super::ReplicateSubobjects(Channel, Bunch, RepFlags);
>
>     for (const UAttributeSet* Set : GetSpawnedAttributes())
>     {
>         if (IsValid(Set))
>         {
>             //开始收集复制数据
>             WroteSomething |= Channel->ReplicateSubobject(const_cast<UAttributeSet*>(Set), 
>             *Bunch, *RepFlags);
>         }
>     }
>
> ....
>
>     return WroteSomething;
> }
> ```


> [!note]- 开始Subobject的复制流程(ReplicateProperties)
> ```cpp
> //对Actor关联的UObject执行属性复制
> bool UActorChannel::ReplicateSubobject(...)
> {
>     if (!DataChannelInternal::bIgnoreLegacyReplicateSubObject)
>     {
>         bWroteSomethingImportant = WriteSubObjectInBunch(SubObj, Bunch, RepFlags);
>     }
> }
>
> bool UActorChannel::WriteSubObjectInBunch(...)
> {
>     //为UObject分配网络GUID
>     if ( !Connection->Driver->GuidCache->SupportsObject( Obj, &WeakObj ) )
>     {
>         Connection->Driver->GuidCache->AssignNewNetGUID_Server( Obj );
>     }
>
>     //为UObject查找或者创建FObjectReplicator 实例
>     TSharedRef<FObjectReplicator>* FoundReplicator = FindReplicator(Obj);
>     TSharedRef<FObjectReplicator>& ObjectReplicator = 
>     !bFoundReplicator ? CreateReplicator(Obj) : *FoundReplicator;
>
>     //通过FObjectReplicator 实例执行属性复制流程
>     bool bWroteSomething = ObjectReplicator.Get().ReplicateProperties(...);
> }
> ```


# **FObjectReplicator**

---

FObjectReplicator 负责处理ActorChannel转发过来的属性复制和RPC
每个ActorChannel都会维护多个ObjectReplicator的对象实例，用于操作网络复制和RPC操作。

```cpp
//每个ActorChannel都有一个FObjectReplicator Map列表
//管理着ActorChannel所有同步对象的属性同步操作
class ENGINE_API UActorChannel : public UChannel
{
...
	//ActorChannel绑定的Actor的同步操作
	TSharedPtr<FObjectReplicator> ActorReplicator;
	//ActorChannel所有同步对象的同步操作
	TMap< UObject*, TSharedRef< FObjectReplicator > > ReplicationMap;

 //创建对应属性的FObjectReplicator 添加到ReplicationMap
  CreateReplicator(UObject* Obj, bool bCheckDormantReplicators)

	//为Actor或者RPC创建FObjectReplicator 
	FindOrCreateReplicator(UObject* Obj, bool* bOutCreated)
....
}
```

> 💡
>
> 大部分操作最终还是要经过FRepLayout实例进行处理

```cpp
class FObjectReplicator
{
	//发包处理(属性复制发包  RPC发包不通过这里触发)
	//自定义增量复制流程(FastArray)  属性复制入口
	ENGINE_API void ReplicateCustomDeltaProperties(...);
	//通用流程 属性复制入口
	ENGINE_API bool ReplicateProperties(...);
	//实际执行属性复制的接口
	ENGINE_API bool ReplicateProperties_r(...);
	
	ENGINE_API void PostSendBunch(...);
	
	
	//收包处理
	ENGINE_API bool ReceivedBunch(...);
	ENGINE_API bool ReceivedRPC(...);
	ENGINE_API void PostReceivedBunch();
	
	//客户端收到属性复制之后 调用OnRep_XXX函数
	ENGINE_API void CallRepNotifies(...);
	
}
```

# **FRepLayout**

---

FRepLayoutF负责处理FObjectReplicator转发过来的属性复制和RPC

FRepLayout维护某一类型的所有同步属性，类型可以是UClass，UStruct或者UFunction。对于一种类型，只会有一个对应的FReplayout实例，类型的多个实例共享。

> 💡
>
> FRepLayout存放的是需要复制的字段的内存偏移信息。根据内存偏移信息加上传入进来的类型实例，就可以获取到对应类型实例的复制字段数据。

FRepLayout是UE实现属性同步的核心，有**比较属性、发送属性数据、序列化和反序列化网络数据包**等功能。

```cpp
//属性同步列表(同一类型的所有对象共用一个)
class FRepLayout : public FGCObject, public TSharedFromThis<FRepLayout>
{
	//用来描述属性复制的属性字段信息
	TArray<FRepParentCmd> Parents;
	TArray<FRepLayoutCmd> Cmds;
	
  //为UClass类型创建一个 FRepLayout 
	ENGINE_API static TSharedPtr<FRepLayout> CreateFromClass(...);

	//为UStruct类型创建一个 FRepLayout 
	ENGINE_API static TSharedPtr<FRepLayout> CreateFromStruct(...);

	//为UFunction类型创建一个 FRepLayout 
	static TSharedPtr<FRepLayout> CreateFromFunction(...);

	//初始化UClass类型FRepLayout 
  //解析类型需要同步的属性
  //调用GetLifetimeReplicatedProps
  void InitFromClass(....);

  //初始化UStruct类型FRepLayout 
  //解析类型需要同步的参数列表
	void InitFromStruct(....);

  //初始化UFunction类型FRepLayout 
  //解析类型需要同步的属性
	void InitFromFunction(...);
	
	//同步对象(Actor或者其关联的同步SubObject)的属性
	bool ReplicateProperties(...) const;
	
	//属性对比
	ERepLayoutResult CompareProperties(...) const;

	//属性发送
	void SendProperties(...) const;
	void SendProperties_r(...) const;
  
 //客户端接收解析属性复制
	bool ReceiveProperties(...) const;

	//为RPC对象(UFunction)同步
	void ENGINE_API SendPropertiesForRPC(...) const;

	//接收解析RPC对象(UFunction)同步
	void ReceivePropertiesForRPC(...)
}

```

### **创建&初始化**

---

FRepLayout可以为**UClass，UFunction、UStruct类型创建实例**

> 💡
>
> 这里主要介绍UClass(属性复制)和UFunction(RPC)

> [!note]- **UClass对应的实例**
> 当NetDriver要同步UObject属性时会检查该UClass是否有RepLayout，没有则调用FRepLayout::CreateFromClass函数创建，创建后再调用FRepLayout::InitFromClass函数进行初始化。
>
> ```cpp
> TSharedPtr<FRepLayout> FRepLayout::CreateFromClass(...)
> {
>     TSharedPtr<FRepLayout> RepLayout = MakeShareable<FRepLayout>(new FRepLayout());
>     RepLayout->InitFromClass(InClass, ServerConnection, CreateFlags);
>     return RepLayout;
> }
> ```
>
> 初始化实例时，会根据UClass中的标记，找出哪些属性字段需要进行属性复制(**ClassReps**)。
>
> ```cpp
> //UClass 收集标记为网络复制的属性字段
> void UClass::SetUpRuntimeReplicationData()
> {
>         TArray<FProperty*> NetProperties;
>         for (TFieldIterator<FField> It(this, EFieldIteratorFlags::ExcludeSuper); 
>         It; ++It)
>         {
>             if (FProperty* Prop = CastField<FProperty>(*It))
>             {
>                 if ((Prop->PropertyFlags & CPF_Net) && Prop->GetOwner<UObject>() == this)
>                 {
>                     NetProperties.Add(Prop);
>                 }
>             }
>         }
>
>         **ClassReps**.Reserve(ClassReps.Num() + NetProperties.Num());
>         for (int32 i = 0; i < NetProperties.Num(); i++)
>         {
>             NetProperties[i]->RepIndex = (uint16)ClassReps.Num();
>             for (int32 j = 0; j < NetProperties[i]->ArrayDim; j++)
>             {
>                 **ClassReps**.Emplace(NetProperties[i], j);
>             }
>         }
> }
> ```
>
> 再根据这些字段信息构造FRepLayout的Parents字段，里面存放了所有需要复制的字段信息，同时收集每个字段的复制规则(调用**GetLifetimeReplicatedProps**)，标记是否有自定义增量复制的字段(FastArray)
>
> ```cpp
> void FRepLayout::InitFromClass(...)
> {
>
>     Parents.Empty(InObjectClass->ClassReps.Num());
>
>     //**构造填充FRepLayout的Parents字段**
>     for (int32 i = 0; i < InObjectClass->ClassReps.Num(); i++)
>     {
>         const int32 ParentHandle = AddParentProperty(Parents, Property, ArrayIdx);
>
>         Parents[ParentHandle].CmdStart = Cmds.Num();
>         //**递归展开填充到Cmds字段中(后面详细介绍)**
>         RelativeHandle = InitFromProperty_r<ERepBuildType::Class>
>         (SharedParams, StackParams);
>
>         Parents[ParentHandle].CmdEnd = Cmds.Num();
>         Parents[ParentHandle].Flags |= ERepParentFlags::IsConditional;
>         //**填充内存偏移信息**
>         Parents[ParentHandle].Offset = GetOffsetForProperty<ERepBuildType::Class>
>         (*Property) + ParentOffset;
>
>         //**填充属性复制规则(全部复制、只复制给主控端或者模拟端、动态条件复制)**
>         TArray<FLifetimeProperty> LifetimeProps;
>         LifetimeProps.Reserve(Parents.Num());
>         UObject* Object = InObjectClass->GetDefaultObject();
>
>         //这里调用**GetLifetimeReplicatedProps开始收集每个字段的复制规则**
>         **Object->GetLifetimeReplicatedProps(LifetimeProps);**
>
>         for (int32 i = 0; i < LifetimeProps.Num(); i++)
>         {
>             Parents[ParentIndex].Condition = LifetimeProps[i].Condition;
>             Parents[ParentIndex].RepNotifyCondition = LifetimeProps[i].RepNotifyCondition;
>         }
>
>         if (!EnumHasAnyFlags(Parents[ParentIndex].Flags,
>          ERepParentFlags::IsCustomDelta))
>         {
>             **//标记属性字段的Flag 是否是自定义增量复制(FastArray)之类的**
>             ...
>             Parents[ParentIndex].Flags |= ERepParentFlags::IsLifetime;
>
>             **//根据复制条件打的Flag**
>             if (LifetimeProps[i].Condition == COND_None)
>             {
>                 Parents[ParentIndex].Flags &= ~ERepParentFlags::IsConditional;
>             }
>             else if (LifetimeProps[i].Condition == COND_InitialOnly)
>             {
>                 Flags |= ERepLayoutFlags::HasInitialOnlyProperties;
>             }
>             else if (LifetimeProps[i].Condition == COND_Dynamic)
>             {
>                 Flags |= ERepLayoutFlags::HasDynamicConditionProperties;
>             }
>         }
>     }
> }
> ```


> [!note]- **UFunction对应的实例**
> 当NetDriver要执行RPC时会检查该RPC函数是否有对应的FRepLayout实例，用于网络数据的传输，没有则调用FRepLayout::CreateFromFunction函数创建，创建后再调用FRepLayout::InitFromFunction函数进行初始化。
>
> ```cpp
> TSharedPtr<FRepLayout> FRepLayout::CreateFromFunction(...)
> {
>     TSharedPtr<FRepLayout> RepLayout = MakeShareable<FRepLayout>(new FRepLayout());
>     RepLayout->InitFromFunction(InFunction, ServerConnection, CreateFlags);
>     return RepLayout;
> }
> ```
>
> 初始化时，主要是根据函数的参数列表进行构造RepLayout的Parents字段，里面存放了所有需要复制的字段信息
>
> ```cpp
> void FRepLayout::InitFromFunction(...)
> {
>
>     for (TFieldIterator<FProperty> It(InFunction); 
> It && (It->PropertyFlags & (CPF_Parm | CPF_ReturnParm)) == CPF_Parm; ++It)
>     {
>         for (int32 ArrayIdx = 0; ArrayIdx < It->ArrayDim; ++ArrayIdx)
>         {
>             const int32 ParentHandle = AddParentProperty(Parents, *It, ArrayIdx);
>
>             Parents[ParentHandle].CmdStart = Cmds.Num();
>
>             //**递归展开填充到Cmds字段中(后面详细介绍)**
>             RelativeHandle = InitFromProperty_r<ERepBuildType::Function>
>             (SharedParams, StackParams);
>
>             Parents[ParentHandle].CmdEnd = Cmds.Num();
>             //**填充内存偏移信息**
>             Parents[ParentHandle].Offset = GetOffsetForProperty<ERepBuildType::Function>
>             (**It);
>         }
>     }
> }
> ```


## **FRepParentCmd&FRepLayoutCmd**

---

FRepLayout 两个最主要的字段 **FRepParentCmd实例数组**和**FRepLayoutCmd实例数组**，用来描述属性复制的操作字段。

```cpp
class FRepLayout : public FGCObject, public TSharedFromThis<FRepLayout>
{

	TArray<FRepParentCmd> Parents;

	TArray<FRepLayoutCmd> Cmds;
}
```

- **FRepParentCmd存放的是UObject支持复制的属性字段(通过UPROPERTY标记的)**
- **FRepLayoutCmd存放的是FRepParentCmd复制字段递归展开的字段(平铺展开)**
- **复制时，实际对比和操作对象是FRepLayoutCmd存放的复制操作单元**

**FRepParentCmd展开成FRepLayoutCmd的规则：**

- 复制字段是int、bool、Byte之类的简原子段或者实现了自定义网络序列化(NetSerialize)的Struct FRepLayoutCmd里存放的跟FRepParentCmd一致，不需要进一步展开。
- 复制字段是数组或者Struct的复合字段，则FRepLayoutCmd里存放的是FRepParentCmd递归展(平铺)的内部字段。**所有展开字段都放到FRepLayoutCmd**。
- RepParentCmd的CmdStart和CmdEnd属性，以及RepLayoutCmd的ParentIndex属性，使两者建立了双向联系。

如下所示的代码:RepTestData3是要复制的属性字段，类型是FRepTestData3。FRepTestData3类型内部嵌套了FRepTestData2，FRepTestData2内部嵌套了FRepTestData1。

```cpp
USTRUCT()
struct FRepTestData1
{
	GENERATED_BODY()

	UPROPERTY()
	int32 a1;

	UPROPERTY()
	float b1;

	UPROPERTY()
	TArray<int32> c1;

	UPROPERTY()
	FVector d1;
};

USTRUCT()
struct FRepTestData2
{
	GENERATED_BODY()

	UPROPERTY()
	FRepTestData1 Data1;

	UPROPERTY()
	int32 a2;
};

USTRUCT()
struct FRepTestData3
{
	GENERATED_BODY()

	UPROPERTY()
	FRepTestData2 Data2;

	UPROPERTY()
	int32 a3;
};

class UTestComponent : public UActorComponent
{
...
	UPROPERTY(Replicated)
	FRepTestData3 RepTestData3;
...
}
```

在构造RepTestData3的FRepParentCmd和FRepLayoutCmd时，RepTestData3是需要复制的属性，放入FRepParentCmd数组中，RepTestData3依次递归展开内部字段和嵌套的数组、结构体，放入FRepLayoutCmd数组中。

FRepLayoutCmd中的ParentIndex标记了其归属的ParentCmd在FRepParentCmd数组中的索引，FRepParentCmd中CmdStart和CmdEnd标记了展开的字段在FRepLayoutCmd数组的起始和截止索引(截止索引是 CmdEnd-1)

![image.png](http://pic.xyyxr.cn/20260504161054391.png)

![Untitled](http://pic.xyyxr.cn/20260504161054392.png)

TArray(c1)会在FRepLayoutCmd占据三个字段，一个是数组本身，一个是数组内部的元素，一个是数组截至标记 ReturnCmd。

![Untitled](http://pic.xyyxr.cn/20260504161056184.png)

**通过InitFromProperty_r执行递归展开**

```cpp
static int32 InitFromProperty_r(...)
{
	if (FArrayProperty* ArrayProp = CastField<FArrayProperty>(StackParams.Property))
	{
		//TArray 类型字段
		const int32 CmdStart = SharedParams.Cmds.Num();
		SharedParams.Parent.Flags |= ERepParentFlags::HasDynamicArrayProperties;

		//添加数组本身
		....
		const uint32 ArrayChecksum = AddArrayCmd(SharedParams, StackParams);

	  //添加数组内部元素、
	  ...
		InitFromProperty_r<BuildType>(SharedParams, NewStackParams);

		//添加数组结束字段空字段
		...
		AddReturnCmd(SharedParams.Cmds);

	
	}
	else if (FStructProperty* StructProp = CastField<FStructProperty>(...))
	{
		//Struct 类型字段
		
		if (EnumHasAnyFlags(Struct->StructFlags, STRUCT_NetSerializeNative))
		{
			//如果Struct是自定义了网络序列化(NetSerialize) 则不需要再递归展开 
			//直接将Strcut字段本身放入
			SharedParams.bHasNetSerializeProperties = true;
		...
			++StackParams.RelativeHandle;
			AddPropertyCmd(SharedParams, StackParams);

			return StackParams.RelativeHandle;
		}

		//如果Struct不是自定义了网络序列化(NetSerialize) 则需要再递归展开
		return InitFromStructProperty<BuildType>(SharedParams, StackParams,
		 StructProp, Struct);
	}
	else
	{
		//普通字段 直接放入
...
		AddPropertyCmd(SharedParams, StackParams);
	}

	return StackParams.RelativeHandle;
}
```

## **自定义网络复制Struct**

---

对于复制字段有Struct字段的，在FRepLayout构造中，普通的Strcut字段会递归展开内部字段放入FRepLayoutCmd数组中

自定义网络复制(NetSerialize)的Struct在RepLayout中会将其视为一个整体，不会再将内部的字段拆分成独立的FRepLayoutCmd等同于int、float之类的原子字段。

两者的区别在于复制和对比时，前者操作的对象是Struct内部的每个字段，会为其内部的每个字段做差异化对比，只复制其中修改的字段。而后者因为直接将Struct字段作为一个整体放到Cmd中，Struct有任意一个字段变化都会视为Struct有修改，触发整个Struct的复制。

自定义网络复制的Struct对比操作相对来说会少一点，不需要递归对比每个字段。但复制数据量可能会大一点。

> 💡
>
> 自定义网络复制的Struct有任意一个字段变化都会视为Struct有修改，可以考虑实现自定义的对比Identica，实现快速高效的对比。同时自定义网络复制实现的NetSerialize可以针对性对一些未发生修改的字段不序列化，直接使用默认值来减少复制数据量。

自定义网络复制的Struct对比是否有字段变化**(**UScriptStruct::CompareScriptStruct**)**

```cpp
bool UScriptStruct::CompareScriptStruct(const void* A, const void* B, uint32 PortFlags) 
{
  //如果实现了自定义对比Identical 则直接调用Identical进行对比
	if (StructFlags & STRUCT_IdenticalNative)
	{
		UScriptStruct::ICppStructOps* TheCppStructOps = GetCppStructOps();
		check(TheCppStructOps);
		bool bResult = false;
		if (TheCppStructOps->Identical(A, B, PortFlags, bResult))
		{
			return bResult;
		}
	}

	//如果未实现了自定义对比Identical 则需要逐个字段进行对比 有一个不同则视为不相等
	for( TFieldIterator<FProperty> It(this); It; ++It )
	{
		for( int32 i=0; i<It->ArrayDim; i++ )
		{
			if( !It->Identical_InContainer(A,B,i,PortFlags) )
			{
				return false;
			}
		}
	}
}
```

### 定制Struct特性

---

在UE中，UScriptStruct(结构体类型)提供了一种机制，用于定制结构体的行为和特性。 UScriptStruct 内部有一个功能强大的接口类ICppStructOps，可以用来定制结构体的行为和特性。这些操作包括构造、析构、复制和序列化等。

ICppStructOps 是一个接口类，它允许为指定类型的结构体(Struct)提供指定的自定义的 C++ 操作函数(NetSerialize、Serialize、Identical)。通过实现这些接口可以定制专有操作(比如自定义网络序列化)。TCppStructOps 是继承ICppStructOps 的模板类

```cpp
class UScriptStruct : public UStruct
{
		struct ICppStructOps
		{
		}
		
		template<class CPPSTRUCT>
		struct TCppStructOps final : public ICppStructOps
		{
			//实现了定制对比特性
			virtual bool Identical(...) override
			{
				if constexpr (TStructOpsTypeTraits<CPPSTRUCT>::WithIdentical)
				{
				bOutResult = ((const CPPSTRUCT*)A)->Identical((const CPPSTRUCT*)B, PortFlags);
					return true;
				}
			}
		}
}
```

下面示例代码是展示如何调用结构体定制对比特性(Identical) 其他定制特性类型

```cpp
bool UScriptStruct::CompareScriptStruct(const void* A, const void* B, uint32 PortFlags) 
{
  //如果实现了结构体定制了对比Identical 则直接调用Identical进行对比
	if (StructFlags & STRUCT_IdenticalNative)
	{
	  //这里通过调用UScriptStruct里的ICppStructOps的Identical来调用对应结构体定制的对比接口
		UScriptStruct::ICppStructOps* TheCppStructOps = GetCppStructOps();
		check(TheCppStructOps);
		bool bResult = false;
		if (TheCppStructOps->Identical(A, B, PortFlags, bResult))
		{
			return bResult;
		}
	}
}
```

下面是一些 ICppStructOps 提供的关键定制功能：

构造和析构：

**Construct**：这是用来构造内存中的结构体实例的函数。

**Destruct**：这是用来销毁内存中的结构体实例的函数。

拷贝：

**Copy**：这是用来将数据从一个结构体实例复制到另一个实例的函数。

序列化：

**Serialize**：这是用来将结构体实例序列化的函数

**PostSerialize**:序列化后执行的函数(比如可以用于DataTableRow的配置检测)

**NetSerialize**：这是用来将结构体实例网络序列化的函数

对比：

**AreEqual**：比较两个结构体实例是否相等。

**Identica**：检查两个结构体实例是否在指定的条件下相等。

通过特化TStructOpsTypeTraits模板类为特定的Struct定制标记该Struct定制了哪些特性

```cpp
template <class CPPSTRUCT>
struct TStructOpsTypeTraitsBase2
{
	enum
	{
	...
		 //自定义对比
		WithIdentical                  = false,
		//自定义网络序列化
		WithNetSerializer              = false,    
		...
	}
}

template<class CPPSTRUCT>
struct TStructOpsTypeTraits : public TStructOpsTypeTraitsBase2<CPPSTRUCT>
{
};
```

> 💡
>
> 比如下面这段模板特化，为FCustomNetSerializeBuff_Minimal类型定制了网络序列化和对比的特性
>
> FCustomNetSerializeBuff_Minimal需要实现Identical 和NetSerializer 接口

```cpp
USTRUCT()
struct FCustomNetSerializeBuff_Minimal
{
	GENERATED_USTRUCT_BODY()

	//实现Identical 和NetSerializer 接口
	bool NetSerialize(...);
	bool Identical(...)

};

//标记结构体FCustomNetSerializeBuff_Minimal定制了哪些特性
template <>
struct TStructOpsTypeTraits<FCustomNetSerializeBuff_Minimal> :
public TStructOpsTypeTraitsBase2<FCustomNetSerializeBuff_Minimal>
{
	enum
	{
		WithNetSerializer = true 
	};
};
```

# **属性对比&复制流程详解**

---

属性复制(同步)的核心逻辑是**DS端比较当前需要同步属性是否发生了变化，如果发生变化就将这个变动的字段数据同步给客户端**。属性复制机制在底层提供了属性对比(CompareProperties)，发送变动属性字段(SendProperties)的机制。

属性复制分为**常规的属性复制**和**自定义增量属性复制**(FastArray)

## 常规的属性复制流程

---

![Untitled](http://pic.xyyxr.cn/20260504161056185.png)

> [!note]- 根据FRepLayout里的FRepParentCmd和FRepLayoutCmd列表去进行字段的对比，实际对比的是FRepLayoutCmd列表里的字段当前数据和历史数据。根据对比结果更新历史数据和本次修改记录
> > 💡 CompareParentProperty⇒CompareProperties_r


> [!note]- 更新对比结果会更新所有连接共享的历史数据和修改记录(UNetDriver上的ReplicationChangeListMap)，同时根据当前连接保留的上次修改记录做对比，得出当前连接本次需要发送哪些修改的字段。
> > 💡 FRepLayout::ReplicateProperties⇒FRepLayout::SendProperties
>
> ```cpp
> bool FRepLayout::ReplicateProperties(...) const
> {
>     if (RepState->LastChangelistIndex <= RepChangelistState->HistoryStart)
>     {
>         RepState->LastChangelistIndex = RepChangelistState->HistoryStart;
>     }
>
>     const int32 PossibleNewHistoryIndex = 
>     RepState->HistoryEnd % FSendingRepState::MAX_CHANGE_HISTORY;
>
>     FRepChangedHistory& PossibleNewHistoryItem = 
>     RepState->ChangeHistory[PossibleNewHistoryIndex];
>
>     TArray<uint16>& Changed = PossibleNewHistoryItem.Changed;
>     //合并历史修改记录
>     //HistoryEnd其实是为下次对比预留的位置
>     for (int32 i = RepState->LastChangelistIndex; i < RepChangelistState->HistoryEnd;
>      ++i)
>     {
>         const int32 HistoryIndex = i % FRepChangelistState::MAX_CHANGE_HISTORY;
>
>         FRepChangedHistory& HistoryItem = 
>         RepChangelistState->ChangeHistory[HistoryIndex];
>
>         TArray<uint16> Temp = MoveTemp(Changed);
>         MergeChangeList(Data, HistoryItem.Changed, Temp, Changed);
>     }
>
>     RepState->LastChangelistIndex = RepChangelistState->HistoryEnd;
>
>     ....
>     if (Changed.Num() > 0)
>     {
>         SendProperties(...);
>     }
> }
> ```


![Untitled](http://pic.xyyxr.cn/20260504161056186.png)

> [!note]- 根据修改记录将有变动的字段进行网络序列化
> > 💡 FRepLayout::SendProperties⇒FRepLayout::SendProperties_r


> [!note]- 将序列化结果放入网络缓存中等待发送
> > 💡 UChannel::SendBunch


## 自定义增量属性复制流程(FastArray)

---

除了常规的属性复制流程，UE还提供一种自定义增量属性复制流程（CustomDeltaProperties），可以定制增量复制规则。

典型的应用就是FastArray，可以手动标记数组哪些元素发生了变动，属性复制时，只需要去对比和复制的那些标记了改动的数组元素即可。下面以FastArray实现为例来说明。

### **FastArray特性**

---

FastArray与普通的TArray数组在网络复制的区别在于，FastArray只会复制发生变动的数值元素，而且只会对比发生变动的数组元素，而普通的TArray数组需要变量对比所有的数组元素是否发生了变化，如果删除中间元素会导致其他数组元素因为发生了位置变化而视为发生了变化触发网络复制。

FastArray还会在客户端接收到数组元素的新增、删除、修改后触发对应的回调接口便于处理对应的逻辑

> 💡
>
> 大部分情况下FastArray因为可以差异化网络复制，只对比、复制发送修改的数据相对于普通TArray方案具有优势， 但同时也会因为各种标记字段增加一些额外的网络开销，所以有些数组元素数据本身就比较小而且数组元素变动时，大部分都是需要修改的数据时，可能TArray的方案会更优。(FastArray本身标记开销至少占16个字节 普通数组相对来说需要记录一个数组的大小2字节)

```cpp
//FastArray的头部标记信息 至少16个字节
template<typename Type, typename SerializerType>
void FFastArraySerializer::TFastArraySerializeHelper<Type, SerializerType>::
WriteDeltaHeader(FFastArraySerializerHeader& Header) const
{
	FBitWriter& Writer = *Parms.Writer;

	//写入数组的最近一次的修改批次号和上一次同步的修改批次号
	Writer << Header.ArrayReplicationKey;
	Writer << Header.BaseReplicationKey;

	//要删除元素的个数
	int32 NumDeletes = Header.DeletedIndices.Num();
	Writer << NumDeletes;

	//要修改的元素个数
	Writer << Header.NumChanged;

}
```

> [!note]- **通过一个自增ID ReplicationID来标记数组中的元素，而不是依赖数组下标Index**
> > 💡
> >
> >     这样的好处就是，删除中间数组元素时不会因为后续数组元素位置发送变化而需要全部复制那些变动位置的数组元素
> >
> >     FastArray依赖的是ReplicationID而不是数组Index，这样删除元素时，客户端只要拿到对应的ReplicationID就可以自行执行删除操作，但这样两端数组顺序可能就会不一致了。（DS端的移除操作无法保证跟客户端执行的移除操作一致，导致两端数组顺序不一致）
>
> ```cpp
> void FFastArraySerializer::TFastArraySerializeHelper<Type, SerializerType>::
> PostReceiveCleanup(...)
> {
>     if (Header.DeletedIndices.Num() > 0)
>     {
>       //先排序
>         Header.DeletedIndices.Sort();
>         for (int32 i = Header.DeletedIndices.Num() - 1; i >= 0; --i)
>         {
>             int32 DeleteIndex = Header.DeletedIndices[i];
>             if (Items.IsValidIndex(DeleteIndex))
>             {
>                 //交换的方式移除元素(效率更高 顺序会被打乱)
>                 Items.RemoveAtSwap(DeleteIndex, EAllowShrinking::No);
>             }
>         }
>     }
> }
> ```


> [!note]- **只同步新增、删除、有修改的数组元素，未发生修改的数组元素不会同步**
> > 💡
> >
> >     因为删除数组元素导致其他数组元素位置发生变化的,那些位置发生变化的元素不会被视为被修改了，只有删除的那个元素会被同步
> >
> >     参照上一条特性 FastArray是通过一个自增ReplicationID来标记数组中的元素，DS和客户端是通过ReplicationID来关联对应的数组元素而不是依赖数组下标Index，所以只要ReplicationID和ReplicationKey(数组元素的修改批次)未变，都视为元素未发生变动。
>
> > 💡
> >
> >     默认情况下数组元素发生变化时，其内部的字段也是增量复制的，只会复制那些有修改的字段。新增数组元素是全量复制，删除的元素值需要复制删除元素的ReplicationID。
>
> ```cpp
> //全局开关
> int32 GSupportsFastArrayDelta = 1;
> static FAutoConsoleVariableRef CVarSupportsFastArrayDelta(
>     TEXT("net.SupportFastArrayDelta"),
>     GSupportsFastArrayDelta,
>     TEXT("Whether or not Fast Array Struct Delta Serialization is enabled.")
> );
>
> FFastArraySerializer()
> {
>     //默认开启了数组元素的结构体字段增量复制设置(只有修改的字段才会复制 减少网络数据量)
>     //如果不开启数组元素就是全量复制(减少字段对比的开销)
>     SetDeltaSerializationEnabled(true);
> }
> ```
>
> > 💡
> >
> >     这里有个要注意的点，如果直接通过=将一个新构造的FastArrayItem赋值给数组中存在的一个数组元素，因为默认情况是会拷贝ReplicationID和ReplicationKey，所以赋值之后虽然数组元素的位置未发生改变，但因为新构造的FastArrayItem的ReplicationID是新增的，这个操作会被视为新增了一个数组元素，从而执行全量复制而不是增量复制。如果要执行增量复制，则需要继承之前元素的ReplicationID和ReplicationKey，或者赋值是不去赋值ReplicationID和ReplicationKey。
>
> 收集FastArray发生变动的元素
>
> ```cpp
> template<typename Type, typename SerializerType>
> void FFastArraySerializer::TFastArraySerializeHelper<Type, SerializerType>::
> BuildChangedAndDeletedBuffers(...)
> {
>
>     //先通过跟之前的数组元素数量的大小对比 算出一个数量差异 作为初始的删除数量
>     const int32 NumConsideredItems = CalcNumItemsForConsideration();
>     int32 DeleteCount = (OldIDToKeyMap ? OldIDToKeyMap->Num(): 0)-NumConsideredItems; 
>     for (int32 i = 0; i < Items.Num(); ++i)
>     {
>         Type& Item = Items[i];
>
>         if (!ArraySerializer.template ShouldWriteFastArrayItem<Type, SerializerType>(
>         Item, Parms.bIsWritingOnClient))
>         {
>             continue;
>         }
>
>         const int32* OldValuePtr = OldIDToKeyMap ? 
>         OldIDToKeyMap->Find(Item.ReplicationID) : NULL;
>         if (OldValuePtr)
>         {
>             if (*OldValuePtr == Item.ReplicationKey)
>             {
>              //如果ReplicationID和ReplicationKey都一样 视为元素没发生变动
>                 continue;
>             }
>             else
>             {
>                 //ReplicationID相同ReplicationKey不同 视为改数组元素发生了修改
>                 ChangedElements.Add(FFastArraySerializer_FastArrayDeltaSerialize_FIdxIDPair(i, Item.ReplicationID));
>             }
>         }
>         else
>         {
>             // 在旧的之中找不到 视为新增元素
>             ChangedElements.Add(FFastArraySerializer_FastArrayDeltaSerialize_FIdxIDPair(i, 
>             Item.ReplicationID));
>             ++DeleteCount; //新增了一个元素 那通过数量差异算出的删除数量应该+1
>         }
>     }
>
>     //如果删除数量 >0 收集下哪些元素被删除了(哪些ReplicationID对应的元素已经不在了)
>     if (DeleteCount > 0 && OldIDToKeyMap)
>     {
>         for (auto It = OldIDToKeyMap->CreateConstIterator(); It; ++It)
>         {
>             if (!NewIDToKeyMap.Contains(It.Key()))
>             {
>                 DeletedElements.Add(It.Key());
>                 //删除的都被收集了 中断查询
>                 if (--DeleteCount <= 0)
>                 {
>                     break;
>                 }
>             }
>         }
>     }
> }
> ```
>
> > 💡
> >
> >     通过实现 ShouldWriteFastArrayItem(const Type& Item, const bool bIsWritingOnClient)，可以将一些满足特定条件的数组元素跳过元素变动检测。可以参照FGameplayAbilitySpecContainer


> [!note]- **在客户端接收FastArray元素新增、移除、修改了会触发对应的回调**
> ```cpp
> void FFastArraySerializer::TFastArraySerializeHelper<Type, SerializerType>::
> PostReceiveCleanup(...)
> {
>      //分别触发FastArray和FastArrayItem的删除操作
>         for (int32 idx : Header.DeletedIndices)
>         {
>             if (Items.IsValidIndex(idx))
>             {
>                 Items[idx].PreReplicatedRemove(ArraySerializer);
>             }
>         }
>         ArraySerializer.PreReplicatedRemove(Header.DeletedIndices, FinalSize);
>
>         //分别触发FastArray和FastArrayItem的新增操作
>         for (int32 idx : AddedIndices)
>         {
>             Items[idx].PostReplicatedAdd(ArraySerializer);
>         }
>         ArraySerializer.PostReplicatedAdd(AddedIndices, FinalSize);
>
>         //分别触发FastArray和FastArrayItem的修改操作
>         for (int32 idx : ChangedIndices)
>         {
>             Items[idx].PostReplicatedChange(ArraySerializer);
>         }
>         ArraySerializer.PostReplicatedChange(ChangedIndices, FinalSize);
>
>         //执行元素删除操作
>         if (Header.DeletedIndices.Num() > 0)
>         {
>             Header.DeletedIndices.Sort();
>             for (int32 i = Header.DeletedIndices.Num() - 1; i >= 0; --i)
>             {
>                 int32 DeleteIndex = Header.DeletedIndices[i];
>                 if (Items.IsValidIndex(DeleteIndex))
>                 {
>                     Items.RemoveAtSwap(DeleteIndex, EAllowShrinking::No);
>                 }
>             }
> }
> ```


### FastArray使用

---

FastArray使用的步骤:

- 创建一个继承自FFastArraySerializerItem的结构体作为增量复制数组(FastArray)的数组元素(下图所示的FFastArrayTestItem)
- 创建一个继承自FFastArraySerializer的结构体作为增量复制数组(FastArray)，结构体内包含一个上面创建的FFastArraySerializerItem子类的对象数组(下图所示的FFastArrayTest )。
- 继承自FFastArraySerializer的子类需要实现NetDeltaSerialize来实现增量复制(一般直接调用基类实现的接口FFastArraySerializer::FastArrayDeltaSerialize)，并特化特性模板TStructOpsTypeTraits，标记需要启用NetDeltaSerializer特性。
- 定义FFastArraySerializer实例并标记属性复制(下图所示的FFastArrayTest FastArrayTestProp ; )

```cpp
**//创建一个继承自FFastArraySerializerItem的结构体作为复制数组(FastArray)的元素**
USTRUCT()
struct FFastArrayTestItem : public FFastArraySerializerItem
{
	GENERATED_BODY()

};

**//创建一个继承自FFastArraySerializer的结构体作为复制数组(FastArray)类型**
USTRUCT()
struct FFastArrayTest : public FFastArraySerializer
{
	GENERATED_BODY()
public:
	UPROPERTY()
	TArray<FFastArrayTestItem > Items;
	
	**//实现NetDeltaSerialize来实现增量复制
	//(一般直接调用基类实现的接口FFastArraySerializer::FastArrayDeltaSerialize)**
	bool NetDeltaSerialize(FNetDeltaSerializeInfo& DeltaParms)
	{
	return FFastArraySerializer::
	FastArrayDeltaSerialize<FFastArrayTestItem , FFastArrayTest>(...);
	}
};

**//特化特性模板TStructOpsTypeTraits，标记需要启用NetDeltaSerializer特性**
template<>
struct TStructOpsTypeTraits<FFastArrayTest> : 
public TStructOpsTypeTraitsBase2<FFastArrayTest>
{
	enum
	{
		WithNetDeltaSerializer = true,
	};
};

class UTestComponent : public UActorComponent
{
...
	**//添加FastArray属性字段**
	UPROPERTY(Replicated)
	FFastArrayTest FastArrayTestProp ;
...
}
```

FastArray的数组元素可以通过实现以下接口，在客户端处理数组元素添加、移除、修改。

```cpp
struct FFastArraySerializerItem
{
	UPROPERTY(NotReplicated)
	int32 ReplicationID;

	UPROPERTY(NotReplicated)
	int32 ReplicationKey;

	UPROPERTY(NotReplicated)
	int32 MostRecentArrayReplicationKey;
	
	//元素被移除
	FORCEINLINE void PreReplicatedRemove(...) { }
	
	//元素被添加
	FORCEINLINE void PostReplicatedAdd(...) { }

	//元素被修改
	FORCEINLINE void PostReplicatedChange(...) { }
}
```

> 💡 FFastArraySerializerItem 有三个属性字段
> ReplicationID
> ReplicationKey
> MostRecentArrayReplicationKey
>
> ReplicationID标记元素，每次新增的元素都会为其分配一个新ID。**ReplicationID不同会认为是两个不同的元素，就算占用的数组索引是一致的，也会认为该位置的元素被新增的元素替换了**。新增元素在复制时默认是全量复制，而原有元素在复制时只复制发生变动的字段。
>
> ReplicationKey 表示该元素的修改批次，每次被修改都会+1。修改批次不同会认为当前元素发生了变动。
>
> MostRecentArrayReplicationKey  记录了FastArray数组最近一次的修改批次
>
> 这里的ReplicationID是标记为非复制的字段，实际FFastArraySerializerItem的ReplicationID是会复制到客户端的，只是不再跟FFastArraySerializerItem绑定，而是通过
> FFastArraySerializer_FastArrayDeltaSerialize_FIdxIDPair的进行网络同步，最终是会放到
> FFastArraySerializer中的ItemMap，这是ReplicationID和数组索引的映射关系
>
> 因为DS和客户端的数组元素不保证顺序一致，所以在客户端ReplicationID不会跟FFastArraySerializerItem进行绑定，而是放到FFastArraySerializer的映射表ItemMap中，这样网络复制时，可以通过复制下来的ReplicationID在映射表中查到客户端对应的数组索引。

> 💡
>
> 当数组元素元素发生变动时， 需要调用MarkItemDirty标记下。
>
> 新增元素会重新分配一个ReplicationID ，现有元素只是修改批次+1

```cpp
	void MarkItemDirty(FFastArraySerializerItem & Item)
	{
		if (Item.ReplicationID == INDEX_NONE)
		{
			Item.ReplicationID = ++IDCounter;
			if (IDCounter == INDEX_NONE)
			{
				IDCounter++;
			}
		}

		Item.ReplicationKey++;
		MarkArrayDirty();
	}
```

### **FastArray属性对比&复制流程**

---

FFastArraySerializer及其子类实现了增量复制的接口(NetDeltaSerialize)，其属性复制流程都由自定义实现的增量复制的接口(NetDeltaSerialize)接管了。

```cpp
void FObjectReplicator::ReplicateCustomDeltaProperties(...)
{
	for (uint16 CustomDeltaProperty = 0; 
	CustomDeltaProperty < NumLifetimeCustomDeltaProperties; ++CustomDeltaProperty)
	{
	...
	SendCustomDeltaProperty(...)
	...
	}
}

bool FRepLayout::SendCustomDeltaProperty(...) const
{
...
return CppStructOps->NetDeltaSerialize(Params, Params.Data);
...
}
```

> 💡
>
> 增量复制的字段对比堆栈

![Untitled](http://pic.xyyxr.cn/20260504161056187.png)

> 💡
>
> 增量复制的字段复制堆栈

![Untitled](http://pic.xyyxr.cn/20260504161056188.png)

FastArray的增量复制的接口(NetDeltaSerialize)一般都是直接调用基类实现的模板函数FFastArraySerializer::FastArrayDeltaSerialize。默认开启了FastArrayItem对应结构体(Struct)内部字段的差异化复制(只复制修改的字段)(SetDeltaSerializationEnabled)，如果不开启则走常规序列化，直接序列化FastArrayItem整体。

```cpp
template<typename Type, typename SerializerType >
bool FFastArraySerializer::FastArrayDeltaSerialize(...)
{

//常规序列化(SetDeltaSerializationEnabled为False)

//收集变动元素
if (Parms.bIsInitializingBaseFromDefault)
	{
		Helper.BuildChangedAndDeletedBuffersFromDefault(NewMap, ChangedElements);
	}
	else
	{
		Helper.BuildChangedAndDeletedBuffers(NewMap, OldMap, ChangedElements, 
		Header.DeletedIndices);
	}

		for (auto It = ChangedElements.CreateIterator(); It; ++It)
		{
			void* ThisElement = &Items[It->Idx];

			// Dont pack this, want property to be byte aligned
			uint32 ID = It->ID;
			Writer << ID;

			UE_LOG(LogNetFastTArray, Log, TEXT("   Changed ElementID: %d"), ID);

			Parms.Struct = InnerStruct;
			Parms.Data = ThisElement;
			
			//序列化FastArrayItem整体(不对比字段 直接全量复制)
			Parms.NetSerializeCB->NetSerializeStruct(Parms);
		}
		
}

	

//
template<typename Type, typename SerializerType>
bool FFastArraySerializer::FastArrayDeltaSerialize_DeltaSerializeStructs(...)
{
...
//构建发送变动的元素
if (Parms.bIsInitializingBaseFromDefault)
{
	Helper.BuildChangedAndDeletedBuffersFromDefault(NewItemMap, ChangedElements);
}
else
{
	Helper.BuildChangedAndDeletedBuffers(NewItemMap, OldItemMap, ChangedElements, Header.DeletedIndices);
}

//执行差异化的网络复制(对比字段 复制差异 增量复制)
return Parms.NetSerializeCB->NetDeltaSerializeForFastArray(DeltaSerializeParams);
...
}
```

> [!note]- 开启了FastArrayItem对应结构体(Struct)内部字段的差异化复制(只复制修改的字段)，会对比Struct内部字段的，只复制修改字段，最终调用的FRepLayout::DeltaSerializeFastArrayProperty进行处理
> ```cpp
> ERepLayoutResult FRepLayout::DeltaSerializeFastArrayProperty(...) const
> {
>     ...
>     if (bIsWriting)
>     {
>     ...
>         **//获取FastArray数组中哪些元素发生了变动**
>         auto& ChangedElements = *Params.WriteChangedElements;
>     ...
>
>         TArray<uint16> NewChangelist;
>
>         **//对变动的元素执行对比操作(如果元素是新增的则不需要对比了)**
>         for (auto& IDIndexPair : ChangedElements)
>         {
>         ...
>             CompareProperties_r(...);
>         ...
>         }
>
>         **//计算哪些字段本次需要发送**
>         for (int32 i = 0; i < ChangedElements.Num(); ++i)
>         {
>             ...
>             BuildChangeList_r(...);
>         ...
>         }
>
>         **//即将发生改变的字段序列化并放入网络发送缓存中**
>         for (int32 i = 0; i < ChangedElements.Num(); ++i)
>         {
>         ...
>             SendProperties_r(...)
>         ...
>         }
>     }
> }
> ```

- 如果不开启FastArrayItem对应结构体(Struct)内部字段的差异化复制(SetDeltaSerializationEnabled),走常规复制，则最终调用的是
FRepLayout::SerializePropertiesForStruct，直接复制整个Struct(全量复制)
    
```cpp
    void FRepLayout::SerializePropertiesForStruct(
    	UStruct* Struct,
    	FBitArchive& Ar,
    	UPackageMap* Map,
    	FRepObjectDataBuffer Data,
    	bool& bHasUnmapped,
    	const UObject* OwningObject) const
    {
    	check(Struct == Owner);
    
    	static FRepSerializationSharedInfo Empty;
    
    	for (int32 i = 0; i < Parents.Num(); i++)
    	{
    		SerializeProperties_r(Ar, Map, Parents[i].CmdStart, Parents[i].CmdEnd, Data, 
    		bHasUnmapped, 0, 0, Empty, nullptr, OwningObject);
    
    		if (Ar.IsError())
    		{
    			return;
    		}
    	}
    }
```
    

**FastArray网络复制头部信息**

```cpp
template<typename Type, typename SerializerType>
void FFastArraySerializer::TFastArraySerializeHelper<Type, SerializerType>::
WriteDeltaHeader(FFastArraySerializerHeader& Header) const
{
	FBitWriter& Writer = *Parms.Writer;

	//写入数组的最近一次的修改批次号和上一次同步的修改批次号
	Writer << Header.ArrayReplicationKey;
	Writer << Header.BaseReplicationKey;

	//要删除元素的个数
	int32 NumDeletes = Header.DeletedIndices.Num();
	Writer << NumDeletes;

	//要修改的元素个数
	Writer << Header.NumChanged;

	// 要删除哪些元素
	for (auto It = Header.DeletedIndices.CreateIterator(); It; ++It)
	{
		int32 ID = *It;
		Writer << ID;
	}
}
```

## **历史记录--ChangelistMgr**

---

属性复制中属性对比必须要一个历史数据作为对比，同时还要保留一份历史修改记录。需要属性复制的UObject会在UNetDriver上维护一份历史数据和历史修改记录

```cpp
class UNetDriver : public UObject, public FExec
{
	TMap< UObject*, FReplicationChangelistMgrWrapper >	ReplicationChangeListMap;
}
```

同一UObject实例在不同网络连接中共享同一份历史数据和修改记录，在执行对比操作时如果发现有变动就更新历史数据和修改记录信息。

同一帧只需要其中一个连接执行一次了对比更新即可，其他连接共享更新后的历史数据和修改记录信息。

> [!note]- ChangelistMgr 记录了上次更新的帧数LastReplicationFrame和实际存放历史记录的变量RepChangelistState
> ```cpp
> class FReplicationChangelistMgr : public FNoncopyable
> {
>
> private:
>
>     uint32 LastReplicationFrame;
>     uint32 LastInitialReplicationFrame;
>
>     FRepChangelistState RepChangelistState;
> }
> ```


> [!note]- 实际存放历史记录的变量RepChangelistState记录了历史修改记录ChangeHistory和历史数据StaticBuffer
> ```cpp
> class FRepChangelistState : public FNoncopyable
> {
>
>     FRepChangedHistory ChangeHistory[MAX_CHANGE_HISTORY];
>     int32 HistoryStart;
>
>     int32 HistoryEnd;
>
>     FRepStateStaticBuffer StaticBuffer;
> }
> ```


### 历史数据--RepStateStaticBuffer

---

```cpp
class FRepChangelistState : public FNoncopyable
{
	FRepStateStaticBuffer StaticBuffer;
}
struct FRepStateStaticBuffer : public FNoncopyable
{
	TArray<uint8, TAlignedHeapAllocator<16>> Buffer;
	TSharedRef<const FRepLayout> RepLayout;
}
```

属性复制中，会存储了一份同步属性的历史数据(数据副本)，属性对比时会将属性当前值和历史数据比较，从而发现哪些属性发生了改变。FRepStateStaticBuffer 就是维护这个历史数据的。

> [!note]- 在创建属性历史状态数据FRepChangelistState实例时，会根据当时的复制属性数据创建首份历史数据(FRepLayout::CreateShadowBuffer)。
> > 💡 历史数据是根据FRepLayout里的FRepParentCmd数据构造的，所以只会存放需要属性复制的字段数据。
>
> ```cpp
> FRepChangelistState::FRepChangelistState(....)
>     : CustomDeltaChangelistState(InDeltaChangelistState)
>     , HistoryStart(0)
>     , HistoryEnd(0)
>     , CompareIndex(0)
>     , StaticBuffer(InRepLayout->CreateShadowBuffer(InSource))
>     {...}
>
> FRepStateStaticBuffer FRepLayout::CreateShadowBuffer(...) const
> {
>     FRepStateStaticBuffer ShadowData(AsShared());
>     if (!IsEmpty())
>     {
>         ...
>             InitRepStateStaticBuffer(ShadowData, Source);
>         ...
>     }
>     return ShadowData;
> }
>
> //初始历史数据
> void FRepLayout::InitRepStateStaticBuffer(...) const
> {
>     check(ShadowData.Buffer.Num() == 0);
>     ShadowData.Buffer.SetNumZeroed(ShadowDataBufferSize);
>     ConstructProperties(ShadowData);
>     CopyProperties(ShadowData, Source);
> }
>
> //根据FRepParentCmd里的字段构造默认历史数据
> void FRepLayout::ConstructProperties(...) const
> {
>     FRepShadowDataBuffer ShadowData = InShadowData.GetData();
>
>     // Construct all items
>     for (const FRepParentCmd& Parent : Parents)
>     {
>         if (Parent.ArrayIndex == 0)
>         {
>             Parent.Property->InitializeValue(ShadowData + Parent);
>         }
>     }
> }
>
> //根据FRepParentCmd里的字段将当前数据拷贝到历史数据中
> void FRepLayout::CopyProperties(...) const
> {
>     FRepShadowDataBuffer ShadowData = InShadowData.GetData();
>
>     // Init all items
>     for (const FRepParentCmd& Parent : Parents)
>     {
>         if (Parent.ArrayIndex == 0)
>         {
>             Parent.Property->CopyCompleteValue(ShadowData + Parent, Source + Parent);
>         }
>     }
> }
> ```


> [!note]- **在属性对比时会更新历史数据**
> > 💡 ShadowData是**ChangelistMgr里的历史数据**StaticBuffer**的引用**
>
> ```cpp
> static uint16 CompareProperties_r(...)
> {
>     if (SharedParams.bForceFail || 
>             !PropertiesAreIdentical(..))
>         {
>             //有修改了 更新历史数据ShadowData
>             StoreProperty(Cmd, ShadowData.Data, Data.Data);
>         }
> }
> ```


### 修改记录--ChangeHistory

---

ChangeHistorys是存放属性复制的历史修改记录，记录每次修改了哪几个字段(记录的字段的Handle,根据字段Handle可以获取字段最新数据)。对于同一个UObject实例所有的网络连接都共享同一份历史修改记录，但每个连接的同步进度并不是完全一致的，有的连接可能是每次变动都同步了，有的连接可能是在属性修改多次后才触发同步(比如中间暂停了同步或者断线重连)，所以需要一份历史修改记录跟当前连接保存的已经同步记录做对比，得出当前连接需要同步哪些变动记录。

```cpp
class FRepChangelistState : public FNoncopyable
{

	FRepChangedHistory ChangeHistory[MAX_CHANGE_HISTORY];
	
	int32 HistoryStart;
	
	int32 HistoryEnd;
	
	FRepStateStaticBuffer StaticBuffer;
}
```

FRepChangedHistory存放的是修改属性的字段对应的Handle，可以根据这个Handle查找到在
FRepLayoutCmd列表中的对应属性字段

```cpp
class FRepChangedHistory
{
	TArray<uint16> Changed;
}
```

历史记录采用了循环数组的实现，执行对比操作之前，会先找到一个空白的历史记录位置，将其引用传入对比操作进行填充，**在属性对比操作时，如果发现字段发生了变动，会将变动字段的Handle存填充到传入的历史修改记录中**。在填充完成之后，历史记录末端会挪到下一个空白位置，如果此时历史记录数组已经满了，**则将数组的第一个记录合并到第二个位置，空出第一个位置，最后一个位置绕到了第一个位置。**

```cpp
ERepLayoutResult FRepLayout::CompareProperties(...) const
{
	const int32 HistoryIndex = RepChangelistState->HistoryEnd % 
	FRepChangelistState::MAX_CHANGE_HISTORY;

	//找到历史记录的末尾位置(预留的首个空白记录)
	FRepChangedHistory& NewHistoryItem = RepChangelistState->ChangeHistory[HistoryIndex];
	TArray<uint16>& Changed = NewHistoryItem.Changed;
	Changed.Empty(1);
	
	//将空白记录引用 传入对比操作进行填充
	FComparePropertiesStackParams StackParams{
	...,
	...,
		Changed,
	...
	};
	
	...
	CompareParentProperties(SharedParams, StackParams);
	...
	
	//修改记录填充完毕了 末尾加一个记录截止的标记
	Changed.Add(0);

	// 末端历史记录 往后挪动下一个空白位置
	RepChangelistState->HistoryEnd++;
	
	**//当历史记录数组满了的时候进行将数合并操作
	//将数组的第一个记录合并到第二个位置 空出第一个位置 最后一个位置绕到了第一个位置(循环数组)**
	if ((RepChangelistState->HistoryEnd - RepChangelistState->HistoryStart) == 
	FRepChangelistState::MAX_CHANGE_HISTORY)
	{
		const int32 FirstHistoryIndex =
		RepChangelistState->HistoryStart % FRepChangelistState::MAX_CHANGE_HISTORY;
		
		RepChangelistState->HistoryStart++;
		
		const int32 SecondHistoryIndex = 
		RepChangelistState->HistoryStart % FRepChangelistState::MAX_CHANGE_HISTORY;

		TArray<uint16>& FirstChangelistRef = 
		RepChangelistState->ChangeHistory[FirstHistoryIndex].Changed;

		TArray<uint16> SecondChangelistCopy = 
		MoveTemp(RepChangelistState->ChangeHistory[SecondHistoryIndex].Changed);
		
		MergeChangeList(...);
	}
}

```

**对比操作填充修改记录**

```cpp
CompareProperties_r(..., Cmd.RelativeHandle - 1);

static uint16 CompareProperties_r(...,uint16 Handle)
{
		if (SharedParams.bForceFail || 
		!PropertiesAreIdentical(....))
		{
			StackParams.Changed.Add(Handle);
		}
}
```

属性对比结束后，**会将历史修改记录跟当前网络连接保留的同步记录进行一次对比合并操作，获取该连接当前需要同步哪些变动字段**(将不在同步记录中的修改合并到同步记录中)。

网络连接保留的同步记录中也保存了一份修改历史记录，之所以要保留一份列表是因为涉及到UDP发送时的丢包重发。当丢包时会从保留的修改记录中取出重发，如果没有丢包，则会在下一次移除已经发送的修改记录。

> [!note]- **每个网络连接都维护了一份同步记录**
> ```cpp
> class FObjectReplicator
> {
>     TUniquePtr<FRepState>  RepState;
> }
>
> class FRepState : public FNoncopyable
> {
>     TUniquePtr<FSendingRepState> SendingRepState;
> }
>
> class FSendingRepState : public FNoncopyable
> {
>     int32 HistoryStart;
>     int32 HistoryEnd;
>     FRepChangedHistory ChangeHistory[MAX_CHANGE_HISTORY];
> }
> ```


> [!note]- **连接同步记录跟历史修改记录的对比合并**
> ```cpp
> bool FObjectReplicator::ReplicateProperties_r(...)
> {
>  //属性复制时 带上当前连接保存的同步记录
>  RepLayout->ReplicateProperties(SendingRepState,....)
> }
>
> bool FRepLayout::ReplicateProperties(...) const
> {
>     if(RepState->LastChangelistIndex <= RepChangelistState->HistoryStart)
>     {
>         //连接保留的上次同步记录小于历史记录中的第一个记录(可能是在连接中首次同步)
>         RepState->LastChangelistIndex = RepChangelistState->HistoryStart;
>     }
>
>     //找个同步记录中的首个空白位置
>     const int32 PossibleNewHistoryIndex =
>      RepState->HistoryEnd % FSendingRepState::MAX_CHANGE_HISTORY;
>
>     FRepChangedHistory& PossibleNewHistoryItem = 
>     RepState->ChangeHistory[PossibleNewHistoryIndex];
>
>     TArray<uint16>& Changed = PossibleNewHistoryItem.Changed;
>
>     **//将历史修改记录跟当前网络连接保留的同步记录进行一次合并操作 
>     //将不在同步记录中的修改合并到同步记录中**
>     for (int32 i = RepState->LastChangelistIndex; 
>     i < RepChangelistState->HistoryEnd; ++i)
>     {
>         const int32 HistoryIndex = i % FRepChangelistState::MAX_CHANGE_HISTORY;
>
>         FRepChangedHistory& HistoryItem = 
>         RepChangelistState->ChangeHistory[HistoryIndex];
>
>         TArray<uint16> Temp = MoveTemp(Changed);
>         MergeChangeList(Data, HistoryItem.Changed, Temp, Changed);
>     }
>
>     //更新同步记录中 上传更新记录索引
>     RepState->LastChangelistIndex = RepChangelistState->HistoryEnd;
>     ....
>
>     //UpdateChangelistHistory是更新下同步记录里面的修该记录
>     //1.如果同步记录里有因为丢包需要重发的 本次合并下一起发送
>     //2.如果同步记录里的修改记录已经被确认接收了 则从列表移除
>     //3.如果同步记录列表满了 则触发下合并操作
>     if (Changed.Num() > 0 || RepState->NumNaks > 0 || bFlushPreOpenAckHistory)
>     {
>         RepState->HistoryEnd++;
>         UpdateChangelistHistory(....);
>     }
>     else
>     {
>         UpdateChangelistHistory(...);
>         return false;
>     }
>
>     ...
>     if (Changed.Num() > 0)
>     {
>         //发送变动字段数据
>         SendProperties(...);
>     }
> }
>
> ```


> [!note]- **更新连接中的同步修改记录**
> ```cpp
>
> //UpdateChangelistHistory是更新下同步记录里面的修该记录
> //1.如果同步记录里有因为丢包需要重发的 本次合并下一起发送
> //2.如果同步记录里的修改记录已经被确认接收了 则从列表移除
> //3.如果同步记录列表满了 则触发下合并操作
> void FRepLayout::UpdateChangelistHistory(...) const
> {
>     //列表满了
>     const bool bDumpHistory = HistoryCount == FSendingRepState::MAX_CHANGE_HISTORY;
>
>     ...
>     for (int32 i = RepState->HistoryStart; i < RepState->HistoryEnd; i++)
>     {
>         const int32 HistoryIndex = i % FSendingRepState::MAX_CHANGE_HISTORY;
>
>         FRepChangedHistory& HistoryItem = RepState->ChangeHistory[HistoryIndex];
>
>     ...
>
>         if (AckPacketId >= HistoryItem.OutPacketIdRange.Last//记录已经被确认接收了
>         || HistoryItem.Resend //需要重发
>         || bDumpHistory //列表满了
>         )
>         {
>             if (HistoryItem.Resend || bDumpHistory)
>             {
>                 //需要重发和列表满的情况下 合并记录
>                 TArray<uint16> Temp = MoveTemp(*OutMerged);
>                 MergeChangeList(Data, HistoryItem.Changed, Temp, *OutMerged);
>
>                 if (HistoryItem.Resend)
>                 {
>                     //需要重发情况下 合并后 重复计数-1
>                     RepState->NumNaks--;
>                 }
>             }
>
>             //将记录从列表移除
>             HistoryItem.Reset();
>             RepState->HistoryStart++;
>         }
>     }
>     ...
> }
> ```


# **UObject的网络映射**

---

UPackageMapClient用于处理客户端与服务器之间的包（Package）映射。这个类负责跟踪客户端和服务器之间的对象和包的映射关系，以确保正确的对象在客户端和服务器之间同步。主要用于网络游戏中的对象同步和网络通讯。

实际上就是对UObject实例的网络映射，确保UObject实例在客户端和服务器之间能正确的对应上。UE会为每个需要进行网络同步的UObject分配一个唯一的NetGUID。客户端和服务器根据这个唯一的NetGUID进行映射，除了NetGUID还需要包（Package）信息在客户端查找或者创建UObject实例进行NetGUID的绑定。

DS端跟客户端进行网络同步的UObject，分为两种:**静态创建和动态创建**

## **静态创建**

---

分别在DS端和客户端各自执行创建逻辑，但需要支持网络同步的。比如场景内摆放的Actor，支持网络复制的Actor在构造函数或者蓝图挂载的SubObject(组件或者其他关联UObject)、直接用CDO的UObject。这种在DS端和客户端加载场景或创建Actor时两端都会各自执行创建逻辑，而且可以根据包信息(Outer)定位到UObject实例的(*查到场景或者对应的Actor实例再根据包信息定位UObject实例*)， 在首次同步时，因为已经创建了，只需要根据消息包附带的包信息(资产路径信息)进行NetGUID的绑定。

> 💡 静态创建的UObject 还有一种是情况是触发首次网络同步是客户端通过RPC进行传递(比如客户端上传的RPC带了一个场景内的Actor指针或者Actor的组件指针)，这种情况下客户上传的消息包附带的UObject是没有NetGUID(**NetGUID.IsDefault**)（NetGUID只会在DS端统一分配）。这时候客户端需要附带路径信息，在DS端接受到之后根据路径信息查找对应的UObject实例同时为其分配和绑定GUID。

> 💡 只在客户端创建的Actor是无法进行网络同步的

根据路径信息(包信息)查找的UObject实例绑定GUID，仅限于满足条件的(IsNameStableForNetworking)

```cpp
bool UObject::IsNameStableForNetworking() const
{
	return HasAnyFlags(RF_WasLoaded | RF_DefaultSubObject 
	| RF_ClassDefaultObject) || IsNative() || IsDefaultSubobject();
}
```

- 场景内摆放的（RF_WasLoaded ）
- Actor静态创建或者构造函数创建的组件和其他UObject（DefaultSubobject）
- CDO(RF_ClassDefaultObject)
- UClass（ IsNative）

## **动态创建**

---

在DS端创建然后通过网络通信在客户端创建。比如Actor的创建，Actor上在构造函数之外创建的支持网络复制的SubObject。这种在首次收到同步消息包后，客户端需要根据消息附带的包信息(资产路径信息)创建对应的UObject并绑定NetGUID(SubObject可能在客户端也提前创建了)。

对于Actor上动态创建的SubObject(不是直接在蓝图里挂载或者构造函数里创建的)，如果需要通过网络传递UObject指针，需要开启组件为可复制的，非组件的UObject需要手动加入到复制列表中去(通过ReplicateSubobjects接口添加)，否则DS不会为其分配NetGUID，无法进行网络传输。对于SubObject，只会为静态创建的和开启网络复制的分配NetGUID。

静态创建的SubObject的可以不开启网络复制也可以通过网络传递UObject指针，但是需要标记为可复制的，才能支持其上面的属性进行网络复制。

## NetGUID的分配绑定

---

> [!note]- NetGUID的分配绑定
> ```cpp
> bool UPackageMapClient::SerializeObject(...)
> {
>
>     if (Ar.IsSaving())
>     {
>         //UObject的序列化(写入)
>
>         //先获取一个唯一的NetGUID(未分配就分配一个)
>         FNetworkGUID NetGUID = GuidCache->GetOrAssignNetGUID( Object );
>         //将NetGUID信息 写入消息包 
>         //如果是首次同步或者NetGUID未分配(客户端触发) 则还需要写入包信息(路径信息)
>         InternalWriteObject( Ar, NetGUID, Object, TEXT( "" ), NULL );
>     }
>     else if (Ar.IsLoading())
>     {
>         //UObject的反序列化(读取)
>
>         //根据传入的NetGUID 查找对应的UObject实例
>         //如果NetGUID未绑定UObject实例 则根据传入的路径信息 查找实例并绑定
>         //如果UObject未创建则 触发创建逻辑 并绑定UObject实例
>         //如果NetGUID是未分配的(客户端触发) 则分配一个并绑定UObject实例
>         FNetworkGUID NetGUID;
>         NetGUID = InternalLoadObject(Ar, Object, 0);
>     }
> }
> ```


- 写入包信息(路径信息)
如果是首次同步或者NetGUID未分配(客户端触发) 则还需要写入包信息(路径信息)
    
```cpp
    void UPackageMapClient::InternalWriteObject(...)
    {
    	 //写入NetGUID
    		Ar << NetGUID;
    		
    	if (NetGUID.IsDefault())
    	{
    		//客户端触发的 序列化 如果尚未分配NetGUID 则需要附带路径信息
    		check(!IsNetGUIDAuthority());
    		ExportFlags.bHasPath = 1;
    
    		Ar << ExportFlags.Value;
    	}
    	else if (GuidCache->IsExportingNetGUIDBunch)
    	{
    		//DS端触发的序列化 如果 NetGUID是首次发往客户端 则需要附带路径信息
    		if (Object != nullptr)
    		{
    			ExportFlags.bHasPath = ShouldSendFullPath(Object, NetGUID) ? 1 : 0;
    		}
    	}
    	
    	
    	if (ExportFlags.bHasPath)
    	{
    	  //有Outer需要带上Outer的信息才能根据路径信息定位实例
    		FNetworkGUID OuterNetGUID = GuidCache->GetOrAssignNetGUID(ObjectOuter);
    		InternalWriteObject(Ar, OuterNetGUID, ObjectOuter, TEXT( "" ), nullptr);
    		
    		//带上路径信息
    		Ar << ObjectPathName;
    	}
    }
    
    bool UPackageMapClient::ShouldSendFullPath(...)
    {
    
    	if ( !NetGUID.IsValid() )
    	{
    		return false;
    	}
    
    	if ( !Object->IsNameStableForNetworking() )
    	{
    		return false;
    	}
    
    	if ( NetGUID.IsDefault() )
    	{
    		return true;
    	}
    
    	return !NetGUIDHasBeenAckd( NetGUID );
    }
```
    

> [!note]- 根据NetGUID或者包信息绑定对应的UObject实例
> ```cpp
> void UPackageMapClient::InternalLoadObject(...)
> {
>     //根据NetGUID信息查找UObject实例
>     //如果NetGUID未绑定UObject实例 则根据传入的路径信息 查找实例并绑定
>     //如果UObject未创建则 触发创建逻辑 并绑定UObject实例
>     //如果NetGUID是未分配的(客户端触发)的逻辑在后面单独处理
>     if ( NetGUID.IsValid() && !NetGUID.IsDefault() )
>     {
>         Object = GetObjectFromNetGUID( NetGUID, GuidCache->IsExportingNetGUIDBunch );
>     }
>
>     if (ExportFlags.bHasPath )
>     {
>         UObject* ObjOuter = NULL;
>         if (NetGUID.IsDefault())
>         {
>             //如果NetGUID是未分配的(客户端触发)  
>             //则根据传入的路径信息 查找实例并未其分配一个NetGUID
>             ...
>         }
>     }
>
> }
>
> UObject* FNetGUIDCache::GetObjectFromNetGUID(...)
> {
>
>     FNetGuidCacheObject * CacheObjectPtr = ObjectLookup.Find( NetGUID );
>     UObject* Object = CacheObjectPtr->Object.Get();
>     if ( Object != NULL )
>     {
>         //直接根据NetGUID 查找到了
>         return Object;
>     }
>
>     UObject* ObjOuter = NULL;
>
>     if ( CacheObjectPtr->OuterGUID.IsValid() )
>     {
>         ObjOuter = GetObjectFromNetGUID(CacheObjectPtr->OuterGUID, bIgnoreMustBeMapped );
>     }
>     //根据Outer和路径信息定位UObject实例
>     Object = FindObjectFast<UObject>(ObjOuter, CacheObjectPtr->PathName);
>
>     //直接从包体加载创建的
>     ....
> }
> ```
>
>
> > 💡 如果属性同步中有某个 UObject* 类型的变量尚未同步的客户端,则会先放入
> > UNetDriver的UnmappedReplicators，在后续Tick会尝试再次通过
> > UpdateUnmappedObjects在客户端进行赋值操作。 
> >
> > 比如同步属性StructA 有一个变量 AActor* B,在该属性同步到客户端时B尚未创建出来，此时客户端的StructA中的变量B赋值就失败了，此时就会先存放到UnmappedReplicators，然后再后续Tick中尝试再次赋值。赋值成功的同时OnRep函数也会再次调用。
>
> > 💡
> >
> > 对于动态创建的Actor需要走创建Actor的流程和额外一些操作，是通过SerializeNewActor进行操作，里面再调用了SerializeObject。

```cpp
bool UPackageMapClient::SerializeNewActor(...)
{
	SerializeObject(Ar, AActor::StaticClass(), NewObj, &NetGUID);
	
	Actor = Cast<AActor>(NewObj);
}
```

# 网络序列化和反序列化

---

UE提供了一套序列化和反序列机制，FArchive是所有序列化和反序列化的基类。

FNetBitWriter/FNetBitReader则是专门用于网络序列化与反序列化的类。分别继承自FBitWriter/FBitReader。在序列化成二进制流时，支持按位进行压缩，减少传输数据量，同时重载了部分类型的序列化操作。

```cpp
class FNetBitWriter : public FBitWriter
{
	//重载了部分类型的序列化
	COREUOBJECT_API virtual FArchive& operator<<(FName& Name) override;
	COREUOBJECT_API virtual FArchive& operator<<(UObject*& Object) override;
	COREUOBJECT_API virtual FArchive& operator<<(FSoftObjectPath& Value) override;
	COREUOBJECT_API virtual FArchive& operator<<(FSoftObjectPtr& Value) override;
	COREUOBJECT_API virtual FArchive& operator<<(FObjectPtr& Value) override;
	COREUOBJECT_API virtual FArchive& operator<<(struct FWeakObjectPtr& Value) override;
}

class FNetBitReader : public FBitReader
{
	//重载了部分类型的序列化
	COREUOBJECT_API virtual FArchive& operator<<(FName& Name) override;
	COREUOBJECT_API virtual FArchive& operator<<(UObject*& Object) override;
	COREUOBJECT_API virtual FArchive& operator<<(FSoftObjectPath& Value) override;
	COREUOBJECT_API virtual FArchive& operator<<(FSoftObjectPtr& Value) override;
	COREUOBJECT_API virtual FArchive& operator<<(FObjectPtr& Value) override;
	COREUOBJECT_API virtual FArchive& operator<<(struct FWeakObjectPtr& Value) override;
}
```

**序列化成二进制字节流**

```cpp
struct FBitWriter : public FBitArchive
{
	//将数据序列化成二进制字节流
	CORE_API virtual void SerializeBits( void* Src, int64 LengthBits ) override;

	//压缩序列化int数值(尽可能减少占用的Bit位)
	CORE_API virtual void SerializeInt(uint32& Value, uint32 Max) override;
	CORE_API virtual void SerializeIntPacked(uint32& Value) override;

private:
	//二进制字节流
	TArray<uint8> Buffer;
	//字节数组中有效的(写人的)Bit位数量
	int64   Num;
	//字节数组中最大的支持的bit位数量
	int64   Max;
}
```

FBitWriter::SerializeBits这个接口将数据转换成二进制，然后按位存放的字节缓存中(Buffer)

```cpp
//这个接口 将数据转换成二进制 然后按位存放的缓存中 比如8 二进制是 1000 在Buff 里面占4个bit位
//Buffer 是一个uint8的数组(字节数组)
//num就是在这一长串二进制已经用到bit位索引(从0开始)

extern const uint8 GShift[8]={0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80};
extern const uint8 GMask [8]={0x00,0x01,0x03,0x07,0x0f,0x1f,0x3f,0x7f};
TArray<uint8> Buffer;

void FBitWriter::SerializeBits( void* Src, int64 LengthBits )
{
	if( AllowAppend(LengthBits) )
	{
		
		if( LengthBits == 1 )
		{
			//就是一个bit位 直接找到bit位的位置放进去 num++ 表示缓存中的一个bit位被占用了
			//如果bit位的值是0 那就不需要对应bit位的二进制值(未使用的位默认就是0) 直接num+1就行
			//如果bit位的值是1 需要找到对应的bit位 将此处的bit位二进制值改为1
			if( ((uint8*)Src)[0] & 0x01 )
				//Num>>3 等同于num/8 查询当前需要占用的bit位在二进制的第几段
				//每段有8个bit位 GShift[Num&7] 可以知道该段哪个bit位还没被占用
				//|操作就是将找到的bit位改写成1
				Buffer[Num>>3] |= GShift[Num&7];
			Num++;
		}
		else
		{
			//更复杂的两串二进制bit位拷贝
			//可以指定从Src二进制的bit位索引为0的位置开始拷贝，需要拷贝LengthBits个bit位
			//放到Buffer二进制串中Bit位索引为Num的位置
			appBitsCpy(Buffer.GetData(), Num, (uint8*)Src, 0, LengthBits);
			Num += LengthBits;
		}
	}
	else
	{
		SetOverflowed(LengthBits);
	}
}
```

按字节(8Bit)拷贝二进制串

```cpp

//两串二进制数据 每8位分为一段(一个字节8位) 
//可以从Src二进制的Bit位索引为SrcBit的位置开始拷贝，需要拷贝BitCount个Bit位
//放到Dest二进制串中索引为DestBit的位置
//**索引位置从右到左(低位到高位)**
void appBitsCpy( uint8* Dest, int32 DestBit, uint8* Src, int32 SrcBit, int32 BitCount )
{
	if( BitCount==0 ) return;

	
	if( BitCount <= 8 ) 
	{
		//如果BitCount<=8  则表示最多需要用到Dest中的两段数据
		//就算操作起始bit位不是从当前段索引0开始 也就最多跨到下一段
	
	 
	 
			
	 //Src二进制段   操作的数据段索引 从第XX段 到 第XX段
		uint32 SrcIndex	   = SrcBit /8;
		uint32 LastSrc	   =( SrcBit +BitCount-1 )/8;  
	
		//这里&7 可以得到当前段操作起始bit位索引 (等同于%8)
		uint32 ShiftSrc     = SrcBit & 7; 
	
		

		uint32 Accu;		

		//如果Src操作的二进制段是同一段 表明直接操作当前段 直接取当前段的数据操作就行了
		//比如操作的二进制数据段是 1111 0011 拷贝6个Bit位 起始索引是2 正好不用跨段 
		//左移两位 丢掉两个低位  得到新数据段 0011 1100(从右到左)
		
		//如果要操作的数据段不是同一段 则需要重新第一段取出从起始索引到末尾的bit位 
		//再从第二段开始的位置取剩下的bit位
		//比如操作的二进制数据段是 1111 0011(第二段) 1100 0000(第一段) 拷贝6个Bit位 起始索引是5 
		//则第一段只能取3位 需要再从第二段再取3位
		//第一段右移5位 保留高3位  得到数据段 0000 0110
		//第二段左移3位 将空出来的低3位留给第一段截取的bit位  得到数据段 1001 1000
		//两段| 运算 等到字符串 1001 1110
		
		if( SrcIndex == LastSrc )
			Accu = (Src[SrcIndex] >> ShiftSrc); 
		else
			Accu =( (Src[SrcIndex] >> ShiftSrc) | (Src[LastSrc ] << (8-ShiftSrc)) );			

	 //Dest二进制段 操作的数据段索引 从第XX段 到 第XX段
		uint32 DestIndex	 = DestBit/8;
		uint32 LastDest	   =( DestBit+BitCount-1 )/8; 
		
		//这里&7 可以得到当前段操作起始bit位索引 (等同于%8)
		uint32 ShiftDest    = DestBit & 7;
			
		//Dest数据段操作**起始索引的掩码** 
		//从起始索引到数据段的结束索引(最左侧) 都用掩码标记下 用1标记
		//左移操作将不需要操作的位置在右侧标记成0
		uint32 FirstMask    = 0xFF << ShiftDest;  
		
		//Dest数据段操作**终点索引掩码**(可能是第一段 也可能是第二段)
		//从数据段的起始位置(最右侧)到操作的终止索引位置 都标记下 用0标记
		//(DestBit + BitCount-1) & 7 得到的操作的终点bit位在数据段中的索引 
		//左移操作将需要操作的bit位在右侧 预留出来
		
		//最少需要操作一位所以直接用0xFE
		uint32 LastMask     = 0xFE << ((DestBit + BitCount-1) & 7) ; 
		
		//1.用掩码将Dest数据段需要操作的bit位置成0(清空)
		//2.来源数据段初步截取的数据段Accu 先通过左移操作跟Dest数据段 
		//最左侧对齐 然后通过掩码取反 获取最终截取的bit位
		//3.|运算合并
		
		if( DestIndex == LastDest )
		{
		 //如果只操作一段数据段 则直接将两段掩码合并下 需要做下取反操作
			uint32 MultiMask = FirstMask & ~LastMask;
			
			Dest[DestIndex] = ( ( Dest[DestIndex] & ~MultiMask ) | 
			((Accu << ShiftDest) & MultiMask) );		
		}
		else
		{	
			//从第一段截取bit位	
			Dest[DestIndex] = (uint8)( ( Dest[DestIndex] & ~FirstMask ) | 
			(( Accu << ShiftDest) & FirstMask) ) ;
			//从第二段截取bit位
			Dest[LastDest ] = (uint8)( ( Dest[LastDest ] & LastMask  )  | 
			(( Accu >> (8-ShiftDest)) & ~LastMask) ) ;
		}

		return;
	}

	// 跨域多个数据段 更复杂的运算
	uint32 DestIndex		= DestBit/8;
	uint32 FirstSrcMask  = 0xFF << ( DestBit & 7);  
	uint32 LastDest		= ( DestBit+BitCount )/8; 
	uint32 LastSrcMask   = 0xFF << ((DestBit + BitCount) & 7); 
	uint32 SrcIndex		= SrcBit/8;
	uint32 LastSrc		= ( SrcBit+BitCount )/8;  
	int32   ShiftCount    = (DestBit & 7) - (SrcBit & 7); 
	int32   DestLoop      = LastDest-DestIndex; 
	int32   SrcLoop       = LastSrc -SrcIndex;  
	uint32 FullLoop;
	uint32 BitAccu;

	// Lead-in needs to read 1 or 2 source bytes depending on alignment.
	if( ShiftCount>=0 )
	{
		FullLoop  = FMath::Max(DestLoop, SrcLoop);  
		BitAccu   = Src[SrcIndex] << ShiftCount; 
		ShiftCount += 8; //prepare for the inner loop.
	}
	else
	{
		ShiftCount +=8; // turn shifts -7..-1 into +1..+7
		FullLoop  = FMath::Max(DestLoop, SrcLoop-1);  
		BitAccu   = Src[SrcIndex] << ShiftCount; 
		SrcIndex++;		
		ShiftCount += 8; // Prepare for inner loop.  
		BitAccu = ( ( (uint32)Src[SrcIndex] << ShiftCount ) + (BitAccu)) >> 8; 
	}

	// Lead-in - first copy.
	Dest[DestIndex] = (uint8) (( BitAccu & FirstSrcMask) | ( Dest[DestIndex] & 
	 ~FirstSrcMask ) );
	 
	SrcIndex++;
	DestIndex++;

	// Fast inner loop. 
	for(; FullLoop>1; FullLoop--) 
	{   // ShiftCount ranges from 8 to 15 - all reads are relevant.
		BitAccu = (( (uint32)Src[SrcIndex] << ShiftCount ) + (BitAccu)) >> 8; 
		SrcIndex++;
		Dest[DestIndex] = (uint8) BitAccu;  // Copy low 8 bits.
		DestIndex++;		
	}

	// Lead-out. 
	if( LastSrcMask != 0xFF) 
	{
		if ((uint32)(SrcBit+BitCount-1)/8 == SrcIndex ) // Last legal byte ?
		{
			BitAccu = ( ( (uint32)Src[SrcIndex] << ShiftCount ) + (BitAccu)) >> 8; 
		}
		else
		{
			BitAccu = BitAccu >> 8; 
		}		

		Dest[DestIndex] = (uint8)( ( Dest[DestIndex] & LastSrcMask ) |
		 (BitAccu & ~LastSrcMask) );  		
	}	
}
```