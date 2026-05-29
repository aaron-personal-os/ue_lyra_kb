# 知识库日志

> append-only 日志，记录知识库的重要变更。

## 2026-05-25

### feat | 新增 gotcha 页面：PowerShell CLIXML 与 Python 编码问题 → [[80-gotchas/powershell-clixml-output]]

- **触发**：本地 Windows 环境执行 `wiki_query.py` / `query.py` 时，PowerShell IDE 输出被 CLIXML 进度标签污染；`render_human()` 中的 emoji（`💡` `⚠` `✗`）触发 `UnicodeEncodeError: 'gbk' codec can't encode character`
- **根因**：
  1. PowerShell 默认输出进度报告为 CLIXML 格式；
  2. Windows 默认代码页 936 (GBK) 不支持 U+1F000 以上 Unicode 字符
- **修复动作**：
  1. `wiki_query.py`：替换 5 处 Unicode 特殊字符为 ASCII 等价文本（`⚠` → `[WARN]`、`✗` → `[DEPRECATED]`、`💡` → `[HINT]`）
  2. `query.py`：替换 2 处 Unicode 字符
  3. 新建 `80-gotchas/powershell-clixml-output.md` 沉淀完整根因、4 种解决方案、验证方法
- **推荐方案**：修改 PowerShell Profile（`$ProgressPreference = 'SilentlyContinue'`）+ 脚本侧避免 emoji

## 2026-05-24

### feat | 检索引擎 v1.1 + 入口合并：query.py 全部特性集成到 wiki_query.py → [[_raw/specs/2026-05-24-tier0-features-into-tier1-eval]] / [[_raw/specs/2026-05-24-merge-query-into-wiki-query-eval]]

- **触发**：知识库 278 页 / 2454 边规模下，`query.py` 的启发式评分质量与 `wiki_query.py` 的 BM25 排名出现差异；两入口并存导致 SKILL/9 个 workflows/4 个 ADR 文档话术不一致
- **v1.1 集成（Tier 0 → Tier 1 三个 P0 特性）**：
  1. **anchors 路径命中**：`pages.anchors_text` 列扁平化路径写入 FTS5 第 6 列（BM25 列权重 2.5）+ 后置 anchor-hit bonus（按命中 token 长度加权）+ id-fulltoken bonus（长 token 完整出现在 page_id 时 +5.0）→ 修复"查 LyraCharacter Top-1 应是 ALyraCharacter 模块文档"严重回归
  2. **alias 词表扩展**：从 `Docs/.wiki-schema.md` 「别名词表」节自动抽取同义词组，查询时扩展 token 集；alias-only 命中页面 × 0.6 软降权；CLI `--no-alias` 关闭
  3. **series-prev/next 隐式边**：`wiki_rebuild.py` 构建后自动按 `series + lesson_index` 写入 `links` 表（208 条 prev + 208 条 next）→ 教程系列种子模式可识别"上一课/下一课"
- **schema 升级**：`build_meta.schema_version` 从 `1.0` → `1.1`，旧 db 自动 fallback 到全量重建（无需手工迁移）
- **v1.1.1 入口合并（query.py shim 化）**：
  - `query.py` CLI 入口加 stderr deprecation 提示（`PROJECT_WIKI_QUERY_NO_DEPRECATION_WARN=1` 关闭）
  - 文件头加注释说明 v1.1.1 软 deprecation
  - **保留完整代码**（不转 30 行 shim）：原因是 `test_query.py` 大量 `import query` 模块函数，硬转 shim 会破坏既有测试
  - 推荐路径：`wiki_query.py --engine grep` 通过统一入口委托
- **文档批量更新**（13 个文件 query.py → wiki_query.py CLI 替换 + 段落重写）：
  - SKILL.md：路由表 + Tier 表更新（Tier 0 重新定位为"诊断 fallback"）
  - workflows: query.md / create-series / crystallize / digest / evolve-series / ingest / source-trace / teach 共 8 个工作流
  - Docs/30-tutorials/README.md / Docs/README.md
  - 4 个 ADR / log / index：仅加 deprecation 注脚，不改写历史陈述
- **测试覆盖**：12（rebuild）+ 21（query，含 6 个 v1.1 专项）= **33/33 通过**
  - test_v11_anchor_hit_lyra_character / test_v11_alias_expansion_gas / test_v11_alias_no_expansion_when_disabled / test_v11_series_implicit_edges / test_v11_schema_version / test_v11_anchors_text_in_db
- **实测效果**：
  - 查 `LyraCharacter` Top-1 = `[[20-modules/cpp/ALyraCharacter]]` (score=21.09)，修复回归
  - 查 `GAS` 自动扩展 alias `[gameplay ability system]`，Top-3 含 ability-system 架构页
  - 种子 `gas/14-GE网络复制` 邻居含 `via:inverse-series-prev` / `via:inverse-series-next`
- **影响面**：核心 3 个 .py（wiki_rebuild +127 / wiki_query +180 / test_wiki_query +110）+ 13 个文档 ≈ 700 行净增；零依赖（仍纯 stdlib）

## 2026-05-23

### refactor | nav_inject 简化为目录段分组单一模式（删除 --section-scope，跨组不连续） → [[60-decisions/0005-tutorial-cross-link-policy]]

- **触发**：上次 evolve-series 操作后发现 nav_inject 触发 270+ 文件大面积 diff，根因是 `--section-scope` 与全局两种互斥模式静默切换 + `## ` 分组粒度过粗（`## 技术教程` 单一 section 包含 23 个教程系列，导致 GAS 末页 next 跨到 movement-system）
- **决策范围**：
  1. 删除 `nav_inject.py` 中所有 section-scope 相关代码（IndexSection / parse_index_with_sections / run_section_scope / section_ctx / --section-scope argparse），共 -120/+30 行净简化
  2. 引入 `nav_group(page_id)` 函数：取目录路径前两级作为分组键（末段视为文件名不计入），prev/next **绝不跨组**
  3. 不再产生 `_本节: ... · 上一节...: ..._` 跨段提示行
  4. 保留 `web-app/src/plugins/remark-wiki-links.ts` 的 `isCrossSectionHintParagraph` 删除逻辑作为 dead-code 兜底（防御 git 历史回退）
- **分组效果验证**（采样）：
  - `30-tutorials/gas/00-GAS系统总览`：prev=`umg/09` ❌ → prev=∅ ✅（GAS 系列首页）
  - `30-tutorials/gas/26-Lyra综合案例死亡能力链`：next=`movement-system/00` ❌ → next=∅ ✅（GAS 系列末页）
  - `30-tutorials/network-sync/iris/00-Iris总览`：prev=`network-sync/07` ✅（子目录归属父系列，符合预期）
  - `40-runbooks/*` / `60-decisions/*` / `70-topics/*` / `80-gotchas/*`：单层目录正确连续翻页
- **关联更新**：
  - `Docs/60-decisions/0005-tutorial-cross-link-policy.md` 追加"R32 演进：导航分组策略简化"小节（含触发问题/决策/实施/后果/经验沉淀）
  - 全量执行 `nav_inject.py --apply`，34 个 nav 分组 / 59 个页面更新，第二次跑确认幂等
- **lint 验证**：0 errors / **0 warnings** ✓（旧的 `tutorial-ext-ref` WARN 因 nav 跨节链接消失而归零）
- **经验沉淀**：项目级、影响所有页的格式选择，不应该靠 CLI flag 让用户在每次调用时选择 —— 要么彻底切换，要么干脆放弃

### evolve-series + ingest | GC 销毁兜底机制专题（21篇追加 + 80-gotchas 新增） → [[30-tutorials/gas/21-GC运行时详解]] [[80-gotchas/gas-cue-cleanup-on-asc-destroy]]

- **触发**：teach 工作流深挖三轮对话，分析"GE 关联 GC + Character/PlayerState 销毁"的网络同步边界，发现知识库未覆盖该高频实战坑
- **调研模式**：🔬 深度解析模式（引擎源码 + Iris ObjectReplicationBridge 双重交叉验证）
- **关键技术要点**：
  1. **GC Owner 关系订正**：`UGameplayCueManager::GetInstancedCueActor` 始终把 `TargetActor` 设为 GC 的 Owner（L505、L525），通过 `OnOwnerDestroyed` 提供销毁兜底
  2. **`bAutoAttachToOwner` 与 `bAutoDestroyOnRemove` 默认值订正**：源码 `GameplayCueNotify_Actor.cpp` L42、L55 显示**默认均为 `false`**（之前回答中误传"默认 true"）
  3. **三层兜底链梳理**：主路径（GE FastArray Remove）/ 兜底1（Owner 销毁强制 OnRemove(nullptr)）/ 兜底2（GC EndPlay）/ 兜底3（HandleGameplayCue MyTarget 无效）
  4. **Iris 边界场景**：ASC 作为 SubObject 走 `DetachSubObjectInstancesFromRemote` 路径时，FastArray 的 `PreReplicatedRemove` 不会被广播，导致带完整 Parameters 的 OnRemove 主路径失效
  5. **Iris 下 `ForceNetUpdate` 行为差异**：仅影响 SendUpdate 调度优先级，不保证同帧发送，必须用 `SetTimerForNextTick(Destroy)` 延迟一帧
- **文件列表**：
  - 修改：`Docs/30-tutorials/gas/21-GC运行时详解.md`（追加"GC Actor 销毁兜底机制"小节，含 Owner vs Attach 关系表、三层兜底 mermaid 图、决策树、工程实践代码、Iris 注意事项；frontmatter `last_synced/last_verified` → 2026-05-23）
  - 新增：`Docs/80-gotchas/gas-cue-cleanup-on-asc-destroy.md`（症状/根因/触发条件/4 套解决方案/验证方法）
- **关联更新**：
  - `Docs/index.md` 已知坑 (Gotchas) 节追加新条目
- **图谱影响评估**：query.py --id 显示 21 篇 inbound=3，仅 series-prev/next + 22 篇前置依赖，连锁影响面小，无需联动改动
- **源码引用**：
  - `Engine/Plugins/Runtime/GameplayAbilities/Source/GameplayAbilities/Private/GameplayCueNotify_Actor.cpp`（L42、L55、L170、L222、L319、L361）
  - `Engine/Plugins/Runtime/GameplayAbilities/Source/GameplayAbilities/Private/GameplayCueManager.cpp`（L491、L505、L525）
  - `Engine/Plugins/Runtime/GameplayAbilities/Source/GameplayAbilities/Private/GameplayCueInterface.cpp`（L251、L330、L387）
  - `Engine/Plugins/Runtime/GameplayAbilities/Source/GameplayAbilities/Private/GameplayEffect.cpp`（L4836、L4853、L4870、L5200）
  - `Engine/Plugins/Runtime/GameplayAbilities/Source/GameplayAbilities/Private/AbilitySystemComponent_Abilities.cpp`（L96、L1356）
  - `Engine/Source/Runtime/Net/Iris/Private/Iris/ReplicationSystem/ObjectReplicationBridge.cpp`（L505-521、L938-951、L1158-1257）
  - `Engine/Source/Runtime/Net/Iris/Private/Iris/ReplicationSystem/ReplicationReader.cpp`（L677-705）
  - `Engine/Source/Runtime/Engine/Private/Net/Iris/ReplicationSystem/ReplicationSystemUtil.cpp`（L321-347）

### docs | 优化 Docs/README.md（强化运行机制可视化 + 上手方式 + 工具链分类）

- **触发**：用户反馈第一版 README 在「30 秒理解」和「快速入口」段落仍偏文字描述，且工具链未区分人/AI 受众
- **优化要点**（5 项）：
  1. **§1 30 秒理解** 新增 Mermaid 大图：`知识来源 → _raw → AI Agent 协作 → Docs 知识图谱 → 人类消费层(web-app/Obsidian/VSCode)` 全景，重点展示教程系列 + AI 协作构建/使用的双向闭环
  2. **§2 快速入口** 重写为「三种推荐上手方式」：① web-app（教学系列学习者首选，含 setup/start/build/deploy 命令对照）② AI 协作（4 类核心 Agent 操作 teach/create-series/evolve-series/review-series + web-app-dev skill）③ Obsidian（手动浏览全 wiki + 图谱视图），不再直接引导读 .md
  3. **§3.1 目录全景** 补充完整 web-app/ 子结构（含 src/components/interactive、layout、ui、lib、plugins、styles、terminal-server、各 .bat/.sh）
  4. **§3.2 一张图理解** 替换为 Mermaid 模块协同图：`CODEBUDDY.md → SKILLS（project-wiki/web-app-dev）→ scripts 工具链 → Docs 主目录 → web-app 消费端` 5 个子图 + 关键流向标注
  5. **§4 核心机制** 调整：① wikilink 段扩充图谱化查询优势对比表（参考 ADR-0004）+ 5 项核心质变能力 ② 移除 anchors 段（非本项目重点）③ 新增 §4.4 web-app 教学阅读站（双层架构 + 技术栈）
  6. **§5 工具链** 完整覆盖 + 显著标注「除 web-app/ .bat/.sh 外，其余脚本主要为 AI Agent 服务」+ 新增 install_pre_commit_hook.sh / web-app/{setup,start,build,deploy}.{bat,sh} 介绍 + 每个 Agent 工具脚本标注「Agent 用」
