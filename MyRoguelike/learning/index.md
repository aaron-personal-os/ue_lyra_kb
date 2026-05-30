# 学习导读索引

每次对话中涉及 Lyra KB 内容时，AI 会自动将相关文档链接追加到对应阶段的导读文件中。本文件是所有阶段的总入口。

## 使用方式

1. **开发某个阶段前** → 打开对应的 `phaseN-*.md`，按推荐顺序阅读，了解背后机制。
2. **已有 UE 组件经验、想直接做 GAS** → 看 [phase1-minimal-reading.md](phase1-minimal-reading.md)（跳过框架系统学习）。
3. **不确定去哪查** → 在本文件搜索关键词，找到对应阶段入口。
4. **对话涉及新 KB 内容** → AI 会自动追加到对应阶段，无需手动维护。

## 快速入口

| 场景 | 文档 |
|------|------|
| 直接做 GAS 技能闭环 | [phase1-minimal-reading.md](phase1-minimal-reading.md) |
| Phase 1 完整导读 + LevelDesign 借鉴 | [phase1-gas-skill-loop.md](phase1-gas-skill-loop.md) |

## 阶段导读

| 阶段 | 文件 | 状态 | 核心主题 |
|------|------|------|----------|
| Phase 0 | [phase0-project-init.md](phase0-project-init.md) | 预填充 | 工程初始化、GameMode、Enhanced Input |
| Phase 1 | [phase1-gas-skill-loop.md](phase1-gas-skill-loop.md) | 已更新 | GAS、ASC、AbilitySet、技能释放；LevelDesign 技能字段/命中时序借鉴 |
| Phase 2 | [phase2-enemy-combat-room.md](phase2-enemy-combat-room.md) | 已更新 | AI 行为、AActor 生命周期、战斗房间；LevelDesign 激进测试 AI 借鉴 |
| Phase 3 | [phase3-relic-system.md](phase3-relic-system.md) | 已更新 | DataAsset、PrimaryAsset、Relic 构筑；LevelDesign 手动叠加反面参照 |
| Phase 4 | [phase4-run-manager.md](phase4-run-manager.md) | 预填充 | GameInstance、RunState、局内状态管理 |
| Phase 5 | [phase5-procedural-level.md](phase5-procedural-level.md) | 预填充 | Level Streaming、异步加载、程序化关卡 |
| Phase 6 | [phase6-meta-progress.md](phase6-meta-progress.md) | 预填充 | 存档、Meta 进度、GC 与资源管理 |

## 维护协议（供 AI 参考）

- 对话中深入引用某篇 `Docs/` 文档时，追加到对应阶段文件，不批量追加整个系列。
- 追加格式：`` - [`文件名`](../../Docs/路径/文件名.md) — 一句话说明目的 ``
- 无法确定阶段时，追加到下方"待分配"区。
- 追加后同步更新本文件对应阶段的"状态"列为"已更新"。

## 待分配

> 以下内容在对话中被引用，但尚未确定归属阶段，待整理后移入对应导读文件。

（暂无）
