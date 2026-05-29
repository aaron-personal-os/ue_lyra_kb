#!/usr/bin/env python3
"""wiki_rebuild.py — LyraStarterGame project-wiki Tier 1/2 索引构建器

移植自 ProjectWiki v2.0（详见 reference/retrieval-engine-design.md）。

纯 Python 3.9+ stdlib（sqlite3 内置，FTS5 可用），无外部依赖。
向量功能需要 `pip install sqlite-vec`（可选）。

扫描 Docs/ 下所有合法 .md 页面，构建：
  - pages 表（元数据 + 正文 + series/lesson_index/prerequisites 等教程字段）
  - pages_fts 虚拟表（FTS5 BM25 全文搜索）
  - links 表（wikilink + prerequisites 知识图谱边）
  - chunks 表（向量检索用的文本块 + embedding）
  - vec_chunks 虚拟表（sqlite-vec 向量索引）
  - build_meta 表（构建时间等）

与源方案的本项目特化点
========================

* 顶层目录是 `00-meta/30-tutorials/...` 数字前缀分类，不是 brain；
  用 `category` 字段（page_id 第一段）替代源方案的 `brain`。
* `domain` 仍取 page_id 第二段（如 `gas` / `network-sync`），用于教程系列定位。
* frontmatter 兼容 `description`（fallback `compiled_summary`）、
  `last_synced`（fallback `last_verified`）。
* 教程特色字段 `series` / `lesson_index` / `prerequisites` 进入 pages 表，
  `prerequisites` 同时进 links 表（与 `related` 同等图边）。
* 排除目录：`_raw/` / `.obsidian/` / `log.d/` / `log-archive/` / `.codebuddy/`。
* 数据库默认在 `.codebuddy/skills/project-wiki/.cache/wiki.db`（已被 gitignore）。

用法
====

    # 全量重建（删库重建，不含向量）
    python3 .codebuddy/skills/project-wiki/scripts/wiki_rebuild.py

    # 全量重建 + 向量（需要 embedding API）
    python3 .codebuddy/skills/project-wiki/scripts/wiki_rebuild.py --with-vectors

    # 只重建向量（pages 表已存在）
    python3 .codebuddy/skills/project-wiki/scripts/wiki_rebuild.py --vectors-only

    # 增量更新（只处理变更文件，基于 content_hash）
    python3 .codebuddy/skills/project-wiki/scripts/wiki_rebuild.py --incremental

    # 检查是否需要重建（CI 用，exit 1 = 需要重建）
    python3 .codebuddy/skills/project-wiki/scripts/wiki_rebuild.py --check

退出码
======

    0  正常 / 无需重建
    1  需要重建 (--check 模式)
    2  CLI 错误
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
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
# 路径与配置
# ---------------------------------------------------------------------------

# Skill 脚本所在目录的 repo 根定位：scripts/ → project-wiki/ → skills/ → .codebuddy/ → repo
SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
REPO_ROOT = SKILL_DIR.parents[2]
DOCS_DIR = REPO_ROOT / "Docs"

CONFIG_PATH = SKILL_DIR / "config.yaml"
DEFAULT_DB_PATH = SKILL_DIR / ".cache" / "wiki.db"

# 顶层目录分类（替代源方案的 brain）
VALID_CATEGORIES = (
    "00-meta", "10-architecture", "20-modules", "30-tutorials",
    "40-runbooks", "50-references", "60-decisions", "70-topics",
    "80-gotchas", "90-snapshots",
)

# 排除目录前缀（相对 Docs/）
EXCLUDE_DIR_PREFIXES = (
    "_raw/", ".obsidian/", "log.d/", "log-archive/",
)

# 排除特殊文件名（顶层 meta 文档不参与全文检索）
EXCLUDE_TOP_FILES = {"index.md", "log.md", "README.md", ".wiki-schema.md"}

# Wikilink 正则
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")


# ---------------------------------------------------------------------------
# 极简 YAML 解析（仅用于 config.yaml）
# ---------------------------------------------------------------------------

def _parse_simple_yaml(text: str) -> dict:
    """极简 YAML 解析器 — 处理 config.yaml 的平坦嵌套结构。"""
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
    """加载 skill 目录下的 config.yaml。"""
    if not CONFIG_PATH.exists():
        return {}
    return _parse_simple_yaml(CONFIG_PATH.read_text(encoding="utf-8"))


def resolve_db_path(config: dict, override: Optional[str] = None) -> Path:
    """解析数据库路径。"""
    if override:
        p = Path(override)
        return p if p.is_absolute() else (REPO_ROOT / p)
    rel = config.get("paths", {}).get("db") or ".codebuddy/skills/project-wiki/.cache/wiki.db"
    return REPO_ROOT / rel


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class PageRecord:
    """一个待索引页面的结构化数据。"""
    id: str                         # "30-tutorials/gas/19-Tag网络复制"
    title: str
    type: str
    status: str
    category: str                   # "30-tutorials"（顶层目录，替代 brain）
    domain: str                     # "gas"（page_id 第二段，教程系列名）
    description: str                # 取 description / compiled_summary / 一句话
    tags: str                       # JSON array as text
    anchors: str                    # JSON array as text（结构化存储）
    anchors_text: str               # ★v1.1★ 扁平化 path 文本（参与 FTS5 倒排索引）
    related: str                    # JSON array as text
    prerequisites: str              # JSON array as text（教程前置依赖）
    series: str                     # 教程系列 slug（如 "gas"）
    lesson_index: int               # 教程序号（-1 = 非教程）
    last_synced: str
    content_hash: str
    body_text: str
    word_count: int
    links: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Frontmatter 解析（与 wiki_lint.py 一致）
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, int]:
    """解析 YAML frontmatter。返回 (fm_dict, fm_占用行数)。"""
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return {}, 0
    lines = text.splitlines()
    if lines[0].strip() != "---":
        return {}, 0

    end = -1
    for i in range(1, min(len(lines), 200)):
        if lines[i].strip() == "---":
            end = i
            break
    if end < 0:
        return {}, 0

    fm: dict = {}
    cur_key: Optional[str] = None
    list_items: list = []
    multiline_scalar: list[str] = []
    in_multiline = False

    for raw in lines[1:end]:
        line = raw.rstrip()

        if in_multiline and cur_key:
            if line.startswith("  ") or line.strip() == "":
                multiline_scalar.append(line.strip())
                continue
            else:
                fm[cur_key] = "\n".join(multiline_scalar).strip()
                in_multiline = False
                multiline_scalar = []

        if not line.strip():
            continue

        m = re.match(r"^\s*-\s*(.*)$", line)
        if m and cur_key is not None and not in_multiline:
            val = m.group(1).strip()
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            inner = re.match(r"^([\w-]+):\s*(.*)$", val)
            if inner:
                list_items.append({inner.group(1): inner.group(2).strip()})
            else:
                list_items.append(val)
            continue

        m = re.match(r"^([\w-]+):\s*(.*)$", line)
        if m:
            if cur_key is not None and list_items:
                fm[cur_key] = list_items
                list_items = []
            cur_key = m.group(1)
            val = m.group(2).strip()
            if val == "":
                continue
            if val == "|" or val == ">":
                in_multiline = True
                multiline_scalar = []
                continue
            if val.startswith("[") and val.endswith("]"):
                inner_val = val[1:-1]
                fm[cur_key] = [x.strip().strip("'\"") for x in inner_val.split(",") if x.strip()]
            else:
                if (val.startswith('"') and val.endswith('"')) or \
                   (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                fm[cur_key] = val
            continue

    if cur_key is not None:
        if in_multiline and multiline_scalar:
            fm[cur_key] = "\n".join(multiline_scalar).strip()
        elif list_items:
            fm[cur_key] = list_items

    return fm, end + 1


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def infer_category(page_id: str) -> str:
    """从页面 id 推断 category（顶层目录）。"""
    parts = page_id.split("/")
    if parts and parts[0] in VALID_CATEGORIES:
        return parts[0]
    return ""


def infer_domain(page_id: str) -> str:
    """从页面 id 推断 domain（如 30-tutorials/gas/... → gas）。"""
    parts = page_id.split("/")
    if len(parts) >= 2:
        return parts[1]
    return ""


def strip_frontmatter(text: str) -> str:
    """去掉 frontmatter 区域，只保留正文。"""
    if not text.startswith("---"):
        return text
    lines = text.splitlines()
    end = -1
    for i in range(1, min(len(lines), 200)):
        if lines[i].strip() == "---":
            end = i
            break
    if end < 0:
        return text
    return "\n".join(lines[end + 1:])


# ---------------------------------------------------------------------------
# CJK 字符级预处理（中文 FTS5 支持）
# ---------------------------------------------------------------------------

_CJK_RE = re.compile(r"([一-鿿㐀-䶿豈-﫿])")


def cjk_space_insert(text: str) -> str:
    """CJK 字符间插入空格，使每个汉字成为独立 FTS5 token。"""
    if not text:
        return text
    result = _CJK_RE.sub(r" \1 ", text)
    result = re.sub(r" +", " ", result)
    return result.strip()


def compute_content_hash(content: str) -> str:
    """SHA-256 of file content for idempotent rebuild."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def extract_title(body: str) -> str:
    """提取第一个 # 标题。"""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return ""


