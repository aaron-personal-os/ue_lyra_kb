# 概述

---

网络序列化器(NetSerializer)定义了一个数据类型该如何**量化、序列化、增量序列化、对比**等。

![Iris复制系统数据转换流程](http://pic.xyyxr.cn/20260504161043993.png)

Iris复制系统数据转换流程

- **PollAndCopy**:属性同步时，会先通过 PollAndCopy 操作跟复制系统存放的副本数据(ReplicationState)做对比，将有改动的字段置脏(MarkDirty)并拷贝新的数值到副本
- **Quantize**:量化(Quantize)操作将副本数据中本帧发生改动的字段量化到量化数据中
- **Serialize**:序列化会将量化数据序列化到网络字节流中准备发送
- **Deserialize**:反序列化将网络中接收到修改数据转化成量化数据。
- **Dequantize**:反量化将量化数据转换成副本数据(ReplicationState)
- **Apply(InternalApplyPropertyValue)**:将副本数据(ReplicationState)的数据拷贝到 Gameplay中

Iris复制系统为很多常用类型创建了对应的序列化器

![常用类型的序列化器](http://pic.xyyxr.cn/20260504161043994.png)

常用类型的序列化器

> 💡
>
> DefaultPropertyNetSerializerInfos.cpp 定义了常用类型的网络序列化器(NetSerializer)
>
> 比如int32的网络序列化器是FPackedInt32NetSerializer可以根据int的大小来动态决定用多少个bit位来传输

FNetSerializer的数据结构。

```cpp
struct FNetSerializer
{
	
	//序列化&反序列化函数指针
	NetSerializeFunction Serialize;
	NetDeserializeFunction Deserialize;

	//增量序列化&增量反序列化函数指针
	NetSerializeDeltaFunction SerializeDelta;
	NetDeserializeDeltaFunction DeserializeDelta;
	
	//量化&反量化函数指针
	NetQuantizeFunction Quantize;
	NetDequantizeFunction Dequantize;

	//对比函数指针
	NetIsEqualFunction IsEqual;
	
	//有效验证函数指针
	NetValidateFunction Validate;
	
	
	//反序列化后拷贝副本数据到Gameplay函数指针
	NetApplyFunction Apply;

	//两个量化数据拷贝时 深度拷贝操作(比如深度拷贝数组元素)函数指针
	NetCloneDynamicStateFunction CloneDynamicState;
	NetFreeDynamicStateFunction FreeDynamicState;
	
	//收集复制字段中UObject的引用函数指针
	NetCollectNetReferencesFunction CollectNetReferences;
	
	//NetSerializerConfig
	const FNetSerializerConfig* DefaultConfig;
	
	//量化数据的内存大小和对齐
	uint16 QuantizedTypeSize;
	uint16 QuantizedTypeAlignment;
	
	//NetSerializerConfig内存大小和对齐
	uint16 ConfigTypeSize;
	uint16 ConfigTypeAlignment;

	const TCHAR* Name;
};
```

> [!note]- 当为指定类型生成自定义网络序列化器(NetSerializer)时，实际是先创建一个NetSerializer实现类(NetSerializerImpl)，这个实现类(NetSerializerImpl)会根据需求实现FNetSerializer中的的函数接口和定义相应的特性字段。
> ```cpp
> struct FRepMovementNetSerializer
> {
>     struct FQuantizedData
>     {
>         ...
>     };
>
>     typedef FRepMovement SourceType;
>     typedef FQuantizedData QuantizedType;
>     typedef FRepMovementNetSerializerConfig ConfigType;
>
>     inline static const ConfigType DefaultConfig;
>
>     //一般需要实现以下这些基础函数
>
>     //量化
>     static void Quantize(...);
>     static void Dequantize(...);
>
>     //序列化
>     static void Serialize(...);
>     static void Deserialize(...);
>
>     //对比
>     static bool IsEqual(...);
>
>     //数据有效性验证
>     static bool Validate(...);
>
>     //下面这个按需实现
>     static void SerializeDelta(...);
>     static void DeserializeDelta(...);
>     static void Apply(...);
>     static void CloneDynamicState(...);
>     static void FreeDynamicState(...);
>     static void CollectNetReferences(...);
> }
> ```


> [!note]- 然后在创建FNetSerializer实例时会触发模板函数ConstructNetSerializer进行构造，会传入序列化器的实现类(NetSerializerImpl)给模板函数进行模板实例化，根据实现类的实现来填充FNetSerializer实例(对应的函数是否实现了，对应的特效字段是否定义了)
> ```cpp
> //FNetSerializer构造模板函数
> static constexpr FNetSerializer ConstructNetSerializer(const TCHAR* Name)
>     {
>         TNetSerializerBuilder<NetSerializerImpl> Builder;
>
>     //这里会校验下NetSerializer实现类(NetSerializerImpl) 是否实现必要的实现接口和元数据
>         Builder.Validate();
>
>         FNetSerializer Serializer = {};
>         Serializer.Version = Builder.GetVersion();
>
>         //根据定义的特效字段和实现函数来填充特性
>         Serializer.Traits = Builder.GetTraits();
>
>         //填充实现的函数接口
>         Serializer.Serialize = Builder.GetSerializeFunction();
>         Serializer.Deserialize = Builder.GetDeserializeFunction();
>         Serializer.SerializeDelta = Builder.GetSerializeDeltaFunction();
>         Serializer.DeserializeDelta = Builder.GetDeserializeDeltaFunction();
>         Serializer.Quantize = Builder.GetQuantizeFunction();
>         Serializer.Dequantize = Builder.GetDequantizeFunction();
>         Serializer.IsEqual = Builder.GetIsEqualFunction();
>         Serializer.Validate = Builder.GetValidateFunction();
>         Serializer.CloneDynamicState = Builder.GetCloneDynamicStateFunction();
>         Serializer.FreeDynamicState = Builder.GetFreeDynamicStateFunction();
>         Serializer.CollectNetReferences = Builder.GetCollectNetReferencesFunction();
>         Serializer.Apply = Builder.GetApplyFunction();
>
>         Serializer.DefaultConfig = Builder.GetDefaultConfig();
>
>         //获取类型内存大小和内存对齐信息
>         Serializer.QuantizedTypeSize = 
>         static_cast<uint16>(Builder.GetQuantizedTypeSize());
>
>         Serializer.QuantizedTypeAlignment = 
>         static_cast<uint16>(Builder.GetQuantizedTypeAlignment());
>
>
>         Serializer.ConfigTypeSize = static_cast<uint16>(Builder.GetConfigTypeSize());
>         Serializer.ConfigTypeAlignment = static_cast<uint16>(
>         Builder.GetConfigTypeAlignment());
>
>         Serializer.Name = Name;
>         return Serializer;
>     }
> ```


Builder是模板TNetSerializerBuilder的实例，会根据传入的实现类类型(NetSerializerImpl)进行模板实例化,自动生成对应版本的函数接口(GetSerializeFunction、GetTraits之类)。

```cpp
class TNetSerializerBuilder
{
	
	template<typename T = void, typename U = typename TEnableIf<HasSerialize, T>::Type, bool V = true>
	static NetSerializeFunction GetSerializeFunction() { return NetSerializerImpl::Serialize; }

	template<typename T = void, typename U = typename TEnableIf<!HasSerialize, T>::Type, char V = 0>
	static NetSerializeFunction GetSerializeFunction() { return NetSerializeFunction(0); }
	
	
	template<typename T = void, typename U = typename TEnableIf<HasSerialize, T>::Type, bool V = true>
	static NetSerializeFunction GetSerializeFunction() { return NetSerializerImpl::Serialize; }

	template<typename T = void, typename U = typename TEnableIf<!HasSerialize, T>::Type, char V = 0>
	static NetSerializeFunction GetSerializeFunction() { return NetSerializeFunction(0); }
}
```

> 💡
>
> TNetSerializerBuilder通过模板的**SFINAE**机制来获取对应的函数实现(类似函数重载，有多个同名函数根据传入类型来决定那个版本的函数适配)。
>
> SerializeDeltaFunction之类的会提供一个保底的默认实现(默认实现就是调用Serialize),
>
> Serialize之类的默认版本是一个无效的函数，实现类必须要实现这些接口
>
> static NetSerializeFunction GetSerializeFunction() { return NetSerializeFunction(0); }
>
> 这里之所以提供一个保底但无效的函数版本是为了避免函数模板实例化时，匹配不到给出模糊不清楚的错误提示，在TNetSerializerBuilder::Validate会通过static_assert在编译器给出清晰的错误提示(这是**SFINAE**机制类型安全的一种常见用法)

# NetSerializer实现类的校验

---

> 💡
>
> TNetSerializerBuilder::Validate会在是在编译期校验NetSerializer实现类(NetSerializerImpl)必须要定义实现的函数接口和元数据

**NetSerializer实现类必须满足以下条件**:

- 必须要有常量字段**Version**且类型为static constexpr uint32 默认值一般都是 0 为版本机制预留的 尚未启用)
- 特性字段的类型必须是static constexpr uint32(特性字段按需定义，详见后面)
    - bIsForwardingSerializer
    - bHasConnectionSpecificSerialization
    - bHasCustomNetReference
    - bHasDynamicState
    - bUseDefaultDelta
- 必须有类型别名SourceType(typedef 原始数据的类型)
- 必须有类型别名ConfigType(typedef NetSerializerConfig类型)
- 如果SourceType不是POD类型 则必须定义量化数据类型，并且声明QuantizedType
- 如果定义了量化数据类型，则量化数据类型必须是POD类型，且必须实现Quantize和Dequantize
- 量化数据类型的内存大小(sizeof)不要超过65535
- Quantize和Dequantize函数要么都实现 要么都不是实现(定义了量化数据类型必须实现)
- 定义了量化数据类型(QuantizedType) 则必须实现IsEqual函数
- 必须实现Serialize和DeserializeDelta函数
- SerializeDelta和DeserializeDelta函数要么都实现 要么都不是实现
- bHasCustomNetReference = true 则必须实现CollectNetReferences
- bHasDynamicState = true 则必须实现CloneDynamicState和FreeDynamicState
- CloneDynamicState和FreeDynamicState函数 要么都实现 要么都不是实现
- 转发序列化器(bIsForwardingSerializer=true)必须要需要实现的所有的接口函数

> 💡
>
> POD类型(简单的旧式数据):比如 int float之类或者简单数据聚合Struct[没有虚函数之类的复杂成员])

