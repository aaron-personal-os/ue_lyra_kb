# Phase 5：程序化关卡生成 — 学习导读

## 本阶段目标

实现关卡的动态拼接：用 Level Streaming 将预制房间模块按规则加载组合，形成每局不同的地图结构。

## 推荐阅读清单

1. [`01-ULevel与LevelStreaming详解.md`](../../Docs/30-tutorials/ue-framework/20-world-layer/01-ULevel与LevelStreaming详解.md)
   — **本阶段最核心**。理解 `ULevelStreamingDynamic`（运行时动态加载子关卡）与 `ULevelStreamingAlwaysLoaded`（编辑器预设）的区别；动态程序化关卡使用前者。

2. [`03-异步加载FStreamableManager与RequestAsyncLoad.md`](../../Docs/30-tutorials/resource-management/03-异步加载FStreamableManager与RequestAsyncLoad.md)
   — Level Streaming 的底层依赖异步资源加载系统；理解加载完成回调的写法，以及如何避免在加载期间卡主线程。

3. [`00-UWorld详解.md`](../../Docs/30-tutorials/ue-framework/20-world-layer/00-UWorld详解.md)
   — `UWorld::LoadLevelInstanceBySoftObjectPtr` 和 `ULevelStreamingDynamic::LoadLevelInstance` 都通过 World 管理；了解 World 如何追踪所有 Streaming Level。

4. [`05-Cook与Pak打包流程.md`](../../Docs/30-tutorials/resource-management/05-Cook与Pak打包流程.md)
   — 程序化生成的房间模块需要被正确 Cook 进包；理解 PrimaryAsset 如何配置 Cook Rules，避免房间模块在打包时被剔除。

## Lyra 单机差异提示

| 文档 | 可跳过的章节 |
|------|------------|
| `ULevel与LevelStreaming详解` | `NetMode` 相关的服务器流加载权威章节、`bShouldBeVisibleOnServer` 等网络属性 |
| `UWorld详解` | 网络旅行（NetTravel）和服务端/客户端 World 差异章节 |

## 项目映射说明

**程序化关卡拼接方案（推荐）：**

- 房间模块 = 独立的 `.umap` SubLevel，每个模块有预设的出口连接点（`AConnectionPoint` Actor）。
- `LevelGeneratorSubsystem`（挂在 GameInstance）负责：
  1. 根据当前层数随机选择房间模板序列。
  2. 依次调用 `ULevelStreamingDynamic::LoadLevelInstance()` 加载房间。
  3. 通过 `AConnectionPoint` 的世界坐标计算下一个房间的偏移量，实现拼接。
  4. 玩家通关当前房间后，卸载上一个房间（`SetShouldBeLoaded(false)`），加载下一个。

- 当前层所有房间不需要同时驻留内存，可以"只保留当前 + 预加载下一个"，节省内存。

Lyra 的 World Partition 方案是大型开放世界的解决方案，**不适合房间式 roguelike**，跳过不看。

## 扩展阅读

- [`07-高级主题IO虚拟化与性能优化.md`](../../Docs/30-tutorials/resource-management/07-高级主题IO虚拟化与性能优化.md) — 若关卡加载出现卡顿，可查阅 IO 优化手段（ZenLoader、异步 IO 优先级调度）。
- [`06-GC性能优化策略.md`](../../Docs/30-tutorials/garbage-collection/06-GC性能优化策略.md) — 动态加载/卸载关卡会频繁触发 GC；了解如何控制 GC 触发时机以减少帧率抖动。
