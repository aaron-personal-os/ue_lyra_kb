> 💡 **本系列文章基于UE5.3**

# 概述

---

**Tag**支持灵活而强大的查询匹配操作，通过一套**类似逻辑运算符(与、或、非)组成的表达式**机制，可以灵活定制各种查询条件，用来**查询指定的Tag集合(FGameplayTagContainer)是否满足筛选、限制条件(应该有哪些Tag、不能有哪些Tag)。**

> 💡 比如下图所示的配置: 转换成表达式
> (!HasTag(Tag1)) &&
> ( **(HasTag(Tag5)||(HasTag(Tag6)** ) && ( **(HasTag(Tag7)||(HasTag(Tag8))**  )&&
> ( HasTag(Tag2)|| HasTag(Tag3) || HasTag(Tag4) )
>
> 即匹配的Tag容器需要同时满足以下三个条件是: 
> 1.不能有Tag1
> 2.Tag5、Tag6 之中至少要有一个并且Tag7、Tag8 之中至少要有一个
> 3.Tag2、Tag3、Tag4 之中至少要有一个

![Untitled](http://pic.xyyxr.cn/20260504111210754.png)

**表达式支持多重嵌套，表达式内可以嵌套子表达式**

用一个树状结构来描述上面的表达式，解析表达式时采用**深度优先遍历**从根表达式(**RootExpression**)逐层递归解析

![Untitled](http://pic.xyyxr.cn/20260504111210755.png)

**FGameplayTagQuery**封装了对Tag集合(FGameplayTagContainer)的匹配操作。可以通过蓝图配置或者直接通过C++代码创建的表达式，为了更高效的存储和评估，在**FGameplayTagQuery**内部通过**Build**函数将配置好的表达式进行解析转换，复杂的多重嵌套表达式转化为一个**字节流(QueryTokenStream)+Tag集合(TagDictionary)**。

评估时通过**Matches**函数直接依次读取**FGameplayTagQuery对象的字节流(**QueryTokenStream**)，再结合Tag集合(**TagDictionary**)就可以进行评估计算**(*不用考虑各种括号和优先级*)

> 💡
>
> 解析表达式时采用深度优先遍历从根表达式(RootExpression)开始遍历，将表达式里用到Tag都放到Tag的集合数组TagDictionary，并将Tag在表达式的操作类型、表达式操作数数量、数组里的索引依次编译到字节流(QueryTokenStream)中。
>
> 评估时读取字节流，就可以知道本次读取的是什么类型的操作，要用到几个Tag参与运算，用到的Tag索引是什么。这样只要在评估时按顺序依次读取字节流，结合通过Tag索引在Tag数组找到对应的Tag,就可以顺利评估出结果。

```cpp
struct FGameplayTagQuery
{
//**字节流(QueryTokenStream)**
TArray<FGameplayTag> TagDictionary;

//**参与计算的Tag集合(TagDictionary)**
TArray<uint8> QueryTokenStream;

GAMEPLAYTAGS_API void Build(...);
GAMEPLAYTAGS_API bool Matches(FGameplayTagContainer const& Tags) const;
}
```

**表达式的操作类型说明**

| 类型 | 说明 | 示例 |
| --- | --- | --- |
| **AnyTagsMatch**  | **有一个Tag匹配即位真**

多个Tag的判定(**HasTag**)之间 做**或(||)**运算 **

**支持只配置一个Tag 则判定结果就是 HasTag(Tag1)  | ***HasTag(Tag1) || HasTag(Tag2) || HasTag(Tag3)***  |
| **AllTagsMatch** |  **所有Tag都匹配才为真**

多个Tag的判定(**HasTag**)之间 做**与**运算

支持只配置一个Tag 则判定结果就是 HasTag(Tag1 | ***HasTag(Tag1) && HasTag(Tag2) && HasTag(Tag3)***  |
| **NoTagsMatch**  | **没有能匹配的Tag才为真**

多个Tag的判定(HasTag)之间 先做**非(!)**运算再做**与(&&)**运算 

支持只配置一个Tag 则判定结果就是 !HasTag(Tag1) | ***!HasTag(Tag1) && !HasTag(Tag2) && !HasTag(Tag3)***   |
|  |  |  |
| **AnyExprMatch**  | **有一个子表达式结果为真即为真**

多个子表达式之间做**或(||)**运算 **

**支持只配置一个子表达式 则结果取决于该子表达式结果 | ***子表达式1 || 子表达式2 ||  子表达式3*** |
| **AllExprMatch**  |  **所有子表达式结果为真才为真**

多个子表达式之间做**与(&&)**运算 **

支持只配置一个子表达式 则结果取决于该子表达式结果 | ***子表达式1 || 子表达式2 || 子表达式3*** |
| **NoExprMatch** | **所有子表达式结果都为假才为真**

多个子表达式直接 先做**非(!)**运算再做**与(&&)**运算 

支持只配置一个子表达式 则判定结果取决于 该表达式的结果取反(**!子表达式**) | ***!子表达式1 && !表达式2 && !表达式3*** |

# 配置&构建

---

配置、构建Tag查询匹配操作的表达式有两种方式:

- **蓝图配置**
- **C++代码配置**

## 蓝图配置&构建

---

C++中定义一个FGameplayTagQuery的变量，设置成蓝图可以编辑或者直接在蓝图中创建的FGameplayTagQuery的变量。编辑该属性时可以直接**打开Tag查询的编辑界面，可以在里面配置查询的表达式**。

![Untitled](http://pic.xyyxr.cn/20260504111210756.png)

**GE的配置中很多地方用到了Tag的查询配置**

![Untitled](http://pic.xyyxr.cn/20260504111210757.png)

**配置完成后，BuildFromEditableQuery根据配置的表达式构建FGameplayTagQuery对象**

```cpp
void FGameplayTagQuery::BuildFromEditableQuery(UEditableGameplayTagQuery& EditableQuery)
{
	QueryTokenStream.Reset();
	TagDictionary.Reset();

	UserDescription = EditableQuery.UserDescription;

	
	QueryTokenStream.Add(EGameplayTagQueryStreamVersion::LatestVersion);
	EditableQuery.EmitTokens(QueryTokenStream, TagDictionary, &AutoDescription);
}
```

BuildFromEditableQuery根据配置的表达式构建FGameplayTagQuery对象会**序列化存储在蓝图中**，运行时可以直接**反序列化构建运行时的FGameplayTagQuery对象**进行匹配查询操作

**在表达式编辑界面编辑时，会触发SGameplayTagQueryWidget::SaveToTagQuery，在这里触发FGameplayTagQuery::BuildFromEditableQuery，再在SGameplayTagQueryEntryBox::OnQueriesCommitted完成对修改的序列化**

![Untitled](http://pic.xyyxr.cn/20260504111210758.png)

![Untitled](http://pic.xyyxr.cn/20260504111210759.png)

![Untitled](http://pic.xyyxr.cn/20260504111210760.png)

## 代码配置&构建

---

除了通过蓝图编辑匹配表达式，还可以在代码里直接创建匹配表达式

**FGameplayTagQueryExpression**是描述表达式的类，提供各种操作类型的表达式的创建接口(**链式方法**)，**先构建一个表达式对象，再设置表达式的运算符(操作类型)和操作数(Tag集合或者子表达式集合)

BuildQuery接口再根据创建的表达式构建FGameplayTagQuery对象**

- **表达式创建示例代码**
    
```cpp
    //等同于
    //(HasTag("TestTag1")&&HasTag("TestTag2")) && (HasTag("TestTag3") || HasTag("TestTag4"))
    
    FGameplayTagQueryExpression TestExpression=FGameplayTagQueryExpression().AllExprMatch().
    AddExpr(FGameplayTagQueryExpression().AllTagsMatch()
    			   .AddTag("TestTag1")
    			   .AddTag("TestTag2")).
    AddExpr(FGameplayTagQueryExpression().AnyTagsMatch()
    				.AddTag("TestTag3")
    				.AddTag("TestTag4"));
    
    //**BuildQuery接口再根据创建的表达式构建FGameplayTagQuery对象**			
    FGameplayTagQuery TestQuery= FGameplayTagQuery::BuildQuery(TestQuery,TEXT("TestTags"));
```
    

- **设置表达式运算符(操作类型)**
    
```cpp
    **//设置表达式运算符(操作类型)**
    FGameplayTagQueryExpression& AnyTagsMatch()
    {
    	ExprType = EGameplayTagQueryExprType::AnyTagsMatch;
    	return *this;
    }
    
    FGameplayTagQueryExpression& AllTagsMatch()
    {
    	ExprType = EGameplayTagQueryExprType::AllTagsMatch;
    	return *this;
    }
    
    FGameplayTagQueryExpression& NoTagsMatch()
    {
    	ExprType = EGameplayTagQueryExprType::NoTagsMatch;
    	return *this;
    }
    
    FGameplayTagQueryExpression& AnyExprMatch()
    {
    	ExprType = EGameplayTagQueryExprType::AnyExprMatch;
    	return *this;
    }
    
    FGameplayTagQueryExpression& AllExprMatch()
    {
    	ExprType = EGameplayTagQueryExprType::AllExprMatch;
    	return *this;
    }
    
    FGameplayTagQueryExpression& NoExprMatch()
    {
    	ExprType = EGameplayTagQueryExprType::NoExprMatch;
    	return *this;
    }
```
    

- **设置表达式操作数(Tag集合或者子表达式集合)**
    
```cpp
    **//设置表达式运算符(操作类型)**
    FGameplayTagQueryExpression& AddTag(TCHAR const* TagString)
    {
    	return AddTag(FName(TagString));
    }
    
    FGameplayTagQueryExpression& AddTag(FGameplayTag Tag)
    {
    	ensure(UsesTagSet());
    	TagSet.Add(Tag);
    	return *this;
    }
    
    FGameplayTagQueryExpression& AddTags(FGameplayTagContainer const& Tags)
    {
    	ensure(UsesTagSet());
    	TagSet.Append(Tags.GameplayTags);
    	return *this;
    }
    
    FGameplayTagQueryExpression& AddExpr(FGameplayTagQueryExpression& Expr)
    {
    	ensure(UsesExprSet());
    	ExprSet.Add(Expr);
    	return *this;
    }
```
    

- **BuildQuery根据创建的表达式构建FGameplayTagQuery对象**
    
```cpp
    FGameplayTagQuery FGameplayTagQuery::BuildQuery(...)
    {
    	FGameplayTagQuery Q;
    	Q.Build(RootQueryExpr, InDescription);
    	return Q;
    }
```
    

- **还提供了一些快速创建简单查询(FGameplayTagQuery)对象的接口**
    
```cpp
    struct FGameplayTagQuery
    {
    //容器里的Tag 做|| 运算 HasTag(Tag1)||HasTag(Tag2)...
    static GAMEPLAYTAGS_API FGameplayTagQuery MakeQuery_MatchAnyTags(FGameplayTagContainer const& InTags);
    
    //容器里的Tag 做&& 运算 !HasTag(Tag1)&&!HasTag(Tag2)...
    static GAMEPLAYTAGS_API FGameplayTagQuery MakeQuery_MatchAllTags(FGameplayTagContainer const& InTags);
    
    //容器里的Tag 做! 运算 !HasTag(Tag1)&&!HasTag(Tag2)...
    static GAMEPLAYTAGS_API FGameplayTagQuery MakeQuery_MatchNoTags(FGameplayTagContainer const& InTags);
    
    //需要有指定的Tag
    static GAMEPLAYTAGS_API FGameplayTagQuery MakeQuery_MatchTag(FGameplayTag const& InTag);
    }
```
    

# 解析&评估

---

- FGameplayTagQuery的**Build**接口调用表达式对象的解析接口**EmitTokens**将配置的表达式转化为一个**字节流(**QueryTokenStream**)+Tag集合(**TagDictionary**)**
    
```cpp
    void FGameplayTagQuery::Build(...)
    {
    	TokenStreamVersion = EGameplayTagQueryStreamVersion::LatestVersion;
    	UserDescription = InUserDescription;
    
    	QueryTokenStream.Reset(128);
    	TagDictionary.Reset();
    
    	
    	QueryTokenStream.Add(EGameplayTagQueryStreamVersion::LatestVersion);
    
    	
    	QueryTokenStream.Add(1);		
    	RootQueryExpr.EmitTokens(QueryTokenStream, TagDictionary);
    }
    
```
    

- FGameplayTagQuery的**Matches**接口调用评估(**FQueryEvaluator** )对象的**Eval**接口执行评估操作
    
```cpp
    //根据编辑的表达式进行匹配评估
    bool FGameplayTagQuery::Matches(FGameplayTagContainer const& Tags) const
    {
    	if (IsEmpty())
    	{
    		return false;
    	}
    
    	FQueryEvaluator QE(*this);
    	return QE.Eval(Tags);
    }
```
    

## **解析表达式**

---

表达式是支持多重嵌套的，解析表达式时**采用深度优先遍历从根表达式(RootExpression)开始遍历**，**EmitTokens**接口将**表达式里用到Tag都放到Tag的集合数组TagDictionary**，并将**表达式的操作类型、表达式操作数数量、Tag在数组里的索引**编译到字节流(QueryTokenStream)

![Untitled](http://pic.xyyxr.cn/20260504111210755.png)

表达式分为两种类型:

1. 参与表达式计算的是**Tag集合(TagSet**)
    - 将用到Tag放入Tag数组TagDictionary(去重)
    - 将表达式操作类型、参与运算的Tag数量、Tag在TagDictionary的索引放入字节流(QueryTokenStream)
2. 参与表达式计算的是嵌套的**子表达式集合(ExprSet)**
    - 将表达式操作类型、参与运算的子表达式数量放入字节流(QueryTokenStream)
    - 通过树的深度优先遍历，递归解析直到表达式参与运算的是Tag

## C++代码创建的表达式解析

---

**FGameplayTagQueryExpression** 是描述直接通过C++代码创建的表达式的类(区别于通过蓝图配置的表达式)，数据结构如下，**内部实现了解析表达式解析接口EmitTokens**。

```cpp
struct FGameplayTagQueryExpression
{
	**//表达式操作类型**
	EGameplayTagQueryExprType ExprType;

	**//表达式参与运算的嵌套子表达式集合**
	TArray<struct FGameplayTagQueryExpression> ExprSet;

	**//表达式参与运算的Tag集合**
	TArray<FGameplayTag> TagSet;
}
```

- **ExprType：表达式运算符(表达式类型)**
- **ExprSet/TagSet：表达式的操作数**

**表达式参与运算的是Tag**

```cpp
void FGameplayTagQueryExpression::EmitTokens(...) const
{
	**//1.先将表达式的操作类型放入Token数组(字节流)**
	TokenStream.Add(static_cast<uint8>(ExprType));

	switch (ExprType)
	{
	case EGameplayTagQueryExprType::AnyTagsMatch:
	case EGameplayTagQueryExprType::AllTagsMatch:
	case EGameplayTagQueryExprType::NoTagsMatch:
	{

		//2.**将Tag表达式用到的Tag数量放入Token数组
		//有了数量评估表达式时才知道需要读取几个Tag参与运算**
		uint8 NumTags = (uint8)TagSet.Num();
		TokenStream.Add(NumTags);

		for (auto Tag : TagSet)
		{
			**//将用到Tag放入Tag数组**TagDictionary(去重)
			**int32 TagIdx = TagDictionary.AddUnique(Tag)**;
			check(TagIdx <= 254);	
			**//3.将Tag在TagDictionary的索引放入Token数组TokenStream**
			TokenStream.Add((uint8)TagIdx);
		}
		....
	}
	break;
}
```

**表达式参与运算的是嵌套的子表达式**

```cpp
void FGameplayTagQueryExpression::EmitTokens(...) const
{
	**//1.先将表达式的操作类型放入Token数组(字节流)**
	TokenStream.Add(static_cast<uint8>(ExprType));

	switch (ExprType)
	{
....
	case EGameplayTagQueryExprType::AnyExprMatch:
	case EGameplayTagQueryExprType::AllExprMatch:
	case EGameplayTagQueryExprType::NoExprMatch:
	{
	//2.**将Tag表达式用到的嵌套子表达式数量放入Token数组(字节流)
	//有了数量评估表达式时才知道需要读取几个嵌套子表达式参与运算**
		uint8 NumExprs = (uint8)ExprSet.Num();
		TokenStream.Add(NumExprs);

		for (auto& E : ExprSet)
		{
			**//递归解析直到表达式参与运算的是Tag(深度优先遍历)**
			E.EmitTokens(TokenStream, TagDictionary);
		}
	}
	break;
	default:
		break;
	}
}
```

## 蓝图配置的表达式解析

---

蓝图配置的表达式解析走的是另一套编辑器环境(WITH_EDITOR)的逻辑，核心逻辑相同。

为了便于编辑，创建了一套继承自UObject的表达式类，表达式基类**UEditableGameplayTagQueryExpression，**每种操作类型都有一个对应的表达式类

![Untitled](http://pic.xyyxr.cn/20260504111210761.png)

**表达式参与运算的是Tag**

```cpp
**//|| 运算**
void UEditableGameplayTagQueryExpression_AnyTagsMatch::EmitTokens(...) const
{
	**//1.先将表达式的操作类型放入Token数组(字节流)**
	TokenStream.Add((uint8)EGameplayTagQueryExprType::AnyTagsMatch);

	if (DebugString)
	{
		DebugString->Append(TEXT(" ANY("));
	}

	**//调用基类的接口统一处理**
	EmitTagTokens(Tags, TokenStream, TagDictionary, DebugString);

	if (DebugString)
	{
		DebugString->Append(TEXT(" )"));
	}
}

**//&& 运算**
void UEditableGameplayTagQueryExpression_AllTagsMatch::EmitTokens(...) const
{
	**//1.先将表达式的操作类型放入Token数组(字节流)**
	TokenStream.Add((uint8)EGameplayTagQueryExprType::AllTagsMatch);

	if (DebugString)
	{
		DebugString->Append(TEXT(" ALL("));
	}
	**//调用基类的接口统一处理**
	EmitTagTokens(Tags, TokenStream, TagDictionary, DebugString);

	if (DebugString)
	{
		DebugString->Append(TEXT(" )"));
	}
}

**//!运算**
void UEditableGameplayTagQueryExpression_NoTagsMatch::EmitTokens(..) const
{
	**//1.先将表达式的操作类型放入Token数组(字节流)**
	TokenStream.Add((uint8)EGameplayTagQueryExprType::NoTagsMatch);

	if (DebugString)
	{
		DebugString->Append(TEXT(" NONE("));
	}

	**//调用基类的接口统一处理**
	EmitTagTokens(Tags, TokenStream, TagDictionary, DebugString);

	if (DebugString)
	{
		DebugString->Append(TEXT(" )"));
	}
}
```

```cpp
void UEditableGameplayTagQueryExpression::EmitTagTokens(...) const
{
 **//2.将Tag表达式用到的Tag数量放入Token数组**
//有了数量评估表达式时才知道需要读取几个Tag参与运算
	uint8 const NumTags = (uint8)TagsToEmit.Num();
	TokenStream.Add(NumTags);

	bool bFirstTag = true;

	for (auto T : TagsToEmit)
	{
		**//将用到Tag放入Tag数组TagDictionary(去重)**
		int32 TagIdx = TagDictionary.AddUnique(T);
		check(TagIdx <= 255);
		
		**//3.将Tag在TagDictionary的索引放入Token数组TokenStream**
		TokenStream.Add((uint8)TagIdx);

		if (DebugString)
		{
			if (bFirstTag == false)
			{
				DebugString->Append(TEXT(","));
			}

			DebugString->Append(TEXT(" "));
			DebugString->Append(T.ToString());
		}

		bFirstTag = false;
	}
}

```

**表达式参与运算的是嵌套的子表达式**

```cpp
**//|| 运算**
void UEditableGameplayTagQueryExpression_AnyExprMatch::EmitTokens(...) const
{
	**//1.先将表达式的操作类型放入Token数组(字节流)**
	TokenStream.Add((uint8)EGameplayTagQueryExprType::AnyExprMatch);

	if (DebugString)
	{
		DebugString->Append(TEXT(" ANY("));
	}
	
	**//递归解析直到表达式参与运算的是Tag(深度优先遍历)**
	EmitExprListTokens(Expressions, TokenStream, TagDictionary, DebugString);

	if (DebugString)
	{
		DebugString->Append(TEXT(" )"));
	}
}

**//&& 运算**
void UEditableGameplayTagQueryExpression_AllExprMatch::EmitTokens(...) const
{
	**//1.先将表达式的操作类型放入Token数组(字节流)**
	TokenStream.Add((uint8)EGameplayTagQueryExprType::AllExprMatch);

	if (DebugString)
	{
		DebugString->Append(TEXT(" ALL("));
	}

	**//递归解析直到表达式参与运算的是Tag(深度优先遍历)**
	EmitExprListTokens(Expressions, TokenStream, TagDictionary, DebugString);

	if (DebugString)
	{
		DebugString->Append(TEXT(" )"));
	}
}

**//! 运算**
void UEditableGameplayTagQueryExpression_NoExprMatch::EmitTokens(...) const
{
	**//1.先将表达式的操作类型放入Token数组(字节流)**
	TokenStream.Add((uint8)EGameplayTagQueryExprType::NoExprMatch);

	if (DebugString)
	{
		DebugString->Append(TEXT(" NONE("));
	}

	**//递归解析直到表达式参与运算的是Tag(深度优先遍历)**
	EmitExprListTokens(Expressions, TokenStream, TagDictionary, DebugString);

	if (DebugString)
	{
		DebugString->Append(TEXT(" )"));
	}
}
```

```cpp
void UEditableGameplayTagQueryExpression::EmitExprListTokens(...) const
{
	//2.**将Tag表达式用到的嵌套子表达式数量放入Token数组(字节流)
	//有了数量评估表达式时才知道需要读取几个嵌套子表达式参与运算**
	uint8 const NumExprs = (uint8)ExprList.Num();
	TokenStream.Add(NumExprs);

	bool bFirstExpr = true;
	
	for (auto E : ExprList)
	{
		if (DebugString)
		{
			if (bFirstExpr == false)
			{
				DebugString->Append(TEXT(","));
			}

			DebugString->Append(TEXT(" "));
		}

		if (E)
		{
			**//调用各个表达式子类的EmitTokens
			E->EmitTokens(TokenStream, TagDictionary, DebugString);**
		}
		else
		{
			// null expression
			TokenStream.Add((uint8)EGameplayTagQueryExprType::Undefined);
			if (DebugString)
			{
				DebugString->Append(TEXT("undefined"));
			}
		}

		bFirstExpr = false;
	}
}

```

## 评估表达式

---

**FQueryEvaluator**负责表达式评估操作(即传入的Tag集合是否满足表达式配置的需求)，评估时，只要依次从字节流中读取Token，可以知道当前要用到哪个操作类型，有哪几个Tag或者子表达式参与计算。

如果参与计算的Tag，则继续读取Tag在**Tag集合(**TagDictionary**)**的索引，取出Tag计算结果

如果参与计算的是嵌套的子表达式，则递归继续往下一层走，直到表达式参与计算的是Tag(参照上面的树状图)。

```cpp
**//评估表达式 如果嵌套了表达式 则递归调用**
bool FQueryEvaluator::EvalExpr(FGameplayTagContainer const& Tags, bool bSkip)
{
	EGameplayTagQueryExprType const ExprType = (EGameplayTagQueryExprType) GetToken();
	if (bReadError)
	{
		return false;
	}

	switch (ExprType)
	{
	//
	case EGameplayTagQueryExprType::AnyTagsMatch:
		return EvalAnyTagsMatch(Tags, bSkip);
	case EGameplayTagQueryExprType::AllTagsMatch:
		return EvalAllTagsMatch(Tags, bSkip);
	case EGameplayTagQueryExprType::NoTagsMatch:
		return EvalNoTagsMatch(Tags, bSkip);

	case EGameplayTagQueryExprType::AnyExprMatch:
		return EvalAnyExprMatch(Tags, bSkip);
	case EGameplayTagQueryExprType::AllExprMatch:
		return EvalAllExprMatch(Tags, bSkip);
	case EGameplayTagQueryExprType::NoExprMatch:
		return EvalNoExprMatch(Tags, bSkip);
	}

	check(false);
	return false;
}
```

**表达式参与运算的是Tag，直接根据Tag计算出结果**

| 类型函数 | 说明 | 示例 |
| --- | --- | --- |
| **EvalAnyTagsMatch**  | **有一个Tag匹配即位真**

多个Tag的判定(**HasTag**)之间 做**或(||)**运算 **

**只配置一个Tag 则判定结果就是 HasTag(Tag1)  | ***HasTag(Tag1) || HasTag(Tag2) || HasTag(Tag3)***  |
| **EvalAllTagsMatch** |  **所有Tag都匹配才为真**

多个Tag的判定(**HasTag**)之间 做**与**运算

只配置一个Tag 则判定结果就是 HasTag(Tag1 | ***HasTag(Tag1) && HasTag(Tag2) && HasTag(Tag3)***  |
| **EvalNoTagsMatch**  | **没有能匹配的Tag才为真**

多个Tag的判定(HasTag)之间 先做**非(!)**运算再做**与(&&)**运算 

只配置一个Tag 则判定结果就是 !HasTag(Tag1) | ***!HasTag(Tag1) && !HasTag(Tag2) && !HasTag(Tag3)***   |

```cpp
//对应 或操作(||) 只要有一个Tag匹配即可匹配成功
bool FQueryEvaluator::EvalAnyTagsMatch(FGameplayTagContainer const& Tags, bool bSkip)
{
	bool bShortCircuit = bSkip;
	bool Result = false;
	
	// 1.解析 Tag数量
	int32 const NumTags = GetToken();
	if (bReadError)
	{
		return false;
	}
	
	
	for (int32 Idx = 0; Idx < NumTags; ++Idx)
	{
		int32 const TagIdx = GetToken();
		if (bReadError)
		{
			return false;
		}
		if (bShortCircuit == false)
		{
			//2. 根据Tag索引读取Tag
			FGameplayTag Tag = Query.GetTagFromIndex(TagIdx);

			bool bHasTag = Tags.HasTag(Tag);

			if (bHasTag)
			{
				//3. 有一个为真 即位真
				bShortCircuit = true; //后面不用再比了
				Result = true;
			}
		}

	return Result;
}

//对应 与操作(&&) 需要所有Tag都匹配才匹配成功
bool FQueryEvaluator::EvalAllTagsMatch(FGameplayTagContainer const& Tags, bool bSkip)
{
	bool bShortCircuit = bSkip;
	bool Result = true;
	
	//1. 解析 Tag数量
	int32 const NumTags = GetToken();
	if (bReadError)
	{
		return false;
	}
	
	for (int32 Idx = 0; Idx < NumTags; ++Idx)
	{
		int32 const TagIdx = GetToken();
		if (bReadError)
		{
			return false;
		}

		if (bShortCircuit == false)
		{
			//2. 根据Tag索引读取Tag
			FGameplayTag const Tag = Query.GetTagFromIndex(TagIdx);
			bool const bHasTag = Tags.HasTag(Tag);

			if (bHasTag == false)
			{
				// 3.有一个为假 则为假
				bShortCircuit = true;
				Result = false;
			}
		}
	}

	return Result;
}

//对应 非操作(!) 不能有匹配的Tag才匹配成功 有多个则 先**非(!)**再**与(&&)**
bool FQueryEvaluator::EvalNoTagsMatch(FGameplayTagContainer const& Tags, bool bSkip)
{
	bool bShortCircuit = bSkip;
	bool Result = true;
	//1. 解析 Tag数量
	int32 const NumTags = GetToken();
	if (bReadError)
	{
		return false;
	}
	
	for (int32 Idx = 0; Idx < NumTags; ++Idx)
	{
		int32 const TagIdx = GetToken();
		if (bReadError)
		{
			return false;
		}

		if (bShortCircuit == false)
		{
			//2. 根据Tag索引读取Tag
			FGameplayTag const Tag = Query.GetTagFromIndex(TagIdx);
			bool const bHasTag = Tags.HasTag(Tag);

			if (bHasTag == true)
			{
				//3. 有一个为真 则为假
				bShortCircuit = true;
				Result = false;
			}
		}
	}

	return Result;
}
```

**表达式参与运算的是嵌套的子表达式,递归评估子表达式直到表达式参与运算的是Tag**

| 类型 | 说明 | 示例 |
| --- | --- | --- |
| **EvalAnyExprMatch**  | **有一个子表达式结果为真即为真**

多个子表达式之间做**或(||)**运算 **

**只配置一个子表达式 则结果取决于该子表达式结果 | ***子表达式1 || 子表达式2 ||  子表达式3*** |
| **EvalAllExprMatch**  |  **所有子表达式结果为真才为真**

多个子表达式之间做**与(&&)**运算 **

只配置一个子表达式 则结果取决于该子表达式结果 | ***子表达式1 || 子表达式2 || 子表达式3*** |
| **EvalNoExprMatch** | **所有子表达式结果都为假才为真**

多个子表达式直接 先做**非(!)**运算再做**与(&&)**运算 

只配置一个子表达式 则判定结果取决于 该表达式的结果取反(**!子表达式**) | ***!子表达式1 && !表达式2 && !表达式3*** |

```cpp
//嵌套的子表达式之间 做||运算     有一个子表达式为真 则为真
bool FQueryEvaluator::EvalAnyExprMatch(FGameplayTagContainer const& Tags, bool bSkip)
{
	bool bShortCircuit = bSkip;
	bool Result = false;
	
	//1. 解析表达式数量
	int32 const NumExprs = GetToken();
	if (bReadError)
	{
		return false;
	}

	for (int32 Idx = 0; Idx < NumExprs; ++Idx)
	{
		//2.子表达式评估 递归
		bool const bExprResult = EvalExpr(Tags, bShortCircuit);
		if (bShortCircuit == false)
		{
			if (bExprResult == true)
			{
				//3. 有一个位真 即为真
				Result = true;
				bShortCircuit = true;
			}
		}
	}

	return Result;
}

//嵌套的子表达式之间 做&&运算     有一个子表达式为假 则为假
bool FQueryEvaluator::EvalAllExprMatch(FGameplayTagContainer const& Tags, bool bSkip)
{
	bool bShortCircuit = bSkip;
	bool Result = true;

	//1. 解析表达式数量
	int32 const NumExprs = GetToken();
	if (bReadError)
	{
		return false;
	}

	for (int32 Idx = 0; Idx < NumExprs; ++Idx)
	{
		//2.递归评估子表达式
		bool const bExprResult = EvalExpr(Tags, bShortCircuit);
		if (bShortCircuit == false)
		{
			if (bExprResult == false)
			{
				//3. 有一个为假 则为假
				Result = false;
				bShortCircuit = true;
			}
		}
	}

	return Result;
}

//嵌套的子表达式之间 先做!再做&&运算     有一个子表达式为真 则为假
bool FQueryEvaluator::EvalNoExprMatch(FGameplayTagContainer const& Tags, bool bSkip)
{
	bool bShortCircuit = bSkip;
	bool Result = true;

	//1. 解析表达式数量
	int32 const NumExprs = GetToken();
	if (bReadError)
	{
		return false;
	}

	for (int32 Idx = 0; Idx < NumExprs; ++Idx)
	{
		//2.递归评估子表达式
		bool const bExprResult = EvalExpr(Tags, bShortCircuit);
		if (bShortCircuit == false)
		{
			if (bExprResult == true)
			{
				//3. 有一个为真 则为假
				Result = false;
				bShortCircuit = true;
			}
		}
	}

	return Result;
}
```

# FGameplayTagRequirements

---

**功能与FGameplayTagQuery类似 也是为了匹配Tag** 

```cpp
struct GAMEPLAYABILITIES_API FGameplayTagRequirements
{
	FGameplayTagContainer RequireTags;
	FGameplayTagContainer IgnoreTags;
	FGameplayTagQuery TagQuery;
}
```

内部封装了一个FGameplayTagQuery对象**TagQuery**、一个指定必须有哪些Tag的FGameplayTagContainer对象**RequireTags**和一个必须不能有哪些Tag的FGameplayTagContainer 对象**IgnoreTags**

> 💡 *5.3之前还没FGameplayTagQuery机制 这个就是简化版FGameplayTagQuery
>
> 5.3加入FGameplayTagQuery实现后* 
> FGameplayTagRequirements在*原有的简化版基础上再扩展了更灵活的FGameplayTagQuery
>
> 同时一些简单的筛选可以直接通过*RequireTags和IgnoreTags配置，不用配置更复杂的*FGameplayTagQuery*

```cpp
bool FGameplayTagRequirements::RequirementsMet(const FGameplayTagContainer& Container) const
{
	//RequireTags 中的Tag 必须有
	const bool bHasRequired = Container.HasAll(RequireTags);
	//IgnoreTags 中的Tag必须没有
	const bool bHasIgnored = Container.HasAny(IgnoreTags);
	//更复杂的用*FGameplayTagQuery 匹配*
	const bool bMatchQuery = TagQuery.IsEmpty() || TagQuery.Matches(Container);

	return bHasRequired && !bHasIgnored && bMatchQuery;
}

```