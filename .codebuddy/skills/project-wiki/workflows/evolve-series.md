# 工作流：evolve-series（教程系列迭代演进）

对已有教程系列进行持续改进：补充新课时、更新已有内容、适配引擎版本升级。

## 触发场景

### 主动触发

- 用户说"优化 GAS 教程第 3 篇"、"给网络同步系列补一篇 XX"
- 用户说"UE 升级到 5.8 了，教程需要更新"
- 用户审核教程后指出问题："这篇的 XX 部分不够深入"

### 被动触发（从其他工作流路由过来）

- **teach** 工作流回答问题后发现：某个教程系列缺少对应课时 → 建议 evolve-series
- **ingest** 工作流消化外部资料后发现：新资料包含对已有教程的重要补充 → 建议 evolve-series
- **crystallize** 工作流沉淀对话后发现：当前分析可以充实某篇教程 → 建议 evolve-series
- **lint** 工作流检测到 `anchor-changed` → 对应教程页可能需要更新

## 与 create-series 的关系

| | create-series | evolve-series |
|---|---|---|
| 前提 | 系列不存在 | 系列已存在 |
| 输出 | 完整新系列 | 增量改动（补课时/更新/版本适配） |
| 共享 | **Phase 1 源码调研** 和 **Phase 5 质量验证** 的标准完全相同 |

**关键共识**：evolve-series 的质量标准**等同于** create-series，不因为是"小改动"就放松源码验证。

## 三种迭代模式

### 模式 A：补充新课时（Extend）

已有系列新增一篇或多篇课时。

**触发示例**：
- "GAS 教程缺少 TargetActor 的专门讲解，补一篇"
- "网络同步系列缺少 NetDormancy 的内容"

**步骤**：

1. **读取 `_series.yaml`** — 了解系列当前结构和学习路径
2. **确定插入位置** — 新课时放在哪个 stage、编号是什么
   - 如果是在中间插入，需要重编号（使用 `rename_page.py`）
   - 推荐：尽量在末尾追加，或使用子编号（如 `05a-xxx`）避免大规模重编号
3. **源码调研**（遵循 `ai-playbook.md` §源码为信源）
   - 推荐使用 SubAgent 进行源码分析
   - 读取引擎层 + Lyra 层相关代码
4. **撰写新课时** — 遵循 `create-series` Phase 4 的单篇撰写规范
5. **更新 `_series.yaml`** — 在 `learning_path` 相应 stage 中添加新课时，更新 `total_lessons`
6. **更新 index.md** — 在系列区块中插入新条目
7. **更新前后课时的链接** — 调整上一课/下一课的 related 和 nav 块
8. **lint 验证 + 自检清单**

### 模式 B：更新已有课时（Update）

对已有课时的内容进行修正、深化、补充。

**触发示例**：
- "GAS 第 2 篇的执行流程分析不够深入，需要补充 AbilityTask 的交互"
- `anchor-changed` lint 告警：对应源码已变化
- teach 工作流发现教程描述与当前源码不一致

**步骤**：

1. **读取目标教程页** — 了解当前内容
2. **定位变更范围**：
   - 内容不够深入 → 需要补充源码分析段落
   - 源码已变化 → 需要重新读取源码、更新代码引用和解读
   - 描述有误 → 需要修正并标注修正原因
3. **源码重新验证**（关键！）
   - 即使只改一段，也必须重新读取对应源码确认
   - 推荐使用 SubAgent：`"读取 <file> 的 <function>，确认当前实现是否与教程描述一致"`
4. **更新内容** — 修改目标段落，保持整体结构不变
5. **更新 frontmatter** — `last_synced` 和 `last_verified` 更新为当天
6. **检查连锁影响**（必须走图谱）

   evolve 改了关键结论后，**所有反向引用页都可能需要联动更新**。wiki_query.py 的 seed 模式专为此设计——一次性看到 related / inverse-prereq / 同系列邻居 / inbound 数：

   ```bash
   python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py --id 30-tutorials/<slug>/<page-id>
   ```

   重点关注输出里的：
   - **inbound 数**（被多少页引用，高 inbound = 改动影响面大）
   - **NEIGHBORS 中 `via:needed-by`**（依赖此页作为 prereq 的下游教程，必须连带评估）
   - **NEIGHBORS 中 `via:related`**（双向关联页，结论变化时需要回检）

   只有 `wiki_query.py` 不可用时才退回手工：
   ```bash
   rg -l '\[\[30-tutorials/<slug>/<page-id>\]\]' Docs/
   ```
