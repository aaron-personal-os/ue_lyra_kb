# 0001: 技术选型基线

## 状态

已接受。

## 背景

目标项目是一个单机 3D 动作 roguelike，核心体验围绕技能释放、局内成长、词条组合和重复游玩展开。

当前参考资料来自 Lyra 知识库，但目标项目不是 Lyra 改造版。Lyra 的强项是 Gameplay Ability System、数据驱动、模块化玩法和 GameFeature/Experience 架构；同时它也包含大量面向在线多人、匹配、专用服务器、复制预测和 LiveOps 的复杂度。

对本项目而言，最重要的问题不是“如何完整复刻 Lyra”，而是选择哪些机制能直接服务于单机技能型 roguelike。

## 决策

采用干净 Unreal 工程作为项目起点，优先建议 Third Person 模板；核心战斗系统使用 Gameplay Ability System。Lyra 作为架构和源码参考，不直接 fork 作为项目地基。

早期不引入完整 Experience/GameFeature 框架。等项目出现明确的“模式切换”“局内 mutator”“可解锁内容包”需求后，再评估是否引入轻量化的 Experience 或 GameFeature 方案。

## 选型表

| 模块 | 决策 | 理由 |
|---|---|---|
| Gameplay Ability System | 必上 | 技能释放、冷却、消耗、命中、buff/debuff、词条叠加都是 GAS 的优势场景。 |
| GameplayEffect / GameplayTag | 必上 | 用 GameplayEffect 表达属性修改和状态变化，用 GameplayTag 表达条件、状态、免疫和触发器。 |
| AbilitySet 思路 | 借鉴 | 将“一组技能、属性、效果”打包成 DataAsset；拾取 relic 或选择职业时授予。 |
| 数据驱动内容 | 必上 | 技能、敌人、物品、词条、房间权重都应尽量数据化，降低新增内容成本。 |
| PawnData 思路 | 轻量借鉴 | 用数据资产描述角色/职业的初始技能、属性和相机配置，不照搬 Lyra 全套。 |
| Experience 系统 | 延后 | 单机早期只有一个主模式，不需要复杂的匹配/URL/命令行覆盖链。 |
| GameFeature 插件 | 延后 | 适合后期的 mutator、挑战包、可解锁内容包；早期引入会增加资产管理和生命周期复杂度。 |
| CommonUI | 暂不采用 | 早期 UMG 足够；CommonUI 主要服务多平台输入和大型 UI 架构。 |
| 匹配/专服/ReplicationGraph | 不采用 | 单机项目没有收益，保留会制造无关复杂度。 |

## 架构原则

1. 先让技能闭环成立，再扩内容。
2. 所有局内成长都尽量通过 GameplayEffect、AbilitySet 和 GameplayTag 表达。
3. 运行时状态和永久进度分开：Run 状态属于本局，Meta 状态属于存档。
4. 程序化关卡不要依赖 Experience 切换；一局内换层应使用轻量化的房间拼接、流式子关卡或运行时生成。
5. Lyra 源码用于学习和参考，不直接继承它的在线服务框架。

## 需要自建的核心系统

### 程序化关卡生成

Lyra 不提供 roguelike 地牢生成。项目需要自建房间池、连接规则、种子、权重、奖励房/商店房/Boss 房等逻辑。

建议早期采用“手工房间块 + 程序化拼接”的方式，而不是一开始做完全自由的几何生成。

### Run 状态管理

需要一个运行时管理者保存当前 run 的随机种子、楼层编号、已获得 relic、当前属性修正、房间访问状态和临时资源。

初期建议使用 `GameInstanceSubsystem` 承载跨关卡的 run 状态，等系统复杂后再拆为更细的 subsystem。

### Meta 进度

跨 run 解锁、永久升级、货币、角色解锁和图鉴等信息应进入 `SaveGame`。不要把永久进度和本局状态混在一起。

## 风险与权衡

### GAS 学习曲线

GAS 概念栈较重，包括 Ability System Component、AttributeSet、GameplayAbility、GameplayEffect、GameplayTag、GameplayCue 等。即使是单机也需要建立清晰约定。

缓解方式：

- 先按本地权威使用，暂时不处理网络预测。
- 第一阶段只做一个主动技能、一个冷却 GameplayEffect、一个消耗 GameplayEffect。
- 等技能闭环稳定后，再扩展词条、被动效果和触发器。

### 过早模块化

GameFeature 和 Experience 能带来强模块化，但也会引入插件生命周期、AssetManager 配置、异步加载时序和调试成本。

缓解方式：

- 早期使用普通 DataAsset + Subsystem。
- 只有当同一套内容需要被独立启用、停用、打包或解锁时，再引入 GameFeature。

### 从 Lyra 复制过多结构

Lyra 为多人在线样例设计，直接 fork 会带来大量不需要的网络与服务代码。

缓解方式：

- 只阅读和移植思想：GAS 使用模式、PawnData、AbilitySet、Experience 的数据驱动思想。
- 不复制匹配、专服、CommonSession、ReplicationGraph 等单机无关模块。

## 后续触发条件

满足以下任一条件时，重新评估是否引入轻量 Experience 或 GameFeature：

- 项目出现多个明确玩法模式，例如普通 run、Boss Rush、每日挑战、无尽模式。
- 需要把某批内容作为可解锁内容包独立启用或停用。
- 需要运行时启用 mutator，例如“本局所有敌人爆炸”“技能无冷却但生命上限降低”。
- 需要将玩法模块拆给不同开发者并行维护。

## 结论

本项目早期路线是：干净工程、GAS 核心、数据驱动内容、自建 roguelike 三件套（程序化关卡、Run 状态、Meta 进度）。

Lyra 的角色是参考资料和设计范式，不是项目基座。
