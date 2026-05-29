> 💡 **本系列文章基于UE5.3**

# 概述

---

Tag在运行时会构建成一个树状结构，如下图所示，每个Tag都可以在构建的Tag树中找到对应的叶子节点存放，同时也可以追溯叶子结点的父节点。

![Untitled](http://pic.xyyxr.cn/20260504111208942.png)

**GameplayTagsManager** 是一个全局唯一管理器(单例模式)，负责在启动时**收集所有Tag配置，构建Tag的树状结构(Tag树)**。维护通过各种途径配置的Tag。

```cpp
FORCEINLINE static UGameplayTagsManager& Get()
{
	if (SingletonManager == nullptr)
	{
		InitializeManager();
	}
	return *SingletonManager;
}

void UGameplayTagsManager::InitializeManager()
{
	check(!SingletonManager);
	SingletonManager = NewObject<UGameplayTagsManager>(GetTransientPackage(), NAME_None);
	SingletonManager->AddToRoot();
}

void FGameplayTagsModule::StartupModule()
{
	UGameplayTagsManager::Get();
}
```

**在初始化GameplayTagsManager 和Tag发生变动(增、删、改)都会触发Tag树的构建**

![Untitled](http://pic.xyyxr.cn/20260504111208943.png)

# 前置知识点

---

梳理Tag的收集和构建之前先了解下涉及的概念和数据结构

## 默认Tag配置类(**UGameplayTagsSettings**)

---

**UGameplayTagsSettings**是Tag的配置类，对应DefaultGameplayTags.ini 可以在**项目设置(ProjectSetting)的GameplayTags页面**进行配置。(Tag的配置DataTable引用就是在这里配置的)。

![Untitled](http://pic.xyyxr.cn/20260504111207012.png)

**对应的ini的文件(DefaultGameplayTags.ini)**

![Untitled](http://pic.xyyxr.cn/20260504111207013.png)

主要配置配置有:

- **Tag配置列表(GameplayTagList)**
- **配置Tag的DataTable路径引用(GameplayTagTableList)**
- **Tag的重命名配置(GameplayTagRedirects)**
- **受限Tag的配置信息列表*(主要有配置文件名和权限拥有者名字信息)***

```cpp
class UGameplayTagsSettings : public UGameplayTagsList
{
	
	**//Tag配置列表**
	TArray<FGameplayTagTableRow> GameplayTagList;
	
	**//Tag配置的DataTable路径引用**
	TArray<FSoftObjectPath> GameplayTagTableList;
	
	**//Tag的重命名配置**
	TArray<FGameplayTagRedirect> GameplayTagRedirects;
	
	**//受限Tag的配置信息列表**
	TArray<FRestrictedConfigInfo> RestrictedConfigFiles;
}
```

## 受限Tag(RestrictedTag)

---

受限Tag与普通Tag的区别在于增加了Tag编辑权限拥有者概念**。**比如部分Tag不想被其他人随意编辑，则在编辑器编辑修改此类Tag时会弹出一个提示，询问是否征求了权限拥有者的允许。

> 💡 *比较简陋的权限管理，实际上只是在编辑器编辑时多了一个提醒，直接修改ini文件或者无视提醒也可以直接编辑*
>
> *这里的拥有者名字匹配的是当前系统的用户名*

> 💡 *受限Tag配置需要指定哪些ini文件配置的Tag为受限Tag，配置在这些文件的所有Tag都是受限Tag。
>
> 每个文件可以指定一个拥有者*

> 💡 **5.3好像这个功能直接被干废了  无法配置受限Tag**

**受限Tag的编辑校验**

```cpp
void SAddNewRestrictedGameplayTagWidget::ValidateNewRestrictedTag()
{
...
	if (bHasOwner)
	{
		bool bRequiresPermission = true;
		**//匹配系统当前用户名**
		const FString& UserName = FPlatformProcess::UserName();
		for (const FString& Owner : TagSourceOwners)
		{
			if (Owner.Equals(UserName))
			{
				CreateNewRestrictedGameplayTag();
				bRequiresPermission = false;
			}
		}

		**//没有权限 弹出个提示**
		if (bRequiresPermission)
		{
			FString StringToDisplay = TEXT("Do you have permission from ");
			StringToDisplay.Append(TagSourceOwners[0]);
			for (int Idx = 1; Idx < TagSourceOwners.Num(); ++Idx)
			{
				StringToDisplay.Append(TEXT(" or "));
				StringToDisplay.Append(TagSourceOwners[Idx]);
			}
			StringToDisplay.Append(TEXT(" to modify "));
			StringToDisplay.Append(TagSource.ToString());
			StringToDisplay.Append(TEXT("?"));

			FNotificationInfo Info(FText::FromString(StringToDisplay));
			Info.ExpireDuration = 10.f;
			Info.ButtonDetails.Add(...);
			Info.ButtonDetails.Add(...);

			AddRestrictedGameplayTagDialog = FSlateNotificationManager::Get().AddNotification()
		}
	}
...
}

```

## Tag配置来源(**TagSources**)

---

Tag可能配置在**ini文件**或者**DataTable**或者**C++代码**中，在构建Tag之前会先从上述地方收集Tag的配置信息并按来源分类缓存起来，可以查询到每个Tag是从哪里配置的或者添加Tags时指定Tag添加到哪个配置来源。(在Tag管理界面等编辑Tag的地方需要用到这些数据)

每个配置Tag的ini文件、每个配置Tag的DataTable、C++代码中每个添加的NativeTag的模块或者插件都对应一个配置来源(**TagSource**)

**GameplayTagsManager**的变量**TagSources**缓存了所有Tag配置来源。Map的Key是SourceName表示配置来源文件名或者模块(插件)名。

```cpp
TMap<FName, FGameplayTagSource> TagSources;
```

![Untitled](http://pic.xyyxr.cn/20260504111208944.png)

```cpp
GAMEPLAYTAGS_API const FGameplayTagSource* FindTagSource(...) const;
GAMEPLAYTAGS_API FGameplayTagSource* FindTagSource(...);
GAMEPLAYTAGS_API void FindTagSourcesWithType(...) const;
GAMEPLAYTAGS_API void FindTagsWithSource(...) const;
```

**EGameplayTagSourceType Tag来源类型**

- **Native：***C++ 代码中添加的Tag*
- **DefaultTagList：***DefaultGameplayTags.ini文件添加的Tag*
- **TagList：***Tags目录的ini文件添加的Tag*
- **RestrictedTagList：***受限Tag(RestrictedTag)ini文件添加的Tag*
- **DataTable：***DataTable添加的Tag*

> 💡 在Content/Config目录或者插件的Config目录下可以新增一个Tags目录 用于放置配置Tag的ini文件，插件(Plugins)就可以通过这种方式添加专属于插件的tag配置ini文件。

```cpp
enum class EGameplayTagSourceType : uint8
{
	Native,				//  C++ 代码中添加的Tag
	DefaultTagList,	// DefaultGameplayTags.ini文件添加的Tag
	TagList,			//Tags目录的ini文件添加的Tag
	RestrictedTagList,	// 受限Tag(RestrictedTag)ini文件添加的Tag
	DataTable,			// DataTable中添加的Tag配置
};
```

**FGameplayTagSource 描述Tag配置列表**(包含一堆Tag)**的来源。**

> 💡
>
> 多个Tag来源(FGameplayTagSource)组合起来就是所有的Tag配置

- **SourceName：***配置来源文件名(**不带路径**)或者模块(插件)名*
- **SourceType：***Tag来源类型(代码中添加、ini配置、DataTable配置)*
- **SourceTagList：***Tag配置列表(非受限)*
- **SourceRestrictedTagList：***Tag配置列表(受限)*

![Untitled](http://pic.xyyxr.cn/20260504111208945.png)

```cpp
struct FGameplayTagSource
{
 //配置来源文件名(**不带路径**)或者模块(插件)名
	FName SourceName;

	//Tag来源类型
	EGameplayTagSourceType SourceType;

	//Tag配置列表(非受限)
	TObjectPtr<class UGameplayTagsList> SourceTagList;

	**//**Tag配置列表(受限)
	TObjectPtr<class URestrictedGameplayTagsList> SourceRestrictedTagList;
}
```

**添加Tag来源**

---

添加Tag配置时会将其添加到对应的Tag来源(**FGameplayTagSource**)的配置列表(**UGameplayTagsList或者URestrictedGameplayTagsList**)中。如果对应的来源对象尚未创建则触发下创建，创建时会记录来源的名字并创建对应的配置列表对象。

- **创建C++代码中添加的Tag(NativeTag)配置来源**
    
```cpp
    **//**SourceType是 EGameplayTagSourceType::Native
    //SourceName是模块(插件)名
    void UGameplayTagsManager::AddNativeGameplayTag(FNativeGameplayTag* TagSource)
    {
    	//进行Tag收集并缓存到**TagSources**
    	const FGameplayTagSource* NativeSource = 
    	FindOrAddTagSource(TagSource->GetModuleName(), EGameplayTagSourceType::Native);
    
    }
    
    FGameplayTagSource* UGameplayTagsManager::FindOrAddTagSource(...)
    {
    ...
    FGameplayTagSource* NewSource = &TagSources.Add(..));
    
    if (SourceType == EGameplayTagSourceType::Native)
    {
    	**//创建配置列表对象**
    	 NewSource->SourceTagList = 
    	 NewObject<UGameplayTagsList>(this, TagSourceName, RF_Transient);
    }
    ...
    }
```
    
> [!note]- **创建ini文件的添加的Tag配置来源**
> **DefaultTagList(***来自DefaultGameplayTags.ini***)、TagList**(*来自除DefaultGameplayTags.ini之外的配置非受限的ini文件*)、**RestrictedTagList**(来自配置受限Tag的ini文件)这三种来源类型都是从配置文件ini读取的
>
> > 💡 *DefaultTagList类型的配置列表直接创建的时候直接填充
> >
> >     TagList类型和*RestrictedTagList类型配置列表*需要记录来源文件的路径信息*

```cpp
    **//**SourceType 可以是 
    //EGameplayTagSourceType::DefaultTagList
    //EGameplayTagSourceType::TagList 
    //EGameplayTagSourceType::RestrictedTagList
    //SourceName是文件名
    
    //EGameplayTagSourceType::DefaultTagList
    void UGameplayTagsManager::ConstructGameplayTagTree()
    {
    	FName TagSource = FGameplayTagSource::GetDefaultName();
    	
    	FGameplayTagSource* DefaultSource = 
    	FindOrAddTagSource(TagSource, EGameplayTagSourceType::DefaultTagList);
    }
    
    //EGameplayTagSourceType::TagList 
    virtual bool AddNewGameplayTagToINI(...) override
    {
    ...
    	const FName TagSource = FName(*FPaths::GetCleanFilename(IniFilePath));
    	
    	if (!TagSource)
    	{
    		TagSource = Manager.
    		FindOrAddTagSource(TagSourceName, EGameplayTagSourceType::TagList);
    	}
    ...
    }
    
    **//**EGameplayTagSourceType::RestrictedTagList
    void UGameplayTagsManager::AddRestrictedGameplayTagSource(const FString& FileName)
    {
    ...
    FName TagSource = FName(*FPaths::GetCleanFilename(FileName));
    
    FGameplayTagSource* FoundSource = 
    FindOrAddTagSource(TagSource, EGameplayTagSourceType::RestrictedTagList);
    ...
    }
```
    

```cpp
FGameplayTagSource* UGameplayTagsManager::FindOrAddTagSource(...)
{
...
	FGameplayTagSource* NewSource = &TagSources.Add(..));
	
	**//DefaultTagList类型的配置列表直接创建的时候直接填充**
	if (SourceType == EGameplayTagSourceType::DefaultTagList)
	{
		//创建配置列表对象
		NewSource->SourceTagList = GetMutableDefault<UGameplayTagsSettings>();
	}
	
	**//TagList类型 需要记录来源文件的路径信息**
	else if (SourceType == EGameplayTagSourceType::TagList)
	{
		 //创建配置列表对象
		NewSource->SourceTagList = NewObject<UGameplayTagsList>(this, TagSourceName, RF_Transient);
		
		//没指定根目录 则使用默认的根目录(Content/Config)
		if (RootDirToUse.IsEmpty())
		{
			NewSource->SourceTagList->ConfigFileName = FString::Printf(TEXT("%sTags/%s"), *FPaths::SourceConfigDir(), *TagSourceName.ToString());
		}
		else
		{
			//指定Tags的根目录(比如插件的目录) 
			NewSource->SourceTagList->ConfigFileName = RootDirToUse / *TagSourceName.ToString();
			RegisteredSearchPaths.FindOrAdd(RootDirToUse);
		}
		
	}
	
	**//RestrictedTagList类型 需要记录来源文件的路径信息**
	else if (SourceType == EGameplayTagSourceType::RestrictedTagList)
	{
		//创建配置列表对象
		NewSource->SourceRestrictedTagList = NewObject<URestrictedGameplayTagsList>(this, TagSourceName, RF_Transient);
		if (RootDirToUse.IsEmpty())
		{
			//没指定根目录 则使用默认的根目录(Content/Config)
			NewSource->SourceRestrictedTagList->ConfigFileName = FString::Printf(TEXT("%sTags/%s"), *FPaths::SourceConfigDir(), *TagSourceName.ToString());
		}
		else
		{			
				//指定Tags的根目录(比如插件的目录) 
			NewSource->SourceRestrictedTagList->ConfigFileName = RootDirToUse / *TagSourceName.ToString();
			RegisteredSearchPaths.FindOrAdd(RootDirToUse);
		}
		
	
...
}
```

> [!note]- **DataTable中添加的Tag配置**
> *来源是DataTable的，本身自带了配置列表数据(每行数据就一个*FGameplayTagTableRow对象*)，就不需要额外再创建配置列表(*UGameplayTagsList*)对象了*

```cpp
    
    **//**SourceType是 EGameplayTagSourceType::DataTable
    //SourceName是DataTable的资源名
    void UGameplayTagsManager::PopulateTreeFromDataTable(class UDataTable* InTable)
    {
    		FName SourceName = InTable->GetOutermost()->GetFName();
    		
    		FGameplayTagSource* FoundSource = 
    		FindOrAddTagSource(SourceName, EGameplayTagSourceType::DataTable);
    }
```
    

## Tag配置列表(GameplayTagsList)

---

每个Tag配置来源(**TagSource** *配置文件ini文件、配置DataTable、C++中添加的NativeTag*)都包含一个配置列表用于存放从配置来源添加的Tag配置信息。

- 一个Tag描述类(**FGameplayTagTableRow**)的对象数组。
- 一个字符串描述来源路径(*ini的文件路径*)。

![Untitled](http://pic.xyyxr.cn/20260504111208946.png)

```cpp
class UGameplayTagsList : public UObject
{
 //配置来源文件名(带完整路径)
 //或者模块(插件)名(对应在代码中添加的**NativeTag**配置)
	FString ConfigFileName;
	//Tag(非受限)配置列表
	TArray<FGameplayTagTableRow> GameplayTagList;
};

class URestrictedGameplayTagsList : public UObject
{
 //配置来源文件名(**带完整路径**)或者模块(插件)名(对应在代码中添加的**NativeTag**配置)
	FString ConfigFileName;
	
	**//Tag(受限)配置列表**
	TArray<FRestrictedGameplayTagTableRow> RestrictedGameplayTagList;
};

```

**UGameplayTagsList  Tag配置列表(非受限Tag)** 

**URestrictedGameplayTagsList  Tag配置列表(受限Tag)**

> 💡 *默认Tag配置类(**UGameplayTagsSettings**)也是一个Tag配置列表 其父类就是***UGameplayTagsList**

## Tag描述类(**FGameplayTagTableRow**)

---

**FGameplayTagTableRow**是单个Tag配置的描述类，每个Tag配置列表(GameplayTagsList)都维护了一个**FGameplayTagTableRow**的对象数组。

- **Tag的命名(FName** *比如”Enemy.Boss.Dragon”*)
- **Tag的说明**(**FString DevComment** *编辑器有效*)

```cpp
struct FGameplayTagTableRow : public FTableRowBase
{
	FName Tag;
	FString DevComment;
};
```

# **收集Tag配置构建Tag树**

---

在**启动或者编辑Tag**时通过**ConstructGameplayTagTree**先收集所有配置Tag的来源，构建Tag(来源)实例。

- 每个来源实例中都包含了**Tag来源(FGameplayTagSource)实例**
- 来源(FGameplayTagSource)实例中包含了**Tag列表(UGameplayTagsList)实例**
- Tag列表(UGameplayTagsList)实例中包含多个**Tag描述(FGameplayTagTableRow)实例**

然后调用**AddTagTableRow**为每个Tag在Tag树查找对应的位置构建叶子节点，最终将所有Tag节点构建成一颗Tag树。每个Tag树的叶子节点都包含了归属Tag信息及其所有父层级的Tag信息。

![Untitled](http://pic.xyyxr.cn/20260504111208942.png)

## **NativeTag的收集与构建**

---

**UE提供了可以直接使用的 NativeGameplayTag注册宏**

```cpp
//导出Tag全局变量(为了是变量可以被外部引用)
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

**NativeGameplayTag注册宏** 代码示例

```cpp
//.h文件(如果变量可以被外部引用 不需要被外部引用则无需添加)
UE_DECLARE_GAMEPLAY_TAG_EXTERN(TAG_Gameplay_Damage);
UE_DECLARE_GAMEPLAY_TAG_EXTERN(TAG_Gameplay_DamageImmunity);

//cpp文件
UE_DEFINE_GAMEPLAY_TAG(TAG_Gameplay_Damage, "Gameplay.Damage");
UE_DEFINE_GAMEPLAY_TAG(TAG_Gameplay_DamageImmunity, "Gameplay.DamageImmunity");
```

在cpp文件中通过注册宏会**定义一个全局的FNativeGameplayTag对象**，触发其构造函数时，会触发Tag的添加逻辑。

FNativeGameplayTag添加Tag有两种情况:

1. 触发时**GameplayTagsManager已创建**，通过**GameplayTagsManager**的**AddNativeGameplayTag**函数来进行Tag的添加。
2. 触发时**GameplayTagsManager**尚未创建，则会先放入一个静态列表**RegisteredNativeTags**中，再在**GameplayTagsManager**创建时通过**ConstructGameplayTagTree**触发Tag的添加。

> 💡 *方式2好像只会触发Tag叶子节点的构建不会触发Tag来源的收集，应该是历史遗留代码。
>
> 一般来说Gameplay模块加载时***GameplayTagsManager***已经创建了，所以通过宏添加的Tag是走的的方式1*

> 💡 *FNativeGameplayTag重载的操作符 支持FNativeGameplayTag到**FGameplayTag 的隐式转换**
>
> 所以通过宏构建的FNativeGameplayTag对象**可以直接当FGameplayTag的对象使用***

```cpp
FNativeGameplayTag::FNativeGameplayTag(...)
{
...
	GetRegisteredNativeTags().Add(this);
	if (UGameplayTagsManager* Manager = UGameplayTagsManager::GetIfAllocated())
	{
		Manager->AddNativeGameplayTag(this);
	}
...
}

//FNativeGameplayTag重载的操作符 支持FNativeGameplayTag到**FGameplayTag** 的隐式转换
operator FGameplayTag() const { return InternalTag; }

//NativeGameplayTag添加Tag 方式1
void UGameplayTagsManager::AddNativeGameplayTag(FNativeGameplayTag* TagSource)
{
	//**进行Tag收集并缓存到TagSources的配置列表中**
	const FGameplayTagSource* NativeSource = 
	FindOrAddTagSource(TagSource->GetModuleName(), EGameplayTagSourceType::Native);
	
	NativeSource->SourceTagList->GameplayTagList.Add(TagSource->GetGameplayTagTableRow());
	
	**//在Tag树上构建叶子节点**
	AddTagTableRow(TagSource->GetGameplayTagTableRow(), NativeSource->SourceName);
	
}

//NativeGameplayTag添加Tag 方式2
void UGameplayTagsManager::ConstructGameplayTagTree()
{
...
for (const class FNativeGameplayTag* NativeTag : FNativeGameplayTag::GetRegisteredNativeTags())
{
	**//在Tag树上构建叶子节点**
	AddTagTableRow(NativeTag->GetGameplayTagTableRow(), NativeTag->GetModuleName());
}
...
}

```

## ini文件配置Tag的收集与构建

---

来源于ini文件配置Tag，每个配置文件都会对应一个配置列表类(**UGameplayTagsList**)的对象。在收集时就是将ini文件的配置加载到配置列表类(**UGameplayTagsList**)的对象中。

### DefaultTagList类型

---

**DefaultTagList**类型对应的ini文件是DefaultGameplayTags.ini。在**ConstructGameplayTagTree**函数中直接读取DefaultGameplayTags.ini进行收集,**加载数据到UGameplayTagsSettings的对象**。尝试创建下DefaultTagList的来源(**FGameplayTagSource**)的对象(有就不需要再创建)，创建的来源对象时会**直接将来源对象的配置列表绑定为UGameplayTagsSettings的对象**。这样来源对象的配置列表直接就是加载好的**UGameplayTagsSettings对象**

```cpp
void UGameplayTagsManager::ConstructGameplayTagTree()
{
...
	**//从DefaultGameplayTags.ini加载数据到UGameplayTagsSettings的对象**
	GConfig->GetArray(TEXT("/Script/GameplayTags.GameplayTagsSettings"), TEXT("+GameplayTags"), EngineConfigTags, MutableDefault->GetDefaultConfigFilename());

	for (const FString& EngineConfigTag : EngineConfigTags)
	{
		MutableDefault->GameplayTagList.AddUnique(FGameplayTagTableRow(FName(*EngineConfigTag)));
	}

#if WITH_EDITOR
	MutableDefault->SortTags();
#endif

	//**这里尝试创建下DefaultTagList的来源对象(有就不需要再创建)**
	//**创建DefaultTagList的来源对象时
	//会直接将来源对象的配置列表绑定为UGameplayTagsSettings的对象**
	FName TagSource = FGameplayTagSource::GetDefaultName();
	FGameplayTagSource* DefaultSource = FindOrAddTagSource(TagSource, EGameplayTagSourceType::DefaultTagList);

	for (const FGameplayTagTableRow& TableRow : MutableDefault->GameplayTagList)
	{
		AddTagTableRow(TableRow, TagSource);
	}

...
}

FGameplayTagSource* UGameplayTagsManager::FindOrAddTagSource(...)
{
...
	FGameplayTagSource* NewSource = &TagSources.Add(..));
	
	**//DefaultTagList类型的配置列表直接创建的时候直接填充**
	if (SourceType == EGameplayTagSourceType::DefaultTagList)
	{
		//创建配置列表对象
		NewSource->SourceTagList = GetMutableDefault<UGameplayTagsSettings>();
	}
}
```

### TagList类型

---

**TagList**类型对应的ini文件都是除DefaultGameplayTags.ini之外配置在Tags目录的配置ini文件，可以是Content/Config目录下创建的Tags目录，也可以是其他目录(比如插件目录)下创建的Tags目录。

在**ConstructGameplayTagTree**函数中先尝试在Content/Config目录下创建的Tags目录查找配置的ini文件，然后再在其他目录下(**RegisteredSearchPaths**)的Tags目录尝试查找配置的ini文件。

```cpp
void UGameplayTagsManager::ConstructGameplayTagTree()
{
...
FString DefaultPath = FPaths::ProjectConfigDir() / TEXT("Tags");
AddTagIniSearchPath(DefaultPath);

// Refresh any other search paths that need it
for (TPair<FString, FGameplayTagSearchPathInfo>& Pair : **RegisteredSearchPaths**)
{
	if (!Pair.Value.IsValid())
	{
		AddTagIniSearchPath(Pair.Key);
	}
}
			...
}
```

**RegisteredSearchPaths**存放了其他配置Tag的配置文件信息路径信息(*比如插件里面有配置Tag的ini文件*)，用于加载Tag配置文件时知道去那个路径下搜索。

![Untitled](http://pic.xyyxr.cn/20260504111208947.png)

在插件里可以通过如下代码往GameplayTagsManager的**RegisteredSearchPaths**添加Tag配置路径信息

```cpp
void FGameSubtitlesModule::StartupModule()
{
	UGameplayTagsManager::Get().AddTagIniSearchPath(FPaths::ProjectPluginsDir() / TEXT("GameSubtitles/Config/Tags"));
}

//GameFeature相关插件 统一注册Tag配置目录的地方
struct FGameFeaturePluginState_Registering : public FGameFeaturePluginState
{
	virtual void UpdateState(FGameFeaturePluginStateStatus& StateStatus) override
	{
		const FString PluginFolder = FPaths::GetPath(StateProperties.PluginInstalledFilename);
		UGameplayTagsManager::Get().AddTagIniSearchPath(PluginFolder / TEXT("Config") / TEXT("Tags"));
	}
}
```

**AddTagIniSearchPath**函数负责在指定的目录下搜寻ini文件并**将收集到的ini加载到配置来源(FGameplayTagSource)对象的配置列表中**，**并为每个Tag在Tag树中对应的位置创建叶子节点**(*如果指定的目录尚未加入到**RegisteredSearchPaths**此时会加进去，参照上面**RegisteredSearchPaths**的说明*)

```cpp
void UGameplayTagsManager::AddTagIniSearchPath(const FString& RootDir)
{
...

	FGameplayTagSearchPathInfo* PathInfo = RegisteredSearchPaths.Find(RootDir);

	if (!PathInfo)
	{
	//*如果指定的目录尚未加入到**RegisteredSearchPaths** 加进去*
		PathInfo = &RegisteredSearchPaths.FindOrAdd(RootDir);
	}
	

	**//搜寻目录下所有配置ini文件**(如果标记成搜索过的目录 不会重复搜索)
	if (!PathInfo->bWasSearched)
	{
		PathInfo->Reset();
		....
		TArray<FString> FilesInDirectory;
		IFileManager::Get().FindFilesRecursive(FilesInDirectory, *RootDir, TEXT("*.ini"), true, false);
		...
		PathInfo->bWasSearched = true;
	}
		
	//**将收集到的ini加载到配置来源(FGameplayTagSource)对象的配置列表中**，
	//**并为每个Tag在Tag树中对应的位置创建叶子节点**(标记处理过的不会重复处理)
	if (!PathInfo->bWasAddedToTree)
	{
		//ini文件可以配置 受限tag配置文件的路径 如果配置了 这里处理下
		//**GetRestrictedConfigsFromIni/AddRestrictedGameplayTagSource**
		for (const FString& IniFilePath : PathInfo->TagIniList)
		{
			TArray<FRestrictedConfigInfo> IniRestrictedConfigs;
			GameplayTagUtil::GetRestrictedConfigsFromIni(IniFilePath, IniRestrictedConfigs);
			const FString IniDirectory = FPaths::GetPath(IniFilePath);
			for (const FRestrictedConfigInfo& Config : IniRestrictedConfigs)
			{
				const FString RestrictedFileName = FString::Printf(TEXT("%s/%s"), *IniDirectory, *Config.RestrictedConfigName);
				AddRestrictedGameplayTagSource(RestrictedFileName);
			}
		**}

		//这里是实际处理的地方
		AddTagsFromAdditionalLooseIniFiles(PathInfo->TagIniList);

		PathInfo->bWasAddedToTree = true;

		HandleGameplayTagTreeChanged(false);
	}
		
...
}

void UGameplayTagsManager::AddTagsFromAdditionalLooseIniFiles(const TArray<FString>& IniFileList)
{
...
	for (const FString& IniFilePath : IniFileList)
	{
	...
		const FName TagSource = FName(*FPaths::GetCleanFilename(IniFilePath));

		**// 跳过配置受限Tag的ini文件 这些文件在另外一个地方处理**
		if (RestrictedGameplayTagSourceNames.Contains(TagSource))
		{
			continue;
		}

		**// 加载ini文件并将数据放到来源(**FGameplayTagSource**)对象的配置列表中**
		FGameplayTagSource* FoundSource = FindOrAddTagSource(TagSource, EGameplayTagSourceType::TagList);
		
		if (FoundSource && FoundSource->SourceTagList)
		{
			FoundSource->SourceTagList->ConfigFileName = IniFilePath;
			
			//加载ini中的Tag 填充到Tag列表实例SourceTagList中
			FoundSource->SourceTagList->LoadConfig(UGameplayTagsList::StaticClass(),*IniFileP);

			**//为配置列表中的每个Tag创建叶子节点**
			for (const FGameplayTagTableRow& TableRow : FoundSource->SourceTagList->GameplayTagList)
			{
				AddTagTableRow(TableRow, TagSource);
			}
	...
	}
...
}
```

### RestrictedTagList类型

---

**RestrictedTagList**类型与**TagList**类型类似,区别在于配置**RestrictedTagList**类型(受限Tag)的ini文件路径需要在别的ini文件中指定，配置字段**RestrictedConfigFiles**(*比如DefaultGameplayTags.ini 也可以是其他有配置字段RestrictedConfigFiles的ini文件*)

**GameplayTagUtil::GetRestrictedConfigsFromIni**函数负责在指定的ini文件收集**RestrictedTagList**类型的ini文件配置路径信息

![Untitled](http://pic.xyyxr.cn/20260504111208948.png)

```cpp
namespace GameplayTagUtil
{
	static void GetRestrictedConfigsFromIni(...)
		{
			FConfigFile ConfigFile;
			ConfigFile.Read(IniFilePath);
	
			TArray<FString> IniConfigStrings;
			if (ConfigFile.GetArray(TEXT("/Script/GameplayTags.GameplayTagsSettings"), 
			TEXT("RestrictedConfigFiles"), IniConfigStrings))
			{
				for (const FString& ConfigString : IniConfigStrings)
				{
					FRestrictedConfigInfo Config;
					if (FRestrictedConfigInfo::StaticStruct()->ImportText(*ConfigString, &Config, 
					nullptr, PPF_None, nullptr, FRestrictedConfigInfo::StaticStruct()->GetName()))
					{
						OutRestrictedConfigs.Add(Config);
					}
				}
			}
		}
}
```

在**ConstructGameplayTagTree**函数中先通过**GetRestrictedConfigsFromIni**查找配置受限Tag的ini文件
，在通过AddRestrictedGameplayTagSource**将收集到的ini加载到配置来源(FGameplayTagSource)对象的配置列表中**，**并为每个Tag在Tag树中对应的位置创建叶子节点**

```cpp
void UGameplayTagsManager::ConstructGameplayTagTree()
{
...
TArray<FString> RestrictedGameplayTagFiles;
GetRestrictedTagConfigFiles(RestrictedGameplayTagFiles);
RestrictedGameplayTagFiles.Sort();

for (const FString& FileName : RestrictedGameplayTagFiles)
{
	AddRestrictedGameplayTagSource(FileName);
}
...
}
```

**GetRestrictedConfigsFromIni**先在**DefaultGameplayTags.ini**配置文件收集配置受限Tag的ini路径信息，再在**RegisteredSearchPaths**中的ini文件收集配置受限Tag的ini路径信息

```cpp
void UGameplayTagsManager::GetRestrictedTagConfigFiles(TArray<FString>& RestrictedConfigFiles) const
{
	UGameplayTagsSettings* MutableDefault = GetMutableDefault<UGameplayTagsSettings>();

**//在DefaultGameplayTags.ini配置文件收集配置受限Tag的ini路径信息**
	if (MutableDefault)
	{
		for (const FRestrictedConfigInfo& Config : MutableDefault->RestrictedConfigFiles)
		{
			RestrictedConfigFiles.Add(FString::Printf(TEXT("%sTags/%s"), *FPaths::SourceConfigDir(), *Config.RestrictedConfigName));
		}
	}

//在**RegisteredSearchPaths**中的ini文件收集配置受限Tag的ini路径信息
	for (const TPair<FString, FGameplayTagSearchPathInfo>& Pair : RegisteredSearchPaths)
	{
		for (const FString& IniFilePath : Pair.Value.TagIniList)
		{
			TArray<FRestrictedConfigInfo> IniRestrictedConfigs;
			GameplayTagUtil::GetRestrictedConfigsFromIni(IniFilePath, IniRestrictedConfigs);
			for (const FRestrictedConfigInfo& Config : IniRestrictedConfigs)
			{
				RestrictedConfigFiles.Add(FString::Printf(TEXT("%s/%s"), *FPaths::GetPath(IniFilePath), *Config.RestrictedConfigName));
			}
		}
	}
}
```

**AddRestrictedGameplayTagSource将收集到的ini加载到配置来源(FGameplayTagSource)对象的配置列表中**，**并为每个Tag在Tag树中对应的位置创建叶子节点**

```cpp
void UGameplayTagsManager::AddRestrictedGameplayTagSource(const FString& FileName)
{
	FName TagSource = FName(*FPaths::GetCleanFilename(FileName));
	if (TagSource == NAME_None)
	{
		return;
	}

	**//已经处理过的跳过**
	if (RestrictedGameplayTagSourceNames.Contains(TagSource))
	{
		return;
	}

	//**将收集到的ini加载到配置来源(FGameplayTagSource)对象的配置列表中**
	RestrictedGameplayTagSourceNames.Add(TagSource);
	FGameplayTagSource* FoundSource = 
	FindOrAddTagSource(TagSource, EGameplayTagSourceType::RestrictedTagList);

	if (FoundSource && FoundSource->SourceRestrictedTagList)
	{
		FoundSource->SourceRestrictedTagList->LoadConfig(URestrictedGameplayTagsList::StaticClass(), *FileName);

		//**为配置列表中的每个Tag在Tag树中对应的位置创建叶子节点**
		for (const FRestrictedGameplayTagTableRow& TableRow : FoundSource->SourceRestrictedTagList->RestrictedGameplayTagList)
		{
			AddTagTableRow(TableRow, TagSource, true);
		}
	}
}
```

## DataTable配置Tag的收集与构建

---

根据DefaultGameplayTags.ini配置的DataTable路径引用加载DataTable，放入GameplayTagsManager的**GameplayTagTables**中,然后将DataTable中配置的Tag进行收集构建。

![Untitled](http://pic.xyyxr.cn/20260504111210752.png)

```cpp
void UGameplayTagsManager::ConstructGameplayTagTree()
{
...
//加载DataTable
if (GameplayTagTables.Num() == 0)
{
	LoadGameplayTagTables(false);
}

//将DataTable中配置的Tag进行收集注册
{
for (UDataTable* DataTable : GameplayTagTables)
{
	if (DataTable)
	{
		PopulateTreeFromDataTable(DataTable);
	}
}
}
...
}
```

```cpp
void UGameplayTagsManager::PopulateTreeFromDataTable(class UDataTable* InTable)
{
...
	//DataTable本身数据就是一个Tag的配置列表
	//其来源数据中无需再设置配置列表数据
	FGameplayTagSource* FoundSource = FindOrAddTagSource(SourceName, 
	EGameplayTagSourceType::DataTable);

	//为DataTable中配置的每个Tag构建Tag叶子节点
	for (const FGameplayTagTableRow* TagRow : TagTableRows)
	{
		if (TagRow)
		{
			AddTagTableRow(*TagRow, SourceName);
		}
	}
...
}
```

## **构建Tag树**

---

在上一步收集好了所有的Tag后**，**会将所有收集的Tag构建成一个树状层级结构**(Tag树)**，为每个Tag分配一个树上的叶子节点**FGameplayTagNode**。

> 💡 **AddTagTableRow**将收集的Tag配置信息构建成**Tag的树状层级结构(Tag树)**。

> 💡
>
> 下图所示 分别是以下Tag 构建的树状结构
> *Ability.Dash
> Ability.Grenade
>
> InputTag.Ability.Dash
> InputTag.Weapon.Fire
> InputTag.Weapon.Reload*

![Untitled](http://pic.xyyxr.cn/20260504111207010.png)

### 定位在Tag树中的叶子节点位置

---

当新增一个Tag配置，先将Tag拆分层并组合出每一层的Tag名字，然后从Tag树的根节点开始一层层往下查找，为每一层的Tag找到其对应的叶子节点。未找到的则创建新的叶子节点。

- **将Tag拆分层并重新组合出每一层的Tag名字**
    
> 💡 *比如Tag Ability.Dash 
>     第一层的Tag名字是Ability
>     第二层的Tag名字是Ability.Dash*
    
- **在Tag树的对应层查找到Tag对应的叶子节点，直到最后一层Tag**
    
> 💡 *比如Ability.Dash 
>     需要在第一层为Ability定位叶子节点，在第二层为Ability.Dash定位叶子节点(这个Tag到第二层就结束了)
>
>     每次定位都是从Tag树的根节点往下查找,第一层的Tag的定位就是在根节点的叶子节点查找是否有对应的Tag，第二层的定位是在第一层找到的节点的叶子节点中查找，后面的依次递推。
>
>     查找定位过程中,如果未找到则为其创建一个新的叶子节点,并返回新创建节点索引，找到了就直接返回节点索引
>
>     拿到本层节点的索引后，在这个节点的叶子节点中继续查找 为下一层Tag定位*
    

```cpp
void UGameplayTagsManager::AddTagTableRow(...)
{
...
	**//将Tag拆分层 读取每一层的Tag名字**
	TArray<FString> SubTags;
	FullTagString.ParseIntoArray(SubTags, TEXT("."), true);
	
	for (int32 SubTagIdx = 0; SubTagIdx < NumSubTags; ++SubTagIdx)
	{
	
		**//重新组合每一层的Tag名字**
		bool bIsExplicitTag = (SubTagIdx == (NumSubTags - 1));
		FName ShortTagName = *SubTags[SubTagIdx];
		FName FullTagName;

		if (bIsExplicitTag)
		{
			//最后一层了
			FullTagName = OriginalTagName;
		}
		else if (SubTagIdx == 0)
		{
			//第一层
			FullTagName = ShortTagName;
			FullTagString = SubTags[SubTagIdx];
		}
		else
		{
			//中间的层
			FullTagString += TEXT(".");
			FullTagString += SubTags[SubTagIdx];

			FullTagName = FName(*FullTagString);
		}
		
		//**在当前层查找到Tag对应的叶子节点(未找到则为其创建一个新的叶子节点)**
	
		// 此处的**CurNode** 其实是当前节点的父节点(第一次循环 CurNode 是Root节点)
		TArray< TSharedPtr<FGameplayTagNode> >& ChildTags = 
		CurNode.Get()->GetChildTagNodes();
		
		
		//InsertTagIntoNodeArray 在当前层查找到Tag对应的叶子节点
		//未找到则为其创建一个新的叶子节点
		**//**并返回当前节点在父节点的ChildTags的索引
		int32 InsertionIdx = InsertTagIntoNodeArray(...);
	
		//获取当前Tag的节点 也是下一次循环的父节点
		CurNode = ChildTags[InsertionIdx];
	}
	
...
}
```

### 构建新的叶子节点

---

如果对应的Tag未在Tag树中查找其对应的Tag叶子节点，则需要为其创建一个新的叶子节点

- 新创建的Tag节点会加入其父节点的子节点列表(ChildTags)，并在新创建的节点设置其父节点引用。这样每个Tag节点都拥有了其归属的父节点和下属的子节点信息。
- 新创建的Tag节点加入Tag和TagNode的映射Map(**GameplayTagNodeMap**) 方便后续的查找

```cpp
TMap<FGameplayTag, TSharedPtr<FGameplayTagNode>> GameplayTagNodeMap**;**
```

```cpp
int32 UGameplayTagsManager::InsertTagIntoNodeArray(...)
{
...
if (FoundNodeIdx == INDEX_NONE)
	{
		if (WhereToInsert == INDEX_NONE)
		{
			// 插到最后
			WhereToInsert = NodeArray.Num();
		}

		**// 构建叶子节点 需要传入父节点信息(Root节点 是一个空节点)**
		TSharedPtr<FGameplayTagNode> TagNode = 
	MakeShareable(new FGameplayTagNode(Tag, FullTag, 
	ParentNode != GameplayRootTag ? ParentNode : nullptr,... ));

		**//将新创建的节点 加入父节点的子节点列表(ChildTags)**
		FoundNodeIdx = NodeArray.Insert(TagNode, WhereToInsert);

		FGameplayTag GameplayTag = TagNode->GetCompleteTag();

		{
			**//将新创建的节点 加入Tag和TagNode的映射Map 方便后续的查找
			//**TMap<FGameplayTag, TSharedPtr<FGameplayTagNode>> GameplayTagNodeMap**;**
			FScopeLock Lock(&GameplayTagMapCritical);
			GameplayTagNodeMap.Add(GameplayTag, TagNode);
		}
	}
	
	//返回查找到的节点索引
	return FoundNodeIdx;
...
}
```

**构建FGameplayTagNode**

---

**FGameplayTagNode**是Tag叶子节点的数据结构，存放了**当前Tag及Tag所有的父层级Tag(CompleteTagWithParents)**，还有**当前节点的子节点(ChildTags)**和**父节点信息(ParentNode)**。

```cpp
struct FGameplayTagNode
{
	//Node 归属的Tag名字
	FName Tag;

	//其包含了当前Node归属的Tag及该Tag所有的父层级Tag。
	FGameplayTagContainer CompleteTagWithParents;

	//所有的子节点
	TArray< TSharedPtr<FGameplayTagNode> > ChildTags;

	//父节点
	TSharedPtr<FGameplayTagNode> ParentNode;
}

struct FGameplayTagContainer
{
	UPROPERTY(VisibleAnywhere, BlueprintReadWrite, Category=GameplayTags, SaveGame)
	TArray<FGameplayTag> GameplayTags;

	UPROPERTY(Transient)
	TArray<FGameplayTag> ParentTags;
}
```

> 💡 **CompleteTagWithParents**是一个Tag集合容器(FGameplayTagContainer)
>
> 其包含了当前Node归属的Tag信息(**GameplayTags**)及该Tag所有的父层级Tag信息(**ParentTags**)。
>
> **GameplayTags**只存放该Node归属的Tag
>
> **ParentTags**存放该Node归属的Tag所有的父层级Tag信息。
>
> *比如一个**FGameplayTagNode**存放的Tag是”Enemy.Boss.Dragon”。则***CompleteTagWithParents**的**GameplayTags={”***Enemy.Boss.Dragon“}*
> **CompleteTagWithParents**的**ParentTags={“***Enemy***”,”***Enemy.Boss***”}**。

- 将当前Tag放入**CompleteTagWithParents**的**GameplayTags**
- 创建时会传入父节点信息，在节点中保留一份对父节点的指针(**ParentNode**)
- 获取父节点信息，将父节点的**CompleteTagWithParents**作为当前Tag的父层级Tag放入**ParentTags，**这样每个节点都保留了其所有的父层级Tag信息
- 当该节点作为父节点创建其叶子节点时，会将创建的叶子节点指针加到其子节点列表中(**ChildTags**)

```cpp
FGameplayTagNode::FGameplayTagNode(...)
	: Tag(InTag)
	, ParentNode(InParentNode)
	, NetIndex(INVALID_TAGNETINDEX)
{

 //将当前Tag放入FGameplayTagContainer的GameplayTags
	CompleteTagWithParents.GameplayTags.Add(FGameplayTag(InFullTag));

	//尝试获取父节点
	FGameplayTagNode* RawParentNode = ParentNode.Get();
	if (RawParentNode && RawParentNode->GetSimpleTagName() != NAME_None)
	{
		//获取父节点的CompleteTagWithParents
		const FGameplayTagContainer ParentContainer = RawParentNode->GetSingleTagContainer();

		//将父节点的CompleteTagWithParents全部放入当前Tag的FGameplayTagContainer的ParentTags
		//从树状结构的根节点往下一层层的构件节点 
		//每层都保留了其所有的父层级Tag信息
		//然后当前层记录的父层级Tag信息会在这里传递给其下一层的Tag
		//一层层继续下来 每个Tag的CompleteTagWithParents都包含了当前Tag及其所有父层级Tag
		CompleteTagWithParents.ParentTags.Add(ParentContainer.GameplayTags[0]);
		CompleteTagWithParents.ParentTags.Append(ParentContainer.ParentTags);
	}
}
```

## 在编辑器中添加&删除

---

除了在启动时收集构建Tag，还有在编辑器中删除或者添加Tag是也会触发Tag的收集与构建。

## 添加

---

**AddNewGameplayTagToINI**函数在编辑器触发添加Tag时触发

- 根据传入的来源名(TagSourceName)查找到来源(**FGameplayTagSource**)对象(*如果没有就新建*)
- 将Tag加到其配置列表中(*根据是否是受限Tag决定加到哪个配置列表*)
- 重新加载一下对应的ini文件(*ini文件已经被上一步修改过了*)
- **EditorRefreshGameplayTagTree**触发Tag树的重构(*删除之前的Tags树再重新创建一颗新的Tag树*)

```cpp
virtual bool AddNewGameplayTagToINI(...) override
{
...

**//根据传入的来源名(TagSourceName)查找到来源(FGameplayTagSource)对象(*如果没有就新建一个*)**
const FGameplayTagSource* TagSource = Manager.FindTagSource(TagSourceName);
if (!TagSource)
{
	// Create a new one
	TagSource = Manager.FindOrAddTagSource(TagSourceName, EGameplayTagSourceType::TagList);
}

if (TagSource)
{
...
**//将Tag加到其配置列表中(*根据是否是受限Tag决定加到哪个配置列表*)**
		if (bIsRestrictedTag && TagSource->SourceRestrictedTagList)
		{
			URestrictedGameplayTagsList* RestrictedTagList = TagSource->SourceRestrictedTagList;
			TagListObj = RestrictedTagList;
			RestrictedTagList->RestrictedGameplayTagList.AddUnique(...);
			RestrictedTagList->SortTags();
			ConfigFileName = RestrictedTagList->ConfigFileName;
			bSuccess = true;
		}
		else if (TagSource->SourceTagList)
		{
			UGameplayTagsList* TagList = TagSource->SourceTagList;
			TagListObj = TagList;
			TagList->GameplayTagList.AddUnique(FGameplayTagTableRow(FName(*NewTag), Comment));
			TagList->SortTags();
			ConfigFileName = TagList->ConfigFileName;
			bSuccess = true;
		}
		
		**//重新加载一下对应的ini文件**
		GConfig->LoadFile(ConfigFileName);
...
}

{
	**//触发Tag树的重构(*删除之前的Tags树再重新创建一颗新的Tag树*)**
	Manager.EditorRefreshGameplayTagTree();
}
...
}
```

```cpp
void UGameplayTagsManager::EditorRefreshGameplayTagTree()
{
	**// 所有的RegisteredSearchPaths都标记未搜寻过 需要重新搜寻**
	for (TPair<FString, FGameplayTagSearchPathInfo>& Pair : RegisteredSearchPaths)
	{
		Pair.Value.bWasSearched = false;
	}

	**//销毁之前的Tag树**
	DestroyGameplayTagTree();
	**//重建Tag树**
	LoadGameplayTagTables(false);
	ConstructGameplayTagTree();

	OnEditorRefreshGameplayTagTree.Broadcast();
}
```

## 删除

---

**DeleteTagFromINI**函数在编辑执行删除Tag操作时触发

- 根据传入的来源名(TagSourceName)查找到来源(**FGameplayTagSource**)对象
- 将Tag从其配置列表中移除
- 重新加载一下对应的ini文件(*ini文件已经被上一步修改过了*)
- **EditorRefreshGameplayTagTree**触发Tag树的重构(*删除之前的Tags树再重新创建一颗新的Tag树*)

```cpp
virtual bool DeleteTagFromINI(TSharedPtr<FGameplayTagNode> TagNodeToDelete) override
{
...

**//根据传入的来源名(TagSourceName)查找到来源(FGameplayTagSource)对象**
const FGameplayTagSource* TagSource = Manager.FindTagSource(TagSourceName);

**//将Tag从其配置列表中移除**
for (int32 i = 0; i < TagListSize; i++)
{
	bool bRemoved = false;
	if (bTagIsRestricted)
	{
		if (TagSource->SourceRestrictedTagList->RestrictedGameplayTagList[i].Tag == TagName)
		{
			TagSource->SourceRestrictedTagList->RestrictedGameplayTagList.RemoveAt(i);
			bRemoved = true;
		}
	}
	else
	{
		if (TagSource->SourceTagList->GameplayTagList[i].Tag == TagName)
		{
			TagSource->SourceTagList->GameplayTagList.RemoveAt(i);
			bRemoved = true;
		}
	}

	if (bRemoved)
	{
	...
		**//重新加载一下对应的ini文件**
		GConfig->LoadFile(ConfigFileName);
		
		**//触发Tag树的重构(*删除之前的Tags树再重新创建一颗新的Tag树*)**
		Manager.EditorRefreshGameplayTagTree();
	...
	}
...
}
```

> 💡
>
> **FRestrictedGameplayTagTableRow**受限Tag描述类。继承自**FGameplayTagTableRow**。

# Tag重命名

---