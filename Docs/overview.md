# LyraStarterGame 项目概览

> 项目顶层概览，帮助新人快速理解项目。

## 项目简介

LyraStarterGame 是 Unreal Engine 5 的官方示例项目，展示了 UE5 的最佳实践和核心功能。

## 核心特性

- **模块化架构**：基于插件和模块的灵活架构
- **GAS 集成**：完整的数码能力系统（Gameplay Ability System）
- **体验系统**：动态的 Experience Definition 系统
- **多玩家支持**：支持单人、多人、分屏等多种模式
- **UI 框架**：基于 Common UI 的现代 UI 架构

## 技术栈

- **引擎**：Unreal Engine 5
- **编程语言**：C++ / Blueprint
- **核心系统**：GAS、StateTree、Experience、Modular Gameplay
- **UI**：Common UI、UMG

## 项目结构

```
LyraStarterGame/
├── Source/              # C++ 源码
│   ├── LyraGame/       # 核心游戏模块
│   ├── LyraExperience/ # 体验系统模块
│   └── LyraUI/         # UI 模块
├── Content/            # 内容资产
├── Plugins/            # 插件
│   ├── CommonGame/     # 通用游戏框架
│   └── CommonUI/       # 通用 UI 框架
├── Config/             # 配置文件
└── Docs/               # 项目知识库（本目录）
    ├── 00-meta/        # 元规则与学习路线
    ├── 10-architecture/ # Lyra 架构文档
    ├── 20-modules/     # Lyra 模块文档
    ├── 30-tutorials/   # ★ 技术教程系列（核心内容）
    ├── 40-runbooks/    # 操作手册
    ├── 50-references/  # 外部参考资料
    ├── 60-decisions/   # 决策记录 (ADR)
    ├── 70-topics/      # 横切主题
    ├── 80-gotchas/     # 已知坑
    └── _raw/           # 原始素材
```

## 知识库定位

本知识库定位为 **UE 技术学习知识库**：
- 结合 Lyra 示例项目和引擎源码，提供系统化的技术教程
- 按"由浅入深、先总后分"的原则组织文档
- 支持通过 AI Agent 对话快速获取技术解答
- 参见 [[00-meta/learning-paths]] 获取学习路线建议

## 快速开始

1. 安装 Unreal Engine 5
2. 克隆项目仓库
3. 生成项目文件
4. 打开 `LyraStarterGame.uproject`
5. 编译并运行

## 相关资源

- [Unreal Engine 5 官方文档](https://docs.unrealengine.com/5.0/zh-CN/)
- [Lyra 示例项目说明](https://docs.unrealengine.com/5.0/zh-CN/lyra-sample-game-in-unreal-engine/)
- [Gameplay Ability System](https://docs.unrealengine.com/5.0/zh-CN/gameplay-ability-system-for-unreal-engine/)

---
> 最后更新：2026-05-17
