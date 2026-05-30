# 0003: 从 LevelDesign/Variant_RPG 吸取经验

## 状态

已接受。

## 背景

`G:\UEProjects\LevelDesign\` 是本机上的另一个 UE 学习工程，其 `Variant_RPG` 变体用**纯组件方案**实现了完整的动作战斗原型，包括：

- `URPGAbilityComponent`：自研技能激活、冷却（TMap 时间戳）、消耗检查、命中检测、AnimNotify 伤害时序
- `URPGAttributeComponent`：轻量 struct（Health / Mana / Stamina / Level / EXP）
- `URPGAbilityDefinition`（UPrimaryDataAsset）：技能数据资产，包含伤害/消耗/冷却/范围/命中方式/Montage 等字段
- `ARPGCharacter`：组件化基类，主类只做路由，业务全在子组件
- `ARPGAIController`：带激进测试模式的极简 AI（追玩家 + 定时攻击）
- `AnimNotify_RPGMeleeDamage`：在动画帧提交近战命中的 AnimNotify

该工程没有实现词条叠加（Buff/Debuff/relic 加成）。`URPGAttributeComponent::RecalculateFromEquipment` 通过手动重算属性来应用装备加成——当词条数量增长后，这种方式不可维护。

这正好反向印证了 MyRoguelike 选择 **GAS（Gameplay Ability System）** 的核心理由：持续型 `GameplayEffect` 天然支持多来源叠加、优先级、撤销，而无需手写叠加逻辑。

## 参考源文件（外部工程，仅作参照）

| 文件 | 借鉴内容 |
|------|---------|
| `Variant_RPG\Data\RPGAbilityDefinition.h` | 技能 DataAsset 字段完整参照 |
| `Variant_RPG\Core\RPGAbilityComponent.cpp` | 冷却时序、PendingActivation 模式、命中检测 |
| `Variant_RPG\Core\RPGTypes.h` | FCharacterInputFrame 输入抽象、FRPGAttributeSet 字段语义 |
| `Variant_RPG\Combat\AnimNotify_RPGMeleeDamage.h` | AnimNotify 提交伤害的时机模式 |
| `Variant_RPG\AI\RPGAIController.h` | bAggressiveTestMode 激进测试 AI |

## 决策：吸取什么，替换什么

### 自研系统 → GAS 等价物映射

| 维度 | LevelDesign 自研实现 | MyRoguelike GAS 等价实现 |
|------|---------------------|------------------------|
| 冷却 | `CooldownTimestamps`（`TMap<Ability*, float>` 时间戳比较） | `GameplayEffect`（Duration 型）+ Cooldown Tag |
| 消耗 | `TrySpendMana()` / `TrySpendStamina()` 直接减属性 | Cost `GameplayEffect`（Instant，SetByCaller 消耗量） |
| 属性 | `URPGAttributeComponent`（普通 struct） | `UAttributeSet`（Health / Energy / AttackPower） |
| 伤害 | `UGameplayStatics::ApplyDamage` | Damage `GameplayEffect`（Instant，SetByCaller 伤害值） |
| 技能数据 | `URPGAbilityDefinition`（UPrimaryDataAsset） | 技能 DataAsset 或 GameplayAbility 默认值（字段设计直接借鉴） |
| 命中时序 | `BeginPendingActivation` → AnimNotify → `CommitPendingMeleeDamage` | `UAbilityTask_PlayMontageAndWait` + `UAbilityTask_WaitGameplayEvent`（Notify 触发 `GameplayEvent.Melee.Hit`） |
| 输入抽象 | `FCharacterInputFrame` struct + `IRPGInputSource` 接口 | `InputTag` → `ASC->TryActivateAbilitiesByTag(InputTag)` |
| 角色结构 | 组件化 `ARPGCharacter`（主类只做 getter 路由） | 组件化 `AMRCharacterBase`（ASC 挂 Character 本体） |
| Buff / 词条叠加 | **未实现**（装备加成靠手动重算） | 持续型 `GameplayEffect`（GAS 原生支持，正是选 GAS 的核心理由） |

### 直接借鉴（思路/模式）

1. **技能 DataAsset 字段结构**：`URPGAbilityDefinition` 已验证了一套完整的技能字段，MyRoguelike 的技能 DataAsset 可以直接参照（详见 Phase 1 导读）。

2. **AnimNotify 命中时序模式**：`PendingActivation` → AnimNotify `CommitPendingMeleeDamage` 的"预登记→帧提交"思路，在 GAS 里用 AbilityTask 等价实现（详见 Phase 1 导读）。

3. **输入抽象**：`FCharacterInputFrame` 把玩家输入和 AI 输入统一抽象为同一个 struct，使 AI 能复用完全相同的角色行为路径。MyRoguelike 的 InputTag 驱动方案达到同等效果（详见 Phase 2 导读）。

4. **组件化角色**：主 Character 类只做组件 getter，业务逻辑全在子组件里，主类不含技能/属性/动画状态逻辑（详见 Phase 1 导读）。

5. **激进测试 AI**：`bAggressiveTestMode`（追玩家 + 定时普攻）是 MVP 阶段验证战斗伤害链的最快路径，无需完整 BehaviorTree（详见 Phase 2 导读）。

### 不借鉴（RPG 特有，roguelike 不需要）

- 等级 / 经验值系统（`FRPGAttributeSet::Level / Experience`）
- 装备槽 / 背包系统（`URPGEquipmentComponent` / `URPGInventoryComponent`）
- 任务系统（`URPGQuestComponent`）
- 交互系统（`URPGInteractionComponent`，roguelike 不需要 NPC 对话式交互）
- `RecalculateFromEquipment` 的手动属性叠加模式（反面参照，见 Phase 3 导读）

## 与其他决策的关系

- [ADR 0001](0001-tech-stack-selection.md)：选 GAS 的决策在此得到了"自研方案局限性"的实践佐证。
- [ADR 0002](0002-windows-dev-environment.md)：LevelDesign 工程在本机同级目录 `G:\UEProjects\LevelDesign\`，不纳入 MyRoguelike 仓库，仅作磁盘参照。

## 结论

LevelDesign/Variant_RPG 是"不用 GAS 能做到什么程度"的最佳实践参照。它验证了动作战斗原型的可行路径，同时也暴露了自研系统在词条叠加场景下的瓶颈——正是 MyRoguelike 需要解决的核心问题。从中借鉴字段设计、时序模式和测试 AI 思路，替换掉自研的 Ability/Attribute 机制，走 GAS 通路。
