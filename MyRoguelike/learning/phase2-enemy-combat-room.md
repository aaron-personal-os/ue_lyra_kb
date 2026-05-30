# Phase 2：敌人与战斗房间 — 学习导读

## 本阶段目标

建立最小战斗回路：敌人拥有 GAS 生命属性、基础 AI 行为（追逐/攻击/死亡），以及 RoomRuntimeController 负责刷怪与房间结算。

## 推荐阅读清单

1. [`00-AActor架构概述.md`](../../Docs/30-tutorials/ue-framework/40-actor-system/00-AActor架构概述.md)
   — 理解 Actor 的组件模型、BeginPlay / EndPlay 调用时机；敌人 Actor 的生命周期管理依赖这套机制。

2. [`01-AActor完整生命周期.md`](../../Docs/30-tutorials/ue-framework/40-actor-system/01-AActor完整生命周期.md)
   — 从 Spawn 到 Destroy 的完整流程；RoomRuntimeController 刷怪和销毁逻辑都基于此。

3. [`00-BehaviorTree与StateTree AI决策系统完全指南.md`](../../Docs/30-tutorials/ai-behavior/00-BehaviorTree与StateTree AI决策系统完全指南.md)
   — 系列总览；快速判断 BehaviorTree 和 StateTree 哪个更适合你的敌人 AI 复杂度。

4. [`01-BehaviorTree基础节点类型与执行流程.md`](../../Docs/30-tutorials/ai-behavior/01-BehaviorTree基础节点类型与执行流程.md)
   — BehaviorTree 核心节点（Sequence、Selector、Task、Decorator）；用于实现追逐/攻击/死亡的最小 AI。

5. [`05-LyraAI实战Bot控制与BehaviorTree.md`](../../Docs/30-tutorials/ai-behavior/05-LyraAI实战Bot控制与BehaviorTree.md)
   — Lyra 如何组织 Bot 的 Controller 和 BehaviorTree；可参考结构，但忽略多人相关内容。

6. [`ai-system.md`](../../Docs/10-architecture/subsystems/ai-system.md)
   — Lyra AI 系统架构总览；了解 AIController / PerceptionSystem 的整合方式。

## Lyra 单机差异提示

| 文档 | 可跳过的章节 |
|------|------------|
| `LyraAI实战` | Bot 生成的网络权威管理、服务器端生成逻辑 |
| `AActor完整生命周期` | Authority / Client 差异章节（单机 Authority 等于 Client） |

## 项目映射说明

- 敌人 Actor 应使用与玩家相同的 GAS 模式（也有 ASC + AttributeSet），这样伤害 GameplayEffect 可以直接在两者之间复用，无需为敌人写特殊逻辑。
- `RoomRuntimeController` 是项目自定义的 Actor/Component，负责管理一个房间的生命周期（刷怪 → 战斗 → 结算 → 开门）。Lyra 没有直接等价物，但 `AGameState` 的状态机思路可参考。
- 敌人死亡时通过 `GameplayTag`（如 `State.Dead`）触发状态转换，而不是直接销毁 Actor，这样 GAS 的死亡动画和奖励逻辑可以干净分离。

## 扩展阅读

- [`02-BehaviorTree高级DecoratorService与EQS.md`](../../Docs/30-tutorials/ai-behavior/02-BehaviorTree高级DecoratorService与EQS.md) — 若需要更复杂的寻路感知逻辑（如 EQS 找掩体）。
- [`03-StateTree入门.md`](../../Docs/30-tutorials/ai-behavior/03-StateTree入门.md) — 若 BehaviorTree 管理起来复杂，可考虑迁移到 StateTree。
- [`00-APawn与ACharacter详解.md`](../../Docs/30-tutorials/ue-framework/50-player-system/00-APawn与ACharacter详解.md) — 敌人角色继承自 ACharacter，理解其移动组件和 Capsule 的行为。

## 从 LevelDesign/Variant_RPG 借鉴

> 参考源：`G:\UEProjects\LevelDesign\Source\LevelDesign\Variant_RPG\`，详见 [ADR 0003](../decisions/0003-borrow-from-leveldesign-rpg.md)。

### MVP 敌人 AI：激进测试模式

LevelDesign 的 `ARPGAIController`（`AI/RPGAIController.h`）提供了一个无需完整 BehaviorTree 的**最简战斗 AI**，通过 `bAggressiveTestMode` 标志开启：

```
bAggressiveTestMode = true
  → Tick 里追玩家（MoveToActor）
  → 进入攻击距离（AggressiveStopDistance = 120cm）后停止
  → 按 AggressiveAttackInterval（默认 0.55s）间隔调用普攻
```

**对 MyRoguelike 的意义**：Phase 2 的最小验收目标是"进房间 → 敌人追玩家 → 技能打死敌人 → 清房结算"。在 BehaviorTree 还没建好之前，可以用一个类似的 `bAggressiveTestMode` 让 `AMREnemyAIController` 直接 Tick 驱动，快速验证整条伤害链（敌人 ASC 受到 GE → Health 归零 → 死亡 → 触发房间结算）。BehaviorTree 在战斗链验证通过后再接入。

### 输入抽象：AI 与玩家复用同一条行为路径

LevelDesign 的 `FCharacterInputFrame`（`Core/RPGTypes.h`）把所有输入——无论来自键盘还是 AI——统一封装成同一个 struct，通过 `IRPGInputSource` 接口注入 Character，AI 和玩家走完全相同的行为路径，方便调试和录制回放。

MyRoguelike 用 **InputTag → `ASC->TryActivateAbilitiesByTag()`** 达到同等效果：

- 玩家输入：`UEnhancedInputComponent::BindAction` → 绑定 InputTag 激活
- AI：`AIController::Tick` 或 BehaviorTree Task → 直接调用 `ASC->TryActivateAbilitiesByTag()`

两者最终都走 ASC 的技能激活路径，无需为 AI 单独实现伤害逻辑。这和 Phase 1 导读"项目映射说明"中"ASC 挂 Character，敌人和玩家共用同一套 GE 伤害链"的结论是一致的。