> 💡
>
> 转发序列化器：Struct 和数组之类的符合类型的NetSerialize且定义了bIsForwardingSerializer=true

> [!note]- 校验实现代码
> ```cpp
> static void Validate()
>     {
>     //校验常量字段常量字段 **Version**的类型(必须要有 默认值一般都是 0 为版本机制预留的 尚未启用)
> static_assert(HasVersion, 
>         "FNetSerializer must have a 'static constexpr uint32 Version' member.");
>
> //**校验特性字段bIsForwardingSerializer**的类型(如果存在会校验类型 也可以不定义这个字段)
> static_assert(!IsForwardingSerializerIsPresent || IsForwardingSerializerIsBool, "FNetSerializer bIsForwardingSerializer member should be declared as 'static constexpr bool bIsForwardingSerializer'.");
>
> //**校验特性字段bHasConnectionSpecificSerialization**的类型(如果存在会校验类型 也可以不定义这个字段)
> static_assert(!HasConnectionSpecificSerializationIsPresent || HasConnectionSpecificSerializationIsBool, "FNetSerializer bHasConnectionSpecificSerialization member should be declared as 'static constexpr bool bHasConnectionSpecificSerialization'.");
>
> //**校验特性字段bHasCustomNetReference**的类型(如果存在会校验类型 也可以不定义这个字段)
> static_assert(!HasCustomNetReferenceIsPresent || HasCustomNetReferenceIsBool, "FNetSerializer bHasCustomNetReference member should be declared as 'static constexpr bool bHasCustomNetReference'.");
>
> //**校验特性字段** **bHasDynamicState**的类型(如果存在会校验类型 也可以不定义这个字段)
> static_assert(!HasDynamicStateIsPresent || HasDynamicStateIsBool, "FNetSerializer bHasDynamicState member should be declared as 'static constexpr bool bHasDynamicState'.");
>
> //**校验特性字段** **bUseDefaultDelta**的类型(如果存在会校验类型 也可以不定义这个字段)
> static_assert(!UseDefaultDeltaIsPresent || UseDefaultDeltaIsBool, "FNetSerializer bUseDefaultDelta member should be declared as 'static constexpr bool bUseDefaultDelta'.");
>
> //**必须有类型别名SourceType(typedef 原始数据的类型)**
> static_assert(HasSourceType, "FNetSerializer must have a SourceType.");
>
> //**必须有类型别名ConfigType(typedef NetSerializerConfig类型)**
> static_assert(HasConfigType, "FNetSerializer must have a ConfigType.");
>
> //**如果定义类型别名QuantizedType(typedef 量化数据类型) 则QuantizedType类型必须是 POD类型**(简单的旧式数据:比如 int float之类或者简单数据聚合Struct[没有虚函数之类的复杂成员])
> static_assert(!HasQuantizedType || QuantizedTypeIsPod, "QuantizedType in FNetSerializer must be POD.");
>
> //**校验NetSerializerConfig**(内存大小)不要超过uint16上限了(65535)
> static_assert(GetConfigTypeSize() <= TNumericLimits<decltype(FNetSerializer::ConfigTypeSize)>::Max() , "FNetSerializer NetSerializerConfig type is too large.");
>
> //**校验NetSerializerConfig**(内存对齐)不要超过uint16上限了(65535)
> static_assert(GetConfigTypeAlignment() <= TNumericLimits<decltype(FNetSerializer::ConfigTypeAlignment)>::Max() , "FNetSerializer NetSerializerConfig type has too large alignment requirements.");
>
> //**校验量化数据类型**(**QuantizedType**)的内存大小不要超过uint16上限了(65535)
> static_assert(GetQuantizedTypeSize() <= TNumericLimits<decltype(FNetSerializer::QuantizedTypeSize)>::Max() , "FNetSerializer quantized type is too large.");
>
> //**校验量化数据类型**(**QuantizedType**)的内存对齐不要超过uint16上限了(65535)
> static_assert(GetQuantizedTypeAlignment() <= TNumericLimits<decltype(FNetSerializer::QuantizedTypeAlignment)>::Max() , "FNetSerializer quantized type has too large alignment requirements.");
>
> //**必须实现Serialize函数**
> static_assert(HasSerialize, "FNetSerializer must implement Serialize.");
> //**必须实现Deserialize函数**
> static_assert(HasDeserialize, "FNetSerializer must implement Deserialize.");
>
> //**SerializeDelta和DeserializeDelta 要么都实现 要么都不是实现**
> static_assert(HasSerializeDelta == HasDeserializeDelta, "FNetSerializer should implement both SerializeDelta and DeserializeDelta or none of them.");
>
> //**Quantize和Dequantize要么都实现 要么都不是实现**
> static_assert(HasQuantize == HasDequantize, "FNetSerializer must implement both Quantize and Dequantize or none of them.");
>
> //**如果SourceType不是POD类型 则必须定义量化数据类型，声明QuantizedType且实现Quantize和Dequantize**
> static_assert(HasQuantize || SourceTypeIsPod, "FNetSerializer must implement Quantize and Dequantize when SourceType isn't POD.");
>
> //**声明了QuantizedType则必须实现Quantize和Dequantize**
> static_assert(!HasQuantizedType || (HasQuantize && HasDequantize), "FNetSerializer must implement Quantize and Dequantize when it has a QuantizedType.");
>
> **//定义了量化数据类型(QuantizedType) 则必须实现IsEqual**
> static_assert(!HasQuantize || HasIsEqual, "FNetSerializer must implement IsEqual when it has Quantize.");
>
> **//bHasCustomNetReference = true 则必须实现CollectNetReferences**
> static_assert(!HasCustomNetReference() || (HasCustomNetReference() && HasCollectNetReferences), "FNetSerializer with bHasCustomNetReference = true must implement CollectNetReferences method.");
>
> **//bHasDynamicState = true 则必须实现CloneDynamicState和FreeDynamicState**
> static_assert(!HasDynamicStateIsBool || (HasFreeDynamicState && HasCloneDynamicState), "FNetSerializer must implement CloneDynamicState and FreeDynamicState when it has dynamic state.");
>
> //转发序列化器(Struct 和数组之类的符合类型的NetSerializer)校验
> ValidateForwardingSerializer();
> }
> ```
>
> > 💡
> >
> >     转发序列化器(Struct 和数组之类的符合类型的NetSerializer)必须要需要实现的所有的接口
>
> ```cpp
> static void ValidateForwardingSerializer()
>     {
>         static_assert(HasSerialize, "Forwarding FNetSerializer must implement Serialize.");
>         static_assert(HasDeserialize, "Forwarding FNetSerializer must implement Deserialize.");
>         static_assert(HasSerializeDelta, "Forwarding FNetSerializer must implement SerializeDelta.");
>         static_assert(HasDeserializeDelta, "Forwarding FNetSerializer must implement DeserializeDelta.");
>         static_assert(HasQuantize, "Forwarding FNetSerializer must implement Quantize.");
>         static_assert(HasDequantize, "Forwarding FNetSerializer must implement Dequantize.");
>         static_assert(HasIsEqual, "Forwarding FNetSerializer must implement IsEqual.");
>         static_assert(HasValidate, "Forwarding FNetSerializer must implement Validate.");
>         static_assert(HasCloneDynamicState, "Forwarding FNetSerializer must implement CloneDynamicState.");
>         static_assert(HasFreeDynamicState, "Forwarding FNetSerializer must implement FreeDynamicState.");
>         static_assert(HasCollectNetReferences, "Forwarding FNetSerializer must implement CollectNetReferences.");
>     }
>
> ```
>
> > 💡
> >
> >     为什么转发序列化器必须实现所有函数？因为如果转化器比实现的话，其内部的字段就是实现了转化的接口，也会因为转发序列化器缺少对应的接口导致转化链的中断


