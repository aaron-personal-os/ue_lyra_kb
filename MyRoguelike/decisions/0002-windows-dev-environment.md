# 0002: Windows 开发环境与双仓库协作

## 状态

已接受。

## 背景

目标项目需要长期在 Unreal Editor 中验证和制作内容。主力开发机器为 Windows（13900K + RTX 4090），Mac 仅作为可选副本，不承担常驻服务。

当前仓库 `ue_lyra_kb` 包含两部分内容：

- `Docs/`：Lyra 技术学习知识库（纯 Markdown）。
- `MyRoguelike/`：roguelike 项目的设计文档、决策记录、架构笔记和学习导读。

真实 UE 游戏工程尚未创建，但会包含大量 C++ 代码和二进制资产（`.uasset` / `.umap`），版本控制和生命周期与知识库完全不同。

曾评估过以下方案：

| 方案 | 描述 | 结论 |
|------|------|------|
| 单仓库混合 | 知识库 + UE 工程放在同一个 git 仓库 | 否决：二进制资产污染文档仓库，`.gitignore` 和 LFS 规则互相干扰 |
| Mac 托管 MCP 知识服务 | Windows 通过 MCP 远程查询 Mac 上的知识库 | 否决：同机无需网络协议；MCP 会丧失 Cursor 原生 `@引用`、全文搜索、离线能力 |
| git submodule | UE 工程把知识库作为 submodule 嵌入 | 否决：耦合度高，KB 更新需手动 bump，与 LFS 互相干扰 |
| **双仓库 + 多根工作区** | 两个独立 git 仓库，通过 Cursor 多根工作区在编辑器层绑定 | **采纳** |

## 决策

采用**双仓库 + Cursor 多根工作区**方案：

1. **仓库 A（`ue_lyra_kb`）**：知识库 + `MyRoguelike/` 设计文档，纯文本，普通 git。
2. **仓库 B（`MyRoguelikeGame`）**：真实 UE 工程，独立 git + Git LFS。
3. **工作区文件（`MyRoguelike.code-workspace`）**：放在两个仓库的公共父目录下，把 A 和 B 纳入同一个 Cursor 窗口。
4. **主力开发环境为 Windows**；Mac 退为可选副本，通过 git 同步，不承担任何常驻服务。

两个仓库之间**不需要网络/协议级通信**。同机上的"协作"通过编辑器层（多根工作区）和文档引用约定实现。

## 目录结构

> 实际父目录为 `g:\UEProjects\`（原设为 `D:\Dev\`，已按实际路径更新）

```text
g:\UEProjects\                       ← 开发父目录（Windows 本地）
├── ue_lyra_kb\                      ← 仓库 A：知识库 + 设计文档
│   ├── Docs\
│   ├── MyRoguelike\
│   │   ├── decisions\
│   │   ├── architecture\
│   │   ├── learning\
│   │   └── dev\                     ← 工作区模板、初始化脚本
│   └── .cursor\rules\
├── MyRoguelikeGame\                 ← 仓库 B：真实 UE 工程（待创建）
│   ├── Source\
│   ├── Content\
│   ├── Config\
│   ├── AGENTS.md                    ← 由 init-roguelike-git.ps1 生成
│   └── MyRoguelikeGame.uproject
└── MyRoguelike.code-workspace       ← 已生成，绑定两个仓库
```

## 三层协作机制

### 第 1 层：编辑器层（多根工作区）

通过 `.code-workspace` 文件把两个仓库纳入同一个 Cursor 窗口。打开工作区后：

- 写 UE 代码时，可用 `@知识库与设计文档/Docs/...` 直接引用 Lyra 教程。
- 全文搜索同时覆盖两个仓库。
- AI agent 同时看到功能代码和对应的学习导读。

模板文件：[`MyRoguelike/dev/MyRoguelike.code-workspace`](../dev/MyRoguelike.code-workspace)

### 第 2 层：文档引用约定

| 方向 | 引用方式 | 示例 |
|------|----------|------|
| 设计文档 → KB 教程 | 仓库 A 内部相对链接 | `../../Docs/30-tutorials/...` |
| UE 代码 → 设计文档 | 工作区路径或文档 ID | `// 设计依据：ue_lyra_kb/MyRoguelike/learning/phase1-gas-skill-loop.md` |
| UE 代码 → KB 教程 | 工作区 `@引用` 或注释中的文档 ID | 在 Cursor 中用 `@知识库与设计文档/Docs/...` |

**禁止**使用跨仓库的 `../` 物理相对路径——一旦某个仓库移动位置就会断链。

### 第 3 层：AI 规则跨仓库生效

`roguelike-learning.mdc` 的 `globs: MyRoguelike/**` 只在编辑仓库 A 的文件时触发。在仓库 B 写 UE 代码时，通过 `AGENTS.md` 引导 AI 维护学习导读。

