> 💡 **本系列文章基于UE5.3**

[在虚幻引擎中使用Gameplay标签](https://dev.epicgames.com/documentation/zh-cn/unreal-engine/using-gameplay-tags-in-unreal-engine)

# 概述

---

**GameplayTag(后面简称Tag)**是一个标签系统，用于描述状态和分类，可以用来表示一个游戏对象的特性、状态、行为等信息。

**Tag的一些主要特性和用途**：

- **标记**
Tag是一种描述性的数据，它可以用来表示一个游戏对象的各种信息，例如对象的**类别、属性、状态、行为**等。例如，你可以用"Enemy", "Boss"等标签来描述一个敌人角色,用“Jump”，“Swimming”表明对象在跳跃或者游泳。
- **层级结构**
Tag支持层级结构，存在父子层级关系，你可以使用"."来分隔不同的层级。
    
    *例如，你可以有一个标签"Enemy.Boss.Dragon"，表示这是一个类型为"Dragon"的"Boss"级别的"Enemy"，Enemy为Enemy.Boss的父层级，Enemy.Boss为Enemy.Boss.Dragon的父层级。*
    **所有配置的Tag会构建成一个Tag树，每个Tag都是Tag树上的一个叶子结点**。
    
> 💡
>
>     下图所示 分别是以下Tag 构建的树状结构
>     *Ability.Dash
>     Ability.Grenade
>
>     InputTag.Ability.Dash
>     InputTag.Weapon.Fire
>     InputTag.Weapon.Reload*
    
    ![Untitled](http://pic.xyyxr.cn/20260504111207010.png)
    
- **查询和过滤**
你可以使用Tag来查询和过滤游戏对象。
*例如，你可以查询所有带有"Enemy"标签的对象，或者过滤掉所有带有"Boss"标签的对象。(子层级的可以匹配父层级，比如查找标签为“Enemy”的游戏对象，带有标签"Enemy.Boss“和“Enemy.Boss.Dragon”的游戏对象都可以匹配)*
- **触发行为**
你可以使用Tag来触发特定的行为。
*例如，你可以在一个GameplayAbility中定义，当目标带有"Boss"标签时，这个能力的效果加倍。*
- **组合和扩展**
你可以组合多个Tag来表示更复杂的信息，也可以通过添加或移除Tag来扩展你的游戏逻辑。
*例如 Ability组件AbilitySystemComponent,有一个Tag容器(FGameplayTagCountContainer),记录了拥有该组件的Actor(比如玩家、NPC)当前拥有的所有Tag。在游戏逻辑中可以检测当前玩家是否有指定的Tag从而执行对应的逻辑，同时可以监听Tag的添加和移除来绑定不同的逻辑。*

**应用场景举例**:

- 某些效果(BUFF)只对具有某个Tag的目标生效。*比如伤害效果对有虚弱Tag的目标伤害加倍*
- 免疫/驱散效果可以免疫/驱散带有指定Tag的效果(GE)
- 可以用Tag标记GA或者GE，然后在GA或者GE通过Tag配置阻止GA或者GE的生效
- 通过Tag驱动GC(GameplayCue)的触发
- 有某些Tag的时候禁止(打断)执行某些行为(比如跳跃、飞行)

> 💡 *GA(GameplayerAbility)、GE(GameplayEffect)、GC(GameplayCue)很多配置都涉及了Tag的配置*

**GameplayTag还可以应有于很多场景，不仅限于GAS系统。**

**Tag本质上就是一串FName**

```cpp
struct FGameplayTag
{
	FName TagName;
}
```

**FName是UE封装的一种可以高效存储和比较的字符值** 可以简单等同为一个**uint64**值

> 💡
>
> *实际上应该是两个uint32的值 ：
> 一个代表FName在全局的FName池子的索引，
> 一个是类似Test_123这种会拆分成字符串Test和uint32数值123*
>
> 对比时通过内存拷贝将两个uint32合并成一个uint64进行对比

**[FName](https://www.notion.so/FName-aa2f3a6f48714792a3371a9c35865b96?pvs=21)** 

GameplayTag是一种非常强大和灵活的工具，它可以帮助你更好地组织和管理你的游戏逻辑。通过合理地使用GameplayTag，你可以使你的代码更加清晰、模块化，也可以更容易地扩展和修改你的游戏逻辑。使用之前需要**根据项目具体的情况规划Tag的分类层级**。

![Untitled](http://pic.xyyxr.cn/20260504111207011.png)

# Tag配置

---

首先在项目设置(ProjectSetting)的GameplayTags页面可以对Tag系统进行配置。

![Untitled](http://pic.xyyxr.cn/20260504111207012.png)

**对应的ini的文件(DefaultGameplayTags.ini)**

![Untitled](http://pic.xyyxr.cn/20260504111207013.png)

**配置字段说明：**

- **Gameplay标签列表(GameplayTagTableList)：**
配置Tag的DataTable引用(*DataTable使用的数据结构**FGameplayTagTableRow***)
- **新建标签来源：**
可以在指定的Tags目录创新新的Tag的ini配置文件
    
> 💡 在Content或者插件(Plugin)的Config目录下创建一个**Tags**目录,可以在这些Tags目录放Tag的ini配置文件
>
>     *首次增加需要为新增的Tag来源添加了Tag后才会创建对应的ini文件*
>
>     *也可以在对应的Tags目录创建手动创建对应的.ini文件 格式参照下图*
    
    ![Untitled](http://pic.xyyxr.cn/20260504111207014.png)
    
    ![Untitled](http://pic.xyyxr.cn/20260504111208938.png)
    
- **Tag管理界面：**
可以对应**查看/添加/删除/重命名**Tag,还可以查看所有**引用Tag**的地方。
    
    ![Untitled](http://pic.xyyxr.cn/20260504111208940.png)
    

- **快速复制(FastReplication):** 
开启了该选项后Tag的网络复制直接复制Tag的索引而不是Tag的名称
    
> 💡 **通过Tag的索引可以实现Tag高效的网络复制**。否则需要将FName转换成字符串再网络复制，相对来说网络开销比较大。
>
>     **复制Tag索引需要保证客户端和服务器的GameplayTag索引的一致性**
    
- **常见复制标签(CommonlyReplicatedTags)**:
可以配置一些会频繁进行网络复制的Tag到列表。配置在该列表中的Tag在构造网络复制索引时会调整到数组的最前面，这样被分配的索引数值就比较小，复制占据的数据量就会小点，效率相对来说也会高点(参照下面**网络索引首位段**的说明)
- **容器大小的位数(NumBitsForContainerSize)：**
复制Tag容器时，容器大小占用的bit位。默认6位表示复制的Tag容器最大支持放63个Tag。
> [!note]- **网络索引首位段(NetIndexFirstBitSegment)**:
> Tag网络复制的索引值是uint16(16个bit位)，也就是最大支持65535个Tag配置。支持在复制Tag索引拆分成两个bit段进行序列化和反序列化。这里可以配置第一个bit段占用多少个bit位，默认配置16位，就是不做拆分(最大也就支持到16位)
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


# Tag添加

---

**Tag的添加有多种方式**:

- **在编辑Tag属性字段的界面直接配置**
*比如GE/GA配置Tag时*
    
    ![Untitled](http://pic.xyyxr.cn/20260504111208941.png)
    
- **在Tag的管理界面添加**
*参照上面Tag管理界面说明*
- **通过Tag的DataTable添加**
*DataTable数据结构是FGameplayTagTableRow
在项目配置(ProjectSetting)的GameplayTags配置对DataTable的引用关系*
> [!note]- **代码添加**
> **UE提供了可以直接使用的 Tag注册宏**
>
> 注册宏定义了一个全局的 **FNativeGameplayTag** 变量 只能在cpp中使用
> 如果需要被外部引用 在.h加上宏UE_DECLARE_GAMEPLAY_TAG_EXTERN
>
> **FNativeGameplayTag** 的构造函数会触发Tag的添加
>
> **FNativeGameplayTag** 和**FGameplayTag** 支持隐式转换(重载了操作符）

```cpp
    //导出Tag全局变量(为了定义在cpp中的Tag变量可以被外部引用)
    #define UE_DECLARE_GAMEPLAY_TAG_EXTERN(TagName) extern FNativeGameplayTag TagName;
    
    //带Tag说明的的注册宏(只能在cpp中使用该宏)
    //(如果需要被外部引用该变量 则在.h文件使用宏UE_DECLARE_GAMEPLAY_TAG_EXTERN)
    #define UE_DEFINE_GAMEPLAY_TAG_COMMENT(TagName, Tag, Comment)
    
    //不带Tag说明的的注册宏(只能在cpp中使用该宏)
    //(如果需要被外部引用该变量 则在.h文件使用宏UE_DECLARE_GAMEPLAY_TAG_EXTERN)
    #define UE_DEFINE_GAMEPLAY_TAG(TagName, Tag)
    
    //不带Tag说明的的注册宏(静态变量)(只能在Cpp文件里声明 且变量不能被外部引用)
    #define UE_DEFINE_GAMEPLAY_TAG_STATIC(TagName, Tag)
```
    
    **Tag注册宏** 代码示例
    
```cpp
    //.h文件(如果变量可以被外部引用 不需要被外部引用则无需添加)
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(TAG_Gameplay_Damage);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(TAG_Gameplay_DamageImmunity);
    
    //cpp文件
    UE_DEFINE_GAMEPLAY_TAG(TAG_Gameplay_Damage, "Gameplay.Damage");
    UE_DEFINE_GAMEPLAY_TAG(TAG_Gameplay_DamageImmunity, "Gameplay.DamageImmunity");
```
    

# **常用接口**

---

| 函数名                                                           | 函数说明                                                               |
| ------------------------------------------------------------- | ------------------------------------------------------------------ |
| **RequestGameplayTag**                                        | **通过一个FName查找到对应的FGameplayTag**                                    |
| **IsValidGameplayTagString**                                  | **判定一个字符串是否是合法的Tag格式**，如果格式不合法会尝试修复(OutFixedString)                |
| **MatchesTag**                                                | **校验下两个Tag是否匹配(模糊匹配 可以用子级Tag匹配父级Tag 但反过来就不行)**                     |                                                                |
| **MatchesTagExact**                                           | **校验下两个Tag是否匹配(精确匹配 需要两个Tag完全一致 ==)**                              |
| **MatchesAny**                                                | **校验下Tag在指定的Tag集合里(模糊匹配 可以用子级Tag匹配父级Tag 但反过来就不行)**                 |                                                                 |
| **MatchesAnyExact**                                           | **校验下Tag在指定的Tag集合里(精确匹配 需要两个Tag完全一致 ==)**                          |
| **MatchesTagDepth**                                           | **查看两个Tag的匹配度(有几个层级是相同的) 值越高表示匹配的层级越**                             |
| **GetSingleTagContainer**                                     | **获取一个包含该Tag和其所有父级Tag的Tag容器FGameplayTagContainer**                 |
| **RequestDirectParent**                                       | **获取该Tag的直接父级(Tag x.y 返回 x )**                                     |
| **GetGameplayTagParents**                                     | **获取该Tag的所有父级Tag集合(包括本身) 都放在FGameplayTagContainer的GameplayTags数组** |