- **wiki_lint --check**：0 errors（未引入新问题）

### docs | 重写 Docs/README.md 与 30-tutorials/README.md（人类用户上手指南）

- **触发**：原 `Docs/README.md` 数据陈旧（标 5 系列 73 篇，实际 23 系列 220+ 篇 / 282 wiki 页 / 2594 wikilink），且未覆盖 v1.3 后引入的 query.py 工具链 / web-app / 6 份 ADR / 11 个工作流
- **目标**：让人类用户先快速建立总体认知（30 秒 / 5 分钟 / 详读），再按需深入
- **结构**（11 个章节，由浅入深）：
  1. 30 秒理解：这是什么（双读者定位 + 三大特色）
  2. 我想做 X 去哪里（10 类需求 → 第一/二站）
  3. 5 分钟掌握知识库结构（目录全景 + 三层映射图 + 当前规模）
  4. 5 个核心机制（wikilink / frontmatter / anchors / _series.yaml / 三层教学）
  5. 工具链（query.py / wiki_lint / nav_inject / rename_page / fix_asymm / log_rollup）
  6. 设计思路（Karpathy LLM Wiki + 三层架构 + 工程化扩展）
  7. 运行机制（11 类工作流 + 通用约束 + 质量保障 + 多 Agent + web-app）
  8. 重点模块解析（00-meta / 30-tutorials / 60-decisions / _raw / web-app）
  9. 给三类读者的具体上手建议（学习者 / 开发者 / 贡献者）
  10. 演进路线 + 当前版本（v1.3）
  11. 相关链接（内部 + 外部）
- **同步刷新**：`30-tutorials/README.md` 列出全 23 系列（按主题分组：基础框架 / 玩法系统 / 网络 / 资源内存 / 角色运动 / 视觉 / UI 工具 / 优化本地化 / Lyra 实战）
- **wiki_lint --check**：0 errors（未引入新问题）

### crystallize | 教程跨层引用策略（图谱完备性 vs 读者可达性） → [[60-decisions/0005-tutorial-cross-link-policy]]

- **触发**：[[60-decisions/0004-knowledge-graph-query]] 落地后实测踩坑——`fix_asymm.py --apply` 给教程 frontmatter 加回引时触发 18 个 `tutorial-ext-ref` ERROR，揭示 `query.py` / `wiki_lint` / `nav_inject` 三方工具间的设计冲突
- **决策**：图谱端保留外部引用 + web-app 渲染端分层降级 + lint 规则放宽（v1.3）
  - **wiki 端**：教程 frontmatter 的 `related/prereq/sources` 允许引外部页（保图谱完备性）
  - **web-app 端**：`remark-wiki-links.ts` 增强——外部 wikilink → 不可点击灰色 `<span class="wiki-link-external">` + 📒 前缀；跨节提示行（`_本节: ... ·  上/下一节...:_`）整段删除
  - **lint 端**：`tutorial-ext-ref` 从 ERROR 降为 WARN（v1.3），仅扫教程**正文**（剥离 frontmatter）
- **改动文件**（共 5 个）：
  - `web-app/src/plugins/remark-wiki-links.ts`（重构：单 plugin 双职责）
  - `web-app/src/styles/typography.css`（新增 `.wiki-link-external` 样式）
  - `.codebuddy/skills/project-wiki/scripts/wiki_lint.py`（v1.3：规则降级 + frontmatter 豁免）
  - `Docs/60-decisions/0005-tutorial-cross-link-policy.md`（新增 ADR）
  - `Docs/30-tutorials/{gas/00,input-system/05}.md`（修复 fix_asymm 留下的重复 `related:` 键）
- **验证**：`wiki_lint --check` 0 errors；`fix_asymm --apply` 0 新错；asymm-link 16 → 0
- **沉淀经验**：当两个工具的硬规则相互冲突，往往意味着设计层缺一条「分层抽象」。本项目独有的「知识图谱（给 Agent 看）vs reader-facing 静态站（给读者看）」双层架构，需要在两层间用规则降级 + 渲染期豁免做翻译

### crystallize | 知识图谱化查询（query.py + 差异化规范） → [[60-decisions/0004-knowledge-graph-query]]

- **触发**：知识库规模达 346 篇 / 2533 处 wikilink，实测 Agent 默认 grep 跳层导致 stale / 重复页 / 漏 prereq 链
- **决策**：差异化规范（4 类问题禁止跳图层）+ 工具化降本（query.py 一击查询）+ 全工作流接入（8 处）
- **新增脚本**：
  - `.codebuddy/skills/project-wiki/scripts/query.py` v1.0 — 关键词 / 种子 / 系列三种模式，5 类图边展开，alias 词表自动扩展
  - `.codebuddy/skills/project-wiki/scripts/test_query.py` — 87 项断言全 PASS
- **本项目特化**：相对通用模板做了 8 项定制（修正 index 行格式 / prerequisites 升级为图边 / inverse-prereq / series 隐式边 / anchors 文件名命中 / alias / 核心 type boost / body grep 降噪）
- **改动文件**（共 11 处）：
  - 工具：`scripts/query.py` + `scripts/test_query.py`（重构自移植版）
  - 工作流：`SKILL.md` + `workflows/{query,teach,source-trace,digest,ingest,crystallize,create-series,evolve-series}.md`
- **不接入**：`init.md` / `lint.md` / `review-series.md`（统计/审查性质，rg 更合适）
- **实测对比 4 场景**：
  - 单点查询 grep 时间快 18×，但 Agent 总成本反而更高
  - 多页综合 grep 噪音 30× / token 占用 15×
  - 创建新页查重重复风险从"高"降到"极低"
  - 抗 stale grep 完全感知不到 / query.py 强制 ⚠ 警告（质变能力）
- **相关 PR / 提交**：（待提交）
- **沉淀经验**：「看到 design ↔ behavior gap 时，不要先想着加 enforcement，先想着把对的路做得更省力」

## 2026-05-22

### review-series | performance-optimization 质量审查 → [[30-tutorials/performance-optimization/00-性能优化系列概览]]
- **审查模式**：Full Review
- **综合评分**：6.0/10 (⭐⭐⭐)
- **问题统计**：Critical 3 / Major 4 / Minor 4
- **已修复（P0）**：3 项
  - 全部 7 文件补充 `last_verified: 2026-05-17`
  - `00-overview` nav `←` 链接从 `modular-gameplay/05-advanced-custom` 改为 `[[index|教程索引]]`
  - `06-lyra-optimization-cases` nav `→` 链接从 `niagara/01-overview` 改为 `系列完`
- **已修复（P1）**：4 项
  - 01~06 补充 `engine_sources` / `lyra_sources`（各 2~3 条引用）
  - `03-gpu-rendering-optimization` 前置依赖从 `02-cpu-optimization` 改为 `01-profiling-tools`
  - `04-memory-optimization` 前置依赖从 `03-gpu-rendering-optimization` 改为 `01-profiling-tools` + `[[30-tutorials/garbage-collection/00-GC垃圾回收系列概览]]`
  - `00-overview` prerequisites 从 `[]` 改为 `[[30-tutorials/ue-framework/00-UE框架概述]]`
- **待修复（Minor）**：4 项（可选，见报告）
- **报告路径**：`Docs/_raw/review-reports/Review-Report-performance-optimization-2026-05-22.md`
- **备注**：报告 Issue 6（"01~05 缺少 Lyra 实例层"）经复核不成立——01~05 每篇已有"Lyra 中的 XXX"小节，仅内容偏简短，已在 P1 阶段通过补充 `lyra_sources` 部分改善。

### review-series | modular-gameplay 质量审查 → [[30-tutorials/modular-gameplay/00-ModularGameplay系统教程系列]]
- **审查模式**：Full Review
- **综合评分**：6.0/10 (⭐⭐⭐)
- **问题统计**：Critical 3 / Major 4 / Minor 2
- **已修复**：7 项（P0: 2 项，P1: 1 项，P2: 2 项）
- **待修复**：Minor 2 项（可选）
- **报告路径**：`Docs/_raw/review-reports/modular-gameplay-review-2026-05-22.md`

### 修复明细

| 文件 | 修复内容 |
|------|----------|
| `03-component-lifecycle.md` | `FGameplayTagCountContainer` → `FOnPawnReadyToInitialize`（类型更正） |
| `04-lyra-practice.md` | 同上 |
| `01-what-is-modular-gameplay.md` | `GetHero()` → `Cast<ALyraCharacter>(GetPawn())`；`RegisterWithOwner` → `RegisterPawnComponent` |
| 全部 6 篇 | 补充 `last_verified: 2026-05-22` |
| `_series.yaml` | `total_lessons: 5` → `6` |
| `01-what-is-modular-gameplay.md` | `related` 自引用 → 改为指向 `00-overview` |

## 2026-05-19

### 创建 `lyra-practical` 教程系列

**系列信息**：
- **系列 ID**：`lyra-practical`
- **系列名称**：Lyra 项目架构与实战
- **难度**：[beginner, advanced]
- **总课时**：11 课（00-10）
- **预计时间**：10 小时

**创建的文件**：
- `30-tutorials/lyra-practical/_series.yaml` - 系列元数据
- `30-tutorials/lyra-practical/00-overview.md` - 系列概览
- `30-tutorials/lyra-practical/01-architecture-overview.md` - Lyra 架构总览
- `30-tutorials/lyra-practical/02-experience-system.md` - Experience 系统详解
- `30-tutorials/lyra-practical/03-gamefeature-modular-gameplay.md` - GameFeature 与 Modular GamePlay
- `30-tutorials/lyra-practical/04-pawn-and-components.md` - Pawn 与组件系统
- `30-tutorials/lyra-practical/05-gas-integration.md` - GAS 集成详解
- `30-tutorials/lyra-practical/06-input-system.md` - 输入系统详解
- `30-tutorials/lyra-practical/07-ui-framework.md` - UI 框架详解
- `30-tutorials/lyra-practical/08-network-sync.md` - 网络同步详解
- `30-tutorials/lyra-practical/09-practical-new-game-mode.md` - 实战：创建新游戏模式
- `30-tutorials/lyra-practical/10-advanced-topics.md` - 高级主题与性能优化

**内容来源**：
- `Docs/10-architecture/` - 架构文档
- `Docs/20-modules/cpp/` - C++ 类文档
- `Docs/40-runbooks/` - 操作手册
- `Docs/70-topics/` - 横切主题
- Lyra 项目源码分析
- UE 官方文档

**学习路径**：
1. 基础架构（00-02）：理解 Lyra 核心设计理念
2. 核心系统（03-05）：深入 GameFeature、Pawn 组件、GAS 集成
3. 输入与 UI（06-07）：Lyra 输入系统和 UI 框架
4. 网络同步（08）：Lyra 网络复制架构与性能优化
5. 实战与高级主题（09-10）：创建自定义游戏模式、高级主题与性能优化

### 引擎路径解析脚本化 + 精简 `ai-playbook.md` 操作章节

**新增工具脚本**（项目根目录）：

- `get_engine_root.ps1` — Windows PowerShell 主脚本，解析 `.uproject.EngineAssociation` → 注册表 → 引擎根路径
- `get_engine_root.bat` — CMD 包装器，转发到 `.ps1`
- `get_engine_root.sh`  — macOS / Linux 版本，从 `Install.ini` 解析（GUID 形式）

**统一接口**：三个脚本均支持 `--json` / `-Json` 输出，字段为 `{ ok, engineAssociation, associationType, engineRoot, engineSource, enginePlugins }`，AI 可直接解析 JSON。

**`ai-playbook.md` 改动**：

- 删除原"Windows 详细操作流程"中冗长的 `reg query` Step 1~3、PowerShell 一键脚本片段、macOS Install.ini 手工解析说明
- 替换为"获取引擎根路径（脚本化）"小节：仅给出三平台调用命令 + JSON 字段示例 + 4 行原理简述
- 强调 AI 必须执行脚本动态获取引擎路径，禁止硬编码绝对路径
- 用 `associationType` 区分 Launcher 安装版（`installed`）与自编译版（`source-build`），二者均含可读 `.cpp`；仅当需要修改并重编译引擎本体时才必须是 `source-build`

### 更新 `00-meta/ai-playbook.md`：补充 Windows 获取引擎源码路径的详细流程

- 修正原文档关于 Windows 使用 `Install.ini` 的错误描述（`Install.ini` 仅 macOS / Linux 使用，Windows 走系统注册表）
- 补充 `EngineAssociation` 两种形式的处理逻辑：
  - **版本号**（如 `"5.7"`）→ 查 `HKLM\SOFTWARE\EpicGames\Unreal Engine\<Version>` 的 `InstalledDirectory`
  - **GUID**（如 `"{A20C82DC-...}"`）→ 查 `HKCU\SOFTWARE\Epic Games\Unreal Engine\Builds`
