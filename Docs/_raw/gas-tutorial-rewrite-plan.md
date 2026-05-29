# GAS 教程重写任务规划

> **目标**：基于 UE 5.7 源码和 Lyra 项目示例，重新整理全面详细的 GAS 教程，整合到项目知识库
>
> **现状**：现有教程基于 UE 5.3，可能存在过时、废弃或不准确的内容
>
> **创建时间**：2026-05-16

## 任务范围

### 现有教程文件分析（25个文件）

```
Docs/_raw/external/GAS/
├── GAS-总览.md
├── GAS-上下文信息-GameplayEffectContext.md
├── GAS-属性(Attribute).md
├── GAS-预判机制(PredictionKey).md
├── GAS-零散记录.md
├── AbilityTask.md
├── GA-1.0简介&配置说明.md
├── GA-2.0执行流程详解.md
├── GA-3.0输入绑定.md
├── GA-4.0 GameplayEvent.md
├── GA-5.0目标信息.md
├── GC-1.0简介&配置.md
├── GC-2.0运行时详解.md
├── GE-1.0简介&配置.md
├── GE-2.0运行流程详解.md
├── GE-3.0数值修正.md
├── GE-4.0属性捕获.md
├── GE-5.0属性修正.md
├── GE-6.0扩展效果之自定义执行类.md
├── GE-7.0扩展效果之GE组件.md
├── GE-8.0匹配查询.md
├── GE-9.0网络复制.md
├── Tag-1.0简介&配置.md
├── Tag-2.0收集&构建.md
├── Tag-3.0集合容器.md
├── Tag-4.0匹配查询.md
└── Tag-5.0网络复制.md
```

## 执行计划

### 阶段一：信息收集与分析（并行）

#### 1.1 现有教程分析
- **目标**：提取现有教程的结构、内容要点、代码示例
- **方法**：使用 SubAgent 读取和分析所有 25 个文件
- **输出**：现有教程内容摘要、需要验证的知识点列表

#### 1.2 UE 5.7 GAS 源码分析
- **目标**：找出 UE 5.3 到 UE 5.7 之间 GAS 的变化
- **重点类**：
  - `UAbilitySystemComponent`
  - `UGameplayAbility`
  - `UGameplayEffect`
  - `UGameplayAbilityTask`
  - `UGameplayCueManager`
  - `FGameplayTagCountContainer`
  - `FGameplayEffectSpec`
  - `FActiveGameplayEffect`
- **方法**：使用 SubAgent 搜索 UE 5.7 源码，对比变化
- **输出**：UE 5.7 GAS 变化清单、新增特性、废弃接口

#### 1.3 Lyra 项目 GAS 用法分析
- **目标**：提取 Lyra 项目中 GAS 的实际用法示例
- **重点文件**：
  - `LyraAbilitySystemComponent`
  - `LyraGameplayAbility`
  - `LyraHealthSet` (AttributeSet 示例)
  - 各种 GA、GE、GC 配置
- **方法**：使用 SubAgent 分析 Lyra 源码和蓝图配置
- **输出**：Lyra GAS 用法示例库

### 阶段二：教程重写（分模块）

#### 2.1 核心概念篇
- GAS 系统总览（基于 UE 5.7）
- 核心类关系图
- GAS 调试方法

#### 2.2 GameplayAbility (GA) 篇
- GA 简介与配置（UE 5.7 更新）
- GA 执行流程详解
- GA 输入绑定
- GA GameplayEvent
- GA 目标信息
- GA 网络复制与预测

#### 2.3 GameplayEffect (GE) 篇
- GE 简介与配置（UE 5.7 更新）
- GE 运行流程详解
- GE 数值修正
- GE 属性捕获
- GE 属性修正
- GE 自定义执行类
- GE 组件（UE 5.3+ 新特性详解）
- GE 匹配查询
- GE 网络复制
- GE 堆叠机制

#### 2.4 GameplayTag (Tag) 篇
- Tag 简介与配置
- Tag 收集与构建
- Tag 集合容器
- Tag 匹配查询
- Tag 网络复制

#### 2.5 GameplayCue (GC) 篇
- GC 简介与配置
- GC 运行时详解

#### 2.6 AbilityTask 篇
- AbilityTask 详解
- 常用 Task 示例

#### 2.7 高级主题篇
- GAS 预判机制（PredictionKey）
- GAS 上下文信息（GameplayEffectContext）
- GAS 属性系统（AttributeSet）
- GAS 网络架构
- GAS 性能优化

### 阶段三：整合到项目知识库

#### 3.1 确定知识库位置
- 外部知识：`Docs/50-references/gas-tutorial/`
- 或者作为专题教程：`Docs/60-topics/gas/`

#### 3.2 创建知识库页面
- 按照 `project-wiki` schema 创建页面
- 添加正确的 frontmatter
- 更新 `Docs/index.md`

#### 3.3 验证与迭代
- 运行 lint 检查
- 验证代码示例准确性
- 标记内容状态

## 并行执行策略

使用 SubAgent 并行分析：
1. **SubAgent A**：分析现有教程所有文件
2. **SubAgent B**：分析 UE 5.7 GAS 源码变化
3. **SubAgent C**：分析 Lyra 项目 GAS 用法

然后汇总分析结果，制定详细的重写方案。

## 注意事项

1. **代码准确性**：所有代码示例必须基于 UE 5.7 源码验证
2. **图片处理**：现有教程中的图片链接可能失效，需要重新截图或绘制 mermaid 图
3. **mermaid 优先**：按照 `ai-playbook.md` 要求，用 mermaid 替代 ASCII art
4. **标注来源**：明确标注内容来源（UE 源码 / Lyra 示例 / 官方文档）
5. **标记状态**：新写的内容标记为 `status: current`

## 开始执行

- [ ] 阶段一：信息收集与分析
  - [ ] 1.1 现有教程分析（SubAgent A）
  - [ ] 1.2 UE 5.7 GAS 源码分析（SubAgent B）
  - [ ] 1.3 Lyra 项目 GAS 用法分析（SubAgent C）
- [ ] 阶段二：教程重写
  - [ ] 2.1 核心概念篇
  - [ ] 2.2 GA 篇
  - [ ] 2.3 GE 篇
  - [ ] 2.4 Tag 篇
  - [ ] 2.5 GC 篇
  - [ ] 2.6 AbilityTask 篇
  - [ ] 2.7 高级主题篇
- [ ] 阶段三：整合到项目知识库
  - [ ] 3.1 确定知识库位置
  - [ ] 3.2 创建知识库页面
  - [ ] 3.3 验证与迭代
