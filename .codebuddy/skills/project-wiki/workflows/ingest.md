# 工作流：ingest（消化素材到项目知识库）

把一份原始素材（spec / 会议纪要 / PR 描述 / 设计文档 / 代码扫描结果 / **外部文章**）变成结构化的 wiki 页面。

## 适用素材类型

| 类型 | 落到 `Docs/_raw/` 哪里 | 主要产出 |
|---|---|---|
| 需求/设计 spec | `_raw/specs/` | `70-topics/` 或 `10-architecture/subsystems/` 页 |
| 会议纪要 | `_raw/meetings/` | 更新若干 `60-decisions/` 或 `10-architecture/` 页 |
| 关键 AI 对话沉淀 | `_raw/chats/` | 走 **crystallize** 工作流，本工作流不直接处理 |
| PR / commit 描述 | （不入 raw，直接走 wiki） | `60-decisions/` 或更新 `20-modules/` |
| 代码扫描产出（如 AI 扫 Source/） | （不入 raw，直接走 wiki） | `10-architecture/` + `20-modules/` |
| **外部文章 / UE 官方文档 / 博客 / 论文 / 视频** | `_raw/external/` | `50-references/{ue-official,third-party,articles}/` |

## 素材类型判断

收到素材后，先判断是**项目内部素材**还是**外部素材**：

- **外部素材**（URL / 非项目来源的文章 / UE 官方文档 / 博客 / 论文 / 视频转写）→ 走下方 **外部素材分支**
- **项目内部素材**（spec / 会议 / PR / 代码扫描）→ 走下方 **步骤 1-8**

---

## 外部素材分支

处理 UE 官方文档、博客文章、论文、视频转写等非项目来源的参考资料。

### E1. 获取内容

- **URL** → 用 `WebFetch` 抓取网页正文（markdown 格式）
- **本地文件**（PDF / Markdown / 纯文本）→ 直接读取
- **纯文本粘贴** → 直接使用

### E2. 保存原始素材

落到 `Docs/_raw/external/{YYYY-MM-DD}-{slug}.md`

### E3. 分类路由

按来源特征决定写到 `Docs/50-references/` 的哪个子目录：

| 来源特征 | 目标目录 |
|---------|---------|
| UE 官方（`docs.unrealengine.com` / `dev.epicgames.com` / UE 论坛） | `50-references/ue-official/` |
| 第三方库文档（GitHub / npm / crates.io） | `50-references/third-party/` |
| 其他文章、博客、论文、视频 | `50-references/articles/` |

### E4. 生成 wiki 页

参考 `templates/external-source.md` 生成页面：

- frontmatter 必须沿用 project-wiki 统一格式（`id` / `type: source` / `status` / `anchors: []` / `last_synced`）
- **核心要点**：3-5 条关键信息
- **与项目的关联**：这篇素材对本项目有什么参考价值
- **关键概念**：用 `[[wikilink]]` 链接到已有 wiki 页（如存在）
- **原文摘录**：2-3 段精彩原文

### E5. 近似查重（必须走图谱）

★ ingest 是"创建新页"场景，query 路由表中**禁止跳过图层**——否则极易产生重复页。

```bash
# 用素材标题 / 核心关键词查（wiki_query.py 自动展开 alias）
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "<素材主题>" --json --no-body
```

判定规则：
- TOP1 候选 score ≥ 6 且 ID/desc 高度重合 → 视为 ≥ 70% 重合 → **update 已有页**
- TOP1 候选 score 在 3~6 之间 → 沿 `related` / 1-hop 邻居进一步确认
- 全部候选 score < 3 → create 新页
- 命中 `status: stale / deprecated` 候选 → 警告用户："已有但过期，是新建还是先 lint 复活旧页？"

### E6. 更新 index.md

追加到 `Docs/index.md` 的 `## 50-references/` 区段：
```
- [[50-references/ue-official/state-tree-overview]] — StateTree 官方文档要点 (source, current, 2026-05-15)
```

### E7. 追加 log.md

```
## [2026-05-15] ingest-external | StateTree 官方文档 → [[50-references/ue-official/state-tree-overview]]
- 来源：https://docs.unrealengine.com/...
- 落 raw：_raw/external/2026-05-15-state-tree-overview.md
- 摘要：1-2 句话
```

### E8. 输出

