# 工作流：style（UI 样式调整）

> 调整视觉表现、动画、响应式布局、主题等纯样式任务。

## 触发场景

- "调整 XX 样式"
- "XX 太宽了/太窄了"
- "改下 XX 的颜色"
- "XX 动画不顺畅"
- "在手机上 XX 显示不对"
- "XX 需要更好的视觉层次"

## 前置检查

1. 读取 `reference/conventions.md` → 样式系统、CSS 变量、响应式策略
2. 读取 `reference/gotchas.md` → 常见样式坑（CSS 污染、inline style 覆盖等）
3. 定位涉及的组件 → 读取其 `<style>` 和 class 用法

## 步骤

### 1. 定位样式来源

确认当前样式来自哪一层：

| 层 | 文件 | 作用域 |
|----|------|--------|
| 全局 reset/base | `src/styles/global.css` | 全站 |
| 排版 | `src/styles/typography.css` | `.prose-tutorial` 内 |
| 演示模式 | `src/styles/presentation.css` | `.reveal` 内 |
| 终端 | `src/styles/terminal.css` | 终端面板 |
| 组件 scoped | 组件内 `<style>` | 仅该组件 |
| Tailwind | class 属性 | inline |
| CSS 变量 | `:root` / inline `style` | 级联 |

### 2. 修改位置决策

```
样式变更影响全站？
├── 是 → 修改 global.css 或 typography.css
└── 否
    ├── 影响所有同类组件？→ 组件内 <style>
    └── 仅影响特定实例？→ Tailwind class 或 inline style
```

### 3. 颜色修改

**绝对禁止**硬编码颜色值。遵循：

```css
/* ✅ 使用 CSS 变量 */
color: var(--text-primary);
background: var(--surface-1);
border: 1px solid var(--border);

/* ✅ 使用 Tailwind 配合 CSS 变量 */
<div class="text-[var(--text-primary)] bg-[var(--surface-1)]">

/* ❌ 硬编码 */
color: #e2e8f0;
background: #1a1d2e;
```

如需新增颜色，在 `global.css` 的 `:root` 中定义变量。

### 4. 间距/布局修改

- 优先使用 Tailwind utility：`p-4`, `gap-6`, `max-w-4xl`
- 复杂布局用 CSS Grid/Flexbox
- 响应式：`@media (max-width: 1024px)` 或 Tailwind `lg:` 前缀

### 5. 动画修改

- 简单过渡：CSS `transition`
- 复杂序列：`@keyframes`
- React 组件内：Framer Motion
- 滚动触发：Intersection Observer（已有 scroll-reveal 模式）

### 6. 全宽元素

如需突破 max-width 容器：
```css
.full-width {
  position: relative;
  left: 50%;
  margin-left: -50vw;
  width: 100vw;
}
```

### 7. 验证

```bash
# 构建检查
pnpm build

# 视觉验证
pnpm dev
# 检查：
# - 正常宽度 (1440px+)
# - 侧栏折叠态
# - 窄屏 (< 1024px)
# - 暗色主题一致性
```

## 质量标准

- [ ] 颜色使用 CSS 变量
- [ ] 响应式正常（1024px 断点）
- [ ] 暗色主题一致性
- [ ] 无 `!important`（除非覆盖 inline style 有充分理由）
- [ ] 动画流畅（无跳帧）
- [ ] 不影响其他组件的布局

## 禁止动作

❌ 不要硬编码颜色值
❌ 不要滥用 `!important`
❌ 不要在组件外写 `:global()` 选择器（除非确实需要跨组件影响）
❌ 不要修改第三方库的源 CSS（拷到 public/vendor/ 后再改）
❌ 不要用 JS 做 CSS 能做的事情（如 hover 效果、简单动画）
❌ 不要给 reveal.js/mermaid 内部元素加 CSS 而不用作用域限制
