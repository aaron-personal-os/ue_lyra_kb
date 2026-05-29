# 组件目录

## 交互组件（React Islands）

### PresentationMode

| 属性 | 值 |
|------|---|
| **文件** | `src/components/interactive/PresentationMode.tsx` |
| **类型** | React Island |
| **水合** | `client:idle` |
| **依赖** | reveal.js 6（动态 import） |
| **功能** | 将教程正文转为 reveal.js 演示 slides（PPT 模式） |
| **触发** | 右下角浮动按钮 |
| **行为** | H2→标题页(zoom)、代码→独占页(convex)、Mermaid→独占页、段落→累积(max 5 项) |
| **退出** | ESC 或右上角 X；退出时移除注入的 CSS link 标签 |
| **状态** | 无持久化 |

### TerminalPanel

| 属性 | 值 |
|------|---|
| **文件** | `src/components/interactive/TerminalPanel.tsx` |
| **类型** | React Island (DEV-only) |
| **水合** | `client:idle` |
| **守卫** | `import.meta.env.DEV`（生产构建时 tree-shake） |
| **依赖** | @xterm/xterm, @xterm/addon-fit, @xterm/addon-web-links |
| **功能** | VSCode 风格底部终端面板，WebSocket 连接 terminal-server |
| **快捷键** | Ctrl+J 切换显隐、Ctrl+Shift+J 新建 tab |
| **持久化** | localStorage: 显隐状态、面板高度、tab 列表 |
| **安全** | 仅连接 ws://127.0.0.1:4322，子协议 `lyra-terminal-v1` |

### ProgressTracker

| 属性 | 值 |
|------|---|
| **文件** | `src/components/interactive/ProgressTracker.tsx` |
| **类型** | React Island（不可见） |
| **水合** | `client:load` |
| **依赖** | 无外部依赖 |
| **功能** | 页面加载时将当前课程标记为已完成（localStorage） |
| **渲染** | 返回 `null`（纯副作用组件） |
| **状态** | localStorage key: `lyra-kb-progress` |

### CodeBlock

| 属性 | 值 |
|------|---|
| **文件** | `src/components/interactive/CodeBlock.tsx` |
| **类型** | React Island |
| **功能** | C++ 源码折叠/展开 + 语法高亮增强 |
| **说明** | 配合 CodeBlockEnhancer.astro 使用 |

### StepAnimation

| 属性 | 值 |
|------|---|
| **文件** | `src/components/interactive/StepAnimation.tsx` |
| **类型** | React Island |
| **依赖** | Framer Motion |
| **功能** | 执行流程步进动画 |
| **触发** | Markdown 中 ` ```steps ``` ` 代码块 |

### Quiz

| 属性 | 值 |
|------|---|
| **文件** | `src/components/interactive/Quiz.tsx` |
| **类型** | React Island |
| **功能** | 选择题/填空 + 即时反馈 |
| **触发** | Markdown 中 ` ```quiz ``` ` 代码块 |

### MermaidDiagram

| 属性 | 值 |
|------|---|
| **文件** | `src/components/interactive/MermaidDiagram.tsx` |
| **类型** | React Island |
| **依赖** | mermaid 11 |
| **功能** | Mermaid 代码块渲染为 SVG |
| **说明** | 配合 MermaidInit.astro 使用 |

---

## 布局组件（Astro）

### Navbar

| 属性 | 值 |
|------|---|
| **文件** | `src/components/layout/Navbar.astro` |
| **功能** | 顶部导航栏（系列 tabs + 搜索入口） |
| **位置** | BaseLayout 顶部 |

### FloatingSidebar

| 属性 | 值 |
|------|---|
| **文件** | `src/components/layout/FloatingSidebar.astro` |
| **功能** | 浮动可折叠侧栏（左：系列导航+进度；右：TOC） |
| **状态** | `<html data-sidebar-left>` / `<html data-sidebar-right>` + localStorage |
| **折叠** | 按钮 / 键盘 `[` `]` / viewport < 1024px 自动 |
| **折叠态** | 极细导轨 (4px) + hover 预览，toggle 按钮独立 fixed 始终可见 |
| **样式** | 自定义滚动条，深色主题 |

