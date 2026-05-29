# 已知坑 (Gotchas)

> 来源：ADR-0002 Lessons Learned + 实际开发经验

## 1. Astro Shiki 管线顺序

**问题**：Astro 的 rehype-shiki 在所有用户 rehype 插件**之前**执行，会把代码块 token 化。

**后果**：如果 mermaid 代码块被 Shiki 处理，原始源码丢失，无法渲染图表。

**解法**：在 **remark 阶段**（Shiki 之前）将需要保护的代码块转为 `html` 节点。参考 `src/plugins/remark-mermaid.ts`。

**规则**：任何自定义代码块（`steps`、`quiz`）都必须在 remark 阶段拦截。

---

## 2. DOM 重排 — 先快照再操作

**问题**：`querySelectorAll` 返回 static NodeList，但 `forEach` 中修改 DOM 时节点的 `parentNode` 会变。

**后果**：SectionReveal 曾因此导致 section 互相嵌套，正文不显示。

**解法**：先 `Array.from()` 快照所有子节点，再循环操作。

```javascript
// ❌ 错误
container.querySelectorAll('h2').forEach(h2 => {
  const section = document.createElement('section');
  h2.parentNode.insertBefore(section, h2); // parentNode 可能已变
});

// ✅ 正确
const nodes = Array.from(container.childNodes);
// 再按 h2 分组操作快照
```

---

## 3. reveal.js CSS 全局污染

**问题**：`reset.css` + `reveal.css` 会重置全局样式（所有 h1-h6、p、ul 等）。

**后果**：退出演示模式后页面排版全乱。

**解法**：CSS 通过 `<link data-reveal-css>` 动态注入，退出时 `document.querySelectorAll('link[data-reveal-css]').forEach(l => l.remove())`。

**规则**：任何第三方库的全局 CSS 都必须动态注入/移除，不能放在全局 import 中。

---

## 4. reveal.js theme CSS 的副作用

**问题**：`theme/black.css` 设置 `font-size: 42px`，会把所有相对单位（em/rem）放大。

**解法**：不加载主题 CSS。用自定义 `presentation.css` 替代。

**规则**：如果自定义样式足够，不要加载第三方主题。

---

## 5. reveal.js transition 在同色背景下不可见

**问题**：所有 slide 背景色相同时，`slide` transition 视觉上等于 `none`。

**解法**：用 CSS `@keyframes` 自定义入场动画，或交替背景色。

```css
.reveal .slides section.present {
  animation: slideIn 0.5s ease-out;
}
@keyframes slideIn {
  from { transform: translateX(30px); opacity: 0.7; }
  to { transform: translateX(0); opacity: 1; }
}
```

---

## 6. SVG inline 属性 vs CSS

**问题**：Mermaid SVG 带固定 `width`/`height`/`style` 属性。

**后果**：CSS `!important` 无法覆盖 inline style。

**解法**：用 DOM API `removeAttribute('width')` / `removeAttribute('height')` / `removeAttribute('style')`。

**注意**：不要用 `.replace(/style="[^"]*"/g, '')` 正则，会删除所有内部元素的 style。

---

## 7. 代码块字号需绝对单位

**问题**：reveal.js 的 base font-size 很大（22-42px），用 `em` 单位会被放大。

**解法**：代码块用固定 `px` 值（如 `13px`）。

**规则**：在演示模式中，所有需要紧凑显示的元素用 `px` 而非 `em`/`rem`。

---

## 8. 全宽突破容器限制

**需求**：让子元素（如 Mermaid 图）突破 `max-width` 父容器占满 viewport 宽度。

**解法**：
```css
.full-width-element {
  position: relative;
  left: 50%;
  margin-left: -50vw;
  width: 100vw;
}
```

---

## 9. Shift+滚轮避免冲突

**问题**：正文页中纯 wheel 事件会与页面滚动冲突。

**解法**：正文页用 `Shift+wheel` 触发缩放；演示模式全屏时可用纯 wheel。

**规则**：任何 wheel 交互必须在正文页用 Shift 修饰。

---

## 10. Fragment 动画 vs Slide 动画

**问题**：用户感知到的"翻页动画"可能来自 fragment 的 `translateY`，与 slide 转场混淆。

**解法**：差异化 — fragment 用 fadeUp (translateY)，slide 用 slideIn (translateX)。

---

## 11. package exports 不导出 CSS 子路径

**问题**：`reveal.js` 的 package.json exports 不包含 CSS 文件路径，直接 import 报错。

**解法**：将需要的 CSS 拷贝到 `public/vendor/reveal/` 目录，运行时从 public 加载。

**规则**：第三方库的 CSS 如果无法通过 import 获取，拷到 `public/vendor/{lib}/`。

---

## 12. Content Collections 的 passthrough()

**注意**：schema 使用 `.passthrough()`，意味着 frontmatter 中任何未定义的字段都不会报错。

**后果**：拼写错误的 frontmatter key 不会被 Zod 捕获。

**建议**：新增 frontmatter 字段时，先在 `content.config.ts` 的 schema 中声明。

---

## 13. 侧栏 Toggle 按钮定位

**问题**：如果 toggle 按钮在 sidebar 面板内部，折叠后按钮也消失。

**解法**：toggle 按钮拆出 aside，使用独立 `position: fixed` 定位。

---

## 14. Astro Dev Toolbar 干扰

**问题**：Astro 内置 dev toolbar 会挡住页面底部内容和终端面板。

**解法**：`astro.config.mjs` 中 `devToolbar: { enabled: false }`。

---

## 15. Windows PTY UTF-8

**问题**：Windows cmd/powershell 默认使用 GBK 编码，中文输出乱码。

**解法**：PTY 启动后自动发送 `chcp 65001` 强制 UTF-8。

---

## 16. Git Bash 在 Windows 的 login shell 问题

**问题**：Git Bash 的 login shell (`-l`) 会加载 `/etc/profile` 链，启动慢 2-3 秒。

**解法**：Windows Git Bash 用 `-i`（interactive）而非 `-l`（login）。

---

## 快速检查清单

开发新功能前过一遍：

- [ ] 是否需要保护代码块不被 Shiki 处理？→ 写 remark 插件
- [ ] 是否操作 DOM NodeList？→ 先 Array.from 快照
- [ ] 是否引入第三方全局 CSS？→ 动态注入/移除
- [ ] 是否在演示模式中用了相对单位？→ 改 px
- [ ] 是否需要 wheel 交互？→ 正文页加 Shift 修饰
- [ ] 是否新增 frontmatter 字段？→ 先改 content.config.ts
- [ ] 第三方 CSS import 报错？→ 拷到 public/vendor/
