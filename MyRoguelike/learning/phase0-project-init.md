# Phase 0：项目初始化 — 学习导读

## 本阶段目标

从干净 Unreal Third Person 模板工程出发，建立 GAS 插件、基础 C++ 角色类和输入绑定，让角色能在编辑器里正常运行。

## 推荐阅读清单

按此顺序阅读，建立整体框架感后再动手配置。

1. [`00-UE引擎层详解.md`](../../Docs/30-tutorials/ue-framework/10-engine-layer/00-UE引擎层详解.md)
   — 了解 UEngine / UGameInstance / UWorld 的层级关系，明白"游戏从哪里启动"。

2. [`01-UGameInstance详解.md`](../../Docs/30-tutorials/ue-framework/10-engine-layer/01-UGameInstance详解.md)
   — GameInstance 是单次游戏会话的全局容器，后续 RunManager 会挂在这里；提前理解生命周期。

3. [`00-AGameModeBase详解.md`](../../Docs/30-tutorials/ue-framework/30-gamemode-layer/00-AGameModeBase详解.md)
   — 初始化阶段需要配置 GameMode，明白它负责"哪种规则"的裁决。

4. [`01-EnhancedInput系统概览.md`](../../Docs/30-tutorials/input-system/01-EnhancedInput系统概览.md)
   — Enhanced Input 是 UE5 标准输入方案；在 Phase 0 结束前需要确认是否启用。

5. [`02-InputActions与MappingContext配置详解.md`](../../Docs/30-tutorials/input-system/02-InputActions与MappingContext配置详解.md)
   — 配置 InputAction 资产和 MappingContext，理解输入绑定的数据驱动结构。

## Lyra 单机差异提示

| 文档 | 可跳过的章节 |
|------|------------|
| `AGameModeBase详解` | 多人 Login/Logout 流程、SpawnDefaultPawnFor 的服务器权威逻辑 |
| `UGameInstance详解` | 旅行（Seamless Travel）与多人会话管理章节 |

## 项目映射说明

- Lyra 用 `ALyraGameMode` + `ULyraExperienceDefinition` 来动态加载玩法配置。本项目**直接用标准 AGameMode**，不引入 Experience System，省去大量初始化开销。
- Enhanced Input 完全可用于单机，不涉及任何网络复制；Lyra 对 InputTag 的封装方式是值得借鉴的命名约定。

## 扩展阅读

- [`00-UWorld详解.md`](../../Docs/30-tutorials/ue-framework/20-world-layer/00-UWorld详解.md) — 理解 World 如何持有 Level 和 Actor，为后续 Level Streaming 打基础。
- [`00-UE5输入系统系列概览.md`](../../Docs/30-tutorials/input-system/00-UE5输入系统系列概览.md) — 系列总览，快速定位想深入的章节。
