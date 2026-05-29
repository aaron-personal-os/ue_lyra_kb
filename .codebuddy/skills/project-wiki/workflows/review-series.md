# 工作流：review-series（教程系列质量审查）

对已有教程系列进行系统性质量审查，从专业性、准确性、教学设计、结构一致性等多维度检查，输出改进建议或直接修复。

## 触发场景

- 用户说"review XX 教程系列"、"检查 XX 系列质量"、"审查教程"
- 教程系列刚创建完毕，需要质量把关
- 定期巡检（如每月一次系列级复盘）
- 用户对教程质量有疑虑："这个系列是不是写得太浅了"

## 与其他工作流的关系

| | lint | review-series | evolve-series |
|---|---|---|---|
| 粒度 | **字段/格式级**（frontmatter、wikilink） | **内容/教学级**（准确性、深度、结构） | **实施级**（实际执行改动） |
| 输出 | lint 报告（PASS/FAIL） | review 报告（改进建议清单） | 改动后的文件 |
| 关系 | 前置（先 lint 再 review） | 上游（产出建议） | 下游（执行建议） |

**典型流程**：`lint` → `review-series` → 用户确认 → `evolve-series` 执行改动

---

## 审查模式

### 模式 A：系列级审查（Full Review）

对整个系列做端到端审查。适用于新系列创建后首次审查、定期巡检。

### 模式 B：单篇审查（Page Review）

对系列中某一篇做深度审查。适用于用户指定某篇有问题、evolve-series 修改后的验证。

### 模式 C：跨系列一致性审查（Cross-Series Review）

检查多个系列间的概念定义、难度层级、交叉引用是否一致。适用于系列数 ≥ 3 后的全局巡检。

---

## 步骤

### Phase 0：确认审查范围

向用户确认：
- **审查目标**：哪个系列？（或全部系列）
- **审查模式**：Full / Page / Cross-Series
- **重点关注**：是否有特别想检查的维度？（默认全维度）
- **输出形式**：仅报告 / 报告 + 自动修复简单问题

---

### Phase 1：前置检查

> **在深度审查前，先跑格式级检查排除低级问题。**

#### 1.1 Lint 检查

```bash
python ToolsScript/check_frontmatter.py --check
# 确保 0 ERROR 后再进入内容审查
```

若 lint 有 ERROR → 先报告给用户，建议先修复格式问题再做内容审查。

#### 1.2 读取系列元数据

```bash
# 读取 _series.yaml
Read Docs/30-tutorials/<slug>/_series.yaml

# 读取系列所有教程的 frontmatter
rg -l 'series: <slug>' Docs/30-tutorials/<slug>/

# 统计系列实际文件数
ls Docs/30-tutorials/<slug>/*.md | wc -l
```

#### 1.3 建立审查上下文

- 读取系列概览页（`00-overview`）了解系列定位
- 读取 `_series.yaml` 确认 learning_path 和 lesson 列表
- 列出系列所有课时文件名和标题

---

### Phase 2：多维度审查

> **这是核心阶段。推荐使用 SubAgent 并行进行多维度审查。**

推荐 SubAgent 分工：

```
主 Agent（编排 + 汇总）
    │
    ├── SubAgent-A：专业性与准确性审查
    │   - 源码验证
    │   - 技术断言检查
    │   - API 准确性
    │
    ├── SubAgent-B：教学设计审查
    │   - 由浅入深检查
    │   - 难度曲线
    │   - 知识密度
    │
    └── SubAgent-C：结构与一致性审查
        - 系列顺序合理性
        - frontmatter 规范性
        - 交叉引用完整性
```

---

#### 维度 1：专业性与准确性（Accuracy & Professionalism）

> **参考 create-series §质量标杆 和 ai-playbook §源码为信源**

##### 检查点