```
已消化外部素材：{标题}

新增：
- Docs/50-references/{分类}/{slug}.md

原始素材：
- Docs/_raw/external/{日期}-{slug}.md

与项目的关联建议：
- 与 [[20-modules/cpp/ALyraCharacter]] 相关（都涉及 ...）
- 建议在 [[70-topics/xxx]] 中引用

别名建议：（仅当发现同义词时）
- 建议添加到 .wiki-schema.md 别名词表：{术语A} = {术语B}
```

---

## 步骤（项目内部素材）

### 1. 前置检查与近似查找（必须走图谱）

★ ingest 是"创建新页"场景，query 路由表中**禁止跳过图层**——否则极易产生重复页。

1. 读 `Docs/.wiki-schema.md` 确认目录约定
2. **走 wiki_query.py 一击查重**（替代手工读 index + rg 关键词）：
   ```bash
   # 用素材标题 + 涉及模块名查
   python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "<标题关键词> <模块名>" --json
   ```
   重点看输出中：
   - TOP N 候选的 `score` / `description` / `tags`
   - 1-HOP NEIGHBORS（同图簇里的相关页，常常就是该 update 的目标）
   - GLOBAL WARNINGS（候选含 stale / deprecated 时必须警告用户）
3. **判定**：
   - 找到 ≥ 70% 重合（TOP1 score ≥ 6 且 id/desc 高度重合）→ **update 该页**
   - 找到 30%~70% 重合 → 沿 1-HOP NEIGHBORS 找更准确的 update 目标
   - < 30% 重合 → **create 新页**，并用 NEIGHBORS 作为新页 `related:` 候选

### 2. 选择目标层级

按素材性质决定写到哪一层（按优先级）：

1. **横切主题** → `70-topics/<slug>.md`
2. **架构性** → `10-architecture/subsystems/<name>.md` 或 `10-architecture/overview.md`
3. **决策性** → `60-decisions/NNNN-<slug>.md`（编号取下一个）
4. **操作性** → `40-runbooks/<slug>.md`
5. **单模块说明** → `20-modules/<cpp|blueprint>/<id>.md`
6. **踩坑** → `80-gotchas/<slug>.md`

### 3. 落 raw（如适用）

- 若素材是文件 → 复制到对应 `_raw/<subtype>/<YYYY-MM-DD>-<slug>.<ext>`
- 若素材是粘贴文本 → 写入 `_raw/<subtype>/<YYYY-MM-DD>-<slug>.md`
- 若素材是 URL → 走上方**外部素材分支**（E1-E8）

### 4. 生成 wiki 页

用对应 template（见 `templates/`）生成：

- frontmatter 必填字段：`id` / `type` / `status: current` / `language: zh` / `owner` / `anchors` / `last_synced` / `tags`
- **anchor 字段**（v0.1 只记 path）：
  ```yaml
  anchors:
    - path: Source/LyraGame/Character/LyraCharacter.h
    - path: Source/LyraGame/Character/LyraCharacter.cpp
  ```
- 写正文：**Why / How / What / Gotchas** 四段，缺哪段就留 `(待补)` 占位

### 5. 双向链接

- 在新页底部"相关页面"加 `[[other-id]]` 链接
- **同时**在被链接页（如已存在）添加反向链接，避免单向

### 6. 更新 index.md

按分类追加：
```
- [[20-modules/cpp/ALyraCharacter]] — Lyra 角色基类 (modules/cpp, current, 2026-05-16)
```

### 7. 追加 log.md

```
## [2026-05-16] ingest | <来源标题> → <目标 wiki id>
- 来源：_raw/specs/2026-05-16-lyra-ability-system.md
- 影响页：[[20-modules/cpp/ALyraCharacter]], [[10-architecture/subsystems/ability-system]]
- 摘要：1-2 句话
```

### 8. 输出

向用户报告：
- 创建/更新的页面列表（带 wiki id）
- 是否触及未存在的 wikilink（建议下次补）
- 是否检测到与已有页面矛盾（如有，提示走 lint）

## 失败/降级

- 找不到合适层级 → 默认放 `70-topics/`，标 `status: draft`，提示用户人工归类
- 素材内容含敏感信息（密钥、IP）→ 自动 redact 再写入 raw，警告用户
- 素材过大（> 50k token）→ 分段处理，每段一次 ingest，最后用 digest 综合

## 与 crystallize 的区别

- **ingest**：处理**已存在的外部/正式**素材（spec/会议/PR）
- **crystallize**：处理**当前会话**里 AI 刚搞清楚的事，沉淀成 wiki 页

两者最终都更新 wiki，但触发场景与产出风格不同。
