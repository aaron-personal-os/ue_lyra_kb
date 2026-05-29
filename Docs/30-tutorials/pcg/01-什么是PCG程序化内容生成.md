---
id: 30-tutorials/pcg/01-什么是PCG程序化内容生成
title: 什么是PCG程序化内容生成
description: "介绍PCG（程序化内容生成）框架的核心价值——通过规则驱动替代手工布置，解决关卡设计中的变体爆炸和迭代效率问题"
type: tutorial
status: current
language: zh
owner: ai
series: pcg
lesson_index: 1
difficulty: beginner
prerequisites: [30-tutorials/pcg/00-overview]
tags: [pcg, procedural, basics]
last_synced: 2026-05-17
---

# 什么是PCG程序化内容生成

> **前置知识**：无
> **预计阅读时间**：15 分钟

## 概念直觉

### 从"手工布置"到"规则驱动"

**传统关卡设计流程**：
```
美术手动摆放 1000 棵树
→ 耗时 8 小时
→ 修改地形后全部重摆
→ 性能有问题，继续调整...
```

**PCG 工作流程**：
```
定义规则："在坡度 < 30° 的区域生成树木，密度随海拔降低"
→ PCG 自动生成 1000 棵树
→ 修改地形后自动更新
→ 调整参数即可全局控制
```

**核心思想**：用 **算法 + 数据** 替代手工劳动。

### PCG 能做什么？

| 应用场景 | 示例 | 传统方式痛点 |
|---------|------|-------------|
| **自然场景** | 森林、草地、岩石分布 | 手工摆放工作量巨大 |
| **城市生成** | 建筑、街道、道具 | 重复性高，难以统一风格 |
| **地牢/迷宫** | 随机房间、通道 | 每次都需要重新设计 |
| **细节填充** | 垃圾、杂草、装饰物 | 容易遗漏，破坏沉浸感 |

### PCG 的核心优势

1. **高效迭代**：修改参数 → 即时预览，无需手工重做
2. **可控随机**：随机中保持艺术控制（不是完全随机）
3. **性能友好**：支持 LOD、流式加载、实例化渲染
4. **可复用**：规则可以保存为资产，跨项目复用

---

## 技术机制

### UE5 PCG 框架架构

```
PCG Volume (体积)
    ↓ 定义生成区域
PCG Component (组件)
    ↓ 执行生成
PCG Graph (图表)
    ↓ 包含
PCG Nodes (节点)
    ↓ 处理
PCG Data (数据)
    ↓ 输出
Actor / Instance (结果)
```

### 核心类概览

基于源码 `Engine/Plugins/PCG/Source/PCG/Public/`：

| 类 | 职责 | 关键方法 |
|---|---|---|
| `UPCGComponent` | PCG 执行入口 | `Generate()`、`Cleanup()` |
| `UPCGGraph` | 节点网络容器 | `Execute()` |
| `UPCGNode` | 单个处理单元 | `Execute()` |
| `UPCGData` | 数据基类 | `GetDimension()` |
| `FPCGPoint` | 点数据（位置+属性） | `Transform`、`Density` |

### PCG 工作流程（简化版）

```mermaid
graph LR
    A[PCG Volume] -->|触发| B[PCG Component]
    B -->|执行| C[PCG Graph]
    C -->|遍历| D[PCG Node 1]
    D -->|输出| E[PCG Node 2]
    E -->|输出| F[...]
    F -->|最终| G[生成 Actor/Instance]
```

### 与 Lyra 的关系

**Lyra 当前未直接使用 PCG**，但 PCG 可以很好地补充 Lyra 的世界构建：

- **Lyra 的世界**：主要是手工布置 + 模块化资产
- **PCG 的补充**：大规模自然场景、细节填充、动态内容

> **学习建议**：即使 Lyra 没用 PCG，掌握 PCG 对 UE5 技术栈非常重要。

---

## 实践案例

### 案例 1：创建第一个 PCG 生成

