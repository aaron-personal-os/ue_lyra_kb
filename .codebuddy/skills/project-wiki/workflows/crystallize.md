# 工作流：crystallize（结晶化当前会话）

把当前 AI 会话里**刚搞清楚的事**沉淀成 wiki 页面，避免下次重新推导。

## 触发场景

- 用户说"把这个记进 wiki" / "crystallize" / "沉淀一下"
- query 工作流末尾，发现答案是有结构的分析（不是事实查询）
- 解决了一个非平凡的技术理解问题后
- 完成了一次架构/机制分析后

## 与 ingest 的区别

| | ingest | crystallize |
|---|---|---|
| 输入 | 外部素材文件/URL | 当前会话内容 |
| 风格 | 提取/重组 | 抽象/归纳 |
| raw 落地 | 必定（`_raw/...`） | 可选（`_raw/chats/`） |
| 频次 | 主动触发 | 既可主动也可 AI 提议 |

## 步骤

### 0. 查重（必须先做）

★ crystallize 是"创建新页"场景，query 路由表中**禁止跳过图层**——否则极易产生与已有教程重复的孤立页。

```bash
# 用本次会话的核心结论作为查询词
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "<会话核心关键词>"
```

判定：
- 找到高度重合页（score ≥ 6）→ **走 evolve-series 补充该页**而非 crystallize 新建
- 找到 1-HOP 邻居中有相关教程系列 → 考虑作为系列新课时（`30-tutorials/<series>/`）
- 完全无重合 → 才走下文步骤 1+ 创建新页（务必把查到的相关页作为 `related:` 候选）

### 1. 决定目标层级

按当前会话的核心产出性质：

- **搞清了"如何做 X"的步骤** → `30-tutorials/<series>/<slug>.md`
- **做了一个架构/技术选型决策** → `60-decisions/NNNN-<slug>.md`
- **梳理了一个横切主题** → `70-topics/<slug>.md`
- **踩了一个坑 / 发现了一个易错点** → `80-gotchas/<slug>.md`
- **记录了某个时间点的系统状态** → `90-snapshots/<slug>.md`

### 2. 抽取核心

从会话里抽出**至少包含**：

- **背景**：为什么会讨论这件事？（一段）
- **结论**：最终的事实/决策/方案（要点形式）
- **理由**：为什么是这个结论而不是别的（如适用）
- **下次需要避免的事**（如适用）

**不要复制粘贴整个对话**。

### 3. 锚定到代码（关键）

若结论涉及代码：

```yaml
anchors:
  - path: Source/LyraGame/AbilitySystem/Abilities/LyraGameplayAbility.cpp
  - path: Source/LyraGame/Character/LyraCharacter.cpp
```

**没有 anchor 的页极易腐烂**，必须挂一个。即使是纯设计页也要挂相关代码入口。

### 4. 可选：保存会话原文

若会话有保留价值（之后可能要追溯），把关键对话片段（**只截取相关段**）保存到：

```
Docs/_raw/chats/<YYYY-MM-DD>-<slug>.md
```

页面 frontmatter 加 `sources: ["[[_raw/chats/2026-05-17-lyra-gas-activation-flow]]"]`。

### 5. 更新 index.md + log.md

```
## [2026-05-17] crystallize | <wiki-id>
- 来源：当前会话
- 触发：用户主动 / 技术分析 / 完成决策
- 摘要：1-2 句
```

### 6. 双向链接

至少与 1 个已有页建立 `[[...]]` 关联。如果完全独立，重新评估是否真有沉淀价值。

## 反模式（不要做）

- ❌ **跳过步骤 0 查重直接 create** — 极易产生重复页 / 孤立页（query 路由表中"创建新页"禁止跳图层）
- ❌ 把会话原文直接当 wiki 页（会话太长、信噪比低）
- ❌ 沉淀"刚刚发生的临时事件"（如某次 lint 输出），这种走 log.md
- ❌ 沉淀**用户自己说的话**而不是双方共识（标好 owner）
- ❌ 沉淀**未验证的假设**而不标 `status: draft`
