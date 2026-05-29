# Phase 6：Meta 进度与存档 — 学习导读

## 本阶段目标

实现跨局持久化数据：解锁的永久词条、通关次数、角色解锁进度，以及游戏内货币（魂/硬币类）积累。

## 推荐阅读清单

1. [`00-UE5资源管理系列概览.md`](../../Docs/30-tutorials/resource-management/00-UE5资源管理系列概览.md)
   — 快速定位存档相关的资产管理知识；UE 的 `USaveGame` 是原生存档解决方案，不依赖任何 Lyra 框架。

2. [`04-引用与GC资源内存管理.md`](../../Docs/30-tutorials/resource-management/04-引用与GC资源内存管理.md)
   — Meta 进度数据中若存储了对 Relic / Ability 资产的软引用（`TSoftObjectPtr`），需要理解它如何在 GC 时被处理，以及序列化到存档时的注意事项。

3. [`01-UObject基础与内存模型.md`](../../Docs/30-tutorials/garbage-collection/01-UObject基础与内存模型.md)
   — `USaveGame` 本身是 `UObject`；理解 UObject 的序列化机制（`UPROPERTY` + `Serialize`），是实现自定义存档字段的基础。

4. [`00-GC垃圾回收系列概览.md`](../../Docs/30-tutorials/garbage-collection/00-GC垃圾回收系列概览.md)
   — Meta 进度系统会在游戏启动时加载、游戏退出时写回；了解 GC 如何处理持久对象的引用，避免存档对象被意外收集。

5. [`06-GC性能优化策略.md`](../../Docs/30-tutorials/garbage-collection/06-GC性能优化策略.md)
   — 若存档包含大量资产软引用，加载时的 GC 压力需要管理；了解 `AddToRoot` / `RemoveFromRoot` 的使用时机。

## Lyra 单机差异提示

| 文档 | 可跳过的章节 |
|------|------------|
| `Lyra资源管理实践` | GameFeature 按需加载的网络同步部分；Meta 进度是纯本地数据，不涉及服务器 |
| `GC系列` | Actor Channel 和 UObject 复制的网络相关章节 |

## 项目映射说明

**Meta 进度存档结构（建议）：**

```cpp
UCLASS()
class UMetaProgressSave : public USaveGame
{
    UPROPERTY() int32 TotalRunsCompleted;
    UPROPERTY() int32 MetaCurrency;                  // 跨局货币
    UPROPERTY() TArray<FName> UnlockedRelicIds;       // 已解锁的永久 Relic
    UPROPERTY() TMap<FName, int32> RelicUpgradeLevels; // 词条升级等级
    UPROPERTY() TArray<FName> UnlockedCharacters;
};
```

- 软引用（`TSoftObjectPtr<URelicData>`）**不推荐**直接存入 SaveGame，因为序列化时只会存路径字符串，资产重命名后会断链。改为存 `FName`（资产唯一 ID），加载时再通过 AssetRegistry 解析。
- Meta 进度子系统挂在 GameInstance（与 RunManager 同层），游戏启动时读取，每局结束时写入，退出时最终写入。

Lyra 没有 roguelike 的 Meta 进度概念，但它处理 `UPrimaryDataAsset` 的命名约定（用 `FPrimaryAssetId` 作为稳定标识符而不是路径）对这里的存档设计有参考价值。

## 扩展阅读

- [`07-Lyra项目中的GC实践.md`](../../Docs/30-tutorials/garbage-collection/07-Lyra项目中的GC实践.md) — Lyra 实际项目中如何管理大量 DataAsset 的生命周期。
- [`05-Cook与Pak打包流程.md`](../../Docs/30-tutorials/resource-management/05-Cook与Pak打包流程.md) — 发布版本中存档路径变化的风险，以及如何通过 Asset Manager 配置规避打包时资产被剔除。