def extract_wikilinks(body: str) -> list[str]:
    """从正文中提取所有 [[...]] wikilink 目标（去重保序）。"""
    found: list[str] = []
    seen: set[str] = set()
    # 先去 code fence，避免代码示例里的 [[]] 被误抓
    clean = re.sub(r"```[\s\S]*?```", "", body, flags=re.MULTILINE)
    clean = re.sub(r"`[^`\n]*`", "", clean)
    for m in WIKILINK_RE.finditer(clean):
        target = m.group(1).strip()
        if target and target not in seen:
            seen.add(target)
            found.append(target)
    return found


def count_words(text: str) -> int:
    """中英混合词数估算。"""
    clean = re.sub(r"```[\s\S]*?```", "", text, flags=re.MULTILINE)
    clean = re.sub(r"`[^`\n]*`", "", clean)
    count = 0
    for token in clean.split():
        has_cjk = any('一' <= c <= '鿿' for c in token)
        if has_cjk:
            count += sum(1 for c in token if '一' <= c <= '鿿')
            non_cjk = re.sub(r'[一-鿿]', ' ', token).split()
            count += len(non_cjk)
        else:
            count += 1
    return count


def get_fm_string(fm: dict, *keys: str) -> str:
    """从 frontmatter 拿字符串（多 key 兜底）。"""
    for key in keys:
        raw = fm.get(key, None)
        if raw is None or raw == "":
            continue
        if isinstance(raw, list):
            return " ".join(str(x) for x in raw)
        return str(raw)
    return ""