| # | 检查项 | 严重级 | 说明 |
|---|--------|--------|------|
| A1 | **源码引用可验证** | 🔴 Critical | 教程中引用的源码段能在对应文件中找到（允许行号偏移 ±20） |
| A2 | **技术断言有据** | 🔴 Critical | 每个"X 会导致 Y"、"X 的作用是 Y"有源码/官方文档支撑 |
| A3 | **类名/函数名拼写正确** | 🔴 Critical | 所有代码标识符可在源码中 grep 到 |
| A4 | **API 签名匹配当前版本** | 🟡 Major | 函数参数列表、返回值与源码一致（标注的 UE 版本下） |
| A5 | **Lyra 源码引用真实存在** | 🔴 Critical | `lyra_sources` 路径在 `Source/LyraGame/` 下确实存在 |
| A6 | **引擎源码引用路径有效** | 🟡 Major | `engine_sources` 路径格式正确（`Engine/...`） |
| A7 | **版本标注一致** | 🟡 Major | 文中提到的 UE 版本与 frontmatter / `_series.yaml` 一致 |
| A8 | **无过时信息** | 🟡 Major | 没有引用已废弃的 API 或已移除的功能 |
| A9 | **设计决策有分析** | 🟢 Minor | 核心机制篇不仅讲"是什么"还讲"为什么这样设计" |
| A10 | **边界情况覆盖** | 🟢 Minor | 提到了异常路径、性能影响、线程安全等 |

##### 验证方法

```bash
# 批量验证类名/函数名是否存在
rg -n '<ClassName>' Source/LyraGame/ --include='*.h' --include='*.cpp'

# 验证引擎源码路径（需要先获取引擎根路径）
# powershell -NoProfile -ExecutionPolicy Bypass -File ./get_engine_root.ps1 -Json

# 批量提取教程中的代码引用路径
rg 'Engine/.*\.(h|cpp)' Docs/30-tutorials/<slug>/ --no-filename | sort -u
```

---

#### 维度 2：教学设计（Pedagogical Design）

> **参考 ai-playbook §教学表达约束 和 create-series §Phase 2 大纲设计**

##### 检查点

| # | 检查项 | 严重级 | 说明 |
|---|--------|--------|------|
| P1 | **由浅入深** | 🔴 Critical | 每篇先概念直觉再源码分析，不在开头贴大段代码 |
| P2 | **三层教学结构** | 🟡 Major | 包含：概念直觉 → 技术机制 → Lyra 实例 |
| P3 | **概览页不过深** | 🟡 Major | `00-overview` 只给全景图+导航，不深入单个机制 |
| P4 | **独立可读性** | 🟡 Major | 每篇有明确学习目标，不依赖"你应该已经知道"的隐含假设 |
| P5 | **前置知识标注** | 🟡 Major | `prerequisites` 字段完整且指向的页面确实存在 |
| P6 | **代码量适度** | 🟢 Minor | 单个代码块不超 40 行，关键行有 `[N]` 编号注释 |
| P7 | **图示辅助** | 🟡 Major | 核心机制篇至少 1 个 mermaid 图，推荐 2-3 个 |
| P8 | **总结要点** | 🟢 Minor | 每篇末尾有 3-5 条核心要点总结（表格或列表） |
| P9 | **知识密度均匀** | 🟢 Minor | 各篇行数差异不超过 2 倍（除概览页外） |
| P10 | **术语首次出现有解释** | 🟡 Major | 专业术语首次出现时有括号解释或链接到 glossary |

##### 检查方法

```bash
# 检查每篇是否有 mermaid 图
for f in Docs/30-tutorials/<slug>/*.md; do
  count=$(grep -c '```mermaid' "$f")
  echo "$f: $count mermaid blocks"
done

# 检查代码块行数
rg -U '```(cpp|c\+\+)[\s\S]*?```' Docs/30-tutorials/<slug>/ --count

