# 工作流：component（组件开发）

> 创建或修改组件（React Island 或 Astro 组件）。

## 触发场景

- "新建一个 XX 组件"
- "把 XX 改成 YY"
- "加个 Island"
- "封装一个 XX"
- "拆出一个 XX 组件"

## 前置检查

1. 读取 `reference/component-catalog.md` → 是否已有类似组件可复用/扩展
2. 读取 `reference/conventions.md` → 组件规范、水合策略、状态管理
3. 如果涉及已知坑 → 读取 `reference/gotchas.md`

## 步骤

### 1. 确定组件类型

```
需要客户端 JS 交互？
├── 否 → Astro 组件 (.astro)
│   ├── 纯展示 → src/components/ui/
│   ├── 布局结构 → src/components/layout/
│   └── 需要 <script> 增强 → src/components/interactive/ (.astro)
└── 是 → React Island (.tsx)
    └── 放 src/components/interactive/
```

### 2. 确定水合策略（React Island 专用）

| 场景 | 指令 | 理由 |
|------|------|------|
| 立即需要交互（表单、输入） | `client:load` | 用户可能立即点击 |
| 延迟可接受（演示、终端） | `client:idle` | 优化首屏性能 |
| 视口外内容 | `client:visible` | 不在屏幕上不加载 |
| Dev-only 组件 | `client:idle` + `import.meta.env.DEV` 守卫 | 生产时 tree-shake |

**默认**：`client:idle`

### 3. 创建组件

#### React Island 模板

使用 `templates/react-island.tsx` 作为起点。关键结构：

```tsx
import { useState, useEffect, useRef } from 'react';

interface Props {
  // 从 Astro 传入的 props
}

export default function MyComponent({ ...props }: Props) {
  // 1. State
  const [state, setState] = useState(initial);
  
  // 2. Refs
  const containerRef = useRef<HTMLDivElement>(null);
  
  // 3. Effects（browser-only）
  useEffect(() => {
    if (typeof window === 'undefined') return;
    // ...
  }, []);
  
  // 4. Render
  return <div ref={containerRef}>...</div>;
}
```

#### Astro 组件模板

使用 `templates/astro-component.astro` 作为起点。关键结构：

```astro
---
interface Props {
  title: string;
}
const { title } = Astro.props;
---

<div class="my-component">
  <slot />
</div>

<style>
  .my-component { /* scoped styles */ }
</style>
```

#### Astro + inline script 组件

适用于简单的客户端增强（无需 React）：

```astro
---
// 服务端逻辑
---

<div class="enhanceable" data-config={JSON.stringify(config)}>
  <!-- 静态 HTML -->
</div>

<script>
  // 客户端增强
  document.querySelectorAll('.enhanceable').forEach(el => {
    const config = JSON.parse(el.dataset.config || '{}');
    // 绑定事件...
  });
</script>
```

### 4. 状态管理

遵循分层原则：

| 需求 | 方案 |
|------|------|
| 组件内临时状态 | `useState` / `useRef` |
| 跨会话持久化 | localStorage (`lyra-kb-{feature}`) |
| 影响全局 UI（如侧栏） | HTML `data-*` 属性 + CustomEvent |
| 从服务端传数据到客户端 | `data-*` 属性 或 inline JSON script |

### 5. 样式

优先级：
1. Tailwind utility classes（布局、间距）
2. CSS 变量（颜色、主题）
3. Scoped `<style>`（组件特有样式）

颜色必须使用 CSS 变量：
```css
color: var(--text-primary);
background: var(--surface-1);
border-color: var(--border);
```

### 6. 挂载

在对应 Layout 或 Page 中挂载：

```astro
---
import MyComponent from '@components/interactive/MyComponent';
---

<!-- 普通组件 -->
<MyComponent client:idle prop={value} />

<!-- Dev-only 组件 -->
{import.meta.env.DEV && <MyComponent client:idle />}
```

## 质量标准

- [ ] 组件职责单一（一个组件做一件事）
- [ ] Props 有 TypeScript 接口定义
- [ ] 样式使用 CSS 变量，不硬编码颜色
- [ ] React Island 选择了正确的水合策略
- [ ] 状态管理遵循分层原则
- [ ] 组件在 1024px 断点前后表现正常
- [ ] `pnpm build` 通过（确认 tree-shaking 正常）

## 禁止动作

❌ 不要为纯展示组件创建 React Island（用 Astro 组件）
❌ 不要在 React Island 中直接操作 DOM（用 ref + state）
❌ 不要引入新的状态管理库
❌ 不要在组件中硬编码系列主题色（从 props 或 CSS 变量获取）
❌ 不要在 Astro 组件的 `<script>` 中使用 import（改用 `<script>` 不带 `is:inline`，或用 React Island）
❌ 不要让组件承担过多职责（超过 200 行考虑拆分）
