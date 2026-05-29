#!/usr/bin/env python3
"""wiki_query.py — LyraStarterGame project-wiki Tier 1/2 查询引擎

移植自 ProjectWiki v2.0（详见 reference/retrieval-engine-design.md）。

纯 Python 3.9+ stdlib，无外部依赖。
向量搜索需要 `pip install sqlite-vec`（可选）。

  Tier 1（推荐）: 当 .cache/wiki.db 存在时，使用 SQLite FTS5 BM25 排序 + 图遍历
  Tier 2（语义）: 当 db 已构建向量时（--with-vectors），BM25 + Vector + RRF 融合
  Tier 0（回退）: 委托给同目录下的 query.py（已有的图谱+grep 引擎）

本项目特化点
============

* 顶层目录是 category（00-meta / 30-tutorials / ...），用 `--category` 替代源方案的 `--brain`
* domain（page_id 第二段）用于教程系列定位（如 30-tutorials/gas/...）
* `--series` 模式：列出指定教程系列的全部课程（按 lesson_index 排序）
* 邻居展开支持三种边：related / prerequisite / wikilink

用法
====

    # 基础查询（自动选 Tier）
    python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "GameplayAbility"

    # 限定 category / domain（软降权，不硬过滤）
    python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "ability" \\
        --category 30-tutorials --domain gas

    # 种子模式
    python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py \\
        --id 30-tutorials/gas/19-Tag网络复制

    # 教程系列模式（按 lesson_index 排序展示整套）
    python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py --series gas

    # 强制指定引擎
    python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "ability" --engine sqlite
    python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "ability" --engine hybrid

    # JSON 输出
    python3 .codebuddy/skills/project-wiki/scripts/wiki_query.py "ability" --json

退出码
======

    0  正常返回
    2  CLI 用法错误
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import struct
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# 向量支持（可选依赖）
# ---------------------------------------------------------------------------

_SQLITE_VEC_AVAILABLE = False
try:
    import sqlite_vec  # type: ignore
    _SQLITE_VEC_AVAILABLE = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
REPO_ROOT = SKILL_DIR.parents[2]
DOCS_DIR = REPO_ROOT / "Docs"
SCHEMA_MD = DOCS_DIR / ".wiki-schema.md"
CONFIG_PATH = SKILL_DIR / "config.yaml"
DEFAULT_DB_PATH = SKILL_DIR / ".cache" / "wiki.db"

VALID_CATEGORIES = {
    "00-meta", "10-architecture", "20-modules", "30-tutorials",
    "40-runbooks", "50-references", "60-decisions", "70-topics",
    "80-gotchas", "90-snapshots",
}


# ---------------------------------------------------------------------------
# 评分常量（与 wiki_rebuild.py 保持一致）
# ---------------------------------------------------------------------------

# 状态修正系数（Tier 0/1/2 共用）
STATUS_MULTIPLIER = {
    "current": 1.0,
    "draft": 0.7,
    "stale": 0.5,
    "deprecated": 0.2,
    "": 1.0,
}

# 不匹配惩罚（仅用户传 --category / --domain 时生效）
CATEGORY_MISMATCH_PENALTY = 0.5
DOMAIN_MISMATCH_PENALTY = 0.7

# ★v1.1★ alias-only 命中软降权：仅由 alias 扩展引入的 token 命中页面 × 0.6
ALIAS_DAMP = 0.6

# ★v1.1★ Anchor-hit bonus 系数：anchors_text 列单独命中的页给后置加分
# 用于"代码反查 wiki"场景（查 LyraCharacter 应 Top-1 命中 [[20-modules/cpp/ALyraCharacter]]）
ANCHOR_HIT_BONUS = 1.5

# ★v1.1★ Page-id full-token bonus：长 token (≥6 字符) 完整出现在 page_id 路径中时给强加分
# 例：query="LyraCharacter" → "lyracharacter" 在 "20-modules/cpp/alyracharacter" 中 → +5.0
# 这模拟用户的精确意图："我要找名字含 X 的页"
ID_FULLTOKEN_BONUS = 5.0

# Vector 路位置感知加权（Tier 2.3）
VECTOR_POSITION_BOOST = {
    0: 1.2,   # summary + body 前段
    1: 0.8,   # body 后段
}
VECTOR_POSITION_DEFAULT = 1.0


# ---------------------------------------------------------------------------
# CJK 预处理
# ---------------------------------------------------------------------------

_CJK_RE = re.compile(r"([一-鿿㐀-䶿豈-﫿])")


def cjk_space_insert(text: str) -> str:
    if not text:
        return text
    result = _CJK_RE.sub(r" \1 ", text)
    result = re.sub(r" +", " ", result)
    return result.strip()


def cjk_space_strip(text: str) -> str:
    """还原 CJK 预处理：去掉中文字符之间的空格（用于展示）。"""
    if not text:
        return text
    result = re.sub(r"(?<=[一-鿿㐀-䶿豈-﫿]) (?=[一-鿿㐀-䶿豈-﫿])", "", text)
    result = re.sub(r"(?<=[一-鿿㐀-䶿豈-﫿]) (?=[。，、；：！？（）【】「」《》])", "", result)
    result = re.sub(r"(?<=[。，、；：！？（）【】「」《》]) (?=[一-鿿㐀-䶿豈-﫿])", "", result)
    result = re.sub(r"(?<=[一-鿿㐀-䶿豈-﫿]) (?=[/,.])", "", result)
    result = re.sub(r"(?<=[/,.]) (?=[一-鿿㐀-䶿豈-﫿])", "", result)
    return result


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    page_id: str
    score: float
    status: str
    type: str
    category: str = ""
    domain: str = ""
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    series: str = ""
    lesson_index: int = -1
    inbound: int = 0
    why: list[str] = field(default_factory=list)
    source: str = "search"
    warnings: list[str] = field(default_factory=list)

    def asdict(self) -> dict:
        return asdict(self)


@dataclass
class QueryResult:
    query: str
    tokens: list[str]
    candidates: list[Candidate]
    neighbors: list[Candidate]
    suggestion: str = ""
    tier: str = "?"
    mode: str = "keyword"     # keyword | seed | series
    alias_extra: list[str] = field(default_factory=list)  # ★v1.1★ alias 扩展进来的 token

    def asdict(self) -> dict:
        return {
            "query": self.query,
            "tokens": self.tokens,
            "candidates": [c.asdict() for c in self.candidates],
            "neighbors": [c.asdict() for c in self.neighbors],
            "suggestion": self.suggestion,
            "tier": self.tier,
            "mode": self.mode,
            "alias_extra": self.alias_extra,
        }


# ---------------------------------------------------------------------------
# 配置加载（极简 YAML）
# ---------------------------------------------------------------------------

def _parse_simple_yaml(text: str) -> dict:
    result: dict = {}
    stack: list[tuple[dict, int]] = [(result, -1)]
    for line in text.splitlines():
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        content = stripped.lstrip()
        if content.startswith("- "):
            continue
        m = re.match(r'^([\w_-]+):\s*(.*)', content)
        if not m:
            continue
        key = m.group(1)
        val_str = m.group(2).strip()
        while len(stack) > 1 and stack[-1][1] >= indent:
            stack.pop()
        parent = stack[-1][0]
        if val_str == "" or val_str.startswith("#"):
            new_dict: dict = {}
            parent[key] = new_dict
            stack.append((new_dict, indent))
            continue
        if val_str.startswith('"'):
            end_q = val_str.find('"', 1)
            val_str = val_str[1:end_q] if end_q > 0 else val_str[1:]
        elif val_str.startswith("'"):
            end_q = val_str.find("'", 1)
            val_str = val_str[1:end_q] if end_q > 0 else val_str[1:]
        else:
            if "#" in val_str:
                val_str = val_str.split("#")[0].strip()
        try:
            if "." in val_str:
                parent[key] = float(val_str)
            else:
                parent[key] = int(val_str)
        except ValueError:
            if val_str.lower() in ("true", "yes"):
                parent[key] = True
            elif val_str.lower() in ("false", "no"):
                parent[key] = False
            elif val_str.startswith("[") and val_str.endswith("]"):
                inner = val_str[1:-1]
                parent[key] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
            else:
                parent[key] = val_str
    return result


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return _parse_simple_yaml(CONFIG_PATH.read_text(encoding="utf-8"))


def resolve_db_path(config: dict, override: Optional[str] = None) -> Path:
    if override:
        p = Path(override)
        return p if p.is_absolute() else (REPO_ROOT / p)
    rel = config.get("paths", {}).get("db") or ".codebuddy/skills/project-wiki/.cache/wiki.db"
    return REPO_ROOT / rel


# ---------------------------------------------------------------------------
# Tokenization（CamelCase + 中英混合）
# ---------------------------------------------------------------------------

TOKEN_SPLIT_RE = re.compile(r"[\s,，;；、\.。:：!！?？\"'`\(\)\[\]【】「」<>《》/\\-]+")
CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
TOKEN_MIN_LEN = 2


def tokenize(query: str) -> list[str]:
    """分词：标点切分 + CamelCase 拆分 + 小写化 + 去重 + 短 token 过滤。"""
    raw_parts = TOKEN_SPLIT_RE.split(query.strip())
    out: list[str] = []
    seen: set[str] = set()

    def _add(t: str) -> None:
        t = t.lower()
        if len(t) < TOKEN_MIN_LEN or t in seen:
            return
        seen.add(t)
        out.append(t)

    for part in raw_parts:
        if not part:
            continue
        _add(part)
        sub_parts = CAMEL_SPLIT_RE.split(part)
        if len(sub_parts) > 1:
            for sp in sub_parts:
                _add(sp)
    return out


# ---------------------------------------------------------------------------
# ★v1.1★ Alias 词表扩展（从 .wiki-schema.md 「别名词表」节自动抽取）
# ---------------------------------------------------------------------------

ALIAS_LINE_RE = re.compile(r"^([^=#\n]+?(?:\s*=\s*[^=#\n]+?)+)\s*$")


def parse_aliases(schema_path: Path = SCHEMA_MD) -> list[set[str]]:
    """从 .wiki-schema.md 「别名词表（Alias Table）」节抽出同义词组。

    返回每组小写 token 的 set 列表，例：
        [{"gas", "gameplay ability system"}, {"lyra", "lyrastartergame", "ue5 示例项目"}, ...]
    """
    if not schema_path.is_file():
        return []
    text = schema_path.read_text(encoding="utf-8")
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
            # 去掉行尾括注，如 "Experience Definition（核心概念）"
            line = re.sub(r"[（(].*?[）)]", "", line).strip()
            if not ALIAS_LINE_RE.match(line):
                continue
            members = {p.strip().lower() for p in line.split("=") if p.strip()}
            if len(members) >= 2:
                groups.append(members)
    return groups


def expand_tokens_with_alias(
    tokens: list[str],
    alias_groups: list[set[str]],
) -> tuple[list[str], list[str]]:
    """根据 alias 词组扩展 tokens；返回 (扩展后 tokens, 新增的 alias-only tokens)。

    扩展规则（v1.1.3 起改为"整词或多词短语整体匹配"）：
        - token == alias 成员（整词相等） → 命中
        - token 命中某个**多词短语成员**（按词边界整体出现） → 命中
          例：tokens 含 "gameplay" + "ability" + "system" 才能匹配
              "gameplay ability system"（短语成员）；单个 "gameplay" 不再触发。
        - 不再做无差别子串包含匹配（旧逻辑会让 "gameplay" 误命中
          "gameplay ability system"，把整个 GAS 全域拉进候选）。
    """
    extra: list[str] = []
    seen = set(tokens)
    token_set = {t.lower() for t in tokens}

    def _member_hit(member: str) -> bool:
        member_norm = member.strip().lower()
        if not member_norm:
            return False
        # 单词成员：必须整词相等
        if " " not in member_norm:
            return member_norm in token_set
        # 多词短语成员：要求短语中每个词都已在 token_set 出现
        parts = [p for p in member_norm.split() if p]
        return all(p in token_set for p in parts)

    for grp in alias_groups:
        if not any(_member_hit(m) for m in grp):
            continue
        for m in grp:
            m_norm = m.strip().lower()
            if m_norm and m_norm not in seen:
                seen.add(m_norm)
                extra.append(m_norm)
    return tokens + extra, extra



# ---------------------------------------------------------------------------
# 数据库读取助手
# ---------------------------------------------------------------------------

def _row_to_candidate(row: sqlite3.Row, *, score: float, why: list[str], source: str) -> Candidate:
    """SQLite Row → Candidate（统一处理 JSON 字段、CJK 还原）。"""
    def _json_list(raw: str) -> list[str]:
        if not raw:
            return []
        try:
            v = json.loads(raw)
            return v if isinstance(v, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    keys = row.keys() if hasattr(row, "keys") else []
    def _get(key: str, default=None):
        if key in keys:
            return row[key]
        return default

    description_raw = _get("description") or ""
    title_raw = _get("title") or ""
    return Candidate(
        page_id=_get("id") or "",
        score=round(score, 4),
        status=_get("status") or "?",
        type=_get("type") or "?",
        category=_get("category") or "",
        domain=_get("domain") or "",
        title=cjk_space_strip(title_raw),
        description=cjk_space_strip(description_raw)[:200],
        tags=_json_list(_get("tags") or "[]"),
        related=_json_list(_get("related") or "[]"),
        prerequisites=_json_list(_get("prerequisites") or "[]"),
        series=_get("series") or "",
        lesson_index=_get("lesson_index") if _get("lesson_index") is not None else -1,
        inbound=0,
        why=why,
        source=source,
    )


def get_page_from_db(db_path: Path, page_id: str) -> Optional[Candidate]:
    """从 db 取单页元数据。"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("""
        SELECT id, title, type, status, category, domain, description,
               tags, related, prerequisites, series, lesson_index
        FROM pages WHERE id = ?
    """, (page_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_candidate(row, score=0.0, why=[], source="db")


def get_neighbors_from_db(db_path: Path, page_id: str) -> list[tuple[str, str]]:
    """获取多类型 1-hop 邻居：返回 [(neighbor_id, edge_type), ...]。

    邻居来源：
      - 出边：from_page=self
      - 入边：to_page=self（反向，用于"哪些课依赖我"）
    """
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("""
        SELECT to_page AS nid, edge_type AS et FROM links WHERE from_page = ?
        UNION
        SELECT from_page AS nid, 'inverse-' || edge_type AS et FROM links WHERE to_page = ?
    """, (page_id, page_id)).fetchall()
    conn.close()
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for nid, et in rows:
        if nid == page_id or nid in seen:
            continue
        seen.add(nid)
        out.append((nid, et))
    return out


def get_inbound_count(db_path: Path, page_id: str) -> int:
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT COUNT(DISTINCT from_page) FROM links WHERE to_page = ?",
        (page_id,)
    ).fetchone()
    conn.close()
    return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# Tier 1: SQLite FTS5 (BM25)
# ---------------------------------------------------------------------------

def query_database(
    db_path: Path,
    tokens: list[str],
    *,
    filter_category: str = "",
    filter_domain: str = "",
    max_candidates: int = 5,
    alias_only_tokens: Optional[set[str]] = None,
) -> list[Candidate]:
    """FTS5 BM25 查询。category/domain 软降权，status 后置乘法修正。

    Args:
        alias_only_tokens: ★v1.1★ 仅由 alias 扩展引入的 token 集（用于命中后软降权）
    """
    if not tokens:
        return []

    alias_only_tokens = alias_only_tokens or set()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # 构造 FTS5 查询：每个 token 做 CJK 预处理后变成 phrase 查询
    fts_terms = []
    for t in tokens:
        t_processed = cjk_space_insert(t)
        safe = t_processed.replace('"', '""')
        fts_terms.append(f'"{safe}"')
    fts_query = " OR ".join(fts_terms)

    fetch_limit = max(max_candidates * 3, 30)  # ★v1.1★ 至少取 30，确保 anchor/id 命中的页都能进入候选池

    # 列权重对应建表顺序（v1.1 起 6 列）：
    #   id=8.0  title=4.0  description=2.0  tags=1.0  anchors_text=2.5  body_text=0.5
    # ★v1.1★ id 权重提到 8.0（精确匹配最强信号），body 降到 0.5（避免长文档堆词压制精准命中）
    # ★v1.1★ anchors_text 给 2.5，配合后置 anchor-hit bonus 让"代码反查 wiki"场景生效
    sql = """
        SELECT p.id, p.title, p.type, p.status, p.category, p.domain,
               p.description, p.tags, p.anchors, p.related, p.prerequisites,
               p.series, p.lesson_index,
               bm25(pages_fts, 8.0, 4.0, 2.0, 1.0, 2.5, 0.5) as score
        FROM pages_fts
        JOIN pages p ON pages_fts.rowid = p.rowid
        WHERE pages_fts MATCH ?
        ORDER BY score LIMIT ?
    """
    try:
        rows = conn.execute(sql, [fts_query, fetch_limit]).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []

    # ★v1.1★ Anchor-hit bonus：单独查 anchor 列命中的页，给后置加分
    # 这是为了修复"查 LyraCharacter 应 Top-1 命中模块文档"的回归。
    #
    # 设计要点：
    # - 不用 BM25 连续分（会因 anchors 内常见词如 lyra/character 累积而虚高），
    #   改用"原始查询 token 在 anchors_text 中的精确子串命中"作为离散信号
    # - 仅对原始 token（非 alias 扩展词）生效，避免 alias 扩展引入的噪音
    # - **长 token 权重更高**：`lyracharacter` (13 char) 命中权重 = len/4 ≈ 3.25，
    #   而 `lyra` (4) 命中权重 = 1.0。这让 CamelCase 完整形式（用户精确意图）
    #   压过短通用词（lyra/character）的累积分数
    anchor_hit_pages: dict[str, tuple[float, list[str]]] = {}
    raw_tokens = [t for t in tokens if t not in (alias_only_tokens or set())]
    if raw_tokens:
        cand_ids = [r["id"] for r in rows]
        if cand_ids:
            placeholders = ",".join("?" * len(cand_ids))
            for ar in conn.execute(
                f"SELECT id, anchors_text FROM pages WHERE id IN ({placeholders})",
                cand_ids,
            ).fetchall():
                at = (ar["anchors_text"] or "").lower()
                if not at:
                    continue
                hit_tokens = [t for t in raw_tokens if t and t in at]
                if hit_tokens:
                    # 长度加权：长 token 命中权重 = len/4，短 token 接近 1
                    weight = sum(max(1.0, len(t) / 4.0) for t in hit_tokens)
                    anchor_hit_pages[ar["id"]] = (weight, hit_tokens)

    results: list[Candidate] = []
    for row in rows:
        raw_score = abs(row["score"])  # BM25 返回负值
        status = row["status"] or ""
        status_mult = STATUS_MULTIPLIER.get(status, 1.0)
        adjusted = raw_score * status_mult

        why: list[str] = [f"fts5-bm25(raw={raw_score:.2f})"]

        # ★v1.1★ Anchor-hit bonus（详见 query_database 顶部注释）
        if row["id"] in anchor_hit_pages:
            weight, hit_toks = anchor_hit_pages[row["id"]]
            bonus = ANCHOR_HIT_BONUS * weight
            adjusted += bonus
            why.append(f"anchor-hit:{','.join(hit_toks)}(+{bonus:.2f})")

        # ★v1.1★ Page-id full-token bonus：完整 query token 出现在 page_id 路径中时给强加分
        # 修复"查 LyraCharacter Top-1 应是 ALyraCharacter 模块文档"场景。
        # 直接用原始 token（非 alias 扩展），且只对长 token (≥6 字符) 生效避免常见词噪音。
        pid_low = (row["id"] or "").lower()
        for t in raw_tokens:
            if len(t) >= 6 and t in pid_low:
                pid_bonus = ID_FULLTOKEN_BONUS
                adjusted += pid_bonus
                why.append(f"id-fulltoken:{t}(+{pid_bonus:.2f})")
                break  # 一个匹配就够了，避免叠加

        # ★v1.1★ alias-only 命中软降权：只命中扩展词、未命中原始词的页面降权
        # 简化判定：如果该页面所有命中的 token 都来自 alias 集，则降权（保守估计）
        if alias_only_tokens:
            page_text = " ".join(filter(None, [
                (row["id"] or "").lower(),
                (row["title"] or "").lower(),
                (row["description"] or "").lower(),
                (row["tags"] or "").lower(),
            ]))
            non_alias_tokens = [t for t in tokens if t not in alias_only_tokens]
            non_alias_hit = any(t in page_text for t in non_alias_tokens)
            if not non_alias_hit:
                adjusted *= ALIAS_DAMP
                why.append(f"alias-only-hit(×{ALIAS_DAMP})")

        if filter_category and row["category"] != filter_category:
            adjusted *= CATEGORY_MISMATCH_PENALTY
            why.append(f"category-mismatch({row['category']}!={filter_category})")
        if filter_domain and row["domain"] != filter_domain:
            adjusted *= DOMAIN_MISMATCH_PENALTY
            why.append(f"domain-mismatch({row['domain']}!={filter_domain})")
        if status_mult < 1.0:
            why.append(f"status={status}(×{status_mult})")

        cand = _row_to_candidate(row, score=adjusted, why=why, source="fts5")
        if status in ("stale", "deprecated"):
            cand.warnings.append(f"status={status} — re-verify before citing")
        results.append(cand)

    conn.close()
    results.sort(key=lambda c: -c.score)
    return results[:max_candidates]


def run_query_db(
    query: str,
    *,
    db_path: Path,
    max_candidates: int = 5,
    filter_category: str = "",
    filter_domain: str = "",
    seed_id: Optional[str] = None,
    series_name: Optional[str] = None,
    use_alias: bool = True,
) -> QueryResult:
    """Tier 1 主入口（含 seed / series 模式 + ★v1.1 alias 扩展★）。"""

    # series 模式
    if series_name:
        return _run_series_mode_db(db_path, series_name)

    # seed 模式
    if seed_id:
        seed_cand = get_page_from_db(db_path, seed_id)
        if not seed_cand:
            return QueryResult(
                query=seed_id, tokens=[], candidates=[], neighbors=[],
                suggestion=f"Page [[{seed_id}]] not found.",
                mode="seed",
            )
        seed_cand.score = 10.0
        seed_cand.why = ["seed-id"]
        seed_cand.source = "seed"
        seed_cand.inbound = get_inbound_count(db_path, seed_id)

        neighbors = []
        for nid, edge in get_neighbors_from_db(db_path, seed_id):
            ncand = get_page_from_db(db_path, nid)
            if not ncand:
                continue
            ncand.why = [f"{edge} from [[{seed_id}]]"]
            ncand.source = "1-hop"
            ncand.inbound = get_inbound_count(db_path, nid)
            neighbors.append(ncand)
        neighbors.sort(key=lambda c: (-c.inbound, c.page_id))

        return QueryResult(
            query=seed_id, tokens=[], candidates=[seed_cand], neighbors=neighbors,
            suggestion=f"Seed [[{seed_id}]] 有 {len(neighbors)} 个邻居",
            mode="seed",
        )

    # keyword 模式
    tokens = tokenize(query)
    if not tokens:
        return QueryResult(query=query, tokens=[], candidates=[], neighbors=[])

    # ★v1.1★ alias 词表扩展
    alias_extra: list[str] = []
    if use_alias:
        alias_groups = parse_aliases(SCHEMA_MD)
        if alias_groups:
            tokens, alias_extra = expand_tokens_with_alias(tokens, alias_groups)
    alias_only_set = set(alias_extra)

    candidates = query_database(
        db_path, tokens,
        filter_category=filter_category,
        filter_domain=filter_domain,
        max_candidates=max_candidates,
        alias_only_tokens=alias_only_set,
    )
    for c in candidates:
        c.inbound = get_inbound_count(db_path, c.page_id)

    # 1-hop 邻居（仅展开 Top-3）
    cand_ids = {c.page_id for c in candidates}
    seen_neighbors: dict[str, tuple[str, str]] = {}  # nid → (via, edge)
    for c in candidates[:3]:
        for nid, edge in get_neighbors_from_db(db_path, c.page_id):
            if nid in cand_ids or nid in seen_neighbors:
                continue
            seen_neighbors[nid] = (c.page_id, edge)

    neighbors_list: list[Candidate] = []
    for nid, (via, edge) in seen_neighbors.items():
        ncand = get_page_from_db(db_path, nid)
        if not ncand:
            continue
        ncand.why = [f"{edge} from [[{via}]]"]
        ncand.source = "1-hop"
        ncand.inbound = get_inbound_count(db_path, nid)
        neighbors_list.append(ncand)
    neighbors_list.sort(key=lambda c: (-c.inbound, c.page_id))

    suggestion = f"建议优先读 [[{candidates[0].page_id}]]" if candidates else ""

    return QueryResult(
        query=query, tokens=tokens,
        candidates=candidates, neighbors=neighbors_list,
        suggestion=suggestion,
        alias_extra=alias_extra,
    )


def _run_series_mode_db(db_path: Path, series_name: str) -> QueryResult:
    """系列模式：列出 series=X 的所有课程，按 lesson_index 排序。"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, type, status, category, domain, description,
               tags, related, prerequisites, series, lesson_index
        FROM pages
        WHERE series = ?
        ORDER BY CASE WHEN lesson_index < 0 THEN 1 ELSE 0 END,
                 lesson_index, id
    """, (series_name,)).fetchall()
    conn.close()

    candidates: list[Candidate] = []
    for r in rows:
        c = _row_to_candidate(r, score=0.0, why=[f"series:{series_name}"], source="series")
        c.inbound = get_inbound_count(db_path, c.page_id)
        candidates.append(c)

    # 跨系列邻居（仅展开 Top-3）
    cand_ids = {c.page_id for c in candidates}
    seen: dict[str, tuple[str, str]] = {}
    for c in candidates[:3]:
        for nid, edge in get_neighbors_from_db(db_path, c.page_id):
            if nid in cand_ids or nid in seen:
                continue
            seen[nid] = (c.page_id, edge)

    neighbors: list[Candidate] = []
    for nid, (via, edge) in seen.items():
        ncand = get_page_from_db(db_path, nid)
        if not ncand or ncand.series == series_name:
            continue
        ncand.why = [f"{edge} from [[{via}]]"]
        ncand.source = "1-hop"
        ncand.inbound = get_inbound_count(db_path, nid)
        neighbors.append(ncand)

    return QueryResult(
        query=f"--series {series_name}",
        tokens=[],
        candidates=candidates,
        neighbors=neighbors,
        suggestion=f"系列 '{series_name}' 共 {len(candidates)} 课" if candidates else f"未找到系列 '{series_name}'",
        mode="series",
    )


# ---------------------------------------------------------------------------
# Tier 2: Hybrid (BM25 + Vector + RRF)
# ---------------------------------------------------------------------------

def _vectors_exist(db_path: Path) -> bool:
    """Check if vector data exists in the database."""
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='chunks'"
        ).fetchone()
        if not row or row[0] == 0:
            conn.close()
            return False
        row = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL"
        ).fetchone()
        conn.close()
        return row is not None and row[0] > 0
    except Exception:
        return False


def _load_embedding_module():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    from wiki_embeddings import EmbeddingConfig, create_provider, embedding_to_blob
    return EmbeddingConfig, create_provider, embedding_to_blob


def query_vectors(
    db_path: Path,
    query_embedding: list[float],
    *,
    filter_category: str = "",
    filter_domain: str = "",
    limit: int = 30,
) -> list[Candidate]:
    """sqlite-vec KNN 查询。"""
    if not _SQLITE_VEC_AVAILABLE:
        return _query_vectors_fallback(
            db_path, query_embedding,
            filter_category=filter_category,
            filter_domain=filter_domain,
            limit=limit,
        )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception:
        conn.close()
        return _query_vectors_fallback(
            db_path, query_embedding,
            filter_category=filter_category,
            filter_domain=filter_domain,
            limit=limit,
        )

    query_blob = struct.pack(f"{len(query_embedding)}f", *query_embedding)
    fetch_limit = limit * 3
    try:
        rows = conn.execute("""
            SELECT rowid, distance FROM vec_chunks
            WHERE embedding MATCH ? ORDER BY distance LIMIT ?
        """, (query_blob, fetch_limit)).fetchall()
    except Exception:
        conn.close()
        return []
    if not rows:
        conn.close()
        return []

    chunk_ids = [r["rowid"] for r in rows]
    distances = {r["rowid"]: r["distance"] for r in rows}
    placeholders = ",".join("?" * len(chunk_ids))
    chunk_rows = conn.execute(f"""
        SELECT c.id as chunk_id, c.chunk_index, c.page_id,
               p.title, p.type, p.status, p.category, p.domain,
               p.description, p.tags, p.related, p.prerequisites,
               p.series, p.lesson_index,
               p.id as page_id_again
        FROM chunks c JOIN pages p ON c.page_id = p.id
        WHERE c.id IN ({placeholders})
    """, chunk_ids).fetchall()
    conn.close()

    seen_pages: dict[str, dict] = {}
    for row in chunk_rows:
        pid = row["page_id"]
        dist = distances.get(row["chunk_id"], 999.0)
        if pid not in seen_pages or dist < seen_pages[pid]["distance"]:
            seen_pages[pid] = {
                "row": row,
                "distance": dist,
                "chunk_index": row["chunk_index"],
            }

    sorted_pages = sorted(seen_pages.items(), key=lambda x: x[1]["distance"])

    results: list[Candidate] = []
    for pid, info in sorted_pages:
        row = info["row"]
        raw_score = 1.0 / (1.0 + info["distance"])
        chunk_idx = info["chunk_index"]
        pos_boost = VECTOR_POSITION_BOOST.get(chunk_idx, VECTOR_POSITION_DEFAULT)
        adjusted = raw_score * pos_boost

        status = row["status"] or ""
        status_mult = STATUS_MULTIPLIER.get(status, 1.0)
        adjusted *= status_mult

        why = [f"vector(dist={info['distance']:.4f}, chunk={chunk_idx}, pos×{pos_boost})"]
        if filter_category and row["category"] != filter_category:
            adjusted *= CATEGORY_MISMATCH_PENALTY
            why.append(f"category-mismatch({row['category']}!={filter_category})")
        if filter_domain and row["domain"] != filter_domain:
            adjusted *= DOMAIN_MISMATCH_PENALTY
            why.append(f"domain-mismatch({row['domain']}!={filter_domain})")
        if status_mult < 1.0:
            why.append(f"status={status}(×{status_mult})")

        # 用一个伪 row 给 _row_to_candidate
        # 注意：chunk_rows 里有 id 列指向 chunks.id，但 page id 在 page_id 列
        cand = Candidate(
            page_id=pid,
            score=round(adjusted, 4),
            status=status or "?",
            type=row["type"] or "?",
            category=row["category"] or "",
            domain=row["domain"] or "",
            title=cjk_space_strip(row["title"] or ""),
            description=cjk_space_strip((row["description"] or ""))[:200],
            tags=_safe_json_list(row["tags"]),
            related=_safe_json_list(row["related"]),
            prerequisites=_safe_json_list(row["prerequisites"]),
            series=row["series"] or "",
            lesson_index=row["lesson_index"] if row["lesson_index"] is not None else -1,
            why=why,
            source="vector",
        )
        if status in ("stale", "deprecated"):
            cand.warnings.append(f"status={status} — re-verify before citing")
        results.append(cand)

    results.sort(key=lambda c: -c.score)
    return results[:limit]


def _safe_json_list(raw) -> list[str]:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _query_vectors_fallback(
    db_path: Path,
    query_embedding: list[float],
    *,
    filter_category: str = "",
    filter_domain: str = "",
    limit: int = 30,
) -> list[Candidate]:
    """无 sqlite-vec 时：暴力余弦相似度。"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT c.id, c.page_id, c.chunk_index, c.embedding,
               p.title, p.type, p.status, p.category, p.domain,
               p.description, p.tags, p.related, p.prerequisites,
               p.series, p.lesson_index
        FROM chunks c JOIN pages p ON c.page_id = p.id
        WHERE c.embedding IS NOT NULL
    """).fetchall()
    conn.close()
    if not rows:
        return []

    dims = len(query_embedding)
    q_norm = sum(x * x for x in query_embedding) ** 0.5
    if q_norm == 0:
        return []

    page_scores: dict[str, tuple[float, sqlite3.Row, int]] = {}
    for row in rows:
        blob = row["embedding"]
        if not blob or len(blob) != dims * 4:
            continue
        emb = struct.unpack(f"{dims}f", blob)
        dot = sum(a * b for a, b in zip(query_embedding, emb))
        emb_norm = sum(x * x for x in emb) ** 0.5
        if emb_norm == 0:
            continue
        sim = dot / (q_norm * emb_norm)
        pid = row["page_id"]
        if pid not in page_scores or sim > page_scores[pid][0]:
            page_scores[pid] = (sim, row, row["chunk_index"])

    sorted_pages = sorted(page_scores.items(), key=lambda x: -x[1][0])

    results: list[Candidate] = []
    for pid, (sim, row, chunk_idx) in sorted_pages:
        pos_boost = VECTOR_POSITION_BOOST.get(chunk_idx, VECTOR_POSITION_DEFAULT)
        adjusted = sim * pos_boost
        status = row["status"] or ""
        status_mult = STATUS_MULTIPLIER.get(status, 1.0)
        adjusted *= status_mult

        why = [f"vector(cosine={sim:.4f}, chunk={chunk_idx}, pos×{pos_boost})"]
        if filter_category and row["category"] != filter_category:
            adjusted *= CATEGORY_MISMATCH_PENALTY
            why.append(f"category-mismatch({row['category']}!={filter_category})")
        if filter_domain and row["domain"] != filter_domain:
            adjusted *= DOMAIN_MISMATCH_PENALTY
            why.append(f"domain-mismatch({row['domain']}!={filter_domain})")
        if status_mult < 1.0:
            why.append(f"status={status}(×{status_mult})")

        cand = Candidate(
            page_id=pid,
            score=round(adjusted, 4),
            status=status or "?",
            type=row["type"] or "?",
            category=row["category"] or "",
            domain=row["domain"] or "",
            title=cjk_space_strip(row["title"] or ""),
            description=cjk_space_strip((row["description"] or ""))[:200],
            tags=_safe_json_list(row["tags"]),
            related=_safe_json_list(row["related"]),
            prerequisites=_safe_json_list(row["prerequisites"]),
            series=row["series"] or "",
            lesson_index=row["lesson_index"] if row["lesson_index"] is not None else -1,
            why=why,
            source="vector",
        )
        results.append(cand)

    results.sort(key=lambda c: -c.score)
    return results[:limit]


def rrf_merge(
    bm25_results: list[Candidate],
    vector_results: list[Candidate],
    k: int = 60,
    bm25_weight: float = 1.0,
    vector_weight: float = 1.0,
) -> list[Candidate]:
    """RRF: score(d) = Σ weight × 1/(k + rank + 1)。"""
    scores: dict[str, float] = {}
    bm25_ranks: dict[str, int] = {}
    vec_ranks: dict[str, int] = {}
    cand_map: dict[str, Candidate] = {}

    for rank, r in enumerate(bm25_results):
        scores[r.page_id] = scores.get(r.page_id, 0) + bm25_weight * (1.0 / (k + rank + 1))
        bm25_ranks[r.page_id] = rank + 1
        cand_map[r.page_id] = r
    for rank, r in enumerate(vector_results):
        scores[r.page_id] = scores.get(r.page_id, 0) + vector_weight * (1.0 / (k + rank + 1))
        vec_ranks[r.page_id] = rank + 1
        if r.page_id not in cand_map:
            cand_map[r.page_id] = r

    sorted_ids = sorted(scores.keys(), key=lambda pid: -scores[pid])

    merged: list[Candidate] = []
    for pid in sorted_ids:
        cand = cand_map[pid]
        cand.score = round(scores[pid], 4)
        parts = []
        if pid in bm25_ranks:
            parts.append(f"bm25=#{bm25_ranks[pid]}")
        if pid in vec_ranks:
            parts.append(f"vector=#{vec_ranks[pid]}")
        cand.why = [f"rrf({', '.join(parts)})"]
        cand.source = "hybrid"
        merged.append(cand)
    return merged


def run_query_hybrid(
    query: str,
    *,
    db_path: Path,
    max_candidates: int = 5,
    filter_category: str = "",
    filter_domain: str = "",
    seed_id: Optional[str] = None,
    series_name: Optional[str] = None,
    config: dict,
    use_alias: bool = True,
) -> QueryResult:
    """Tier 2 Hybrid 查询。"""
    # seed / series 模式直接走 Tier 1
    if seed_id or series_name:
        return run_query_db(
            query, db_path=db_path,
            max_candidates=max_candidates,
            filter_category=filter_category,
            filter_domain=filter_domain,
            seed_id=seed_id,
            series_name=series_name,
        )

    tokens = tokenize(query)
    if not tokens:
        return QueryResult(query=query, tokens=[], candidates=[], neighbors=[])

    # ★v1.1★ alias 词表扩展（Hybrid 路也享受）
    alias_extra: list[str] = []
    if use_alias:
        alias_groups = parse_aliases(SCHEMA_MD)
        if alias_groups:
            tokens, alias_extra = expand_tokens_with_alias(tokens, alias_groups)
    alias_only_set = set(alias_extra)

    search_cfg = config.get("retrieval", {}).get("search", {})
    rrf_k = int(search_cfg.get("rrf_k", 60))
    bm25_w = float(search_cfg.get("bm25_weight", 1.0))
    vec_w = float(search_cfg.get("vector_weight", 1.0))

    bm25_results = query_database(
        db_path, tokens,
        filter_category=filter_category,
        filter_domain=filter_domain,
        max_candidates=30,
        alias_only_tokens=alias_only_set,
    )

    vector_results: list[Candidate] = []
    try:
        EmbeddingConfig, create_provider, _ = _load_embedding_module()
        embed_cfg = EmbeddingConfig.from_dict(
            config.get("retrieval", {}).get("embedding", {})
        )
        provider = create_provider(embed_cfg)
        available, reason = provider.is_available()
        if available:
            qe = provider.embed_one(query)
            if qe:
                vector_results = query_vectors(
                    db_path, qe,
                    filter_category=filter_category,
                    filter_domain=filter_domain,
                    limit=30,
                )
        else:
            print(f"  [warn] Embedding provider not available: {reason}", file=sys.stderr)
    except Exception as e:
        print(f"  [warn] Vector search failed: {e}", file=sys.stderr)

    fused = rrf_merge(bm25_results, vector_results, k=rrf_k,
                      bm25_weight=bm25_w, vector_weight=vec_w) if vector_results else bm25_results
    top = fused[:max_candidates]

    for c in top:
        c.inbound = get_inbound_count(db_path, c.page_id)

    # 邻居展开
    cand_ids = {c.page_id for c in top}
    seen: dict[str, tuple[str, str]] = {}
    for c in top[:3]:
        for nid, edge in get_neighbors_from_db(db_path, c.page_id):
            if nid in cand_ids or nid in seen:
                continue
            seen[nid] = (c.page_id, edge)
    neighbors_list: list[Candidate] = []
    for nid, (via, edge) in seen.items():
        ncand = get_page_from_db(db_path, nid)
        if not ncand:
            continue
        ncand.why = [f"{edge} from [[{via}]]"]
        ncand.source = "1-hop"
        ncand.inbound = get_inbound_count(db_path, nid)
        neighbors_list.append(ncand)
    neighbors_list.sort(key=lambda c: (-c.inbound, c.page_id))

    suggestion = f"建议优先读 [[{top[0].page_id}]]" if top else ""
    return QueryResult(
        query=query, tokens=tokens,
        candidates=top, neighbors=neighbors_list,
        suggestion=suggestion,
        alias_extra=alias_extra,
    )


# ---------------------------------------------------------------------------
# Tier 决策
# ---------------------------------------------------------------------------

def determine_tier(db_path: Path, config: dict, override: str = "") -> str:
    """决定使用哪个 Tier。返回 'grep' | 'sqlite' | 'hybrid'。"""
    engine = override or config.get("retrieval", {}).get("engine", "auto")
    db_exists = db_path.exists()
    vectors_exist = _vectors_exist(db_path) if db_exists else False

    if engine == "grep":
        return "grep"
    if engine == "sqlite":
        return "sqlite" if db_exists else "grep"
    if engine == "hybrid":
        if db_exists and vectors_exist:
            return "hybrid"
        return "sqlite" if db_exists else "grep"

    # auto
    if not db_exists:
        return "grep"
    thresholds = config.get("retrieval", {}).get("auto_thresholds", {})
    tier1_at = int(thresholds.get("tier1_at", 200))
    tier2_at = int(thresholds.get("tier2_at", 3000))
    try:
        conn = sqlite3.connect(str(db_path))
        page_count = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        conn.close()
    except Exception:
        page_count = 0

    if page_count >= tier2_at and vectors_exist:
        return "hybrid"
    if page_count >= tier1_at:
        return "sqlite"
    return "sqlite"  # db 已存在就用 db，不退到 grep


# ---------------------------------------------------------------------------
# 输出格式化
# ---------------------------------------------------------------------------

def _supports_color() -> bool:
    return sys.stdout.isatty() and sys.platform != "win32"


def _c(code: str, text: str) -> str:
    if not _supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def _bold(s): return _c("1", s)
def _dim(s): return _c("2", s)
def _green(s): return _c("32", s)
def _yellow(s): return _c("33", s)
def _red(s): return _c("31", s)


def _status_label(status: str) -> str:
    if status == "current":
        return _green(status)
    if status == "draft":
        return _yellow(status)
    if status == "stale":
        return _yellow(f"[WARN] {status}")
    if status == "deprecated":
        return _red(f"[DEPRECATED] {status}")
    return status


def format_candidate(c: Candidate, idx: int, *, show_score: bool = True) -> str:
    lines: list[str] = []
    star = "★ " if idx == 1 else "  "
    head = f"[{idx}] {star}[[{c.page_id}]]"
    if show_score:
        lines.append(_bold(head) + f"   {_dim('score=')}{c.score}")
    else:
        lines.append(_bold(head))

    meta_parts = [
        f"type={c.type}",
        f"status={_status_label(c.status)}",
        f"category={c.category}",
    ]
    if c.domain:
        meta_parts.append(f"domain={c.domain}")
    if c.inbound:
        meta_parts.append(f"inbound={c.inbound}")
    if c.series:
        li = f"#{c.lesson_index}" if c.lesson_index >= 0 else ""
        meta_parts.append(f"series={c.series}{li}")
    lines.append("     " + "  ".join(meta_parts))

    if c.title and c.title != c.page_id.split("/")[-1]:
        lines.append(f"     title: {c.title}")
    if c.description:
        lines.append(f"     desc:  {c.description}")
    if c.related:
        head_rel = ", ".join(f"[[{r}]]" for r in c.related[:3])
        rest = f" (+{len(c.related) - 3} more)" if len(c.related) > 3 else ""
        lines.append(f"     related: {head_rel}{rest}")
    if c.prerequisites:
        head_pre = ", ".join(f"[[{p}]]" for p in c.prerequisites[:3])
        rest = f" (+{len(c.prerequisites) - 3} more)" if len(c.prerequisites) > 3 else ""
        lines.append(f"     prereq:  {head_pre}{rest}")
    if c.why:
        lines.append(_dim(f"     why: {'; '.join(c.why)}"))
    for w in c.warnings:
        lines.append(_yellow(f"     [WARN] {w}"))
    return "\n".join(lines)


def render_human(result: QueryResult) -> str:
    out: list[str] = []

    if result.mode == "seed":
        out.append(_bold(f"Seed mode: {result.query!r}"))
    elif result.mode == "series":
        out.append(_bold(f"Series mode: {result.query}  ({len(result.candidates)} 课)"))
    else:
        out.append(_bold(f"Query: {result.query!r}"))
        if result.tokens:
            out.append(f"Tokens: {', '.join(result.tokens)}")
        if result.alias_extra:
            out.append(_dim(f"Alias-expanded: {', '.join(result.alias_extra)}"))
    out.append("")

    if not result.candidates:
        out.append(_yellow("[WARN] No candidate found."))
    else:
        if result.mode == "series":
            out.append(_bold(f"═══ {result.query} 系列课程 ═══"))
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
        out.append(_dim("(候选页的 related / prereq / wikilink 邻居)"))
        for n in result.neighbors[:12]:
            edge = ""
            if n.why and n.why[0]:
                first_tok = n.why[0].split()[0]
                edge = _dim(f" via:{first_tok}")
            warn_tag = _yellow(f"  [WARN] {n.status}") if n.status in ("stale", "deprecated") else ""
            out.append(
                f"  - [[{n.page_id}]]  ({_status_label(n.status)}, {n.type}, "
                f"inbound={n.inbound}){edge}{warn_tag}"
            )
            if n.description:
                out.append(_dim(f"      {n.description[:120]}"))
        out.append("")

    if result.suggestion:
        out.append(_dim(f"[HINT] {result.suggestion}"))

    out.append(_dim(f"[Tier: {result.tier}]"))
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Tier 0 委托
# ---------------------------------------------------------------------------

def run_tier0_delegate(
    query: str,
    *,
    seed_id: Optional[str],
    series_name: Optional[str],
    max_candidates: int,
    json_output: bool,
    use_alias: bool = True,
    no_body: bool = False,
) -> int:
    """委托给同目录下的 query.py（已有的 grep+图谱引擎）。"""
    import subprocess
    cmd = [sys.executable, str(SCRIPTS_DIR / "query.py")]
    if seed_id:
        cmd += ["--id", seed_id]
    elif series_name:
        cmd += ["--series", series_name]
    elif query:
        cmd.append(query)
    cmd += ["--max-candidates", str(max_candidates)]
    if json_output:
        cmd.append("--json")
    if not use_alias:
        cmd.append("--no-alias")
    if no_body:
        cmd.append("--no-body")
    return subprocess.call(cmd)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="wiki_query.py",
        description="LyraStarterGame project-wiki Tier 1/2 查询（FTS5 / Hybrid）"
    )
    ap.add_argument("query", nargs="?", default="",
                    help="查询关键词（空格分隔，CamelCase 自动拆分）")
    ap.add_argument("--id", dest="seed_id", default=None,
                    help="种子页 id：直接展示该页 + 多类型 1-hop 邻居")
    ap.add_argument("--series", dest="series_name", default=None,
                    help="教程系列模式：列出系列全部课程（如 gas / network-sync）")
    ap.add_argument("--category", default="",
                    help="限定 category 软降权（如 30-tutorials / 60-decisions）")
    ap.add_argument("--domain", default="",
                    help="限定 domain 软降权（如 gas / network-sync）")
    ap.add_argument("--max-candidates", type=int, default=5,
                    help="返回 top N 候选 (default: 5)")
    ap.add_argument("--engine", default="",
                    choices=["", "grep", "sqlite", "hybrid", "auto"],
                    help="强制指定引擎（覆盖 config.yaml）")
    ap.add_argument("--db-path", default=None,
                    help="数据库路径覆盖")
    ap.add_argument("--no-alias", action="store_true",
                    help="关闭 alias 词表扩展（默认开启，用 .wiki-schema.md 「别名词表」节）")
    ap.add_argument("--no-body", action="store_true",
                    help="（兼容 query.py CLI；Tier 1 默认就是 FTS5 索引查询，无 body grep）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    ap = build_argparser()
    args = ap.parse_args(argv)

    if not args.query and not args.seed_id and not args.series_name:
        ap.error("请提供查询关键词、--id 或 --series")
        return 2
    if args.seed_id and args.series_name:
        ap.error("--id 与 --series 互斥")
        return 2

    config = load_config()
    db_path = resolve_db_path(config, args.db_path)
    tier = determine_tier(db_path, config, override=args.engine)
    use_alias = not args.no_alias

    # ★v1.1.2★ 用户强制 grep 路径
    if tier == "grep":
        return run_tier0_delegate(
            args.query,
            seed_id=args.seed_id,
            series_name=args.series_name,
            max_candidates=args.max_candidates,
            json_output=args.json,
            use_alias=use_alias,
            no_body=args.no_body,
        )

    # ★v1.1.2★ Tier 1/2 主路径 + 异常/零结果自动 fallback 到 Tier 0
    #
    # 触发 fallback 的三种情况：
    #   1. Tier 1/2 执行抛异常（FTS5 损坏、表缺失、SQL 错误等）
    #   2. keyword 模式返回零候选（BM25 完全没命中，让 Tier 0 启发式 + body grep 兜底）
    #   3. seed/series 模式返回种子不存在（Tier 0 也会一样失败，但保持一致路径）
    #
    # fallback 前会输出 stderr 提示，便于诊断。
    fallback_reason = ""
    result = None
    try:
        if tier == "hybrid":
            result = run_query_hybrid(
                args.query, db_path=db_path,
                max_candidates=args.max_candidates,
                filter_category=args.category,
                filter_domain=args.domain,
                seed_id=args.seed_id,
                series_name=args.series_name,
                config=config,
                use_alias=use_alias,
            )
            result.tier = "Tier 2 (Hybrid: BM25 + Vector + RRF)"
        else:
            # Tier 1
            result = run_query_db(
                args.query, db_path=db_path,
                max_candidates=args.max_candidates,
                filter_category=args.category,
                filter_domain=args.domain,
                seed_id=args.seed_id,
                series_name=args.series_name,
                use_alias=use_alias,
            )
            result.tier = "Tier 1 (FTS5)"
    except Exception as e:
        fallback_reason = f"Tier {'2' if tier == 'hybrid' else '1'} 执行异常: {type(e).__name__}: {e}"

    # 零候选触发 fallback（仅 keyword 模式；seed/series 找不到目标是合理结果，不触发）
    if not fallback_reason and result is not None:
        is_keyword_mode = not args.seed_id and not args.series_name
        if is_keyword_mode and not result.candidates:
            fallback_reason = f"Tier {'2' if tier == 'hybrid' else '1'} 零候选（BM25 未命中），尝试 Tier 0 启发式 + body grep 兜底"

    if fallback_reason:
        print(
            f"[wiki_query] {fallback_reason}\n"
            f"[wiki_query] 自动 fallback → Tier 0 (query.py)。如需禁用，设 PROJECT_WIKI_NO_AUTO_FALLBACK=1",
            file=sys.stderr,
        )
        import os
        if not os.environ.get("PROJECT_WIKI_NO_AUTO_FALLBACK"):
            return run_tier0_delegate(
                args.query,
                seed_id=args.seed_id,
                series_name=args.series_name,
                max_candidates=args.max_candidates,
                json_output=args.json,
                use_alias=use_alias,
                no_body=args.no_body,
            )

    if args.json:
        print(json.dumps(result.asdict(), ensure_ascii=False, indent=2))
    else:
        print(render_human(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