# 检查是否有 [N] 编号注释
rg '\[[0-9]+\]' Docs/30-tutorials/<slug>/
```

---

#### 维度 3：系列顺序与结构（Series Structure）

> **参考 create-series §Phase 2 结构原则 和 .wiki-schema §教程系列元数据**

##### 检查点

| # | 检查项 | 严重级 | 说明 |
|---|--------|--------|------|
| S1 | **难度梯度合理** | 🔴 Critical | difficulty 从 beginner → intermediate → advanced 递进，无跳跃 |
| S2 | **prerequisites 链条完整** | 🔴 Critical | 每篇的 prerequisites 指向前序课时或其他系列的基础课 |
| S3 | **lesson_index 连续** | 🟡 Major | 编号无间断（00, 01, 02, ...），与 `_series.yaml` lessons 列表一致 |
| S4 | **learning_path 阶段划分** | 🟡 Major | `_series.yaml` 的 stage 划分与实际内容难度对应 |
| S5 | **先总后分** | 🟡 Major | 00-overview 给全景图，后续逐一深入子主题 |
| S6 | **概念依赖无环** | 🔴 Critical | 后篇不能依赖后续才讲的概念（前向引用） |
| S7 | **Lyra 案例放置** | 🟢 Minor | Lyra 综合案例分析推荐在系列末尾（或各篇内有小节） |
| S8 | **nav 导航块正确** | 🟡 Major | 上一课/下一课链接正确，边界篇处理得当 |
| S9 | **系列定位无重叠** | 🟢 Minor | 与其他系列的主题不重叠（>30% 重合需考虑合并） |
| S10 | **estimated_hours 合理** | 🟢 Minor | 根据篇数和难度，预估学习时长是否靠谱 |

##### 检查方法

```bash
# 提取所有 lesson_index 检查连续性
rg 'lesson_index:' Docs/30-tutorials/<slug>/ --no-filename | sort -n

# 提取难度分布
rg 'difficulty:' Docs/30-tutorials/<slug>/ --no-filename | sort

# 检查 prerequisites 引用是否有效
rg 'prerequisites:' -A 5 Docs/30-tutorials/<slug>/ | rg '\[\[' 

# 检查 nav 块
rg 'nav:auto' Docs/30-tutorials/<slug>/
```

---

#### 维度 4：格式与规范一致性（Formatting & Consistency）

> **参考 .wiki-schema §页面格式 和 ai-playbook §写 Wiki 规范**

##### 检查点

| # | 检查项 | 严重级 | 说明 |
|---|--------|--------|------|
| F1 | **frontmatter 完整** | 🔴 Critical | 必填字段全部存在（id, type, status, series, lesson_index, difficulty, last_synced, last_verified） |
| F2 | **id 与文件路径一致** | 🔴 Critical | frontmatter `id` == 文件路径去 `Docs/` 前缀和 `.md` 后缀 |
| F3 | **type 正确** | 🟡 Major | 概览页 = `guide`，课时页 = `tutorial`，案例 = `case-study` |
| F4 | **tags 有意义** | 🟢 Minor | tags 非空，且在系列内有一定共性 + 各课有区分 |
| F5 | **日期格式统一** | 🟢 Minor | `last_synced` / `last_verified` 为 `YYYY-MM-DD` 格式 |
| F6 | **图示用 mermaid** | 🟡 Major | 无 ASCII art 图示（目录树/日志输出豁免） |
| F7 | **正文结构标准** | 🟡 Major | 包含标准段落：概述 → 核心概念 → 源码分析 → Lyra 实践 → 总结 |
| F8 | **源码引用规范** | 🟡 Major | 标注文件路径 + 大致行号 + UE 版本，关键行有编号注释 |
| F9 | **wikilink 语法正确** | 🔴 Critical | `[[id]]` 格式无误，引用的页面存在 |
| F10 | **无裸 URL** | 🟢 Minor | 外部链接用 `[text](url)` 而非裸 URL |

---

#### 维度 5：内容完备性（Completeness）

> **参考 create-series §质量标杆 广度维度**

##### 检查点

| # | 检查项 | 严重级 | 说明 |
|---|--------|--------|------|
| C1 | **核心概念无遗漏** | 🟡 Major | 系列覆盖了该技术主题的所有核心子系统 |
| C2 | **引擎层 + Lyra 层双覆盖** | 🟡 Major | 不只讲引擎通用机制，还有 Lyra 的定制实现 |
| C3 | **常见问题/陷阱** | 🟢 Minor | 至少在高级篇或末尾覆盖了常见误区 |
| C4 | **网络同步（如适用）** | 🟡 Major | 涉及 Gameplay 的系列需覆盖网络复制/预测 |
| C5 | **性能考量** | 🟢 Minor | 重要操作标注了性能影响或最佳实践 |
| C6 | **related 页面链接** | 🟢 Minor | 各篇末尾有相关页面链接（模块文档、架构文档等） |

---

### Phase 3：生成审查报告

#### 3.1 报告格式

```markdown
# Review 报告：<系列名称>

