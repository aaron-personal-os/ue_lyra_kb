# 工作流：rebuild-index（构建/更新检索索引）

> 维护 `.codebuddy/skills/project-wiki/.cache/wiki.db`（Tier 1 FTS5 + 知识图谱）/ 可选向量索引（Tier 2）。
>
> **默认走增量重建**（`--incremental`，毫秒级）。**只有用户明确说"全量重建 / 重新建索引 / rebuild from scratch"才走全量**。

## 触发关键词

| 用户意图 | 模式 | 命令 |
|---|---|---|
| "更新索引" / "重建索引" / "rebuild wiki index" / "更新检索" / "刷新数据库" | **增量**（默认） | `wiki_rebuild.py --incremental` |
| "全量重建" / "重新建索引" / "rebuild from scratch" / "drop wiki.db" / "删库重建" | 全量 | `wiki_rebuild.py` |
| "检查索引是否需要更新" / "check 索引" | 检查 | `wiki_rebuild.py --check` |
| "构建向量索引" / "启用 Tier 2" / "with vectors" | 增量 + 向量 | `wiki_rebuild.py --incremental && wiki_rebuild.py --with-vectors` |
| "只重建向量" / "rebuild vectors only" | 仅向量 | `wiki_rebuild.py --vectors-only` |

## ★ 标准流程：增量重建（默认）

**90% 的场景走这一条**。基于 SHA-256 hash 比对，未变更文件直接跳过，毫秒级完成。

```bash
python3 .codebuddy/skills/project-wiki/scripts/wiki_rebuild.py --incremental
```

**预期输出**：

```
Rebuilt wiki.db (Incremental): 3 pages indexed, 12 edges extracted, 275 skipped (unchanged) [241ms]
  → .codebuddy/skills/project-wiki/.cache/wiki.db
```

**关键字段**：
- `pages indexed`：本次因 hash 变化重新写入的页数
- `edges extracted`：本次写入的图边数（wikilink + related + prerequisite 三类）
- `skipped (unchanged)`：hash 未变 → 跳过
- `deleted`：源文件已删除 → 从 db 清理

## 何时该跑增量重建

✅ 触发场景（用户给/AI 自己改完 Docs/ 后**主动建议跑一次**）：

1. **写完 / 改完 wiki 页**（teach / ingest / crystallize / evolve-series / create-series 完成时）
2. **批量编辑后**（rename_page.py / fix_asymm.py / nav_inject.py 跑完后）
3. **lint --fix 后**（lint 修了 frontmatter / index 漏录）
4. **git pull 后**（拉取了同事的 Docs/ 变更）
5. **回答前发现 wiki.db 比 Docs/ 旧**（`--check` 退出码 1）

❌ 不需要跑：

- 只读了 wiki 没改
- 只动了 `Source/` / `Plugins/` / `Content/` 等非 Docs/ 内容
- 只改了 `Docs/_raw/` 或 `Docs/log.d/`（被排除目录）

## 检查模式（CI / 自检用）

```bash
python3 .codebuddy/skills/project-wiki/scripts/wiki_rebuild.py --check
# exit 0 = 无需重建
# exit 1 = 检测到变更（输出第一个变更的页 id）
```

可作 pre-commit hook，避免提交时 wiki.db 滞后于 Docs/。

## ⚠ 全量重建（仅在用户明确要求时执行）

**重要**：默认**绝不**走全量重建。只有以下情况：

| 触发条件 | 例子 |
|---|---|
| 用户**明确说**全量 | "全量重建索引"、"drop 数据库重新建"、"rebuild from scratch"、"delete wiki.db and rebuild" |
| schema 升级（自增量自动 fallback） | `wiki_rebuild.py` 检测到 `build_meta.schema_version` 不匹配时**自动**走全量（无需用户介入） |
| `wiki.db` 损坏 / 索引数据明显错误 | 如查 "ability" 应该命中却返回空 |
| 首次构建（`wiki.db` 不存在） | 增量模式自动 fallback 到全量 |

