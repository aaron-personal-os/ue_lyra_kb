---
name: web-app-dev
version: 1.0.0
description: 知识库 Web 应用开发 Skill。让 AI Agent 快速掌握 web-app/ 的架构、组件体系和编码规范，高效执行前端开发任务。
trigger: 当用户任务涉及 web-app/ 目录下的代码（页面、组件、样式、配置、terminal-server）时自动加载。
---

# web-app-dev — 知识库 Web 应用开发

> 让 AI Agent 在 10 秒内掌握 web-app 项目上下文，直接进入开发状态。

## 30 秒速览

```
技术栈：Astro 5 + React 19 Islands + Tailwind CSS 4 + TypeScript
架构：  静态优先（Islands 按需水合），Content Collections 直读 Docs/30-tutorials/
端口：  4321（Astro dev）· 4322（terminal-server, dev-only）
包管理：pnpm 9
```

```text
web-app/
├── astro.config.mjs          ← Astro 配置（remarkPlugins、aliases、Shiki）
├── src/
│   ├── content.config.ts     ← Content Collections（glob Docs/30-tutorials/）
│   ├── layouts/              ← BaseLayout · TutorialLayout
│   ├── pages/                ← index · series/[slug] · series/[slug]/[...lesson] · search
│   ├── components/
│   │   ├── interactive/      ← React Islands（PresentationMode、TerminalPanel、CodeBlock…）
│   │   ├── layout/           ← Astro 组件（Navbar、FloatingSidebar、Hero、TOC）
│   │   └── ui/               ← 原子 UI 组件（Badge）
│   ├── lib/                  ← 工具函数（series.ts、theme.ts、progress.ts）
│   ├── plugins/              ← Remark 插件（remark-mermaid、remark-wiki-links）
│   └── styles/               ← global.css · typography.css · presentation.css · terminal.css
├── public/
│   ├── fonts/
│   └── vendor/reveal/        ← reveal.js CSS（避免 package exports 问题）
└── terminal-server/          ← Dev-only PTY bridge（独立 package.json）
    ├── index.mjs
    └── package.json          ← ws + node-pty
```

## 架构约束（硬规则）

1. **Islands 最小化** — 只有需要客户端交互的功能才用 React Island；布局/排版用 Astro
2. **内容源不动** — Markdown 活在 `Docs/30-tutorials/`，web-app 通过 glob 读取，绝不复制
3. **Dev-only 隔离** — TerminalPanel 用 `import.meta.env.DEV` 守卫；terminal-server/ 不进 `web-app/package.json`
4. **无全局状态库** — 使用 localStorage + HTML `data-*` 属性 + 自定义事件
5. **CSS 变量驱动主题** — 颜色系统在 `global.css` 定义，系列主题由 `lib/theme.ts` 注入
6. **静态构建** — 不使用 SSR/hybrid 模式，`astro build` 输出纯静态文件

## 每次会话必读

| 顺序 | 文件 | 获得的信息 |
|------|------|-----------|
| 1 | `reference/architecture.md` | 架构全貌、技术栈、数据流 |
| 2 | `reference/conventions.md` | 编码规范、状态管理、样式系统 |
| 3 | `reference/component-catalog.md` | 现有组件清单（避免重复造轮子） |

## 工作流路由

> 根据用户意图，读取对应工作流文件

### 开发任务

| 用户意图 | 工作流 | 文件 |
|---------|--------|------|
| "新增 XX 页面"、"加个 XX 功能"、"实现 XX" | **implement** | `workflows/implement.md` |
| "XX 不显示"、"修复 XX bug"、"为什么 XX 不工作" | **fix-bug** | `workflows/fix-bug.md` |
| "新建一个 XX 组件"、"把 XX 改成 YY"、"加个 Island" | **component** | `workflows/component.md` |
| "调整 XX 样式"、"XX 太宽了"、"改下 XX 的颜色" | **style** | `workflows/style.md` |
| "优化 XX"、"重构 XX"、"拆分 XX 组件" | **refactor** | `workflows/refactor.md` |

### 默认规则

- 涉及新页面/路由 → **implement**
- 涉及视觉表现但不改逻辑 → **style**
- 涉及某个组件但不是纯样式 → **component**
- 报 bug / 某功能失效 → **fix-bug**
- "性能"/"拆分"/"解耦" → **refactor**
- 不确定 → 先读 `reference/architecture.md` 定位涉及文件，再选 workflow

## 通用前置检查

每个 workflow 执行前：

1. 确认 `web-app/package.json` 存在（项目已初始化）
2. 读取 `reference/architecture.md` 了解文件结构
3. 读取 `reference/conventions.md` 了解编码规范
4. 如果涉及现有组件 → 先读 `reference/component-catalog.md` 确认是否已有类似实现
5. 如果涉及已知坑点 → 读 `reference/gotchas.md`

## 关联 ADR

- `Docs/60-decisions/0001-knowledge-base-web-app.md` — 基础架构决策
- `Docs/60-decisions/0002-web-app-ui-enhancements.md` — UI 增强 + 演示模式 + Lessons Learned
- `Docs/60-decisions/0003-dev-only-web-terminal.md` — 嵌入式终端架构
