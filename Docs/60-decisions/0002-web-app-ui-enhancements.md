---
id: 60-decisions/0002-web-app-ui-enhancements
type: adr
status: accepted
language: zh
owner: human
decided_at: 2026-05-19
decided_by: robert
anchors: []
supersedes: []
superseded_by: []
related:
  - "[[60-decisions/0001-knowledge-base-web-app]]"
sources: []
last_synced: 2026-05-19
last_verified: 2026-05-19
tags: [adr, web-app, ui, mermaid, reveal.js, presentation, astro, zoom-pan]
---

# ADR-0002：Web 应用 UI 增强与演示模式

> 对知识库 Web 应用进行系统性 UI 美化、Bug 修复、交互增强，并引入 reveal.js 演示模式，实现 PPT 式教学体验。

## 背景 (Context)

ADR-0001 确立了 Astro 5 + React Islands 的 Web 应用基础架构。首版 MVP 完成后，在实际使用中发现以下问题：

1. **正文页内容不显示**：SectionReveal 组件的 DOM 重排逻辑存在嵌套 bug
2. **Mermaid 图不渲染**：Astro/Shiki 把 mermaid 代码块 token 化后丢失原始源码
3. **Mermaid 图颜色杂乱**：源 markdown 写死了 200+ 条浅色 `style` 指令
4. **侧栏体验不佳**：收缩按钮随面板消失、左右风格不统一
5. **系列总览页问题**：Hero 背景不搭、Prerequisites 多余、学习路径显示文件名
6. **正文页 H1 重复**：Hero 已展示标题但正文 H1 仍显示
7. **首页排序**：未按 learning-paths.md 推荐顺序排列
8. **缺乏演示体验**：纯文档无法提供 PPT 式教学演示

## 决策 (Decision)

### 一、Bug 修复（7 项）

| 问题 | 根因 | 修复 |
|------|------|------|
| 正文不显示 | SectionReveal forEach 导致 section 互相嵌套 | 先快照 childNodes 再按 h2 分组 |
| Mermaid 不渲染 | Shiki 改写 class | remark-mermaid 插件在 Shiki 前转为 raw HTML |
| Mermaid 浅色 | `style XXX fill:#e1f5fe` | sanitizeMermaid() 剥除颜色 + CSS 兜底 |
| H1 重复 | `> h1:first-child` 被 section 包装后失效 | CSS `h1 { display: none }` + JS remove |
| reveal.js CSS 污染 | reset.css 重置全局样式 | 退出时移除 `link[data-reveal-css]` |
| SVG inline 尺寸 | mermaid SVG 带固定 width/height | DOM API removeAttribute |
| package exports | reveal.js 不导出 CSS 子路径 | 拷贝到 public/vendor/ |

### 二、UI 美化

#### Mermaid 卡片化
- 深色卡片 + 顶部青色发光线 + 图表类型 badge
- `theme: 'base'` + 暗色 themeVariables
- 节点统一深色填充 + 青色描边 + 白色文字
- **全宽布局**：`left: 50%; margin-left: -50vw; width: 100vw` 突破正文容器
- **交互提示**：header 右侧显示 "Shift+滚轮缩放 · 拖拽移动 · 双击复位"
- **Shift+滚轮缩放 + 拖拽移动 + 双击复位**（正文页）

#### 代码块 macOS 窗口化
- 红黄绿圆点 + 语言 badge + 行数 + 折叠/复制按钮
- 双层背景 + 超 15 行折叠 + 渐隐展开

#### 侧栏重构
- Toggle 按钮拆出 aside，独立 fixed 定位
- 折叠态按钮停在屏幕边缘（始终可见）
- 状态源：`<html data-sidebar-*>` + localStorage 持久化
- BaseLayout pre-paint 脚本防 FOUC

#### 系列总览页
- Hero 全屏 + 主题色渐变 + blob + 底部淡出
- 删除 Prerequisites
- `getLessonMeta()` 从 H1 + blockquote 提取标题/摘要
- 卡片化 lesson 列表 + 编号 + 摘要 + chip