> 审查日期：YYYY-MM-DD
> 审查模式：Full / Page / Cross-Series
> 审查篇数：N

## 评分摘要

| 维度 | 得分 | 评级 | 说明 |
|------|------|------|------|
| 专业性与准确性 | X/10 | ⭐⭐⭐⭐ | ... |
| 教学设计 | X/10 | ⭐⭐⭐⭐ | ... |
| 系列结构 | X/10 | ⭐⭐⭐⭐ | ... |
| 格式规范 | X/10 | ⭐⭐⭐⭐ | ... |
| 内容完备性 | X/10 | ⭐⭐⭐ | ... |
| **综合** | **X/10** | **⭐⭐⭐⭐** | ... |

### 评级标准
- ⭐⭐⭐⭐⭐ (9-10)：优秀，可作为其他系列的标杆
- ⭐⭐⭐⭐ (7-8)：良好，有小改进空间
- ⭐⭐⭐ (5-6)：合格，有明确改进方向
- ⭐⭐ (3-4)：需改进，存在较多问题
- ⭐ (1-2)：不合格，需要重大修改或重写



## 🔴 Critical 问题（必须修复）

| # | 检查项 | 影响文件 | 问题描述 | 建议修复方式 |
|---|--------|---------|---------|------------|
| 1 | A1 | `03-xxx.md` | L45 引用的 `DoSomething()` 在源码中不存在 | 验证源码后更正函数名 |
| ... | ... | ... | ... | ... |

## 🟡 Major 问题（建议修复）

| # | 检查项 | 影响文件 | 问题描述 | 建议修复方式 |
|---|--------|---------|---------|------------|
| ... | ... | ... | ... | ... |

## 🟢 Minor 问题（可选改进）

| # | 检查项 | 影响文件 | 问题描述 | 建议修复方式 |
|---|--------|---------|---------|------------|
| ... | ... | ... | ... | ... |

## 系列顺序评估

### 当前顺序
| # | 文件 | 难度 | 核心内容 |
|---|------|------|---------|
| 00 | ... | beginner | ... |
| 01 | ... | beginner | ... |
| 02 | ... | intermediate | ... |
| ... | ... | ... | ... |

### 顺序评价
- ✅ 顺序合理的部分：...
- ⚠️ 顺序待商榷的部分：...（附调整建议）

### 建议调整（如有）
| 原序号 | 建议新序号 | 原因 |
|--------|-----------|------|
| ... | ... | ... |

## 改进优先级

按 ROI（改进收益/工作量）排序的改进建议：

