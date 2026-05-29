---
id: 60-decisions/0001-knowledge-base-web-app
type: adr
status: proposed
language: zh
owner: human
decided_at: 2026-05-18
decided_by: robert
anchors: []
supersedes: []
superseded_by: []
related:
  - "[[00-meta/learning-paths]]"
  - "[[30-tutorials/README]]"
  - "[[60-decisions/0003-dev-only-web-terminal]]"
sources: []
last_synced: 2026-05-18
last_verified: 2026-05-18
tags: [adr, web-app, astro, tutorials, interactive-teaching]
---

# ADR-0001：知识库教学演示 Web 应用

> 采用 Astro 5 + React Islands 方案，构建本地交互式教学演示应用，直接解析 `Docs/30-tutorials/` 的 Markdown 和 `_series.yaml`。

## 背景 (Context)

项目知识库 `Docs/30-tutorials/` 已积累 13 个系列、134 篇深度技术教程。当前只能通过 IDE 或纯文本方式阅读 Markdown，存在以下痛点：

1. **无交互式教学体验** — 执行流程、生命周期等概念缺乏步进动画演示
2. **无系列导航** — `_series.yaml` 定义了学习路径但无法可视化呈现
3. **无进度追踪** — 无法知道自己学到了哪里
4. **阅读体验一般** — 纯 Markdown 渲染缺乏精美排版和视觉层次

需要一个本地 Web 应用，将现有 Markdown 教程转化为交互式教学页面。

## 决策 (Decision)

### 技术方案：Astro 5 + React Islands

- **框架**：Astro 5.x（Content Collections 直接读取 Docs/ 目录）
- **交互组件**：React 19（Islands 架构，按需水合）
- **样式**：Tailwind CSS 4
- **代码高亮**：Shiki（Astro 内置）
- **动画**：Framer Motion
- **图表**：Mermaid
- **搜索**：Pagefind（客户端离线搜索）
- **字体**：Inter + Noto Sans SC
- **包管理**：pnpm

### 核心设计

1. **零迁移** — Astro Content Collections 通过 `glob({ base: '../../Docs/30-tutorials' })` 直接读取现有文件，不移动、不复制、不修改
2. **类型安全** — Zod schema 验证 `_series.yaml` 和 frontmatter
3. **Islands 性能** — 页面默认纯静态 HTML，交互组件按需加载 JS
4. **沉浸阅读** — 浮动双侧栏可收缩隐藏，正文最大化
5. **精美 Hero** — 每篇教程顶部渐变首屏，展示系列徽章、难度、进度
6. **一键部署** — 跨平台脚本（macOS + Windows）

### 页面路由

| 路径 | 内容 |
|---|---|
| `/` | 首页 + 学习路线图 |
| `/series/:slug` | 系列概览（从 `_series.yaml` 生成） |
| `/series/:slug/:lesson` | 教程正文 + 交互组件 |
| `/search` | 全文搜索 |

### 交互组件（Islands）

| 组件 | 功能 | 技术 |
|---|---|---|
| CodeBlock | C++ 源码折叠/展开 + 高亮 | React + Shiki |
| StepAnimation | 执行流程步进动画 | React + Framer Motion |
| Quiz | 选择题/填空 + 即时反馈 | React |
| MermaidDiagram | Mermaid 块渲染为 SVG | React + Mermaid |
| ProgressTracker | 系列学习进度条 | React + localStorage |
| Search | 全文搜索 | Pagefind |

### 页面布局

```text
┌──────────────────────────────────────────┐
│  Navbar (series tabs + search)           │
├──────┬────────────────────────────┬──────┤
│ Side │  Hero (gradient + meta)    │ TOC  │
│ bar  │  ────────────────────────  │      │
│(float│  Content (3-layer teach)   │(float│
│ able)│  Interactive widgets       │ able)│
│      │  Prev/Next navigation      │      │
└──────┴────────────────────────────┴──────┘
```

- 左侧栏：系列导航树 + 进度条，可收缩
- 右侧栏：TOC 目录，可收缩
- 收缩行为：点击按钮 / 键盘 `[` `]` / viewport < 1024px 自动收缩
- 收缩态：极细导轨 (4px) + hover 预览
- 状态持久化：localStorage

### 项目文件结构

```text
LyraStarterGame/
├── Docs/                       ← 现有知识库（不动）
│   └── 30-tutorials/           ← 核心内容源
│
├── web-app/                    ← ★ 新建 Web 应用
│   ├── package.json
│   ├── astro.config.mjs
│   ├── tsconfig.json
│   ├── setup.sh / setup.bat    ← 一键安装
│   ├── start.sh / start.bat    ← 一键启动
│   │
│   ├── src/
│   │   ├── content/
│   │   │   └── config.ts       ← Content Collections 定义
│   │   ├── layouts/
│   │   │   ├── BaseLayout.astro
│   │   │   └── TutorialLayout.astro
│   │   ├── pages/
│   │   │   ├── index.astro
│   │   │   ├── series/[slug].astro
│   │   │   ├── series/[slug]/[lesson].astro
│   │   │   └── search.astro
│   │   ├── components/
│   │   │   ├── layout/         ← Navbar, Sidebar, TOC, Hero
│   │   │   ├── interactive/    ← CodeBlock, StepAnimation, Quiz...
│   │   │   └── ui/             ← Badge, Button, Card
│   │   ├── lib/
│   │   │   ├── series.ts       ← _series.yaml 解析器
│   │   │   ├── progress.ts     ← localStorage 进度 API
│   │   │   └── theme.ts        ← 系列配色主题
│   │   └── styles/
│   │       ├── global.css
│   │       ├── typography.css  ← CJK 优化排版
│   │       └── code-theme.css
│   │
│   ├── public/fonts/
│   ├── plugins/
│   │   └── remark-wiki-links.ts ← [[wikilink]] 解析
│   └── scripts/
│       └── check-env.js        ← 跨平台环境检测
│
└── Docs/60-decisions/
    └── 0001-knowledge-base-web-app.md  ← 本文档
```