### TableOfContents

| 属性 | 值 |
|------|---|
| **文件** | `src/components/layout/TableOfContents.astro` |
| **功能** | 从 headings 生成目录树（H2/H3，去 H4） |
| **位置** | 右侧 FloatingSidebar 内容 |

### Hero

| 属性 | 值 |
|------|---|
| **文件** | `src/components/layout/Hero.astro` |
| **功能** | 全屏首屏（渐变背景 + 系列徽章 + 难度 + 进度 + CTA） |
| **位置** | 教程正文上方，脱出 main 容器不受 sidebar 限制 |
| **主题** | 从 `lib/theme.ts` 获取系列配色 |

---

## 增强组件（Astro + inline script）

### MermaidInit

| 属性 | 值 |
|------|---|
| **文件** | `src/components/interactive/MermaidInit.astro` |
| **功能** | 客户端 Mermaid 初始化：检测 `.mermaid-source` → 渲染 SVG → 美化容器 |
| **交互** | Shift+滚轮缩放 (0.3x~4x) + 拖拽平移 + 双击复位 |
| **样式** | 深色卡片 + 顶部青色发光线 + 图表类型 badge + 全宽突破容器 |
| **防护** | `data-zoom-init` 防重复绑定、sanitizeMermaid() 剥除硬编码颜色 |

### CodeBlockEnhancer

| 属性 | 值 |
|------|---|
| **文件** | `src/components/interactive/CodeBlockEnhancer.astro` |
| **功能** | 代码块美化：macOS 红黄绿圆点 + 语言 badge + 行数 + 折叠(>15行)/复制 |
| **样式** | 双层深色背景 + 渐隐展开动画 |

### SectionReveal

| 属性 | 值 |
|------|---|
| **文件** | `src/components/interactive/SectionReveal.astro` |
| **功能** | 按 H2 分组内容，滚动时渐显 |
| **注意** | 先快照 childNodes 再按 H2 分组（避免 DOM 重排 bug） |

---

## UI 组件

### Badge

| 属性 | 值 |
|------|---|
| **文件** | `src/components/ui/Badge.astro` |
| **功能** | 通用标签/徽章组件 |

---

## 工具库 (src/lib/)

### series.ts

| 函数 | 说明 |
|------|------|
| `getAllSeries()` | 读取所有 `_series.yaml`，返回系列元数据数组 |
| `getSeriesBySlug(slug)` | 按 slug 获取单个系列 |
| `getSeriesLessons(slug)` | 获取系列所有课程文件列表 |
| `getLessonMeta(seriesSlug, lessonFile)` | 解析 MD 提取标题/摘要 |
| `getLessonTitle(seriesSlug, lessonFile)` | 快捷获取课程标题 |

### theme.ts

| 导出 | 说明 |
|------|------|
| `SeriesTheme` | 接口：gradient, badge, accent |
| `getSeriesTheme(slug)` | 获取系列主题色（硬编码映射） |
| 默认主题 | Slate/neutral |

### progress.ts

| 函数 | 说明 |
|------|------|
| `getProgress(seriesSlug)` | 从 localStorage 读取系列进度 |
| `markLessonComplete(seriesSlug, lessonId)` | 标记课程完成 |
| `getSeriesProgressPercent(seriesSlug, totalLessons)` | 计算完成百分比 |

---

## Remark 插件 (src/plugins/)

### remark-mermaid.ts

- **时机**：在 Shiki 之前执行（remark 阶段）
- **行为**：将 ` ```mermaid ``` ` 代码块转为 `<pre class="mermaid-source">` HTML 节点
- **原因**：保护原始代码不被 Shiki token 化

### remark-wiki-links.ts

- **行为**：将 `[[page-id|title]]` 转为 HTML 链接
- **用途**：支持知识库 wikilink 语法