## NetSerialize特性

---

NetSerializer实现类可以通过定义指定的常量字段(static constexpr)来标记该NetSerializer开启了对应的扩展特性。

特性字段可以不定义表明不启用该特性，定义了一般设置为True表示启用该特性(bUseDefaultDelta除外)。

```cpp
class TNetSerializerBuilder
{
	//表明特性开启与否的默认状态
	struct FTraits
	{
		static constexpr bool bIsForwardingSerializer = false;
		static constexpr bool bHasConnectionSpecificSerialization = false;
		static constexpr bool bHasCustomNetReference = false;
		static constexpr bool bHasDynamicState = false;
		static constexpr bool bUseDefaultDelta = true;
		static constexpr bool bUseSerializerIsEqual = false;
	};
}

```

> [!note]- **bIsForwardingSerializer**
> 用于标识NetSerializer是否为转发序列化器（Forwarding Serializer）。
>
> 转发序列化器是一种容器型/包装型序列化器，它本身不直接处理数据，而是将序列化工作转发（Forward）给内部的子序列化器来完成。(数组和结构体类型)

> [!note]- **bHasConnectionSpecificSerialization**
> 标记该序列化器在序列化数据时，需要根据目标连接（Connection）的不同而产生不同的序列化结果。
> 应该尽量避免使用，因为它会阻止序列化状态的共享。
> FPredictionKeyNetSerializer(预测 Key)这种特殊的类型才会启用。所有这个类型的字段只会发生给主控客户端(预测Key 仅对主控端才有意义)

> [!note]- **bHasCustomNetReference**
> 标记是否实现了接口CollectNetReferences(收集UObject 引用)
>
> 标记是否实现接口CloneDynamicState 和 FreeDynamicState
>
> 用于深拷贝量化数据的动态内存(字符串、动态数组元素之类)

> [!note]- **bUseDefaultDelta**
> 标记是否将SerializeDelta视为Serialize(默认版本SerializeDelta的实现)
>
> 如果bUseDefaultDelta定义了且为false且没有自己实现SerializeDelta则触发SerializeDelta是还是会调用Serialize，不过Serialize的参数是带数据对比的FNetSerializeDeltaArgs。
>
> > 💡
> >
> >     FNetSerializeDeltaArgs是FNetSerializeArgs的子类
>
> ```cpp
> NetSerializeDeltaDefault(FNetSerializationContext& Context, const FNetSerializeDeltaArgs& Args)
> {
>     FNetIsEqualArgs EqualArgs;
>     EqualArgs.Version = 0;
>     EqualArgs.NetSerializerConfig = Args.NetSerializerConfig;
>     EqualArgs.Source0 = Args.Source;
>     EqualArgs.Source1 = Args.Prev;
>     EqualArgs.bStateIsQuantized = true;
>
>     if (Context.GetBitStreamWriter()->WriteBool(IsEqual(Context, EqualArgs)))
>     {
>         return;
>     }
>
>     Serialize(Context, Args);
> };
> ```

> [!note]- **bUseSerializerIsEqual**
> 标记是否用序列化器的自定义 IsEqual 函数进行对比(前提是实现了 IsEqual 函数，没实现了的话这个标记就是无效的)
>
> ```cpp
>
> //UseSerializerIsEqual()只有在定义了bUseSerializerIsEqual特性字段
> //且bUseSerializerIsEqual=True 且实现了 IsEqual函数时才会返回 True
> template<typename T = void, typename U = typename TEnableIf<UseSerializerIsEqualIsBool && HasIsEqual, T>::Type, bool V = true>
>     static constexpr bool UseSerializerIsEqual() { return NetSerializerImpl::bUseSerializerIsEqual; }
>
>     template<typename T = void, typename U = typename TEnableIf<!(UseSerializerIsEqualIsBool && HasIsEqual), T>::Type, char V = 0>
>     static constexpr bool UseSerializerIsEqual() { return false; }
> ```