- 给出完整的 `reg query` 命令示例和实测输出
- 增加切换 Lyra 关联到源码版本的操作步骤
- 提供一段 PowerShell 一键脚本，AI 可直接调用解析 `.uproject` → 注册表 → 引擎根路径
- 强调 `EpicGames`（无空格，已安装版本）与 `Epic Games`（有空格，源码版本）的注册表项命名差异

> 上一条记录已被本次脚本化重构覆盖，但保留作为变更线索（脚本内部仍按上一条总结的注册表规则查表）。


## 2026-05-16



### 提交 85787e40: feat(docs): 初始化项目知识库

- 创建 `Docs/` 目录骨架和核心文件（项目知识库 v0.1）
- 配置 `.vscode/settings.json` 忽略 UE5 生成文件
- 更新 `CODEBUDDY.md` 注入知识库摘要
- 创建 `.gitignore` 忽略生成文件
- 知识库包含：
  - `.wiki-schema.md` - 知识库 schema
  - `README.md` - 人工入口
  - `index.md` - 知识目录
  - `log.md` - 更新日志
  - `overview.md` - 项目概览
  - `00-meta/` - 元规则（conventions、glossary、workflows、ai-playbook）
  - `30-decisions/0000-template.md` - ADR 模板

### 提交 9cae473a: docs: 添加自动提交规则到项目约定

- 在 `Docs/00-meta/conventions.md` 中添加自动提交规则
- 定义自动提交的触发时机
- 明确不提交的情况
- 添加提交前检查清单

### 扫描 Source/ 目录，生成架构文档

- 创建 `Docs/10-architecture/overview.md` - 架构概览
  - 模块化游戏玩法（Modular Gameplay）
  - 体验系统（Experience System）
  - 组件化架构（Component-Based）
  - 核心类说明（ALyraGameMode、ALyraCharacter、ULyraExperienceDefinition）
  - 数据流和扩展点
- 创建 `Docs/10-architecture/subsystems/experience-system.md` - 体验系统详解
  - 核心类（ULyraExperienceDefinition、ULyraExperienceManagerComponent、ULyraExperienceActionSet）
  - 工作流程（加载、启用 Game Features、执行 Actions、配置 Pawn）
  - 创建自定义 Experience 步骤
  - 最佳实践
- 创建 `Docs/10-architecture/subsystems/modular-gameplay.md` - 模块化游戏玩法详解
  - 核心类（ModularCharacter、ModularGameMode、ModularGameState、PawnComponent、GameStateComponent）
  - 组件生命周期
  - 优势（功能解耦、代码复用、动态组装）
  - 最佳实践
- 创建 `Docs/10-architecture/subsystems/ability-system.md` - 游戏能力系统详解
  - 核心类（ULyraAbilitySystemComponent、ULyraGameplayAbility、ULyraAbilitySet）
  - 集成流程（初始化 ASC、授予 Ability Set、绑定 Input）
  - 网络复制
  - 最佳实践
- 创建 `Docs/20-modules/cpp/ALyraCharacter.md` - ALyraCharacter 详解
  - 继承关系和实现的接口
  - 关键属性和函数
  - 数据结构（FLyraReplicatedAcceleration、FSharedRepMovement）
  - 使用方式和最佳实践
- 创建 `Docs/20-modules/cpp/ALyraGameMode.md` - ALyraGameMode 详解
  - 继承关系
  - 关键函数和委托
  - 工作流程（初始化游戏、玩家登录、玩家重启）
  - 匹配分配优先级
  - 使用方式和最佳实践
- 创建 `Docs/20-modules/cpp/ULyraExperienceDefinition.md` - ULyraExperienceDefinition 详解
  - 继承关系
  - 关键属性（GameFeaturesToEnable、DefaultPawnData、Actions、ActionSets）
  - 工作流程（加载、启用 Game Features、执行 Actions、配置 Pawn）
  - 创建自定义 Experience 步骤
  - 最佳实践
- 更新 `Docs/index.md` - 添加新创建的文档链接

### 更新 Docs/00-meta/ai-playbook.md - 添加提交节奏与规范章节

- 添加"默认节奏"小节：定义 R 段完成后自动 commit 的规则
- 添加"段尾 checklist 3 件套"小节：定义 R 段完成的 3 个必要条件
- 添加"实务启发式：堆积未 commit 时合并比拆分省成本"小节：提供合并 vs 拆分的判断阈值
- 添加"反模式（禁止）"小节：列出禁止的 commit 行为
- 添加"commit message 风格"小节：定义 commit message 的格式规范（默认中文）
- 添加"图示优先 mermaid，禁止 ASCII art"小节：定义 wiki 页图示规范

### 创建操作手册 (Runbooks)

- 创建 `Docs/40-runbooks/how-to-add-gameplay-ability.md` - 如何添加新的 Gameplay Ability
  - 步骤 1：创建 Ability 类（C++ 或 Blueprint）
  - 步骤 2：创建 Ability Set 包装 Ability
  - 步骤 3：将 Ability Set 挂载到 PawnData
  - 步骤 4：绑定输入动作（Optional）
  - 验证步骤、常见问题、最佳实践
- 创建 `Docs/40-runbooks/how-to-create-new-experience.md` - 如何创建新的 Experience
  - 步骤 1：创建 Experience Definition 资产
  - 步骤 2：配置 Game Features
  - 步骤 3：配置 Default Pawn Data
  - 步骤 4：添加 Action Sets（可选）
  - 步骤 5：添加 Actions（可选）
  - 步骤 6：在 Game Mode 中引用新的 Experience
  - 验证步骤、常见问题、最佳实践
- 创建 `Docs/40-runbooks/how-to-add-new-weapon.md` - 如何添加新的武器
  - 步骤 1：创建 Weapon Definition 资产
  - 步骤 2：配置 Weapon Instance 类（可选）
  - 步骤 3：创建 Weapon Actor Blueprint
  - 步骤 4：配置射击逻辑（Gameplay Ability）
  - 步骤 5：将武器添加到游戏
  - 验证步骤、常见问题、最佳实践
- 更新 `Docs/index.md` - 添加新创建的操作手册链接

### 修复早期文档中的图示：将 ASCII art 改为 mermaid 图

- 修复 `Docs/10-architecture/overview.md` 中的 ASCII art，改为 mermaid 图
  - 模块依赖关系图（修复 1）
  - ALyraGameMode 继承关系图（修复 2）
  - ALyraCharacter 继承关系图（修复 4）
  - 玩家登录流程图（修复 5）
  - 能力系统集成图（修复 6）
- 修复 `Docs/10-architecture/subsystems/experience-system.md` 中的 ASCII art，改为 mermaid 图
  - Experience 加载流程图（修复 7）
  - Experience 结构示例图（修复 9）
- 修复 `Docs/10-architecture/subsystems/modular-gameplay.md` 中的 ASCII art，改为 mermaid 图
  - Pawn Component 生命周期流程图（修复 11）
  - 传统继承方式 vs 模块化方式对比图（修复 13）

### 继续修复早期文档中的图示：将 ASCII art 改为 mermaid 图

- 修复 `Docs/20-modules/cpp/ALyraCharacter.md` 中的 ASCII art，改为 mermaid 图
  - 继承关系图（修复 1）
- 修复 `Docs/20-modules/cpp/ALyraGameMode.md` 中的 ASCII art，改为 mermaid 图
  - 继承关系图（修复 2）
  - 初始化游戏流程图（修复 3）
  - 玩家登录流程图（修复 4）
  - 玩家重启流程图（修复 5）
- 修复 `Docs/20-modules/cpp/ULyraExperienceDefinition.md` 中的 ASCII art，改为 mermaid 图
  - 继承关系图（修复 6）
  - 加载 Experience 流程图（修复 7）
  - Experience 结构示例图（修复 8）

### 调整 .gitignore 并设置远程仓库

- 修改 `.gitignore` 文件，只保留 `.codebuddy/`、`Docs/` 和 `CODEBUDDY.md`
  - 使用 `*` 忽略所有文件和目录
  - 使用 `!` 前缀取消忽略（whitelist）`.codebuddy/`、`Docs/` 和 `CODEBUDDY.md`
  - 添加 `!.gitkeep` 保留目录结构
- 添加远程仓库 `origin`：`https://gitee.com/luoy0918/ue_lyra_analysis.git`
- 注意：需要从 git 索引中删除其他已跟踪的文件（如 `Binaries/`、`Intermediate/` 等）

---
> 最后更新：2026-05-16

### 分析 Lyra 预设体验系统

- 分析 Lyra 项目中预设的 5 个 Experience Definition 资产：
  - B_LyraFrontEnd_Experience（前端菜单体验）
  - B_LyraDefaultExperience（默认游戏体验）
  - B_TopDownArenaExperience（俯视角竞技场体验）
  - B_TopDownArena_Multiplayer_Experience（俯视角竞技场多人体验）
  - B_TestInventoryExperience（测试库存体验）
- 分析 5 个 Game Feature 插件的功能和依赖关系：
  - ShooterCore（射击核心玩法）
  - TopDownArena（俯视角竞技场）
  - ShooterExplorer（射击+冒险探索）
  - ShooterMaps（射击游戏地图）
  - ShooterTests（测试套件）
- 更新 `Docs/10-architecture/subsystems/experience-system.md`：
  - 添加"Lyra 预设体验系统"章节，详细描述每个预设体验
  - 添加"Game Feature 插件架构"章节，说明插件间的依赖关系
  - 添加 Mermaid 图展示体验系统与 Game Feature 的关系
- 结合 UE 官方文档和源码进行综合分析

## 2026-05-16（续）

### 完成 GAS 教程系列重写（UE5.3 → UE5.7）

- 基于 UE5.3 的原始 GAS 教程（25 个文件），重写为 UE5.7 合规版本
- 创建完整的 GAS 教程系列（00-25），覆盖所有核心主题：
  - **GAS 总览**（00-gas-overview）
  - **GA 系列**（01-ga-overview 至 05-ga-target-info）
  - **GE 系列**（06-ge-overview 至 14-ge-network-replication）
  - **Tag 系列**（15-tag-overview 至 19-tag-network-replication）
  - **GC 系列**（20-gc-overview、21-gc-runtime）
  - **AbilityTask**（22-ability-task）
  - **高级主题**（23-prediction-key、24-gameplay-effect-context、25-attribute-set）
- 教程内容更新：
  - 添加 UE5.7 更新内容说明
  - 添加 Mermaid 图表替代 ASCII art
  - 添加 Lyra 项目示例代码
  - 更新代码段以符合 UE5.7 API
  - 添加 proper frontmatter（id、type、status、tags、anchors）
- 更新 `Docs/index.md` 添加所有 26 个教程条目
- 遵循 `project-wiki` skill 规则和 `ai-playbook.md` 约束
- 分模块提交（GA 系列、GE 系列、Tag 系列、GC+AbilityTask+高级主题）

### UE 网络通信与同步专项文档第一版结构化重写（UE5.7）

- 基于 `Docs/_raw/external/NetworkSync/` 下 11 篇原始教程，结合 UE5.7 官方资料、UE5.7 引擎源码和 Lyra 项目源码，完成网络通信与同步专项文档第一版结构化重写；后续继续补强源码级复核结论与逐项纠偏。
- 新增项目级入口与 Lyra 架构页：
  - `Docs/60-topics/networking-and-synchronization.md` - 网络通信与同步专题
  - `Docs/10-architecture/subsystems/networking-system.md` - Lyra 网络同步系统
  - `Docs/10-architecture/data-flow/network-replication-flow.md` - 网络复制数据流
- 新增 UE5.7 网络参考系列：
  - `00-network-overview`、`01-connection-lifecycle`、`02-packet-bunch-ack`
  - `03-legacy-actor-replication-flow`、`04-legacy-property-rpc-flow`
  - `05-rep-layout-fast-array-netguid`、`06-replication-graph`
  - `07-legacy-vs-iris` 横向对比
- 新增 Iris 子系列：
  - `iris/00-iris-overview`
  - `iris/01-replication-state-descriptor`
  - `iris/02-net-serializer`
  - `iris/03-net-token`
  - `iris/04-iris-property-rpc-flow`
  - `iris/05-iris-migration-checklist`
- 新增 `Docs/70-gotchas/networking-ue57-review-checklist.md`，沉淀旧教程迁移到 UE5.7 时的风险复核清单。
- 更新 `Docs/index.md`，将网络架构、数据流、参考系列、专题页和 Gotcha 页接入知识库导航。
- 关键结论：Lyra 启用了 Iris 插件和构建支持，具备 Iris 配置；ReplicationGraph 代码存在但默认禁用；业务层仍大量使用 `DOREPLIFETIME`、RPC、FastArray、SubObject 与 GAS prediction 等高层网络 API。

### UE 网络同步专项文档源码复核补强（P0/P1 第一批）