**全量命令**：

```bash
python3 .codebuddy/skills/project-wiki/scripts/wiki_rebuild.py
```

> ⚠️ 全量重建会**先删除整个 wiki.db**再从头扫所有 .md 文件。278 页约 350-500ms，但之前的向量索引（Tier 2）会一并丢失，需要 `--with-vectors` 重新嵌入（或后续 `--vectors-only` 补回）。

## Tier 2：构建向量索引（语义检索）

**前置依赖**：

```bash
pip install sqlite-vec               # 向量虚拟表（可选；不装则用暴力余弦回退）
export OPENAI_API_KEY="sk-..."       # 或配置 ollama provider
```

**首次构建（FTS + 向量一起）**：

```bash
python3 .codebuddy/skills/project-wiki/scripts/wiki_rebuild.py --with-vectors
```

**只补建向量（FTS 已存在）**：

```bash
python3 .codebuddy/skills/project-wiki/scripts/wiki_rebuild.py --vectors-only
```

**注意**：
- 向量构建会调用 embedding API，速度取决于网络（OpenAI ~4s/100 页，Ollama 本地 ~1s/100 页）
- 向量索引**不支持增量**：每次都是 `DELETE FROM chunks; DELETE FROM vec_chunks; 重新嵌入`
- 因此**默认增量重建不带 `--with-vectors`**；用户明确要求向量时再补

## 验证索引健康

跑完重建后建议立刻做一次冒烟查询：

```bash
# 测一个稳定的高频关键词，确认 Tier 1 已生效
python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "GameplayAbility" --max-candidates 1

# 输出末尾应有 [Tier: Tier 1 (FTS5)]
```

## 路径与产物

| 路径 | 作用 | 是否进 git |
|---|---|---|
| `.codebuddy/skills/project-wiki/.cache/wiki.db` | SQLite 索引（pages + pages_fts + links + chunks + vec_chunks + build_meta） | ❌ 已被 `.gitignore` 排除 |
| `.codebuddy/skills/project-wiki/config.yaml` | 引擎/嵌入配置 | ✅ |
| `Docs/**/*.md` | **System of Record（真相源）** | ✅ |

> **wiki.db 是可重建的派生缓存**。多人协作 = `git pull` + `wiki_rebuild.py --incremental`。灾难恢复 = `rm wiki.db; wiki_rebuild.py`。

## AI Agent 行为约定

1. **用户说"更新索引 / 重建索引"等模糊表述** → **默认走增量**（`--incremental`），不要主动走全量
2. **回答前自检**：如果发现刚刚改过 Docs/ 但还没跑 rebuild → 先 `--check`，需要时跑 `--incremental` 再继续
3. **写 wiki 工作流末尾**（teach / ingest / crystallize / evolve-series / create-series 收尾时）→ **主动建议**跑 `--incremental`，由用户确认（不自动跑）
4. **报告输出**：跑完 rebuild 后向用户报告 `pages indexed / edges extracted / skipped / elapsed`
5. **绝不跑 `rm wiki.db`**：除非用户明确说"删库 / drop / reset"
6. **配套查询**：跑完 rebuild 后，引导用户用 `wiki_query.py`（Tier 1）而不是 `query.py`（Tier 0），享受 BM25 排名 + CJK 中文检索的提升

## 反模式

- ❌ 用户说"更新索引"就走全量重建（应是增量）
- ❌ 改 Docs/ 后不跑 rebuild 直接用 `wiki_query.py` 查询（结果可能滞后）
- ❌ 增量构建后未做冒烟查询验证就声称"索引更新完成"
- ❌ Tier 2 向量索引每次跟着 FTS 一起重建（API 成本高，应只在用户明确要语义检索时跑 `--with-vectors`）
- ❌ 把 `wiki.db` 提交进 git（已被 .gitignore 排除，但仍要警惕 `git add -f` 误操作）