> [!note]- 填充NetSerializer的特性(Traits)
> ```cpp
>     enum class ENetSerializerTraits : uint32
> {
>     None = 0U,
>     IsForwardingSerializer = 1U << 0U,
>     HasDynamicState = IsForwardingSerializer << 1U,
>     HasConnectionSpecificSerialization = HasDynamicState << 1U,
>     HasCustomNetReference = HasConnectionSpecificSerialization << 1U,
>     UseSerializerIsEqual = HasCustomNetReference << 1U,
>     HasApply = UseSerializerIsEqual << 1U,
> };
>
> static constexpr ENetSerializerTraits GetTraits()
>     { 
>         ENetSerializerTraits Traits = ENetSerializerTraits::None;
>         Traits |= (IsForwardingSerializer() ? ENetSerializerTraits::IsForwardingSerializer : ENetSerializerTraits::None);
>
>         Traits |= (HasConnectionSpecificSerialization() ? ENetSerializerTraits::HasConnectionSpecificSerialization : ENetSerializerTraits::None);
>
>         Traits |= (HasCustomNetReference() ? ENetSerializerTraits::HasCustomNetReference : ENetSerializerTraits::None);
>
>         Traits |= (HasDynamicState() ? ENetSerializerTraits::HasDynamicState : ENetSerializerTraits::None);
>
>         Traits |= (UseSerializerIsEqual() ? ENetSerializerTraits::UseSerializerIsEqual : ENetSerializerTraits::None);
>
>         Traits |= (HasApply ? ENetSerializerTraits::HasApply : ENetSerializerTraits::None);
>
>         return Traits;
> }
> ```


## 构建网络序列化器

---

UE已经为很多类型写好了对应的NetSerializer，参照(DefaultPropertyNetSerializerInfos.cpp)

下面以FRepMovementNetSerializer为示例，讲解下如果要单独为某个Struct定制一个NetSerializer 

### 创建对应的代码文件

---

创建XXXNetSerializer.h和XXXNetSerializer.cpp存放NetSerializer相关代码

### 声明NetSerializer

---

在.h文件中通过宏**UE_NET_DECLARE_SERIALIZER**声明定义NetSerializer及相关接口

```cpp
USTRUCT()
struct FRepMovementNetSerializerConfig : public FNetSerializerConfig
{
	GENERATED_BODY()
};

namespace UE::Net
{
UE_NET_DECLARE_SERIALIZER(FRepMovementNetSerializer, XXX_API);
}

//UE_NET_DECLARE_SERIALIZER宏展开
//声明NetSerializer的变量(在CPP中会对这个变量赋值)
struct FRepMovementSerializerNetSerializerInfo
{
	static const UE::Net::FNetSerializer Serializer;
	static uint32 GetQuantizedTypeSize();
	static uint32 GetQuantizedTypeAlignment();
	static const FNetSerializerConfig* GetDefaultConfig();
};
```

### 创建NetSerializer的实现类

---

在cpp文件先定义NetSerializer的实现类(NetSerializerImpl),并实现对应的函数接口

```cpp
struct FRepMovementNetSerializer
{
	struct FQuantizedData
	{
		...
	};
	
	typedef FRepMovement SourceType;
	typedef FQuantizedData QuantizedType;
	typedef FRepMovementNetSerializerConfig ConfigType;
	
	inline static const ConfigType DefaultConfig;
	
	//一般需要实现以下这些基础函数
	
	//量化
	static void Quantize(...);
	static void Dequantize(...);
	
	//序列化
	static void Serialize(...);
	static void Deserialize(...);
	
	//对比
	static bool IsEqual(...);
	//数据有效性验证
	static bool Validate(...);
	
	//下面这个按需实现
	static void SerializeDelta(...);
	static void DeserializeDelta(...);
	static void Apply(...);
	static void CloneDynamicState(...);
	static void FreeDynamicState(...);
	static void CollectNetReferences(...);
}
```

### **通过实现类构建NetSerializer**

---

宏**UE_NET_IMPLEMENT_SERIALIZER**通过实现类FRepMovementNetSerializer构建了对应的FNetSerializer对象实例。

调用模板函数ConstructNetSerializer 创建NetSerializer对象实例 并填充

```cpp
struct FRepMovementNetSerializer
{
...
...
}
**UE_NET_IMPLEMENT_SERIALIZER**(FRepMovementNetSerializer);

//UE_NET_IMPLEMENT_SERIALIZER展开代码

//这里调用模板函数ConstructNetSerializer 创建NetSerializer对象实例 并赋值
const UE::Net::FNetSerializer FRepMovementNetSerializerNetSerializerInfo::Serializer = 
UE::Net::TNetSerializer<FRepMovementNetSerializer>::ConstructNetSerializer(L"FRepMovementNetSerializer");

uint32 FRepMovementNetSerializerNetSerializerInfo::GetQuantizedTypeSize()
{
	return UE::Net::TNetSerializerBuilder<FRepMovementNetSerializer>::GetQuantizedTypeSize();
};

uint32 FRepMovementNetSerializerNetSerializerInfo::GetQuantizedTypeAlignment()
{
	return UE::Net::TNetSerializerBuilder<FRepMovementNetSerializer>::GetQuantizedTypeAlignment();
};

const FNetSerializerConfig* FRepMovementNetSerializerNetSerializerInfo::GetDefaultConfig()
{
	return UE::Net::TNetSerializerBuilder<FRepMovementNetSerializer>::GetDefaultConfig();
};
```

### **注册NetSerializer**

---

注册自定义的NetSerializer，将生成FNetSerializer与类型关联起来

> [!note]- 在实现类 FRepMovementNetSerializer 内部定义一个内部类FNetSerializerRegistryDelegates 继承自UE::Net::FNetSerializerRegistryDelegates。这个类作用就是将自定义类型的NetSerializer跟类型进行绑定。
> ```cpp
> struct FRepMovementNetSerializer
> {
> ...
> private:
>     class FNetSerializerRegistryDelegates final : 
>     private UE::Net::FNetSerializerRegistryDelegates
>     {
>     public:
>         virtual ~FNetSerializerRegistryDelegates();
>
>     private:
>         virtual void OnPreFreezeNetSerializerRegistry() override;
>
>         inline static const FName RepMovementNetSerializer = FName("RepMovement");
>         UE_NET_IMPLEMENT_NAMED_STRUCT_NETSERIALIZER_INFO(RepMovementNetSerializer, 
>         FRepMovementNetSerializer);
>     };
>
>     inline static FRepMovementNetSerializer::
>     FNetSerializerRegistryDelegates NetSerializerRegistryDelegates;
> ...
> }
>
> ```


> [!note]- 定义静态变量NetSerializerRegistryDelegates时，其构造函数会触发委托绑定，在执行NetSerializer注册时，会触发PreFreezeNetSerializerRegistry和PostFreezeNetSerializerRegistry，
> ```cpp
>     void RegisterPropertyNetSerializerSelectorTypes()
>     {
>         ...
>
>         //注册前的操作 可以加入自定义的NetSerializer注册
>         FInternalNetSerializerDelegates::BroadcastPreFreezeNetSerializerRegistry();
>
>         //注册UE预设的NetSerializer
>         RegisterDefaultPropertyNetSerializerInfos();
>
>         FPropertyNetSerializerInfoRegistry::Freeze();
>
>         //注册完成的操作
>         FInternalNetSerializerDelegates::BroadcastPostFreezeNetSerializerRegistry();
>
>     ...
>     }
> ```