- 修正 `Docs/log.md` 对上一阶段的过度“完成”表述，改为“第一版结构化重写”。
- 修正 `Docs/10-architecture/subsystems/networking-system.md` 中 Iris `ObjectReplicationBridgeConfig` 的错误描述：`Actor=None`，`Pawn=Spatial`，不是二者都使用空间过滤。
- 补充 Lyra 当前 `Config/` 中未发现显式 `net.Iris.UseIrisReplication`、Iris NetDriver 或 `NetDriverDefinitions` 的事实，避免误判运行时一定走 Iris。
- 为 Legacy 系列补入 UE5.7 源码复核结论：
  - ControlChannel 登录链路（`NMT_Hello` → `Challenge` → `Login` → `Welcome` → `Join`）
  - Packet/Bunch/Ack 可靠性边界
  - `UNetDriver::ServerReplicateActors` 阶段拆解
  - `UActorChannel` / `FObjectReplicator` / `FRepLayout` 属性复制链
  - RPC 发送/接收链
  - `UPackageMapClient` / `FNetGUIDCache` 对象引用与 NetGUID 导出链
- 为 Iris 系列补入 UE5.7 源码复核结论：
  - Iris 启用决策链（CVar、命令行、`IrisNetDriverConfigs`、`UEngine::WillNetDriverUseIris`、NetDriver 初始化）
  - `UReplicationSystem::NetUpdate` 主循环
  - `FReplicationStateDescriptor` 构建边界
  - `FNetSerializer` registry / serializer API 边界
  - `FNetTokenStore` / `NetTokenDataStream` 机制边界

### UE 网络同步专项文档源码复核补强（P1 第二批）

- 补强 `Docs/50-references/network-sync/06-replication-graph.md`：加入 Lyra RepGraph 创建委托、路由策略、PlayerState 限频和 Iris 互斥边界的源码复核结论。
- 补强 `Docs/50-references/network-sync/07-legacy-vs-iris.md`：加入 Legacy / Iris / Lyra / 迁移影响的源码复核矩阵。
- 补强 `Docs/50-references/network-sync/iris/04-iris-property-rpc-flow.md`：加入 `UNetDriver::TickFlush`、`UReplicationSystem::NetUpdate`、Bridge poll、DataStream 发送和 SubObject 依赖关系链路。
- 补强 `Docs/50-references/network-sync/iris/05-iris-migration-checklist.md` 与 `Docs/70-gotchas/networking-ue57-review-checklist.md`：明确 `net.Iris.UseIrisReplication` 默认值、`IrisNetDriverConfigs` 门槛、命令行覆盖和 Lyra 当前缺少显式运行时 Iris 开关的事实。

### UE 网络同步专项文档 Iris 细节复核补强（P1 第三批）

- 补强 `Docs/50-references/network-sync/iris/03-net-token.md`：按 UE5.7 `FNetToken` 源码补入 `Index:20`、`TypeId:3`、authority bit、`MaxTypeIdCount=8`、`MaxNetTokenCount=1048576` 等精确位布局结论。
- 补强 `Docs/50-references/network-sync/iris/02-net-serializer.md`：按 UE5.7 `NetSerializer.h` 补入 serializer 函数集合、`UE_NET_DECLARE_SERIALIZER` / `UE_NET_IMPLEMENT_SERIALIZER` 宏，以及 trait 为 `static constexpr bool` 的结论。
- 补强 `Docs/50-references/network-sync/iris/01-replication-state-descriptor.md`：明确 `SupportsStructNetSerializerList` 的源码语义，即允许带自定义 `NetSerialize` / `NetDeltaSerialize` 的结构体使用默认 Iris `StructNetSerializer`。

### UE 网络同步专项文档模块页与 Bridge 深挖（P2 第一批）

- 新增 `Docs/50-references/network-sync/iris/06-object-replication-bridge.md`，补充 `UObjectReplicationBridge`、`UEngineReplicationBridge`、root/subobject、dependent/creation dependency、DataStream/RPC blob 的 UE5.7 源码边界。
- 新增网络同步相关模块页：
  - `Docs/20-modules/cpp/ULyraInventoryManagerComponent.md` - 背包 FastArray + SubObject 复制
  - `Docs/20-modules/cpp/ULyraEquipmentManagerComponent.md` - 装备 FastArray + SubObject + AbilitySet 授予
  - `Docs/20-modules/cpp/ULyraWeaponStateComponent.md` - 武器 TargetData 命中确认 Client RPC
  - `Docs/20-modules/cpp/ULyraReplicationGraph.md` - Lyra ReplicationGraph 实现
  - `Docs/20-modules/cpp/FLyraGameplayAbilityTargetData_SingleTargetHit.md` - 武器 TargetData 自定义 NetSerialize 与 Iris 支持
- 更新 `Docs/index.md`，将新增模块页和 Iris Bridge 页纳入知识库导航。

### UE 网络同步运行时验证 Runbook

- 新增 `Docs/40-runbooks/how-to-verify-network-replication-runtime.md`，把 Iris 插件/Build/配置事实与 UE5.7 `net.Iris.UseIrisReplication`、`IrisNetDriverConfigs`、`UEngine::WillNetDriverUseIris` 的源码结论串成可操作验证流程。
- Runbook 覆盖 Legacy / ReplicationGraph / Iris 的运行时判定、日志关键字、RepGraph 调试命令、关键业务链路测试矩阵和 Join-in-progress 验证点。
- 更新 `Docs/index.md`，将该 runbook 接入操作手册导航。

### UE 网络同步专项完成态收口

- 修复网络专项 Review 发现的 broken-link：补齐 `ALyraCharacter` 相关的 `ULyraPawnExtensionComponent`、`ULyraHealthComponent`、`ULyraCameraComponent` 模块页，并补齐 GAS / Experience / GameState 等历史断链模块页。
- 新增 `ALyraPlayerState` 模块页，补齐 Lyra GAS / PlayerState 复制承载点的源码覆盖。
- 强化 `ALyraCharacter.md` 网络同步章节：补充 `COND_SimulatedOnly`、`PreReplication`、`FSharedRepMovement::NetSerialize`、`FastSharedReplication`、RepGraph FastShared Path 与 Legacy/Iris 边界。
- 将 `ULyraWeaponStateComponent.md` 中源码 TODO 改写为明确“已知限制”，补充 `ShouldShowHitAsSuccess` 与 `ShouldUpdateDamageInstigatedTime` 的风险边界。
- 补强 `how-to-verify-network-replication-runtime.md`，加入 macOS 启动命令、DS/Client 示例、日志路径、`rg` 搜索命令与证据记录模板。
- 补强 `07-legacy-vs-iris.md`，新增“旧教程/旧认知 → UE5.7 源码复核 → Lyra 当前事实 → 迁移影响”纠偏矩阵。
- 修复 `how-to-add-new-weapon.md` 中不存在的 `ULyraWeaponDefinition` 链接，改为实际存在的 `ULyraWeaponInstance`。
- 更新 `Docs/index.md`，将新增模块页全部接入知识库导航。

## 2026-05-16（续）

### 创建 UE 框架技术专项文档系列（第1批）

> 基于原 UE 框架教程文档（Markdown 格式），结合 UE5.7 引擎源码和 Lyra 项目源码，创建 UE 框架深度分析文档系列。所有图片资源改用 mermaid 图描述，内容按由简到繁、先总体后细节的原则组织。

- 创建 `Docs/50-references/ue-framework/` 目录结构
  - `00-overview.md` - UE 框架总览（引擎层 vs 游戏世界层、分屏机制）
  - `01-game-loop.md` - 游戏主循环详解（Init → Tick → Exit 完整流程）
  - `10-engine-layer/00-engines.md` - Engine 类详解（UEngine/UGameEngine/UEditorEngine）
  - `10-engine-layer/01-gameinstance.md` - GameInstance 详解（WorldContext、玩家管理、子系统管理）

- 文档特点：
  - ✅ 使用 mermaid 图替代原图片（架构图、流程图、时序图、状态图）
  - ✅ 按"概述 → 核心概念 → 架构解析 → 执行流程 → 与其他模块的关系 → 参考资料"结构组织
  - ✅ 包含完整 frontmatter（符合项目规范）
  - ✅ 引用源码片段（用代码块）
  - ✅ 提供常见陷阱与最佳实践

- 更新 `Docs/index.md` - 添加 UE 框架系列文档链接
- 更新 `Docs/log.md` - 记录本次更新

---

## 2026-05-16（续2）

### 创建 UE 框架技术专项文档系列（第2批）

> 基于原 UE 框架教程文档，结合 UE5.7 引擎源码，创建 UE 框架深度分析文档系列第2批（游戏世界与游戏逻辑层）。

- 创建第2批4篇文档：
  - `Docs/50-references/ue-framework/20-world-layer/00-world.md` - UWorld 详解
    * 核心概念：World 类型（EWorldType）、World 职责
    * 架构解析：UWorld 类继承关系、关键方法（mermaid）
    * 执行流程：InitializeNewWorld、SetGameMode、SpawnPlayActor、BeginPlay、Tick（mermaid 时序图）
    * 与其他模块的关系
  - `Docs/50-references/ue-framework/20-world-layer/01-level.md` - ULevel 与 Level Streaming 详解
    * 核心概念：Level 职责、Level Streaming（流关卡）、World 切换（Travel）
    * 架构解析：ULevel 类继承关系、ULevelStreaming 类继承关系、关键方法（mermaid）
    * 执行流程：Level 加载流程、Level Streaming 加载流程、World 切换流程（ServerTravel）（mermaid 时序图）
    * 与其他模块的关系
  - `Docs/50-references/ue-framework/30-gamemode-layer/00-gamemode.md` - AGameModeBase 详解（全新编写）
    * 核心概念：GameMode 职责、GameMode 与 GameState 的关系
    * 架构解析：AGameModeBase 类继承关系、AGame 类继承关系、关键方法（mermaid）
    * 执行流程：GameMode 完整生命周期、Login → PostLogin 流程、玩家加入完整流程（mermaid 时序图）
    * 与其他模块的关系
  - `Docs/50-references/ue-framework/30-gamemode-layer/01-gamestate.md` - AGameStateBase 详解（全新编写）
    * 核心概念：GameState 职责、GameState 与 GameMode 的区别
    * 架构解析：AGameStateBase 类继承关系、关键属性（PlayerArray、MatchState、ElapsedTime）、关键方法（mermaid）
    * 执行流程：GameState 完整生命周期、GameState 初始化流程、属性复制流程（mermaid 时序图）
    * 与其他模块的关系

- 文档特点：
  - ✅ 使用 mermaid 图替代原图片（架构图、流程图、时序图、状态图）
  - ✅ 按"概述 → 核心概念 → 架构解析 → 执行流程 → 与其他模块的关系 → 参考资料"结构组织
  - ✅ 包含完整 frontmatter（符合项目规范）
  - ✅ 引用源码片段（用代码块）
  - ✅ 提供常见陷阱与最佳实践

- 更新索引文件：
  - 更新 `Docs/index.md` - 添加第2批 UE 框架系列文档链接
  - 更新 `Docs/log.md` - 记录本次更新

---

## 2026-05-16（续3）

### 创建 UE 框架技术专项文档系列（第3批）

> 基于 UE5.7 引擎源码和 Lyra 项目源码，创建 UE 框架深度分析文档系列第3批（Actor 系统与玩家系统）。

- 创建第3批4篇文档：
  - `Docs/50-references/ue-framework/40-actor-system/00-actor-overview.md` - AActor 架构概述
    * 核心概念：Actor 的职责、Actor 的特点（需要 RootComponent、可以嵌套）
    * 架构解析：AActor 类继承关系、关键属性（RootComponent、OwnedComponents、PrimaryActorTick）（mermaid）
    * 执行流程：Actor 完整初始化流程、Actor Tick 流程、Actor 销毁流程（mermaid 时序图）
    * 与其他模块的关系
  - `Docs/50-references/ue-framework/40-actor-system/01-actor-lifecycle.md` - AActor 完整生命周期
    * 核心概念：Actor 生命周期阶段（Spawned → Initialized → Constructed → Playing → Ending → Destroyed）
    * 架构解析：Actor 生命周期关键方法（PostSpawnInitialize、FinishSpawning、DispatchBeginPlay、Destroy、Destroyed、RouteEndPlay）（mermaid）
    * 执行流程：Actor 完整生命周期时序图（mermaid 时序图）
    * 与其他模块的关系
  - `Docs/50-references/ue-framework/50-player-system/00-pawn.md` - APawn 与 ACharacter 详解
    * 核心概念：Pawn 的职责、Character 的职责
    * 架构解析：APawn 类继承关系、ACharacter 类继承关系、关键属性（Controller、PlayerState）、关键方法（PossessedBy、UnPossessed、AddMovementInput、Jump、Crouch）（mermaid）
    * 执行流程：Pawn 被 Controller 控制流程、Character 移动流程（mermaid 时序图）
    * 与其他模块的关系
  - `Docs/50-references/ue-framework/50-player-system/01-controller.md` - AController 详解
    * 核心概念：Controller 的职责、Controller 与 Pawn 的关系
    * 架构解析：AController 类继承关系、APlayerController 类继承关系、AAIController 类继承关系、关键属性（Pawn、PlayerState）、关键方法（Possess、UnPossess、OnPossess、SetupInputComponent）（mermaid）
    * 执行流程：Controller 控制 Pawn 的完整流程、PlayerController 输入处理流程（mermaid 时序图）
    * 与其他模块的关系

