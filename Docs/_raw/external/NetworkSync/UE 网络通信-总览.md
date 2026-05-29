[《Exploring in UE4》网络同步原理深入（上）[原理分析]](https://zhuanlan.zhihu.com/p/34723199)

[UE5 -- Replication（网络复制）](https://zhuanlan.zhihu.com/p/578480318?utm_medium=social&utm_oi=641905948277477376&utm_psn=1572168122618085378&utm_source=wechat_session)

[UE5中的网络同步能力和同构服务器框架（上）](https://zhuanlan.zhihu.com/p/621339344)

> 💡 **本系列文章基于UE5.3**

# 概述

---

![Untitled](http://pic.xyyxr.cn/20260504161048535.png)

如上图所示，UE的网络通信是基于Channel的，每个网络连接(NetConnection)都包含了多个通信通道(Channel)，其中主要是ActorChannel。ActorChannel对应的是Actor。所以UE的网络通信的基本单元主要是Actor。

每个支持网络通信(网络复制)的Actor都会在各个网络连接中创建一个ActorChannel与该连接进行网络通信交互，主要是负责对该的Actor及Actor关联的且支持网络复制UObject(比如组件Component)进行属性复制和RPC的调用。

下面主要介绍下网络通信相关的基本概念:

- **UNetDriver**
- **UPlayer**
- **UNetConnection**
- **APlayerController**
- **UChannel**
- **Packet**
- **Bunch**
- **Ack**
- **FNetBitWriter/FNetBitReader**
- **UPackageMap**

# **网络驱动-NetDriver**

---

网络驱动**UNetDriver**类负责管理网络连接、处理网络数据包的发送和接收、以及处理网络通信中的其他重要任务。

- 管理着网络连接：包括建立、维护和关闭与客户端和服务器之间的连接。
- 收发包处理(RPC调用和Actor属性复制)
- 允许开发人员配置网络设置，如带宽限制、丢包模拟等，以优化网络性能和稳定性。

**UNetDriver 的主要类型：**

- **UIpNetDriver**（基于 UDP 协议的网络驱动程序，用于快速的数据传输）
- **UDemoNetDriver**（用于模拟网络行为 用于游戏录制、回放之类）
- **UWebSocketNetDriver**（基于 WebSocket 的网络驱动程序）
- **USteamNetDriver**（Steam 专用的网络驱动程序）

> 💡
>
> 主要是使用其子类**UIpNetDriver**
>
> UE里面默认的都是基于UDP Socket进行通信的

```cpp
class UNetDriver : public UObject, public FExec
{

  //客户端与服务器的网络连接
	UPROPERTY()
	TObjectPtr<class UNetConnection> ServerConnection;

	//服务器与客户端的网络连接
	UPROPERTY()
	TArray<TObjectPtr<UNetConnection>> ClientConnections;
	
	//RPC函数处理
	virtual void ProcessRemoteFunction(...);
	
	//发包处理
	void TickFlush(float DeltaSeconds);
	
	//收包处理
	void TickDispatch( float DeltaTime );
	
}
```

# 玩家连接信息-Player

---

UPlayer可以理解为玩家的输入信息。对于游戏内的一个玩家，需要为其提供输入信息，才能控制其进行游戏，而UPlayer就是给玩家提供输入信息的。

```cpp
class UPlayer : public UObject, public FExec
{
	UPROPERTY(transient)
	TObjectPtr<class APlayerController> PlayerController;
}
```

对于一个连接了客户端的DS端玩家角色
输入信息是由连接客户端的网络通信连接来提供输入信息的。

> 💡
>
> 网络通信连接UNetConnection 继承自UPlayer

对于一个客户端的玩家角色(主控端角色)
其输入信息是由连接DS端的网络通信连接和本地输入连接一起提供。

> 💡
>
> 本地输入连接ULocalPlayer 继承自UPlayer

> 💡 DS端创建的NPC、AI其输入直接是由DS内部逻辑提供(状态机、行为树之类的)，不存在UPlayer。

## 网络连接-NetConnection

---

网络通信连接UNetConnection 继承自UPlayer
DS上持有多个客户端到服务器的连接ClientConnection
在客户端上，持有服务器到客户端的连接ServerConnectio

```cpp
class UNetConnection : public UPlayer
{
	//网络连接控制的Actor(玩家)
	UPROPERTY()
	TObjectPtr<class AActor> ViewTarget;

	//网络连接归属Actor(PlayerController)
	UPROPERTY()
	TObjectPtr<class AActor> OwningActor;
}
```

# **玩家控制器-PlayerController**

---

PlayerController（玩家控制器）是用于控制玩家角色（Pawn）的重要类之一。用于处理玩家的输入交互(本地输入和网络输入)以及管理玩家在游戏中的操作和视角。

- 负责处理玩家的输入，包括键盘、鼠标、手柄输入等，以便控制玩家角色的移动、行为和交互。
- 管理玩家的视角，包括相机设置、视角旋转等，影响玩家在游戏中的视觉体验。
- 管理游戏 HUD（Heads-Up Display 抬头显示），用于显示玩家角色的生命值、武器信息、任务指引等关键信息。
- 负责管理游戏的状态和流程控制，处理玩家之间的互动、游戏进度控制以及切换游戏状态等功能。
- 在多人游戏中，PlayerController 管理玩家网络通信，确保玩家的同步和通信正常。
- 可以用于实现游戏截图、录制游戏过程或回放等功能

> 💡
>
> PlayerController作为一个控制器， 连接输入和被控制的角色(Pawn),将输入信息转发给被控制的角色

```cpp
class APlayerController : public AController
{
//分配的连接信息UPlayer 
//客户端是U**LocalPlayer** DS是**网络连接**UNetConnection(跟下面的NetConnection是同一个对象)

TObjectPtr<UPlayer> Player;

//网络通信链接
TObjectPtr<UNetConnection> NetConnection;

//HUD
TObjectPtr<AHUD> MyHUD;

//摄像机管理器
TObjectPtr<APlayerCameraManager> PlayerCameraManager;
	
//本地输入	
TObjectPtr<UPlayerInput> PlayerInput;
}
```

PlayerController关联一个主连接信息**Player(**UPlayer对象)
主控端角色是**ULocalPlayer** 
DS端角色是**UNetConnection**

对于联网游戏的主控客户端玩家，除了接收来自本地的ULocalPlayer提供的输入信息。 还需要有一个接收来自DS端提供的输入信息。所以PlayerController额外关联一个网络连接**NetConnection**(UNetConnection对象 基类是 UPlayer)

**PlayerController绑定连接信息**

![Untitled](http://pic.xyyxr.cn/20260504161056189.png)

# **网络通信通道-Channel**

---

**网络通信的数据通道(**每一个通道只负责交换某一个特定类型特定实例的数据信息)

![Untitled](http://pic.xyyxr.cn/20260504161056190.png)

### **ControlChannel**

**主要是发送接收连接与断开的相关消息**
在一个Connection中只会在初始化连接的时候创建一个该通道实例

### **VoiceChannel**

**用于发送接收语音消息**

在一个Connection中只会在初始化连接的时候创建一个该通道实例。

### **ActorChannel**

**网络通信的主要通道，处理Actor本身相关信息的同步，包括自身的同步以及SubObject**

属性的同步，RPC调用等

每个连接(Connection)里的会为每个网络相关的Actor创建对应的一个ActorChannel实例

> 💡
>
> 对于休眠的Actor(**Dormant**)不会进行网络同步

# 其他收发包相关概念

---

> [!note]- **Packet**
> 从Socket读出来的消息包数据
>
> 如下图所示，网络消息包Packet分为包头数据(PacketHead)和包体数据(PacketData)两部分。
> 包头数据主要包含了本次发送的消息包的序列号和Ack数据，包体数据部分主要是Bunch数据。
>
> > 💡
> >
> >     一个Packet可能只有包头数据而包体数据部分为空
>
> ![image.png](http://pic.xyyxr.cn/20260504161056191.png)


- **Bunch**
一个Bunch里面主要记录了Channel信息(比如ActorChannel主要是属性复制和RPC)。同时包含其他的附属信息如是否是完整的Bunch，是否是可靠等。
    
> 💡
>
>     **Bunch**数据过大可能会拆分成多个子Bunch分开传输，再在收包时合并)
    

- **Ack** 
Ack是与Bunch同级别概念的网络数据串，用于实现UDP的可靠数据传输，UDP传输时应答数据包(用于校验是否丢包了)，能让通信双方知道发给彼此的消息包哪些被接收了哪些被丢包
- **FNetBitReader/FNetBitWriter**
网络收发包的序列化类，继承自FArchive。负责网络收发包时的序列化和反序列化
- **FSocket**  
所有平台Socket的基类。 FSocketBSD：使用winSocket的Socket封装
- **UPackageMap** 
生成与维护UObject实例与NetGUID的映射绑定，负责UObject实例的网络传输序列化(保证客户端和DS端通过网络传输的UObject实例指针能一一对应上)。每一个网络连接Connection对应一个UPackageMap。
- **PacketHandler**  
网络包预处理，比如加密，前向纠错，握手等。里面有一个或多个HandlerComponents来执行特殊的数据处理。目前内置的包括加密组件RSA，AES，以及必备的握手组件StatelessConnectHandlerComponent

# 弱网环境和丢包率模拟

---

可以在下图所示的界面中设置弱网环境和丢包模拟

![image.png](http://pic.xyyxr.cn/20260504161056192.png)

# **网络分析器（Network Profiler）**

---

[使用虚幻引擎中的网络分析器 | 虚幻引擎 5.5 文档 | Epic Developer Community](https://dev.epicgames.com/documentation/zh-cn/unreal-engine/using-the-network-profiler-in-unreal-engine?application_version=5.5)

- 运行游戏时 在控制台输入指令 **NetProfile Enable** 开始采集网络通信数据
- 需要结束采集时 在控制台输入指令  **NetProfile Disable** 停止采集网络通信数据 通知会生成数据采集文件
- 在Saved\Profiling\目录下可以看到刚才采集数据生成的文件(后缀为.nprof)
> [!note]- 打开网络性能分析工具NetworkProfiler.exe 解析数据采集文件
> 在引擎目录下\Engine\Binaries\DotNET\可以找到网络性能分析工具NetworkProfiler.exe
>
> ![image.png](http://pic.xyyxr.cn/20260504161056193.png)
>
> ![image.png](http://pic.xyyxr.cn/20260504161058222.png)