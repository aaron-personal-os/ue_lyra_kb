# 概述

---

FNetToken 系统用于优化网络复制中的"稳定数据"，支持类型如下

- FName
- GameplayTag(本质也是FName)
- 字符串常量(比如网络同步需要传输的资产路径)
- Struct(仅适用那些只有值变化只有有限排列组合的 慎用)

**实现思路**:

- 给FName(或者其他支持类型)运行时动态分配一个唯一标识(Token)，并跟原始数据建立映射关系
- 首次网络同步时会将标识(Token)和原始数据都发送给接收端，并在接收端建立原始数据和Token的映射关系.
- 后续就可以只发送Token节省网络数据量，接收端拿到Token后再查找映射关系来获取对应的原始数据。

FNetToken 是一个紧凑的 32 位结构体

```cpp
class FNetToken
{
private:
    union 
    {
        struct
        {
            uint32 Index : 20; // Token 索引（20位，映射数组索引 数组最大 1,048,576 个）
            uint32 TypeId : 3; // Token 类型ID（3位，标识Token类型 最多 8 种类型）
            uint32 bIsAssignedByAuthority : 1; // 是否由权威端分配（1位）
            uint32 Padding : 8;// 填充位(预留)
        };
        uint32 Value;// 整体值
    };
};
```

**NetToken的优势&特性**

> [!note]- 带宽优化:大幅度节省网络带宽
> > 💡
> >
> >     Token 仅占 20-23 位（取决于是否写入 TypeId）
> >     相比以前把 FName当完整字符串发送，节省 90%+ 带宽
> >
> >     第一次发送 Token 时，同时发送完整数据
> >
> >     接收端建立完整的映射关系，后续仅发送 Token（节省带宽），收到Token后再查找映射关系来获取对应的原始数据


> [!note]- 类型安全
> > 💡
> >
> >     通过模板参数 T 指定 DataStore 类型
> >     开发构建中自动验证类型匹配
> >
> >     每种数据类型有独立的 TypeId（0-7）
> >     每种类型有独立的 TokenDataStore
> >     每种类型有独立的映射数组

> [!note]- 双端支持
> > 💡
> >
> >     每个连接独立维护:
> >
> >     LocalNetTokenStoreState：存储本地创建的Token映射信息(FNetTokenStoreKey)
> >     RemoteNetTokenStoreState：存储远程接收的Token映射信息(FNetTokenStoreKey)
> >
> >     服务器和客户端都可以分配 Token
> >     通过 bIsAssignedByAuthority 标志区分来源
> >
> >     客户端临时 Token 会被权威 Token 替换，保证全局一致性(类似NetGuid之类的网络唯一标识)
> >
> >     通过消息包确认机制(Ack) 确保 Token数据能最终达到远程端