- 文档特点：
  - ✅ 使用 mermaid 图描述架构、流程、关系
  - ✅ 按"概述 → 核心概念 → 架构解析 → 执行流程 → 与其他模块的关系 → 参考资料"结构组织
  - ✅ 包含完整 frontmatter（符合项目规范）
  - ✅ 引用源码片段（用代码块）
  - ✅ 提供常见陷阱与最佳实践
  - ✅ **不引用原始导出文档**（原始文档不纳入项目知识库）

- 更新索引文件：
  - 更新 `Docs/index.md` - 添加第3批 UE 框架系列文档链接
  - 更新 `Docs/log.md` - 记录本次更新

---

## 2026-05-16（续4）

### 创建 UE 框架技术专项文档系列（第4批）

> 基于 UE5.7 引擎源码和 Lyra 项目源码，创建 UE 框架深度分析文档系列第4批（Tick 系统与 Lyra 实例分析）。

- 创建第4批4篇文档：
  - `Docs/50-references/ue-framework/60-tick-system/00-tick-overview.md` - Tick 系统架构概述
    * 核心概念：FTickFunction 的职责、Tick 分组（ETickingGroup）、FTickTaskManager 的职责
    * 架构解析：FTickFunction 结构体（属性、方法）、FTickTaskManager 类（方法）（mermaid）
    * 执行流程：Tick 系统完整执行流程、Tick 函数注册流程、Tick 函数执行流程（mermaid 时序图）
    * 与其他模块的关系
  - `Docs/50-references/ue-framework/60-tick-system/01-tick-function.md` - FTickFunction 与组件 Tick 详解
    * 核心概念：FTickFunction 的职责、组件 Tick 机制、Tick 组（ETickingGroup）
    * 架构解析：FTickFunction 结构体（属性、方法）、FTickFunction 继承关系、UActorComponent 的 Tick 相关属性（mermaid）
    * 执行流程：FTickFunction 注册流程、FTickFunction 执行流程、UActorComponent 的 Tick 流程（mermaid 流程图）
    * 与其他模块的关系
  - `Docs/50-references/ue-framework/70-lyra-case-study/00-lyra-architecture-overview.md` - Lyra 架构总览
    * 核心概念：Experience 系统、Modular Gameplay、Game Features
    * 架构解析：Lyra 核心类继承关系（mermaid）、Experience 加载流程（mermaid）
    * 执行流程：Lyra 启动流程、Experience 加载流程、Modular Gameplay 流程（mermaid 时序图）
    * 与其他模块的关系
  - `Docs/50-references/ue-framework/70-lyra-case-study/01-lyra-gamemode.md` - Lyra 中的 GameMode 与 Player 系统实现
    * 核心概念：LyraGameMode 的职责、Lyra 中的 Player 系统
    * 架构解析：Lyra 核心类继承关系（mermaid）、ALyraGameMode 类、ALyraPlayerController 类、ALyraPlayerState 类、ALyraCharacter 类
    * 执行流程：LyraGameMode 初始化流程、Lyra 中玩家加入流程、Lyra 中输入处理流程（mermaid 时序图）
    * 与其他模块的关系

- 文档特点：
  - ✅ 使用 mermaid 图描述架构、流程、关系
  - ✅ 按"概述 → 核心概念 → 架构解析 → 执行流程 → 与其他模块的关系 → 参考资料"结构组织
  - ✅ 包含完整 frontmatter（符合项目规范）
  - ✅ 引用源码片段（用代码块）
  - ✅ 提供常见陷阱与最佳实践
  - ✅ **不引用原始导出文档**（原始文档不纳入项目知识库）

- 更新索引文件：
  - 更新 `Docs/index.md` - 添加第4批 UE 框架系列文档链接
  - 更新 `Docs/log.md` - 记录本次更新

---

## 2026-05-16（续5）

### 优化 UE 框架技术专项文档系列（修复 frontmatter）

> 修复16个 UE 框架文档的 frontmatter 格式错误，通过 `wiki_lint --check` 检查。

- 修复内容：
  - 修复16个文档的 `anchors:` 字段格式（指向 `LyraStarterGame.uproject`）
  - 修复4个文档的 frontmatter 损坏问题（`---` 结束标记位置错误）
  - 移除所有 `sources:` 字段（原始文档不纳入知识库）
  - 修复 `id:` 字段格式（横杠 `-` 改为斜杠 `/`）
  - 修复 `type:` 字段（去掉多余引号）

- 检查结果：
  - ✅ `wiki_lint --check` 通过（0 errors, 0 warnings）

- 更新索引文件：
  - 更新 `Docs/log.md` - 记录本次更新

---

### 深入分析 Lyra 项目中的 Niagara 系统应用

- 创建 `Docs/50-references/niagara-system/08-lyra-implementation.md` - Lyra 项目中的 Niagara 系统应用实例
  - 伤害数字弹出系统（Damage Pop）详解：
    * `ULyraNumberPopComponent_NiagaraText` 组件原理与实现
    * `AddNumberPop()` 方法详解（数据流：`FVector4` 打包 XYZ 位置 + W 伤害值）
    * `ULyraDamagePopStyleNiagara` 样式定义（`NiagaraArrayName`、`TextNiagara`）
    * Data Interface Array 数据传递机制（C++ ↔ Niagara）
  - Context Effects 系统中的 Niagara 集成：
    * `ULyraContextEffectComponent` 组件原理与 `AnimMotionEffect_Implementation` 实现
    * `UAnimNotify_LyraContextEffects` 动画通知触发流程
    * `ULyraContextEffectsSubsystem` 特效管理系统（`SpawnContextEffects`、`LoadAndAddContextEffectsLibraries`）
    * `ULyraContextEffectsLibrary` 特效库数据结构与匹配逻辑
  - Lyra 中的 Niagara 资产：
    * `Damage_BasicNiagaraStyle.uasset`（样式数据资产）
    * `B_NiagaraNumberPopComponent.uasset`（蓝图组件）
  - 包含 Mermaid 序列图、流程图（伤害数字系统架构、Context Effects 系统架构、数据传递机制）
  - 包含完整源码片段（带文件路径和行号）
  - 文档长度 500+ 行
- 更新 `Docs/index.md` - 添加 Niagara Lyra 实现文档链接
- 更新 `Docs/log.md` - 记录本次更新

---

- 创建 `Docs/50-references/animation-system/02-engine-foundation.md` - UE5 动画系统引擎基础框架深度分析
- 分析 `FAnimNode_Base` 源码（AnimNodeBase.h/cpp）
- 包含内容：
  - 类声明与继承关系（纯 struct，非 UObject）
  - 核心属性（LODThreshold、NodeData 等）
  - 关键虚函数及其调用时机（Initialize、CacheBones、Update、Evaluate、EvaluateComponentSpace、GatherDebugData）
  - 节点执行流程（初始化 → 更新 → 评估）
  - 上下文结构（FAnimationBaseContext、FAnimationUpdateContext、FPoseContext、FComponentSpacePoseContext）
  - 主要派生类（FAnimNode_AssetPlayerBase、FAnimNode_SkeletalControlBase、FAnimNode_StateMachine 等）
  - 为什么 FAnimNode_Base 是纯 struct（性能、设计考虑）
  - Lyra 项目可能使用的节点类型
  - 节点执行流程图（mermaid）

---

## 2026-05-17

### 注入 Wiki 页面尾部导航 + 更新 Lint 检查

- 运行 `nav_inject.py --apply` 给所有 wiki 页面注入尾部导航块
  - 成功注入 106 个页面
  - 导航格式：`<!-- nav:auto -->` 包裹的 prev/up/next 链接
  - 跳过：index.md、overview.md、00-meta/ 下文件、不在 index.md 的页面
- 更新 `.codebuddy/skills/project-wiki/scripts/wiki_lint.py`
  - 新增 `check_nav_block()` 函数（v0.8）
  - 在 `run()` 函数中注册检查（full 模式下运行）
  - 检查代码：`missing-nav` 警告，检测缺少导航块的页面
  - 验证通过：创建测试页面验证检查正常工作
- 更新 `Docs/.wiki-schema.md` 和 `Docs/00-meta/ai-playbook.md`
  - 添加尾部导航相关说明
  - 更新 lint 规则章节



---

## 2026-05-17（续）

### 创建 GameFeature 系统技术专题

- 创建 `Docs/70-topics/game-feature-system.md` - GameFeature 系统技术专题
  - 结合知乎文章（InsideUE5 系列）和 Lyra 项目实际实现
  - 涵盖内容：
    - GameFeature 架构演进（从历史痛点到现在解决方案）
    - 核心机制（GameFeaturePlugin、GameFeatureData、GameFeatureAction）
    - 生命周期与加载流程（状态图、时序图）
    - Lyra 中的实践（ShooterCore、TopDownArena 等插件分析）
    - Experience System 与 GameFeature 的关系
    - Modular GamePlay 与 GameFeature 的协同工作
    - 最佳实践与常见陷阱
    - 扩展：自定义 GameFeatureAction
  - 包含 Mermaid 图表（架构图、流程图、时序图、状态图）
  - 引用外部资料：知乎文章 3 篇
  - 更新 `Docs/index.md` - 添加横切主题链接

---

## 2026-05-17（续2）

### 创建 GameFeature 教程系列（30-tutorials/game-feature/）

- 创建 `Docs/30-tutorials/game-feature/` 目录和系列文件
- 创建 `_series.yaml` - 系列元数据（5 个课时，预计 4 小时）
- 创建 `00-overview.md` - 系列概览（概念理解、核心机制、Lyra 实战、高级主题）
- 创建 `01-what-is-gamefeature.md` - GameFeature 是什么？（架构演进、核心概念、与 Plugin 的区别）
- 创建 `02-core-mechanism.md` - 核心机制详解（GameFeaturePlugin、GameFeatureData、GameFeatureAction）
- 创建 `03-lifecycle-loading.md` - 生命周期与加载流程（状态机、加载时序、API 使用）
- 创建 `04-lyra-experience.md` - Lyra 中的 Experience System 实践（预设 Experience、加载流程、插件架构）
- 创建 `05-advanced-custom.md` - 高级主题与最佳实践（自定义 Action、最佳实践、常见陷阱）
- 更新 `Docs/index.md` - 添加 GameFeature 教程系列链接
- 更新 `Docs/00-meta/learning-paths.md` - 添加路线 F：GameFeature 系统
- 引用外部资料：知乎文章 3 篇（InsideUE5 系列）
- 包含 Mermaid 图表（架构图、流程图、时序图、状态图）

---

## 2026-05-17（续3）

### 创建 Modular Gameplay 教程系列（30-tutorials/modular-gameplay/）

- 创建 `Docs/30-tutorials/modular-gameplay/` 目录和系列文件
- 创建 `_series.yaml` - 系列元数据（5 个课时，预计 3.5 小时）
- 创建 `00-overview.md` - 系列概览（概念理解、核心类、Lyra 实战、高级主题）
- 创建 `01-what-is-modular-gameplay.md` - Modular Gameplay 是什么？（设计理念、与传统继承对比）
- 创建 `02-core-classes.md` - 核心类详解（ModularCharacter/GameMode/GameState/PawnComponent）
- 创建 `03-component-lifecycle.md` - 组件生命周期（注册、初始化、回调、注销）
- 创建 `04-lyra-practice.md` - Lyra 实战（角色架构、Experience 集成、组件协作）
- 创建 `05-advanced-custom.md` - 高级主题（自定义组件、最佳实践、性能优化）
- 更新 `Docs/index.md` - 添加 Modular Gameplay 教程系列链接
- 更新 `Docs/00-meta/learning-paths.md` - 添加路线 G：Modular Gameplay 系统
- 参考架构文档：`Docs/10-architecture/subsystems/modular-gameplay.md`
- 包含 Mermaid 图表（架构图、流程图、时序图、状态图、类图）

---

## 2026-05-17（续4）

### 创建 性能优化（Performance Optimization）教程系列（30-tutorials/performance-optimization/）

- 创建 `Docs/30-tutorials/performance-optimization/` 目录和系列文件
- 创建 `_series.yaml` - 系列元数据（6 个课时，预计 5 小时）
- 创建 `00-overview.md` - 系列概览（性能优化原则、系列大纲、核心概念全景图）
- 创建 `01-profiling-tools.md` - 课时 1：性能分析工具（Unreal Insights、Stat 命令、Profiler、GPU Visualizer）
- 创建 `02-cpu-optimization.md` - 课时 2：CPU 性能优化（Tick 优化、算法优化、多线程）
- 创建 `03-gpu-rendering-optimization.md` - 课时 3：GPU 与渲染优化（Draw Call 优化、材质优化、LOD）
- 创建 `04-memory-optimization.md` - 课时 4：内存优化（GC 优化、资源加载优化、内存监控）
- 创建 `05-network-optimization.md` - 课时 5：网络性能优化（复制优化、带宽控制、RPC 优化）
- 创建 `06-lyra-optimization-cases.md` - 课时 6：Lyra 性能实战（组件化架构、异步加载、网络优化）
- 更新 `Docs/index.md` - 添加性能优化教程系列链接
- 更新 `Docs/00-meta/learning-paths.md` - 添加路线 H：性能优化
- 参考架构文档：`Docs/10-architecture/subsystems/modular-gameplay.md`、`Docs/10-architecture/subsystems/networking-system.md`
- 包含 Mermaid 图表（架构图、流程图、时序图、状态图、类图、思维导图）
## 2026-05-17（续5）

