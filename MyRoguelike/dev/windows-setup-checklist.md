# Windows 开发环境搭建 Checklist

按顺序执行。每步完成后打勾。

## 前置准备

- [x] Windows 上安装 **Unreal Engine 5.7**（与知识库参考版本一致）
- [x] 安装 **Git**（已安装：git 2.50.1）
- [x] 安装 **Git LFS**（已安装：git-lfs 3.7.0，执行过 `git lfs install`）
- [ ] 安装 **Cursor**（https://cursor.com）
- [ ] 安装 **Visual Studio 2022**（含"使用 C++ 的游戏开发"工作负载）

## 目录与仓库

> 实际父目录为 `g:\UEProjects\`（非文档原设的 `D:\Dev\`）

- [x] 知识库仓库已位于 `g:\UEProjects\ue_lyra_kb\`
- [ ] 在 UE 中创建 **Third Person（C++）** 模板工程，保存到 `g:\UEProjects\MyRoguelikeGame\`
- [ ] 在 UE 工程中启用插件：**GameplayAbilities**、**GameplayTags**、**GameplayTasks**
- [ ] 初始化 UE 工程的 git 仓库（创建工程后运行 `init-roguelike-git.ps1`）
  ```powershell
  cd g:\UEProjects
  powershell -ExecutionPolicy Bypass -File ue_lyra_kb\MyRoguelike\dev\init-roguelike-git.ps1
  ```
- [ ] 首次提交并推到独立远端
  ```powershell
  cd g:\UEProjects\MyRoguelikeGame
  git remote add origin <你的远端地址>
  git push -u origin main
  ```

## 工作区配置

- [x] 工作区文件已生成：`g:\UEProjects\MyRoguelike.code-workspace`
- [ ] AGENTS.md 由初始化脚本写入 UE 工程根目录（运行脚本后自动完成）
- [ ] 用 Cursor 打开 `g:\UEProjects\MyRoguelike.code-workspace`
- [ ] 确认两个文件夹都出现在侧边栏："知识库与设计文档" 和 "UE 工程"
- [ ] 测试 `@知识库与设计文档/Docs/` 引用是否可用

## 验证

- [ ] UE 工程能在编辑器中正常打开和编译
- [ ] 第三人称角色能在 PIE 中移动
- [ ] Cursor 中全文搜索能同时覆盖两个仓库
- [ ] 在 UE 工程中问 AI 一个 GAS 相关问题，确认它能引用知识库内容

## Mac 同步（可选）

- [ ] Mac 上 `git pull` 同步知识库仓库（`g:\UEProjects\ue_lyra_kb` 对应远端）
- [ ] Mac 不再承担任何常驻服务或 MCP 知识服务

## 开始开发

完成以上步骤后，按 [路线图](../roadmap.md) 从 **阶段 0** 和 **阶段 1** 开始：

1. 给玩家角色接入 ASC。
2. 做出第一个可释放技能。
3. 加入冷却、消耗和伤害 GameplayEffect。

开发前阅读对应阶段的学习导读：[learning/index.md](../learning/index.md)
