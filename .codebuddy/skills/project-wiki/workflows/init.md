# 工作流：init（初始化项目知识库）

## 前置检查

1. 检查`<项目根目录>`是否已有 `Docs/.wiki-schema.md`
   - 已有 → 提示"项目知识库已存在，是否重新初始化？（默认否）"
2. 若用户确认重新初始化 → `git mv Docs Docs.bak.<YYYYMMDD>`，再继续

## 步骤

### 1. 生成 `Docs/` 完整目录骨架

按下列结构创建（**所有目录用 `.gitkeep` 占位**，确保 git 可追踪）：

```
Docs/
├── .wiki-schema.md
├── README.md
├── index.md
├── log.md
├── overview.md
├── 00-meta/
│   ├── conventions.md
│   ├── glossary.md
│   ├── workflows.md
│   ├── ai-playbook.md
│   └── learning-paths.md
├── 10-architecture/
│   ├── .gitkeep
│   ├── subsystems/.gitkeep
│   └── data-flow/.gitkeep
├── 20-modules/
│   ├── cpp/.gitkeep
│   ├── blueprint/.gitkeep
│   ├── data-tables/.gitkeep
│   └── assets/.gitkeep
├── 30-tutorials/.gitkeep
├── 40-runbooks/.gitkeep
├── 50-references/
│   ├── ue-official/.gitkeep
│   ├── third-party/.gitkeep
│   └── articles/.gitkeep
├── 60-decisions/
│   ├── .gitkeep
│   └── 0000-template.md
├── 70-topics/.gitkeep
├── 80-gotchas/.gitkeep
├── 90-snapshots/.gitkeep
└── _raw/
    ├── meetings/.gitkeep
    ├── chats/.gitkeep
    ├── specs/.gitkeep
    └── external/.gitkeep
```

### 2. 写入核心入口文件

按当前 skill 内置的模板（见 `templates/` 与下方"内置文件内容"）写入：

- `Docs/.wiki-schema.md` — 见本仓库 `.codebuddy/skills/project-wiki/templates/schema-seed.md`
- `Docs/README.md` — 给人看的入口
- `Docs/index.md` — 空目录，含分类占位
- `Docs/log.md` — append-only 日志，含一条 init 记录
- `Docs/overview.md` — 顶层概览占位

### 3. 写入 `00-meta/` 元规则

- `conventions.md` — 命名/分支/编码约定（先占位 + 已知规则种子）
- `glossary.md` — 术语表（预填 LyraStarterGame 项目已知术语种子）
- `workflows.md` — 开发/测试/发布工作流（占位）
- `ai-playbook.md` — **AI 协作硬约束**（最关键，写完整）
- `learning-paths.md` — 学习路径索引（按主题组织教程与参考的推荐阅读顺序）

### 4. 写入 60-decisions/0000-template.md

提供 ADR 模板让用户照抄。

### 5. 同步 schema 摘要到 agent 入口

把 `Docs/.wiki-schema.md` 中**最关键的 4 条 AI 必读约束**（来自 `ai-playbook.md`）以注入区块的形式写入项目根的 `CODEBUDDY.md`：

```markdown
<!-- BEGIN project-wiki:schema-summary -->
本项目维护 `Docs/` 下的内部知识库（基于 [karpathy/llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 思路工程化扩展）。

**执行任何任务前必须遵守：**
先加载Skill   **project-wiki** 读取Skill内容，了解项目知识库机制，**严格**按照其内容执行。

<!-- END project-wiki:schema-summary -->
```



### 6. 输出引导

```
LyraStarterGame 项目知识库已初始化：Docs/

骨架已生成，但具体内容是空的。下一步建议：

1. 跑一遍 ingest，让我把现有 Source/LyraGame/ 扫一遍写出 10-architecture/overview.md
2. 也可以直接给我 spec / 会议记录 / PR 链接，说"消化进项目知识库"
3. 用 Obsidian 打开 Docs/ 文件夹，实时看 wiki 构建效果

```

## 幂等性

- 若 `Docs/` 已存在且 `.wiki-schema.md` 完整 → 提示用户、不动文件
- 若 `Docs/` 存在但缺关键文件 → 仅补齐缺失项，不覆盖现有内容
- 写 `CODEBUDDY.md` 注入区块前，先查是否已有同名 marker，有则 in-place 更新
