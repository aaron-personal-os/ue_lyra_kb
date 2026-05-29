# 架构速查

## 技术栈版本

| 技术 | 版本 | 用途 |
|------|------|------|
| Astro | 5.7+ | 框架核心（Content Collections、SSG、Islands） |
| React | 19 | 交互组件（Islands 水合） |
| Tailwind CSS | 4 | 实用优先样式 |
| TypeScript | 5.7+ | 类型安全 |
| Framer Motion | 11 | 动画（StepAnimation） |
| Mermaid | 11.4+ | 流程图/时序图渲染 |
| reveal.js | 6 | 演示模式（PPT 式教学） |
| Shiki | 内置 | 代码高亮（one-dark-pro 主题） |
| Pagefind | 1.3+ | 客户端离线全文搜索 |
| xterm.js | 5.5 | 终端 UI（dev-only） |
| node-pty | 1.x | PTY 桥接（dev-only） |
| ws | 8.x | WebSocket（dev-only） |
| pnpm | 9 | 包管理 |

## 架构图

```text
┌─────────────────────────────────────────────────────────────┐
│                     浏览器 (localhost:4321)                    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ Astro 静态 HTML + CSS                                 │    │
│  │  ┌─────────┐  ┌──────────────┐  ┌─────────────────┐ │    │
│  │  │ Navbar  │  │ FloatingSidebar│  │ Hero + Content  │ │    │
│  │  └─────────┘  └──────────────┘  └─────────────────┘ │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─ React Islands (按需水合) ──────────────────────────────┐ │
│  │ PresentationMode │ MermaidInit │ CodeBlockEnhancer │ ... │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─ Dev-Only ─────────────────────────────────────────────┐  │
│  │ TerminalPanel (xterm.js) ←→ ws://127.0.0.1:4322       │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 数据源 (Docs/30-tutorials/)                    │
│                                                               │
│  _series.yaml → getAllSeries() → 系列导航/进度               │
│  *.md         → Content Collections → 教程页面渲染           │
│  frontmatter  → Zod schema 验证 → 类型安全的元数据           │
└─────────────────────────────────────────────────────────────┘
```

## 数据流

```
Docs/30-tutorials/{series}/_series.yaml
  ↓ (lib/series.ts → getAllSeries / getSeriesLessons)
  ↓
pages/index.astro ← 首页渲染所有系列卡片
pages/series/[slug].astro ← 系列概览 + 课程列表
pages/series/[slug]/[...lesson].astro ← 教程正文

Docs/30-tutorials/{series}/*.md
  ↓ (Content Collections → glob loader)
  ↓ (remark-mermaid → 保护 mermaid 代码块)
  ↓ (remark-wiki-links → 转换 [[link]])
  ↓ (Shiki → 代码高亮)
  ↓
TutorialLayout.astro → 渲染 HTML
  ↓
MermaidInit.astro → 客户端渲染 SVG 图表
CodeBlockEnhancer.astro → 代码块增强（折叠/复制/窗口化）
SectionReveal.astro → 滚动渐显动画
```

## 页面路由

| 路径 | 页面文件 | 内容 |
|------|----------|------|
| `/` | `pages/index.astro` | 首页 + 系列网格（按 learning-paths 排序） |
| `/series/:slug` | `pages/series/[slug].astro` | 系列概览（从 `_series.yaml` 生成） |
| `/series/:slug/:lesson` | `pages/series/[slug]/[...lesson].astro` | 教程正文 + 交互组件 |
| `/search` | `pages/search.astro` | Pagefind 全文搜索 |

## 布局层级

```
BaseLayout.astro
├── <head> — 字体加载、CSS 导入
├── pre-paint script — 防 FOUC（读 localStorage 设 data-sidebar-*）
├── scroll-reveal observer
└── <body>
    └── TutorialLayout.astro（教程页专用）
        ├── Navbar
        ├── FloatingSidebar (left) — 系列导航 + 进度条
        ├── Hero — 全屏首屏（渐变 + 元信息）
        ├── <article class="prose-tutorial"> — Markdown 正文
        ├── Prev/Next 导航
        ├── FloatingSidebar (right) — TOC 目录
        ├── MermaidInit — Mermaid 渲染
        ├── CodeBlockEnhancer — 代码块增强
        ├── SectionReveal — 滚动动画
        ├── PresentationMode (React Island) — reveal.js 演示
        ├── ProgressTracker (React Island) — 进度记录
        └── TerminalPanel (React Island, DEV only) — 嵌入终端
```

## 构建命令

| 命令 | 说明 |
|------|------|
| `pnpm dev` | 启动 Astro dev server (4321) |
| `pnpm build` | 静态构建 + Pagefind 索引 |
| `pnpm preview` | 预览构建产物 |
| `node terminal-server/index.mjs` | 启动 PTY server (4322, dev-only) |

## Astro 配置要点 (astro.config.mjs)

- `devToolbar: { enabled: false }` — 关闭 dev toolbar
- `integrations: [react()]` — 启用 React Islands
- `vite.plugins: [tailwindcss()]` — Tailwind 4 via Vite 插件
- `markdown.remarkPlugins: [remarkMermaid, remarkWikiLinks]` — 自定义 remark 插件
- `markdown.shikiConfig.theme: 'one-dark-pro'` — 代码高亮主题
- 路径别名：`@/` → `src/`、`@components/` → `src/components/`、`@lib/` → `src/lib/`

## 端口约定

| 端口 | 服务 | 说明 |
|------|------|------|
| 4321 | Astro dev server | 前端页面 |
| 4322 | terminal-server | PTY WebSocket（仅 dev 模式） |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LYRA_TERMINAL_PORT` | 4322 | terminal-server 端口 |
| `LYRA_DEV_PORT` | 4321 | Astro dev 端口（Origin 校验用） |
| `LYRA_TERMINAL_SHELL` | 平台默认 | 强制使用的 shell 路径 |
| `LYRA_TERMINAL_LOGIN_SHELL` | 0 | Unix: 设为 1 使用 login shell |
