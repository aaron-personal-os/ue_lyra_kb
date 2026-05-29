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