#### 正文页
- Hero 全屏（抽出 main 外，不受 sidebar 限制）
- "开始阅读"/"返回系列" CTA

#### 首页
- 按 learning-paths.md 排序（01-22）
- 卡片加路线编号 + 主题色 accent 线 + hover 发光

### 三、演示模式（reveal.js 6.x）

#### 架构
- `client:idle` React Island，CSS 动态注入 + 退出时移除
- 内容从 `.prose-tutorial` innerHTML 实时获取
- Astro DevToolbar 已关闭（`devToolbar: { enabled: false }`）

#### Slide 切分策略
- 展平 `.tutorial-section` wrapper
- 过滤导航/footer/hr/最后更新等无关内容
- **H2 → 独占标题页**（居中、font-size 2.2em、zoom 动画）
- **H3 → 内容 slide 头部**（不单独成页，当 itemCount≥3 时才翻页）
- **代码块 → 独占页**（macOS 窗口 + 行号 + token 高亮 + 全部显示可滚动）
- **Mermaid → 独占页**（窗口容器 + Shift+滚轮缩放 + 拖拽）
- **段落/列表 → 累积**（max 5 项后翻页，居中显示）
- **表格 → 独占页**
- **Blockquote → speaker notes**

#### 代码高亮（Token Scanner）
逐字符扫描器，支持：
- 注释（`//`, `/* */`, `#`）→ 灰色斜体
- 字符串 → 浅蓝
- C++ 关键字 / UE 宏 → 红色
- UE 类型（`UObject`/`AActor`/`FName`）→ 紫色
- TS/JS 关键字 → 红色
- 数字 → 天蓝
- 函数调用 → 紫色

#### Mermaid Slide
- 窗口容器（红黄绿 dots + badge + 提示）
- SVG 原样输出，CSS 控制 `max-width/max-height`
- 滚轮缩放（0.3x~4x）+ 拖拽平移 + 双击复位

#### 翻页动画
- 全局默认：`transition: 'slide'`（左右平移）
- H2 标题页：`data-transition="zoom"`（缩放弹出）
- 代码页：`data-transition="convex"`（3D 翻转）
- CSS 补充：`.present` slide 入场 `@keyframes slideIn`（translateX 30px → 0）
- Fragment：opacity fade + translateY 16px

#### 操作
- ← → 翻页、空格下一步、ESC 退出
- 右下角浮动"演示模式"按钮
- 右上角 X 关闭按钮
- 底部进度条

### 四、正文页 Mermaid 交互

- **Shift + 鼠标滚轮**：缩放（0.3x ~ 4x）
- **鼠标左键拖拽**：平移
- **双击**：重置
- `overflow: hidden` 防溢出
- `transition: transform 0.1s ease-out` 平滑
- `data-zoom-init` 防重复绑定
- Cursor 提示：grab / grabbing

### 五、文件清单

#### 新增
```
web-app/src/plugins/remark-mermaid.ts
web-app/src/components/interactive/PresentationMode.tsx
web-app/src/styles/presentation.css
web-app/public/vendor/reveal/reveal.css
web-app/public/vendor/reveal/reset.css
web-app/public/vendor/reveal/theme-black.css
```

#### 关键修改
```
astro.config.mjs                    — remarkMermaid、devToolbar off
src/styles/global.css               — .scroll-reveal、导入 presentation.css
src/styles/typography.css           — h1 { display: none }
src/layouts/BaseLayout.astro        — pre-paint、scroll-reveal
src/layouts/TutorialLayout.astro    — Hero 外置、PresentationMode、getLessonTitle
src/components/layout/FloatingSidebar.astro  — 完全重写
src/components/layout/TableOfContents.astro  — 去 h4
src/components/layout/Hero.astro    — 全屏重写
src/components/interactive/SectionReveal.astro    — 修复嵌套 + 删 H1
src/components/interactive/MermaidInit.astro       — remark + sanitizer + 美化 + zoom/pan
src/components/interactive/CodeBlockEnhancer.astro — macOS 窗口
src/pages/index.astro               — 排序 + 卡片
src/pages/series/[slug].astro       — 全屏 Hero + 学习路径卡片
src/lib/series.ts                   — getLessonMeta()
src/lib/theme.ts                    — +localization-i18n
```

