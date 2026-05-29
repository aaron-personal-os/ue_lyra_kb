---
id: 60-decisions/review-game-feature-series
type: adr
status: current
language: zh
owner: ai
last_synced: 2026-05-22
last_verified: 2026-05-22
tags: [game-feature, review, tutorial, adr]
---

# Review: GameFeature 系统从入门到实战系列教程

> 2026-05-22 对 `Docs/30-tutorials/game-feature/` 系列的审查报告。P0 问题已修复。

## 审查范围

- `_series.yaml`
- `00-overview.md` ~ `05-advanced-custom.md`（共 6 篇）
- `70-topics/game-feature-system.md`（关联页面）
- 经 Lyra 源码抽样验证关键技术断言

## 总体评价

系列整体结构合理，渐进式学习路径清晰，Mermaid 图示丰富，教学风格统一。但经 Lyra 源码抽样验证，发现若干**技术断言不准确**和**内容重复**问题。

---

## 一、严重问题（源码验证失败）

### P0-1. `LoadExperience()` 方法名错误 — 多处出现

**涉及文件**: `03-lifecycle-loading.md:330`, `04-lyra-experience.md:268,297,313,339`

教程中多次写成：
```cpp
void ULyraExperienceManagerComponent::LoadExperience(TSoftClassPtr<ULyraExperienceDefinition> ExperienceClass);
```

**实际源码** (`LyraExperienceManagerComponent.h:47`)：
```cpp
void SetCurrentExperience(FPrimaryAssetId ExperienceId);
```

- 方法名、参数类型、参数名全部不同
- 实际接受 `FPrimaryAssetId`（不是 `TSoftClassPtr`）
- 这是一个**高风险错误**，读者按教程写代码会编译失败

### P0-2. `OnExperienceLoaded` 委托访问方式错误

**涉及文件**: `03-lifecycle-loading.md:313`, `04-lyra-experience.md:275`

教程暗示可直接访问委托：
```cpp
FOnExperienceLoaded OnExperienceLoaded;
```

**实际源码** 有三个优先级的委托，且通过方法访问：
```cpp
FOnLyraExperienceLoaded OnExperienceLoaded_HighPriority;
FOnLyraExperienceLoaded OnExperienceLoaded;
FOnLyraExperienceLoaded OnExperienceLoaded_LowPriority;
```
访问方式为 `CallOrRegister_OnExperienceLoaded()` 等方法，不是直接访问 delegate。

### P0-3. GameFeatureAction 生命周期方法签名不完整

**涉及文件**: `01-what-is-gamefeature.md:286`, `02-core-mechanism.md:253`, `05-advanced-custom.md:81-84`

教程写的是：
```cpp
virtual void OnGameFeatureActivating() override;
virtual void OnGameFeatureDeactivating() override;
```

**实际源码**（`GameFeatureAction_WorldActionBase.h:28-29`）：
```cpp
virtual void OnGameFeatureActivating(FGameFeatureActivatingContext& Context) override;
virtual void OnGameFeatureDeactivating(FGameFeatureDeactivatingContext& Context) override;
```

方法签名带 `Context` 参数，教程全部遗漏。自定义 Action 示例代码也因此无法编译。

### P0-4. `RegisterInitiatedComponent` API 错误

**涉及文件**: `01-what-is-gamefeature.md:378`, `02-core-mechanism.md:377-381`, `05-advanced-custom.md:337-341`

教程写的：
```cpp
UGameFrameworkComponentManager::GetForActor(this)->RegisterInitiatedComponent(this, FComponentInitDelegate());
```

**实际 API**：`AModularCharacter` 使用的是 `AddGameFrameworkComponentReceiver(this)`，不是 `RegisterInitiatedComponent`。

### P0-5. 自定义 Action 示例代码无法编译

**涉及文件**: `05-advanced-custom.md:59-156`

自定义 `UMyGameFeatureAction` 示例中 `OnGameFeatureActivating()` 和 `OnGameFeatureDeactivating()` 缺少 Context 参数，且未展示 `FGameFeatureActivatingContext` 的用法。

---

## 二、中等问题

### P1-1. 大段伪代码未标注"简化"

`03-lifecycle-loading.md:165-262` 中 `LoadAndActivateGameFeaturePlugin`、`LoadGameFeaturePlugin`、`LoadGameFeatureData`、`ActivateGameFeatureActions` 等函数实现是伪代码，不是引擎真实源码。但教程未标注"简化实现"。

根据 `ai-playbook.md` 的信源准则，这些属于"AI 推断"级别，应标注或明确标注为伪代码。

