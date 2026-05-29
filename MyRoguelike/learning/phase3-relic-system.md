# Phase 3：Relic / 词条系统 — 学习导读

## 本阶段目标

实现局内随机构筑系统：Relic 是数据资产，拾取时通过 GAS 授予技能和 Effect，移除时干净撤销，支持叠加和互斥规则。

## 推荐阅读清单

1. [`01-资产分类体系PrimaryAsset与SecondaryAsset.md`](../../Docs/30-tutorials/resource-management/01-资产分类体系PrimaryAsset与SecondaryAsset.md)
   — 理解 PrimaryAsset / SecondaryAsset 区分；Relic 应设计为 `UPrimaryDataAsset`，以便通过 Asset Manager 异步加载和卸载，避免内存常驻。

2. [`02-AssetRegistry资产注册表查询.md`](../../Docs/30-tutorials/resource-management/02-AssetRegistry资产注册表查询.md)
   — 如何在运行时查询所有 Relic 资产（用于随机抽取候选池），不需要硬引用所有 Relic。

3. [`03-异步加载FStreamableManager与RequestAsyncLoad.md`](../../Docs/30-tutorials/resource-management/03-异步加载FStreamableManager与RequestAsyncLoad.md)
   — Relic 数据资产按需异步加载；明白 `TSoftObjectPtr` 与强引用的区别，避免所有 Relic 在启动时全量加载。

4. [`ULyraAbilitySet.md`](../../Docs/20-modules/cpp/ULyraAbilitySet.md)
   — **本阶段最核心参考**。Lyra 的 AbilitySet 模式完全可复用为 Relic：每个 Relic 内含一个 AbilitySet，拾取时 `GiveToAbilitySystem()`，移除时 `TakeFromAbilitySystem()`，系统自动追踪授予记录（`FLyraAbilitySet_GrantedHandles`）。

5. [`06-Lyra资源管理实践.md`](../../Docs/30-tutorials/resource-management/06-Lyra资源管理实践.md)
   — Lyra 实际如何组织 PawnData、AbilitySet、Experience 的资产依赖关系；可作为设计 Relic 资产目录结构的参考。

## Lyra 单机差异提示

| 文档 | 可跳过的章节 |
|------|------------|
| `ULyraAbilitySet` | 关于 SubObject 复制和网络同步的部分（单机无需） |
| `Lyra资源管理实践` | GameFeature Plugin 的按需加载（单机不用 GameFeature 框架） |

## 项目映射说明

**Relic 数据资产结构（建议）：**

```
URelicData : UPrimaryDataAsset
├── FText DisplayName
├── UTexture2D* Icon
├── ULyraAbilitySet* GrantedAbilitySet    // 复用 Lyra 模式
├── TArray<FGameplayTag> RequiredTags      // 前置条件
└── TArray<FGameplayTag> ExclusiveTags    // 互斥条件
```

**Relic 系统流程：**
- 候选池 = 用 AssetRegistry 查询所有 `URelicData` 类型资产 → 过滤已拥有 / 互斥标签 → 随机抽 3 个展示。
- 拾取 = 异步加载 → 调用 `RelicData->GrantedAbilitySet->GiveToAbilitySystem()` → 存储 `GrantedHandles`。
- 移除（如 Boss 诅咒）= 用存储的 `GrantedHandles` 调用 `TakeFromAbilitySystem()`。

`ULyraAbilitySet` 的 GrantedHandles 机制已经处理了"撤销时同时移除技能、Effect 和 Tag 的授予"，不需要自己实现。

## 扩展阅读

- [`04-引用与GC资源内存管理.md`](../../Docs/30-tutorials/resource-management/04-引用与GC资源内存管理.md) — 理解强引用 vs 软引用的 GC 影响，确保 Relic 资产在不需要时能被正确卸载。
- [`ULyraEquipmentManagerComponent.md`](../../Docs/20-modules/cpp/ULyraEquipmentManagerComponent.md) — Lyra 装备系统也用了 AbilitySet 授予模式，可以看一下装备和卸载的完整流程作为参考。