模板文件：[`MyRoguelike/dev/AGENTS.md.template`](../dev/AGENTS.md.template)

## Git 策略

| 仓库 | 版本控制 | 远端 | 提交内容 |
|------|----------|------|----------|
| `ue_lyra_kb` | 普通 git | 私有远端（GitHub 等） | Markdown、配置、Cursor rules |
| `MyRoguelikeGame` | git + **Git LFS** | 独立私有远端 | C++ 源码、`.uasset`、`.umap`、配置 |

两个仓库**各自独立**：独立的 git 历史、独立的远端、独立的 `.gitignore`。通过 `git pull` / `git push` 在 Windows 和 Mac 之间同步。

### Git LFS 必配扩展名（仓库 B）

```gitattributes
*.uasset filter=lfs diff=lfs merge=lfs -text
*.umap filter=lfs diff=lfs merge=lfs -text
*.ubulk filter=lfs diff=lfs merge=lfs -text
*.uexp filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
*.wav filter=lfs diff=lfs merge=lfs -text
*.fbx filter=lfs diff=lfs merge=lfs -text
```

在创建 UE 工程、产生任何二进制资产之前就配好 LFS，不要事后补救。

## Windows 迁移 Checklist

完整步骤见 [`MyRoguelike/dev/windows-setup-checklist.md`](../dev/windows-setup-checklist.md)。

概要（实际路径 `g:\UEProjects\`）：

1. Windows 安装 UE 5.7（已完成前置）。
2. 安装 Git + Git LFS（已就绪：git 2.50、git-lfs 3.7）。
3. 父目录 `g:\UEProjects\` 已存在，仓库 A 已位于其中。
4. 在 UE 中创建 Third Person C++ 工程到 `g:\UEProjects\MyRoguelikeGame\`。
5. 启用 GameplayAbilities / GameplayTags / GameplayTasks 插件。
6. 运行 `init-roguelike-git.ps1` 初始化仓库 B 的 git + LFS 并首次提交。
7. `MyRoguelike.code-workspace` 已生成于 `g:\UEProjects\`。
8. `AGENTS.md` 由初始化脚本写入 `g:\UEProjects\MyRoguelikeGame\`。
9. 用 Cursor 打开 `g:\UEProjects\MyRoguelike.code-workspace` 开始工作。
10. Mac 上 `git pull` 同步知识库（可选，非必须）。

## Mac 特化配置的处置

之前在 Mac 上为 Remote Execution 做的特化配置，迁到 Windows 后不再需要主动维护：

| 文件 | Mac 特化内容 | Windows 处置 |
|------|-------------|-------------|
| `Config/DefaultEngine.ini` | `RemoteExecutionMulticastBindAddress=0.0.0.0` | Windows 默认 `127.0.0.1` 即可，可保留也可清理 |
| `.ue-py-config.json` | `multicast_bind_address` | 仓库 A 的配置，不影响仓库 B |
| `ue_python.py` | `platform.system() == 'Darwin'` 分支 | 自动走 Windows 路径，无需改动 |

这些配置留在仓库 A 中不影响 Windows 工作。如果未来需要在 Windows 上用 Remote Execution 驱动 UE，重新按 Windows 环境配置即可。

## 风险与权衡

### 两个仓库的同步节奏

知识库（仓库 A）和 UE 工程（仓库 B）的提交节奏不同。设计文档可能在功能实现之前就写好，也可能在实现后补充。

缓解方式：不强制两边同步提交。设计文档在仓库 A 独立演进，UE 代码在仓库 B 独立演进。通过工作区 `@引用` 和注释中的文档 ID 建立关联。

### 学习导读的跨仓库维护

在仓库 B 写代码时，`roguelike-learning.mdc` 不会自动触发。

缓解方式：仓库 B 的 `AGENTS.md` 明确要求 AI 在引用 KB 内容时检查并更新仓库 A 的 `MyRoguelike/learning/` 导读文件。

### Git LFS 配额

GitHub 免费账户 LFS 存储 1 GB、带宽 1 GB/月。独立 roguelike 早期体量通常够用；若超出，考虑自建 Git LFS 服务器或迁移到 Perforce。

## 后续触发条件

满足以下任一条件时，重新评估当前方案：

- 需要在多台机器上同时编辑 UE 工程（考虑 Perforce 锁文件机制）。
- 知识库需要语义/向量检索能力（考虑在 Windows 本地跑带 embedding 的 MCP 知识服务）。
- 需要在 CI/CD 中自动构建和测试（工作区方案不影响 CI，但需确保构建机能访问两个仓库）。

## 结论

主力开发全部在 Windows 上进行。知识库和 UE 工程物理隔离、git 各管各的，通过 Cursor 多根工作区在编辑器层"合体"。Mac 退为可选副本，不承担任何常驻服务。MCP 留给未来"操作 UE 引擎"的自动化场景，不用于查文档。