### P1-2. `UnloadGameFeaturePlugin` 在 Lyra 中未使用

教程多处暗示加载→激活→停用→卸载是完整流程，但 Lyra 实际只调用 `DeactivateGameFeaturePlugin()`，不调用 `UnloadGameFeaturePlugin()`。`LyraExperienceManagerComponent.cpp:24` 有注释：`// @TODO: Handle deactivating game features, right now we 'leak' them enabled`。

### P1-3. 缺少 `last_verified` 字段

根据 `.wiki-schema.md` 规范，所有页面**必须**包含 `last_verified` 字段，但全部 6 个教程文件都缺失该字段。

### P1-4. `00-overview.md` 导航链接指向不相关页面

`00-overview.md:219` 的导航左箭头指向 `30-tutorials/pcg/10-performance-optimization`，明显错误。

---

## 三、内容重复问题

### P2-1. 系列内大量重复

| 重复内容 | 出现位置 |
|---------|---------|
| `ULyraExperienceDefinition` 属性代码 | 01, 02, 04 (3次) |
| Plugin vs GameFeature 对比表 | 00, 01 (2次) |
| USB 类比 | 00, 01 (2次) |
| "合理划分 GameFeature" 最佳实践 | 02, 05 (2次) |
| "使用 Experience Definition 管理" 最佳实践 | 02, 03, 04, 05 (4次) |
| "异步加载处理" 最佳实践 | 02, 03, 05 (3次) |
| "忘记注册 Receiver" 陷阱 | 01, 02, 05 (3次) |
| Lyra GameFeature 插件列表 | 00, 01, 04 (3次) |

**建议**: 在首次出现处详细讲解，后续引用时用 `详见 [[XX]]` 的 wikilink 引导。

### P2-2. 教程与 `70-topics/game-feature-system.md` 高度重复

topic 页面与教程系列内容重叠率约 80%，几乎同样的架构图、代码示例、最佳实践。应明确分工。

### P2-3. 课时 3 和 4 边界模糊

课时 3 已经详细讲了 Lyra Experience System 的加载流程，课时 4 又重复讲了一遍。

### P2-4. 缺少实操练习

每课时末尾都是"总结与要点"和"下一步"，但缺少动手练习。

### P2-5. 代码示例偏伪代码，缺 Lyra 真实代码

04 中 ShooterCore 的 Actions 配置示例（如 `ULyraShootAbility::StaticClass()`）是虚构的，并非 Lyra 真实类名。

---

## 四、正面评价

1. **渐进式结构** 设计合理：概念→机制→生命周期→实战→高级
2. **Mermaid 图示** 覆盖率高，架构图、时序图、状态图均有
3. **Frontmatter** 规范（除缺 `last_verified` 外），`engine_sources` / `lyra_sources` 标注了源码参考路径
4. **常见陷阱** 部分实用（Receiver 注册、名称匹配、AssetManager 配置）
5. **导航系统** 完整，每页有前后导航和相关页面链接

---

## 五、修复优先级总结

| 优先级 | 问题 | 数量 |
|--------|------|------|
| **P0 (必须修)** | 源码验证失败（方法名/签名错误） | 5 |
| **P1 (应修)** | 伪代码未标注、缺 last_verified、导航错误 | 4 |
| **P2 (建议修)** | 内容重复、课时边界、缺实操练习 | 5 |

---

## 源码验证关键路径

| 验证项 | 源码路径 | 结论 |
|--------|---------|------|
| Experience 加载方法 | `Source/LyraGame/GameModes/LyraExperienceManagerComponent.h:47` | `SetCurrentExperience(FPrimaryAssetId)` |
| 委托访问 | 同上 `:52-60` | `CallOrRegister_OnExperienceLoaded*()` |
| Action 基类签名 | `Source/LyraGame/GameFeatures/GameFeatureAction_WorldActionBase.h:28-29` | 带 `Context` 参数 |
| ModularCharacter 注册 | `Plugins/ModularGameplayActors/.../ModularCharacter.cpp:12` | `AddGameFrameworkComponentReceiver(this)` |
| Experience Definition 属性 | `Source/LyraGame/GameModes/LyraExperienceDefinition.h:38-51` | 四属性均正确 |
| ShooterCore uplugin | `Plugins/GameFeatures/ShooterCore/ShooterCore.uplugin` | 三字段均正确 |
| AsyncAction_ExperienceReady | `Source/LyraGame/GameModes/AsyncAction_ExperienceReady.h:27-28` | `WaitForExperienceReady(UObject*)` |

---

> 审查日期：2026-05-22 | 审查方式：全量阅读 + Lyra 源码抽样验证
