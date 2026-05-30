# Phase 1：GAS 最小技能闭环 — 学习导读

## 本阶段目标

给玩家角色接入 Ability System Component，实现第一个可释放技能，并通过 GameplayEffect 处理冷却、消耗和伤害。

## 推荐阅读清单

1. [`ability-system.md`](../../Docs/10-architecture/subsystems/ability-system.md)
   — GAS 架构总览；先从这里建立 ASC / Attribute / Ability / Effect / Tag 五要素的整体认知，再看具体实现。

2. [`05-Lyra中的GAS集成.md`](../../Docs/30-tutorials/lyra-practical/05-Lyra中的GAS集成.md)
   — Lyra 如何初始化 ASC、分配 AbilitySet、与 PawnData 协作；重点理解"数据驱动授予技能"的模式。

3. [`ULyraAbilitySet.md`](../../Docs/20-modules/cpp/ULyraAbilitySet.md)
   — AbilitySet 是"一组技能 + 一组 Effect + 一组 Tag"的数据资产，Phase 3 的 Relic 系统会直接复用这个模式。

4. [`ULyraGameplayAbility.md`](../../Docs/20-modules/cpp/ULyraGameplayAbility.md)
   — Lyra 对 GameplayAbility 的封装；重点关注激活条件、Cost / Cooldown Effect 的绑定方式。

5. [`ULyraHealthComponent.md`](../../Docs/20-modules/cpp/ULyraHealthComponent.md)
   — 生命值属性和死亡状态的组件封装；本项目可以直接参考这个模式实现 HealthComponent。

6. [`05-Lyra实践InputTag与GAS联动详解.md`](../../Docs/30-tutorials/input-system/05-Lyra实践InputTag与GAS联动详解.md)
   — 输入事件如何通过 InputTag 触发 GAS Ability 的激活；这是技能释放闭环的关键连接点。

## Lyra 单机差异提示

| 文档 | 可跳过的章节 |
|------|------------|
| `ability-system.md` | Prediction Key 预测与回滚（单机无需）、网络复制 ASC 的服务器权威章节 |
| `Lyra中的GAS集成` | Replication Mode 设置（单机推荐 `Full`，无需复杂配置）、PlayerState 持有 ASC 的复制原因说明 |
| `ULyraAbilitySet` | SubObject 复制相关内容 |

## 项目映射说明

- Lyra 将 ASC 挂在 `ALyraPlayerState` 上（用于多人同步）。本项目单机环境下，**直接把 ASC 挂在 Character 上**即可，更简单。
- `ULyraAbilitySet` 的模式完全适用于 Relic 系统：每个 Relic 就是一个 `AbilitySet` 数据资产，拾取时调用 `GiveToAbilitySystem()`，移除时调用 `TakeFromAbilitySystem()`。这是 Phase 3 的核心设计依据（见 [Phase 3 导读](phase3-relic-system.md)）。
- InputTag 与 GAS 的联动模式可以直接照搬，与多人无关。

## 扩展阅读

- [`ULyraAbilitySystemComponent.md`](../../Docs/20-modules/cpp/ULyraAbilitySystemComponent.md) — Lyra 对 ASC 的扩展，如需深入了解扩展点可查阅。
- [`ULyraPawnData.md`](../../Docs/20-modules/cpp/ULyraPawnData.md) — PawnData 是 Lyra 将 AbilitySet、Camera 模式等配置绑定到 Pawn 的方式；可作为未来数据驱动扩展的参考。
- [`ULyraPawnExtensionComponent.md`](../../Docs/20-modules/cpp/ULyraPawnExtensionComponent.md) — 理解 Lyra 如何在 Pawn 初始化时桥接 ASC，若想模仿其初始化顺序可参考。

## 从 LevelDesign/Variant_RPG 借鉴

> 参考源：`G:\UEProjects\LevelDesign\Source\LevelDesign\Variant_RPG\`，详见 [ADR 0003](../decisions/0003-borrow-from-leveldesign-rpg.md)。

### 技能 DataAsset 字段清单

`URPGAbilityDefinition`（`Data/RPGAbilityDefinition.h`）已在真实原型中验证了一套完整的技能字段。MyRoguelike 技能 DataAsset 或 GameplayAbility 默认值可直接参照以下字段：

| 字段 | 含义 | GAS 落地位置 |
|------|------|-------------|
| `Damage` | 基础伤害值 | Damage GE 的 SetByCaller Magnitude |
| `ManaCost` / `StaminaCost` | 消耗资源量 | Cost GE 的 SetByCaller Magnitude |
| `CooldownSeconds` | 冷却时长 | Cooldown GE 的 Duration |
| `Range` | 技能作用范围 | GA 内射线检测参数 |
| `DamageApplicationTiming` | `Instant`（即时）或 `OnAnimNotify`（帧提交） | 决定 GA 在 ActivateAbility 还是 WaitGameplayEvent 中应用 GE |
| `MeleeTargetQuery` | `ActorLineTrace` 或 `SocketSphereSweep` | GA 内命中检测逻辑选择 |
| `MeleeTraceSocketName` | 武器骨骼 Socket 名 | SweepSingleByChannel 起点 |
| `MeleeHitRange` / `MeleeHitRadius` | 近战有效距离与判定半径 | 球扫描参数 |
| `ActionMontage` | 技能动画 | `UAbilityTask_PlayMontageAndWait` 的输入 |

### 命中时序模式：PendingActivation → GAS AbilityTask

LevelDesign 的时序是：

```
TryActivateAbility()
  → PlayActionMontage()
  → BeginPendingActivation()    ← 登记"待命中"
AnimNotify_RPGMeleeDamage
  → CommitPendingMeleeDamage()  ← 在正确帧做射线检测 + 伤害
Montage 结束
  → ClearPendingActivation()
```

GAS 里的等价实现（推荐结构）：

```
GameplayAbility::ActivateAbility()
  → UAbilityTask_PlayMontageAndWait::CreatePlayMontageAndWaitProxy()
  → UAbilityTask_WaitGameplayEvent::WaitGameplayEvent(Tag: "GameplayEvent.Melee.Hit")
                                          ↑
                        AnimNotify_SendGameplayEvent 在正确帧发出该 Event
  → OnEventReceived()
      → LineTrace / SphereSweep 检测命中
      → ApplyGameplayEffectToTarget(DamageGE)
  → OnCompleted() / OnInterrupted()
      → EndAbility()
```

好处：帧提交时序与 LevelDesign 完全一致，同时伤害通过 GE 表达，可叠加 relic 的伤害加成修正。

### 组件化角色结构

参照 `ARPGCharacter`（`Core/RPGCharacter.h`）的设计原则：**主 Character 类只做组件 getter，不含任何业务逻辑**。

`AMRCharacterBase` 建议遵循同样约定：

```cpp
// 主类只暴露 getter，职责边界清晰
UAbilitySystemComponent* GetAbilitySystemComponent() const;
UMRAttributeSet*         GetAttributeSet()           const;
// 未来可按需添加 AnimationComponent / EquipmentComponent 等
```

ASC 挂在 Character 本体（非 PlayerState），Owner 和 Avatar 均为 `this`，单机场景完全够用且更简单。