7. **lint 验证**

### 模式 C：版本适配（Upgrade）

UE 引擎版本升级后，系统性更新教程系列。

**触发示例**：
- "UE 从 5.7 升到 5.8，GAS 系列需要适配"
- 新引擎版本引入了重大 API 变化

**步骤**：

1. **评估影响范围**：
   ```bash
   # 找出所有标注了目标 UE 版本的教程
   rg -l 'ue_version.*5\.7' Docs/30-tutorials/<slug>/
   rg 'UE 5\.7' Docs/30-tutorials/<slug>/
   ```
2. **收集版本差异**：
   - 阅读 UE Release Notes / Migration Guide
   - WebSearch 新版本的 API 变化
   - 对比新旧引擎源码（如果可用）
3. **逐篇评估**：对每篇教程标记影响级别
   - 🟢 无影响：API 未变
   - 🟡 轻微影响：参数/签名微调，需更新代码引用
   - 🔴 重大影响：架构变化，需要重写该课时
4. **逐篇更新**（按影响级别排序，先改 🔴 再改 🟡）
   - 每篇都需要重新验证源码
   - 更新代码引用中的版本标注
5. **更新 `_series.yaml`** — 更新 `ue_version` 字段
6. **更新系列概览页** — 在概述中标注版本变化
7. **全系列 lint 验证**

## 从其他工作流路由到 evolve-series

### teach → evolve-series

当 teach 工作流回答技术问题后发现知识库缺口：

```markdown
💡 **知识库改进建议**：
- 当前 [[30-tutorials/gas/02-ga-execution-flow]] 未覆盖 AbilityTask 的异步回调机制
- 建议走 evolve-series 补充该内容（模式 B: Update）
- 预估工作量：在"源码深度分析"段落新增 ~50 行
```

AI 应主动向用户提出建议，但**不自动执行**——等用户确认后再走 evolve-series。

### ingest → evolve-series

当 ingest 工作流消化外部资料时，发现与已有教程相关：

```markdown
💡 **已有教程可改进**：
- 刚消化的文章介绍了 UE 5.8 对 GAS 预测系统的改进
- [[30-tutorials/gas/23-prediction-key]] 目前基于 UE 5.7，可能需要更新
- 建议走 evolve-series 确认并更新（模式 B 或 C）
```

### crystallize → evolve-series

当 crystallize 沉淀当前对话时，发现分析内容可以充实教程：

```markdown
💡 **可合并到教程**：
- 当前沉淀的 "Lyra 武器系统 TargetData 网络序列化分析" 
- 可以补充到 [[30-tutorials/network-sync/05-rep-layout-fast-array-netguid]] 的 FastArray 部分
- 建议走 evolve-series（模式 B: Update）而非独立建页
```

## 质量约束（与 create-series 共享）

### 源码验证（强制）

遵循 `ai-playbook.md` §源码为信源。所有三种模式的任何改动，都必须：
- 读取对应源码确认技术事实
- 更新代码引用的文件路径和行号
- 推荐使用 SubAgent 做源码分析

### 自检清单

每次 evolve-series 操作完成后：

- [ ] 改动的技术断言都有源码支撑
- [ ] frontmatter `last_synced` 已更新
- [ ] 如果修改了关键结论，检查了引用方是否需要连锁更新
- [ ] `_series.yaml` 与实际文件一致（课时数、learning_path）
- [ ] lint 通过（0 ERROR）
- [ ] nav 块正确（如果改了课时编号，运行 `nav_inject.py --apply`）

## 反模式（禁止）

| 反模式 | 正确做法 |
|--------|---------|
| "就改一句话不用验证源码" | **任何改动都必须重新确认对应源码** |
| 直接在教程中插入 teach 回答的原文 | 需要按教程格式重写（由浅入深 + 源码引用） |
| 补了新课时但没更新 `_series.yaml` | **同步更新 learning_path 和 total_lessons** |
| 版本升级时只改了版本号标注 | 必须逐篇验证 API 是否真的没变 |
| 引擎源码没变就认为教程不用动 | 可能教程本身就有不够深入/不够准确的地方 |