> [!note]- 自定义的NetSerializer可以在PreFreezeNetSerializerRegistry执行注册(析构时需要取消注册)。
> UE_NET_REGISTER_NETSERIALIZER_INFO  注册宏
>
> UE_NET_UNREGISTER_NETSERIALIZER_INFO 取消注册宏
>
> UE_NET_IMPLEMENT_NAMED_STRUCT_NETSERIALIZER_INFO 注册信息获取宏
>
> ```cpp
> void FRepMovementNetSerializer::FNetSerializerRegistryDelegates::
> OnPreFreezeNetSerializerRegistry()
> {
> ...
>     UE_NET_REGISTER_NETSERIALIZER_INFO(RepMovementNetSerializer);
> ...
> }
>
> //析构时需要取消注册
> FRepMovementNetSerializer::FNetSerializerRegistryDelegates::
> ~FNetSerializerRegistryDelegates()
> {
>     UE_NET_UNREGISTER_NETSERIALIZER_INFO(RepMovementNetSerializer);
> }
>
> //UE_NET_REGISTER_NETSERIALIZER_INFO 展开
> //通过函数GetPropertyNetSerializerInfo_RepMovementNetSerializer获取注册信息
> UE::Net::FPropertyNetSerializerInfoRegistry::
> Register(&GetPropertyNetSerializerInfo_RepMovementNetSerializer());
>
> //Register的实现FProperty与PropertyNetSerializerInfo实例的映射(一对多)
> void FPropertyNetSerializerInfoRegistry::
> Register(const FPropertyNetSerializerInfo* Info)
> {
>     check(Info);
>
>     const FFieldClass* PropertyClass = Info->GetPropertyTypeClass();
>
>     check(PropertyClass);
>
>     Registry.AddUnique(MakeTuple<>(PropertyClass, Info));
>
>     bRegistryIsDirty = true;
> }
> ```


GetPropertyNetSerializerInfo_RepMovementNetSerializer()获取注册信息的函数实现在宏**UE_NET_IMPLEMENT_NAMED_STRUCT_NETSERIALIZER_INFO**中

```cpp
inline static const FName RepMovementNetSerializer = FName("RepMovement");
UE_NET_IMPLEMENT_NAMED_STRUCT_NETSERIALIZER_INFO(RepMovementNetSerializer, 
		FRepMovementNetSerializer);
		
		
//宏展开后
const UE::Net::FPropertyNetSerializerInfo& 
GetPropertyNetSerializerInfo_RepMovementNetSerializer()
	{
		static UE::Net::FNamedStructPropertyNetSerializerInfo StaticInstance(RepMovementNetSerializer,  static_cast<const UE::Net::FNetSerializer&>(FRepMovementNetSerializerNetSerializerInfo::Serializer));

	return StaticInstance;
};
		
```

GetPropertyNetSerializerInfo_RepMovementNetSerializer 返回的**FNamedStructPropertyNetSerializerInfo**(FPropertyNetSerializerInfo子类)的实例，包含了类型信息(StructName)和FNetSerializer实例(Serializer)。

到这里类型跟对应的NetSerializer就绑定起来了。

```cpp
struct FNamedStructPropertyNetSerializerInfo : public TSimplePropertyNetSerializerInfo<FStructProperty>
{
	FName StructName;
	const FNetSerializer& Serializer;
}
```

> 💡
>
> 以下都是绑定类型和网络序列化器的宏，实现逻辑跟上面类似
>
> 简单类型的实现宏
> UE_NET_IMPLEMENT_NETSERIALIZER_INFO
>
> UE_NET_IMPLEMENT_SIMPLE_NETSERIALIZER_INFO
>
> Struct类型的实现宏
> UE_NET_IMPLEMENT_NAMED_STRUCT_NETSERIALIZER_INFO
>
> UE_NET_IMPLEMENT_NAMED_STRUCT_NETSERIALIZER_WITH_CUSTOM_FRAGMENT_INFO
> UE_NET_IMPLEMENT_NAMED_STRUCT_LASTRESORT_NETSERIALIZER_INFO
>
> UE_NET_IMPLEMENT_NAMED_STRUCT_LASTRESORT_NETSERIALIZER_INFO_WITH_SIZE_OVERRIDE

## **通过字段类型查找到对应的NetSerializer**

---

在创建类型的复制状态描述符(ReplicationStateDescriptor)时,

> [!note]- 先根据字段的反射信息FProperty查找到对应的NetSerializerInfo(FPropertyNetSerializerInfo实例)
> > 💡
> >
> >     比如上面创建的FNamedStructPropertyNetSerializerInfo的对象实例
>
> ```cpp
> bool FPropertyReplicationStateDescriptorBuilder::IsSupportedProperty(...)
> {
> ...
> //这里可以通过字段的反射信息FProperty在注册表中查找到对应的NetSerializerInfo
> //(比如上面创建的FNamedStructPropertyNetSerializerInfo的对象实例)
> const FPropertyNetSerializerInfo* NetSerializerInfo = 
> FPropertyNetSerializerInfoRegistry::FindSerializerInfo(Property);
>
>     ...
>     OutMemberProperty.SerializerInfo = NetSerializerInfo;
>     ...
>
> ...
> }
> ```

> [!note]- 再通过NetSerializerInfo查找到到对应的FNetSerializer对象示例(Serializer )，这样就成功在ReplicationStateDescriptor为类型关联上了对应的NetSerializer。
> ```cpp
> void FPropertyReplicationStateDescriptorBuilder::BuildMemberSerializerDescriptors(...) 
> {
>
>     for (const FMemberProperty& Info : Members)
>     {
>         CurrentMemberSerializerDescriptor->Serializer = 
>         Info.SerializerInfo->GetNetSerializer(Info.Property);
>
>     }
> }
> ```
>
>
> > 💡
> >
> > FindSerializerInfo是根据注册的类型找到对应的NetSerializer信息，如果一个类型(比如FText)没在注册列表中，则会用兜底的FLastResortPropertyNetSerializer，旧版的复制方式(调用
> > FProperty的NetSerializeItem)，效率较低，不建议使用。(部分类型不支持NetSerializeItem就无法复制，比如Map和Set)

```cpp
void FLastResortPropertyNetSerializer::Quantize(...)
{
...
	Property->NetSerializeItem(...);
...
}
```

> 💡
>
> FNamedStructLastResortPropertyNetSerializerInfo则是FLastResortPropertyNetSerializer的子类，使用旧版的复制系统来复制指定类型的Struct类型，不推荐使用。
>
> 使用这种方式一定需要实现自定义的NetSerialize

```cpp
bool FStructProperty::NetSerializeItem(...) const
{

	if (Struct->StructFlags & STRUCT_NetSerializeNative)
	{
	...
		UScriptStruct::ICppStructOps* CppStructOps = Struct->GetCppStructOps();
		check(CppStructOps); // else should not have STRUCT_NetSerializeNative
		bool bSuccess = true;
		bool bMapped = CppStructOps->NetSerialize(Ar, Map, bSuccess, Data);
		...
	}

	UE_LOG( LogProperty, Fatal, TEXT( "Deprecated code path" ) );

	return 1;
}
```