### 创建 GC（垃圾回收）教程系列（30-tutorials/garbage-collection/）

- 创建 `Docs/30-tutorials/garbage-collection/` 目录和系列文件
- 创建 `_series.yaml` - 系列元数据（8 个课时，预计 10 小时）
- 创建 `00-overview.md` - 系列概览（GC 概念、学习路径、Lyra 关系）
- 创建 `01-uoobject-basics.md` - 课时 1：UObject 基础与内存模型
- 创建 `02-gc-algorithm.md` - 课时 2：GC 算法详解（标记-清除）
- 创建 `03-reference-types.md` - 课时 3：引用类型系统（UPROPERTY/TWeakObjectPtr）
- 创建 `04-gc-lifecycle.md` - 课时 4：UObject 生命周期与 GC 交互
- 创建 `05-gc-collection.md` - 课时 5：GC 触发时机与收集流程
- 创建 `06-gc-optimization.md` - 课时 6：GC 性能优化策略
- 创建 `07-lyra-gc-practices.md` - 课时 7：Lyra 项目中的 GC 实践（案例分析）
- 更新 `Docs/index.md` - 添加 GC（垃圾回收）系列链接
- 更新 `Docs/00-meta/learning-paths.md` - 添加路线 I：GC（垃圾回收）
- 包含 Mermaid 图表（架构图、流程图、时序图、状态图）

## [2026-05-17] create-series | Behavior Tree & StateTree → [[30-tutorials/ai-behavior/00-BehaviorTree与StateTreeAI决策系统完全指南]]
- 系列篇数：7（00-overview + 01-06）
- 系列定位：BT 基础 → ST 深入 → 对比迁移
- 来源素材：UE5.7 引擎源码（BehaviorTree / StateTree 模块）
- 已完成：_series.yaml + 00-overview + 01（full）+ 02-06（stub）
- lint 验证：0 errors, 0 warnings
- 已更新：Docs/index.md、Docs/10-architecture/subsystems/ai-system.md

## [2026-05-18] create-series | Behavior Tree 高级 → [[30-tutorials/ai-behavior/02-BehaviorTree高级DecoratorService与EQS]]
- 完成：02-behavior-tree-advanced.md（完整教程，约 500 行）
- 内容：Decorator 源码分析 + Service 源码分析 + EQS 集成
- 包含：Mermaid 图示（类图、时序图、状态图）
- 源码引用：BTDecorator.cpp、BTService.cpp、BTService_RunEQS.cpp
- lint 验证：0 errors, 0 warnings
- 已更新：导航块（nav_inject.py --apply）

## [2026-05-18] create-series | StateTree 入门 + 核心机制 → [[30-tutorials/ai-behavior/03-StateTree入门]]
- 完成：03-statetree-intro.md（StateTree 入门，约 400 行）
- 完成：04-statetree-core.md（StateTree 核心机制，约 500 行）
- 内容：StateTree 核心概念 + ExecutionContext 源码分析 + 性能优化
- 包含：Mermaid 图示（类图、时序图、状态图、流程图）
- 源码引用：StateTree.h、StateTreeTaskBase.h、StateTreeEvaluatorBase.h、StateTreeComponent.h
- lint 验证：0 errors, 0 warnings
- 已更新：导航块（nav_inject.py --apply）

## [2026-05-18] create-series | Lyra AI 实战 + 迁移指南 → [[30-tutorials/ai-behavior/05-LyraAI实战Bot控制与BehaviorTree]]
- 完成：05-lyra-ai.md（Lyra AI 实战，约 650 行）
- 完成：06-migration-comparison.md（迁移指南，约 1000 行，SubAgent 创建）
- 内容：
  - 05：Bot 创建流程 + ALyraPlayerBotController 源码分析 + GAS 集成
  - 06：官方建议 + 性能对比 + 功能对比表 + 迁移策略 + 详细步骤
- 包含：Mermaid 图示（类图、流程图、状态图、决策树）
- 源码引用：LyraPlayerBotController.h/cpp、LyraBotCreationComponent.h/cpp
- lint 验证：0 errors, 0 warnings
- 已更新：导航块（nav_inject.py --apply）


## 2026-05-18

### 创建资源管理（Resource Management）教程系列

- 创建 `Docs/30-tutorials/resource-management/` 目录和系列文件
- 创建 `_series.yaml` - 系列元数据（8 个课时，UE 5.7）
- 创建 `00-overview.md` - 系列概览（全景图、与 Lyra 映射、阅读指南）
- 创建 `01-asset-classification.md` - 资产分类体系（Primary/Secondary Asset、AssetManager 配置、Lyra 实践）
- 创建 `02-asset-registry.md` - Asset Registry 查询（FAssetData、FARFilter、按标签过滤、Lyra 实践）
- 创建 `03-async-loading.md` - 异步加载（FStreamableManager、RequestAsyncLoad、FStreamableHandle、Lyra 实践）
- 创建 `04-reference-and-gc.md` - 引用与 GC（引用类型对比、引用链、TSoftObjectPtr 详解、Lyra 实践）
- 创建 `05-cook-and-pak.md` - Cook 与 Pak（Cook 流程、Pak 文件结构、IoStore、Chunk 系统、常见问题）
- 创建 `06-lyra-practices.md` - Lyra 资源管理实践（ULyraAssetManager、Experience 动态加载、Bundle 系统、启动任务）
- 创建 `07-advanced-topics.md` - 高级主题（性能优化、IO 虚拟化、内存诊断、高级 Bundle 用法）
- 更新 `Docs/index.md` - 在 GC 系列后添加资源管理系列入口
- 更新 `Docs/00-meta/learning-paths.md` - 添加路线 J：资源管理
- 所有教程基于引擎源码（f:\UE_5.7\Engine\Source）和 Lyra 项目源码分析
- 遵循 `project-wiki` skill 规则和 `ai-playbook.md` 约束

---

## 2026-05-18（续）

### 创建 输入系统（Input System）教程系列

- 创建 `Docs/30-tutorials/input-system/` 目录和系列文件
- 创建 `_series.yaml` - 系列元数据（7 个课时，UE 5.7）
- 创建 `00-overview.md` - 系列概览（全景图、与 Lyra 映射、阅读指南）
- 创建 `01-input-system-overview.md` - 课时 1：UE 输入系统演进（Legacy Input → Enhanced Input、核心架构）
- 创建 `02-input-actions-and-mapping.md` - 课时 2：Input Action 与 Input Mapping（UInputAction、UInputMappingContext、配置实战）
- 创建 `03-input-triggers-and-modifiers.md` - 课时 3：触发器与修饰器（UInputTrigger 类型、UInputModifier 类型、自定义扩展）
- 创建 `04-input-processing-flow.md` - 课时 4：输入处理流程（UEnhancedInputComponent、优先级、输入路由）
- 创建 `05-lyra-input-practices.md` - 课时 5：Lyra 输入实践（ULyraInputConfig、InputTag 路由、Ability 绑定）
- 创建 `06-advanced-topics.md` - 课时 6：高级主题（多玩家输入、调试技巧、性能优化、常见陷阱）
- 更新 `Docs/index.md` - 在资源管理系列后添加输入系统系列入口
- 更新 `Docs/00-meta/learning-paths.md` - 添加路线 K：输入系统
- 所有教程基于引擎源码（Plugins/EnhancedInput/）和 Lyra 项目源码分析
- 文档路径使用相对路径（遵循用户要求）
- 遵循 `project-wiki` skill 规则和 `ai-playbook.md` 约束

---

## [2026-05-19] create-series | Mutable 可定制角色系统 → [[30-tutorials/mutable/00-Mutable可定制角色系统系列概览]]
- 系列篇数：7（00-overview + 01-06）
- 调研模式：🚀 快速模式
- 来源素材：UE5.7 Mutable 插件源码（`Engine/Plugins/Mutable/Source/`）
- 摘要：创建 Mutable 可定制角色系统从入门到实战系列教程，覆盖概念、架构、核心类、运行时更新、编译/Baking/优化、高级主题
- 更新：`Docs/index.md`、`Docs/00-meta/learning-paths.md`

## [2026-05-19]

### 创建 UMG 教程系列（03-umg-slate-binding、04-widget-tree-and-lifecycle）

- 创建 `Docs/30-tutorials/umg/03-umg-slate-binding.md` - UMG 与 Slate 绑定机制深度分析
  - 概述：UMG 与 Slate 的关系、为什么要分层
  - 核心概念：Slate 是什么、为什么 UMG 不直接渲染、绑定关系的建立时机
  - 源码深度分析：
    - UWidget::TakeWidget() 分析（Widget.cpp L976-L1114）
    - SObjectWidget 分析（SObjectWidget.h）
    - 属性同步机制（SynchronizeProperties）
    - 完整绑定链图示（mermaid sequenceDiagram）
  - 设计决策分析：为什么需要 SObjectWidget、为什么 MyWidget 是 TWeakPtr
  - Lyra 实践：CommonUI 的 SCommonButton 与 UCommonButtonBase 绑定关系
  - 常见问题：TakeWidget() 返回空指针、MyWidget.IsValid() 为 false
  - 包含 mermaid 图示、代码段注释编号

- 创建 `Docs/30-tutorials/umg/04-widget-tree-and-lifecycle.md` - 控件树构建与 Widget 生命周期
  - 概述：从 CreateWidget<T>() 到界面显示的完整流程
  - 核心概念：Widget 生命周期阶段、关键函数调用顺序
  - 源码深度分析：
    - CreateWidget<T>() 流程（UserWidget.h L1811-L1829）
    - Initialize() 深度分析（UserWidget.cpp L135-L202）
    - RebuildWidget() 深度分析（UserWidget.cpp L1179-L1206）
    - OnWidgetRebuilt() 分析（UserWidget.cpp L1208-L1240）
    - NativeConstruct() 深度分析（UserWidget.cpp L1874-L1906）
    - NativeDestruct() 分析（UserWidget.cpp L1908-L1941）
    - Tick 机制（UserWidget.cpp L2086-L2126）
  - 完整生命周期时序图（mermaid sequenceDiagram）
  - Lyra 实践：ULyraActivatableWidget 重写的函数分析
  - 常见问题：为什么 Construct() 被调用两次、为什么 Tick 不执行
  - 包含 mermaid 图示、代码段注释编号

- 更新 `Docs/30-tutorials/umg/_series.yaml` - 系列元数据（已包含 03、04）
- 更新 `Docs/index.md` - 添加 UMG 教程系列链接
- 遵循 `project-wiki` skill 规则和 `ai-playbook.md` 约束
- 已验证源码：Widget.cpp、SObjectWidget.h、UserWidget.cpp、UserWidget.h
- 已验证 Lyra 源码：LyraActivatableWidget.cpp

---

## [2026-05-19] create-series | ue-reflection → [[30-tutorials/ue-reflection/00-UE反射系统从入门到实战]]
- 系列篇数：8（00-overview + 01-07）
- 调研模式：🚀 快速模式
- 来源素材：Engine 源码（`ObjectMacros.h`、`Class.h`、`Field.h`）+ Lyra 源码（`LyraAbilitySet.h`、`LyraPlayerState.cpp`、`LyraHealthComponent.cpp` 等）
- 摘要：创建 UE 反射系统入门到实战系列，覆盖反射概念、核心宏、反射 API、反射驱动的系统（序列化/复制/CDO）、蓝图交互、高级主题与 Lyra 实践

## [2026-05-18] evolve-series | GameplayTag 网络复制 Iris 优化 → [[30-tutorials/gas/19-Tag网络复制]]- 更新：添加 "Iris 复制体系对 FName/GameplayTag 的优化" 章节（约 250 行）
- 新增内容：
  - Iris 是什么（Legacy vs Iris 对比表）
  - FName 两种序列化器（FNameNetSerializer / FNameAsNetTokenNetSerializer）
  - FNameTokenStore 机制详解（Token 生命周期、带宽优化效果表）
  - GameplayTag 在 Iris 中的特殊处理（FGameplayTagNetSerializer 两种模式）
  - FGameplayTagTokenStore（继承自 FNameTokenStore）
  - Legacy vs Iris 完整对比表
  - Lyra 中的 Iris 配置方法（`bUseIrisReplication=true`）
- 更新 mermaid 图（概述区）展示 Legacy/Iris 双路径
- 更新参考资料：新增 Iris 引擎源码引用（6 个文件路径）
- 更新 frontmatter：`last_synced`/`last_verified` → 2026-05-18，`tags` 新增 `Iris`
- 源码验证：`StringNetSerializers.h/cpp`、`GameplayTagNetSerializer.h/cpp`
- lint 验证：0 errors, 0 warnings

---
## [2026-05-19] create-series | UMG 教程系列

