# 工作流：digest（深度综合 / 跨页分析）

跨多个 wiki 页做**综合性产出**，用于：

- 设计评审报告
- 多方案对比
- 某主题/模块的演化时间线
- 季度/版本快照（`90-snapshots/`）
- 给新人/新 AI 会话的 onboarding 摘要

## 与 query 的区别

| | query | digest |
|---|---|---|
| 输入 | 1 个具体问题 | 1 个主题 + 范围 |
| 输出 | 直接回答（短） | 结构化报告（长） |
| 是否落 wiki | 默认否（除非有保留价值） | **默认是**（落到 `70-topics/` 或 `90-snapshots/`） |
| 涉及页数 | 1-5 | 10+ |

## 步骤

### 1. 明确范围

向用户确认：
- 主题是什么？（如"GAS 能力系统的架构演化"）
- 范围多大？（仅 `Source/LyraGame/`？还是含 Blueprint？含插件？）
- 目标读者？（决定语言深度）
- 是否落 wiki 页？

### 2. 收集来源

★ **必须走图谱**（digest 是"多页综合"，query 路由表中**禁止跳过图层**的场景）。详见 [query 工作流](./query.md#按问题形态选检索路径)：

```bash
# 主题词 → 候选页（自动展开 alias，输出含 status 警告，避免引 stale）
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "<主题关键词>" --max-candidates 10 --json > /tmp/cands.json

# 系列性主题 → 系列模式列出整组课程
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py --series <slug> --json

# 已知一个核心页 → 沿 related / prereq / inverse-prereq 展开图邻居
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py --id <seed-id>

# 跨模块综合（如"GAS 涉及到的所有 cpp 模块"）→ 兜底用 anchor 路径查
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "<模块/路径关键词>"
```

输出包含：
- TOP N 候选 + 每个候选的 `prereq` / `related` 字段
- 1-HOP NEIGHBORS（含 `via:related / via:prereq / via:needed-by / via:series-*` 边类型）
- 全局 stale / deprecated 警告

**digest 是"重建因果链"场景**——务必沿 `prereq` / `needed-by` 展开 1-hop 甚至 2-hop（连续 wiki_query.py --id 邻居 id），把"设计 → 决策 → 演化 → 操作"的完整链路都拿到，再决定取舍。

得到候选页列表后，**读取每页 frontmatter**，过滤 `status: deprecated` 的（wiki_query.py 已标注 ⚠ 警告）。

### 3. 选模板

- **演化时间线** → 按 `created` / `log.md` 时间排，输出"X 月 / 决策 / 影响"表
- **多方案对比** → 列横轴方案、纵轴维度，输出对比矩阵
- **设计评审** → 现状 / 问题 / 备选方案 / 推荐 / 风险
- **Snapshot** → 顶层架构图 + 关键决策清单 + 已知 gotchas 清单

### 4. 输出 + 落 wiki

落到合适位置：

- 横切主题分析 → `70-topics/<slug>.md`
- 季度快照 → `90-snapshots/<YYYY-Q[1-4]>-<slug>.md`
- 设计评审 → `60-decisions/NNNN-<slug>.md`（这种类型本身也是决策）

frontmatter 必填 `sources` 字段列出综合的所有源页：

```yaml
sources:
  - "[[10-architecture/subsystems/ability-system]]"
  - "[[20-modules/cpp/ULyraAbilitySystemComponent]]"
  - "[[60-decisions/0001-project-knowledge-base]]"
```

### 5. 更新 index.md + log.md

```
## [2026-05-16] digest | Lyra 网络同步方案演化时间线 → [[70-topics/networking-and-synchronization]]
- 综合页数：12
- 时间跨度：2024-09 ~ 2026-05
- 摘要：从 Dedicated Server 到 Replication Graph 的关键架构决策梳理
```

## 注意事项

- digest 是**综合**，不是**复制**。如果只是把原页拼起来，没价值
- 综合中如发现矛盾 → 必须显式标出"⚠️ [[x]] 与 [[y]] 对 Z 的描述不一致"
- 综合中如发现 stale 页 → 顺手在 lint 阶段处理（或标记到 digest 末尾"建议 lint"）
- 不要在 digest 里塞太多代码细节（那是 module 页的事），digest 关注**抽象层结论**
