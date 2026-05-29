# Windows 开发环境搭建 Checklist

按顺序执行。每步完成后打勾。

## 前置准备

- [ ] Windows 上安装 **Unreal Engine 5.7**（与知识库参考版本一致）
- [ ] 安装 **Git**（https://git-scm.com/download/win）
- [ ] 安装 **Git LFS**（`git lfs install`）
- [ ] 安装 **Cursor**（https://cursor.com）
- [ ] 安装 **Visual Studio 2022**（含"使用 C++ 的游戏开发"工作负载）

## 目录与仓库

- [ ] 创建开发父目录，例如 `D:\Dev\`
- [ ] Clone 知识库仓库到 `D:\Dev\ue_lyra_kb\`
  ```powershell
  cd D:\Dev
  git clone <你的远端地址> ue_lyra_kb
  ```
- [ ] 在 UE 中创建 **Third Person** 模板工程，保存到 `D:\Dev\MyRoguelikeGame\`
- [ ] 在 UE 工程中启用插件：**GameplayAbilities**、**GameplayTags**、**GameplayTasks**
- [ ] 初始化 UE 工程的 git 仓库
  ```powershell
  cd D:\Dev\MyRoguelikeGame
  git init
  git lfs install
  ```
- [ ] 创建 `.gitattributes`（LFS 规则，见 ADR 0002）
- [ ] 创建 `.gitignore`（可用 UE 官方模板或从 Lyra 知识库参考）
- [ ] 首次提交并推到独立远端
  ```powershell
  git add .
  git commit -m "Initial UE project setup"
  git remote add origin <你的远端地址>
  git push -u origin main
  ```

## 工作区配置

- [ ] 复制工作区模板到父目录
  ```powershell
  copy D:\Dev\ue_lyra_kb\MyRoguelike\dev\MyRoguelike.code-workspace D:\Dev\
  ```
- [ ] 复制 AGENTS.md 模板到 UE 工程根目录
  ```powershell
  copy D:\Dev\ue_lyra_kb\MyRoguelike\dev\AGENTS.md.template D:\Dev\MyRoguelikeGame\AGENTS.md
  ```
- [ ] 用 Cursor 打开 `D:\Dev\MyRoguelike.code-workspace`
- [ ] 确认两个文件夹都出现在侧边栏："知识库与设计文档" 和 "UE 工程"
- [ ] 测试 `@知识库与设计文档/Docs/` 引用是否可用

## 验证

- [ ] UE 工程能在编辑器中正常打开和编译
- [ ] 第三人称角色能在 PIE 中移动
- [ ] Cursor 中全文搜索能同时覆盖两个仓库
- [ ] 在 UE 工程中问 AI 一个 GAS 相关问题，确认它能引用知识库内容

## Mac 同步（可选）

- [ ] Mac 上 `git pull` 同步知识库仓库
- [ ] Mac 不再承担任何常驻服务或 MCP 知识服务

## 开始开发

完成以上步骤后，按 [路线图](../roadmap.md) 从 **阶段 0** 和 **阶段 1** 开始：

1. 给玩家角色接入 ASC。
2. 做出第一个可释放技能。
3. 加入冷却、消耗和伤害 GameplayEffect。

开发前阅读对应阶段的学习导读：[learning/index.md](../learning/index.md)