- 系列篇数：10
- 调研模式：🚀 快速模式
- 来源素材：UE5.7 引擎源码 + Lyra 项目源码 + Epic 官方文档
- 摘要：完成 UMG（Unreal Motion Graphics）从入门到实战系列教程，覆盖基础概念、核心机制、高级主题与 Lyra 实战
- 文件清单：
  - `30-tutorials/umg/_series.yaml` — 系列元数据
  - `30-tutorials/umg/00-overview.md` — 系列概览
  - `30-tutorials/umg/01-umg-foundation.md` — UMG 基础与核心类架构
  - `30-tutorials/umg/02-widget-types-and-usage.md` — 常用控件详解
  - `30-tutorials/umg/03-umg-slate-binding.md` — UMG 与 Slate 绑定机制深度分析
  - `30-tutorials/umg/04-widget-tree-and-lifecycle.md` — 控件树构建与 Widget 生命周期
  - `30-tutorials/umg/05-umg-animation-system.md` — UMG 动画系统详解
  - `30-tutorials/umg/06-data-binding-and-notify.md` — UMG 数据绑定与属性通知
  - `30-tutorials/umg/07-input-handling-in-umg.md` — UMG 中的输入处理
  - `30-tutorials/umg/08-lyra-umg-practices.md` — Lyra 项目 UMG 实战
  - `30-tutorials/umg/09-umg-performance-optimization.md` — UMG 性能优化
- lint 验证：0 UMG errors after fixes (last_synced, nav blocks, broken links)

---

## [2026-05-19] create-series | UE 摄像机（Camera）系统 → [[30-tutorials/camera-system/00-UE摄像机-Camera系统从入门到实战]]
- 系列篇数：11（00-10）
- 调研模式：🚀 快速模式
- 来源素材：UE5.7 引擎源码（CameraComponent.h、PlayerCameraManager.h、SpringArmComponent.h、CameraShakeBase.h）+ Lyra 项目源码（LyraCameraComponent.h/cpp、LyraCameraMode.h/cpp、LyraCameraMode_ThirdPerson.h、LyraHeroComponent.cpp）
- 摘要：创建 UE 摄像机系统从入门到实战系列教程，覆盖引擎层基础（CameraComponent、PlayerCameraManager、SpringArmComponent、CameraShake）和 Lyra 层架构（CameraMode、CameraModeStack、LyraCameraComponent、Experience 集成），附完整案例分析。

---

## [2026-05-19] create-series | UE Config/INI 系统 → [[30-tutorials/config-in-i/00-overview]]
- 系列篇数：8（00-overview ～ 07-advanced-topics）
- 调研模式：🚀 快速模式
- 来源素材：引擎源码 `ConfigHierarchy.h`、`ConfigCacheIni.h/.cpp`；Lyra `Config/DefaultGame.ini`、`DefaultEngine.ini`
- 摘要：创建 UE Config/INI 系统从入门到实战系列教程，覆盖 INI 文件类型、配置层级合并规则、INI 操作符与 FConfigValue 对应关系、GConfig/FConfigFile API、UObject 配置集成、Lyra 实战、命令行覆盖与 Hotfix 动态层。

## [2026-05-19] create-series | 移动系统系列教程 → [[30-tutorials/movement-system/00-overview.md]]

- **内容**：
  - `00-overview.md` - 系列概览
  - `01-charactermovementcomponent-architecture.md` - CMC 架构
  - `02-movement-modes.md` - 移动模式详解
  - `03-input-to-movement.md` - 输入到移动管线
  - `04-movement-math.md` - 移动物理与数学
  - `05-jump-fly-swim.md` - 跳跃/飞行/游泳
  - `06-network-replication.md` - 网络同步
  - `07-custom-movement-mode.md` - 自定义移动模式
  - `08-root-motion.md` - Root Motion 系统
  - `09-lyra-movement-practices.md` - Lyra 移动实践
  - `_series.yaml` - 系列元数据
- **关联更新**：
  - `Docs/index.md` - 添加系列入口
  - `Docs/00-meta/learning-paths.md` - 添加路线 N（UE 移动系统）
- **引擎源码**：`Engine/Source/Runtime/Engine/Classes/GameFramework/CharacterMovementComponent.h`、`Engine/Source/Runtime/Engine/Private/Components/CharacterMovementComponent.cpp`
- **执行人**：AI（create-series 工作流）


## [2026-05-19] create-series | 创建 UE Config/INI 系统教程系列 → [[Docs/30-tutorials/config-ini/00-overview.md]]


> 基于引擎源码（`ConfigHierarchy.h`、`ConfigCacheIni.h/.cpp`、`ConfigContext.cpp`）和 Lyra 项目实际 INI 文件，创建从入门到实战的完整教程系列。

- 创建 `Docs/30-tutorials/config-ini/` 目录和系列文件：
  - `_series.yaml` — 系列元数据（8 课时，预计 6 小时）
  - `00-overview.md` — 系列概览（Config 系统全景图、14 层 INI 层级图、INI 操作符速查）
  - `01-ini-file-types.md` — INI 文件类型与命名规范（Base/Default/Platform/Saved 详解、`{TYPE}` 替换规则）
  - `02-config-hierarchy.md` — 配置层级与合并规则深度解析（GConfigLayers[] 逐层详解、FConfigFile::Combine() 行为）
  - `03-ini-operators.md` — INI 操作符详解（CommandLookup 表映射、7 大操作符逐一解析、Lyra 实战案例）
  - `04-gconfig-api.md` — GConfig 与 FConfigFile API 实战（GConfig 全局指针、FConfigFile/FConfigSection/FConfigValue API、实战示例）
  - `05-uobject-config.md` — UObject 与 Config 系统集成（`config` 说明符、LoadConfig/SaveConfig 机制与调用链、`PerObjectConfig`、LyraSettingsLocal 示例）
  - `06-lyra-config-examples.md` — Lyra 项目 Config 实战分析（`DefaultGame.ini` 和 `DefaultEngine.ini` 逐段解析、INI Section 与 C++ 类映射表）
  - `07-advanced-topics.md` — 高级主题（命令行覆盖、Hotfix 动态层、平台差异化配置、`SafeUnload` 内存优化、调试技巧、性能优化建议）

- 更新索引文件：
  - `Docs/index.md` — 添加 Config/INI 系统系列链接（8 课全部接入导航）
  - `Docs/00-meta/learning-paths.md` — 添加路线 O：Config/INI 系统

- 关键技术要点：
  - ✅ 正确识别 `GConfigLayers[]` 为 **14 层**（非 13 层），含 `GameDirUser` 层
  - ✅ 正确映射 `CommandLookup` 表（`\0`=Set、`.`=ArrayAdd、`+`=ArrayAddUnique、`-`=Remove、`!`=Clear、`^`=InitializeToEmpty、`@`=ArrayOfStructKey、`*`=POCArrayOfStructKey）
  - ✅ 结合 Lyra 实际 INI 文件提供案例（`DefaultGame.ini`、`DefaultEngine.ini`）
  - ✅ 提供 `ULyraSettingsLocal` 完整源码分析（`UPROPERTY(config)` 示例、`LoadSettings()` 实现）

- 遵循 `project-wiki` skill 规则和 `ai-playbook.md` 约束
- lint 验证：所有文件 `status: current`，索引完整


## [2026-05-19] create-series | 本地化与国际化系列 → [[30-tutorials/localization-i18n/00-UE本地化与国际化概览]]

- **系列篇数**：7 篇
- **调研模式**：🚀 快速模式
- **来源素材**：UE 5.7 官方文档、Lyra 项目源码（LyraSettingValueDiscrete_Language.cpp、LyraTextHotfixConfig.cpp、Game_Gather.ini、Game_Compile.ini）
- **摘要**：创建了完整的 UE 本地化与国际化教程系列，涵盖 I18n/L10n 概念、FText、String Table、本地化仪表盘、资产本地化、运行时语言切换、Lyra 实践案例
- **文件列表**：
  - `30-tutorials/localization-i18n/_series.yaml`
  - `30-tutorials/localization-i18n/00-overview.md`
  - `30-tutorials/localization-i18n/01-i18n-vs-l10n.md`
  - `30-tutorials/localization-i18n/02-text-localization.md`
  - `30-tutorials/localization-i18n/03-localization-dashboard.md`
  - `30-tutorials/localization-i18n/04-asset-localization.md`
  - `30-tutorials/localization-i18n/05-runtime-language-switch.md`
  - `30-tutorials/localization-i18n/06-lyra-localization-practice.md`
  - `30-tutorials/localization-i18n/index.md`
- **索引更新**：`Docs/index.md`

---

## [2026-05-20] evolve-series | 动画系统系列补充 Motion Matching 教程 → [[30-tutorials/animation/09-MotionMatching运动匹配深度解析]]
- **系列篇数**：9 篇（原 8 篇 + 新增 1 篇）
- **调研模式**：🚀 快速模式（基于官方文档 + WebSearch）
- **来源素材**：UE 5.7 官方文档、Epic Developer Community 教程、知乎技术文章
- **摘要**：深入讲解 Motion Matching 原理、Pose Search 系统、设置流程及与传统状态机的对比，包含 Lyra 集成方案分析
- **文件列表**：
  - `30-tutorials/animation/09-motion-matching.md`（新创建）
  - `30-tutorials/animation/_series.yaml`（更新 total_lessons: 8→9）
  - `Docs/index.md`（更新动画系列索引）
  - `30-tutorials/animation/01-overview.md`（更新导航表格和 mermaid 图）
  - `30-tutorials/animation/08-advanced-topics.md`（更新 nav 块指向 09）
- **关联更新**：01-overview 的建议学习路径（高级开发者路径添加 09）
- **关键技术要点**：
  - Motion Matching 通过每帧从动画库匹配最佳姿势替代传统状态机
  - 核心组件：Pose Search Schema（规则）、Database（数据）、Channels（比较维度）
  - 使用 PCAKDTree 搜索算法优化性能（60min 数据库：120ms→3ms）
  - Lyra 默认未使用 Motion Matching（UE 5.0 时尚未集成），但提供了集成方案分析
- **lint 验证**：0 errors, 4 warnings（warnings 为存量 missing-nav 问题）

---

## [2026-05-21] evolve-series | 动画系统系列补充程序化动画教程 → [[30-tutorials/animation/10-ControlRig深度解析]] [[30-tutorials/animation/11-程序化动画技术-Warping-PoseDriver-FullBodyIK]]
- **系列篇数**：11 篇（原 9 篇 + 新增 2 篇）
- **调研模式**：🔬 深度解析模式（基于引擎源码 + WebSearch）
- **来源素材**：UE 5.7 ControlRig 插件源码、AnimationWarping 插件源码、UE 官方文档
- **摘要**：深入讲解 UE5 程序化动画技术，包括 Control Rig 架构、RigVM、Rig Units、Animation Warping、Pose Driver、Full Body IK、Animation Modifiers
- **文件列表**：
  - `30-tutorials/animation/10-control-rig-deep-dive.md`（新创建，Control Rig 深度解析）
  - `30-tutorials/animation/11-procedural-animation-techniques.md`（新创建，程序化动画综合技术）
  - `30-tutorials/animation/_series.yaml`（更新 total_lessons: 9→11，添加程序化动画阶段）
  - `Docs/index.md`（更新动画系列索引，添加 10、11 条目）
  - `30-tutorials/animation/09-motion-matching.md`（更新 nav 块指向 10）
- **关联更新**：`_series.yaml` 新增"程序化动画"学习阶段（第 4 阶段）
- **关键技术要点**：
  - Control Rig 通过 RigVM 虚拟机执行节点图，性能接近 C++ 硬编码
  - Rig Hierarchy 管理骨骼/Control/Curve 的层次结构
  - Animation Warping 包含四大节点：Orientation/Slope/Stride/Foot Placement
  - Lyra 默认未使用 Control Rig，使用传统 AnimNode IK（如 FABRIK）
  - 程序化动画技术栈：Control Rig → Animation Warping → Pose Driver → Full Body IK
- **lint 验证**：0 errors

---

## [2026-05-21] create-series | 新增 review-series 工作流 → [[00-meta/ai-playbook]]
- **摘要**：新增教程系列质量审查工作流（review-series），系统性检查教程的专业性、准确性、教学设计、系列顺序合理性和格式规范
- **文件列表**：
  - `.claude/skills/project-wiki/workflows/review-series.md`（新建）
  - `.claude/skills/project-wiki/skill.md`（更新路由表）
  - `Docs/00-meta/ai-playbook.md`（更新工作流路由和验证要求表）
- **审查维度**：5 大维度 / 40+ 检查点
  - 专业性与准确性（10 项）
  - 教学设计（10 项）
  - 系列顺序与结构（10 项）
  - 格式与规范一致性（10 项）
  - 内容完备性（6 项）
- **支持模式**：Full Review / Page Review / Cross-Series Review

---

## [2026-05-21] review-series | network-sync 质量审查 → [[30-tutorials/network-sync/00-UE网络通信总览]]
- **审查模式**：Full Review
- **综合评分**：9.2/10 (⭐⭐⭐⭐⭐)
- **问题统计**：Critical 0 / Major 2 / Minor 1
- **已修复**：0 项（已导出报告，暂缓修复）
- **待修复**：3 项
- **报告文档**：[[_raw/chats/2026-05-21-network-sync-review]]

