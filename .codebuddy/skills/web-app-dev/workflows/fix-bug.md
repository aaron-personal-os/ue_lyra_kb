# 工作流：fix-bug（调试修复）

> 定位并修复 web-app 中的 bug。

## 触发场景

- "XX 不显示"
- "修复 XX bug"
- "为什么 XX 不工作"
- "XX 报错了"
- "XX 样式不对"

## 前置检查

1. 读取 `reference/gotchas.md` → 是否命中已知坑点
2. 读取 `reference/component-catalog.md` → 定位涉及的组件
3. 读取 `reference/architecture.md` → 理解数据流，定位问题层

## 步骤

### 1. 复现与定位

确认问题出在哪一层：

```
数据层    → Content Collections 配置 / _series.yaml / frontmatter
构建层    → Remark 插件 / Astro 构建
渲染层    → Layout / Astro 组件 / HTML 输出
交互层    → React Island / inline script / 事件处理
样式层    → CSS 变量 / Tailwind / scoped style / 全局样式冲突
网络层    → WebSocket / fetch / 资源加载
```

### 2. 检查常见根因

按照 ADR-0002 Lessons Learned 逐一排查：

| 症状 | 可能根因 | 检查点 |
|------|----------|--------|
| 内容不显示 | DOM 重排 bug | SectionReveal 是否正确快照 childNodes |
| Mermaid 不渲染 | Shiki 抢先 token 化 | remark-mermaid 是否正确拦截 |
| Mermaid 颜色乱 | 源 md 硬编码 style | sanitizeMermaid() 是否剥除 |
| 侧栏按钮消失 | Toggle 在折叠容器内 | 按钮是否独立 fixed 定位 |
| 演示模式退出后乱 | CSS 全局污染 | data-reveal-css link 是否被移除 |
| SVG 尺寸不对 | inline width/height | 是否用 DOM API removeAttribute |
| 代码块字号过大 | 相对单位被 reveal.js 放大 | 是否用了绝对 px |
| 滚轮交互冲突 | 未使用 Shift 修饰 | 正文页 wheel handler 是否检查 shiftKey |

### 3. 定位代码

根据问题层读取对应文件：

| 层 | 关键文件 |
|----|----------|
| Content | `src/content.config.ts`, `src/lib/series.ts` |
| Remark | `src/plugins/remark-mermaid.ts`, `src/plugins/remark-wiki-links.ts` |
| Layout | `src/layouts/TutorialLayout.astro`, `src/layouts/BaseLayout.astro` |
| 组件 | `src/components/interactive/`, `src/components/layout/` |
| 样式 | `src/styles/global.css`, `src/styles/typography.css` |
| 终端 | `terminal-server/index.mjs`, `src/components/interactive/TerminalPanel.tsx` |

### 4. 修复

- **DOM 相关**：先 Array.from 快照再操作
- **CSS 相关**：检查 specificity、inline style、CSS 变量覆盖链
- **数据相关**：检查 Zod schema、YAML 格式、文件路径匹配
- **时序相关**：检查 client:idle vs client:load、script 加载顺序

### 5. 回归验证

```bash
# 构建验证
pnpm build

# 开发模式验证
pnpm dev
# 手动检查：
# - 问题页面正常显示
# - 相邻页面未被影响
# - 响应式（缩窄到 < 1024px）
# - 侧栏折叠/展开
# - 演示模式进出
```

## 质量标准

- [ ] Bug 已修复（问题不再复现）
- [ ] 无回归（相邻功能未受影响）
- [ ] `pnpm build` 通过
- [ ] 修复方法符合已知模式（不引入新坑）

## 禁止动作

❌ 不要用 `!important` 解决 CSS 问题（找到正确的 specificity 层）
❌ 不要在正文页用纯 wheel 事件做交互（必须 Shift 修饰）
❌ 不要用正则替换 SVG innerHTML（用 DOM API 操作具体属性）
❌ 不要忽略 Astro 的 remark/rehype 插件执行顺序
❌ 不要把 fix 散落在多处（集中在根因所在的一个地方修复）