> [!note]- 灵活性
> ![image.png](http://pic.xyyxr.cn/20260504161043999.png)
>
> > 💡
> >
> >     支持多种数据类型
> >
> >     FName(FNameTokenStore)
> >
> >     GameplayTag(FGameplayTagTokenStore)(FNameTokenStore子类)
> >
> >     字符串常量(FStringTokenStore)(发送UObject路径时)
> >
> >     Struct(TStructNetTokenDataStore)
> >     每种类型有独立的 FNetTokenDataStore


> [!note]- 映射体系
>
> ![映射关系](http://pic.xyyxr.cn/20260504161044000.png)
>
> 映射关系
>
> > 💡
> >
> >     KeyIndex时映射数组索引
> >
> >     网络传输的是FNetToken（TypeId+Index+bIsAssignedByAuthority）


**使用NetToken的注意事项**

- 类型必须匹配：调用 WriteNetTokenWithKnownType<T> 时，Token 必须是由 T 类型的 DataStore 创建的
- 导出管理：首次使用 Token 时需要调用 AppendExport 导出完整数据
- 连接状态：每个连接维护独立的 AcknowledgedExports来跟踪连接已导出的 Token
- Token 限制：最多支持  8 种类型，每种类型最多1,048,576 个 Token

在 DefaultEngine.ini 中需要为每种 TokenStore 分配 TypeID

```cpp
[/Script/IrisCore.NetTokenTypeIdConfig]
+ReservedTypeIds=(StoreTypeName="StringTokenStore", TypeID=0)
+ReservedTypeIds=(StoreTypeName="NameTokenStore", TypeID=1)
+ReservedTypeIds=(StoreTypeName="GameplayTagTokenStore", TypeID=2)
+ReservedTypeIds=(StoreTypeName="FModuleInputNetTokenData", TypeID=3)
+ReservedTypeIds=(StoreTypeName="FNetworkModularVehicleStateNetTokenData", TypeID=4)
```

# Token映射机制

---

> 💡
>
> FNetToken包含TypeId+TypeIndex：TypeId是Token类型、TypeIndex是类型内部自增计数
>
> **FNetTokenStoreKey**(KeyIndex)是数组下标
>
> **通过FNetTokenStoreKey串联起原始数据和 FNetToken**
>
> **原始数据和 FNetToken 分别存放在一个数组里，同一对数据在两个数组的下标一致**
>
> // 发送端：原始数据 → Token
> 原始数据  → StoreKey → NetToken
>
> // 接收端：Token → 原始数据
> NetToken → StoreKey → 原始数据

> 💡
>
> **FNetTokenStoreKey**内部维护的KeyIndex对于本地创建的Token，跟Token的TypeIndex是一致的，为什么需要单独维护一个FNetTokenStoreKey来充当中间映射呢?
>
> 但有一种情况是不一致的，当客户端把本地创建的Token发给DS时，DS会在DS端生成一个Token，并把这个Token分发下来，覆盖客户端本地之前创建的Token(保持Token的网络唯一标识)。此时Token的TypeIndex跟客户端本地维护的FNetTokenStoreKey内部的KeyIndex时大概率不一致的。
>
> 所以这个独立的中间转换FNetTokenStoreKey是有存在必要的

> [!note]- **FNetTokenDataStore**
> ```cpp
> class FNetTokenDataStore
> {
>     //Token数组
>     TArray<FNetToken> StoredTokens;
> }
> ```
>
> **FNetTokenDataStore** 是存放每种类型Tokens数据的基类，不同类型实现对应的子类，在子类中实现原始数据与Token的映射关系建立
>
> ![image.png](http://pic.xyyxr.cn/20260504161044001.png)

> [!note]- **FNetTokenStore**
> ```cpp
> class FNetTokenStore
> {
>     //本地生成的所有类型的FNetTokenStoreKey 信息
>     //二维数组存放FNetTokenStoreKey 方便将Token快速转换为FNetTokenStoreKey
>     //通过FNetTokenStoreKey 可以访问原始信息
>     TUniquePtr<FNetTokenStoreState> LocalNetTokenStoreState;
>
>     //每个连接远程生成的所有类型的FNetTokenStoreKey 信息
>     //二维数组存放FNetTokenStoreKey 方便将Token快速转换为FNetTokenStoreKey
>     //通过FNetTokenStoreKey 可以访问原始信息
>     TArray<TUniquePtr<FNetTokenStoreState>> RemoteNetTokenStoreStates;
>
>     //所有类型Token的数据(FNetTokenDataStore指针数组)
>     TArray<TTuple<FName, TUniquePtr<FNetTokenDataStore>>> TokenDataStores;
> }
>
> class FNetTokenStoreState
> {
> //二维数组 存放所有类型的以生成的Token数组索引信息
> TArray<FNetTokenDataStore::FNetTokenStoreKey> 
> TokenInfoArray[FNetToken::MaxTypeIdCount];
> }
> ```
>
> **FNetTokenStore**是记录所有类型的Token的生成状态信息(**StoreState**)，包括本地端生成了哪些，每个连接的远程端生成了哪些，全局只存在一个实例。
>
> FNetTokenStoreState 是一个二维数组，能通过Token的TypeId+TypeIndex快速访问到对应的FNetTokenStoreKey数据。(TypeId一维下标，TypeIndex二维下标)
>
> 拿到FNetTokenStoreKey后就可以获取对应的原始数据
>
>
> > 💡
> >
> > 以 FName 为例讲解

## 原始数据转Token

---

```cpp
FNetToken FNameTokenStore::GetOrCreateToken(FName Name)
{
	//先查找或者创建中间映射FNetTokenStoreKey(原始数据转FNetTokenStoreKey)
	FNetTokenStoreKey Key = GetOrCreateTokenStoreKey(Name);
	
	//FNetTokenStoreKey转Token
	if (Key.IsValid())
	{
		//Token存在直接返回
		const FNetToken ExistingToken = GetNetTokenFromKey(Key);
		if (ExistingToken.IsValid())
		{
			return ExistingToken;
		}
		else
		{
			//不存在则新建Token
			const FNetToken NewToken = CreateAndStoreTokenForKey(Key);
			return NewToken;
		}
	}

	return FNetToken();
}
```

## Token转原始数据

---

```cpp
FName FNameTokenStore::ResolveToken(...) const
{
	const FNetTokenStoreState* TokenStoreState = TokenStore.IsLocalToken(Token) ? 
	TokenStore.GetLocalNetTokenStoreState() : NetTokenStoreState;
	
	if (Token.IsValid() && TokenStoreState )
	{
		//Token转FNetTokenStoreState
		const FNetTokenStoreKey StoreKey = GetTokenKey(Token, *TokenStoreState);
		
		//FNetTokenStoreState转原始数据
		if (StoreKey.IsValid() && StoreKey.GetKeyIndex() < (uint32)StoredFNames.Num())
		{
			return StoredFNames[StoreKey.GetKeyIndex()];
		}
	}

	return FName();
}
```

## 原始数据 & FNetTokenStoreKey 双向映射

---

```cpp
FNetTokenStoreKey FNameTokenStore::GetOrCreateTokenStoreKey(FName Name)
{
    // 1. 查找是否已存在(通过原始数据查找FNetTokenStoreKey)
    if (const FNetTokenStoreKey* ExistingKey = FNameToKey.Find(Name))
    {
        return *ExistingKey;
    }
    
    // 2. 创建新的 StoreKey
    const FNetTokenStoreKey NewKey = GetNextNetTokenStoreKey();
    
    // 3. 建立双向映射(FNetTokenStoreKey和原始数据的双向映射)
    FNameToKey.Add(Name, NewKey);      // FName → Key
    StoredFNames.Add(Name);            // Key → FName
    
    return NewKey;
}

```

> [!note]- **通过原始数据查找FNetTokenStoreKey**
> ```cpp
> FNetTokenStoreKey FNameTokenStore::GetOrCreateTokenStoreKey(FName Name)
> {
>     // 通过原始数据查找FNetTokenStoreKey
>     if (const FNetTokenStoreKey* ExistingKey = FNameToKey.Find(Name))
>     {
>         return *ExistingKey;
>     }
>     //没有就创建一个
>     const FNetTokenStoreKey NewKey = GetNextNetTokenStoreKey();
>  }
> ```


> [!note]- **通过FNetTokenStoreKey 查找原始数据**
> ```cpp
> if (StoreKey.IsValid() && StoreKey.GetKeyIndex() < (uint32)StoredFNames.Num())
> {
>     return StoredFNames[StoreKey.GetKeyIndex()];
> }
> ```


## FNetTokenStoreKey & FNetToken 双向映射

---

```cpp
//创建FNetTokenStoreKey和FNetToken的双向映射
FNetToken FNetTokenDataStore::CreateAndStoreTokenForKey(FNetTokenStoreKey Key)
{
    FNetTokenStoreState& LocalState = *TokenStore.GetLocalNetTokenStoreState();
    
    // 1. 分配新的 Token 索引
    const uint32 NextTokenIndex = LocalState.TokenInfoArray[GetTypeId()].Num();
    
    // 2. 创建 NetToken（包含 TypeId、Index、Authority 标志）
    FNetToken NewToken = FNetTokenStore::MakeNetToken(
        TypeId, 
        NextTokenIndex, 
        TokenStore.IsAuthority() ? Authority : None
    );
    
    // 3. 建立映射：FNetToken→ StoreKey
    LocalState.TokenInfoArray[GetTypeId()].Add(Key);
    
    // 4. 建立映射：StoreKey → FNetToken
    StoredTokens[Key.GetKeyIndex()] = NewToken;
    
    return NewToken;
}

```

> [!note]- **通过FNetTokenStoreKey 查找 Token**
> ```cpp
> //通过FNetTokenStoreKey 查找 Token
> FNetToken FNetTokenDataStore::GetNetTokenFromKey(FNetTokenStoreKey Key) const
> {
>     return StoredTokens[Key.GetKeyIndex()];
> }
> ```


> [!note]- **通过Token 查找FNetTokenStoreKey**
> ```cpp
> FNetTokenDataStore::FNetTokenStoreKey FNetTokenDataStore::GetTokenKey(..) const
> {
>     if (Token.GetTypeId() == GetTypeId())
>     {
>         //访问二维数组TokenInfoArray
>         const TArray<FNetTokenStoreKey>& TokenStoreKeysForType = 
>         TokenStoreState.TokenInfoArray[GetTypeId()];
>
>         const int32 TokenIndex(Token.GetIndex());
>
>         return TokenIndex < TokenStoreKeysForType.Num() ? 
>         TokenStoreKeysForType[TokenIndex] : FNetTokenStoreKey();
>     }
>
> }
> ```


# 双端数据同步

---

![image.png](http://pic.xyyxr.cn/20260504161044002.png)

> 💡
>
> Iris每个网络连接的同步通道DataStreamChannel定义了两个数据流。
>
> NetTokenDataStream 专门处理NetToken数据的
> ReplicationDataStream 通用的数据同步数据流
>
> NetTokenDataStream 比 ReplicationDataStream 先处理

```cpp
[/Script/IrisCore.DataStreamDefinitions]
+DataStreamDefinitions=(DataStreamName=NetToken, ClassName=/Script/IrisCore.NetTokenDataStream, DefaultSendStatus=EDataStreamSendStatus::Send, bAutoCreate=true)

+DataStreamDefinitions=(DataStreamName=Replication, ClassName=/Script/IrisCore.ReplicationDataStream, DefaultSendStatus=EDataStreamSendStatus::Send, bAutoCreate=true)
```

NetToken首次发送需要附带的完整信息是通过UNetTokenDataStream数据流处理

> 💡
>
> 也就是对于正常流程的网络同步数据UReplicationDataStream数据流中的数据，不管首次还是再次发送，都仅需发送Token本身(也就是在ReplicationDataStream数据流角度来说，FName总是以Token的形式传输)。
>
> 至于是否发送包括原始数据完整的数据则交给UNetTokenDataStream去处理，通用的数据同步流程不需要关注。
>
> 因为UNetTokenDataStream中的数据比UReplicationDataStream中的数据更早的处理，所以当处理UReplicationDataStream中同步下来的Token时，接收端的Token映射已经建立好了。

## 同步流程

---

![image.png](http://pic.xyyxr.cn/20260504161046196.png)

> 💡
>
> 以FName为例

> [!note]- **FName的量化&序列化(**ReplicationDataStream**)**
> ```cpp
> void FNameAsNetTokenNetSerializer::Quantize(...)
> {
>     if (bIsString)
>     {
> ...
>         TargetName.NetToken = NameTokenStore->GetOrCreateToken(SourceName);
> ...
>     }
> }
>
> void FNameAsNetTokenNetSerializer::Serialize(...)
> {
> ...
>     if (Writer->WriteBool(Value.bIsString))
>     {
>         // 这里仅写入Token本身
>         Context.GetNetTokenStore()->WriteNetTokenWithKnownType<FNameTokenStore>(...);
>
>         // 然后通知NetTokenDataStream我要发送一个Token
>         // 是否需要把Token对应的原始数据带上你自己判定下
>         FNetTokenStore::AppendExport(Context, Value.NetToken);
>     }
> ...
> }
> ```

> [!note]- **FName的反序列化&反量化(**ReplicationDataStream**)**
> ```cpp
> void FNameAsNetTokenNetSerializer::Deserialize(...)
> {
> ...
>     if (const bool bIsString = Reader->ReadBool())
>     {
>         Target.bIsString = 1;
>
>         // 这里仅读取Token数据(不带原始数据的)
>         FNetToken NetToken = Context.GetNetTokenStore()->
>         ReadNetTokenWithKnownType<FNameTokenStore>(Context);
>
>         if (Reader->IsOverflown())
>         {
>             return;
>         }
>
>         Target.NetToken = NetToken;
>     }
> ...
> }
>
> void FNameAsNetTokenNetSerializer::Dequantize(...)
> {
> ...
> if (Source.bIsString)
>     {
>         //直接通过Token获取对应的原始数据(映射关系会在UNetTokenDataStream提前处理好)
>         Target = FNameAsNetTokenNetSerializer::ResolveNetToken(Context, Source.NetToken);
>     }
> ...
> }
> ```


> [!note]- **写入本次发送需要完整数据(**NetTokenDataStream)
> ```cpp
> UDataStream::EWriteResult UNetTokenDataStream::WriteData(...)
> {
>         //只有未导出的(如果是客户端 则对于DS分配的Token都不需要导出)
>         if (!(Token.IsAssignedByAuthority() && !bIsNetTokenAuthority) && 
>         !ExportContext->IsExported(Token))
>         {
>         ...
>             //写入Token的完整数据
>             SubStream.WriteBool(true);
>             NetTokenStore->WriteNetToken(SubContext, Token);
>             NetTokenStore->WriteTokenData(SubContext, Token);
>
>             if (SubStream.IsOverflown())
>             {
>                 break;
>             }
>             else
>             {
>                 //标记已经导出的Token
>                 ExportContext->AddExported(Token);
>
>                 //这里缓存先 丢包重发用
>                 NetTokenExports.Add(Token);
>                 ++WrittenCount;
>             }
>         ...
>         }
>
>
>     if (WrittenCount)
>     {
>         ...
>     }
>     else
>     {
>         //没有要写入的数据
>         Writer->DiscardSubstream(SubStream);
>         return EWriteResult::NoData;
>     }
> }
> ```


> [!note]- **读取首次发送给接收端的完整数据**，**提前建立Token映射(**NetTokenDataStream)
> ```cpp
> void UNetTokenDataStream::ReadData(UE::Net::FNetSerializationContext& Context)
> {
> ...
> ...
> }
>
> bool FNetTokenStore::ValidateAndStoreNetTokenData(...)
> {
> ...
>     if (NetToken.IsAssignedByAuthority() && !IsAuthority())
>     {
>         //客户端将本地之前预先创建的Token换成DS分配的Token
>         //不管是本地之前预先创建的还是本次新建的 直接覆盖
>         DataStore.StoredTokens[StoreKey.GetKeyIndex()] = NetToken;
>     }
>
>     //RemoteNetTokenStoreState 记录来自远端创建的Token
>     TokenStoreKeysForType[NetToken.GetIndex()] = StoreKey;
> ...
> }
> ```
>
> > 💡
> >
> >     当客户端把本地创建的Token发给DS时，DS会在DS端生成一个Token，并把这个Token分发下来，覆盖客户端本地之前创建的本地Token(为保持网络唯一标识)。此时Token的TypeIndex跟客户端本地维护的FNetTokenStoreKey内部的KeyIndex时大概率不一致的。
> >
> >     （这就是中间映射FNetTokenStoreKey存在的意义）