### 一键化脚本

#### 安装脚本 (`setup.sh` / `setup.bat`)

1. 检测 Node.js ≥ 18（未安装则提示下载链接）
2. 检测 pnpm（未安装则自动 `npm install -g pnpm`）
3. 执行 `pnpm install`
4. 打印成功 + 启动提示

#### 启动脚本 (`start.sh` / `start.bat`)

1. 检测依赖是否已安装（未安装先触发 setup）
2. 启动 Astro dev server
3. 自动打开默认浏览器（macOS: `open`, Windows: `start`）
4. 终端显示访问地址

#### 跨平台策略

| 关注点 | 方案 |
|---|---|
| Shell 差异 | `.sh`（bash）+ `.bat`（cmd），逻辑对称 |
| 核心检测 | `scripts/check-env.js`（Node.js 跨平台） |
| 路径 | 脚本用相对路径，Node 层用 `path.resolve()` |
| 浏览器打开 | macOS: `open`, Windows: `start` |
| 编码 | `.bat` 使用 UTF-8 BOM |

### 交互组件触发机制

交互组件通过 **Markdown 中的特定代码块标记** 触发，不需要修改现有 md 格式：

| 组件 | 触发方式 | 示例 |
|---|---|---|
| CodeBlock | 标准 ` ```cpp ``` ` 代码块自动增强 | 自动折叠超过 15 行的代码块 |
| MermaidDiagram | ` ```mermaid ``` ` 代码块自动渲染 | 现有 mermaid 块零改动 |
| StepAnimation | ` ```steps ``` ` 自定义代码块 | 新标记，需要教程中添加 |
| Quiz | ` ```quiz ``` ` 自定义代码块 | 新标记，需要教程中添加 |
| ProgressTracker | 自动（页面加载即记录） | 无需任何标记 |
| Search | 独立页面 | 无需标记 |

**原则**：现有 md 内容**不改动**即可获得 CodeBlock 和 Mermaid 增强。StepAnimation 和 Quiz 作为新增教学元素，后续按需在教程中添加对应标记。

### 范围界定

#### MVP (Phase 1)

- `30-tutorials/` 目录完整解析渲染
- `_series.yaml` 驱动导航和进度
- 全部 6 个交互组件
- 一键安装 + 启动脚本
- 浮动侧栏 + Hero 首屏

#### Phase 2 (预留扩展)

- 其他 Docs 目录（10-architecture, 20-modules 等）— Content Collection 定义已预留
- Web Terminal（xterm.js + node-pty + WebSocket）— Astro SSR 模式支持
- 知识图谱可视化

## 备选方案 (Alternatives)

### 方案 A：VitePress + Vue

- **优点**：启动最快（5 min），Vite 极速 HMR，Vue SFC 开发体验好
- **缺点**：需自写 `_series.yaml` 插件，交互组件生态不如 React，无原生 YAML 支持
- **拒绝理由**：对 `_series.yaml` 的原生支持不如 Astro，且后期加 Terminal 需要额外后端进程

### 方案 B：Docusaurus + MDX + React

- **优点**：社区最大，插件最多，MDX 强大，versioning / i18n 开箱即用
- **缺点**：Webpack 较慢 HMR，现有 md 需迁移为 MDX，配置复杂
- **拒绝理由**：需要格式迁移（破坏零侵入原则），HMR 体验不如 Vite，Webpack 增加复杂度

## 后果 (Consequences)

### 正面

- 现有教程零迁移即可获得精美展示
- 交互式教学大幅提升学习效率
- 进度追踪让学习有方向感
- Islands 架构保证性能（首屏 < 100ms）
- 一键脚本降低使用门槛
- 未来可平滑升级到 SSR 模式支持终端

### 负面 / 代价

- 新增 `web-app/` 目录及 Node.js 依赖
- 需要学习 Astro 框架
- 交互组件（StepAnimation、Quiz）需要在 md 中添加特定标记才能触发
- 初始开发工作量约 3-5 天

### 中性影响

- 项目新增 Node.js 技术栈（原本纯 C++/Blueprint）
- 知识库同时有 markdown 源和 web 渲染两种阅读方式

## 验证 (Validation)

- **MVP 验证**：完成 1 个系列（如 GAS 前 3 课）的完整渲染，确认交互组件工作正常
- **性能验证**：134 篇文档全部加载，dev server 启动 < 3s，HMR < 500ms
- **跨平台验证**：在 macOS 和 Windows 上分别测试一键脚本
- **Review 时机**：MVP 完成后，评估是否需要调整组件设计或扩展范围

## 相关页面

- [[00-meta/learning-paths]] — 学习路线定义
- [[30-tutorials/README]] — 教程目录总览

---
> 最后更新：2026-05-18

<!-- nav:auto -->

---

**导航**: ← [[60-decisions/0000-template|0000-template]] · [[60-decisions/0002-web-app-ui-enhancements|0002-web-app-ui-enhancements]] →

<!-- /nav:auto -->