def get_fm_list(fm: dict, key: str) -> list[str]:
    """从 frontmatter 拿列表字段。"""
    raw = fm.get(key, []) or []
    if isinstance(raw, str):
        return [raw] if raw else []
    result: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            for v in item.values():
                result.append(str(v))
        else:
            result.append(str(item))
    return result


def normalize_link_id(target: str) -> str:
    """归一化 wikilink target："[[id]]" / "id|alias" / "id#anchor" → "id"。"""
    s = str(target).strip()
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2]
    s = s.split("|", 1)[0].split("#", 1)[0].strip()
    return s


def get_related_ids(fm: dict) -> list[str]:
    """从 frontmatter.related 提取 wikilink id。"""
    out: list[str] = []
    for item in get_fm_list(fm, "related"):
        nid = normalize_link_id(item)
        if nid:
            out.append(nid)
    return out


def get_prerequisite_ids(fm: dict) -> list[str]:
    """从 frontmatter.prerequisites 提取 wikilink id（教程系列特色字段）。"""
    out: list[str] = []
    for item in get_fm_list(fm, "prerequisites"):
        nid = normalize_link_id(item)
        if nid:
            out.append(nid)
    return out


def get_lesson_index(fm: dict) -> int:
    """获取 lesson_index 整数（-1 = 缺失）。"""
    raw = fm.get("lesson_index", None)
    if raw is None or raw == "":
        return -1
    try:
        return int(str(raw).split()[0])
    except (ValueError, AttributeError):
        return -1


# ---------------------------------------------------------------------------
# 页面收集
# ---------------------------------------------------------------------------

def should_exclude(rel_path: str, filename: str) -> bool:
    """判断文件是否应排除。"""
    if any(rel_path.startswith(prefix) for prefix in EXCLUDE_DIR_PREFIXES):
        return True
    # 顶层 meta 文件不参与全文索引
    if "/" not in rel_path and filename in EXCLUDE_TOP_FILES:
        return True
    # log-* 分片日志（兜底，正常应已被 log.d/ 排除）
    if filename.startswith("log-") and filename.endswith(".md"):
        return True
    return False


