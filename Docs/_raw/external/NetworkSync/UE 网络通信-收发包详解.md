[《Exploring in UE4》关于网络同步的理解与思考[概念理解]](https://zhuanlan.zhihu.com/p/34721113)

[《Exploring in UE4》网络同步原理深入（上）[原理分析]](https://zhuanlan.zhihu.com/p/34723199)

[《Exploring in UE4》网络同步原理深入（下）[原理分析]](https://zhuanlan.zhihu.com/p/55596030)

[UE4属性同步（一）服务器同步属性](https://zhuanlan.zhihu.com/p/412517987)

[UE4网络同步思考（二）---大世界同步方案ReplicationGraph](https://zhuanlan.zhihu.com/p/56922476)

> 💡 **本系列文章基于UE5.3**

# 网络数据包组成

---

如下图所示，网络数据包Packet分为包头数据(PacketHead)和包体数据(PacketData)两部分。包头数据主要包含了本次发送的消息包的序列号和Ack数据，包体部分主要是Bunch数据。

Ack用于UDP传输时应答数据包(用于校验是否丢包了)，能让通信双方知道发给彼此的消息包哪些被接收了哪些被丢包

Bunch里面主要记录了Channel信息(比如ActorChannel主要是属性复制和RPC)。同时包含其他的附属信息如是否是完整的Bunch，是否是可靠等。

> 💡
>
> 一个Packet可能只有包头数据而包体数据部分为空

![image.png](http://pic.xyyxr.cn/20260504161056191.png)

每帧处理接收到的消息包时，会统计本次收包情况(哪些包收到了，哪些包丢包了)，在填充本帧发送的网络数据包时会将该信息写入包头数据中， 每次属性复制和RPC都是序列化成Bunch数据包写入包体数据中。

- **写入包头信息**
首次填充发送缓存时 先填充包头信息(在最后发包之前 还有一次修改包头信息的机会)
    
```cpp
    void UNetConnection::PrepareWriteBitsToSendBuffer(...)
    {
    		//首次填充发送缓存时 先填充包头信息
    		if (SendBuffer.GetNumBits() == 0 && !IsInternalAck() )
    		{
    			WritePacketHeader(SendBuffer);
    		}
    }
    
    void UNetConnection::FlushNet(bool bIgnoreSimulation)
    {
    		//在最后发包之前 还有一次修改包头信息的机会(包头数据大小不会变 只是更新里面的内容)
    		if ( !IsInternalAck() )
    		{
    			WritePacketHeader(SendBuffer);
    			WriteFinalPacketInfo(SendBuffer, PacketSentTimeInS);
    		}
    }
    
```
    
- **写入包体信息(**Bunch**)**
将Bunch数据写人包体数据中
    
```cpp
    int32 UNetConnection::SendRawBunch(...)
    {
    	//将Bunch数据写人包体数据中
    	PrepareWriteBitsToSendBuffer(BunchHeaderBits, BunchBits);
    	Bunch.PacketId = WriteBitsToSendBufferInternal(SendBunchHeader.GetData(), BunchHeaderBits, Bunch.GetData(), BunchBits, EWriteBitsDataType::Bunch);
    
    }
```
    

## Ack

---

因为UE底层通信用的是UDP进行传输。UDP效率高但不保证数据一定能达到，UE实现了一套机制，能让通信双方知道发给彼此的消息包哪些被接收了哪些被丢包。**接收端收到来自发送端的消息包之后，通过消息包包头携带的序列号判定出哪些消息包丢包了，在下个接收端发往发送端的消息包包头信息放入收包确认数据Ack(*acknowledged*)数据，告诉发送端哪些消息包被成功接收，哪些消息包丢失了，如果是可靠通信，在得知丢包后会进行数据包重发**。

> 💡
>
> 通信的双方都会通过ack数据确认发给彼此消息包是否被对方成功接收了(有点类似TCP的三次握手机制)，并且会维护了一个消息包收包情况历史记录， 万一携带收包记录(ack)的消息包也丢了，还能再通过完备的历史记录进行重发。(本质就是通过冗余的重发来解决UDP不可靠性的)

> 💡
>
> UE可靠通信和不可靠通信概念是针对Bunch层面的，ack校验是否丢包是Packet层面的，如果某个Packet丢包，则其携带的可靠Bunch会触发数据重发(放到新的Packet中进行重发)，不可靠Bunch直接就丢弃了。

每个网络连接都会一个**FNetPacketNotify**的实例来管理消息包的是否被正常接收。

```cpp
class UNetConnection : public UPlayer
{
	FNetPacketNotify PacketNotify;
}

class FNetPacketNotify
{
	//记录通过哪个消息包给对方发送了回复消息包接收情况的ack数据
	//如果后续确认这个消息包被成功接收则会通过这个记录标记哪个回复已经被顺利送达到另一端了
	//就是下面的InAckSeqAck
	AckRecordT AckRecord;
	
	//消息包收包情况历史记录 存放了256 Bit位(长度为8的uint32数组)
	//每个Bit位表示一个Ack确认记录(1为收到0为丢包 最新记录放最低位) 会记录最新的256条ack确认记录
	//如下图所示记录表示最近的256条通信都没有丢包
	SequenceHistoryT InSeqHistory;
	//接收到的最新消息包序列号		
	SequenceNumberT InSeq;	
	//已经给对方回复过的最新消息包序列号(不保证这个回复被对方成功接收)
	SequenceNumberT InAckSeq;
	//回复信息已经被对方成功接收的最新消息包序列号
	SequenceNumberT InAckSeqAck;
	
	//发出的最新消息包序列号
	SequenceNumberT OutSeq;				
	//发出并且确认过是否被接收的最新消息包序列号
	SequenceNumberT OutAckSeq;			
}
```

![image.png](http://pic.xyyxr.cn/20260504161058223.png)

比如客户端(C端)收到来自服务端(S端)的一个消息包，C端根据消息包序列号来判定中间是否丢包了(本次序列号跟上传接收的序列号中间如果有缺失的序列号，视为缺失的序列号丢包)，然后将确认记录放入历史记录**InSeqHistory**中，待到本帧最后处理C端发往S端的发包时(发送缓存有数据或者有ack数据要发送都会触发发包)将确认信息写入包头，同时C端会更新记录列表**AckRecord**表明已经通过哪个消息包给S端发送了携带回复接收情况的ack数据的消息包。如果S端收到这个回复消息包，则会根据ack数据来确认是否需要对丢包数据进行重发

> 💡
>
> UNetConnection::ReceivedAck/UChannel::ReceivedNak来处理接收到ack信息

同时S端也会通知C端这个携带Ack数据的消息包收到了，C端再接收到这个信息后，会更新字段**InAckSeqAck**，记录目前确认信息已经被对方成功接收的最新消息包序列号。

> 💡
>
> 通过Ack可以确认发给彼此消息包是否被对方成功接收了

如果出现携带ack数据的消息包丢失的情况，则会通过本次接收的消息包序列号**InSeq**和字段**InAckSeqAck**对比，得出两次通信之间有哪些确认数据对方还没收到的，则会通过历史记录**InSeqHistory**将对应的记录重新发一遍。

> 💡
>
> 比如收到序号为100的消息包，但**InAckSeqAck**值是97，没丢包的情况下InAckSeqAck值应该是是99, 表明携带序号为98，99的ack数据的消息包丢失了，此时会将序列号为98，99，100的收包情况统一再给对方发一次

> 💡
>
> 消息包序列号是一个自增的编号，每一次发送编号+1。

下面以客户端(C端)往服务器(S端)发送一个可靠RPC为例进行详细分析

> [!note]- **C端在网络数据放入网络缓存之前(PrepBunch),会将数据包(Bunch)保存在一个等待回复(Ack)的队列(OutRec)**
> ```cpp
> class UChannel : public UObject
> {
>         GENERATED_BODY()
>         FOutBunch*  OutRec;             //等待确认(Ack)的队列(OutRec)
>  }
>
> FOutBunch* UChannel::PrepBunch(FOutBunch* Bunch, FOutBunch* OutBunch, bool Merge)
> {
> ...
>     if( Bunch->bReliable )
>     {
>         //放入待确认的队列OutRec
>             OutBunch = new FOutBunch(*Bunch);
>             FOutBunch** OutLink = &OutRec;
>             while(*OutLink)
>             {
>                 OutLink=&(*OutLink)->Next;
>             }
>             *OutLink = OutBunch;
>     }
> ...
> }
> ```

> [!note]- **S端在收到C端消息包后，会给C端发送哪些包收到了，哪些包丢了的Ack信息**
> 收到消息包后，根据消息包序列号确认哪些包收到了，哪些包丢包了，并将Ack信息写入包头信息传给发送端
>
> ```cpp
> //收到消息包后 会通知发送端 哪些包收到了 哪些包丢包了 记录ack数据
> void UNetConnection::ReceivedPacket(...)
> {
> ...
>     if( !IsInternalAck() )
>     {
>
>         if ( bSkipAck )
>         {
>             PacketNotify.NakSeq( InPacketId );
>         }
>         else
>         {
>             PacketNotify.AckSeq( InPacketId );
>         }
>         ++HasDirtyAcks;
>     }
> ...
> }
>
> void FNetPacketNotify::AckSeq(SequenceNumberT AckedSeq, bool IsAck)
> {
>     check( AckedSeq == InSeq);
>
>     while (AckedSeq > InAckSeq)
>     {
>         ++InAckSeq;
>
>         //这中间没收到的包 认为丢包了
>         const bool bReportAcked = InAckSeq == AckedSeq ? IsAck : false;
>         InSeqHistory.AddDeliveryStatus(bReportAcked);       
>     }
> }
> ```


将Ack信息写入包头信息传给C端，并更新记录AckRecord，记录通过哪个消息包给对方发送了回复消息包接收情况的ack数据

```cpp
bool FNetPacketNotify::WriteHeader(FBitWriter& Writer, bool bRefresh)
{
	//将Ack信息写入包头信息	传给发送端
	InSeqHistory.Write(Writer, WrittenHistoryWordCount);
}

void UNetConnection::FlushNet(bool bIgnoreSimulation)
{
....
		if (!IsInternalAck())
		{
			PacketNotify.CommitAndIncrementOutSeq();
		}
...
}

//更新记录AckRecord，记录通过哪个消息包给对方发送了回复消息包接收情况的ack数据
void UNetConnection::FlushNet(bool bIgnoreSimulation)
{
....
		if (!IsInternalAck())
		{
			PacketNotify.CommitAndIncrementOutSeq();
		}
...
}

//更新记录AckRecord，记录通过哪个消息包给对方发送了回复消息包接收情况的ack数据
FNetPacketNotify::SequenceNumberT FNetPacketNotify::CommitAndIncrementOutSeq()
{
	AckRecord.Enqueue( {OutSeq, WrittenInAckSeq} );
	WrittenHistoryWordCount = 0u;
	
	return ++OutSeq;
}
```

- **当C端收到Ack数据时，会根据Ack数据决定是否有需要重发的数据包。同时S端也会回复这个携带ack数据的消息包接收到了(参照上一步)**
消息包被正常接收时，从等待回复队列中移除数据包(ReceivedAck)，当数据包未被正常接收时，触发数据包重发(ReceivedNak)
    
    ![image.png](http://pic.xyyxr.cn/20260504161058224.png)
    
```cpp
    void UNetConnection::ReceivedPacket(...)
    {
    ...
       //从包头信息中提取 哪些包接受到了 哪些包丢失了
    		auto HandlePacketNotification = [&Header, &ChannelsToClose, this](...)
    		{
    			// Increase LastNotifiedPacketId, this is a full packet Id
    			++LastNotifiedPacketId;
    			++OutTotalNotifiedPackets;
    			Driver->IncreaseOutTotalNotifiedPackets();
    
    			// Sanity check
    			if (FNetPacketNotify::SequenceNumberT(LastNotifiedPacketId) != AckedSequence)
    			{
    				UE_LOG(LogNet, Warning, TEXT("LastNotifiedPacketId != AckedSequence"));
    
    				Close(ENetCloseResult::AckSequenceMismatch);
    
    				return;
    			}
    
    			if (bDelivered)
    			{
    				ReceivedAck(LastNotifiedPacketId, ChannelsToClose);
    			}
    			else
    			{
    				ReceivedNak(LastNotifiedPacketId);
    			};
    		};
    
    		PacketNotify.Update(Header, HandlePacketNotification);
    ....
    }
    
    //数据包被正常接收 标记已经被接收 从等待列表中移除
    void UNetConnection::ReceivedAck(...)
    {
    
    	auto AckChannelFunc = [this, &OutChannelsToClose](int32 AckedPacketId, uint32 ChannelIndex)
    	{
    		for (FOutBunch* OutBunch = Channel->OutRec; OutBunch; OutBunch = OutBunch->Next)
    			{
    				if (OutBunch->bOpen)
    				{
    					//标记已经被正确接收了
    					if (OutBunch->PacketId == AckedPacketId)
    					{
    						OutBunch->ReceivedAck = 1;
    					}
    			}
    			
    			//从OutRec移除已经标记正确接收的数据包
    			if (Channel->ReceivedAcks(CloseReason))
    			{
    			}
    	}
    }
    
    //当数据包未被正常接收时，触发数据包重发(ReceivedNak)
    void UChannel::ReceivedNak( int32 NakPacketId )
    {
    	for( FOutBunch* Out=OutRec; Out; Out=Out->Next )
    	{
    		if( Out->PacketId==NakPacketId && !Out->ReceivedAck )
    		{
    	...
    				Connection->SendRawBunch( *Out, 0 );
    	...
    		}
    	}
    }
```
    

> [!note]- **当S端收到C端确认收到之前那个携带确认信息的消息包时，会根据列表AckRecord记录会更新字段InAckSeqAck(**回复信息已经被对方成功接收的最新消息包序列号**)**
> ```cpp
> void FNetPacketNotify::ProcessReceivedAcks(...)
> {
> ...
>         InAckSeqAck = UpdateInAckSeqAck(AckCount, NotificationData.AckedSeq);
> ...
> }
>
> FNetPacketNotify::SequenceNumberT FNetPacketNotify::UpdateInAckSeqAck(...)
> {
>     if ((SIZE_T)AckCount <= AckRecord.Count())
>     {
>         if (AckCount > 1)
>         {
>             AckRecord.PopNoCheck(AckCount - 1);
>         }
>
>         FSentAckData AckData = AckRecord.PeekNoCheck();
>         AckRecord.PopNoCheck();
>
>         // verify that we have a matching sequence number
>         if (AckData.OutSeq == AckedSeq)
>         {
>             return AckData.InAckSeq;
>         }
>     }
>
> }
> ```


## Bunch

---

Bunch是RPC和属性复制生成的网络数据包，每一次RPC调用或者属性复制都会生成一个Bunch数据包写入网络发送缓存SendBuffs中

```cpp
class FOutBunch : public FNetBitWriter
{
	//从哪个Channel发出的
	int32					ChIndex;
	//在Channel中的排序(可靠通信的顺序凭证)
	int32					ChSequence;
	//填充到哪个Packet中
	int32					PacketId;
	//是否是可靠通信
	uint8					bReliable:1;
	//是否是拆分的子串(数据包过大会拆分成子串)
	uint8					bPartial:1;
	//是否是拆分子串的初始部分
	uint8					bPartialInitial:1;
	//是否是拆分子串的结尾部分
	uint8					bPartialFinal:1;
}

class FInBunch : public FNetBitReader
{
//字段跟FOutBunch 差不多
}
```

### **可靠通信机制时序**

---

UE可靠通信和不可靠通信概念是针对Bunch数据包层面的(bReliable)，**可靠通信的Bunch数据包会在丢包后进行重发，并且同一个Channel发出的可靠数据包，会根据发出的顺序，在接收端保持同样的顺序执行，能保证执行的时序。**

每个发出的Bunch串都会记录其归属的Channe，可靠Bunch还会记录在Channel中的写入顺序(首次写入，重发不会修改顺序)，以此作为收包时执行时序的凭证

```cpp
FOutBunch* UChannel::PrepBunch(FOutBunch* Bunch, FOutBunch* OutBunch, bool Merge)
{
	if( Bunch->bReliable )
	{
		Bunch->ChSequence = ++Connection->OutReliable[ChIndex];
	}
}
```

在每个连接(Connection)记录了当前连接每个Channel的发出的可靠Bunch的序列OutReliable和接受到的可靠Bunch序列InReliable来保证可靠Bunch的执行顺序。

```cpp
class UNetConnection : public UPlayer
{
	TArray<int32>		OutReliable;
	TArray<int32>		InReliable;
}
```

当收包处理Bunch数据包时，根据携带的ChSequence序号跟当前InReliable记录的序号做对比。如果不匹配表明前置数据包还没成功接收，会先放入队列等待。

等到了期望序列的可靠数据包，开始按执行，先处理当前期望的可靠消息包，如果有等待队列则按顺序依次执行队列的数据包

```cpp
void UChannel::ReceivedRawBunch( FInBunch & Bunch, bool & bOutSkipAck )
{
...
	//根据携带的ChSequence序号跟当前InReliable记录的序号做对比。
	//如果不匹配表明前置数据包还没成功接收，会先放入队列等待,直到预期的可靠消息包到达
	if ( Bunch.bReliable && Bunch.ChSequence != Connection->InReliable[ChIndex] + 1 )
	{
		//按可靠消息包序列号找到对应的位置插入(保证队列按序列号进行排序)
		FInBunch** InPtr;
		for( InPtr=&InRec; *InPtr; InPtr=&(*InPtr)->Next )
		{
			if(Bunch.ChSequence==(*InPtr)->ChSequence )
			{
				// Already queued.
				return;
			}
			else if( Bunch.ChSequence<(*InPtr)->ChSequence )
			{
				// Stick before this one.
				break;
			}
		}
		FInBunch* New = new FInBunch(Bunch);
		New->Next     = *InPtr;
		*InPtr        = New;
		NumInRec++;

		//排队的可靠消息包过多 报错
		if ( NumInRec >= RELIABLE_BUFFER )
		{
			Bunch.SetError();
			return;
		}
		checkSlow(NumInRec<=RELIABLE_BUFFER);
	}
	else
	{
		//等到了期望序列的可靠数据包 开始按执行 
		
		//先处理当前期望的可靠数据包
		bool bDeleted = ReceivedNextBunch( Bunch, bOutSkipAck );
		
		//接着因为前置消息包没到达而处理队列中等待的消息包
		while( InRec )
		{
			//队列中的前置消息包还没到达 则继续等待
			if( InRec->ChSequence!=Connection->InReliable[ChIndex]+1 )
				break;
			FInBunch* Release = InRec;
			InRec = InRec->Next;
			NumInRec--;

			Release->Next = nullptr;
			
			bDeleted = ReceivedNextBunch( *Release, bLocalSkipAck );
	  }
...
}

bool UChannel::ReceivedNextBunch( FInBunch & Bunch, bool & bOutSkipAck )
{
	if ( Bunch.bReliable )
	{
		//保证可靠消息包的执行顺序 接收端记录的可靠消息包序列跟当前接受到可靠消息包序列需要匹配
		check( Bunch.ChSequence == Connection->InReliable[Bunch.ChIndex] + 1 );

		Connection->InReliable[Bunch.ChIndex] = Bunch.ChSequence;
	}
}
```

# 网络发包&收包流程

---

UE的网络同步主要基于 UDP 进行传输，以满足大多数实时网络游戏对速度和低延迟的需求。这种选择使游戏能够在动态和快速变化的环境中保持流畅。UDP 本身不保证数据包顺序和完整性，但 UE 通过多种机制来管理和实现网络同步的可靠性和顺序性。

## **执行顺序**

---

每帧都是先处理收包作为本帧的网络输入信息，然后执行玩法逻辑写入本帧发送网络数据缓存(SendBuff)，最后将本帧发送网络数据缓存发送。

```cpp
void UWorld::Tick( ELevelTick TickType, float DeltaSeconds )
{
		//收包处理 调用UNetDriver::TickDispatch
		BroadcastTickDispatch(DeltaSeconds);
		//收包之后的处理 调用UNetDriver::PostTickDispatch
		BroadcastPostTickDispatch();
		
		//各种玩法Tick(产生本帧需要发送的网络数据)
		....
		
		//发包处理 调用UNetDriver::TickFlush
		BroadcastTickFlush(RealDeltaSeconds);
		//发包之后的处理 调用UNetDriver::PostTickFlush
		BroadcastPostTickFlush(RealDeltaSeconds);
	}

```

## 发包流程

---

UNetDriver::TickFlush中处理每一帧需要发送的网络数据

```cpp
void UNetDriver::TickFlush(float DeltaSeconds)
{
		if (IsServer() && ClientConnections.Num() > 0 && !bSkipServerReplicateActors)
		{
			 //属性复制检测 收集当帧所有需要复制的属性数据
				Updated = ServerReplicateActors(DeltaSeconds);
		}
		
		//驱动客户端连接Tick
		//(在Tick中触发UNetConnection::FlushNet将缓存的网络数据包发送出去)
		for (UNetConnection* Connection : ClientConnections)
		{
			Connection->Tick(DeltaSeconds);
		}
}
```

> [!note]- **属性同步和RPC都是先将需要发送的数据写入待发送的网络数据包缓存(*SendBuffer*)中(*UNetConnection::WriteBitsToSendBufferInternal* )**
> **属性复制数据写入网络数据包缓存**
>
> ```cpp
> int64 UActorChannel::ReplicateActor()
> {
> ...
> //Actor本身的属性复制
> const bool bCanSkipUpdate = ActorReplicator->CanSkipUpdate(RepFlags);
> if (UE::Net::bPushModelValidateSkipUpdate || !bCanSkipUpdate)
> {
>     bWroteSomethingImportant |= ActorReplicator->ReplicateProperties(Bunch, RepFlags);
> }
>
> ...
> //Actor关联的SubObject的属性复制
> bWroteSomethingImportant |= DoSubObjectReplication(Bunch, RepFlags);
>
> ...
> //写入发送数据缓存中
> if (bWroteSomethingImportant)
> {
>     FPacketIdRange PacketRange = SendBunch( &Bunch, 1 );
> }
> }
> ```
>
> ![Untitled](http://pic.xyyxr.cn/20260504161058225.png)


**RPC数据写入网络数据包缓存**

```cpp
void UNetDriver::ProcessRemoteFunction(...)
{
...
  //广播RPC
	if (bIsServerMulticast)
	{
			for (int32 i = 0; i < ClientConnections.Num(); ++i)
			{
				Connection = ClientConnections[i];
				if (Actor->IsNetRelevantFor(...)
				{
					RepLayout->BuildSharedSerializationForRPC(Parameters);
					InternalProcessRemoteFunctionPrivate(...);
				}
			}
			
			return;
	}
	
	//非广播RPC
	Connection = Actor->GetNetConnection();
	if (Connection)
	{
		InternalProcessRemoteFunction(...);
	}
}

void UNetDriver::ProcessRemoteFunctionForChannelPrivate(...)
{
	//复制RPC相关数据(函数及其参数列表)
	TSharedPtr<FRepLayout> RepLayout = GetFunctionRepLayout(Function);
	RepLayout->SendPropertiesForRPC(Function, Ch, TempWriter, Parms);
	
	if (QueueBunch)
	{
		//广播非可靠RPC先放入队列 稍后跟属性复制一起写入发送缓存中
		Ch->QueueRemoteFunctionBunch(TargetObj, Function, Bunch);
	}
	else
	{
		//直接写入 发送缓存中
		Ch->SendBunch(&Bunch, true);
	}
}
```

![Untitled](http://pic.xyyxr.cn/20260504161058226.png)

> 💡
>
> 非可靠的广播RPC会通过UActorChannel::QueueRemoteFunctionBunch先将网络数据串(Bunch)放入缓存RemoteFunctions中，稍候跟随属性复制一起写入网络数据包缓存中(放在属性复制之后)。
>
> 同一批次处理中，同一非可靠广播RPC最多调用两次，多了会被丢弃

```cpp
void FObjectReplicator::QueueRemoteFunctionBunch( UFunction* Func, FOutBunch &Bunch )
{
//同一批次处理中，同一非可靠广播RPC最多调用两次，多了会被丢弃
	if (++RemoteFuncInfo[InfoIdx].Calls > CVarMaxRPCPerNetUpdate.GetValueOnAnyThread())
	{
		UE_LOG(LogRep, Verbose, TEXT("Too many calls (%d) to RPC %s within a single netupdate. Skipping. %s.  LastCallTime: %.2f. CurrentTime: %.2f. LastRelevantTime: %.2f. LastUpdateTime: %.2f "),
		return;
	}
	
	//放入缓存RemoteFunctions中，稍候跟随属性复制一起写入网络数据包缓存中。
	RemoteFunctions->SerializeBits(Bunch.GetData(), Bunch.GetNumBits());
}

bool FObjectReplicator::ReplicateProperties_r(...)
{
...
//处理属性复制的逻辑
...

	if ( RemoteFunctions != nullptr && RemoteFunctions->GetNumBits() > 0 )
	{
		if ( UNLIKELY(GNetRPCDebug == 1) )
		{
		Writer.SerializeBits( RemoteFunctions->GetData(), RemoteFunctions->GetNumBits());
		}
	}
}
```

- **再通过FlushNet将缓存中的数据发送(LowLevelSend)**。
FlushNet一般是在网络连接(UNetConnection)的Tick中触发的，也可以手动调用提前触发下数据推送。
    
    ![Untitled](http://pic.xyyxr.cn/20260504161054389.png)
    
    **FlushNet通过LowLevelSend发送网络数据包**
    
```cpp
    void UNetConnection::FlushNet(bool bIgnoreSimulation)
    {
    ...
    
    	if (Driver->IsNetResourceValid())
    		{
    			LowLevelSend(SendBuffer.GetData(), SendBuffer.GetNumBits(), Traits);
    		}
    
    ...
    }
```
    
    **UNetConnection的Tick中触发FlushNet**
    
```cpp
    void UNetConnection::Tick(float DeltaSeconds)
    {
    	// Flush.
    		if ( TimeSensitive || 
    		(Driver->GetElapsedTime() - LastSendTime) > Driver->KeepAliveTime)
    		{
    			bool bHandlerHandshakeComplete = !Handler.IsValid() || 
    			Handler->IsFullyInitialized();
    	
    			if (bHandlerHandshakeComplete && HasReceivedClientPacket())
    			{
    				FlushNet();
    			}
    		}
    	
    }
```
    

**手动调用FlushNet**（发送缓存满了直接触发下数据推送 每个Packet 最多1024个字节）

```cpp
int32 UNetConnection::WriteBitsToSendBufferInternal(...)
{
	// Flush now if we are full
	if (GetFreeSendBufferBits() == 0
#if !UE_BUILD_SHIPPING
		|| CVarForceNetFlush.GetValueOnAnyThread() != 0
#endif
		)
	{
		FlushNet();
	}

	return RememberedPacketId;
}
```

## **发包网络带宽限制**

---

每个连接每帧处理的数据量是有限制的，当数据量超过处理限制时，就会造成网络阻塞。

当前连接通过带宽剩余量计算

```cpp

//塞入数据包时 将数据包发送大小计入带宽占用量
void UNetConnection::FlushNet(bool bIgnoreSimulation)
{
	if (!IsReplay())
		{
			int32 NewQueuedBits = 0;
			const bool bWouldOverflow = UE::Net::Connection::Private::Add_DetectOverflow_Clamp(QueuedBits, PacketBytes * 8, NewQueuedBits);

			QueuedBits = NewQueuedBits;
		}
}

void UNetConnection::Tick(float DeltaSeconds)
{

//每帧释放出来来带宽
	if (!IsReplay())
		{
			float BandwidthDeltaTime = DeltaTime;
			if (DesiredTickRate != 0.0f)
			{
				BandwidthDeltaTime = FMath::Clamp(BandwidthDeltaTime, 0.0f, 1.0f / DesiredTickRate);
			}
	
			float DeltaBits = CurrentNetSpeed * BandwidthDeltaTime * 8.f;
	
			int32 NewQueuedBits = 0;
			const int64 DeltaQueuedBits = -FMath::TruncToInt(DeltaBits);
			const bool bWouldOverflow = UE::Net::Connection::Private::Add_DetectOverflow_Clamp(QueuedBits, DeltaQueuedBits, NewQueuedBits);
	
			QueuedBits = NewQueuedBits;
	
	}
}
```

**如果当前连接的数据量超出限制时,IsNetReady返回False,表示当前连接处于堵塞状态。**

```cpp
int32 UNetConnection::IsNetReady(bool Saturate)
{
	if (IsReplay())
	{
		return 1;
	}

	// Return whether we can send more data without saturation the connection.
	if (Saturate)
	{
		QueuedBits = -SendBuffer.GetNumBits();
	}

#if !(UE_BUILD_SHIPPING || UE_BUILD_TEST)
	if (CVarDisableBandwithThrottling.GetValueOnAnyThread() > 0)
	{
		return 1;
	}
#endif

	if (NetworkCongestionControl.IsSet())
	{
		return NetworkCongestionControl.GetValue().IsReadyToSend(Driver->GetElapsedTime());
	}

	return QueuedBits + SendBuffer.GetNumBits() <= 0;
}
```

net.DisableBandwithThrottling 指令可以关闭带宽限制(非Shipping包)

```cpp
#if !UE_BUILD_SHIPPING
static TAutoConsoleVariable<int32> CVarDisableBandwithThrottling(TEXT("net.DisableBandwithThrottling"), 0,
	TEXT("Forces IsNetReady to always return true. Not available in shipping builds."));
#endif
```

**当前网络连接出现堵塞状态时**

> [!note]- 一些非可靠RPC会直接丢弃(非可靠的广播RPC不会被直接丢弃，放入缓存中稍候跟随属性同步一起下发)
> ```cpp
> void UNetDriver::InternalProcessRemoteFunctionPrivate(...)
> {
>     if (!(Function->FunctionFlags & FUNC_NetReliable) && (!(Function->FunctionFlags & FUNC_NetMulticast)) && (!Connection->IsNetReady(0)))
>     {
>         DEBUG_REMOTEFUNCTION(TEXT("Network saturated, not calling %s::%s"), *GetNameSafe(Actor), *GetNameSafe(Function));
>         return;
>     }
> }
> ```

> [!note]- 属性复制会被暂停
> ```cpp
> int32 UNetDriver::ServerReplicateActors_ProcessPrioritizedActorsRange(...)
> {
>         if (!Connection->IsNetReady( 0 ) && !bIgnoreSaturation)
>         {
>             GNumSaturatedConnections++;
>             return 0;
>         }
> }
> ```
>
>
> > 💡
> >
> > 当高频率的可靠RPC和广播的RPC(包括非可靠的)过多导致网络频繁阻塞的情况下。可以考虑用属性同步代替RPC,因为网络阻塞的状态会暂停属性复制，不会加剧阻塞。当网络阻塞解除时，直接复制最新的属性值到客户端，对应一些不太重要的状态，当出现阻塞时，可以忽略一些中间数据，拿到最新数据即可。

## 收包流程

---

![Untitled](http://pic.xyyxr.cn/20260504161058227.png)

> [!note]- **UIpNetDriver::TickDispatch中处理每一帧接收的网络数据**
> ```cpp
> void UIpNetDriver::TickDispatch(float DeltaTime)
> {
>     //处理所有接受到的消息包
>     for (FPacketIterator It(this); It; ++It)
>     {
>         //解析单个Packet
>         Connection->ReceivedRawPacket(...);
>     }
> }
> ```

> [!note]- **UNetConnection::ReceivedPacket解析收到的单个消息包(Packet)**
> ```cpp
> void UNetConnection::ReceivedPacket( FBitReader& Reader, bool bIsReinjectedPacket, bool bDispatchPacket )
> {
> ...
>     FNetPacketNotify::FNotificationHeader Header;
>     //读取PacketHead(包头信息)
>     if (!PacketNotify.ReadHeader(Header, Reader))
>     {
>     }
>
>     //通过包头信息分析ack数据 确认发给对方的哪些消息包被接收 哪些包丢包了
>     //对丢包的可靠Bunch数据包 安排重发
>     PacketNotify.Update(Header, HandlePacketNotification);
>
>   //处理包体数据 Bunch数据包
>     if (bDispatchPacket)
>     {
>         DispatchPacket(Reader, InPacketId, bSkipAck, bHasBunchErrors);
>     }
>
>
>     //更新ack数据确认对方发过来的消息包接收情况
>     if( !IsInternalAck() )
>     {
>         if ( bSkipAck )
>         {
>             PacketNotify.NakSeq( InPacketId );
>         }
>         else
>         {
>             PacketNotify.AckSeq( InPacketId );
>         }
>     }
> ...
> }
> ```

> [!note]- **UNetConnection::DispatchPacket处理包体数据(Bunch数据包)**
> ```cpp
> void UNetConnection::DispatchPacket( FBitReader& Reader, int32 PacketId, bool& bOutSkipAck, bool& bOutHasBunchErrors )
> {
>     while( !Reader.AtEnd() && GetConnectionState()!=USOCK_Closed )
>     {
>     }
> }
> ```

- **将接收到Bunch数据包到逐层分发(**NetConnection→ActorChannel→FObjectReplicator)，**最终在FObjectReplicator::ReceivedBunch里对收到消息包进行处理**
(根据是RPC数据还是属性复制数据做不同的处理)

```cpp
bool FObjectReplicator::ReceivedBunch(...)
{

// Handle replayout properties
	if (bHasRepLayout)
	{
....
		if (!LocalRepLayout.ReceiveProperties(...))
		{
			return false;
		}

...
	}
	while (true)
	{

...
		// Handle property
		if (FStructProperty* ReplicatedProp = CastField<FStructProperty>
		(FieldCache->Field.ToField()))
		{
			if (!FNetSerializeCB::ReceiveCustomDeltaProperty(...))
			{
				...
				continue;
			}
		}
		// Handle function call
		else if ( Cast< UFunction >( FieldCache->Field.ToUObject() ) )
		{
		...
			bool bSuccess = ReceivedRPC(Reader, RepFlags, 
			FieldCache, bCanDelayRPCs, bDelayFunction, UnmappedGuids);
...
			
		}
		else
		{
			return false;
		}
	}
}
```

## 收包时序机制

---

UDP不保证消息包的接收顺序跟发送顺序一致，所有UE在收包时会根据消息包的序号进行排序，尽量保证时序的一致性。如果接收到的消息包序列号靠后但提前收到(前面的消息包还未处理)，会先缓存先来等待前置消息包处理(最多缓存32个)。但这种缓存等待前置消息包的机制是在有限条件下才成立的

- 首先仅限于当帧接收到的一批消息包，不在一帧接收的不会一直缓存等待。
- 其次是如果是首次触发缓存等待，需跟前置消息包缺失限制在一个阈值(默认是3)，超过阈值则也不会触发缓存等待，会直接视为前置消息包丢失。
- 如果等待队列塞满了(默认最多放32个) 则后续包视为丢包
- 如果等待队列(PacketOrderCache)尚未启用 视为丢包

![image.png](http://pic.xyyxr.cn/20260504161058228.png)

> 💡
>
> 这是Packet层面的时序机制，丢包重发是新的Packet就不在时序保证范围内。Bunch层面的时序机制是Bunch内部维护的一个序列号，能保证丢包重发依然保证时序，前提是属于同一个ActorChannel。(可靠Bunch的时序问题参照上面Bunch部分)

```cpp
void UNetConnection::ReceivedPacket( FBitReader& Reader, bool bIsReinjectedPacket, bool bDispatchPacket )
{
		//判定下当前处理的包跟上一个处理的包 直接的序号差值
		const int32 PacketSequenceDelta = PacketNotify.GetSequenceDelta(Header);
		if (PacketSequenceDelta > 0)
		{
...
			const int32 MissingPacketCount = PacketSequenceDelta - 1;
			
		 //如果已经启用了缓存等待或者出现前置序号缺失且在阈值范围内 则将消息包到达缓存队列中
			if (bFillingPacketOrderCache || 
			(bCheckForMissingSequence && 
			MissingPacketCount > 0 && 
			MissingPacketCount <= MaxMissingPackets))
			{
				int32 LinearCacheIdx = PacketSequenceDelta - 1;
				
				//循环数组大小32
				int32 CacheCapacity = PacketOrderCache->Capacity();
				bool bLastCacheEntry = LinearCacheIdx >= (CacheCapacity - 1);
				LinearCacheIdx = bLastCacheEntry ? (CacheCapacity - 1) : LinearCacheIdx;

				int32 CircularCacheIdx = PacketOrderCacheStartIdx;
				//在缓存队列中找到对应的位置 LinearDec为1那数组索引就是1 以此类推
				//LinearDec为0 表明等到了缓存队列需要的前置消息包 可以准备处理缓存
				for (int32 LinearDec=LinearCacheIdx; LinearDec > 0; LinearDec--)
				{
					CircularCacheIdx = PacketOrderCache->GetNextIndex(CircularCacheIdx);
				}

				TUniquePtr<FBitReader>& CurCachePacket = PacketOrderCache.GetValue()[CircularCacheIdx];

				
				if (!CurCachePacket.IsValid())
				{
				 //缓存到等待队列中
					CurCachePacket = MakeUnique<FBitReader>(Reader);

					PacketOrderCacheCount++;
					TotalOutOfOrderPacketsRecovered++;
				...
				}
				else
				{
					//队列超了 当丢包处理
					TotalOutOfOrderPacketsDuplicate++;
					...
				}

				return;
			}
		}
		else
		{
			//走到这里表明 出现了先处理序列号靠后的消息包的情况
			//(可能是消息包在后几帧才收到或者尚未启用排队等待机制PacketOrderCache)
			//视为丢包 并会尝试启动缓存等待机制(如果还没启用的话)
			TotalOutOfOrderPacketsLost++;
			....

			//尝试启动缓存等待机制(如果还没启用的话)
			if (!PacketOrderCache.IsSet() && 
			CVarNetDoPacketOrderCorrection.GetValueOnAnyThread() != 0)
			{
				int32 EnableThreshold = 
				CVarNetPacketOrderCorrectionEnableThreshold.GetValueOnAnyThread();

				if (TotalOutOfOrderPacketsLost >= EnableThreshold)
				{
				....
					PacketOrderCache.Emplace(CacheSize);
				}
			}
			return;
		}
}
```

在每次处理完单个消息包(ReceivedPacket)和处理完所有消息包之后都会调用一次**FlushPacketOrderCache**尝试处理一次排队等待的队列。

两次调用的区别在于:

- 处理完单个消息包后的调用是为了检测本次处理消息包之后等待队列那个期待队首消息包是否到了，等到了就开始处理，没等到就继续等待。(数组PacketOrderCache索引为PacketOrderCacheStartIdx的那个就是本帧等待队列期望接受到消息包，如果启用了等待队列ReceivedPacket处理这个等待消息包时也是先放入队列中，统一在FlushPacketOrderCache再按顺序依次处理)。
- 处理完所有消息包之后的调用则是不管等待队列期待的那个包消息是否等到了都开始按顺序依次处理，缺失的消息视为丢包(bFlushWholeCache=true)。

```cpp
void UNetConnection::ReceivedRawPacket( void* InData, int32 Count )
{
...
ReceivedPacket(Reader);
//检测本次处理消息包之后等待队列那个期待队首消息包是否到了，等到了就开始处理，没等到就继续等待
FlushPacketOrderCache();
...
}

void UNetConnection::PostTickDispatch()
{
...
//不管等待队列期待的那个包消息是否等到了都开始按顺序依次处理，缺失的消息视为丢包
//(bFlushWholeCache=true)。
FlushPacketOrderCache(/*bFlushWholeCache=*/true);
...
}

void UNetConnection::FlushPacketOrderCache(bool bFlushWholeCache/*=false*/)
{
	if (PacketOrderCache.IsSet() && PacketOrderCacheCount > 0)
	{
		bFlushWholeCache = bFlushWholeCache || bEndOfCacheSet;
		while (PacketOrderCacheCount > 0)
		{
			TUniquePtr<FBitReader>& CurCachePacket = Cache[PacketOrderCacheStartIdx];
			if (CurCachePacket.IsValid())
			{
				ReceivedPacket(*CurCachePacket.Get());
				CurCachePacket.Reset();
				PacketOrderCacheCount--;
			}
			else if (!bFlushWholeCache)
			{
			 //bFlushWholeCache 为False 则出现缺失的消息包 直接中断
			 //bFlushWholeCache 为True  则出现缺失的消息包 继续处理 缺失的视为丢包
				break;
			}
			PacketOrderCacheStartIdx = PacketOrderCache->GetNextIndex(...);
		}
		bFlushingPacketOrderCache = false;
	}
}
```

## 网络数据包拆分

---

发包当单个数据串(Bunch)数据量过大时是(超过MAX_SINGLE_BUNCH_SIZE_BITS)，会被拆分成多个子串进行发送。拆分的串会标记是否是拆分串bPartial,是否是首个子串bPartialInitial，是否是最后一个子串bPartialFinal 。收包将拆分的子串全部收集后再合并处理，合并完之前不会继续执行后面的处理逻辑，直到等到所有的拆分子串。

如果拆分的子串超过阈值(默认8个)，会将数据包标记为Reliable,并暂停该ActorChannel的属性复制,直到收到接收端确认包(bPausedUntilReliableACK )。

```cpp
FPacketIdRange UChannel::SendBunch( FOutBunch* Bunch, bool Merge )
{
...
//拆分多个子串
	if( Bunch->GetNumBits() > MAX_SINGLE_BUNCH_SIZE_BITS )
	{
		uint8 *data = Bunch->GetData();
		int64 bitsLeft = Bunch->GetNumBits();
		Merge = false;

		while(bitsLeft > 0)
		{
		....
			FOutBunch * PartialBunch = new FOutBunch(this, false);
			int64 bitsThisBunch = FMath::Min<int64>(bitsLeft, MAX_PARTIAL_BUNCH_SIZE_BITS);
			PartialBunch->SerializeBits(data, bitsThisBunch)
			OutgoingBunches.Add(PartialBunch);
		....
		}
	
	//如果拆分的子串超过阈值(默认8个)，会将数据包标记为Reliable,并暂停该ActorChannel的属性复制
	if ((GCVarNetPartialBunchReliableThreshold > 0) && (OutgoingBunches.Num() >= GCVarNetPartialBunchReliableThreshold) && !Connection->IsInternalAck())
	{
		if (!bOverflowsReliable)
		{
			Bunch->bReliable = true;
			bPausedUntilReliableACK = true;
		}

	}
	
		//将拆分的字段依次放入发送网络缓存中
		for( int32 PartialNum = 0; PartialNum < OutgoingBunches.Num(); ++PartialNum)
		{
			FOutBunch * NextBunch = OutgoingBunches[PartialNum];
	...
			if (OutgoingBunches.Num() > 1)
			{
			 //标记子串
				NextBunch->bPartial = 1;
				NextBunch->bPartialInitial = (PartialNum == 0 ? 1: 0);
				NextBunch->bPartialFinal = (PartialNum == OutgoingBunches.Num() - 1 ? 1: 0);
		
			}
			int32 PacketId = SendRawBunch(ThisOutBunch, Merge, GetTraceCollector(*NextBunch));
		}
...
}
```

接收端对拆分子包的处理:如果识别是一个拆分子串，会先将接收到的子串内容先在InPartialBunch中合并，合并完成之后才会作为HandleBunch进行后续处理。

```cpp
bool UChannel::ReceivedNextBunch( FInBunch & Bunch, bool & bOutSkipAck )
{
	//需要处理的Bunch
	FInBunch* HandleBunch = &Bunch;
	if (Bunch.bPartial)
	{
		//拆分是子串的话 不能将子串作为HandleBunch 
		//应该将合并完所有子串的数据InPartialBunch 作为最终的HandleBunch 
		HandleBunch = NULL;
		//处理拆分成多个子串的Bunch
	...
		if (Bunch.bPartialInitial)
		{
		 //首个拆分子串 创建一个接收Bunch开始接收后续拆分子Bunch 合并数据
		  InPartialBunch = new FInBunch(Bunch, false);
			InPartialBunch->AppendDataFromChecked(...);
		}
		else
		{
			if (InPartialBunch ...)
			{
				//合并后续数据
				InPartialBunch->AppendDataFromChecked(...);
				if (Bunch.bPartialFinal)
				{
					//拆分子串合并完成了 将合并完成的数据 作为HandleBunch可以开始处理
					HandleBunch = InPartialBunch;
				}
			}
		}
	...
	}
	
	if ( HandleBunch != NULL )
	{
		//继续处理Bunch数据
		//子串没合并完之前 不会走到这里
		return ReceivedSequencedBunch( *HandleBunch );
	}
}
```

# 网络包收/发包总结

---

[Replicated Object Execution Order in Unreal Engine | Unreal Engine 5.5 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/replicated-object-execution-order-in-unreal-engine)

- UE网络同步时使用可靠(reliable)和不可靠(unreliable)通信方法的组合在服务器和连接的客户端之间传输信息。可靠的通信会保证接收端能收到，如果丢包了会触发数据重发。不可靠通信不保证接收端能接受到，丢包不会重发。

> [!note]- Actor的属性复制(PropertyReplication)是不可靠通信。不同属性的复制在客户端调用OnRep_XXX是不保证先后顺序的，跟置脏(MarkedDirty)和声明顺序无关,如果客户端逻辑依赖于多个字段OnRep_XXX调用顺序的，建议是将这些字段封装到一个结构体里。(同一帧是先将所有属性赋值之后，再统一调用OnRep_XXX)
> ```cpp
> void FObjectReplicator::PostReceivedBunch()
> {
> ...
>     CallRepNotifies(true);
> ...
> }
> ```
>
> > 💡
> >
> >     UObject::PostRepNotifies是客户端执行完本帧所有属性复制的OnRep_XX之后调用的，一些逻辑可以考虑放在这里处理。

> [!note]- 不同Actor(ActorChannel)之间的RPC调用在接收端执行的顺序是不确定的
> 同一个Actor(ActorChannel)的可靠RPC(包括可靠的广播RPC)在接收端的执行顺序是确定的
>
> ```cpp
> MyActor->ClientRPC1();
> OtherActor->ClientRPC2();
> MyActor->ClientRPC3();
>
> //上面的代码 在接收端执行的顺序可以是下面排序的任一一种都可能
> //RPC1 --> RPC2 --> RPC3
> //RPC1 --> RPC3 --> RPC2
> //RPC2 --> RPC1 --> RPC3
> //RPC2 --> RPC3 --> RPC1
> //RPC3 --> RPC1 --> RPC2
> //RPC3 --> RPC2 --> RPC1
> ```
>
> ```cpp
> MyActor->ClientReliableRPC1();
> MyActor->ClientReliableRPC2();
> MyActor->ClientReliableRPC3();
>
> //在接收端执行的顺序是确定的
> //RPC1 --> RPC2 --> RPC3
>
> //Actor和SubObject1是同一ActorChannel在接收端执行顺序也是确定
> MyActor->ClientReliableRPC1();
> MyActor->SubObject1->ClientReliableRPC2();
> MyActor->SubObject2->ClientReliableRPC3();
> MyActor->ClientReliableRPC4();
>
> //RPC1 --> RPC2 --> RPC3 --> RPC4
> ```

> [!note]- 同一个Actor(ActorChannel)的可靠RPC和不可靠RPC在接收端的顺序是不保证的，不可靠RPC可能会丢包或者放入队列(比如不可靠广播RPC或者指定要放入队列的,放入队列的会稍候跟属性复制一起下发)。
> ```cpp
> void UNetDriver::ProcessRemoteFunctionForChannelPrivate(...)
> {
> switch (SendPolicy)
>         {
>             case ERemoteFunctionSendPolicy::Default:
>                 QueueBunch = ( !Bunch.bReliable && 
>                 Function->FunctionFlags & FUNC_NetMulticast );
>                 break;
>             case ERemoteFunctionSendPolicy::ForceQueue:
>                 QueueBunch = true;
>                 break;
>             case ERemoteFunctionSendPolicy::ForceSend:
>                 QueueBunch = false;
>                 break;
>         }
>
>     if (QueueBunch)
>     {
>         Ch->QueueRemoteFunctionBunch(TargetObj, Function, Bunch);
>     }
> }
> ```

- 广播的不可靠RPC，一般不是直接放了网络发送缓存，而是先放入一个队列，会跟本帧属性复制一起放入网络发送缓存下发。(参照ERemoteFunctionSendPolicy)
- RPC和属性复制之间的执行顺序: RPC一般先于属性复制放入网络发送缓存(属性复制在Tick中检测写人，RPC在调用时就写入)，缓存在队列中跟随属性复制一起写入的RPC(比如广播的非可靠RPC)在属性复制执行完之后再写入缓存。