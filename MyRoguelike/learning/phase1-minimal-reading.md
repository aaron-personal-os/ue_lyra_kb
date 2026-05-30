# Phase 1 最小阅读清单（可执行版）

> 适用对象：已有 Third Person / 组件化 C++ 经验（如 LevelDesign/Variant_RPG），希望**跳过 UE 框架系统学习，直接做 GAS 技能闭环**。
>
> 完整版导读仍见 [phase0-project-init.md](phase0-project-init.md) 与 [phase1-gas-skill-loop.md](phase1-gas-skill-loop.md)。本文是精简路径。

## 开始前：4 项自检

能答「是」就可以开 GAS，不必先读 UE 框架系列：

- [ ] 会在 C++ Character 上挂 `UActorComponent`
- [ ] 知道在 `BeginPlay` 里做初始化
- [ ] 会用 Enhanced Input 绑一个按键（或 LevelDesign 的 `FCharacterInputFrame` 等价思路）
- [ ] 知道 GameMode 负责生成玩家 Pawn（不必深入 GameInstance / UWorld）

---

## 第 0 步：只做工程，几乎不读书（约 30 分钟）

按 [windows-setup-checklist.md](../dev/windows-setup-checklist.md) 完成：

1. 创建 Third Person **C++** 工程，启用 `GameplayAbilities` / `GameplayTags` / `GameplayTasks`
2. PIE 能跑、能移动、能编译
3. 运行 `init-roguelike-git.ps1` 初始化 git

**可选速览（仅卡住时看）：**

| 卡住的问题 | 看这一篇 |
|-----------|---------|
| InputAction / MappingContext 不会配 | [`01-EnhancedInput系统概览.md`](../../Docs/30-tutorials/input-system/01-EnhancedInput系统概览.md) |
| 不知道 GameMode 干什么 | [`00-AGameModeBase详解.md`](../../Docs/30-tutorials/ue-framework/30-gamemode-layer/00-AGameModeBase详解.md) 前半部分即可 |

**明确暂缓（Phase 4 之前不用读）：**

- `00-UE引擎层详解` / `UGameInstance详解` / `UWorld详解`
- 网络复制、Authority、Prediction 全部章节

---

## 第 1 步：GAS 主线阅读（按顺序，约 2～3 小时）

只读下面 **7 篇**，够做出第一个技能闭环。

| 顺序 | 文档 | 读什么 | 跳过什么 |
|------|------|--------|---------|
| 1 | [`ability-system.md`](../../Docs/10-architecture/subsystems/ability-system.md) | ASC / AttributeSet / GA / GE / Tag 五要素关系 | 网络复制、Prediction |
| 2 | [`00-GAS系统总览.md`](../../Docs/30-tutorials/gas/00-GAS系统总览.md) | GAS 在 UE 里的模块边界与术语 | 联机相关 |
| 3 | [`25-Attribute属性详解.md`](../../Docs/30-tutorials/gas/25-Attribute属性详解.md) | Health / Energy 属性定义与修改 | — |
| 4 | [`01-GA简介与配置.md`](../../Docs/30-tutorials/gas/01-GA简介与配置.md) | 第一个 GameplayAbility 怎么建 | — |
| 5 | [`06-GE简介与配置.md`](../../Docs/30-tutorials/gas/06-GE简介与配置.md) | Cost / Cooldown / Damage 三类 GE | 网络复制章节 |
| 6 | [`15-Tag简介与配置.md`](../../Docs/30-tutorials/gas/15-Tag简介与配置.md) | 冷却 Tag、状态 Tag、InputTag | Tag 网络复制 |
| 7 | [`05-Lyra实践InputTag与GAS联动详解.md`](../../Docs/30-tutorials/input-system/05-Lyra实践InputTag与GAS联动详解.md) | 按键 → InputTag → 激活技能 | 多人相关 |

**Lyra 实战参考（实现时对照，不必先通读）：**

- [`05-Lyra中的GAS集成.md`](../../Docs/30-tutorials/lyra-practical/05-Lyra中的GAS集成.md) — 看 ASC 初始化与授予技能；**ASC 挂 Character，不挂 PlayerState**
- [phase1 导读 · 从 LevelDesign 借鉴](phase1-gas-skill-loop.md#从-leveldesignvariantrpg-借鉴) — 技能字段、AnimNotify 命中时序

---

## 第 2 步：动手清单（对照 roadmap Phase 1）

按顺序实现，每项做完再进下一项：

```
[ ] MRCharacterBase：挂 UAbilitySystemComponent + UMRAttributeSet
[ ] BeginPlay：InitAbilityActorInfo(this, this)
[ ] AttributeSet：Health、Energy、AttackPower
[ ] 第一个 GA（如冲刺斩）：Activation 绑 InputTag
[ ] Cost GE：消耗 Energy
[ ] Cooldown GE：Duration + Cooldown Tag
[ ] Damage GE：Instant + SetByCaller 伤害值
[ ] 命中检测：LineTrace 或 SocketSphereSweep（可先 Instant，后接 AnimNotify）
[ ] 日志或 HUD：打印激活成功 / 冷却中 / 能量不足
```

**验收标准（与 [roadmap.md](../roadmap.md) Phase 1 一致）：**

- 按键释放技能
- 能量不足 → 失败
- 冷却中 → 失败
- 命中敌人 → 扣血

---

## 按需查阅（卡住再打开）

| 问题 | 文档 |
|------|------|
| GA 激活流程不清楚 | [`02-GA执行流程详解.md`](../../Docs/30-tutorials/gas/02-GA执行流程详解.md) |
| 动画帧才结算伤害 | [`22-AbilityTask详解.md`](../../Docs/30-tutorials/gas/22-AbilityTask详解.md) + [phase1 LevelDesign 命中时序](phase1-gas-skill-loop.md#命中时序模式pendingactivation--gas-abilitytask) |
| GE 数值怎么叠 | [`08-GE数值修正.md`](../../Docs/30-tutorials/gas/08-GE数值修正.md) |
| 死亡 / 生命归零 | [`ULyraHealthComponent.md`](../../Docs/20-modules/cpp/ULyraHealthComponent.md) |
| 组件化角色怎么拆 | [ADR 0003](../decisions/0003-borrow-from-leveldesign-rpg.md) + LevelDesign `ARPGCharacter` |

---

## 各阶段再补 UE 框架（不必现在学）

| 阶段 | 届时再读 |
|------|---------|
| Phase 2 敌人 / 房间 | `AActor` 生命周期、BehaviorTree 入门 |
| Phase 4 RunManager | `UGameInstance详解` |
| Phase 5 程序化关卡 | `UWorld详解`、Level Streaming |
| Phase 6 存档 | SaveGame 相关 |

---

## 一句话总结

**工程先跑起来 → 7 篇 GAS 文档 → 按清单做第一个技能闭环；UE 框架全书式学习可以跳过，用到再查。**