def collect_pages(docs_root: Path) -> list[PageRecord]:
    """收集 Docs/ 下所有需要索引的 .md 页面。"""
    records: list[PageRecord] = []

    if not docs_root.is_dir():
        return records

    for md_file in sorted(docs_root.rglob("*.md")):
        rel = md_file.relative_to(docs_root).as_posix()
        filename = md_file.name

        if should_exclude(rel, filename):
            continue

        # 顶层目录必须是合法 category
        parts = rel.split("/")
        if len(parts) < 2:
            continue
        category = parts[0]
        if category not in VALID_CATEGORIES:
            continue

        content = md_file.read_text(encoding="utf-8")
        content_hash = compute_content_hash(content)

        fm, fm_lines = parse_frontmatter(content)
        body = strip_frontmatter(content)

        # page_id：优先 frontmatter.id，否则用相对路径去 .md
        page_id = rel.removesuffix(".md")
        fm_id = fm.get("id", "")
        if fm_id:
            page_id = str(fm_id).strip()

        title = extract_title(body) or page_id.split("/")[-1]
        body_links = extract_wikilinks(body)
        related_links = get_related_ids(fm)
        prereq_links = get_prerequisite_ids(fm)

        # 所有图边：related + prerequisites + body 中的 wikilink，保序去重
        all_links = list(dict.fromkeys(related_links + prereq_links + body_links))

        # 描述：description（本项目主流） / compiled_summary / 兜底 title
        description = get_fm_string(fm, "description", "compiled_summary", "compiled-summary")

        # ★v1.1★ anchors 扁平化文本：把路径分隔符替换为空格，让文件名片段成为独立 FTS5 token
        # 例：'Source/LyraGame/Character/LyraCharacter.h' →
        #     'Source LyraGame Character LyraCharacter.h LyraCharacter.h'
        # （重复一次文件名让 BM25 给文件名更高权重，不依赖目录词。）
        anchor_paths = get_fm_list(fm, "anchors")
        anchors_text_parts: list[str] = []
        for ap in anchor_paths:
            # 路径分隔符 → 空格
            flat = ap.replace("/", " ").replace("\\", " ")
            # 提取文件名（最后一段）追加一次，强化文件名权重
            basename = ap.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            anchors_text_parts.append(flat)
            if basename and basename != flat:
                anchors_text_parts.append(basename)
        anchors_text = " ".join(anchors_text_parts)

        record = PageRecord(
            id=page_id,
            title=cjk_space_insert(title),
            type=get_fm_string(fm, "type") or "page",
            status=get_fm_string(fm, "status") or "draft",
            category=category,
            domain=infer_domain(page_id),
            description=cjk_space_insert(description),
            tags=json.dumps(get_fm_list(fm, "tags"), ensure_ascii=False),
            anchors=json.dumps(anchor_paths, ensure_ascii=False),
            anchors_text=cjk_space_insert(anchors_text),  # ★v1.1★ 进 FTS5
            related=json.dumps(related_links, ensure_ascii=False),
            prerequisites=json.dumps(prereq_links, ensure_ascii=False),
            series=get_fm_string(fm, "series"),
            lesson_index=get_lesson_index(fm),
            last_synced=get_fm_string(fm, "last_synced", "last-synced", "last_verified", "last-verified"),
            content_hash=content_hash,
            body_text=cjk_space_insert(body),
            word_count=count_words(body),
            links=all_links,
        )
        records.append(record)

    return records


# ---------------------------------------------------------------------------
# SQLite Schema
# ---------------------------------------------------------------------------

# 注意：FTS5 列顺序与 query.py 中 bm25() 权重参数顺序必须一致：
# (id, title, description, tags, anchors_text, body_text) → 权重 (5.0, 3.0, 2.0, 1.0, 2.5, 1.0)
# ★v1.1★ anchors_text 列用于"代码反查 wiki"场景（查 LyraCharacter 应命中模块文档）
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pages (
    id TEXT PRIMARY KEY,
    title TEXT,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    category TEXT NOT NULL,
    domain TEXT NOT NULL,
    description TEXT,
    tags TEXT,
    anchors TEXT,
    anchors_text TEXT,
    related TEXT,
    prerequisites TEXT,
    series TEXT,
    lesson_index INTEGER DEFAULT -1,
    last_synced TEXT,
    content_hash TEXT,
    body_text TEXT,
    word_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_pages_category ON pages(category);
CREATE INDEX IF NOT EXISTS idx_pages_series ON pages(series);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);

-- FTS5 全文索引（External Content 模式，6 列）
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    id,
    title,
    description,
    tags,
    anchors_text,
    body_text,
    content='pages',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

-- 同步触发器
CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
    INSERT INTO pages_fts(rowid, id, title, description, tags, anchors_text, body_text)
    VALUES (new.rowid, new.id, new.title, new.description, new.tags, new.anchors_text, new.body_text);
END;

CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, id, title, description, tags, anchors_text, body_text)
    VALUES('delete', old.rowid, old.id, old.title, old.description, old.tags, old.anchors_text, old.body_text);
END;

CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, id, title, description, tags, anchors_text, body_text)
    VALUES('delete', old.rowid, old.id, old.title, old.description, old.tags, old.anchors_text, old.body_text);
    INSERT INTO pages_fts(rowid, id, title, description, tags, anchors_text, body_text)
    VALUES (new.rowid, new.id, new.title, new.description, new.tags, new.anchors_text, new.body_text);
END;

-- 知识图谱边（区分 wikilink / related / prerequisite / series-prev / series-next）
CREATE TABLE IF NOT EXISTS links (
    from_page TEXT NOT NULL,
    to_page TEXT NOT NULL,
    edge_type TEXT NOT NULL DEFAULT 'wikilink',  -- wikilink | related | prerequisite | series-prev | series-next
    PRIMARY KEY (from_page, to_page, edge_type)
);
CREATE INDEX IF NOT EXISTS idx_links_from ON links(from_page);
CREATE INDEX IF NOT EXISTS idx_links_to ON links(to_page);

CREATE TABLE IF NOT EXISTS build_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

CHUNKS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    token_count INTEGER,
    embedding BLOB,
    UNIQUE(page_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_page_id ON chunks(page_id);
"""


# ---------------------------------------------------------------------------
# DB 操作
# ---------------------------------------------------------------------------

def create_database(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)
    return conn


def open_database(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    return sqlite3.connect(str(db_path))


def insert_page(conn: sqlite3.Connection, record: PageRecord) -> None:
    conn.execute("""
        INSERT OR REPLACE INTO pages
        (id, title, type, status, category, domain, description,
         tags, anchors, anchors_text, related, prerequisites, series, lesson_index,
         last_synced, content_hash, body_text, word_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.id, record.title, record.type, record.status,
        record.category, record.domain, record.description,
        record.tags, record.anchors, record.anchors_text,
        record.related, record.prerequisites,
        record.series, record.lesson_index,
        record.last_synced, record.content_hash, record.body_text,
        record.word_count,
    ))


def insert_links(conn: sqlite3.Connection, record: PageRecord) -> int:
    """写入 links 表。返回写入的边数。"""
    count = 0
    # 1. 显式 related 边
    for rid in json.loads(record.related or "[]"):
        if rid and rid != record.id:
            conn.execute(
                "INSERT OR IGNORE INTO links (from_page, to_page, edge_type) VALUES (?, ?, 'related')",
                (record.id, rid),
            )
            count += 1
    # 2. 教程 prerequisites 边（特色字段）
    for pid in json.loads(record.prerequisites or "[]"):
        if pid and pid != record.id:
            conn.execute(
                "INSERT OR IGNORE INTO links (from_page, to_page, edge_type) VALUES (?, ?, 'prerequisite')",
                (record.id, pid),
            )
            count += 1
    # 3. 正文 wikilink 边（含 related/prereq 的，但 edge_type 标 wikilink；保留主键唯一）
    for tid in record.links:
        if tid and tid != record.id:
            conn.execute(
                "INSERT OR IGNORE INTO links (from_page, to_page, edge_type) VALUES (?, ?, 'wikilink')",
                (record.id, tid),
            )
            count += 1
    return count


def delete_page(conn: sqlite3.Connection, page_id: str) -> None:
    conn.execute("DELETE FROM pages WHERE id = ?", (page_id,))
    conn.execute("DELETE FROM links WHERE from_page = ?", (page_id,))


def get_stored_hashes(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT id, content_hash FROM pages").fetchall()
    return {row[0]: row[1] for row in rows}


def set_build_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO build_meta (key, value) VALUES (?, ?)",
        (key, value),
    )


# ---------------------------------------------------------------------------
# 构建流程
# ---------------------------------------------------------------------------

# Schema 版本号。改动 pages / pages_fts / links 表结构时必须升版，
# 旧 db 会在 build_incremental 检测到不匹配时自动 fallback 到 build_full。
SCHEMA_VERSION = "1.1"


@dataclass
class BuildStats:
    pages_indexed: int = 0
    links_extracted: int = 0
    skipped_unchanged: int = 0
    deleted: int = 0
    chunks_created: int = 0
    vectors_built: int = 0
    elapsed_ms: float = 0.0


