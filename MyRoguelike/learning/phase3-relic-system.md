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

## 从 LevelDesign/Variant_RPG 对比（反面参照）

> 参考源：`G:\UEProjects\LevelDesign\Source\LevelDesign\Variant_RPG\Core\RPGAttributeComponent.cpp`，详见 [ADR 0003](../decisions/0003-borrow-from-leveldesign-rpg.md)。

### 手动重算加成的局限

LevelDesign 的装备加成通过 `RecalculateFromEquipment(FRPGItemStatModifiers)` 实现：每次装备变动时，重新累加所有装备的 `BonusMaxHealth` / `BonusAttackDamage` 并写回属性。

```cpp
// LevelDesign 的方式（不要在 MyRoguelike 里照搬）
void URPGAttributeComponent::RecalculateFromEquipment(const FRPGItemStatModifiers& EquipmentModifiers)
{
    Attributes.MaxHealth = BaseAttributes.MaxHealth + EquipmentModifiers.BonusMaxHealth;
    BonusAttackDamage    = EquipmentModifiers.BonusAttackDamage;
    BroadcastChange(TEXT("MaxHealth"), Attributes.MaxHealth);
}
```

这在"只有装备加成"的场景下够用，但 roguelike 的 relic 系统会有：

- 多个 relic 同时贡献相同属性（5 个 relic 各加 10% 伤害 → 需要叠加）
- 同一 relic 有时间维度（持续 3 秒内伤害翻倍）
- 某些 relic 有条件触发（"击杀后"）
- Boss 诅咒需要**精确撤销**某个具体 relic 的加成

每增加一种 relic 机制，`RecalculateFromEquipment` 就要扩展一次，最终变成一个庞大的条件计算函数，难以维护。

### GAS 持续型 GameplayEffect 的优势

Relic 选用 GAS 的 `AbilitySet::GiveToAbilitySystem()` + 持续型 `GameplayEffect`，每个 relic 独立授予、独立存在、独立撤销：

```text
Relic A 授予 → GE_RelicA_DamageBoost（持续型，Modifier: AttackPower * 1.1）
Relic B 授予 → GE_RelicB_DamageBoost（持续型，Modifier: AttackPower * 1.1）
...（n 个 relic 各自独立，GAS 自动聚合所有 Modifier）

撤销 Relic A → TakeFromAbilitySystem(GrantedHandles_A) → 仅移除 A 的效果，B 不受影响
```

GAS 的 `FActiveGameplayEffectsContainer` 自动维护所有激活效果的叠加计算，不需要手动重算。这正是 MyRoguelike 的 relic 系统选择 GAS 路径的核心依据。

### 字段语义可借鉴

`FRPGItemStatModifiers` 的字段命名（`BonusMaxHealth` / `BonusAttackDamage`）是合理的语义参照，在 MyRoguelike 的 `URelicData` DataAsset 或 GE 配置中，可以用相似的描述性命名约定。
