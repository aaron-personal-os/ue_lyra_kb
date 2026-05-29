#!/usr/bin/env python3
"""query.py — LyraStarterGame 知识库一击查询工具 v1.0

⚠️ ★v1.1.1 起 deprecation 软提示★
==================================
推荐改用 `wiki_query.py`（Tier 1 FTS5，2-3× 更快，已集成 anchors/alias/series-prev/next 全部 Tier 0 特性）。
旧 CLI 命令仍可工作，会显示 stderr 警告（设 `PROJECT_WIKI_QUERY_NO_DEPRECATION_WARN=1` 关闭）。
作为模块 `import query` 导入仍稳定（test_query.py 等内部工具继续依赖）。

迁移路径：
    旧: python3 query.py "GAS"                    → 新: python3 wiki_query.py "GAS"
    旧: python3 query.py --id <pid> --no-body     → 新: python3 wiki_query.py --id <pid>
    旧: python3 query.py "ability" --no-alias     → 新: python3 wiki_query.py "ability" --no-alias

把 wiki_query.py 看作"包含 query.py 的所有能力 + Tier 1 BM25 + 自动 Tier 决策"的超集。

==================================

把 ai-playbook §一 的 L1+L2+L3 检索路径折叠成单次工具调用：
    1. 读 Docs/index.md 做轻量预筛（id / description）
    2. 读候选页 frontmatter 拿 anchors / related / prerequisites / tags / series
    3. 沿多类边做 1-hop 图邻居展开：
         - related: 双向边
         - prerequisites: 教程前置依赖（本项目教程系列特色）
         - inverse-prerequisites: 反向（"哪些课依赖我"）
         - same-series: 同教程系列（series + lesson_index 提供的隐式边）
    4. 兜底全文 grep（去 meta 噪音 / --no-body 跳过）
    5. 综合打分 + 输出排序后的候选清单（人类可读 / JSON）

为什么走图谱（不是 grep）
=======================

346 篇文档 / 2533 处 wikilink / 257 处 prerequisites edge：
图密度已超过移植版假设的 sweet spot 下限，多页综合 / 决策性引用 /
查重场景 grep 完全压不住（详见 [[60-topics/...]] §5.3.4）。

针对本项目的定制
================

相对移植版（v0.1）的关键改动：

* 修正 index.md 行格式：本项目用 `- [[id]] - desc`，不带 (type, status, date)
  元组；status / type 改从 frontmatter 拿权威值。
* prerequisites 升级为一类图边（教程系列大量使用，257 处）。
* 同 series + lesson_index 提供"姊妹课程"隐式边。
* anchors 命中：anchors[].path 中的文件名与 token 匹配 → 加分（从代码
  反查 wiki 的关键路径）。
* alias 词表：自动从 .wiki-schema.md 「别名词表」节抽取同义词，
  扩展用户 token 集合（e.g. GAS ↔ Gameplay Ability System）。
* body grep 降噪：跳过 index / log / overview / README 等 meta 文件。
* --series mode：直接看某教程系列的整体图谱。

依赖
====

只用 Python 3.9+ stdlib（项目 UE Python 3.11.8）。复用 wiki_lint.py 的
parse_frontmatter / WIKILINK_RE / strip_code / collect_pages。

用法
====

    # 基础查询（自动展开 alias）
    python query.py "GAS GameplayTag 网络复制"

    # 控制候选数 / 跳过正文 grep / JSON 输出
    python query.py "log rollup" --max-candidates 8 --no-body --json

    # 种子模式（看某 id 的图邻居 / 多类型边都展开）
    python query.py --id 30-tutorials/gas/19-Tag网络复制

    # 系列模式（看一整个教程系列的图簇）
    python query.py --series gas

    # 关闭 alias 扩展（精确查）
    python query.py "ability" --no-alias

退出码
======

    0  正常返回结果（命中 0 条也算正常）
    2  CLI 用法错 / 文件读失败
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# 复用 wiki_lint.py 的 parse_frontmatter / WIKILINK_RE / strip_code / collect_pages
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wiki_lint as L  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[4]
DOCS_DIR = REPO_ROOT / "Docs"
INDEX_MD = DOCS_DIR / "index.md"
SCHEMA_MD = DOCS_DIR / ".wiki-schema.md"

# Body grep 时这些 meta 文件无信息密度，跳过
BODY_GREP_SKIP_IDS = {"index", "log", "overview", "README", ".wiki-schema"}

# 教程目录前缀（用于识别 30-tutorials/<series>/<lesson> 结构）
TUTORIAL_PREFIX = "30-tutorials/"

# 核心 type 的 boost（小幅，避免压过命中信号）
CORE_TYPE_BOOST = {
    "tutorial": 0.4,
    "topic": 0.3,
    "adr": 0.3,
    "guide": 0.2,
    "module": 0.1,
}


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class IndexEntry:
    """index.md 中的一条 wiki 条目（仅 id + description；其它字段从 frontmatter 拿）。"""

    page_id: str
    description: str
    raw_line: str = ""

    def asdict(self) -> dict:
        return asdict(self)


@dataclass
class Candidate:
    """一个查询候选（含评分理由）。"""

    page_id: str
    score: float
    status: str
    type: str
    last_synced: str
    description: str = ""
    anchors: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    series: str = ""
    lesson_index: Optional[int] = None
    inbound: int = 0
    why: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source: str = "index"  # index / tag-only / 1-hop / seed / series

    def asdict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Tokenization & Alias 扩展
# ---------------------------------------------------------------------------

# 切分查询字符串：按 ASCII 空白 / 常见中英标点 / markdown 反引号 / 中文分隔符
TOKEN_SPLIT_RE = re.compile(r"[\s,，;；、\.。:：!！?？\"'`\(\)\[\]【】「」<>《》/\\]+")

# 单字符 token 容易误命中，过滤
TOKEN_MIN_LEN = 2


def tokenize(query: str) -> list[str]:
    """把用户查询拆成关键词列表（小写，去重，过滤过短的）。"""
    raw = TOKEN_SPLIT_RE.split(query.strip())
    out: list[str] = []
    seen: set[str] = set()
    for t in raw:
        t = t.strip().lower()
        if not t:
            continue
        if len(t) < TOKEN_MIN_LEN:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


# 匹配 schema 「别名词表」代码块里 "A = B = C" 形式
ALIAS_LINE_RE = re.compile(r"^([^=#\n]+?(?:\s*=\s*[^=#\n]+?)+)\s*$")


def parse_aliases(schema_path: Path) -> list[set[str]]:
    """从 .wiki-schema.md 「别名词表（Alias Table）」节抽出同义词组。

    返回每组小写 token 的 set 列表，例：
        [{"gas", "gameplay ability system"}, {"lyra", "lyrastartergame", "ue5 示例项目"}, ...]
    """
    if not schema_path.is_file():
        return []
    text = schema_path.read_text(encoding="utf-8")
    # 抓「别名词表」一节里的代码块
    section_re = re.compile(
        r"##\s*别名词表[^\n]*\n(.*?)(?=\n##\s|\Z)",
        re.DOTALL,
    )
    m = section_re.search(text)
    if not m:
        return []
    block_re = re.compile(r"```[^\n]*\n(.*?)\n```", re.DOTALL)
    groups: list[set[str]] = []
    for block in block_re.finditer(m.group(1)):
        for raw in block.group(1).splitlines():
            line = raw.strip()
            if not line or "=" not in line:
                continue
            # 去掉行尾括注，如 "Experience Definition（Lyra 的核心概念）"
            line = re.sub(r"[（(].*?[）)]", "", line).strip()
            if not ALIAS_LINE_RE.match(line):
                continue
            members = {p.strip().lower() for p in line.split("=") if p.strip()}
            if len(members) >= 2:
                groups.append(members)
    return groups


def expand_tokens_with_alias(tokens: list[str], alias_groups: list[set[str]]) -> tuple[list[str], list[str]]:
    """根据 alias 词组扩展 tokens；返回 (扩展后 tokens, 新增的 alias-only tokens)。

    扩展规则：若 token (或 token 是某 alias 的子串) 命中某组 → 把组内其它成员都加入。
    """
    extra: list[str] = []
    seen = set(tokens)
    for tok in tokens:
        for grp in alias_groups:
            hit = any(tok == m or tok in m or m in tok for m in grp)
            if not hit:
                continue
            for m in grp:
                if m and m not in seen:
                    seen.add(m)
                    extra.append(m)
    return tokens + extra, extra


# ---------------------------------------------------------------------------
# index.md 解析（兼容简化格式）
# ---------------------------------------------------------------------------

# 兼容三种行形态：
#   - [[id]] - 描述
#   - [[id]] — 描述
#   - [[id]]                                        （仅 id 无描述也接受）
# 末尾允许有可选 (type, status, YYYY-MM-DD) 元组（当前项目暂未启用，但保留兼容）
INDEX_LINE_RE = re.compile(
    r"^\s*[-*]\s*\[\[([^\]|#]+)\]\]\s*"
    r"(?:[—\-–:：]+\s*(.*?)\s*)?"
    r"(?:\(([^,)]+),\s*([^,)]+),\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\))?\s*$"
)


def parse_index(index_path: Path) -> list[IndexEntry]:
    """解析 Docs/index.md，提取所有 wiki 条目（id + 描述）。

    本项目 index.md 行格式简洁（无 type/status/last_synced 元组），
    这些权威字段统一从 frontmatter 拿。
    """
    if not index_path.is_file():
        return []
    entries: list[IndexEntry] = []
    seen_ids: set[str] = set()
    for raw in index_path.read_text(encoding="utf-8").splitlines():
        # 跳过表头分隔符等噪音
        if "|---" in raw:
            continue
        m = INDEX_LINE_RE.match(raw)
        if not m:
            continue
        page_id = m.group(1).strip()
        if page_id in seen_ids:
            continue
        seen_ids.add(page_id)
        entries.append(IndexEntry(
            page_id=page_id,
            description=(m.group(2) or "").strip(),
            raw_line=raw,
        ))
    return entries


# ---------------------------------------------------------------------------
# Wiki 页加载（frontmatter / 边收集 / inbound 计数）
# ---------------------------------------------------------------------------

def normalize_wikilink_id(target: str) -> str:
    """把 frontmatter 里的 '[[60-topics/foo]]' / '60-topics/foo|alias' 还原为 id。"""
    s = target.strip()
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2]
    s = s.split("|", 1)[0].split("#", 1)[0].strip()
    return s


def collect_listish(page: L.WikiPage, key: str) -> list[str]:
    """从 frontmatter 取一个可能是 list / str / list-of-dict 的字段。"""
    raw = page.fm.get(key, []) or []
    if isinstance(raw, str):
        raw = [raw]
    out: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            # anchors 的 list-of-dict 形态在专用函数里处理
            continue
        nid = normalize_wikilink_id(str(item))
        if nid:
            out.append(nid)
    return out


def collect_related(page: L.WikiPage) -> list[str]:
    return collect_listish(page, "related")


def collect_prerequisites(page: L.WikiPage) -> list[str]:
    return collect_listish(page, "prerequisites")


def collect_anchors(page: L.WikiPage) -> list[str]:
    """anchors 是 list-of-dict（{path: ...}），返回所有 path 字符串。"""
    raw = page.fm.get("anchors", []) or []
    if isinstance(raw, str):
        raw = [raw]
    out: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            p = item.get("path")
            if p:
                out.append(str(p))
        else:
            s = str(item).strip()
            if s:
                out.append(s)
    return out


def collect_tags(page: L.WikiPage) -> list[str]:
    raw = page.fm.get("tags", []) or []
    if isinstance(raw, str):
        return [raw]
    return [str(t) for t in raw if t]


def collect_series(page: L.WikiPage) -> str:
    val = page.fm.get("series", "")
    return str(val).strip() if val else ""


def collect_lesson_index(page: L.WikiPage) -> Optional[int]:
    val = page.fm.get("lesson_index", None)
    if val is None or val == "":
        return None
    try:
        return int(str(val).split()[0])
    except (ValueError, AttributeError):
        return None


def build_inbound_counts(all_pages: list[L.WikiPage]) -> dict[str, int]:
    """统计每个 page_id 被多少其它页 wikilink 引用（去 code block）。"""
    counts: dict[str, int] = {}
    for src in all_pages:
        clean = L.strip_code(src.text)
        for m in L.WIKILINK_RE.finditer(clean):
            tid = normalize_wikilink_id(m.group(1))
            if tid == src.page_id:
                continue
            counts[tid] = counts.get(tid, 0) + 1
    return counts


def build_inverse_prerequisites(all_pages: list[L.WikiPage]) -> dict[str, list[str]]:
    """构建反向 prerequisites 索引：tid → [依赖 tid 的页]。"""
    inv: dict[str, list[str]] = {}
    for p in all_pages:
        for pre in collect_prerequisites(p):
            inv.setdefault(pre, []).append(p.page_id)
    return inv


def build_series_index(all_pages: list[L.WikiPage]) -> dict[str, list[L.WikiPage]]:
    """按 frontmatter `series` 字段分组（仅对 30-tutorials/<series>/* 有意义）。"""
    idx: dict[str, list[L.WikiPage]] = {}
    for p in all_pages:
        s = collect_series(p)
        if s:
            idx.setdefault(s, []).append(p)
    # 同系列按 lesson_index 升序排（None 排末尾）
    for s in idx:
        idx[s].sort(key=lambda pg: (collect_lesson_index(pg) is None, collect_lesson_index(pg) or 0, pg.page_id))
    return idx


# ---------------------------------------------------------------------------
# 评分算法
# ---------------------------------------------------------------------------

# 各信号的权重（数字相对关系比绝对值重要）
W_ID_HIT = 3.0          # id 命中（最强）
W_DESC_HIT = 1.5        # index.md description 命中
W_TAG_HIT = 1.0         # frontmatter tag 命中
W_TYPE_HIT = 0.6        # type 名命中（如 query="adr" → 加分给所有 type=adr）
W_ANCHOR_HIT = 1.2      # anchors path 文件名命中（关键：从代码反查 wiki）
W_BODY_HIT_PER = 0.5    # body grep 命中（每条 +0.5，封顶 5 条）
W_BODY_HIT_CAP = 5
W_INBOUND_PER = 0.1     # 每个入边 +0.1，封顶 10 个
W_INBOUND_CAP = 10
W_ALIAS_DAMP = 0.6      # alias 扩展出的 token 命中权重打折（避免误命中放大）

# 状态修正系数
STATUS_MULTIPLIER = {
    "current": 1.0,
    "draft": 0.7,
    "stale": 0.5,
    "deprecated": 0.2,
    "": 1.0,
}


def _hits_in(tokens: list[str], haystack: str, alias_set: set[str]) -> tuple[float, list[str]]:
    """统计 tokens 在 haystack 中的命中（alias-only token 的命中权重打折）。

    返回 (分数, 命中 token 列表)。
    """
    hits: list[str] = []
    score = 0.0
    for t in tokens:
        if not t or t not in haystack:
            continue
        weight = W_ALIAS_DAMP if t in alias_set else 1.0
        hits.append(t)
        score += weight
    return score, hits


def score_against_index_entry(
    entry: IndexEntry,
    tokens: list[str],
    alias_set: set[str],
) -> tuple[float, list[str]]:
    """按 index.md 的 id + description 字段打分。返回 (score, why_list)。"""
    score = 0.0
    why: list[str] = []

    pid_low = entry.page_id.lower()
    desc_low = entry.description.lower()

    s, hits = _hits_in(tokens, pid_low, alias_set)
    if hits:
        score += W_ID_HIT * s
        why.append(f"id-hit:{','.join(hits)}")

    s, hits = _hits_in(tokens, desc_low, alias_set)
    if hits:
        score += W_DESC_HIT * s
        why.append(f"desc-hit:{','.join(hits)}")

    return score, why


def score_against_page(
    page: L.WikiPage,
    tokens: list[str],
    alias_set: set[str],
) -> tuple[float, list[str]]:
    """对已加载 wiki 页做 tag / anchors / type / core-type-boost 加分。"""
    score = 0.0
    why: list[str] = []

    # tags
    tags_text = " ".join(t.lower() for t in collect_tags(page))
    if tags_text:
        s, hits = _hits_in(tokens, tags_text, alias_set)
        if hits:
            score += W_TAG_HIT * s
            why.append(f"tag-hit:{','.join(hits)}")

    # anchors path 文件名（关键：用户查 "LyraCharacter" 应能命中 ALyraCharacter.md）
    anchor_text = " ".join(a.lower() for a in collect_anchors(page))
    if anchor_text:
        s, hits = _hits_in(tokens, anchor_text, alias_set)
        if hits:
            score += W_ANCHOR_HIT * s
            why.append(f"anchor-hit:{','.join(hits)}")

    # type 精确匹配（query=adr → 给 type=adr 的页加分）
    type_low = (page.fm.get("type") or "").lower()
    type_hits = [t for t in tokens if t and t == type_low]
    if type_hits:
        score += W_TYPE_HIT * len(type_hits)
        why.append(f"type-hit:{','.join(type_hits)}")

    # 核心 type 小幅 boost（仅在已有命中信号时生效，避免无关 tutorial 凭 boost+inbound 霸榜）
    # 修复：原实现无条件 +0.4，叠加 inbound(≤1.0) 形成 1.4 分"虚假底线"，挤掉真正命中正文的文档
    boost = CORE_TYPE_BOOST.get(type_low, 0.0)
    if boost > 0 and score > 0:
        score += boost
        # 不写入 why（噪音），只生效

    return score, why


def status_warning(status: str) -> Optional[str]:
    if status == "stale":
        return "status=stale (re-verify before citing)"
    if status == "deprecated":
        return "status=deprecated (do not cite without warning)"
    if status == "draft":
        return "status=draft (work in progress)"
    return None


# ---------------------------------------------------------------------------
# 主查询流程
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    query: str
    tokens: list[str]
    alias_extra: list[str]              # 经 alias 扩展新加入的 token
    candidates: list[Candidate]
    neighbors: list[Candidate]          # 1-hop 邻居（多类型边）
    body_matches: list[dict]            # body-only 命中
    warnings: list[str]                 # 全局警告
    mode: str = "keyword"               # keyword / seed / series
    series_name: str = ""

    def asdict(self) -> dict:
        return {
            "query": self.query,
            "tokens": self.tokens,
            "alias_extra": self.alias_extra,
            "candidates": [c.asdict() for c in self.candidates],
            "neighbors": [c.asdict() for c in self.neighbors],
            "body_matches": self.body_matches,
            "warnings": self.warnings,
            "mode": self.mode,
            "series_name": self.series_name,
        }


def _build_candidate(
    pid: str,
    raw_score: float,
    why: list[str],
    page: Optional[L.WikiPage],
    entry: Optional[IndexEntry],
    inbound: int,
    source: str,
) -> Candidate:
    """统一组装一个 Candidate（含 status 修正、warning）。"""
    # status 权威值：frontmatter 优先（本项目 index 不带 status）
    status = (page.fm.get("status") if page else "") or ""
    mult = STATUS_MULTIPLIER.get(status, 1.0)
    score_with_inb = raw_score + min(inbound, W_INBOUND_CAP) * W_INBOUND_PER
    final_score = score_with_inb * mult

    warns: list[str] = []
    sw = status_warning(status)
    if sw:
        warns.append(sw)

    return Candidate(
        page_id=pid,
        score=round(final_score, 2),
        status=status or "?",
        type=(page.fm.get("type") if page else "") or "?",
        last_synced=(page.fm.get("last_synced") if page else "") or "",
        description=(entry.description if entry else "") or (page.fm.get("description") if page else "") or "",
        anchors=collect_anchors(page) if page else [],
        related=collect_related(page) if page else [],
        prerequisites=collect_prerequisites(page) if page else [],
        tags=collect_tags(page) if page else [],
        series=collect_series(page) if page else "",
        lesson_index=collect_lesson_index(page) if page else None,
        inbound=inbound,
        why=why,
        warnings=warns,
        source=source,
    )


def _expand_neighbors(
    seed_ids: set[str],
    pages_by_id: dict[str, L.WikiPage],
    entries_by_id: dict[str, IndexEntry],
    inbound_counts: dict[str, int],
    inv_prereq: dict[str, list[str]],
    series_index: dict[str, list[L.WikiPage]],
) -> list[Candidate]:
    """从 seed_ids 出发做多类型 1-hop 邻居展开。

    展开的边类型：
      - related: 双向边
      - prerequisites: 教程前置（A 依赖 B → B 是 A 的邻居）
      - inverse-prerequisites: 反向（A 是 B 的前置 → B 是 A 的邻居）
      - same-series: 同 series 相邻 lesson_index（前后各一）
    """
    out: dict[str, tuple[Candidate, str]] = {}  # nid → (Candidate, via-edge-label)

    def add_neighbor(nid: str, via_pid: str, edge: str) -> None:
        if nid in seed_ids or nid in out:
            return
        npage = pages_by_id.get(nid)
        nentry = entries_by_id.get(nid)
        if not npage and not nentry:
            return
        c = _build_candidate(
            pid=nid,
            raw_score=0.0,  # 邻居不参与排序
            why=[f"{edge} from [[{via_pid}]]"],
            page=npage,
            entry=nentry,
            inbound=inbound_counts.get(nid, 0),
            source="1-hop",
        )
        out[nid] = (c, edge)

    for sid in seed_ids:
        spage = pages_by_id.get(sid)
        # related 边
        if spage:
            for nid in collect_related(spage):
                add_neighbor(nid, sid, "related")
            # prerequisites 边（A 依赖 B → B 是邻居）
            for nid in collect_prerequisites(spage):
                add_neighbor(nid, sid, "prereq")
        # inverse-prerequisites 边（B 依赖 A → B 是邻居）
        for nid in inv_prereq.get(sid, []):
            add_neighbor(nid, sid, "needed-by")
        # same-series 边（前后相邻课程）
        if spage:
            series = collect_series(spage)
            li = collect_lesson_index(spage)
            if series and li is not None and series in series_index:
                ordered = series_index[series]
                for i, p in enumerate(ordered):
                    if p.page_id != sid:
                        continue
                    if i > 0:
                        add_neighbor(ordered[i - 1].page_id, sid, "series-prev")
                    if i + 1 < len(ordered):
                        add_neighbor(ordered[i + 1].page_id, sid, "series-next")
                    break

    # 排序：先按 inbound 降序，再按 id
    rows = list(out.values())
    rows.sort(key=lambda x: (-x[0].inbound, x[0].page_id))
    return [c for c, _ in rows]


def grep_body(
    tokens: list[str],
    skip_ids: set[str],
    all_pages: list[L.WikiPage],
    *,
    max_files: int = 8,
) -> list[dict]:
    """对所有 wiki 页正文做关键词全文搜索（去 code block / 跳过 meta 文件）。"""
    out: list[dict] = []
    for page in all_pages:
        if page.page_id in skip_ids:
            continue
        if page.page_id in BODY_GREP_SKIP_IDS:
            continue
        clean = L.strip_code(page.text)
        body_low = clean.lower()
        match_lines: list[int] = []
        match_count = 0
        all_text_lines = page.text.splitlines()
        for token in tokens:
            if token not in body_low:
                continue
            for i, line in enumerate(all_text_lines, 1):
                if token in line.lower() and i not in match_lines:
                    match_lines.append(i)
                    if len(match_lines) >= 5:
                        break
            match_count += body_low.count(token)
        if match_count > 0:
            out.append({
                "page_id": page.page_id,
                "matches": match_count,
                "lines": sorted(match_lines)[:5],
            })
    out.sort(key=lambda d: -d["matches"])
    return out[:max_files]


def run_query(
    query: str,
    *,
    max_candidates: int = 5,
    body_search: bool = True,
    seed_id: Optional[str] = None,
    series_name: Optional[str] = None,
    use_alias: bool = True,
) -> QueryResult:
    """主查询入口。

    三种模式（互斥）：
      - keyword: 默认，按 query 字符串关键词查
      - seed_id: 直接以某 id 为种子，看其图邻居
      - series_name: 列出某教程系列的整个图簇
    """
    # ----- 加载 -----
    entries = parse_index(INDEX_MD)
    entries_by_id: dict[str, IndexEntry] = {e.page_id: e for e in entries}
    all_pages = L.collect_pages(DOCS_DIR)
    pages_by_id: dict[str, L.WikiPage] = {p.page_id: p for p in all_pages}
    inbound_counts = build_inbound_counts(all_pages)
    inv_prereq = build_inverse_prerequisites(all_pages)
    series_index = build_series_index(all_pages)

    # ----- 模式分派 -----
    if series_name:
        return _run_series_mode(
            series_name, all_pages, pages_by_id, entries_by_id,
            inbound_counts, inv_prereq, series_index,
        )

    if seed_id:
        return _run_seed_mode(
            seed_id, pages_by_id, entries_by_id,
            inbound_counts, inv_prereq, series_index,
        )

    # ----- 默认 keyword 模式 -----
    tokens = tokenize(query)
    alias_extra: list[str] = []
    if use_alias and tokens:
        alias_groups = parse_aliases(SCHEMA_MD)
        tokens, alias_extra = expand_tokens_with_alias(tokens, alias_groups)
    alias_set = set(alias_extra)

    # 1. L1: 基于 index.md 的 id+desc 打分
    cand_scores: dict[str, tuple[float, list[str]]] = {}
    for e in entries:
        s, why = score_against_index_entry(e, tokens, alias_set)
        if s > 0:
            cand_scores[e.page_id] = (s, why)

    # 2. L2: 对所有 wiki 页加 tag/anchors/type 加分（即便没出现在 index 候选里）
    for page in all_pages:
        s_extra, why_extra = score_against_page(page, tokens, alias_set)
        if s_extra <= 0:
            continue
        if page.page_id in cand_scores:
            cur_s, cur_why = cand_scores[page.page_id]
            cand_scores[page.page_id] = (cur_s + s_extra, cur_why + why_extra)
        else:
            cand_scores[page.page_id] = (s_extra, why_extra)

    # 3. L3: body grep —— 既用于"BODY-ONLY MATCHES"展示，也回灌候选评分
    # 修复：原实现 body 命中只显示不计分，导致正文重度命中文档被纯 boost 候选挤出 TOP
    body_matches_full: list[dict] = []
    if body_search and tokens:
        body_matches_full = grep_body(tokens, set(), all_pages, max_files=50)
        for m in body_matches_full:
            pid = m["page_id"]
            body_score = min(m["matches"], W_BODY_HIT_CAP) * W_BODY_HIT_PER
            body_why = f"body-hit:{m['matches']}@{','.join(f'L{i}' for i in m['lines'])}"
            if pid in cand_scores:
                cur_s, cur_why = cand_scores[pid]
                cand_scores[pid] = (cur_s + body_score, cur_why + [body_why])
            else:
                cand_scores[pid] = (body_score, [body_why])

    # 4. 组装 + 排序
    candidates: list[Candidate] = []
    for pid, (raw_score, why) in cand_scores.items():
        page = pages_by_id.get(pid)
        entry = entries_by_id.get(pid)
        c = _build_candidate(
            pid=pid,
            raw_score=raw_score,
            why=why,
            page=page,
            entry=entry,
            inbound=inbound_counts.get(pid, 0),
            source="index" if entry else "tag-only",
        )
        candidates.append(c)

    # 排序：分数降序；并列时教程按 lesson_index 升序，其余按 id
    def _sort_key(c: Candidate) -> tuple:
        li = c.lesson_index if c.lesson_index is not None else 9999
        return (-c.score, li, c.page_id)

    candidates.sort(key=_sort_key)
    top_candidates = candidates[:max_candidates]

    # 5. 1-hop 邻居展开（多类型边）
    seed_ids = {c.page_id for c in top_candidates}
    neighbors = _expand_neighbors(
        seed_ids, pages_by_id, entries_by_id,
        inbound_counts, inv_prereq, series_index,
    )

    # 6. BODY-ONLY 展示：仅显示既未进 TOP 也未进邻居的 body 命中
    already = seed_ids | {n.page_id for n in neighbors}
    body_matches: list[dict] = [m for m in body_matches_full if m["page_id"] not in already][:8]

    # 7. 全局警告
    global_warnings: list[str] = []
    for c in top_candidates:
        if c.status in ("stale", "deprecated"):
            global_warnings.append(f"[[{c.page_id}]] is {c.status} — do not cite without re-verify")

    return QueryResult(
        query=query,
        tokens=tokens,
        alias_extra=alias_extra,
        candidates=top_candidates,
        neighbors=neighbors,
        body_matches=body_matches,
        warnings=global_warnings,
        mode="keyword",
    )


def _run_seed_mode(
    seed_id: str,
    pages_by_id: dict[str, L.WikiPage],
    entries_by_id: dict[str, IndexEntry],
    inbound_counts: dict[str, int],
    inv_prereq: dict[str, list[str]],
    series_index: dict[str, list[L.WikiPage]],
) -> QueryResult:
    """种子模式：以 seed_id 为唯一候选，展开多类型 1-hop 邻居。"""
    page = pages_by_id.get(seed_id)
    entry = entries_by_id.get(seed_id)
    seed_cand = _build_candidate(
        pid=seed_id,
        raw_score=10.0,
        why=["seed-id"],
        page=page,
        entry=entry,
        inbound=inbound_counts.get(seed_id, 0),
        source="seed",
    )
    # 即便 page 不存在仍允许（提示用户）
    if not page and not entry:
        seed_cand.warnings.append(f"seed id [[{seed_id}]] not found in Docs/ or index.md")

    neighbors = _expand_neighbors(
        {seed_id}, pages_by_id, entries_by_id,
        inbound_counts, inv_prereq, series_index,
    )
    return QueryResult(
        query=f"--id {seed_id}",
        tokens=[],
        alias_extra=[],
        candidates=[seed_cand],
        neighbors=neighbors,
        body_matches=[],
        warnings=[],
        mode="seed",
    )


def _run_series_mode(
    series_name: str,
    all_pages: list[L.WikiPage],
    pages_by_id: dict[str, L.WikiPage],
    entries_by_id: dict[str, IndexEntry],
    inbound_counts: dict[str, int],
    inv_prereq: dict[str, list[str]],
    series_index: dict[str, list[L.WikiPage]],
) -> QueryResult:
    """系列模式：列出指定教程系列的所有课，按 lesson_index 排序，附 1-hop 跨系列邻居。"""
    members = series_index.get(series_name, [])
    candidates: list[Candidate] = []
    for p in members:
        c = _build_candidate(
            pid=p.page_id,
            raw_score=0.0,
            why=[f"series:{series_name}"],
            page=p,
            entry=entries_by_id.get(p.page_id),
            inbound=inbound_counts.get(p.page_id, 0),
            source="series",
        )
        candidates.append(c)

    seed_ids = {c.page_id for c in candidates}
    # 系列模式邻居：仅展开 related + prerequisites 跨系列的（series-prev/next 已在内部不需要）
    neighbors_full = _expand_neighbors(
        seed_ids, pages_by_id, entries_by_id,
        inbound_counts, inv_prereq, series_index,
    )
    # 过滤掉同系列邻居（避免噪音；用户已经看到全部成员了）
    neighbors = [n for n in neighbors_full if n.series != series_name]

    warnings: list[str] = []
    if not members:
        warnings.append(f"series '{series_name}' not found (查 Docs/30-tutorials/<series>/_series.yaml)")

    return QueryResult(
        query=f"--series {series_name}",
        tokens=[],
        alias_extra=[],
        candidates=candidates,
        neighbors=neighbors,
        body_matches=[],
        warnings=warnings,
        mode="series",
        series_name=series_name,
    )


# ---------------------------------------------------------------------------
# 输出格式化
# ---------------------------------------------------------------------------

def _supports_color() -> bool:
    return sys.stdout.isatty() and sys.platform != "win32"


def _c(code: str, text: str) -> str:
    if not _supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def _bold(s: str) -> str:
    return _c("1", s)


def _dim(s: str) -> str:
    return _c("2", s)


def _yellow(s: str) -> str:
    return _c("33", s)


def _red(s: str) -> str:
    return _c("31", s)


def _green(s: str) -> str:
    return _c("32", s)


def _status_label(status: str) -> str:
    if status == "current":
        return _green(status)
    if status == "draft":
        return _yellow(status)
    if status == "stale":
        return _yellow(f"⚠ {status}")
    if status == "deprecated":
        return _red(f"✗ {status}")
    return status


def format_candidate(c: Candidate, idx: int, *, show_score: bool = True) -> str:
    lines: list[str] = []
    star = "★ " if idx == 1 else "  "
    head = f"[{idx}] {star}[[{c.page_id}]]"
    if show_score:
        lines.append(_bold(head) + f"   {_dim('score=')}{c.score}")
    else:
        lines.append(_bold(head))
    meta = (
        f"     type={c.type}   status={_status_label(c.status)}   "
        f"last_synced={c.last_synced}   inbound={c.inbound}"
    )
    if c.series:
        li = f"#{c.lesson_index}" if c.lesson_index is not None else ""
        meta += f"   series={c.series}{li}"
    lines.append(meta)
    if c.description:
        lines.append(f"     desc: {c.description}")
    if c.anchors:
        head_anchor = c.anchors[0]
        rest = f" (+{len(c.anchors) - 1} more)" if len(c.anchors) > 1 else ""
        lines.append(f"     anchors: {head_anchor}{rest}")
    if c.related:
        head_rel = ", ".join(f"[[{r}]]" for r in c.related[:3])
        rest = f" (+{len(c.related) - 3} more)" if len(c.related) > 3 else ""
        lines.append(f"     related: {head_rel}{rest}")
    if c.prerequisites:
        head_pre = ", ".join(f"[[{r}]]" for r in c.prerequisites[:3])
        rest = f" (+{len(c.prerequisites) - 3} more)" if len(c.prerequisites) > 3 else ""
        lines.append(f"     prereq:  {head_pre}{rest}")
    if c.why:
        lines.append(_dim(f"     why: {'; '.join(c.why)}"))
    for w in c.warnings:
        lines.append(_yellow(f"     ⚠ {w}"))
    return "\n".join(lines)


def render_human(result: QueryResult) -> str:
    out: list[str] = []

    if result.mode == "seed":
        out.append(_bold(f"Seed mode: {result.query!r}"))
    elif result.mode == "series":
        out.append(_bold(f"Series mode: {result.series_name!r}  ({len(result.candidates)} 课)"))
    else:
        out.append(_bold(f"Query: {result.query!r}"))
        if result.tokens:
            out.append(f"Tokens: {', '.join(result.tokens)}")
        if result.alias_extra:
            out.append(_dim(f"Alias-expanded: {', '.join(result.alias_extra)}"))
    out.append("")

    if not result.candidates:
        out.append(_yellow("⚠ No candidate hit. Falling back to body grep below."))
    else:
        if result.mode == "series":
            out.append(_bold(f"═══ {result.series_name.upper()} 系列课程 ═══"))
            for i, c in enumerate(result.candidates, 1):
                out.append(format_candidate(c, i, show_score=False))
                out.append("")
        else:
            out.append(_bold(f"═══ TOP {len(result.candidates)} CANDIDATES ═══"))
            for i, c in enumerate(result.candidates, 1):
                out.append(format_candidate(c, i))
                out.append("")

    if result.neighbors:
        out.append(_bold(f"═══ 1-HOP NEIGHBORS ({len(result.neighbors)}) ═══"))
        out.append(_dim("(候选页的 related / prereq / 同系列邻居，未直接命中关键词)"))
        for n in result.neighbors[:12]:
            warn_tag = ""
            if n.warnings:
                warn_tag = _yellow(f"  ⚠ {n.status}")
            edge = ""
            if n.why and n.why[0].startswith(("series-", "needed-by", "prereq", "related")):
                edge = _dim(f" via:{n.why[0].split()[0]}")
            out.append(
                f"  - [[{n.page_id}]]  ({_status_label(n.status)}, {n.type}, "
                f"inbound={n.inbound}){edge}{warn_tag}"
            )
            if n.description:
                out.append(_dim(f"      {n.description}"))
        out.append("")

    if result.body_matches:
        out.append(_bold(f"═══ BODY-ONLY MATCHES ({len(result.body_matches)}) ═══"))
        out.append(_dim("(被 grep 命中但 index 没强候选；可能是边缘提及或 index 漏录)"))
        for m in result.body_matches:
            line_str = ",".join(f"L{i}" for i in m["lines"])
            out.append(f"  - {m['page_id']}  ({m['matches']} matches @ {line_str})")
        out.append("")

    if result.warnings:
        out.append(_bold(_yellow("═══ [WARN] GLOBAL WARNINGS ═══")))
        for w in result.warnings:
            out.append(_yellow(f"  - {w}"))
        out.append("")

    if result.candidates and result.mode == "keyword":
        top = result.candidates[0]
        bits = [f"[HINT] 建议优先读 [[{top.page_id}]]"]
        if top.related or top.prerequisites:
            bits.append("沿 related / prereq 看图邻居")
        if top.series:
            bits.append(f"或跑 query.py --series {top.series} 看整套系列")
        out.append(_dim(" + ".join(bits)))

    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="query.py",
        description="LyraStarterGame 知识库一击查询（图谱优先 + grep 兜底）。",
    )
    ap.add_argument(
        "query", nargs="?", default="",
        help="查询关键词（可空格分隔多关键词，支持中英混合 + alias 扩展）",
    )
    ap.add_argument(
        "--id", dest="seed_id", default=None,
        help="种子 id 模式：跳过关键词搜索，直接看该 id 的多类型 1-hop 邻居",
    )
    ap.add_argument(
        "--series", dest="series_name", default=None,
        help="系列模式：列出某教程系列的全部课程 + 跨系列邻居（如 gas / network-sync）",
    )
    ap.add_argument(
        "--max-candidates", type=int, default=5,
        help="返回 top N 候选 (default: 5)",
    )
    ap.add_argument(
        "--no-body", action="store_true",
        help="跳过正文 grep（更快，但可能漏掉 index 没收录的页）",
    )
    ap.add_argument(
        "--no-alias", action="store_true",
        help="关闭别名词表扩展（默认开启，用 schema 里的同义词组）",
    )
    ap.add_argument(
        "--json", action="store_true",
        help="JSON 输出（便于 Agent 解析 / 喂下游工具）",
    )
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    ap = build_argparser()
    args = ap.parse_args(argv)

    # ★v1.1.1★ Deprecation 提示：CLI 入口推荐用 wiki_query.py（Tier 1 FTS5 默认更快更准）
    # 不阻断执行；可通过环境变量 PROJECT_WIKI_QUERY_NO_DEPRECATION_WARN=1 关闭
    import os
    if not os.environ.get("PROJECT_WIKI_QUERY_NO_DEPRECATION_WARN"):
        print(
            "[query.py deprecation] 推荐改用 wiki_query.py（Tier 1 FTS5，2-3× 更快，含 v1.1 anchors/alias/series 集成）。\n"
            "[query.py deprecation] 旧命令仍可工作（自动转发到 Tier 0 引擎）。设置 PROJECT_WIKI_QUERY_NO_DEPRECATION_WARN=1 关闭此提示。",
            file=sys.stderr,
        )

    if not args.query and not args.seed_id and not args.series_name:
        ap.error("请提供查询关键词、--id <page_id> 或 --series <name>")
        return 2

    # 互斥模式校验
    mode_count = sum(1 for x in (args.query, args.seed_id, args.series_name) if x)
    if args.seed_id and args.series_name:
        ap.error("--id 与 --series 互斥")
        return 2

    try:
        result = run_query(
            args.query,
            max_candidates=args.max_candidates,
            body_search=not args.no_body,
            seed_id=args.seed_id,
            series_name=args.series_name,
            use_alias=not args.no_alias,
        )
    except FileNotFoundError as e:
        print(f"[query.py] error: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.asdict(), ensure_ascii=False, indent=2))
    else:
        print(render_human(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
