# 编码规范

## 命名规范

| 类型 | 风格 | 示例 |
|------|------|------|
| React 组件 | PascalCase | `PresentationMode.tsx` |
| Astro 组件 | PascalCase | `FloatingSidebar.astro` |
| 工具函数 | camelCase | `getAllSeries()`, `getLessonMeta()` |
| 常量 | UPPER_SNAKE_CASE | `SERIES_ORDER`, `STORAGE_KEY` |
| CSS 类 | kebab-case | `prose-tutorial`, `series-card` |
| CSS 变量 | --kebab-case | `--surface-0`, `--text-primary` |
| 页面文件 | 小写 + 方括号动态段 | `[slug].astro`, `[...lesson].astro` |
| Lib 文件 | kebab-case | `series.ts`, `progress.ts` |

## 文件组织

```
src/components/
├── interactive/    ← 需要 JS 交互的组件（React Islands 或 Astro+inline script）
├── layout/         ← 布局结构组件（Navbar, Sidebar, Hero, TOC）
└── ui/             ← 原子 UI 组件（Badge, Button, Card）

src/lib/            ← 纯逻辑工具函数（无 UI）
src/plugins/        ← Remark/Rehype 插件
src/styles/         ← 全局 CSS（非 scoped）
```

## 状态管理模式

### 客户端状态分层

```
localStorage (持久化)
  ↓ 读取
<html data-*> 属性 (DOM 状态源)
  ↓ CSS 选择器
CSS 样式 (视觉表现)
  ↓ 事件
Custom Events (跨组件通信)
```

### 规则

1. **持久化** → localStorage
   - Key 命名：`lyra-kb-{feature}`（如 `lyra-kb-progress`、`lyra-kb-sidebar-left`）
2. **DOM 状态** → HTML `data-*` 属性
   - 侧栏折叠：`<html data-sidebar-left="collapsed">` / `<html data-sidebar-right="collapsed">`
3. **跨组件** → CustomEvent
   - `sidebar-toggle` 事件通知 main 内容区调整 margin
4. **组件内** → React useState / useRef
5. **禁止** → 全局状态库（Redux / Zustand / Context）

### Pre-paint 脚本（防 FOUC）

在 BaseLayout.astro 的 `<head>` 中插入同步 inline script：
```html
<script is:inline>
  // 在首次渲染前读取 localStorage 设置 data-* 属性
  // 避免侧栏闪烁（先展开再折叠的视觉跳动）
</script>
```

## 样式系统

### 颜色系统（CSS 变量）

```css
:root {
  --surface-0: #0f1117;   /* 最深背景 */
  --surface-1: #1a1d2e;   /* 面板/卡片背景 */
  --surface-2: #252939;   /* hover/次级背景 */
  --accent: #60a5fa;      /* 默认蓝色强调 */
  --text-primary: #e2e8f0; /* 主文字 */
  --text-secondary: #94a3b8; /* 次级文字 */
  --border: #2e3348;      /* 边框 */
}
```

### 主题色注入

系列主题由 `lib/theme.ts` 提供，通过 inline style 注入 CSS 变量：
```html
<div style="--card-accent: #f59e0b; --series-gradient: ...">
```

### 样式优先级

1. **Tailwind 4 utility classes** — 布局、间距、基础样式
2. **CSS 变量** — 颜色、主题
3. **Scoped `<style>`** — 组件特有样式（Astro 自动 scope）
4. **global.css / typography.css** — 全局 reset、排版、prose 样式

### 响应式策略

| 断点 | 行为 |
|------|------|
| < 1024px | 侧栏自动折叠、单栏布局 |
| ≥ 1024px | 双侧栏展开、三栏布局 |

快捷键 `[` `]` 手动切换侧栏折叠。

## React Island 水合策略

| 指令 | 时机 | 适用场景 |
|------|------|----------|
| `client:load` | 页面加载立即水合 | 需要立即可交互的组件（ProgressTracker） |
| `client:idle` | 浏览器空闲时水合 | 可延迟的交互（PresentationMode、TerminalPanel） |
| `client:visible` | 进入视口时水合 | 页面底部组件 |
| 无指令 | 不水合（纯服务端） | 仅 SSG 输出 HTML |

**默认选择**：`client:idle`（绝大多数 Island 不需要立即交互）

## TypeScript 规范

- 开启 strict 模式
- 接口优先于 type（`interface SeriesMeta {}` 而非 `type SeriesMeta = {}`）
- 文件顶部声明接口/类型，底部 export
- 使用路径别名：`@/lib/series` 而非 `../../lib/series`

## Import 顺序

```typescript
// 1. 框架/库
import { useState } from 'react';
import { motion } from 'framer-motion';

// 2. 内部库
import { getAllSeries } from '@/lib/series';
import { getSeriesTheme } from '@/lib/theme';

// 3. 组件
import Badge from '@components/ui/Badge.astro';

// 4. 类型
import type { SeriesMeta } from '@/lib/series';
```

## Astro 组件规范

```astro
---
// 1. 导入
import BaseLayout from '@layouts/BaseLayout.astro';
import { getAllSeries } from '@/lib/series';

// 2. Props 接口
interface Props {
  title: string;
  series?: string;
}

// 3. 数据获取
const { title, series } = Astro.props;
const allSeries = await getAllSeries();

// 4. 计算逻辑
const sorted = allSeries.sort((a, b) => a.name.localeCompare(b.name));
---

<!-- 5. 模板 -->
<BaseLayout title={title}>
  <main>
    <slot />
  </main>
</BaseLayout>

<!-- 6. Scoped 样式 -->
<style>
  main { max-width: 80ch; }
</style>

<!-- 7. 客户端脚本（如需要） -->
<script>
  // 仅在此组件被挂载时执行
</script>
```

## 代码块增强约定

- **自动增强**：标准 ` ```cpp ``` ` 代码块由 CodeBlockEnhancer 自动加工（macOS 窗口 + 折叠）
- **Mermaid 保护**：` ```mermaid ``` ` 由 remark-mermaid 在 Shiki 前拦截
- **新增标记**（需手动添加到 md）：
  - ` ```steps ``` ` → StepAnimation 组件
  - ` ```quiz ``` ` → Quiz 组件
