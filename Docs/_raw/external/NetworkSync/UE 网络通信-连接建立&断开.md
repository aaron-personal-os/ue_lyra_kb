> 💡 **本系列文章基于UE5.3**

# 建立网络连接

---

UE的网络通信是基于Channel的，其中ControlChannel就是负责控制客户端与服务器建立连接的通道

## DS端创建监听

---

DS端在启动时，会通过UWorld::Listen创建网络模块NetDriver、创建和绑定Socket

![Untitled](http://pic.xyyxr.cn/20260504161058229.png)

## 客户端尝试连接DS

---

客户端在指定连接的服务器时会创建网络模块并创建一个对应的网络连接ServerConnection

![Untitled](http://pic.xyyxr.cn/20260504161058230.png)

```cpp
void UPendingNetGame::InitNetDriver()
{
...
		if (GEngine->CreateNamedNetDriver(...))
		{
			NetDriver = GEngine->FindNamedNetDriver(this, NAME_PendingNetDriver);
		}
		if( NetDriver->InitConnect( this, URL, ConnectionError ) )
		{
		}
...
}

bool UIpNetDriver::InitConnect(...)
{
...
	ServerConnection = NewObject<UNetConnection>(...);
...
}
```

## 客户端和DS通过握手流程建立连接

---

客户端和DS初始化网络连接后会通过一个握手流程(Handshake)来建立连接，握手流程消息包类型如下:

```cpp
	enum class EHandshakePacketType : uint8
	{
		InitialPacket		= 0,
		Challenge			= 1,
		Response			= 2,
		Ack					= 3,
		RestartHandshake	= 4,
		RestartResponse		= 5,
		VersionUpgrade		= 6,

		Last = VersionUpgrade
	};
```

会通过四次通信确立连接：

客户端先跟服务器打招呼⇒是你吗?(InitialPacket)

服务器回复⇒是的，你要进行连接吗?(Challenge)/不是，找错人了(VersionUpgrade)(连接失败)

客户端回复⇒是的，现在可以连接吗?(Response)

服务器回复⇒可以(Ack)

- **InitialPacket**
首先客户端发一个InitialPacket消息包启动握手流程尝试跟DS端建立连接(打招呼)
    
    ![Untitled](http://pic.xyyxr.cn/20260504161058231.png)
    
```cpp
    void StatelessConnectHandlerComponent::SendInitialPacket(...)
    {
    ...
    	BeginHandshakePacket(...);
    	SendToServer(...,EHandshakePacketType::InitialPacket,...);
    ...
    }
```
    

> [!note]- **Challenge/VersionUpgrade**
> DS端在接受到一个客户端的握手消息包后，会为其创建一个客户端连接并执行新连接接入流程(IncomingConnectionless)。
>
> 先校验版本，校验不过则SendVersionUpgradeMessage通知客户端版本校验不通过（**VersionUpgrade**），连接失败。
>
> 校验通过则通过SendConnectChallenge发送回复消息包(连接询问包)(**Challenge**)
>
> ![Untitled](http://pic.xyyxr.cn/20260504161100283.png)
>
> ```cpp
> void UIpNetDriver::TickDispatch(float DeltaTime)
> {
> ...
>     for (FPacketIterator It(this); It; ++It)
>     {
>         ...
>         if (Connection == nullptr)
>         {
>             ...
>             //判定是否是首次握手的消息包 是则创建一个新的网络连接
>             if (bAcceptingConnection)
>                 {
>                     ...
>                     Connection = ProcessConnectionlessPacket(...);
>                     ...
>                 }
>             ...
>             }
>         ...
>     }
> ...
> }
> ```
>
> ```cpp
> void StatelessConnectHandlerComponent::IncomingConnectionless(...)
> {
>     const bool bValidVersion = CheckVersion(HandshakeData, TargetVersion);
>
>     const bool bInitialConnect = 
>     HandshakeData.HandshakePacketType == EHandshakePacketType::InitialPacket &&
>                                                 HandshakeData.Timestamp == 0.0;
>
>         if (Handler->Mode == UE::Handler::Mode::Server && 
>             bValidVersion && 
>             (bHasValidSessionID || bInitialConnect))
>             {
>                 if (bInitialConnect)
>                 {
>                     SendConnectChallenge(...);
>                 }
>             }
>
>             else if (Handler->Mode == UE::Handler::Mode::Server && 
>             !bValidVersion && bInitialConnect &&
>                         HandshakeData.RemoteCurVersion >= 
>                         EHandshakeVersion::NetCLUpgradeMessage)
>             {
>
>                     SendVersionUpgradeMessage(...);
>
>             }
>
> }
>
> bool StatelessConnectHandlerComponent::CheckVersion(...) const
> {
> }
> ```


> [!note]- **Response**
> 客户端在收到DS端发过来的Challenge消息包后，通过SendChallengeResponse再发一个回复包(连接回复包)（**Response**）  
>
> ![Untitled](http://pic.xyyxr.cn/20260504161100284.png)
>
> ```cpp
> void StatelessConnectHandlerComponent::Incoming(FBitReader& Packet)
> {
>     const bool bIsChallengePacket = 
>     HandshakeData.HandshakePacketType == EHandshakePacketType::Challenge && 
>     HandshakeData.Timestamp > 0.0;
>
>     if (bIsChallengePacket)
>     {
>         SendChallengeResponse(...);
>     }
> }
> ```

- **Ack**	
DS端在收到Response后再通过发送一个SendChallengeAck 发送一个确认包(连接确认包)(**Ack**)
    
    ![Untitled](http://pic.xyyxr.cn/20260504161100285.png)
    
```cpp
    void StatelessConnectHandlerComponent::IncomingConnectionless(...)
    {
    	const bool bValidVersion = CheckVersion(HandshakeData, TargetVersion);
    	
    	const bool bInitialConnect = 
    	HandshakeData.HandshakePacketType == EHandshakePacketType::InitialPacket &&
    												HandshakeData.Timestamp == 0.0;
    												
    		if (Handler->Mode == UE::Handler::Mode::Server && 
    			bValidVersion && 
    			(bHasValidSessionID || bInitialConnect))
    			{
    				if (bInitialConnect)
    				{
    					...
    				}
    				else
    				{
    					SendChallengeAck(...);
    				}
    			}								
    }
```
    

> 💡 RestartHandshake/RestartResponse是指重新连接是触发的握手流程

客户端在收到Ack包后，连接初始化就完成了。进入下一流程登录游戏**(**SendInitialJoin**)**。

![Untitled](http://pic.xyyxr.cn/20260504161100286.png)

```cpp
void StatelessConnectHandlerComponent::Incoming(FBitReader& Packet)
{
	if (HandshakeData.HandshakePacketType == EHandshakePacketType::Ack 
	&& HandshakeData.Timestamp < 0.0)
	{
		SetState(UE::Handler::Component::State::Initialized);
		Initialized();
	}
}

void HandlerComponent::Initialized()
{
	bInitialized = true;
	Handler->HandlerComponentInitialized(this);
}
```

# 加入游戏

---

DS端在握手流程执行完成之后，开始加入游戏(登录流程)

1. 首先客户端和DS发送消息包⇒打招呼**NMT_Hello (你好)**
    
    ![Untitled](http://pic.xyyxr.cn/20260504161100286.png)
    
```cpp
    void UPendingNetGame::SendInitialJoin()
    {
    ...
    		FNetControlMessage<NMT_Hello>::Send(...);
    		ServerConn->FlushNet();
    ...
    }
```
    
2. DS端收到**NMT_Hello**后会先校验下网络通信版本，根据校验结果进行回复⇒通过则发送询问NMT_Challenge(校验通过,是否需要加入游戏)/不通过则发送NMT_Upgrade(校验不通过无法加入游戏)
    
    ![Untitled](http://pic.xyyxr.cn/20260504161100287.png)
    
```cpp
    void UWorld::NotifyControlMessage(...)
    {
    ...
    case NMT_Hello:
    			{
    				const bool bIsCompatible = FNetworkVersion::IsNetworkCompatible(...);
    				if (!bIsCompatible)
    				{
    						FNetControlMessage<NMT_Upgrade>::Send(...);
    						Connection->FlushNet(true);
    						Connection->Close(ENetCloseResult::Upgrade);
    				}
    				else
    				{
    						...
    						Connection->SendChallengeControlMessage();
    						...
    				}
    			}
    ...
    }
    
    void UNetConnection::SendChallengeControlMessage()
    {
    ...
    		Challenge = FString::Printf(TEXT("%08X"), FPlatformTime::Cycles());
    		SetExpectedClientLoginMsgType(NMT_Login);
    		FNetControlMessage<NMT_Challenge>::Send(this, Challenge);
    		FlushNet();
    	...
    }
```
    
3. 客户端收到DS发送的询问是否登录游戏的消息**NMT_Challenge**后发送回复消息⇒**NMT_Login(是的，请求加入游戏)**
    
```cpp
    void UPendingNetGame::NotifyControlMessage(...)
    {
    case NMT_Challenge:
    		{
    			FNetControlMessage<NMT_Login>::Send(...);
    			NetDriver->ServerConnection->FlushNet();
    		}
    }
```
    
4. DS端收到客户端请求登录的消息(**NMT_Login**)发送回复消息⇒**NMT_Welcome(欢迎登录游戏)**并告诉客户端加载那张地图(Map)
    
    ![Untitled](http://pic.xyyxr.cn/20260504161100288.png)
    
```cpp
    void UWorld::NotifyControlMessage(...)
    {
    case NMT_Login:
    			{
    			if (GameMode)
    				{
    					GameMode->PreLoginAsync(...);
    				}
    			}
    }
    
    void UWorld::WelcomePlayer(..)
    {
    ...
    	FNetControlMessage<NMT_Welcome>::Send(...);
    ...
    }
```
    
5. 客户端收到DS端发送的欢迎登录消息(**NMT_Welcome**)，开始执行地图加载
并先立即发送回复消息:**NMT_Netspeed** 表示连接已经建立完成
    
```cpp
    void UPendingNetGame::NotifyControlMessage(...)
    {
    case NMT_Welcome:
    		{
    			URL.Map = TempURL.Map;
    			URL.RedirectURL = RedirectURL;
    			URL.Op.Append(TempURL.Op);
    			FNetControlMessage<NMT_Netspeed>::Send(...);
    		}
    }
    
    void UEngine::TickWorldTravel(FWorldContext& Context, float DeltaSeconds)
    {
    ...
    	if (Context.PendingNetGame && 
    	Context.PendingNetGame->bSuccessfullyConnected && 
    	!Context.PendingNetGame->bSentJoinRequest && 
    	!Context.PendingNetGame->bLoadedMapSuccessfully && 
    	(Context.OwningGameInstance == NULL || !
    	Context.OwningGameInstance->DelayPendingNetGameTravel()))
    		{
    			if (!Context.PendingNetGame->bLoadedMapSuccessfully)
    			{
    				// Attempt to load the map.
    				FString Error;
    
    				const bool bLoadedMapSuccessfully = LoadMap(Context, 
    				Context.PendingNetGame->URL);
    				
    			}
    		}
    ...
    }
```
    
    在地图加载完成之后会再次向DS发送消息告诉DS客户端已经完成了加入游戏的准备工作(**NMT_Join**)
    

![Untitled](http://pic.xyyxr.cn/20260504161100289.png)

    
```cpp
    void UPendingNetGame::SendJoin()
    {
    	bSentJoinRequest = true;
    
    	FNetControlMessage<NMT_Join>::Send(NetDriver->ServerConnection);
    	NetDriver->ServerConnection->FlushNet(true);
    }
```
    
6. **DS端在接收到客户做好加入游戏的准备后(NMT_Join)，开始执行DS端的登录流程**
    
```cpp
    void UWorld::NotifyControlMessage(...)
    {
    case NMT_Join:
    			{
    				Connection->PlayerController = SpawnPlayActor(...);
    			}
    }
    
    APlayerController* UWorld::SpawnPlayActor(...)
    {
    	if (AGameModeBase* const GameMode = GetAuthGameMode())
    	{
    		APlayerController* const NewPlayerController = GameMode->Login(...);
    		
    		GameMode->PostLogin(NewPlayerController);
    		return NewPlayerController;
    	}
    }
```
    

# 断开连接

---

UE默认流程在玩家断线之后会销毁对应的PlayerControll和绑定的Character ,但会在AGameMode的InactivePlayerArray 保留一份APlayerState的复制副本(原来的需要销毁掉)

(AGameMode::Logout=>AGameMode::AddInactivePlayer)，再断线重连之后从保存的副本里还原数据。(AGameMode::FindInactivePlayer)

```cpp
void AGameMode::Logout( AController* Exiting )
{
	APlayerController* PC = Cast<APlayerController>(Exiting);
	if ( PC != nullptr )
	{
		RemovePlayerControllerFromPlayerCount(PC);
		AddInactivePlayer(PC->PlayerState, PC);
	}

	Super::Logout(Exiting);
}

void AGameMode::PostLogin( APlayerController* NewPlayer )
{
	FindInactivePlayer(NewPlayer);
}

bool AGameMode::FindInactivePlayer(APlayerController* PC)
{
...
	if (EvaluatePlayerState(CurrentPlayerState))
		{
			APlayerState* OldPlayerState = PC->PlayerState;
			PC->SetPlayerState(CurrentPlayerState);
			PC->PlayerState->SetOwner(PC);
			PC->PlayerState->SetReplicates(true);
			PC->PlayerState->SetLifeSpan(0.0f);
			OverridePlayerState(PC, OldPlayerState);
			GameState->AddPlayerState(PC->PlayerState);
			InactivePlayerArray.RemoveAt(i, 1);
			OldPlayerState->SetIsInactive(true);
			OldPlayerState->SetUniqueId(FUniqueNetIdRepl());
			OldPlayerState->Destroy();
			PC->PlayerState->OnReactivated();
			return true;
		}
	...
}
```

如果要实现断线后玩家依然存在  也可以考虑修改下流程 APlayerController::OnNetCleanup 不销毁PlayerController 而是保留 

> 💡
>
> 在GameMode里 用一个列表去直接保存断开连接的PlayerController及其全局唯一标识， 客户端连接时带上唯一标识，能在保存列表里查找到对应的PlayerController就不用重新生成了，直接绑定原来的PlayerController

```cpp
void APlayerController::OnNetCleanup(UNetConnection* Connection)
{
	Player = NULL;
	NetConnection = NULL;	
	Destroy( true );
}
```

![Untitled](http://pic.xyyxr.cn/20260504161100290.png)