def build_series_implicit_edges(conn: sqlite3.Connection) -> int:
    """★v1.1★ 根据 series + lesson_index 自动建 series-prev/next 边。

    教程系列的相邻课程未必显式 wikilink 互引，但学习路径上前后相邻 ——
    自动建边让 seed 模式 / 邻居展开能识别"上一课/下一课"。

    返回写入的边数（每对相邻课产生 2 条边：prev + next）。
    """
    rows = conn.execute("""
        SELECT id, series, lesson_index FROM pages
        WHERE series IS NOT NULL AND series != '' AND lesson_index >= 0
        ORDER BY series, lesson_index, id
    """).fetchall()

    by_series: dict[str, list[tuple[int, str]]] = {}
    for page_id, series, idx in rows:
        by_series.setdefault(series, []).append((int(idx), page_id))

    count = 0
    for series, items in by_series.items():
        items.sort()
        for i in range(len(items) - 1):
            cur_id = items[i][1]
            next_id = items[i + 1][1]
            # 同 lesson_index 的两课视为同一位置，跳过自连
            if cur_id == next_id:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO links (from_page, to_page, edge_type) "
                "VALUES (?, ?, 'series-next')",
                (cur_id, next_id),
            )
            conn.execute(
                "INSERT OR IGNORE INTO links (from_page, to_page, edge_type) "
                "VALUES (?, ?, 'series-prev')",
                (next_id, cur_id),
            )
            count += 2
    return count



def build_full(docs_root: Path, db_path: Path) -> BuildStats:
    """全量重建数据库。"""
    stats = BuildStats()
    t0 = time.time()

    conn = create_database(db_path)
    records = collect_pages(docs_root)

    for record in records:
        insert_page(conn, record)
        stats.links_extracted += insert_links(conn, record)
        stats.pages_indexed += 1

    # ★v1.1★ 构建 series-prev/next 隐式边（教程系列学习顺序自动建模）
    series_edges = build_series_implicit_edges(conn)
    stats.links_extracted += series_edges

    set_build_meta(conn, "build_time", time.strftime("%Y-%m-%dT%H:%M:%S"))
    set_build_meta(conn, "page_count", str(stats.pages_indexed))
    set_build_meta(conn, "link_count", str(stats.links_extracted))
    set_build_meta(conn, "docs_root", str(docs_root.resolve()))
    set_build_meta(conn, "schema_version", SCHEMA_VERSION)

    conn.commit()
    conn.close()

    stats.elapsed_ms = (time.time() - t0) * 1000
    return stats


def build_incremental(docs_root: Path, db_path: Path) -> BuildStats:
    """增量更新——只处理 hash 变更或新增/删除的文件。"""
    stats = BuildStats()
    t0 = time.time()

    if not db_path.exists():
        return build_full(docs_root, db_path)

    # schema 版本检查（schema 升级时退回全量重建）
    conn = open_database(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM build_meta WHERE key='schema_version'"
        ).fetchone()
        ver = row[0] if row else "0"
    except sqlite3.OperationalError:
        ver = "0"

    if ver != SCHEMA_VERSION:
        conn.close()
        return build_full(docs_root, db_path)

    stored_hashes = get_stored_hashes(conn)
    records = collect_pages(docs_root)
    current_ids: set[str] = set()
    series_changed = False

    for record in records:
        current_ids.add(record.id)
        stored_hash = stored_hashes.get(record.id, "")
        if stored_hash == record.content_hash:
            stats.skipped_unchanged += 1
            continue

        if record.id in stored_hashes:
            delete_page(conn, record.id)

        insert_page(conn, record)
        stats.links_extracted += insert_links(conn, record)
        stats.pages_indexed += 1
        if record.series:
            series_changed = True

    for old_id in stored_hashes:
        if old_id not in current_ids:
            delete_page(conn, old_id)
            stats.deleted += 1
            series_changed = True

    # ★v1.1★ series-prev/next 边重建（任何 series 页变化 / 删除时都重算，开销极小）
    if series_changed or stats.pages_indexed > 0 or stats.deleted > 0:
        # 先清理旧 series-* 边再重建
        conn.execute(
            "DELETE FROM links WHERE edge_type IN ('series-prev', 'series-next')"
        )
        stats.links_extracted += build_series_implicit_edges(conn)

    set_build_meta(conn, "build_time", time.strftime("%Y-%m-%dT%H:%M:%S"))
    total_pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    total_links = conn.execute("SELECT COUNT(*) FROM links").fetchone()[0]
    set_build_meta(conn, "page_count", str(total_pages))
    set_build_meta(conn, "link_count", str(total_links))

    conn.commit()
    conn.close()

    stats.elapsed_ms = (time.time() - t0) * 1000
    return stats


