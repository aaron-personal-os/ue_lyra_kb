# GameFeatures-基础

> 来源：知乎专栏《InsideUE5》系列文章
> 原文链接：
> - [《InsideUE5》GameFeatures架构（一）发展由来](https://zhuanlan.zhihu.com/p/467236675)
> - [《InsideUE5》GameFeatures架构（二）基础用法](https://zhuanlan.zhihu.com/p/470184973)
> - [【UE5】聊聊ModularGameplay](https://zhuanlan.zhihu.com/p/377632346)

## 一、发展由来

GameFeatures作为GamePlay的新发展出来的一套框架，究其发展，就不得不回顾历史盘点手上的现有工具们。

### 1. 内建GamePlay框架

最早的最基础的当然要属于引擎的内建GamePlay框架，这部分相信大家也是都非常了解了。这套GamePlay框架其实也是随时代一直在进化的，从UE3时代比较简单的功能，进化到UE4的这些，然后再到UE5的WordPartition，LevelInstance等功能。可以说这些基本的Game Play类构成了引擎的核心玩法框架基石。它们提供的功能也很丰富，场景编辑、序列化、网络同步，生命周期等。一个初级开发者就可以直接利用这些基本的类开发出游戏雏形。

### 2. GameAbilitySystem技能框架

再之后随着玩法的复杂化，游戏里常常会需要丰富多样的技能。这就要求游戏玩法框架也能实现一套复杂的技能系统，同时我们还希望它易于扩展、易于配置、易于协作且还能支持联机。《堡垒游戏》的技能多样化需求也一直催生着GAS框架的进化。

### 3. Subsystem系统

再之后是Subsystem系统，UE在4.22版本的时候，开始引入Subsystems，然后在4.24完善。简单来说，Subsystems允许你从已经预定义的5个类中继续下来，并自动实例化和托管生命周期，用起来非常省心。 当你在代码里发现要写一个Manager类的时候，就很可能是把它换成Subsystem的好时机。 现在引擎代码的趋势是把越来越多的模块用Subsystem来管理，包括接下来要介绍的GameFeatues框架也有个GameFeatureSubsystem。

### 4. GameFeatures是什么？

终于说到GameFeatures，那它是一套什么东西呢？GameFeature其实就是一种比较特殊的插件，这些插件共同组成了游戏的整体玩法。普通的插件为游戏提供了一些基础功能的封装，例如数据库读取、EOS等这种功能。而游戏玩法上的插件，就可以说是GameFeature。我们利用这个插件框架，可以把一种玩法封装成一个插件，在运行时动态的开关这个插件，从而改变游戏的玩法。这么说起来和MOD意味还有点像，只不过MOD是一般通过直接修改游戏本体而实现的。 如果把一个游戏比喻成一台主机，那GameFeature就是像USB那样热插拔加上的功能，而Plugin的话就是类似插在主板上的内存显卡等这种更基础的功能。

这个比喻有点傻，不过却隐含了一些机制的道理：

- 谁更基础。插在主板上的硬件显然要比USB设备要更基础一些。因此Plugin也是用于实现相比GameFeature更加基础的功能的，比如网络通信SDK这些。而GameFeature是用于实现"玩法"的。
- 依赖顺序。如果把PC主机机箱比作我们的游戏项目CoreGame，则显然CoreGame是依赖于Plugin的，就像主板要依赖主板插槽上的设备。而USB设备显然要依赖于主机的功能，因此GameFeature是依赖于CoreGame的。
- 易变性。主板上的设备显然一般是插在上面就好了不会插来拔去，也一般不会在开机运行状态下热插拔，就像Plugin一般也是随着游戏打包编译到发行包里去的，一般也不会在运行时动态的加载释放。而USB设备的热插拔就是常规操作了，就像GameFeature设计之初就是用来在运行时开关某个游戏功能的。
- 底层本质一致。如果我们深究一下，会发现内存显卡等设备和USB设备其本质其实也都是通过某种接口"插在"主板上的，其实是一种共通的机制。因此GameFeature其实也是一种Plugin，也是依托于Plugin的机制实现的。

### 5. 为什么需要GameFeatures？

按理说基础的内建GamePlay框架、GAS、Subsystem这些功能已经挺强大，我们也用得挺顺手的，也开发出了众多的游戏，何必无事生非多出一个GameFeature呢？啊，时代在进步，命运在呼唤。一些问题只有在项目开发运营经历积累到一定时期了才展现出来，新的问题催生新的方案。以Epic的自家游戏《堡垒之夜》为例，在其开发过程中，随着每次赛季更新和活动内容迭代，也会很快就发现在玩家的Pawn类里开始充斥了几千行代码和上百个方法。逐渐就变得难以维护和难以查错。每次要做个活动加点新内容，就得在Pawn里添加特定的方法，开发过程逐渐就变成一种苦痛负担。玩家一时爽，开发苦断肠。

因此我们需要一种**模块化**的逻辑组织方式，这就是GameFeatures的由来。虽然Subsystem和GAS在框架的某些方面都提供了解耦的作用，但GameFeatures更进一步，允许在"游戏功能"这个颗粒度上进行解耦。

这种方式还为我们提供了这些优点：

- 团队内新人更易上手，因为无需了解项目内其他内在工作机制，就能开发这些独立功能。他可以创建一个GameFeature然后独立的开发和测试。
- 更少漏洞，更易读代码。因为GameFeature本身是独立自包含的，因此代码天然更易于进行单元测试，可以自然地避免在构建时意外或偶然地依赖其他代码。
- 更轻松的在多个团队或项目中共享功能，可以更容易的迁移插件模块。在以往我们虽然也幻想一个游戏功能模块可以从一个项目复用到另一个项目，但这些一般都是偏向玩法无关的功能模块。因为游戏玩法模块一般来说都合作得很"紧密"，耦合得很深，一般也很难干净拆出来复用。而GameFeatues则至少为我们提供了一个解决方向，把一些独立玩法封装成GameFeatue，则至少大大增大了复用的可能。
- 更容易在大型或分布式开发环境中协作，模块化总是能促进团队协作，更少的担心自己的修改会干涉到别人的功能。
- 更容易在"快迭代更新"游戏中迭代功能，也能快速安全的删除出现问题的功能。当前游戏业是越来越多的网游了，因此这些长运营的游戏一般也都得不停的迭代更新功能，在开发过程中，把这些要更新出去的功能以GameFeature的方式一小包一小包的模块化分发出去，显然更容易开发和管理。万一哪个玩法包出错了，也可以及时动态的关闭它，而不影响游戏本体的功能。

## 二、基础用法

### 1. 开启插件

第一步就是来到插件界面，开启这两个插件：GameFeatures和ModularGameplay。

其中GameFeatures插件实现了Actions执行和GameFeature的装载，而ModularGameplay为AddComponent提供了实现支撑。

### 2. 创建GameFeature

在插件界面，选NewPlugin后就会多一个GameFeature的选项,点创建就可以创建出一个GameFeature了。这里只要注意一点**不要更改默认的目录，必须放在GameFeatures目录下**。因此源码里写死了只检测该目录下的插件为GameFeature。

通过编辑器创建GameFeature，会自动的帮你配置AssetManager和在GameFeatures目录创建GameFeatureData资产，因此也是首选推荐这种方式。当然有些时候你也可能想从别处拷贝一个现有GameFeature到你的项目里，手动拷贝创建的方式你就得额外注意目录正确、AssetManager配置和GameFeatureData的名字和配置了。

**注意点：不要更改默认的目录，GameFeature必须放在GameFeatures目录下!**

### 3. 查看GameFeature

创建出来的GF，在内容浏览器上选择显示插件内容就可以看见了。我们这里已经注意到在根目录上已经自动生成了一个插件同名的资产(MyFeature)。这是个GameFeatureData，定义描述了整个GameFeature要执行的动作列表。GameFeature的机制是直接读取跟插件同名的GameFeatureData资产的，所以我们应该去编辑它，但不要去改它的名字。

**注意点：不要更改GameFeatureData的名字，保持跟GameFeature的插件同名!**

### 4. 配置AssetManager

当然这个时候我们可以去检查一下项目设置里AssetManager，是否已经自动加上了GameFeatureData的主资产类型。如果没有的话，比如说我们是直接从别的地方拷贝过来的GameFeature插件，这样的话就不会自动有。我们就按照图上的方式补上就好了。只有定义了此项，GameFeatureData的加载才能正常工作。GameFeature的实现强烈依赖于AssetManager的资源探测发现来加载释放相应的资产，因此一定要配置此项。好在这个配置是机械无脑的，照着做就好了，不用太深究原理。

如果没有配置，在编辑器启动的时候会报出警告：

**注意点：一定要记得相应配置AssetManager来扫描GameFeatureData，否则无法正常工作！**

### 5. 配置Actions

我们双击GameFeatureData，就可以来配置这个GameFeature插件的功能。从上到下依次是插件的初始状态和当前状态，关于GameFeature的状态我们在之后会详细描述。这里最重要的是配置Actions，我们在这里可以配置一个Action数组，指定插件激活后要进行的一系列操作动作。整个GameFeature插件的实现其实就是在插件内定义一些组件或资产，然后在这里通过Action来配置关联上。配置完成后，最好重启一下编辑器，以便让编辑器重新加载一下GameFeatureData，或者把当前状态设为Installed再Active一下来重新加载。

**注意点：在Active状态是无法Edit Plugin信息的，编辑完GameFeatureData后最好触发重新加载一下来生效。**

### 6. GameFeatureAction_AddComponent示例

Action中最重要的就是AddComponent，这里以《古代山谷》的黑暗世界对战为例，Echo在接触到传送门后，会触发AncientBattle Game Feature插件的开启，之后AddComponent开始用做，会在Echo身上添加一个动画替换组件，把Echo的骨骼动画替换成另一个动画蓝图，增加施法动作。还会在场景里为可被攻击成为目标的物体添加标记。

我们自己项目里的逻辑也是同样的套路。通过某种场景互动或契机触发GameFeature的Active，然后这个GameFeature的一系列Action就开始生效运作。失效的时候反向做一些清理收尾工作就行。

### 7. 注册Actor为接收者

想要让AddComponent发挥作用的前提是，受体Actor身上要把自己注册为接收者。记得在Actor的BeginPlay和EndPlay分别调用AddReceiver和RemoveReceiver就可以了。为想要动态添加GameFeatureAction_AddComponent(最常见)的Actor调用AddReceiver，记得在EndPlay调用RemoveReceiver。之后就可在其身上添加应用AddComponent Action，其他类型的Action不需要此手动操作。在调试GameFeature的时候，常常可能发现明明配了Action，但是Actor怎么就没有反应不起作用呢，这时就很可能是你忘了给该Actor事先注册为接收者。多提一句，AddComponent的实现还蛮精巧的，即使是在GameFeature生效之后再事后注册Actor为Receiver，也能成功的AddComponent。

当然每次对每一个想要实施的Actor都来这一步还挺麻烦的，对于懒人，在ModularGameplay插件里定义的ModularGameplayActors都已经帮你实现好了该操作，我们只要从该基类继承下来就成。

**注意点：一定要记得把Actor注册为Receiver，AddComponent才能工作！**

### 7. 激活GameFeature

加载激活插件有几种办法可以用，在编辑器里可以直接通过按钮来切换。在运行时还可以通过GameFeaturesSubsystem提供的C++ API。也可以通过命令行指令来执行，其底层核心都是调用的UGameFeaturesSubsystem内部的各种方法。你可以在你的游戏逻辑合适位置来调用这些API。

**控制台启用指令** 
```
LoadGameFeaturePlugin GF_PersonalTestForLY
```

**蓝图激活** 
使用 `Load And Activate Game Feature Plugin` 蓝图节点。

**注意点：要记得激活GameFeature后才能工作！**

## 总结

希望看到这，能引起你的兴趣来继续学习GameFeatures这个框架。对于每个UE程序员来说，只要工作中有涉及到GamePlay部分，我觉得都有必要来学习一下。因为GameFeatures新的思想和代码资源组织方式，必然会对项目的整体架构产生深远的影响，从而影响到每个人的工作内容涉及部分。