> 💡
>
> Map/Set容器类型不支持网络复制

```cpp
bool FSetProperty::NetSerializeItem(...) const
{
	UE_LOG( LogProperty, Error, TEXT( "Replicated TSets are not supported." ) );
	return 1;
}

bool FMapProperty::NetSerializeItem(...) const
{
	UE_LOG( LogProperty, Error, TEXT( "Replicated TMaps are not supported." ) );
	return 1;
}
```

[UE 反射](https://www.notion.so/UE-bafaa2a141a44996b0ce634c78784d21?pvs=21) 

## 转发序列化器(ForwardingSerializer)

---

转发序列化器是一种容器型/包装型序列化器，它本身不直接处理数据，而是将序列化工作转发（Forward）给内部的子序列化器来完成。

可以在转发序列化器的实现类定义字段bIsForwardingSerializer =true来标记NetSerializer为转发序列化器。

```cpp
struct FStructNetSerializer
{
public:
	...
	static constexpr bool bIsForwardingSerializer = true; 
	...
}
```

典型的转发序列化器类型：

- FStructNetSerializer
- FArrayPropertyNetSerializer
- FInstancedStructNetSerializer
- FPolymorphicStructNetSerializer
- FSoftObjectNetSerializer
- FFieldPathNetSerializer

**bIsForwardingSerializer的作用:**

- 识容器型序列化器：表明这是一个将工作转发给子序列化器的包装器
- 强制完整实现：编译期确保实现所有11个必需函数
- 保证转发链完整：确保递归转发不会中断
- 防止内存泄漏：强制实现动态状态管理函数
- 确保引用追踪：强制实现网络引用收集
- 提供清晰错误：编译期给出明确的错误信息

应该使用使用 bIsForwardingSerializer = true的场景：

- 结构体序列化器（包含多个成员）
- 数组/容器序列化器（包含多个元素）
- 多态类型序列化器（转发给具体类型）
- 包装器序列化器（如软引用、字段路径）

不需要使用的场景：

- 简单数据类型（int、float、bool、FVector）
- 叶子节点序列化器（直接读写位流）
- 不需要转发的自定义类型

## 量化

---

在Iris复制系统引入了一个量化(Quantize)的概念。量化操作就是将副本数据(复制系统对Gameplay原始复制数据的备份)转换为更适合网络传输和存储的格式(新的数据结构)的过程。

> 💡
>
> 量化操作是Iris系统实现高效网络复制的核心机制之一，通过在内存表示和网络传输之间进行智能转换来优化整体性能

**量化目的&优势**

- 压缩数据：减少网络传输的数据量
- 优化存储：使用更紧凑的内部表示
- 提高性能：减少序列化/反序列化开销
- 精度控制：可根据需要调整量化精度

![Iris数据内存布局](http://pic.xyyxr.cn/20260504161043995.png)

Iris数据内存布局

> 💡
>
> - 副本数据只保留原始数据中需要复制的字段(复制字段的内存布局跟原始数据的一致)
> - 量化数据相对于副本数据为了适配更高效的序列化和压缩数据量，可以是新的类型，新的内存布局(具体参照后面示例)。
> - 量化数据中只保留需要复制的字段。比如复制字段中嵌套了一个Struct的，副本数据中是保留完整的Struct的内存布局，而量化数据则只保留Struct中需要复制的子字段，不复制的子字段丢弃，内存更加连续紧凑。

**以FRepMovementNetSerializer为例进行说明:**

```cpp
struct FRepMovement
{
	FVector LinearVelocity;
	FVector AngularVelocity;
	FVector Location;
	FRotator Rotation;
	FVector Acceleration;
	uint8 bSimulatedPhysicSleep : 1;
	uint8 bRepPhysics : 1;
	uint8 bRepAcceleration : 1;
	int32 ServerFrame;
	int32 ServerPhysicsHandle = INDEX_NONE;
	EVectorQuantization LocationQuantizationLevel;
	EVectorQuantization VelocityQuantizationLevel;
	ERotatorQuantization RotationQuantizationLevel;
}

struct FRepMovementNetSerializer
{
	struct FQuantizedData
	{
		uint64 LinearVelocity[4];
		uint64 AngularVelocity[4];
		uint64 Location[4];
		uint16 Rotation[4];
		uint64 Acceleration[4];
		int32 ServerFrame;
		int32 ServerPhysicsHandle;

		uint16 Flags : 4;
		uint16 VelocityQuantizationLevel : 2;
		uint16 LocationQuantizationLevel : 2;
		uint16 RotationQuantizationLevel : 1;
		uint16 RepAcceleration : 1;
		uint16 Unused : 6;
		uint16 Padding[3];
	};
}

enum class EVectorQuantization : uint8
{
	//向量分量值四舍五入后只保留整数
	RoundWholeNumber,
	///向量分量值四舍五入后保留一位小数
	RoundOneDecimal,
	///向量分量值四舍五入后保留两位小数
	RoundTwoDecimals
};

enum class ERotatorQuantization : uint8
{
	//旋转分量值用8 bit存储 
	//将 [0->360) 映射位 [0->256) 精度低一点
	ByteComponents,
	//旋转分量值用16 bit存储
	//将 [0->360) 映射位 [0->65536) 精度高一点
	ShortComponents
};
```

对比两者，可以看出量化数据结构(FRepMovementNetSerializer::FQuantizedData)跟原始数据结构FRepMovement有比较大的差异。

这样做的目的是为了更高效的序列化和压缩数据量。

- FRepMovementNetSerializer::Quantize会将FRepMovement类型数据转换成更适合序列化的FRepMovementNetSerializer::FQuantizedData类型的数据
- 然后FRepMovementNetSerializer::Serialize对FRepMovementNetSerializer::FQuantizedData类型的数据序列化时进行压缩。

**详细分析：**

> [!note]- FVector 类型的通过FPackedVectorNetSerializerBase来压缩数据(根据EVectorQuantization 配置来决定是只保留整数部分、保留一位小数、保留两位小数)。
> > 💡
> >
> >     FPackedVectorNetSerializerBase将浮点数转换成uint64,然后根据最大分向量值的大小动态算出占用的bit位，来减少数据量。(不压缩一个分向量可能是32bit或者64bit)

> [!note]- FRotator 类型的通过FRotatorAsByteNetSerializerBase或者FRotatorAsShortNetSerializerBase来压缩数据(根据ERotatorQuantization 配置决定用哪个精度的)
> > 💡
> >
> >     FRotatorAsByteNetSerializerBase或者FRotatorAsShortNetSerializerBase将浮点型转换成uint8（将 [0->360) 映射位 [0->256)）和uint16(将 [0->360) 映射为[0->65536)，分别用8bit和16bit存放旋转分量，区别就是FRotatorAsShortNetSerializerBase精度高一点


> [!note]- Flags 用来记录bSimulatedPhysicSleep、bRepPhysics 、ServerFrame、ServerPhysicsHandle这四个字段是否被修改过，没被修改过的就跳过。
> > 💡
> >
> >     bSimulatedPhysicSleep、bRepPhysics 不需要单独序列化了 根据Flags 就可以推断出来

> [!note]- 序列化时Flags 、VelocityQuantizationLevel 、LocationQuantizationLevel 、RotationQuantizationLevel 共用一个int32
> > 💡
> >
> >     加起来只占用了9bit

> [!note]- ServerFrame、ServerPhysicsHandle 用压缩版本的Int序列化(WritePackedInt32)压缩数据
> > 💡
> >
> >     WritePackedInt32根据int的大小动态算出占用的字节数(1~4个字节)

- bRepAcceleration单独用bool序列化

```cpp
void FRepMovementNetSerializer::Serialize(...)
{
	const QuantizedType& Value = *reinterpret_cast<const QuantizedType*>(Args.Source);

	FNetBitStreamWriter* Writer = Context.GetBitStreamWriter();

	//Flags 、VelocityQuantizationLevel 、LocationQuantizationLevel 、RotationQuantizationLevel 共用一个int32
	constexpr uint32 QuantizationLevelsBitOffset = 4;
	const uint32 FlagsAndQuantizationLevels = 
	(((Value.RotationQuantizationLevel << 4U) | 
	(Value.LocationQuantizationLevel << 2U) | 
	Value.VelocityQuantizationLevel) << QuantizationLevelsBitOffset) | Value.Flags;
	
	if (Writer->WriteBool(FlagsAndQuantizationLevels != 0))
	{
		Writer->WriteBits(FlagsAndQuantizationLevels, 
		QuantizationLevelsBitCount + QuantizationLevelsBitOffset);
	}
	
	

	//FVector 类型通过FPackedVectorNetSerializerBase来压缩数据
	if (Value.Flags & Flag_RepPhysics)
	{
		const FNetSerializer* Serializer = 
		VectorNetQuantizeNetSerializers[Value.VelocityQuantizationLevel];
		...
		Serializer->Serialize(Context, MemberArgs);
	}
	....

	// FRotator 类型通过FRotatorAsByteNetSerializerBase或者FRotatorAsShortNetSerializerBase来压缩数据
	{
	
		const FNetSerializer* Serializer = 
		RotatorNetSerializers[Value.RotationQuantizationLevel];
	 ...
		Serializer->Serialize(Context, MemberArgs);
	}

	// 用压缩版本的Int序列化(WritePackedInt32)压缩数据
	if (Value.Flags & Flag_ServerFrameIsPresent)
	{
		WritePackedInt32(Writer, Value.ServerFrame);
	}
 ...

}
```

## 增量序列化

---

Iris的复制系统提供一种增量序列化的机制，将数据序列化到网络字节流时，不用序列化完整的数据，可以通过跟上一次量化数据做对比，只序列化差异部分，以此来减少带宽开销。

> [!note]- **以int32的增量序列化为例**
> ```cpp
> //以int32的增量序列化为例
> struct FPackedInt32NetSerializerBase
> {
>     static constexpr SIZE_T DeltaBitCountTableEntryCount = 3;
>     static constexpr uint8 DeltaBitCountTable[] = {0, 4, 14};
> };
>
> static inline void SerializeUintDeltaImpl( FNetBitStreamWriter& Writer, 
>     const T Value,                    // 当前值
>     const T PrevValue,                // 前一个值
>     const uint8* SmallBitCountTable,  // 小比特数查找表({0, 4, 14})
>     const uint32 SmallBitCountTableEntryCount, // 表项数量(3)
>     uint8 LargeBitCount               // 大值比特数(32Bit)
> {
>     //计算无符号增量(两个int的差值)，并限制在 LargeBitCount 范围内
>     const T UnsignedDelta = (Value - PrevValue) & 
>     (~T(0) >> (TypeBitCount - LargeBitCount));
>
>     // 将无符号增量转换为有符号增量（二进制补码技巧）
> const T DeltaSignMask = T(1) << (LargeBitCount - 1U);
> const SignedType Delta = SignedType((UnsignedDelta ^ DeltaSignMask) - DeltaSignMask);
>
>     //计算增量所需比特数
>     const uint32 BitCountForDelta = GetBitsNeeded(Delta);
>
>     if (BitCountForDelta <= MaxDeltaBitCount)
>     {
>         for (uint32 TableIndex = 0, 
>         TableEndIndex = SmallBitCountTableEntryCount; 
>         TableIndex != SmallBitCountTableEntryCount; 
>         ++TableIndex)
>         {
>             const uint32 SmallBitCount = SmallBitCountTable[TableIndex];
>             if ((BitCountForDelta <= SmallBitCount) | (Delta == 0))
>             {
>                 //记录存放差量用了几个Bit位(根据索引去SmallBitCountTable找)
>                 Writer.WriteBits(TableIndex + 1U, BitCountForTableIndex);
>                 //写入差量值
>                 Writer.WriteBits(static_cast<uint32>(static_cast<T>(Delta)), SmallBitCount);
>                 return;
>             }
>         }
>     }
>     else
>     {
>         //差值占的bit位超过了DeltaBitCountTable的范围 直接写入完整值
>         Writer.WriteBits(0U, BitCountForTableIndex);
>         Writer.WriteBits(static_cast<uint32>(Value), LargeBitCount);
>     }
> }
> ```
>
> > 💡
> >
> >     还可以参照移动数据的差异化
> >     FRepMovementNetSerializer::SerializeDelta


> [!note]- **通过配置文件来决定对应的UObject是否开启增量序列化**
> ```cpp
>
> bool UObjectReplicationBridge::ShouldClassBeDeltaCompressed(const UClass* Class)
> {
>     using namespace UE::Net;
>
>     if (ClassesWithDeltaCompression.Num() > 0)
>     {
>         //配置类的子类也会自动开启
>         for (; Class != nullptr; Class = Class->GetSuperClass())
>         {
>             if (bool* bShouldBeDeltaCompressed = 
>             ClassesWithDeltaCompression.Find(GetConfigClassPathName(Class)))
>             {
>                 return *bShouldBeDeltaCompressed;
>             }
>         }
>     }
>
>     return false;
> }
> ```
>
> > 💡
> >
> >     Pawn和PlayerState及其子类开启了增量序列化
>
> ```cpp
> +DeltaCompressionConfigs=(ClassName=/Script/Engine.Pawn))
> +DeltaCompressionConfigs=(ClassName=/Script/Engine.PlayerState))
> +DeltaCompressionConfigs=(ClassName=/Script/GameplayDebugger.GameplayDebuggerCategoryReplicator))
> ```
>
>
> > 💡
> >
> > 默认增量序列化和反序列提供默认实现，如果类型的网络序列化未提供
> >
> > SerializeDelta和DeserializeDelta的实现则增量序列化和反序列时默认调用的是
> > Serialize和Deserialize实现。所以对应UObject开启了增量序列化后，还需要复制字段对应的类型也实现了SerializeDelta和DeserializeDelta操作。

```cpp
static NetSerializeDeltaFunction GetSerializeDeltaFunction() { return NetSerializeDeltaDefault<NetSerializerImpl::Serialize>; }

static NetDeserializeDeltaFunction GetDeserializeDeltaFunction(...) { 
return NetDeserializeDeltaDefault<NetSerializerImpl::Deserialize>; }

void NetSerializeDeltaDefault(...)
{
	Serialize(Context, Args);
};

void NetDeserializeDeltaDefault(...)
{
	if (Context.GetBitStreamReader()->ReadBool())
	{
		// Clone from prev. Need to free target first.
		if (FreeDynamicState != NetFreeDynamicStateFunction(nullptr))
		{
			FNetFreeDynamicStateArgs FreeArgs;
			FreeArgs.Version = 0;
			FreeArgs.NetSerializerConfig = Args.NetSerializerConfig;
			FreeArgs.Source = Args.Target;

			FreeDynamicState(Context, FreeArgs);
		}

		FMemory::Memcpy(reinterpret_cast<uint8*>(Args.Target), 
		reinterpret_cast<uint8*>(Args.Prev), QuantizedTypeSize);

		if (CloneDynamicState != NetCloneDynamicStateFunction(nullptr))
		{
			FNetCloneDynamicStateArgs CloneArgs;
			CloneArgs.Version = 0;
			CloneArgs.NetSerializerConfig = Args.NetSerializerConfig;
			CloneArgs.Source = Args.Prev;
			CloneArgs.Target = Args.Target;

			CloneDynamicState(Context, CloneArgs);
		}

		return;
	}

	Deserialize(Context, Args);
}
```

> [!note]- **发送端增量序列化的基准数据**
> ```cpp
> //发送端的基准数据了记录了两份基准数据(已发送待确认的 已发送已确认的)
> class FObjectBaselineInfo
> {
> public:
>     FInternalBaseline Baselines[2];
> };
>
> //发送端发送数据时记录 本次发送的数据到基准信息中(已发送待确认的)
> FReplicationWriter::WriteObjectAndSubObjects(...)
> {
> ...
>
>                 if (Info.PendingBaselineIndex == 
>                 FDeltaCompressionBaselineManager::InvalidBaselineIndex)
>                 {
>
>                     const uint32 NextBaselineIndex = bIsInitialState ? 
>                     0U : (Info.LastAckedBaselineIndex + 1U) % FDeltaCompressionBaselineManager::MaxBaselineCount;
>
>                     FDeltaCompressionBaseline NewBaseline = 
>                     BaselineManager->CreateBaseline(...);       
> ...
> }
>
> void FReplicationWriter::ProcessDeliveryNotification(...)
> {
>     if (PacketDeliveryStatus == EPacketDeliveryStatus::Delivered)
>         {
>             ...
>                 { 
>                     //接收端确认收到的发送的数据
>                     //(收到了话将发送的数据作为下次增量序列化的基准数据 已发送已确认的)
>                     HandleDeliveredRecord(RecordInfo, Info, AttachmentRecord);
>                 }
>             );
>         }
>         else if (PacketDeliveryStatus == EPacketDeliveryStatus::Lost)
>         {
>             //接收端丢包 
>             ...
>                 {
>                     HandleDroppedRecord(RecordInfo, Info, AttachmentRecord);
>                 }
>             );
>         }
>         else if (PacketDeliveryStatus == EPacketDeliveryStatus::Discard)
>         {
>             //连接关闭清理释放
>             ...
>                 {
>                     HandleDiscardedRecord(RecordInfo, Info, AttachmentRecord);
>                 }
>             );
>         }
> }
>
> void FReplicationWriter::HandleDeliveredRecord(...)
> {
>     if (RecordInfo.NewBaselineIndex != 
>     FDeltaCompressionBaselineManager::InvalidBaselineIndex)
>     {
>         ...
>         //移除上一个已发送已确认的基准数据 改为当前最新确认的基准数据
>         if (Info.LastAckedBaselineIndex != 
>         FDeltaCompressionBaselineManager::InvalidBaselineIndex)
>         {           
>             BaselineManager->DestroyBaseline(Parameters.ConnectionId, 
>             InternalIndex, 
>             Info.LastAckedBaselineIndex);
>         }
>         Info.LastAckedBaselineIndex = RecordInfo.NewBaselineIndex;
>     }
> }
>
> void FReplicationWriter::HandleDroppedRecord(...)
> {
>     if (RecordInfo.NewBaselineIndex != 
>     FDeltaCompressionBaselineManager::InvalidBaselineIndex)
>     {
>      //最近一次发送的数据 接收失败 放弃发送时记录的基准数据
>         BaselineManager->LostBaseline(...);
>     }
> }
> ```
>
> ![发送端发送数据时记录 本次发送的数据到基准信息中](http://pic.xyyxr.cn/20260504161043996.png)
>
> 发送端发送数据时记录 本次发送的数据到基准信息中
>
> ![接收端确认收到的基准数据](http://pic.xyyxr.cn/20260504161043997.png)
>
> 接收端确认收到的基准数据

> [!note]- **接收端获取增量序列化的基准数据**
> ```cpp
> class FReplicationReader
> {
>         struct FReplicatedObjectInfo
>         {
>         ...
>         //数据接收端会保留一份用于增量序列的基准数据 来对比差异
>         //存放了两份基准数据 本次接收的基准数据和上次接收的基准数据
>         uint8* StoredBaselines[2];
>         ...
>         }
> }
>
> void FReplicationReader::ReadObjectInBatch(...)
> {
> }
>
> uint8* FReplicationStateStorage::AllocBaseline(...)
> {
> ...
> case EReplicationStateType::CurrentSendState:
>         {
>         //将接受到的数据 拷贝一份放到增量序列的基准数据中
>         CloneState(Protocol, Storage, ObjectInfo->StateBuffers[(unsigned)EStateBufferType::SendState]);
>             break;
>         };
> ...
> }
> ```


## 拷贝数据到Gameplay(Apply)

---

![InternalApplyPropertyValue 将接收到的网络数据复制到 Gameplay](http://pic.xyyxr.cn/20260504161043998.png)

InternalApplyPropertyValue 将接收到的网络数据复制到 Gameplay

```cpp
void InternalApplyPropertyValue(...)
{
...
		//如果类型对应 NetSerializer 实现了 Apply 函数，则直接调用 Apply 函数
		if (EnumHasAnyFlags(MemberSerializerDescriptor.Serializer->Traits, 
		ENetSerializerTraits::HasApply))
	{
		FNetSerializationContext Context;
		FNetApplyArgs ApplyArgs;
		ApplyArgs.NetSerializerConfig = MemberSerializerDescriptor.SerializerConfig;
		ApplyArgs.Source = NetSerializerValuePointer(Src);
		ApplyArgs.Target = NetSerializerValuePointer(Dst);
		MemberSerializerDescriptor.Serializer->Apply(Context, ApplyArgs);
		return;
	}
	
	if (IsUsingStructNetSerializer(MemberSerializerDescriptor))
	{
		 //处理 Struct 类型
	}
	else if (IsUsingArrayPropertyNetSerializer(MemberSerializerDescriptor))
	{
		//处理数组类型
	}
	
	//默认操作 直接拷贝
	const FProperty* Property = Descriptor->MemberProperties[MemberIndex];
	Property->CopySingleValue(Dst, Src);
	
...
}
```

InternalApplyPropertyValue将副本数据拷贝到Gameplay对应的复制字段时，通过FReplicationStateDescriptor总存放的字段反射数据Property获取内存偏移信息。

```cpp
void FPropertyReplicationState::PushPropertyReplicationState(...) const
{
...
for (uint32 MemberIt = 0; MemberIt < MemberCount; ++MemberIt)
		{
			...

				PushPropertyValue(MemberIt, 
				DstBuffer + Property->GetOffset_ForGC() + Property->GetElementSize()*MemberPropertyDescriptor.ArrayIndex);
....
			}
		}
...
}
```