**目标**：在地面上自动生成 100 个点。

#### 步骤 1：启用 PCG 插件

1. `Edit` → `Plugins`
2. 搜索 `PCG`
3. 勾选 `PCG Framework`
4. 重启编辑器

#### 步骤 2：创建 PCG 图表

1. 内容浏览器右键 → `PCG` → `PCG Graph`
2. 命名：`PCG_TestGraph`
3. 双击打开

#### 步骤 3：添加节点

在 PCG 图表中添加：

```
[Surface Sampler] → [Transform Points] → [Debug Draw]
```

- **Surface Sampler**：在地面上采样点
- **Transform Points**：调整点的位置/旋转/缩放
- **Debug Draw**：可视化点（调试用）

#### 步骤 4：配置 Surface Sampler

| 参数 | 值 | 说明 |
|-----|---|---|
| `Density` | 1.0 | 点密度 |
| `Bounds Modifier` | `PCG Volume` | 使用 Volume 的范围 |
| `Loose Bounds` | 1000x1000 | 生成范围 |

#### 步骤 5：测试

1. 场景中放置 `PCG Volume`
2. 将 `PCG_TestGraph` 赋值给 Volume 的 `PCG Component`
3. 点击 `Generate`

**预期结果**：Volume 范围内出现蓝色点（Debug Draw）。

---

## 常见错误

### Error 1：PCG 没有生成任何内容

**症状**：点击 Generate 后没有任何反应。

**排查**：
1. 检查 `PCG Volume` 是否勾选 `Auto Generate`
2. 检查 `PCG Graph` 是否有有效的输出节点
3. 检查 Scene Complexity（场景复杂度）是否过高

**解决**：
```cpp
// 源码位置：PCGComponent.cpp
void UPCGComponent::Generate()
{
    if (!bActivated) return; // ← 检查这个标志
    // ...
}
```

### Error 2：性能爆炸（生成太慢）

**症状**：Generate 需要 10+ 秒。

**原因**：
- 点数量过多（>10000）
- 节点图太复杂
- 没有使用 Instance 渲染

**解决**：
1. 降低 `Density`
2. 使用 `Static Mesh Spawner`（实例化）
3. 分区域生成（多个 PCG Volume）

---

## 延伸阅读

### 官方文档
- [PCG 框架官方文档](https://dev.epicgames.com/documentation/zh-cn/unreal-engine/procedural-content-generation-framework-in-unreal-engine)
- [PCG 快速入门](https://dev.epicgames.com/documentation/zh-cn/unreal-engine/procedural-content-generation-quick-start-guide-in-unreal-engine)

### 源码参考
- `Engine/Plugins/PCG/Source/PCG/Public/PCGComponent.h`
- `Engine/Plugins/PCG/Source/PCG/Public/PCGGraph.h`

### 社区教程
- [Reids Channel - PCG 教程系列](https://www.youtube.com/watch?v=PL_9jbU_gxY)
- [PrismaticaDev - PCG 高级技巧](https://www.youtube.com/watch?v=bkMJOvem3FI)

---

## 总结

通过本篇你学到了：

1. **PCG 是什么** — 程序化内容生成框架，用规则替代手工布置
2. **核心价值** — 高效迭代、可控随机、性能友好、可复用
3. **与手工布置对比** — PCG 是"定义规则 → 自动生成"，不是手动摆放
4. **第一个 PCG 生成** — 使用 Surface Sampler + Transform Points + Debug Draw

---

## 下一步

→ **下一课**：[02-核心组件详解](./02-PCG核心组件详解.md) — 深入理解 PCG Component、Graph、Node 的实现机制。

<!-- nav:auto -->

---

**导航**: ← [[30-tutorials/pcg/00-PCG程序化内容生成框架教程系列|00-PCG程序化内容生成框架教程系列]] · [[30-tutorials/pcg/02-PCG核心组件详解|02-PCG核心组件详解]] →

<!-- /nav:auto -->
