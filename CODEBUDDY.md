# LyraStarterGame 项目

<!-- BEGIN project-wiki:schema-summary -->
本项目维护 `Docs/` 下的内部知识库（基于 [karpathy/llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 思路工程化扩展）。

**执行任何任务前必须遵守：**
先加载Skill **project-wiki**  读取Skill内容，了解项目知识库机制，**严格**按照其内容执行。

## 知识库核心约束

1. **检索优先级**：`Docs/index.md` → `Docs/overview.md` → frontmatter → 全文搜索
2. **先读后写**：任何任务前，先读取相关 wiki 页面
3. **保持同步**：代码变更后，同步更新 wiki
4. **标注状态**：及时标记页面的 `status`（current/stale/deprecated）
5. **教学优先**：回答技术问题时优先引用 `30-tutorials/` 系列教程

## 必读文件

- `Docs/00-meta/ai-playbook.md` - AI 协作硬约束
- `Docs/overview.md` - 项目顶层概览
- `Docs/.wiki-schema.md` - 知识库 schema
- `Docs/index.md` - 知识库全量目录
- `Docs/00-meta/learning-paths.md` - 学习路线总览

<!-- END project-wiki:schema-summary -->

## Web 应用开发

当用户任务涉及 `web-app/` 目录（页面、组件、样式、配置、terminal-server）时：
先加载 Skill **web-app-dev**，了解 Web 应用架构和编码规范，按照其工作流执行开发任务。

## 项目简介

LyraStarterGame 是 Unreal Engine 5 的官方示例项目，展示了 UE5 的最佳实践和核心功能。

## 技术栈

- **引擎**：Unreal Engine 5
- **编程语言**：C++ / Blueprint
- **核心系统**：GAS、StateTree、Experience、Modular Gameplay
- **UI**：Common UI、UMG

**重要： 通过执行脚本 get_engine_root.bat / get_engine_root.sh 可以获取项目关联的UE引擎源码根目录**

## 项目结构

```
LyraStarterGame/
├── Source/              # C++ 源码
├── Content/            # 内容资产
├── Plugins/            # 插件
├── Config/             # 配置文件
└── Docs/               # 项目知识库
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



## 相关资源

- [Unreal Engine 5 官方文档](https://docs.unrealengine.com/5.0/zh-CN/)
- [Lyra 示例项目说明](https://docs.unrealengine.com/5.0/zh-CN/lyra-sample-game-in-unreal-engine/)
