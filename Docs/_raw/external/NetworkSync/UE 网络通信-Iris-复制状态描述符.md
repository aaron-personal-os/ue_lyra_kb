# 概述

---

**复制状态描述符（ReplicationStateDescriptor）** 基于类型的反射数据构造，描述复制对象的复制字段(包括 RPC的参数列表字段)内存偏移、内存大小、怎么复制(量化、序列化操作等）。

其中包括：

- 内存布局(内存偏移)
- 序列化器(NetSerializer)
- 条件过滤(ELifetimeCondition)
- 优先级安排

**复制对象(UObject)可能存在一个或者多个复制状态描述符(会将复制字段进行分组)**

**每个复制状态描述符可以描述一个或者多个复制字段**

```cpp
struct FReplicationStateDescriptor
{
	**//描述复制字段的内存偏移**
	//(包括副本数据内存偏移和复制系统量化数据的内存偏移)
	//有了内存偏移就能根据复制对象实例的起始地址获取属性字段的内存地址(指针) 
	//就可以取出对应的值了
	const FReplicationStateMemberDescriptor* MemberDescriptors;
	
	**//描述复制字段的网络序列化器**(NetSerializer 描述怎么量化、序列化、对比)
	//字段的序列化器这里的NetSerializerConfig中
	const FReplicationStateMemberSerializerDescriptor* 
	MemberSerializerDescriptors;
	
	**//RPC 函数的描述(包括函数指针和函数参数列表的描述)**
	const FReplicationStateMemberFunctionDescriptor* MemberFunctionDescriptors;
}	
```

> 💡
>
> 描述复制中的MemberDescriptors、MemberSerializerDescriptors可以视为一个数组的起始地址。通过这两个属性可以找到复制状态描述符描述的多个字段的内存偏移信息和对应的序列化器(NetSerializer)，在复制时就可以对其中的字段进行复制操作了。
>
> 序列化器(NetSerializer)执行对比、量化、序列化等操作，内存偏移信息定位内存地址，获取字段值

> 💡
>
> Map和Set类型的字段不支持网络复制

> 💡
>
> MemberFunctionDescriptors可以视为一个数组的起始地址，包含了一个或者多个的RPC函数描述，每份描述中包含一个参数列表的状态描述符和函数的反射信息

**复制状态描述符的创建流程**

![创建堆栈](http://pic.xyyxr.cn/20260504161046197.png)

创建堆栈

当一个复制对象UObject注册到复制系统时(StartReplicatingNetObject),会为其在复制系统生成一个对应的 NetObject，此时需要:

- 为复制对象UObject和对应的NetObject生成一个**复制实例协议(Replication Instance Protocol)**让两者能互相转化，交换数据。
- 复制实例协议其实就是各个**复制片段(ReplicationFragment)**的集合
- 复制片段的包含了**复制状态描述符(**还有复制对象实例的指针和副本数据指针)
- **创建复制片段时需要先创建对应的复制状态描述符**(CreateDescriptorsForClass)

> 💡
>
> 为 UObject 创建复制状态描述符时 会创建一个或者多个(复制字段会分成多组，每组创建一个，所有RPC函数创建一个,每个 FastArray 类型的单独创建一个)，每个复制状态描述符对应一个复制片段。

```cpp
FReplicationFragmentUtil::CreateAndRegisterFragmentsForObject(...)
{
	FReplicationStateDescriptorBuilder::FResult Result;
	//为 UObject 创建复制状态描述符(一个或者多个)
	FReplicationStateDescriptorBuilder::CreateDescriptorsForClass(...);
	
	//为每个复制状态描述符创建**复制片段(ReplicationFragment)**
	for (TRefCountPtr<const FReplicationStateDescriptor>& Desc : Result)
	{
		if (Desc->CreateAndRegisterReplicationFragmentFunction)
		{
			Fragment = Desc->CreateAndRegisterReplicationFragmentFunction(...);
		}
		else
		{
			Fragment = FPropertyReplicationFragment::CreateAndRegisterFragment(...);
		}
	}

}
```

**相同类型共用一组状态描述符**

```cpp
//一个类型对应一个或者多个描述符(UObject 类型就可能对应多个)
class FReplicationStateDescriptorRegistry
{
	FClassToDescriptorMap RegisteredDescriptorsMap;
}

if (Parameters.DescriptorRegistry)
	{	
		if (... Result = Parameters.DescriptorRegistry->Find(Property))
		{
			return (*Result)[0];
		}
	}
	
	
```

# UObject类型描述符

---

UObject类型(复制对象)一般对应多个复制状态描述符，按类型(Functions、InitOnly、LifetimeConditionals、State)将复制内容进行分组。

```cpp
static constexpr FPropertyReplicationStateType InternalPropertyReplicationStateTypes[] = 
{
	{ TEXT("_Functions"), },
	{ TEXT("_InitOnly"), },
	{ TEXT("_LifetimeConditionals"), },
	{ TEXT("_State"), },
};
```

- Functions-RPC函数
- InitOnly-只在初始时复制的字段
- LifetimeConditionals-按条件复制的字段
- State-兜底的

> 💡
>
> 每组分别创建一个对应的状态描述符

> 💡
>
> 每个自定义复制片段的字段(FastArray)单独创建一个的状态描述符

> 💡
>
> 每个状态描述符有一个或者多个复制字段

## 创建不同分组的描述符

---

当为一个复制对象(UObject)创建描述符时，会先根据类型(Functions、InitOnly、LifetimeConditionals、State)先分组，创建PropertyReplicationStateDescriptorBuilder数组，每组创建的ReplicationStateDescriptor对应不同字段或函数的复制状态描述符。

> [!note]- 代码分析
> ```cpp
> FReplicationStateDescriptorBuilder::CreateDescriptorsForClass(..)
> {
>         constexpr uint32 BuilderTypeCount = 
>         UE_ARRAY_COUNT(InternalPropertyReplicationStateTypes);
>
>         //创建分组
>         FPropertyReplicationStateDescriptorBuilder Builders[BuilderTypeCount];
>
>
>         //按属性字段的类型进行分组
>         for (const FRepRecord& RepRecord : InObjectClass->ClassReps)
>         {
>                     //InitOnly
>                     if (EnumHasAnyFlags(MemberProperty.Traits, 
>                     EMemberPropertyTraits::InitOnly))
>                     {
>                         Builders[InitPropertyReplicationStateBuilderIndex].
>                         AddMemberProperty(MemberProperty);
>                     }
>
>                     //LifetimeConditionals
>                     if (EnumHasAnyFlags(MemberProperty.Traits, 
>                     EMemberPropertyTraits::HasLifetimeConditionals))
>                     {
>                         Builders[LifetimeConditionalsReplicationStateBuilderIndex].
>                         AddMemberProperty(MemberProperty);
>                     }
>
>                     //兜底的
>                     if (!EnumHasAnyFlags(MemberProperty.Traits, 
>                     EMemberPropertyTraits::InitOnly | ConditionTraits))
>                     {
>                         Builders[RegularPropertyReplicationStateBuilderIndex].
>                         AddMemberProperty(MemberProperty);
>                     }
>             }
>
>             //RPC函数(包括父类的)
>             Builder = Builders[FunctionsPropertyReplicationStateBuilderIndex];
>             for (...)
>             {
>                 for (const UField* NetField : MakeArrayView(CurrentClass->NetFields))
>                 {
>                     if (const UFunction* Function = Cast<UFunction>(NetField))
>                     {
>                         MemberFunction.Function = Function;
>                         Builder.AddMemberFunction(MemberFunction);
>                     }
>                 }
>             }
>
>
>             //创建所有分组的ReplicationStateDescriptor
>             for (uint32 BuilderTypeIndex = 0; 
>             BuilderTypeIndex < BuilderTypeCount; 
>             ++BuilderTypeIndex)
>             {
>                 if (Builders[BuilderTypeIndex].HasDataToBuild())
>                 {
>
>                     Descriptor = Builders[BuilderTypeIndex].Build(..);
>                     CreatedDescriptors.Add(Descriptor);
>                 }
>             }
>
> }
> ```


## 创建自定义复制片段的描述符

---

复制对象(UObject) 自定义复制片段的属性字段(比如 FastArray)，是每个字段单独创建一个ReplicationStateDescriptor来描述

> [!note]- 代码分析
> ```cpp
> FReplicationStateDescriptorBuilder::CreateDescriptorForStruct()
> {
>     for (const FRepRecord& RepRecord : InObjectClass->ClassReps)
>     {
>                 //单独实现自定义复制片段的属性字段(FastArray)
>                 if (MemberProperty.CreateAndRegisterReplicationFragmentFunction)
>                 {
>                     CustomProperties.Add(MemberProperty);
>                     continue;
>                 }
>         }
>
>
>     //为自定义复制片段的属性字段单独创建一个ReplicationStateDescriptor
>     for (uint32 CustomPropertyIt = 0, 
>         CustomArrayPropertyEndIt = CustomProperties.Num(); 
>         CustomPropertyIt != CustomArrayPropertyEndIt; ++CustomPropertyIt)
>     {
>
>         Builder.AddMemberProperty(MemberProperty);
>         Descriptor = Builder.Build();
>         CreatedDescriptors.Add(Descriptor);
>     }
>
> }
> ```


# 复合类型-Struct类型描述符

---

```cpp
enum class EStructNetSerializerType : unsigned
{
	Struct,
	Custom,
	DerivedFromCustom,
};
```

Struct类型的复制字段分为三种

- Struct：类型没有实现自定义序列化器(NetSerializer)，用默认的FStructNetSerializer
- Custom：类型实现了自己的自定义序列化器(NetSerializer)
- DerivedFromCustom：类型自己没创建自定义序列化器(NetSerializer)，但其中有个父类创建了

根据三种类型创建描述符时的逻辑不一致

## 默认序列化器类型

---

Struct类型没有实现自定义序列化器(NetSerializer)，用默认的FStructNetSerializer，会为字段创建一个嵌套的子状态描述符(递归展开），子状态描述符用于描述Struct内部复制字段

```cpp
void FPropertyReplicationStateDescriptorBuilder::BuildMemberCache(..)
{
	for (FMemberProperty& Member : Members)
	{
		//Struct类型使用默认的FStructNetSerializer
		if (IsStructNetSerializer(Serializer))
		{
			//触发递归展开
			CurrentCacheEntry->Descriptor = 
			GetDescriptorForStructProperty(Member, DescriptorRegistry);
		}
	}
}
```

> 💡
>
> 创建子状态描述符描述Struct内部的复制字段

```cpp
FReplicationStateDescriptorBuilder::CreateDescriptorForStruct(...)
{
...
	{
	...
	for (...It(InStruct, EFieldIteratorFlags::IncludeSuper); It; ++It)
		{
			//跳过不复制的字段
			if (EnumHasAnyFlags(Property->PropertyFlags, EPropertyFlags::CPF_RepSkip))
			{
				...
				continue;
			}

			//将需要复制的字段加入描述符的成员列表
			if (FPropertyReplicationStateDescriptorBuilder::
			IsSupportedProperty(MemberProperty, Property))
			{
			...
				Builder.AddMemberProperty(MemberProperty);
			...
			}
	...
	}
...	
}
```

> 💡
>
> 嵌套的子状态描述符会存放在FStructNetSerializerConfi

```cpp
USTRUCT()
struct FStructNetSerializerConfig : public FNetSerializerConfig
{
	//嵌套的子状态描述符
	TRefCountPtr<const UE::Net::FReplicationStateDescriptor> StateDescriptor;
};

FPropertyReplicationStateDescriptorBuilder::BuildMemberSerializerConfigs(...)
{
...
	for (const FMemberProperty& Member : Members)
	{
	...
			if (IsStructNetSerializer(MemberCacheEntry->Serializer))
			{
				FStructNetSerializerConfig* SerializerConfig = 
				new (SerializerConfigBuffer) FStructNetSerializerConfig();
				
				SerializerConfig->StateDescriptor = MemberCacheEntry->Descriptor;
				
				MemberSerializerDescriptor->SerializerConfig = SerializerConfig;
			}
	...
	}
...
}
	
```

**示例**

```cpp
class A:public UObject
{
	int a1;
	struct B a2;
	int a3
}

struct B
{
	int b1;
	int b2;
	struct C b3;
}

struct C
{
	int c1;
	int c2;
	int c3;
}
```

![嵌套的子状态描述符递归展开](http://pic.xyyxr.cn/20260504161046198.png)

嵌套的子状态描述符递归展开

## 实现了自定义序列化器的类型

---

Struct类型如果实现了自定义序列化器，那个这个类型的字段会被视为跟int、float类型一样的，不会再为内部的字段创建嵌套的子描述符。

```cpp
void FPropertyReplicationStateDescriptorBuilder::BuildMemberCache(..)
{
	for (FMemberProperty& Member : Members)
	{
		//Struct类型使用默认的FStructNetSerializer
		if (IsStructNetSerializer(Serializer))
		{
			//触发递归展开
			...
		}
		else if (Member.Property)
		{
			//Struct类型如果实现了自定义序列化器,类型的字段会被视为跟int、float类型一样的 
			//执行到这里 不会为内部的字段创建嵌套的子描述符
		}
	}
}
```

序列化器的所需操作都需要自己在自定义序列化器自己实现，内部的每个字段该如何量化、序列化都需要单独创建

这种情况下对于Struct内还嵌套的复合型字段(FVector、数组、其他类型Struct)时，处理逻辑就有点复杂，Iris提供了两种解决方案参考。

> [!note]- 一种是参照FGameplayEffectContextNetSerializer实现
> > 💡
> >
> >     这种解决方案是为这个类型的Struct手动创建一个使用默认Struct序列化器类型的状态描述符(上面那种)，这个手动创建的状态描述符有一个嵌套的子状态描述符，能获取内部复制字段的内存偏移和序列化器。
> >
> >     这种方案即可以在自定义序列化器插入自己的逻辑优化复制效率，又可以复用默认Struct序列化器类型的逻辑，降低代码复杂度，适合Struct字段比较复杂的。
>
> ```cpp
> //类型自定义序列化器注册完成后会执行到这
> void FGameplayEffectContextNetSerializer::FNetSerializerRegistryDelegates::
> OnPostFreezeNetSerializerRegistry()
> {
>  ...
>         FReplicationStateDescriptorBuilder::FParameters Params;
>         //不检测是否有自定义序列化器 本次创建视为用默认的Struct序列化器
>         Params.SkipCheckForCustomNetSerializerForStruct = true;
>
>          //手动创建一个状态描述符
>         StructNetSerializerConfigForGE.StateDescriptor = 
>         FReplicationStateDescriptorBuilder::CreateDescriptorForStruct(...);
>  ...
>  }
>
> void FGameplayEffectContextNetSerializer::Serialize(...)
> {
> ...
> //这里为了降低代码复杂度 直接用默认的 FStructNetSerializer的量化接口
> //本质就是内存拷贝 性能开销不大
>     {
>         FNetQuantizeArgs GEQuantizeArgs = {};
>         GEQuantizeArgs.NetSerializerConfig = &StructNetSerializerConfigForGE;
>         GEQuantizeArgs.Source = NetSerializerValuePointer(&TempGE);
>         GEQuantizeArgs.Target = NetSerializerValuePointer
>         (&TargetValue.EffectContext);
>
>         StructNetSerializer->Quantize(Context, GEQuantizeArgs);
>     }
> ...
> } 
>
> void FGameplayEffectContextNetSerializer::Serialize(...)
> {
>
>         for (uint32 PropertyIt = 0; PropertyIt != PropertyEndIt; ++PropertyIt)
>         {
>             //没修改的字段跳过 减少复制量
>             if (!MemberMask.GetBit(PropertyIt))
>             {
>                 continue;
>             }
>
>             ...
>             //跟FStructNetSerializer一样的实现 直接调用内部字段对应的序列化器
>             ...
>             MemberSerializerDescriptor.Serializer->Serialize(...);
>         }
> ```
>
>
> > 💡
> >
> > 这种方式的量化数据类型 EffectContext应该Struct的sizeof大小，HitResult是FHitResult的量化数据大小，ReplicationFlags记录内部哪些字段被复制了，量化数据的类型无法做更细致的优化调整

```cpp
struct FQuantizedType
{
		alignas(16) uint8 EffectContext[152];
		alignas(16) uint8 HitResult[320];
		uint32 ReplicationFlags;
};
```

> [!note]- 一种是参照FRepMovementNetSerializer
> > 💡
> >
> >     这种解决方案是更极致的优化，内部的每个字段都单独处理，能更大的压缩数据量和提升效率。适合追求更极致的优化，内部字段不会太复制的
>
> ```cpp
> void FRepMovementNetSerializer::Serialize(...)
> {
>     const QuantizedType& Value = *reinterpret_cast<const QuantizedType*>(Args.Source);
>
>     FNetBitStreamWriter* Writer = Context.GetBitStreamWriter();
>
>     //Flags 、VelocityQuantizationLevel 、LocationQuantizationLevel 、RotationQuantizationLevel 共用一个int32
>     constexpr uint32 QuantizationLevelsBitOffset = 4;
>     const uint32 FlagsAndQuantizationLevels = 
>     (((Value.RotationQuantizationLevel << 4U) | 
>     (Value.LocationQuantizationLevel << 2U) | 
>     Value.VelocityQuantizationLevel) << QuantizationLevelsBitOffset) | Value.Flags;
>
>     if (Writer->WriteBool(FlagsAndQuantizationLevels != 0))
>     {
>         Writer->WriteBits(FlagsAndQuantizationLevels, 
>         QuantizationLevelsBitCount + QuantizationLevelsBitOffset);
>     }
>
>
>
>     //FVector 类型通过FPackedVectorNetSerializerBase来压缩数据
>     if (Value.Flags & Flag_RepPhysics)
>     {
>         const FNetSerializer* Serializer = 
>         VectorNetQuantizeNetSerializers[Value.VelocityQuantizationLevel];
>         ...
>         Serializer->Serialize(Context, MemberArgs);
>     }
>     ....
>
>     // FRotator 类型通过FRotatorAsByteNetSerializerBase或者FRotatorAsShortNetSerializerBase来压缩数据
>     {
>
>         const FNetSerializer* Serializer = 
>         RotatorNetSerializers[Value.RotationQuantizationLevel];
>      ...
>         Serializer->Serialize(Context, MemberArgs);
>     }
>
>     // 用压缩版本的Int序列化(WritePackedInt32)压缩数据
>     if (Value.Flags & Flag_ServerFrameIsPresent)
>     {
>         WritePackedInt32(Writer, Value.ServerFrame);
>     }
>  ...
>
> }
> ```
>
> > 💡
> >
> >     这种解决方案的量化数据可以更精准的定制使其更高效率的执行序列化
>
> ```cpp
> //量化数据可以更精准的定制使其更高效率的执行序列化
>     struct FQuantizedData
>     {
>         uint64 AngularVelocity[4];
>         uint64 LinearVelocity[4];
>         uint64 Location[4];
>         uint16 Rotation[4];
>         uint64 Acceleration[4];
>         int32 ServerFrame;
>         int32 ServerPhysicsHandle;
>
>         uint16 Flags : 4;
>         uint16 VelocityQuantizationLevel : 2;
>         uint16 LocationQuantizationLevel : 2;
>         uint16 RotationQuantizationLevel : 1;
>         uint16 RepAcceleration : 1;
>         uint16 Unused : 6;
>         uint16 Padding[3];
>     };
> ```


## 父类创建了自定义序列化器的类型

---

这种Struct类型自己没创建自定义序列化器(NetSerializer)，但其中有个父类创建了。这种情况当描述复制Build这个字段，首先会被视为使用默认Struct序列化器的(第一种)。

区别在于当为这种类型创建嵌套的子状态符时，会检测到其有一个父类实现了自定义的序列化器，此时会把属于那个父类的字段打包成状态描述符的一个字段，其对应的序列化器就是自定义的那个。剩下不在那个父类的字段再单独加在状态描述符的字段列表中。

```cpp

```

> 💡
>
> 这种情况与第一种情况更相似，区别就是将一部分字段打包成状态描述符中一个成员

# 复合类型-数组类型描述符

---

数组跟默认的Struct类型类似，也会为内部元素创建一个子状态描述符来描述数组内部元素。

```cpp
void FPropertyReplicationStateDescriptorBuilder::BuildMemberCache(...)
{
...
	for (FMemberProperty& Member : Members)
	{
		...
		else if (IsArrayPropertyNetSerializer(Serializer))
		{
			CurrentCacheEntry->Descriptor = 
			GetDescriptorForArrayProperty(Member.Property, DescriptorRegistry);
		}
		...
	}
...
}
```

> 💡
>
> 创建子状态描述符描述数组内部的元素(描述符只有一个成员)

```cpp
FPropertyReplicationStateDescriptorBuilder::CreateDescriptorForProperty(...) const
{
	FPropertyReplicationStateDescriptorBuilder Builder;
	FPropertyReplicationStateDescriptorBuilder::FMemberProperty MemberProperty;

	...

	Builder.AddMemberProperty(MemberProperty);
	TRefCountPtr<const FReplicationStateDescriptor> Descriptor = Builder.Build(...);
	
	...
}
```

> 💡
>
> 子状态描述符存放在FArrayPropertyNetSerializerConfig ,FArrayPropertyNetSerializerConfig 还记录了数组的发射信息，最大支持大小(65535)

```cpp
USTRUCT()
struct FArrayPropertyNetSerializerConfig : public FNetSerializerConfig
{
	GENERATED_BODY()

public:
	

	UPROPERTY()
	uint16 MaxElementCount = 0;

	UPROPERTY()
	uint16 ElementCountBitCount = 0;

	UPROPERTY()
	TFieldPath<FArrayProperty> Property;

	TRefCountPtr<const UE::Net::FReplicationStateDescriptor> StateDescriptor;
};
```

# RPC函数描述符

---

```cpp
struct FReplicationStateDescriptor
{
	const FReplicationStateMemberFunctionDescriptor* MemberFunctionDescriptors;
}

struct FReplicationStateMemberFunctionDescriptor
{
	const UFunction* Function;
	const FReplicationStateDescriptor* Descriptor;
};
```

UObject用于描述RPC函数的状态描述符的MemberFunctionDescriptors存放了一个或者多个RPC函数的描述信息，每个成员都会生成一个子状态描述符描述函数参数列表和一个函数反射信息。

```cpp
void FPropertyReplicationStateDescriptorBuilder::BuildMemberFunctionCache(...) const
{
	...
	**//遍历所有的RPC函数 收集下函数反射信息并为为每个RPC函数创建子状态描述符**
	for (const FMemberFunction& MemberFunction : Functions)
	{
		...
		CurrentCacheEntry->Function = MemberFunction.Function;
		CurrentCacheEntry->Descriptor = GetOrCreateDescriptorForFunction(...);
		...
	}
	...
}
```

```cpp
void FPropertyReplicationStateDescriptorBuilder::BuildMemberFunctionDescriptors(..) const
{

	**//每个RPC函数成员都会有一个子状态描述符描述参数列表和一个函数反射信息**
	for (const FMemberFunctionCacheEntry& MemberFunction : Context.MemberFunctionCache)
	{
		CurrentMemberFunctionDescriptor->Function = MemberFunction.Function;
		CurrentMemberFunctionDescriptor->Descriptor = MemberFunction.Descriptor;
		
		CurrentMemberFunctionDescriptor->Descriptor->AddRef();
		++CurrentMemberFunctionDescriptor;

	}
}
```

> 💡
>
> 创建子状态描述符描述RPC函数的参数列表

```cpp
FReplicationStateDescriptorBuilder::CreateDescriptorForFunction(...)
{
...
	//遍历参数列表 加入描述符的成员列表
	for (TFieldIterator<FProperty> It(Function); 
	It && (It->PropertyFlags & (CPF_Parm | CPF_ReturnParm)) == CPF_Parm; ++It)
	{
	...
		if (FPropertyReplicationStateDescriptorBuilder::
				IsSupportedProperty(MemberProperty, Property))
		{
			Builder.AddMemberProperty(MemberProperty);
		}
	...
	}
	
	Descriptor = Builder.Build(...);
...	
}

```

# **状态描述符字段详解**

---

```cpp
struct FReplicationStateDescriptor
{
	//**包含一个或者多个复制字段的内存偏移信**息
	//(包括副本数据内存偏移和复制系统量化数据的内存偏移)
	//有了内存偏移就能根据复制对象实例的起始地址获取属性字段的内存地址(指针) 
	//就可以取出对应的值了
	const FReplicationStateMemberDescriptor* MemberDescriptors;
	
	//**描述复制字段的网络序列化器**(NetSerializer 描述怎么量化、序列化、对比)
	//字段的序列化器放在这里的NetSerializerConfig中
	const FReplicationStateMemberSerializerDescriptor* 
	MemberSerializerDescriptors;
	
	
	//**RPC函数的描述(包括函数指针和函数参数列表的状态描述符)**
	const FReplicationStateMemberFunctionDescriptor* MemberFunctionDescriptors;
	
	
	
	//**用于描述字段是否被修改的Bit 偏移和 Bit 数量**
	//非数组类型 1 个 bit 位即可(标记字段本身是否被修改)
	//数组类型需要标记内部的数组元素是否被修改，额外分配 63 个 bit
	//数组类型如果数组元素超过 63 个则通过取模运算复用前 63 位的 bit位
	const FReplicationStateMemberChangeMaskDescriptor* 
	MemberChangeMaskDescriptors;
	
	
	
	//**描述字段的特性描述**
	const FReplicationStateMemberTraitsDescriptor* MemberTraitsDescriptors;
	

	
	//**复制标签信息(RepTag)**
	//用于为复制状态中的特定成员附加语义标识，使得网络系统可以通过标签名称而非硬编码的偏移量来访问特定的复制属性,方便快速定位到某个属性字段(包括 Struct嵌套的字段)。
	//嵌套子状态描述符的 tag 会汇总到最上层的MemberTagDescriptors中
	const FReplicationStateMemberTagDescriptor* MemberTagDescriptors;
	
	//**UObject对象引用追踪数组**，用于记录复制状态中所有包含 UObject 引用的成员信息
	//嵌套子状态描述符的会汇总到最上层的MemberReferenceDescriptors中
	const FReplicationStateMemberReferenceDescriptor* MemberReferenceDescriptors;

	//**Gameplay复制字段的反射信息**
	//从副本数据拷贝到Gameplay字段时，可以通过这个获取内存偏移信息
	const FProperty** MemberProperties;

	//**复制字段的额外信息描述**(OnRep 函数、定长数组下标之类的)
	const FReplicationStateMemberPropertyDescriptor* MemberPropertyDescriptors;

	// **复制字段的条件过滤描述**(ELifetimeCondition）
	const FReplicationStateMemberLifetimeConditionDescriptor* 
	MemberLifetimeConditionDescriptors;

	// **传统复制系统的RepIndex(FProperty::RepIndex)转换为Iris系统的MemberIndex**（成员索引）
	const FReplicationStateMemberRepIndexToMemberIndexDescriptor* 
	MemberRepIndexToMemberIndexDescriptors;

	//**Struct类型的基类反射数据(**最接近且实现了NetSerialize的基类**)**
	const UScriptStruct* BaseStruct;

	// **调试信息**
	const FNetDebugName* DebugName;
	const FReplicationStateMemberDebugDescriptor* MemberDebugDescriptors;

  //**在副本数据(External)和量化数据(Interal)的内存大小和对齐**
	uint32 ExternalSize;		
	uint32 InternalSize;		
	uint16 ExternalAlignment;
	uint16 InternalAlignment;

	//复制字段的数组大小
	uint16 MemberCount;
	
	//RPC函数描述数组大小
	uint16 FunctionCount;
	
	//复制标签信息(RepTag)数组大小
	uint16 TagCount;
	
	//Object引用信息数组大小
	uint16 ObjectReferenceCount;

	//传统复制系统的RepIndex转换为Iris系统的MemberIndex的数组大小
	uint16 RepIndexCount;

	// 用于追踪复制字段是否修改需要几个 bit位
	uint16 ChangeMaskBitCount;
	
	//副本数据中用于存放追踪复制字段ChangeMasks的偏移量
	//(会存放ChangeMask, ConditionalChangeMask ，MemberPollMask)
	uint32 ChangeMasksExternalOffset;

	//描述符的标识
	FReplicationStateIdentifier DescriptorIdentifier;

	// **用于构造ReplicationState中的副本数据StateBuffer的函数指针**
	//(有默认实现ConstructPropertyReplicationState)
	ConstructReplicationStateFunc ConstructReplicationState;

	//**用于析构ReplicationState中的副本数据StateBuffer的函数指针**
	//(有默认实现DestructPropertyReplicationState)
	DestructReplicationStateFunc DestructReplicationState;

	// **为特定的复制状态创建自定义的 ReplicationFragment，用于实现特殊的复制逻辑**
	//（如 FastArray、GameplayCue 等）。
	//(有默认实现FPropertyReplicationFragment::CreateAndRegisterFragment)
	CreateAndRegisterReplicationFragmentFunc 
	CreateAndRegisterReplicationFragmentFunction;

	//特性汇总
	EReplicationStateTraits Traits;

	//**指向默认复制状态的内部量化表示的指针，存储了所有属性的默认值**（复制对象CDO的量化版本）。
	const uint8* DefaultStateBuffer;
}
```

> 💡
>
> 在复制状态描述符（ReplicationStateDescriptor）中的涉及内存大小、内存偏移、内存对齐经常能看到ExternalSize、InternalSize、ExternalAlignment、InternalAlignment之类涉及External和Internal的概念，这里的External和Internal对应的是复制状态(副本数据)和量化数据。
>
> 副本数据的复制字段内存跟原始数据(Gameplay)的一致，所以被视为External
>
> 量化数据时复制系统内部重新规划的数据结构，所以被视为Internal
>
> 外部是未量化过的原始数据(Gameplay复制数据、副本数据)，内部是复制系统量化过的数据(副本数据量化或者客户端接收反序列化后的数据)。
>
> 为了减少网络传输的数据量、使用更紧凑的数据流、减少序列化开销，Iris复制系统会对复制状态(副本数据)进行量化操作，量化数据类型是一个新的类型(QuantizedType)，新类型的数据结构能更高效的序列化和压缩数据，所以有单独的内存大小、内存偏移、内存对齐。

> [!note]- 量化数据类型示例
> ```cpp
> struct FRepMovement
> {
>     FVector LinearVelocity;
>     FVector AngularVelocity;
>     FVector Location;
>     FRotator Rotation;
>     FVector Acceleration;
>     uint8 bSimulatedPhysicSleep : 1;
>     uint8 bRepPhysics : 1;
>     uint8 bRepAcceleration : 1;
>     int32 ServerFrame;
>     int32 ServerPhysicsHandle = INDEX_NONE;
>     EVectorQuantization LocationQuantizationLevel;
>     EVectorQuantization VelocityQuantizationLevel;
>     ERotatorQuantization RotationQuantizationLevel;
> }
>
> struct FRepMovementNetSerializer
> {
>     struct FQuantizedData
>     {
>         uint64 LinearVelocity[4];
>         uint64 AngularVelocity[4];
>         uint64 Location[4];
>         uint16 Rotation[4];
>         uint64 Acceleration[4];
>         int32 ServerFrame;
>         int32 ServerPhysicsHandle;
>
>         uint16 Flags : 4;
>         uint16 VelocityQuantizationLevel : 2;
>         uint16 LocationQuantizationLevel : 2;
>         uint16 RotationQuantizationLevel : 1;
>         uint16 RepAcceleration : 1;
>         uint16 Unused : 6;
>         uint16 Padding[3];
>     };
> }
> ```
>
>
> > 💡
> >
> > ReplicationStateDescriptorBuilder负责创建状态描述符的，在通过DescriptorBuilder创建描述符实例时，会先收集必要信息存放在DescriptorBuilder的Member变量或者BuilderContext中，然后再填充信息。

## 复制字段成员的内存偏移

---

```cpp
struct FReplicationStateMemberDescriptor
{
	uint32 ExternalMemberOffset;		
	uint32 InternalMemberOffset;		
};
```

**MemberDescriptors**记录了每个复制字段的内存偏移信息(分为External、Internal分别代表在副本数据和量化数据中的偏移)。

> [!note]- **收集描述符字段成员的内存大小信息**(会触发递归展开)
> ```cpp
> void FPropertyReplicationStateDescriptorBuilder::BuildMemberCache(...)
> {
>     for (FMemberProperty& Member : Members)
>     {
>         //未实现自定义NetSerializer的Struct
>         if (IsStructNetSerializer(Serializer))
>         {
>             //触发递归
>             CurrentCacheEntry->Descriptor = GetDescriptorForStructProperty(...);
>
>             //收集内存大小
>             **//Struct副本数据(External)的内存大小通过字段反射信息获取**
>             CurrentCacheEntry->ExternalSizeAndAlignment = 
>             { (SIZE_T)Member.Property->GetElementSize(), 
>             (SIZE_T)Member.Property->GetMinAlignment() };
>
>             **//Struct量化数据(Internal)的内存大小等于内部复制字段的大小累计**
>             CurrentCacheEntry->InternalSizeAndAlignment = { 
>             Descriptor->InternalSize, 
>             Descriptor->InternalAlignment };
>         }
>         //数组
>         else if (IsArrayPropertyNetSerializer(Serializer))
>         {
>             //触发递归
>             CurrentCacheEntry->Descriptor = GetDescriptorForArrayProperty(...);
>
>             //收集内存大小
>             **//数组副本数据(External)的内存大小通过字段反射信息获取**
>             CurrentCacheEntry->ExternalSizeAndAlignment = { 
>             (SIZE_T)Member.Property->GetElementSize(), 
>             (SIZE_T)Member.Property->GetMinAlignment() };
>
>             **//数组量化数据(Internal)的内存大小跟量化数据结构的大小**
>             CurrentCacheEntry->InternalSizeAndAlignment = { 
>             Serializer->QuantizedTypeSize, 
>             Serializer->QuantizedTypeAlignment };
>         }
>         //其他字段
>         else if (Member.Property)
>         {
>             //收集内存大小
>             **//其他类型副本数据(External)的内存大小通过字段反射信息获取**
>             CurrentCacheEntry->ExternalSizeAndAlignment = { 
>             (SIZE_T)Member.Property->GetElementSize(), 
>             (SIZE_T)Member.Property->GetMinAlignment() };
>
>             **//其他类型量化数据(Internal)的内存大小跟量化数据结构的大小**
>             CurrentCacheEntry->InternalSizeAndAlignment = { 
>             Serializer->QuantizedTypeSize,
>             Serializer->QuantizedTypeAlignment };
>         }
>         ...
>     }
> }
> ```


> [!note]- **通过收集的信息构建描述符字段成员的内存偏移信息**
> ```cpp
> void FPropertyReplicationStateDescriptorBuilder::BuildMemberDescriptors(..) const
> {
>     SIZE_T ExternalOffset = Context.External.Size;
>     SIZE_T InternalOffset = Context.Internal.Size;
>     for (const FMemberProperty& Member : Members)
>     {
>     ...
>         **//副本数据(External)的内存偏移**
>         CurrentMemberDescriptor->ExternalMemberOffset=(ExternalOffset);
>         ExternalOffset += ExternalMemberSize;
>
>         **//量化数据(Internal)的内存偏移**
>         CurrentMemberDescriptor->InternalMemberOffset = (InternalOffset);
>         InternalOffset += InternalMemberSize;
>     ...
>
>     }
>
>     **//更新描述的内存占用大小(加上了所有字段成员占用的内存大小)**
>     Context.External.Size = ExternalOffset;
>     Context.Internal.Size = InternalOffset;
> }
> ```


## 复制字段成员的NetSerializer

---

```cpp
struct FReplicationStateMemberSerializerDescriptor
{
	const FNetSerializer* Serializer;
	const FNetSerializerConfig* SerializerConfig;
};
```

**MemberSerializerDescriptors**记录了每个复制字段的网络序列器(NetSerializer)信息，描述字段该如何对比、量化、序列化

> [!note]- **收集字段成员的NetSerializer信息**
> ```cpp
> bool FPropertyReplicationStateDescriptorBuilder::IsSupportedProperty(..)
> {
>     **//通过字段反射数据在NetSerializer注册表中查找到对应的NetSerializerInfo**
>     const FPropertyNetSerializerInfo* NetSerializerInfo = 
>     FPropertyNetSerializerInfoRegistry::FindSerializerInfo(Property);
>
>     **//缓存字符的缓存信息**
>     OutMemberProperty.Property = Property;
>     OutMemberProperty.SerializerInfo = NetSerializerInfo;
> }
> ```

> [!note]- **根据收集信息填充字段成员的NetSerializer信息**
> ```cpp
> //填充复制字段成员的网络序列化器Serializer信息
> FPropertyReplicationStateDescriptorBuilder::BuildMemberSerializerDescriptors(...)
> {
> ...
>     for (const FMemberProperty& Info : Members)
>     {
>     ...
>         **//通过字段反射数据在NetSerializer注册表中查找到对应的NetSerializer**
>         CurrentMemberSerializerDescriptor->Serializer = 
>         Info.SerializerInfo->GetNetSerializer(Info.Property);
>     ...
>     }
> ... 
> }
> ```
>
> ```cpp
> //填充复制字段成员的NetSerializerConfig信息
> void FPropertyReplicationStateDescriptorBuilder::BuildMemberSerializerConfigs(...)
> {
> ...
>     for (const FMemberProperty& Member : Members)
>     {
>     ...
>             if (IsStructNetSerializer(MemberCacheEntry->Serializer))
>             {
>             ...
>                 //未实现自定义NetSerializer的Struct字段的网络序列器
>                 **//填充描述Struct内部字段的子状态描述符**
>                 SerializerConfig->StateDescriptor = MemberCacheEntry->Descriptor;
>             ...
>             }
>             else if (IsArrayPropertyNetSerializer(MemberCacheEntry->Serializer))
>             {
>             ...
>                 //数组
>                 **//填充描述数组内部字段的反射数据**
>                 SerializerConfig->Property = (Member.Property)));
>                 **//填充描述数组内部字段的子状态描述符**
>                 SerializerConfig->StateDescriptor = MemberCacheEntry->Descriptor;
>             ...
>
>             }
>             else
>             {
>                 **//其他类型字段根据NetSerializer注册信息按需创建**
>                 const FNetSerializerConfig* SerializerConfig = Member.SerializerInfo->
>                 BuildNetSerializerConfig(SerializerConfigBuffer, Member.Property);
>             }
>     ...
>     }
> ...
> }
> ```


## 复制字段成员的修改标记位(ChangeMask)

---

```cpp
struct FReplicationStateMemberChangeMaskDescriptor
{
	uint16 BitOffset;	//脏标记存放的内存偏移				
	uint16 BitCount; //脏标记占用的bit位
};

```

**MemberChangeMaskDescriptors**是用来标记复制字段是否修改的。

- 对于非数组类型的字段一个 bit 位就可以标记复制字段是否修改了
- 对于数组类型(包括 FastArray)则MemberChangeMask除了标记数组本身是否改变了(数组大小，整体变化)，还需要标记其内部的数组元素是否发生了修改，这样如果只是其中的某个元素发生变化的话，只需要复制其中的发生变动的数组，不需要复制整个数组。

```cpp
bool FPropertyReplicationStateDescriptorBuilder::IsSupportedProperty(...)
{
	
	//默认占用一个 bit 位
	OutMemberProperty.ChangeMaskBits = 1u;
...
	**//数组类型用额外的 63 个 bit位记录内部的数组元素是否发生变动**
	if (EnumHasAnyFlags(...EMemberPropertyTraits::IsFastArray))
	{
		OutMemberProperty.ChangeMaskBits = 1U + 
		FIrisFastArraySerializer::IrisFastArrayChangeMaskBits;
	}
	else if (EnumHasAnyFlags(..., EMemberPropertyTraits::IsTArray))
	{
		if (bIrisUseChangeMaskForTArray)
		{
			OutMemberProperty.ChangeMaskBits = 1U + 
			FPropertyReplicationState::TArrayElementChangeMaskBits;
		}
	}
...
}
```

对于一个TArray(包括 FastArray类型)属性，MemberChangeMask分配了 64个bit（1 + 63）：

- 第0位：表示数组本身是否脏（大小变化、整体变化）
- 第1-63位：追踪前63个元素的脏状态

63 的内部元素变化的追踪位并不意味的数组大小不能超过 63，而是当超过 63 位时，复用置脏位
(元素索引 0, 63, 126, 189... 共享同一个变更位)。

这是一个合理的设计权衡，因为大多数复制数组不会有太多元素，而64位掩码可以高效地存储和操作(超过 63 的就是触发下冗余复制，可以接受)。

> [!note]- **ChangeMask的Set&Get**
> ```cpp
> //对比&拷贝数组元素时，对数组下标取模，超过 63的索引跟前63位的共用一个脏标记位(SetBit)
> bool InternalCompareAndCopyArrayWithElementChangeMask(...)
> {
>     for (...)
>     {
>         ...
>             //这里对数组索引取模(%)了
>             const uint32 ElementBitOffset = ElementChangeMaskBitOffset + 
>             (**ElementIt % FPropertyReplicationState::TArrayElementChangeMaskBits**);
>
>             **//标记对应的字段被修改了**
>             ChangeMask.SetBit(ElementBitOffset);
>             ...
>     }
> }
> ```
>
> ```cpp
> //量化&序列化数组元素时，对数组下标取模，超过63的索引跟前63位的共用一个脏标记位(GetBit)
> void FArrayPropertyNetSerializer::Quantize(...)
> {
> ...
>         for (...)
>         {
>             //**判定数组元素是否被修改**(这里对数组索引取模(%)了)
>             if (ChangeMask->GetBit(ChangeMaskBitOffset + 
>             (**ElementIt % ChangeMaskBitCount**)))
>             {
>                 ...
>                 ElementSerializer->Quantize(Context, ElementArgs);
>                 ...
>             }
>         }
> ...
> }
>
> void FArrayPropertyNetSerializer::Serialize(...)
> {
>         for (...)
>         {
>             //**判定数组元素是否被修改**(这里对数组索引取模(%)了)
>             if (ChangeMask->GetBit(ChangeMaskBitOffset + 
>             (**ElementIt % ChangeMaskBitCount**)))
>             {
>             ...
>                 ElementSerializer->Serialize(Context, ElementArgs);
>             }
>     ...
>         }
> }
> ```


> [!note]- **ChangeMask的序列化&反序列化**
> ```cpp
> void FReplicationProtocolOperations::SerializeWithMask(...)
> {
>     //写入ChangeMask
>     WriteSparseBitArray(Writer, ChangeMaskData, Protocol->ChangeMaskBitCount);
> }
>
> void FReplicationStateOperations::DeserializeWithMask(...)
> {
> ...
>         // 读取 ChangeMask
>     ReadSparseBitArray(Context.GetBitStreamReader(), 
>     DstChangeMaskData, Protocol->ChangeMaskBitCount);
> ...
> }
> ```


ChangeMask 通过稀疏位数组格式传输，只传输非零且非全1的int32数据，这种格式大大减少了网络带宽消耗，因为：

- 全0的字不传输数据
- 全1的字只传输1位标记(InvertedWordMask)
- 只有部分位为1的字才传输完整的32位数据(NonZeroWordMask)，使用 WriteSparseUint32UsingIndices 进一步压缩。

> [!note]- 稀疏位数实现代码
> ```cpp
> template<typename GetDataFunc, typename WriteSparseUint32Func>
> void WriteSparseBitArray(...)
> {
> ...
>
>     // ========== 第一步：构建掩码 ==========
>     ...
>         // 如果Word既不是全0也不是全1，标记为NonZero
>         NonZeroWordMask |= (CurrentWord == 0) or (InvertedWord == 0) ?
>          0U : CurrentBitMask;
>
>         // 如果Word是全1，标记为Inverted
>         InvertedWordMask |= InvertedWord == 0 ? CurrentBitMask : 0U;
>     }
>     ...
>
>     // ========== 第二步：写入掩码 ==========
>     Writer->WriteBits(NonZeroWordMask, WordCount);
>     if (Writer->WriteBool(InvertedWordMask != 0))
>     {
>         Writer->WriteBits(InvertedWordMask, WordCount);
>     }
>
>     // ========== 第三步：编码非零Word ==========
>     uint32 CurrentMaskBit = 1U;
>     uint32 WordIt = 0U;
>     uint32 RemainingBits = BitCount;
>
>     while (RemainingBits >= 32U)
>     {
>         if (NonZeroWordMask & CurrentMaskBit)
>         {
>             WriteSparseUint32Function(Writer, GetDataFunction(Data[WordIt]), 32U);
>         }
>         ++WordIt;
>         CurrentMaskBit <<= 1;
>         RemainingBits -= 32U;
>     }
>
>     // 处理最后不足32位的Word
>     if (RemainingBits && (NonZeroWordMask & CurrentMaskBit))
>     {
>         const StorageWordType CurrentWord = 
>         GetDataFunction(Data[WordIt]) & LastWordMask;
>
>         WriteSparseUint32Function(Writer, CurrentWord, RemainingBits);
>     }
> }
>
> ```


## 复制字段成员的标签(RepTag)

---

```cpp
typedef uint64 FRepTag;

struct FReplicationStateMemberTagDescriptor
{
	FRepTag Tag; //RepTag(uint64)
	uint16 MemberIndex; //属于哪个字段成员
	uint16 InnerTagIndex; //嵌套子字段成员中的 Index
};
```

MemberTagDescriptors是复制字段标签(RepTag) 的集合，RepTag是 uint64 类型，通过 CityHash64 算法从标签名称生成。

用于为复制对象中的特定成员附加语义标识，使得网络系统可以通过标签名称而非硬编码的偏移量来访问特定的复制属性。

这是一种基于名称的属性查找机制，类似于反射系统，但专门为网络复制优化，通过
UE::Net::MakeRepTag创建，可以通过 RepTag 快速定位到对应的字段

（包括字段在Struct这种嵌套类型中）。

**设计优势**

- **解耦**：网络系统不需要知道具体的类结构，只需要知道标签名称
- **灵活性**：支持不同类型的对象，只要它们有相同的标签
- **可扩展**：可以轻松添加新的标签
- **类型安全**：通过 FRepTagFindInfo 返回序列化器信息，确保正确的数据访问
- **嵌套支持**：支持复杂的数据结构（结构体内部的标签）

用法示例:

```cpp
FRepTag HealthTag = MakeRepTag("Health");
FRepTagFindInfo TagInfo;

if (FindRepTag(Protocol, HealthTag, TagInfo))
{
    // 读取健康值
    const float* Health = reinterpret_cast<const float*>
    (StateBuffer + TagInfo.ExternalStateOffset);
 }
```

> 💡
>
> 可以直接通过FRepTag (uint64) 快速获取对应字段的内存偏移，从而读取字段值

> 💡
>
> 在 RepTag.h 中预定义了几个重要的系统标签

```cpp
// 通过 MakeRepTag("WorldLocation") 生成
constexpr FRepTag RepTag_WorldLocation = 0x0719E9E9E02F8B16ULL;

// 通过 MakeRepTag("NetRole") 生成
constexpr FRepTag RepTag_NetRole = 0xFFAAB417B1123942ULL;

// 通过 MakeRepTag("NetRemoteRole") 生成
constexpr FRepTag RepTag_NetRemoteRole = 0xF754C2703924C7AAULL;

// 通过 MakeRepTag("CullDistanceSqr") 生成
constexpr FRepTag RepTag_CullDistanceSqr = 0x6BB13A5C1A655157ULL;

```

> 💡
>
> 目前只能使用预定义的几个重要标签，如果需要自定义标签修改对应的代码。
>
> 目前尚未支持通过 RepTag 之类的Property标签(类似ReplicatedUsing)来指定 Tag，估计后面会加上方便定制标签

```cpp
FRepTag GetRepTagFromProperty(...)
{
...
...
}
```

> 💡
>
> 嵌套子状态描述符的 tag 会汇总到最上层的MemberTagDescriptors中

```cpp
void FPropertyReplicationStateDescriptorBuilder::BuildMemberTagDescriptors(...) 
{
...
	if (TagEntry.bInDescriptor)
		{
			// 汇总子状态的 Tag
			for (...)
			{
				CurrentMemberTagDescriptor->Tag = 
				MemberStateDescriptor->MemberTagDescriptors[TagIt].Tag;
		
			}
		}
...
}
```

## 复制字段成员的条件过滤(LifetimeCondition)

---

**MemberLifetimeConditionDescriptors** 是一个生命周期条件描述符数组，用于存储每个复制成员的复制条件（Replication Condition）。

它是 UE 传统复制系统中 DOREPLIFETIME_CONDITION 宏在 Iris 系统中的实现基础。使得 Iris 能够灵活地控制属性复制的目标连接，实现精细的网络带宽优化和安全控制。

核心作用：

- **控制属性复制的目标连接**：决定属性应该复制给哪些客户端
- **实现条件复制**：支持 Owner Only、Skip Owner、Simulated Only 等条件
- **向后兼容**：与传统复制系统的 ELifetimeCondition 保持兼容
- **动态条件支持**：支持运行时修改复制条件（COND_Dynamic）

```cpp
enum ELifetimeCondition : int
{
    COND_None = 0,                  //无条件，任何时候变化都复制
    COND_InitialOnly = 1,           //仅在初始包中发送(只在连接建立时传输)
    COND_OwnerOnly = 2,             //仅发送给其Owner持有的网络连接
    COND_SkipOwner = 3,             //发送给除其Owner持有的网络连接之外的所有连接
    COND_SimulatedOnly = 4,         //仅发送给在所在网络连接被视为Simulated
    COND_AutonomousOnly = 5,        //仅发送给在所在网络连接被视为AutonomousOnly
    COND_SimulatedOrPhysics = 6,        //发送给模拟或物理 Actor
    COND_InitialOrOwner = 7,            //初始包或发送给所有者
    COND_Custom = 8,               //自定义条件，可通过SetCustomIsActiveOverride切换
    COND_ReplayOrOwner = 9,             //仅发送给回放连接或所有者
    COND_ReplayOnly = 10,               //仅发送给回放连接
    COND_SimulatedOnlyNoReplay = 11,    //仅发送给模拟 Actor，不包括回放
    COND_SimulatedOrPhysicsNoReplay = 12, //发送给模拟或物理 Actor，不包括回放
    COND_SkipReplay = 13,               //不发送给回放连接
    COND_Dynamic = 14,                  //运行时动态条件（默认总是复制，直到覆盖）
    COND_Never = 15,                    //永不复制
    COND_NetGroup = 16,                 //子对象复制给同组连接（不用于属性）
    COND_Max = 17
};

```

## UObject对象引用追踪(MemberReference)

---

**MemberReferenceDescriptors** 是一个对象引用追踪数组，用于记录复制状态中所有包含 UObject 引用的成员信息。它的核心作用是：

- 记录所有UObject对象引用的位置和类型:快速定位所有对象引用，无需遍历所有成员，直接访问包含引用的成员
- 支持引用收集：在网络复制时收集所有需要复制的对象引用(有依赖关系)
- 处理嵌套引用：支持结构体内部、动态数组内部的引用(会汇总到最上层的状态描述符中)
- 引用解析控制：通过 Info.ResolveType 控制引用的解析行为
- 与变更掩码配合实现增量复制

```cpp
struct FReplicationStateMemberReferenceDescriptor
{
	uint32 Offset;//内存偏移信息				
	FNetReferenceInfo Info;	//引用信息	
	uint16 MemberIndex;//成员索引			
	uint16 InnerReferenceIndex; //嵌套引用索引
};
```

> 💡
>
> 在网络复制时，系统需要收集所有UObject对象引用以确保依赖关系正确，有了MemberReferenceDescriptors就可以快速遍历所有引用，无需检查每个成员
> (只处理包含引用的成员)

```cpp
void FReplicationStateOperationsInternal::CollectReferences(...)
{
    // 遍历所有引用描述符
    const FReplicationStateMemberReferenceDescriptor* ReferenceDescriptors = 
    Descriptor->MemberReferenceDescriptors;
    
    for (... )
    {
        // 情况1：直接引用（静态存储）
        if (MemberReferenceDescriptor.Info.ResolveType 
        != FNetReferenceInfo::EResolveType::Invalid)
        {
            Collector.Add(...);
        }
        // 情况2：动态引用（数组、自定义序列化器）
        else
        {
            // 需要通过序列化器的 CollectNetReferences 函数处理
            // ...
        }
    }
}

```

## RepIndexToMemberIndex

---

MemberRepIndexToMemberIndexDescriptors 是一个RepIndex 到 MemberIndex 的映射表，用于快速将传统复制系统的 RepIndex（属性复制索引）转换为 Iris 系统的 MemberIndex（成员索引）。

这个设计使得 Iris 能够无缝集成到现有的 UE 复制系统中，同时保持高性能和灵活性。开发者可以继续使用熟悉的 RepIndex API，而 Iris 内部会自动转换为高效的 MemberIndex 访问。

核心作用：

> [!note]- 桥接两套索引系统：连接传统复制系统（FProperty::RepIndex）和 Iris 系统（MemberIndex）
> > 💡
> >
> >     比如传统复制系统
> >     DOREPLIFETIME_CONDITION(AMyActor, MyProperty, COND_OwnerOnly);
> >     内部会使用 MyProperty 的 RepIndex 来标识属性复制条件，Iris 需要兼容这些传统的复制代码

- 快速查找：O(1) 时间复杂度通过 RepIndex 定位到 MemberIndex
- 向后兼容：支持传统 API（如 SetPropertyDynamicCondition）
- 稀疏映射：支持不连续的 RepIndex（使用 InvalidEntry 标记空位）

RepIndex介绍：

> [!note]- FProperty::RepIndex
> ```cpp
> // 在 UnrealType.h 中
> class FProperty
> {
>     // ...
>     uint16 RepIndex;  // 复制索引，由 UE 反射系统分配
> };
>
> ```


- RepIndex 的分配
    - 在类的 GetLifetimeReplicatedProps 函数中隐式分配
    - 按照属性在类层次结构中的顺序分配
    - 父类的属性先分配，子类的属性后分配
    - 静态数组的每个元素占用连续的 RepIndex

> [!note]- RepIndex 的使用
> ```cpp
> // 传统复制系统
> DOREPLIFETIME_CONDITION(AMyActor, MyProperty, COND_OwnerOnly);
>
> // 内部会使用 MyProperty 的 RepIndex 来标识属性
> ```


> [!note]- RepIndex 可能不连续
> > 💡
> >
> >     如果有其他非复制属性，RepIndex 可能跳跃。映射数组MemberRepIndexToMemberIndexDescriptors中对应的索引为空值


> [!note]- 静态数组(定长数组)的特殊处理
> ```cpp
> UPROPERTY(Replicated)
> int32 MyArray[5];  // 占用 5 个 RepIndex
>
> // 构建映射时：
> // RepIndex N+0 -> MemberIndex M+0
> // RepIndex N+1 -> MemberIndex M+1
> // RepIndex N+2 -> MemberIndex M+2
> // RepIndex N+3 -> MemberIndex M+3
> // RepIndex N+4 -> MemberIndex M+4
>
> ```


## 构造副本数据和复制片段的函数指针

---

> [!note]- **ConstructReplicationState**&**DestructReplicationState**
> ConstructReplicationState用于构造ReplicationState中的副本数据StateBuffer的函数指针，初始化副本数据所有成员属性。(有默认实现 ConstructPropertyReplicationState)
>
> DestructReplicationState用于析构ReplicationState中的副本数据StateBuffer的函数指针
> (有默认实现DestructPropertyReplicationState)
>
> 反序列化前、调试输出时构造临时数据副本
>
> ```cpp
> // 在 DequantizeAndApplyHelper 中 反序列化前的构造临时数据副本
> uint8* StateBuffer = (uint8*)Allocator.Alloc(
> CurrentDescriptor->ExternalSize, 
> CurrentDescriptor->ExternalAlignment);
>
> // 构造外部状态
> CurrentDescriptor->ConstructReplicationState(StateBuffer, CurrentDescriptor);
>
> // 反量化网络数据到外部状态
> FReplicationStateOperations::Dequantize(
> NetSerializationContext, StateBuffer, 
> (uint8*)CurrentInternalStateBuffer, CurrentDescriptor);
>
> // 应用到实际对象...
>
> // 析构临时状态
> CurrentDescriptor->DestructReplicationState(StateBuffer, CurrentDescriptor);
> FMemory::Free(StateBuffer);
>
> ```

> [!note]- **CreateAndRegisterReplicationFragmentFunction**
> 为特定的复制状态创建自定义的 ReplicationFragment，用于实现特殊的复制逻辑（如 FastArray、GameplayCue 等）。
> (有默认实现FPropertyReplicationFragment::CreateAndRegisterFragment)


## 复制对象 CDO的量化数据

---

**DefaultStateBuffer** 是一个指向默认复制状态的内部量化表示的指针，存储了所有属性的默认值（复制对象的CDO量化版本）。

- 用于在增量序列化时，只序列化与 CDO不同的值。减少初始状态的网络带宽消耗
- 默认状态哈希计算，用于验证客户端和服务器的默认状态一致性。
- 调试输出，打印默认状态的哈希值和内容。

```cpp
void FPropertyReplicationStateDescriptorBuilder::
AllocateAndInitializeDefaultInternalStateBuffer(...) const
{

}
```

# 复制状态描述符创建流程

---

```cpp
class FReplicationStateDescriptorBuilder
{

static SIZE_T CreateDescriptorsForClass(...);

static TRefCountPtr<const FReplicationStateDescriptor> 
CreateDescriptorForStruct(...);

static TRefCountPtr<const FReplicationStateDescriptor> 
CreateDescriptorForFunction(...);
}

```

ReplicationStateDescriptorBuilder是负责创建状态描述符的，在通过DescriptorBuilder创建描述符实例时，会先收集必要信息存放在DescriptorBuilder的Member变量或者BuilderContext中，然后再填充信息。

收集过程中可能触发递归创建

> [!note]- **执行创建前会先统计描述符需要描述哪些成员**(复制字段或者RPC函数)
> ```cpp
> FReplicationStateDescriptorBuilder::CreateDescriptorForStruct(...)
> {
> ...
>
>     if (Parameters.DescriptorRegistry)
>     {   
>         //类型之前已经注册的 直接返回
>         if (const FReplicationStateDescriptorRegistry::FDescriptors* Result = 
>         Parameters.DescriptorRegistry->Find(InStruct))
>         {
>             return (*Result)[0];
>         }
>     }
>
>     for (TFieldIterator<FProperty> It(...); It; ++It)
>     {
>     ...
>     **Builder.AddMemberProperty(MemberProperty);**
>     ...
>     }
> ...
> }
> ```
>
> > 💡
> >
> >     CreateDescriptorsForClass、CreateDescriptorForFunction也有类似逻辑

> [!note]- **然后执行Build接口开始创建**
> > 💡
> >
> >     执行Build时继续先收集描述符创建需要的信息(BuilderContex)
> >
> >     收集信息阶段如果描述符成员是通用结构体(没有自定义网络序列器的)、数组、RPC函数会递归调用Build
> >
> >     (CreateDescriptorForStruct、CreateDescriptorForFunction、CreateDescriptorForProperty)
>
> ```cpp
> struct FBuilderContext
> {
>         //收集复制字段成员信息
>         FMemberCache MemberCache;
>
>         //收集UObject引用信息
>         FMemberReferenceCache ReferenceCache;
>
>         //收集有RepTag标记的成员信息
>         FMemberTagCache MemberTagCache;
>
>         //收集RPC函数信息
>         FMemberFunctionCache MemberFunctionCache;
>
>         //收集特性信息
>         EMemberPropertyTraits CombinedPropertyTraits;
>         EMemberPropertyTraits SharedPropertyTraits;
>
>         //累计的内存偏移大小和内存对齐信息
>         FSizeAndAlignment External;
>         FSizeAndAlignment Internal;
>
>         //附加参数信息
>         FBuildParameters BuildParams;
> }
> ```
>
> ```cpp
> FPropertyReplicationStateDescriptorBuilder::Build(...)
> {
>     //收集FReplicationStateDescriptor需要的信息(Context)
>     FBuilderContext Context;
>     Context.BuildParams = BuildParams
>
>     **//收集字段成员内存大小、内存对齐信息、嵌套子Descriptor、特性信息**
>     //会在触发复合类型的递归展开
>     BuildMemberCache(Context,...);
>
>     **//收集UObject引用信息**
>     BuildMemberReferenceCache(Context.ReferenceCache,...);
>
>     **//收集 RepTag 信息**
>     BuildMemberTagCache(Context.MemberTagCache,...);
>
>     **//收集RPC函数成员信息**
>     BuildMemberFunctionCache(Context,...);
>
>     **//汇总收集的特性信息**
>     const EReplicationStateTraits Traits =BuildReplicationStateTraits(Context)
>
> }
> ```

> [!note]- **收集完毕开始构建填充描述符**
> ```cpp
> FPropertyReplicationStateDescriptorBuilder::Build(...)
> {
>     ...
>
>     **//创建ReplicationStateDescriptor实例**
>   FReplicationStateDescriptor* Descriptor = new (...);
>
>   **//填充字段成员内存偏移信息**
>     BuildMemberDescriptors(...);
>
>     **//填充NetSerializer信息**
>     BuildMemberSerializerDescriptors(...);
>
>     **//填充特性信息**
>     BuildMemberTraitsDescriptors(...)
>
>     **//填充 RepTag 信息**
>     BuildMemberTagDescriptors(...)
>
>     **//填充UObject对象引用字段信息**
>     BuildMemberReferenceDescriptors(...)
>
>     **//填充 RPC 信息**
>     BuildMemberFunctionDescriptors(...)
>
>     **//填充字段反射信息**
>     BuildMemberProperties(...)
>
>     **//填充复制字段 OnRep 定长数组下标等信息**
>     BuildMemberPropertyDescriptors(...)
>
>     **//填充复制条件筛选(ELifetimeCondition)**
>     BuildMemberLifetimeConditionDescriptors(...)
>
>     **//传统复制系统的RepIndex(FProperty::RepIndex)转换为Iris系统的MemberIndex**
>     BuildMemberRepIndexToMemberDescriptors(...)
>
>     **//填充调试信息**
>     BuildMemberDebugDescriptors(...)
>
>     **//填充NetSerializerConfig信息**
>     BuildMemberSerializerConfigs(...)
>
>     **//填充ReplicationStateDescriptor之后的操作**
>     FinalizeDescriptor(...);
> ...
>
> }
>
> ```