| 优先级 | 改进项 | 预估工作量 | 预期收益 | 执行方式 |
|--------|--------|-----------|---------|---------|
| P0 | ... | 小 | 高 | evolve-series 模式 B |
| P1 | ... | 中 | 高 | evolve-series 模式 B |
| P2 | ... | 大 | 中 | evolve-series 模式 A |
| ... | ... | ... | ... | ... |
```




#### 3.2 评分规则

每个维度 10 分制，扣分规则：

| 严重级 | 每个问题扣分 | 上限 |
|--------|-------------|------|
| 🔴 Critical | -2 | 该维度最低 1 分 |
| 🟡 Major | -1 | 该维度最低 2 分 |
| 🟢 Minor | -0.5 | 最多扣 3 分 |

综合分 = 加权平均（权重：准确性 30%、教学设计 25%、系列结构 20%、格式规范 15%、完备性 10%）



### 3.3 报告保存(**重要**)

**重要:生成的报告自动保存到到 Docs/_raw/review-reports 目录，以 Review-Report-<系列名称>-YYYY-MM-DD.md 的形式命名，不要在Index.md中引用**


---


### Phase 4：用户确认与执行

#### 4.1 报告呈现

将审查报告呈现给用户，用 `AskUserQuestion` 确认下一步：

```
审查完成，发现 X 个 Critical / Y 个 Major / Z 个 Minor 问题：
- ✅ 仅记录，稍后手动修复
- 🔧 自动修复 Critical + Major 问题（走 evolve-series）
- 🔧 全部修复（走 evolve-series）
```

#### 4.2 自动修复执行

如果用户选择自动修复：

1. **按优先级排序** — P0 → P1 → P2
2. **对每个修复项走 evolve-series 模式 B**：
   - 读取目标教程页
   - 源码重新验证
   - 执行修改
   - 更新 frontmatter
3. **每修复 5 项做一次增量验证**（避免级联错误）
4. **完成后重跑 lint + 受影响检查项**

#### 4.3 记录审查结果

```bash
# 追加到 log.md
## [YYYY-MM-DD] review-series | <系列名> 质量审查 → [[30-tutorials/<slug>/00-overview]]
- **审查模式**：Full / Page / Cross-Series
- **综合评分**：X/10 (⭐⭐⭐⭐)
- **问题统计**：Critical X / Major Y / Minor Z
- **已修复**：N 项
- **待修复**：M 项
```

---

## 模式 C 补充：跨系列一致性审查

当有 3+ 个教程系列时，额外检查：

| # | 检查项 | 说明 |
|---|--------|------|
| X1 | **术语定义一致** | 同一术语（如 "GameplayTag"）在不同系列中定义是否一致 |
| X2 | **难度标定一致** | 系列 A 的 "intermediate" 与系列 B 的 "intermediate" 难度是否匹配 |
| X3 | **交叉引用对称** | A 系列引用了 B 系列的课，B 系列是否回引 |
| X4 | **知识无矛盾** | 不同系列对同一技术机制的描述是否一致 |
| X5 | **学习路径衔接** | `learning-paths.md` 推荐的系列间顺序是否合理 |

---

## 反模式（禁止）

| 反模式 | 为什么不行 | 正确做法 |
|--------|-----------|---------|
| 只看 frontmatter 不读正文 | 格式合格 ≠ 内容合格 | **必须抽样阅读正文内容** |
| 不验证源码就判"准确" | AI 训练数据可能过时 | **关键断言必须 grep 源码验证** |
| 评分过宽/全给高分 | 失去审查价值 | **严格按扣分规则，宁严勿松** |
| 发现问题直接改不报告 | 用户失去可见性 | **先报告，用户确认后再改** |
| 把 lint 能查的问题重复列入 | 重复工作 | **Phase 1 先 lint，review 聚焦内容级问题** |
| 只审查不给改进建议 | 报告无行动价值 | **每个问题必须附建议修复方式** |

---

## 抽样策略

当系列篇数较多（>10 篇）时，不必逐篇做全维度深度审查：

| 步骤 | 方法 |
|------|------|
| 全系列扫描 | frontmatter 完整性 + lesson_index 连续性 + nav 块 → **全查** |
| 结构审查 | `_series.yaml` + 难度梯度 + 概念依赖 → **全查** |
| 内容深度审查 | 抽样 3-5 篇做源码验证 + 教学设计审查：<br>• 必选：`00-overview` + 最后一篇<br>• 随机：中间抽 2-3 篇（含不同难度） |
| 全量源码验证 | 仅在 Critical 问题较多时升级为全篇验证 |

---

## 定期审查建议

| 频率 | 触发 | 模式 | 范围 |
|------|------|------|------|
| 每次 create-series 后 | 自动建议 | Full Review | 新系列 |
| 每次 evolve-series 大改后 | 自动建议 | Page Review | 受影响篇 |
| 每月（可选） | 用户主动 | Cross-Series | 全部系列 |
| 引擎版本升级后 | 用户主动 | Full Review | 所有系列 |
