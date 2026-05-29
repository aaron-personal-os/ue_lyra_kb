> 💡 **本系列文章基于UE5.3**

# 概述

---

Tag是支持网络复制，因为Tag本质上就是一个FName，而FName网络复制需要转换成FString，相对来说开销比较大。UE提供了另一种快速复制的方式：**复制Tag的索引**。

Tag的网络复制配置可以在**项目设置(ProjectSetting)的GameplayTags页面进行配置。**

![Untitled](http://pic.xyyxr.cn/20260504111212565.png)

- **快速复制(FastReplication):** 
开启了该选项后Tag的网络复制直接复制Tag的索引而不是Tag的名称
    
    
- **常见复制标签(CommonlyReplicatedTags)**:
可以配置一些会频繁进行网络复制的Tag到列表。配置在该列表中的Tag在构造网络复制索引时会调整到数组的最前面，这样被分配的索引数值就比较小，复制占据的数据量就会小点，效率相对来说也会高点(参照下面**网络索引首位段**的说明)
- **容器大小的位数(NumBitsForContainerSize)：**
复制Tag容器时，容器大小占用的bit位。默认6位表示复制的Tag容器最大支持放63个Tag。
> [!note]- **网络索引首位段(NetIndexFirstBitSegment)**:
> Tag网络复制的索引值是uint16(16个bit位)，也就是最大支持65535个Tag配置。支持在复制Tag索引拆分成两个bit段进行序列化和反序列化。这里可以配置第一个bit段(**首位段**)占用多少个bit位，默认配置16位，就是不做拆分(最大也就支持到16位)
>
> > 💡 配置**首位段**(复制Tag索引是拆分成两个bit段)的意义:
> >     **复制比较小的索引时，可以占用更少的bit位**
> >
> >     在复制Tag索引时，序列化占用多个bit位取决于最大索引值和**首位段**最大占用bit位。比如最大索引值是1024，转换成bit就需要占用11位，如果不做拆分(配置的**首位段**占用位数≤0 或者配成默认的16)，那不管复制多大的索引都需要占用11个bit位。
> >
> >     如果需要频繁复制Tag索引只是其中一小部分，比如不到64个，则可以考虑拆分成两个bit段，将**首位段**设置占用6位就够，并将频繁复制的Tag添加到**常见复制标签**列表，这样这些频繁复制的Tag就会分配一个较小的索引编号，复制这些Tag是占用的bit位也就更少了。
> >
> >     在序列化第一bit段时会多占用一个bit位，标记是否拆分成两个bit段。不管拆不拆分两个bit位都会占用。
> >
> >     如果复制的索引值超过**首位段**设置的bit位，会自动拆分成两个bit段进行序列化操作，两个bit段总共占用的bit位是最大索引号需要占用bit位+1(多了一个bit位用来标记是否拆分两个bit段了)


# Tag复制索引构建

---

GameplayTagsManager的**ConstructNetIndex**函数负责构建Tag的网络复制索引。具体操作是将GameplayTagsManager中存放所有Tag信息的Map:**GameplayTagNodeMap**转换成数组**NetworkGameplayTagNodeIndex**。索引指的就是Tag在数组**NetworkGameplayTagNodeIndex**中的索引。所以如果要使用Tag的快速复制，**需要保证两端的Tag配置是一致的**(可以通过构建网络复制索引时生成的Hash值**NetworkGameplayTagNodeIndexHash**进行验证)。

```cpp
class UGameplayTagsManager : public UObject
{
...
TMap<FGameplayTag, TSharedPtr<FGameplayTagNode>> GameplayTagNodeMap;

TArray<TSharedPtr<FGameplayTagNode>> NetworkGameplayTagNodeIndex;
...
}
```

> 💡 *关于一致性的校验，提供个简单的思路。可以通过GM指令或者其他方式触发一个RPC，把客户端的Hash值NetworkGameplayTagNodeIndexHash发送给服务器，跟服务器的Hash值NetworkGameplayTagNodeIndexHash进行匹配校验*

```cpp
void UGameplayTagsManager::ConstructNetIndex()
{
...
//**GameplayTagNodeMap**转换成数组**NetworkGameplayTagNodeIndex**
GameplayTagNodeMap.GenerateValueArray(**NetworkGameplayTagNodeIndex**);

//**将配置常见复制标签(CommonlyReplicatedTags)列表的Tag调整到数组的前面
//为其分配一个比较小的索引**
for (int32 CommonIdx=0; CommonIdx < **CommonlyReplicatedTags**.Num(); ++CommonIdx)
{
		int32 BaseIdx=0;
		FGameplayTag& Tag = CommonlyReplicatedTags[CommonIdx];
	
		bool Found = false;
		for (int32 findidx=0; findidx < NetworkGameplayTagNodeIndex.Num(); ++findidx)
		{
			if (NetworkGameplayTagNodeIndex[findidx]->GetCompleteTag() == Tag)
			{
				NetworkGameplayTagNodeIndex.Swap(findidx, CommonIdx);
				Found = true;
				break;
			}
		}
}

/**/根据最大索引值 计算出Tag索引最大占用的bit位**
InvalidTagNetIndex = 
IntCastChecked<uint16, int32>(NetworkGameplayTagNodeIndex.Num() + 1);

**NetIndexTrueBitNum** = 
FMath::CeilToInt(FMath::Log2(static_cast<float>(InvalidTagNetIndex)));

**//配置的首位段最大占用的bit位**
**NetIndexFirstBitSegment** = FMath::Min<int32>(
GetDefault<UGameplayTagsSettings>()->NetIndexFirstBitSegment, NetIndexTrueBitNum);

**//将网络复制索引值分配给每个Tag节点**
for (FGameplayTagNetIndex i = 0; i < NetworkGameplayTagNodeIndex.Num(); i++)
{
	if (NetworkGameplayTagNodeIndex[i].IsValid())
	{
		NetworkGameplayTagNodeIndex[i]->NetIndex = i;

	 **//计算哈希值**
		NetworkGameplayTagNodeIndexHash = 
		FCrc::StrCrc32(*NetworkGameplayTagNodeIndex[i]->GetCompleteTagString().ToLower(),
		 NetworkGameplayTagNodeIndexHash);
	}

}
...
}
```

# Tag索引序列化

---

**NetSerialize_Packed**是统一处理Tag索引网络复制的接口。如果开启了快速复制(**FastReplication**),这序列化的是给Tag分配的复制索引(**uint16**)，如果不开启快速复制，则复制时直接复制FName，会转换成FString进行复制，网络开销相对来说比较大。

而且为了尽可能的节省频繁复制Tag时的网络开销**(流量和数据处理速度**)，复制uint16的Tag索引时还会尽可能的减少序列化时占用的bit位。**SerializeTagNetIndexPacked**就是将一个uint16的Tag索引压缩bit位的处理接口

```cpp
bool FGameplayTag::NetSerialize_Packed(...)
{
	if (TagManager.ShouldUseFastReplication())
	{
		if (bIsReplay)
		{
			...
			//这里是本地重放逻辑的复制  不需要考虑网络流量直接复制就行了 略过
			uint32 NetIndex32 = NetIndex;
			Ar.SerializeIntPacked(NetIndex32);
			....
			return true;
		
		}
		
		
		if (Ar.IsSaving())
		{
		  //序列化
			**NetIndex = TagManager.GetNetIndexFromTag(*this);**
			
			**SerializeTagNetIndexPacked**(Ar, 
			NetIndex, 
			TagManager.GetNetIndexFirstBitSegment(), 
			TagManager.GetNetIndexTrueBitNum());
		}
		else
		{
		 //反序列化
			**SerializeTagNetIndexPacked**(Ar,
			 NetIndex, 
			 TagManager.GetNetIndexFirstBitSegment(), 
			 TagManager.GetNetIndexTrueBitNum());
			 
			**TagName = TagManager.GetTagNameFromNetIndex(NetIndex);**
		}
	}
	else
	{
		Ar << TagName;
	}
}

```

**SerializeTagNetIndexPacked**将**uint16的Tag索引按bit位进行序列化**。在上一步**ConstructNetIndex**构建Tag索引时，已经计算出最大的索引值占用多少个bit位**MaxBits**(比如最大索引值是1024，那就Tag索引最大bit位就占用11位，不用16位了)。

还可以进一步压缩，如果频繁复制的Tag数量并不多，可以考虑给这些频繁复制的Tag的索引分配一些较小的索引值(参照上一步**ConstructNetIndex**)。也就是说经常被复制的索引值可能比较小，大部分情况下都用不到最大索引值的11位。那就可以考虑**网络索引首位段(NetIndexFirstBitSegment)**的设置。

思路就是将序列化的bit位拆分成两段，第一段(首位段)可以分配一个较小的bit位数量。比如经常复制的不超过64个,那首位段分配6位就可以了。也就是绝大多数复制Tag索引时，用6位就可以了(实际是7位还需要有额外的一位标记是否被拆分成两段了)。索引值≥64的将会启用第二段bit位段。

**网络索引首位段(NetIndexFirstBitSegment)**的设置序列化时需要额外占用一个bit位段进行标记是否有第二段bit位段。但总体而言还是能节省一部分网络开销(上面例子能节省30%左右)。

```cpp
void SerializeTagNetIndexPacked(...)
{
	//MaxBits就是最大索引值占用的bit位 1024占11位
	//**NetIndexFirstBitSegment** <=0或者比MaxBits 还大时 统一占用MaxBits位
	if (NetIndexFirstBitSegment <= 0 || NetIndexFirstBitSegment >= MaxBits)
	{
		if (Ar.IsLoading())
		{
			Value = 0;
		}
		Ar.SerializeBits(&Value, MaxBits);
		return;
	}
	
	const uint32 BitMasks[] = 
	{0x00, 0x01, 0x03, 0x07, 
	 0x0f, 0x1f, 0x3f, 0x7f, 
	 0xff, 0x1ff, 0x3ff, 0x7ff, 
	 0xfff, 0x1fff, 0x3fff, 0x7fff, 0xffff};
	 
	const uint32 MoreBits[] = 
	{0x00, 0x01, 0x02, 0x04, 
	0x08, 0x10, 0x20, 0x40, 
	0x80, 0x100, 0x200, 0x400, 
	0x800, 0x1000, 0x2000, 0x4000, 0x8000};
	
	//第一个bit段(**首位段**) 占用的bit位
	const int32 FirstSegment = NetIndexFirstBitSegment;
	
	//第二个bit段占用的bit位(剩下的全部)
	const int32 SecondSegment = MaxBits - NetIndexFirstBitSegment;
	
	
	if (Ar.IsSaving())
	{
		**//序列化**
		uint32 Mask = BitMasks[FirstSegment];
		if (Value > Mask)
		{
			**//索引值 超过了第一个bit段(首位段)容纳的大小 放不下的 拆分到第二bit段**
			uint32 FirstDataSegment = ((Value & Mask) | MoreBits[FirstSegment+1]);
			uint32 SecondDataSegment = (Value >> FirstSegment);

			uint32 SerializedValue = 
			FirstDataSegment | (SecondDataSegment << (FirstSegment+1));				

			Ar.SerializeBits(&SerializedValue, MaxBits + 1);
		}
		else
		{
			//**索引值 没超过了第一个bit段(首位段)容纳的大小 
			//只占NetIndexFirstBitSegment + 1个bit位**
			uint32 SerializedValue = Value;
			Ar.SerializeBits(&SerializedValue, NetIndexFirstBitSegment + 1);
		}

	}
	else
	{
	
		**//反序列化**
		uint32 FirstData = 0;
		Ar.SerializeBits(&FirstData, FirstSegment + 1);
		uint32 More = FirstData & MoreBits[FirstSegment+1];
		if (More)
		{
		 //如果拆分成两段了 则需要继续读取下一段
			uint32 SecondData = 0;
			Ar.SerializeBits(&SecondData, SecondSegment);
			Value = IntCastChecked<uint16, uint32>(SecondData << FirstSegment);
			Value |= (FirstData & BitMasks[FirstSegment]);
		}
		else
		{
			Value = IntCastChecked<uint16, uint32>(FirstData);
		}
	...
	}
	...
}
```

# Tag复制

---

Tag的复制分为两种方式，**复制单个Tag**和**复制整体Tag容器(FGameplayTagContainer)**

## 复制单个Tag

---

**NetSerialize_Packed** 进行Tag的序列化和反序列化，如果开启了快速复制，则就是序列化Tag的网络索引，反序列化时再根据索引查找的TagName。如果没有开启开始复制，则直接复制TagName(会转换成字符串FString)

```cpp

bool FGameplayTag::NetSerialize(...)
{
#if !(UE_BUILD_SHIPPING || UE_BUILD_TEST)
	if (Ar.IsSaving())
	{
		UGameplayTagsManager::Get().NotifyTagReplicated(*this, false);
	}
#endif

	NetSerialize_Packed(Ar, Map, bOutSuccess);

	bOutSuccess = true;
	return true;
}

```

## 复制Tag容器

---

复制Tag容器(**FGameplayTagContainer**)就是将容器里Tag(不需要复制ParentTags)依次序列化，同时还需要容器的大小复制。

反序列化时，根据复制的容器大小现创建好空容器，再依次反序列化Tag填充到容器中。用了Tag信息就可以查找到Tag节点(**FGameplayTagNode**)信息，填充ParentTags。这样Tag容器就被还原了。

```cpp
//
bool FGameplayTagContainer::NetSerialize(...)
{
...
const int32 NumBitsForContainerSize = UGameplayTagsManager::Get().NumBitsForContainerSize;

	if (Ar.IsSaving())
	{
		uint8 NumTags = IntCastChecked<uint8, int32>(GameplayTags.Num());
		uint8 MaxSize = (1 << NumBitsForContainerSize) - 1;
	 ...
		NumTags = MaxSize;
	 ...
		
		Ar.SerializeBits(&NumTags, NumBitsForContainerSize);
		for (int32 idx=0; idx < NumTags;++idx)
		{
			FGameplayTag& Tag = GameplayTags[idx];
			Tag.NetSerialize_Packed(Ar, Map, bOutSuccess);

#if !(UE_BUILD_SHIPPING || UE_BUILD_TEST)
			UGameplayTagsManager::Get().NotifyTagReplicated(Tag, true);
#endif
		}
	}
	else
	{
		// No Common Container tags, just replicate this like normal
		uint8 NumTags = 0;
		Ar.SerializeBits(&NumTags, NumBitsForContainerSize);

		GameplayTags.Empty(NumTags);
		GameplayTags.AddDefaulted(NumTags);
		for (uint8 idx = 0; idx < NumTags; ++idx)
		{
			GameplayTags[idx].NetSerialize_Packed(Ar, Map, bOutSuccess);
		}
		FillParentTags();
	}
}
...
```

```cpp
FORCEINLINE_DEBUGGABLE void FGameplayTagContainer::AddParentsForTag(...)
{
	const FGameplayTagContainer* SingleContainer = 
	UGameplayTagsManager::Get().GetSingleTagContainer(Tag);
	
	if (SingleContainer)
	{
		// Add Parent tags from this tag to our own
		for (const FGameplayTag& ParentTag : SingleContainer->ParentTags)
		{
			ParentTags.AddUnique(ParentTag);
		}
	}
}
```

# 查看Tag复制频率的指令

---

启动游戏，运行一段时间后在控制台输入指令***GameplayTags.PrintReport**或者GameplayTags.PrintReplicationFrequencyReport*会打印运行期间内哪些Tag被复制。

还可以输入指令***GameplayTags.PrintReportOnShutdown 1**，*会在游戏关闭时打印运行期间被复制的Tag信息。

> 💡 复制操作是发生的DS端的，所以这些指令都需要在DS段执行，日志也是打印在DS的日志里的
>
> 也可以根据项目需求在，需要的地方(比如对局房间关闭的时候)手动调用**UGameplayTagsManager::Get().PrintReplicationFrequencyReport();**

```cpp
FAutoConsoleCommand GameplayTagPrintReplicationMapCmd(
	TEXT("GameplayTags.PrintReport"), 
	TEXT( "Prints frequency of gameplay tags" ), 
	FConsoleCommandDelegate::CreateStatic(GameplayTagPrintReplicationMap)
);

#if !(UE_BUILD_SHIPPING || UE_BUILD_TEST)

static FAutoConsoleCommand PrintReplicationFrequencyReportCommand(
	TEXT("GameplayTags.PrintReplicationFrequencyReport"),
	TEXT("Prints the frequency each tag is replicated."),
	FConsoleCommandDelegate::CreateLambda([]()
	{
		UGameplayTagsManager::Get().PrintReplicationFrequencyReport();
	})
);

#endif

static void GameplayTagPrintReplicationMap()
{
	UGameplayTagsManager::Get().PrintReplicationFrequencyReport();
}
```

```cpp
#if !(UE_BUILD_SHIPPING || UE_BUILD_TEST)
int32 GameplayTagPrintReportOnShutdown = 0;
static FAutoConsoleVariableRef CVarGameplayTagPrintReportOnShutdown
(TEXT("GameplayTags.PrintReportOnShutdown"), 
GameplayTagPrintReportOnShutdown, 
TEXT("Print gameplay tag replication report on shutdown"), ECVF_Default );
#endif

void FGameplayTagsModule::ShutdownModule()
{
#if !(UE_BUILD_SHIPPING || UE_BUILD_TEST)
	if (GameplayTagPrintReportOnShutdown)
	{
		UGameplayTagsManager::Get().PrintReplicationFrequencyReport();
	}
#endif

	UGameplayTagsManager::SingletonManager = nullptr;
}
```

在复制单个Tag和Tag容器(FGameplayTagContainer)时，会调用NotifyTagReplicated通知GameplayTagsManager哪些Tag正在被复制了。然后就可以统计哪些Tag被复制了,被复制了多少次，是单个复制，还是通过Tag容器复制。**PrintReplicationFrequencyReport**就可以打印出这些信息，并按复制次数进行排序。**最后还会根据统计结果计算出首位段的最大占用Bit位配成多少可以节省最多， 并以此打印出哪些Tag建议配进常见复制标签(CommonlyReplicatedTags)列表，首位段最大Bit建议配成多大。**

```cpp
//复制单个Tag
bool FGameplayTag::NetSerialize(...)
{
#if !(UE_BUILD_SHIPPING || UE_BUILD_TEST)
	if (Ar.IsSaving())
	{
		UGameplayTagsManager::Get().NotifyTagReplicated(*this, false);
	}
#endif

	NetSerialize_Packed(Ar, Map, bOutSuccess);

	bOutSuccess = true;
	return true;
}

//复制Tag容器
bool FGameplayTagContainer::NetSerialize(...)
{
...
if (Ar.IsSaving())
	{
#if !(UE_BUILD_SHIPPING || UE_BUILD_TEST)
			UGameplayTagsManager::Get().NotifyTagReplicated(Tag, true);
#endif
		}
	}
...
}
```

```cpp
void UGameplayTagsManager::NotifyTagReplicated(FGameplayTag Tag, bool WasInContainer)
{
	ReplicationCountMap.FindOrAdd(Tag)++;

	if (WasInContainer)
	{
		ReplicationCountMap_Containers.FindOrAdd(Tag)++;
	}
	else
	{
		ReplicationCountMap_SingleTags.FindOrAdd(Tag)++;
	}
}
	
```