def check_rebuild_needed(docs_root: Path, db_path: Path) -> tuple[bool, str]:
    """检查是否需要重建。"""
    if not db_path.exists():
        return True, "database does not exist"

    conn = open_database(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM build_meta WHERE key='schema_version'"
        ).fetchone()
        ver = row[0] if row else "0"
    except sqlite3.OperationalError:
        ver = "0"
    if ver != SCHEMA_VERSION:
        conn.close()
        return True, f"schema version mismatch ({ver} != {SCHEMA_VERSION})"

    stored_hashes = get_stored_hashes(conn)
    conn.close()

    records = collect_pages(docs_root)
    current_ids: set[str] = set()

    for record in records:
        current_ids.add(record.id)
        stored_hash = stored_hashes.get(record.id, "")
        if stored_hash != record.content_hash:
            return True, f"page changed: {record.id}"

    for old_id in stored_hashes:
        if old_id not in current_ids:
            return True, f"page deleted: {old_id}"

    return False, "all pages up-to-date"


# ---------------------------------------------------------------------------
# Tier 2: 向量索引构建
# ---------------------------------------------------------------------------

def _load_embedding_module():
    """Lazy import wiki_embeddings。"""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    from wiki_embeddings import (
        EmbeddingConfig, chunk_page, create_provider,
        embed_chunks_batched, embedding_to_blob,
    )
    return EmbeddingConfig, chunk_page, create_provider, embed_chunks_batched, embedding_to_blob


