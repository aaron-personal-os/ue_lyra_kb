# 工作流：implement（新增功能/页面）

> 新增页面、路由、功能模块时使用此工作流。

## 触发场景

- "新增 XX 页面"
- "加个 XX 功能"
- "实现 XX 路由"
- "添加 XX 支持"

## 前置检查

1. 读取 `reference/architecture.md` → 了解页面路由结构和数据流
2. 读取 `reference/component-catalog.md` → 确认是否有可复用的现有组件
3. 读取 `reference/conventions.md` → 了解文件组织和编码规范
4. 检查 `web-app/src/pages/` → 了解现有页面结构

## 步骤

### 1. 需求分析

- 明确功能边界：这个功能需要什么输入？输出什么？
- 确认是否需要新的数据源（新的 Content Collection？新的 YAML？）
- 确认是否需要客户端交互（决定是用 Astro 还是 React Island）

### 2. 设计路由

- 遵循现有路由模式：
  ```
  pages/index.astro              → /
  pages/series/[slug].astro      → /series/:slug
  pages/series/[slug]/[...lesson].astro → /series/:slug/:lesson
  pages/search.astro             → /search
  ```
- 动态路由必须实现 `getStaticPaths()`
- Catch-all 路由用 `[...param]` 语法

### 3. 确定数据获取

- **已有数据**：通过 `getCollection('tutorials')` 或 `lib/series.ts` 获取
- **新数据**：
  1. 在 `src/content.config.ts` 定义新 Collection
  2. 在 `src/lib/` 新增工具函数
  3. 用 Zod schema 验证

### 4. 选择组件方案

决策树：
```
需要客户端 JS 交互？
├── 否 → Astro 组件（.astro）
└── 是
    ├── 交互简单（toggle/scroll）→ Astro + <script is:inline>
    └── 交互复杂（状态/事件/动画）→ React Island（.tsx）
        ├── 需立即交互 → client:load
        ├── 可延迟 → client:idle（默认）
        └── 滚动到才需要 → client:visible
```

### 5. 实现

1. **创建页面文件** — `src/pages/...astro`
2. **创建组件** — `src/components/{interactive|layout|ui}/...`
3. **创建工具函数** — `src/lib/...ts`（如需要）
4. **添加样式** — 优先 Tailwind utility → scoped `<style>` → global CSS
5. **连接数据** — frontmatter 数据获取 → props 传递 → 渲染

### 6. 集成到布局

- 新页面使用 `BaseLayout`（通用）或 `TutorialLayout`（教程相关）
- 新组件在对应 Layout 中挂载
- Dev-only 组件用 `import.meta.env.DEV` 守卫

## 质量标准

- [ ] 静态构建通过：`pnpm build` 无错误
- [ ] 路由正确：dev 模式下页面可访问
- [ ] 响应式：1024px 断点前后表现正常
- [ ] 暗色主题：所有新增 UI 使用 CSS 变量
- [ ] 类型安全：TypeScript 无报错
- [ ] 组件复用：没有重复造轮子

## 禁止动作

❌ 不要把 Markdown 内容复制到 web-app/ 目录（应通过 Content Collections 读取）
❌ 不要引入全局状态管理库
❌ 不要使用 SSR/hybrid 模式（保持纯静态）
❌ 不要在 `web-app/package.json` 中添加 terminal-server 的依赖
❌ 不要硬编码颜色值到组件中（使用 CSS 变量或 theme.ts）
