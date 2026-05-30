# MyRoguelike

这是一个专用于单机 3D 动作技能型 roguelike 项目的文档区。

当前项目定位：

- 单机。
- 3D 动作战斗。
- 核心体验围绕技能释放、局内成长和随机构筑。
- 技术路线为干净 Unreal 工程 + Gameplay Ability System。
- Lyra 作为学习参考，不作为项目基座。

## 当前状态

阶段：技术选型与架构基线，待迁移至 Windows 主力开发环境。

已确定的基线决策：

- 使用干净工程起步，优先 Third Person 模板。
- 核心战斗系统使用 Gameplay Ability System。
- 借鉴 Lyra 的数据驱动思想、AbilitySet / PawnData 模式。
- 暂不引入完整 Experience / GameFeature / CommonUI / 联机服务框架。
- 自建 roguelike 三件套：程序化关卡、Run 状态、Meta 进度。
- 知识库与 UE 工程双仓库隔离，Windows 主力开发，Cursor 多根工作区绑定。

## 文档索引

### 决策记录

- [0001: 技术选型基线](decisions/0001-tech-stack-selection.md)
- [0002: Windows 开发环境与双仓库协作](decisions/0002-windows-dev-environment.md)
- [0003: 从 LevelDesign/Variant_RPG 吸取经验](decisions/0003-borrow-from-leveldesign-rpg.md)

### 开发环境

- [Windows 搭建 Checklist](dev/windows-setup-checklist.md)
- [多根工作区模板](dev/MyRoguelike.code-workspace)
- [UE 工程 AGENTS.md 模板](dev/AGENTS.md.template)
- [Git LFS 规则模板](dev/gitattributes.template)

### 架构笔记

- [架构总览](architecture/overview.md)

### 实施路线

- [路线图](roadmap.md)

### 学习导读

边开发边学习：每个 roadmap 阶段都有对应的导读文件，索引了 Lyra 知识库中最相关的教程，并附上单机差异提示和项目映射说明。

- [学习导读总索引](learning/index.md)
- [Phase 1 最小阅读清单（可执行版）](learning/phase1-minimal-reading.md) — 有 UE 组件经验时推荐，跳过框架系统学习
- [Phase 0：项目初始化](learning/phase0-project-init.md)
- [Phase 1：GAS 最小技能闭环](learning/phase1-gas-skill-loop.md)
- [Phase 2：敌人与战斗房间](learning/phase2-enemy-combat-room.md)
- [Phase 3：Relic / 词条系统](learning/phase3-relic-system.md)
- [Phase 4：Run 状态管理](learning/phase4-run-manager.md)
- [Phase 5：程序化关卡生成](learning/phase5-procedural-level.md)
- [Phase 6：Meta 进度与存档](learning/phase6-meta-progress.md)

## 与 Lyra 知识库的关系

当前仓库的 `Docs/` 是 Lyra 技术学习知识库，用于理解 Lyra、GAS、Experience、GameFeature 等系统。

本目录 `MyRoguelike/` 是目标项目自己的设计文档区，用于沉淀独立 roguelike 项目的决策、架构和实施计划。

关系可以理解为：

```text
ue_lyra_kb/    = 仓库 A：学习参考 + 项目设计文档（本目录）
MyRoguelikeGame/ = 仓库 B：真实 UE 工程（Windows 上独立创建）
```

两个仓库通过 Cursor 多根工作区在编辑器层绑定，详见 [ADR 0002](decisions/0002-windows-dev-environment.md)。

## 下一步

建议先在 Windows 上完成 [开发环境搭建](dev/windows-setup-checklist.md)，再按 [路线图](roadmap.md) 从阶段 0 和阶段 1 开始：

1. 创建干净 Unreal Third Person 工程。
2. 启用 GAS 相关插件。
3. 给玩家角色接入 ASC。
4. 做出第一个可释放技能。
5. 加入冷却、消耗和伤害 GameplayEffect。

只要技能闭环没跑通，先不要扩展复杂 roguelike 系统。