def init_vec_table(conn: sqlite3.Connection, dimensions: int) -> bool:
    """初始化 sqlite-vec 虚拟表。"""
    if not _SQLITE_VEC_AVAILABLE:
        return False
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception as e:
        print(f"  [warn] sqlite-vec load failed: {e}", file=sys.stderr)
        return False

    conn.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks
        USING vec0(embedding float[{dimensions}])
    """)
    return True


def build_vectors(docs_root: Path, db_path: Path, config: dict) -> BuildStats:
    """构建向量索引：分块 → 嵌入 → 写入 chunks + vec_chunks。"""
    stats = BuildStats()
    t0 = time.time()

    try:
        EmbeddingConfig, chunk_page, create_provider, embed_chunks_batched, embedding_to_blob = \
            _load_embedding_module()
    except ImportError as e:
        print(f"[wiki_rebuild] error: cannot import wiki_embeddings: {e}", file=sys.stderr)
        stats.elapsed_ms = (time.time() - t0) * 1000
        return stats

    embed_cfg_raw = config.get("retrieval", {}).get("embedding", {})
    embed_cfg = EmbeddingConfig.from_dict(embed_cfg_raw)
    provider = create_provider(embed_cfg)
    available, reason = provider.is_available()
    if not available:
        print(f"[wiki_rebuild] error: embedding provider not available: {reason}",
              file=sys.stderr)
        stats.elapsed_ms = (time.time() - t0) * 1000
        return stats

    if not db_path.exists():
        print("[wiki_rebuild] error: wiki.db not found. Run full rebuild first.",
              file=sys.stderr)
        stats.elapsed_ms = (time.time() - t0) * 1000
        return stats

    conn = open_database(db_path)
    conn.executescript(CHUNKS_SCHEMA_SQL)

    vec_available = init_vec_table(conn, embed_cfg.dimensions)
    if not vec_available:
        print("  [warn] sqlite-vec not available; storing embeddings in chunks.embedding only",
              file=sys.stderr)

    rows = conn.execute(
        "SELECT id, description, body_text FROM pages"
    ).fetchall()
    if not rows:
        print("[wiki_rebuild] warn: no pages in database", file=sys.stderr)
        conn.close()
        stats.elapsed_ms = (time.time() - t0) * 1000
        return stats

    conn.execute("DELETE FROM chunks")
    if vec_available:
        conn.execute("DROP TABLE IF EXISTS vec_chunks")
        conn.execute(f"""
            CREATE VIRTUAL TABLE vec_chunks
            USING vec0(embedding float[{embed_cfg.dimensions}])
        """)
    conn.commit()

    all_chunks = []
    for row in rows:
        page_id, description, body_text = row
        page_chunks = chunk_page(page_id, description or "", body_text or "")
        all_chunks.extend(page_chunks)

    print(f"  Chunked {len(rows)} pages → {len(all_chunks)} chunks")
    stats.chunks_created = len(all_chunks)
    if not all_chunks:
        conn.close()
        stats.elapsed_ms = (time.time() - t0) * 1000
        return stats

    def progress_cb(done: int, total: int):
        print(f"  Embedding: {done}/{total}", end="\r", flush=True)

    results = embed_chunks_batched(
        provider, all_chunks,
        batch_size=embed_cfg.batch_size,
        on_progress=progress_cb,
    )
    print()

    for chunk, embedding in results:
        blob = embedding_to_blob(embedding)
        conn.execute("""
            INSERT OR REPLACE INTO chunks (page_id, chunk_index, chunk_text, token_count, embedding)
            VALUES (?, ?, ?, ?, ?)
        """, (chunk.page_id, chunk.chunk_index, chunk.chunk_text, chunk.token_count, blob))
    conn.commit()

    if vec_available:
        chunk_rows = conn.execute(
            "SELECT id, embedding FROM chunks WHERE embedding IS NOT NULL"
        ).fetchall()
        for row_id, emb_blob in chunk_rows:
            if emb_blob:
                conn.execute(
                    "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                    (row_id, emb_blob),
                )
        conn.commit()

    stats.vectors_built = len(results)

    set_build_meta(conn, "vectors_built_time", time.strftime("%Y-%m-%dT%H:%M:%S"))
    set_build_meta(conn, "vector_count", str(stats.vectors_built))
    set_build_meta(conn, "embedding_model", embed_cfg.model)
    set_build_meta(conn, "embedding_dimensions", str(embed_cfg.dimensions))
    set_build_meta(conn, "sqlite_vec_available", str(vec_available))
    conn.commit()
    conn.close()

    stats.elapsed_ms = (time.time() - t0) * 1000
    print(f"  Vectors: {stats.vectors_built}/{stats.chunks_created} chunks embedded "
          f"[{stats.elapsed_ms:.0f}ms]")
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="wiki_rebuild.py",
        description="LyraStarterGame project-wiki Tier 1/2 索引构建器",
    )
    ap.add_argument(
        "--docs-root", default=None,
        help=f"Docs/ 根目录（默认: {DOCS_DIR}）",
    )
    ap.add_argument(
        "--db-path", default=None,
        help="自定义数据库路径（默认: .codebuddy/skills/project-wiki/.cache/wiki.db）",
    )
    ap.add_argument(
        "--incremental", action="store_true",
        help="增量模式：只更新变更文件",
    )
    ap.add_argument(
        "--check", action="store_true",
        help="检查模式：是否需要重建（exit 0=不需要 / 1=需要）",
    )
    ap.add_argument(
        "--with-vectors", action="store_true",
        help="全量重建后同时构建向量索引（需要 embedding API）",
    )
    ap.add_argument(
        "--vectors-only", action="store_true",
        help="只重建向量（pages 表必须已存在）",
    )
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    ap = build_argparser()
    args = ap.parse_args(argv)

    docs_root = Path(args.docs_root) if args.docs_root else DOCS_DIR
    if not docs_root.is_dir():
        print(f"[wiki_rebuild] error: Docs root not found: {docs_root}", file=sys.stderr)
        return 2

    config = load_config()
    db_path = resolve_db_path(config, args.db_path)

    if args.check:
        needed, reason = check_rebuild_needed(docs_root, db_path)
        if needed:
            print(f"Rebuild needed: {reason}")
            return 1
        print(f"No rebuild needed: {reason}")
        return 0

    if args.vectors_only:
        if not db_path.exists():
            print("[wiki_rebuild] error: database not found. Run full rebuild first.",
                  file=sys.stderr)
            return 2
        print("Vector-only rebuild...")
        vstats = build_vectors(docs_root, db_path, config)
        if vstats.vectors_built == 0:
            print("[wiki_rebuild] warn: no vectors were built (check API config)",
                  file=sys.stderr)
            return 1
        return 0

    if args.incremental:
        stats = build_incremental(docs_root, db_path)
        mode = "Incremental"
    else:
        stats = build_full(docs_root, db_path)
        mode = "Full"

    print(
        f"Rebuilt wiki.db ({mode}): "
        f"{stats.pages_indexed} pages indexed, "
        f"{stats.links_extracted} edges extracted, "
        f"{stats.skipped_unchanged} skipped (unchanged)"
        + (f", {stats.deleted} deleted" if stats.deleted else "")
        + f" [{stats.elapsed_ms:.0f}ms]"
    )
    print(f"  → {db_path.relative_to(REPO_ROOT) if db_path.is_relative_to(REPO_ROOT) else db_path}")

    if args.with_vectors:
        print("Building vectors...")
        sys.stdout.flush()
        vstats = build_vectors(docs_root, db_path, config)
        if vstats.vectors_built == 0:
            print("[wiki_rebuild] warn: no vectors were built (check API config or network)",
                  file=sys.stderr)
        else:
            stats.chunks_created = vstats.chunks_created
            stats.vectors_built = vstats.vectors_built

    return 0


if __name__ == "__main__":
    sys.exit(main())
