# 工作流：refactor（重构/优化）

> 优化代码质量、性能、可维护性，不改变外部行为。

## 触发场景

- "优化 XX"
- "重构 XX"
- "拆分 XX 组件"
- "XX 太大了需要拆"
- "提取 XX 为公共函数"
- "性能优化"

## 前置检查

1. 读取 `reference/architecture.md` → 理解现有架构和依赖关系
2. 读取 `reference/component-catalog.md` → 了解组件间的关系
3. 读取涉及重构的源文件 → 理解现有实现

## 步骤

### 1. 明确重构目标

| 类型 | 信号 | 策略 |
|------|------|------|
| 组件过大 | > 200 行 | 拆分为子组件 |
| 重复代码 | 2+ 处相同逻辑 | 提取到 `src/lib/` |
| 职责不清 | 组件做了多件事 | 按关注点分离 |
| 性能问题 | 首屏慢、水合大 | 延迟加载 / 减少 Island |
| 类型不安全 | `any` / 缺少接口 | 补充 TypeScript 类型 |

### 2. 确定安全边界

重构前确认：
- 哪些组件依赖当前实现？（检查 import 关系）
- 是否有 Layout/Page 直接引用即将拆分的 export？
- 是否有 inline script 依赖特定的 DOM 结构/class 名？

### 3. 组件拆分

遵循 Islands 原则：

```
大组件 (300+ 行)
├── 静态展示部分 → 拆为 Astro 子组件（不需要水合）
├── 交互逻辑部分 → 保留为 React Island
└── 工具函数 → 提取到 src/lib/
```

**拆分步骤**：
1. 识别可独立的子树（有明确的 props 边界）
2. 创建新组件文件
3. 定义 Props 接口
4. 移动代码 + 样式
5. 在父组件中引用新子组件
6. 验证行为不变

### 4. 函数提取

识别可复用逻辑：

```typescript
// 从组件中提取到 src/lib/ 的信号：
// 1. 多个组件需要相同逻辑
// 2. 纯函数（无副作用）
// 3. 与 UI 无关的数据处理

// src/lib/helpers.ts
export function formatDuration(minutes: number): string { ... }
export function slugify(text: string): string { ... }
```

### 5. 性能优化

| 问题 | 解法 |
|------|------|
| Island 太大 | 拆分 / dynamic import / 换 client:visible |
| 首屏加载慢 | 减少 client:load，改 client:idle |
| 不必要的 JS | 用 Astro 组件替代不需要交互的 React |
| CSS 过大 | 删除未使用的全局样式 |
| 图片/字体大 | 优化资源 / 延迟加载 |

### 6. 验证

```bash
# 构建对比
pnpm build
# 检查 dist/ 体积变化

# 功能验证
pnpm dev
# 逐个验证重构涉及的页面/组件：
# - 行为与重构前完全一致
# - 响应式正常
# - 交互正常
```

## 质量标准

- [ ] 外部行为不变（用户看到的完全一样）
- [ ] `pnpm build` 通过
- [ ] TypeScript 无新增错误
- [ ] 代码更清晰（职责单一、命名准确）
- [ ] 无回归（相邻功能正常）
- [ ] 如涉及性能，有量化验证（dist 体积、lighthouse 分数等）

## 禁止动作

❌ 不要在重构中偷偷加新功能（纯重构不改行为）
❌ 不要一次性重构过多文件（小步迭代）
❌ 不要破坏现有的 import 路径而不更新所有引用
❌ 不要把 Astro 组件改成 React Island（除非有充分的交互理由）
❌ 不要删除看似"没用"的 data-* 属性（可能有 CSS 或 JS 依赖）
❌ 不要合并多个小组件为一个大组件（方向反了）