## [2026-05-21] fix | network-sync 质量审查问题修复 → [[30-tutorials/network-sync/00-UE网络通信总览]]
- **修复内容**：解决了 `00-network-overview.md` 的 related 引用不对称问题，并为部分代码块增加了 `[N]` 行号导读注释。
- **忽略内容**：跳过 `lesson_index` 断层的修复。

## [2026-05-21] review-series | 动画系统教程质量审查 → [[30-tutorials/animation/01-Lyra动画系统框架深度分析-概览]]
- **审查模式**：Full Review
- **综合评分**：8.8/10 (⭐⭐⭐⭐⭐)
- **问题统计**：Critical 3 / Major 2 / Minor 0
- **已修复**：3 项（版本漂移、对称链接、prerequisites 格式修复）
- **待修复**：2 项（代码块过长、缺少 lyra_sources 记录）
- **生成的报告**：Docs/Review-Report-Animation.md

## [2026-05-21] evolve-series | 动画系统教程专项修复
- **审查模式**：单篇修复
- **执行原因**：解决此前全系列审查（Full Review）发现的 Major 问题
- **关联更新**：
  - 拆分了 `04-anim-graph-state-machine` 和 `07-notify-and-effects` 中超过 50 行的 6 个超长代码块，补充了中文分析注释
  - 补充了 `09`、`10`、`11` 等高级篇目遗漏的 `lyra_sources` 资产路径记录
- **lint 验证**：无相关系列报错

## [2026-05-21] review-series + evolve-series | Niagara 系统教程质量审查与修复
- **审查模式**：Full Review
- **综合评分**：7.0/10 (⭐⭐⭐⭐)
- **问题统计**：Critical 1 / Major 3 / Minor 2
- **已修复**：
  - P0: 批量替换 6 篇文档中的 macOS 绝对路径为相对路径 `Engine/...`
  - P1: 统一全系列 prerequisites 为 `[[...]]` 双括号格式
  - P2: 拆分 16 个超长代码块（03/04/05/07/08），补充中文逻辑说明与 [N] 编号
  - P3: 调整 04/05/07 难度为 `advanced`，移除 08 中非技术标签 `reference`
- **lint 验证**：无相关系列报错

## [2026-05-22] review-series | garbage-collection 质量审查 → [[30-tutorials/garbage-collection/00-GC垃圾回收系列概览]]
- **审查模式**：Full Review
- **综合评分**：7.5/10 (⭐⭐⭐⭐)
- **问题统计**：Critical 2 / Major 3 / Minor 4
- **已修复（P0）**：2 项
  - 重命名 `01-uoobject-basics.md` → `01-uobject-basics.md`（修正拼写错误）
  - 更新 `_series.yaml` 和所有 wikilinks 指向新文件名
- **已修复（P1）**：3 项
  - 移除全部 8 篇文档的手动 nav 块（由 `nav_inject.py` 自动管理）
  - 修正 `01-uobject-basics.md` 的 `id` 字段为 `30-tutorials/garbage-collection/01-uobject-basics`
  - 补充 `00-overview.md` 缺少的 `related` 字段
- **已修复（P2）**：2 项
  - ✅ P2: `01-uobject-basics.md` 添加 UObject 继承关系 mermaid 图（classDiagram）
  - ✅ P2: `06-gc-optimization.md` 添加 GC 优化决策流程图（flowchart TD）
- **已修复（P3）**：2 项
  - ✅ P3: 多处硬编码 `UObject`（应为 `UObject`）— **经核实为误判**：`UPROPERTY`/`GENERATED_BODY` 是正确宏名称（UE 宏命名惯例用数字 `0` 代替字母 `O`），无需修复
  - ✅ P3: 为 01-06 添加「Lyra 中的实践」小节（每篇 1-2 段 + 代码示例）
- **跳过（P3）**：1 项
  - ⏭ P3: 代码示例 `[N]` 行号标注 — **跳过**（8 个文件工作量过大，且现有代码块已足够清晰）
- **报告路径**：`Docs/_raw/review-reports/Review-Report-garbage-collection-2026-05-22.md`

## [2026-05-22] review-series | mutable 系列质量审查 → [[30-tutorials/mutable/00-Mutable可定制角色系统系列概览]]
- **审查模式**：Full Review
- **综合评分**：7.15/10 (⭐⭐⭐⭐)
- **问题统计**：Critical 2 / Major 4 / Minor 3
- **已修复（P0）**：1 项
  - ✅ P0: `03-customizable-object-and-instance.md` 添加 mermaid 关系图（UCustomizableObject ↔ UCustomizableObjectInstance）
- **已修复（P2）**：1 项
  - ✅ P2: `05-compilation-baking-and-optimization.md` 添加编译流程示意图（flowchart TD）
- **已修复（P1）**：1 项
  - ⚠️ P1: 全系列源码行号标注为"约 LXX"（因引擎源码访问超时，未真正验证，标注为待验证）
- **已修复（P3）**：1 项（大动作）
  - ✅ P3: 拆分 `06-advanced-topics` 为两篇：`06-advanced-multi-component.md` + `07-integration-and-gotchas.md`
  - 更新 `_series.yaml`：`total_lessons: 8`，learning_path 高级主题阶段包含两篇
  - 原 `06-advanced-topics.md` 标记 `status: deprecated`
  - 更新 `Docs/index.md` 拆分引用
- **已检查（P4）**：1 项
  - ✅ P4: 统一总结要点格式 — 经逐篇检查，格式已统一为 `| # | 要点 |` 表格，无需修复
- **报告路径**：`Docs/_raw/review-reports/Review-Report-mutable-2026-05-22.md`
- **lint 验证**：待执行（自动修复后需重跑）

---

### review-series | localization-i18n 质量审查 → [[30-tutorials/localization-i18n/00-UE本地化与国际化概览]]
- **审查模式**：Full Review
- **综合评分**：7.2/10 (⭐⭐⭐)
- **问题统计**：Critical 3 / Major 6 / Minor 5
- **已修复（P0）**：2 项
  - ✅ P0: 全套 8 文件 `prerequisites:` 改为标准 wikilink 格式，移除 `keywords` 非标准字段
  - ✅ P0: `06-lyra-localization-practice.md` nav 块移除错误的 camera-system 引用
- **已修复（P1）**：1 项
  - ✅ P1: `05-runtime-language-switch.md` 修复 `BindDynamic` C++ 语法错误（改为 SetText 直接调用）
- **待修复（P1 剩余）**：1 项
  - ⚠️ P1: `02-text-localization.md` 中 `FStringTableRegistry` API 需验证 UE 5.7 中是否仍有效
- **待修复（P2/P3）**：若干（可选，见报告）
- **报告路径**：`Docs/_raw/review-reports/Review-Report-localization-i18n-2026-05-22.md`

---

## [2026-05-22] review-series | ai-behavior 质量审查 → [[30-tutorials/ai-behavior/00-BehaviorTree与StateTreeAI决策系统完全指南]]
- **审查模式**：Full Review
- **综合评分**：6.5/10 (⭐⭐⭐)
- **问题统计**：Critical 7 / Major 8 / Minor 5
- **已修复（P0）**：3 项
  - ✅ `01-behavior-tree-basics.md` status: draft → current
  - ✅ `01-behavior-tree-basics.md` 添加 `last_verified: 2026-05-17`
  - ✅ `00-overview.md` + `01-behavior-tree-basics.md` 绝对路径改相对路径
- **已修复（P1）**：6 项
  - ✅ `03-statetree-intro.md` + `04-statetree-core.md` 修复 mermaid 语法错误
  - ✅ 全套 7 个文件移除手动 nav 块（改由 `nav:auto` 管理）
  - ✅ `03-statetree-intro.md` difficulty: beginner → intermediate
  - ✅ `03-statetree-intro.md` prerequisites 改为指向 `01-behavior-tree-basics`
  - ✅ `01-behavior-tree-basics.md` 添加 `estimated_minutes: 60`
  - ✅ `06-migration-comparison.md` 添加 `last_verified` + `estimated_minutes: 120`
- **待修复（P2/P3）**：若干（见报告）
- **报告路径**：`Docs/_raw/review-reports/Review-Report-ai-behavior-2026-05-22.md`

## [2026-05-23] fix | query.py 修复无关文档霸榜 TOP → [[00-meta/ai-playbook]]

- **触发场景**：`python3 query.py "免疫"` TOP 5 全是 blueprint-system / editor-extension / game-feature 等无关 tutorial（统一 score=1.4），真正含"免疫"内容的 GAS 文档（`12-GE组件` 7 处命中、`13-GE匹配查询` 5 处命中）被挤到 BODY-ONLY 区块
- **根因**：`CORE_TYPE_BOOST["tutorial"]=0.4` 无条件保底 + `inbound` 加分封顶 1.0 = 1.4 分"虚假底线"；`grep_body()` 结果只用于显示不回灌排序
- **修复点**：
  - `score_against_page()` (L490-494)：`CORE_TYPE_BOOST` 加守卫 `if boost > 0 and score > 0`，无命中信号时不发放 boost
  - `run_query()` (L745-810)：body grep 提前到组装候选**之前**执行，分数 `min(matches,5)*0.5` 回灌 `cand_scores`，命中行号写入 `why`（如 `body-hit:7@L25,L146,...`）；BODY-ONLY 区块改为只显示未被 TOP/邻居吸纳的命中
- **修复效果对比**（"免疫"查询）：

  | 排名 | 修复前 (1.4) | 修复后 |
  |---|---|---|
  | 1 ★ | blueprint-system/01（无关） | **gas/06-GE简介与配置** (2.8) |
  | 2 | editor-extension/01（无关） | **gas/12-GE组件** (2.8) |
  | 3 | game-feature/01（无关） | **gas/13-GE匹配查询** (2.8) |
  | 4 | garbage-collection/01（无关） | **gas/18-Tag匹配查询** (2.8) |
  | 5 | modular-gameplay/01（无关） | **gas/07-GE运行流程详解** (1.9) |

- **文件列表**：`.codebuddy/skills/project-wiki/scripts/query.py`
- **lint 验证**：原有 basedpyright 类型注解告警与本次修复无关（pre-existing），未引入新错误

---

## [2026-05-26] crystallize | 预测 GA 触发 AddGameplayCue 在 Full 模式的双播抑制坑沉淀 → [[80-gotchas/gas-predicted-add-cue-on-full-replication]]

- **来源素材**：用户提问"主动预测 GA Active 触发 AddGameplayCue_Internal，最终 NetMulticast_InvokeGameplayCueAdded_WithParams_Implementation 因 Full 模式被客户端无视"的本次会话分析
- **摘要**：根因不是 ReplicationMode 单独导致，而是 `PredictionKey.IsLocalClientKey()` 过滤 + 客户端 `else` 分支预测窗口失效组合所致；Full 模式下不重写 key 是因为信任 else 分支已本地播过
- **文件列表**：
  - 新增 `Docs/80-gotchas/gas-predicted-add-cue-on-full-replication.md`（完整 gotcha：根因链 + 4 种方案 + 决策树 + 复现步骤）
  - 修改 `Docs/30-tutorials/gas/21-GC运行时详解.md`：在"多端触发机制"之后新增章节《预测 GA 触发 Add 类 Cue 的双播抑制与 ReplicationMode 差异》（含真值表、时序图、设计意图、定位指南），`last_synced` / `last_verified` 更新至 2026-05-26
- **关联更新**：
  - `Docs/index.md` 已知坑章节追加 gotcha 链接
  - `_series.yaml` 无需变更（lesson 数未变）
- **关键技术要点**：
  - `NetMulticast_InvokeGameplayCueAdded_WithParams_Implementation` 过滤条件：`IsOwnerActorAuthoritative() || (!IsLocalClientKey() && !bIsMixedReplicationFromServer)`（`AbilitySystemComponent.cpp` L1637-L1648）
  - `AddGameplayCue_Internal` 服务器分支在 Full 模式下 `PredictionKeyForRPC = ScopedPredictionKey` 不重写（L1503-L1523）
  - 客户端 `else if (ScopedPredictionKey.IsLocalClientKey())` 分支本地立即播 OnActive/WhileActive（L1538-L1545）
  - `IsLocalClientKey()` 语义是"当前进程生成"而非"client 类型"
  - 4 种解决方案：A 改用 ExecuteGameplayCue / B 切换 Mixed（Lyra 默认）/ C 手动 HasAuthority 分支补播 / D MinimalReplication + 手动播
- **源码验证**：已读取 UE 5.7 `Engine/Plugins/Runtime/GameplayAbilities/Source/GameplayAbilities/Private/AbilitySystemComponent.cpp`（L1447-L1666）+ `AbilitySystemReplicationProxyInterface.cpp` L36-L53 + `AbilitySystemComponent.h` L78-L88
- **后续建议**：建议跑 `wiki_rebuild.py --incremental` 让 FTS5 索引同步本次新增/修改的两页

---