## 经验教训（Lessons Learned）

### 1. Astro Shiki 管线顺序
Astro 的 rehype-shiki 在所有用户 rehype 插件**之前**执行。保护代码块必须在 **remark 阶段**转为 `html` 节点。

### 2. DOM 重排 — 先快照再操作
`querySelectorAll` 返回 static NodeList，但 `forEach` 中修改 DOM 时 `parentNode` 会变。**先 Array.from 快照再循环操作**。

### 3. reveal.js CSS 全局污染
`reset.css` + `reveal.css` 重置全局样式。必须在退出时**移除注入的 link 标签**。

### 4. reveal.js theme CSS 的副作用
`theme/black.css` 设 `font-size: 42px`，会把所有相对单位放大。如果自定义样式足够，**不要加载主题 CSS**。

### 5. reveal.js transition 在同色背景下不可见
所有 slide 背景色相同时，`slide` transition 视觉上等于 `none`。需要用 **CSS @keyframes 自定义入场动画**或交替背景色。

### 6. SVG inline 属性 vs CSS
Mermaid SVG 带固定 `width`/`height`/`style`。CSS `!important` 无法覆盖 inline style。用 **DOM API removeAttribute** 或克隆后清理。

### 7. 正则全局替换的副作用
对 SVG outerHTML `.replace(/style="[^"]*"/g, '')` 会删除**所有内部元素**的 style。应仅操作根标签或用 DOM API。

### 8. Fragment 动画 vs Slide 动画的区分
用户感知到的"翻页动画"可能来自 fragment 的 `translateY`。两者需要差异化：fragment 用 fadeUp，slide 用 slideIn（translateX）。

### 9. 代码块字号需绝对单位
reveal.js 的 base font-size 很大（22-42px），用 `em` 单位会被放大。代码块用 **固定 px** 值（13px）确保紧凑。

### 10. 全宽突破容器限制
```css
.mermaid-figure {
  position: relative;
  left: 50%;
  margin-left: -50vw;
  width: 100vw;
}
```
经典技巧：让子元素突破 `max-width` 父容器占满 viewport 宽度。

### 11. Shift+滚轮避免冲突
正文页用 `Shift+wheel` 触发缩放（而非纯 wheel），避免与页面正常滚动冲突。演示模式全屏时可用纯 wheel（无页面滚动）。

## 验证 (Validation)

- ✅ 正文页完整显示
- ✅ Mermaid 图统一暗色 + 全宽 + Shift+滚轮缩放/拖拽/双击复位
- ✅ 代码块折叠/复制
- ✅ 侧栏折叠/展开 + 收缩态按钮可见
- ✅ ESC 退出演示后布局正常
- ✅ 演示模式：标题页 zoom、代码页 convex、内容 slideIn
- ✅ 演示模式代码块：全量行 + 行号 + 高亮 + 可滚动
- ✅ 演示模式 Mermaid：窗口化 + 缩放/拖拽
- ✅ 导航/footer 内容不出现在演示中
- ✅ 首页按 learning-paths 排序 + 编号

## 相关页面

- [[60-decisions/0001-knowledge-base-web-app]] — 原始架构决策
- [[00-meta/learning-paths]] — 学习路线排序依据
- [[30-tutorials/README]] — 教程目录

---
> 最后更新：2026-05-19

<!-- nav:auto -->

---

**导航**: ← [[60-decisions/0001-knowledge-base-web-app|0001-knowledge-base-web-app]] · [[60-decisions/0003-dev-only-web-terminal|0003-dev-only-web-terminal]] →

<!-- /nav:auto -->
