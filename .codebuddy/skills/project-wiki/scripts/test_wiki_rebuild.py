#!/usr/bin/env python3
"""test_wiki_rebuild.py — wiki_rebuild.py 单元/集成测试。

可独立运行：
    python3 .codebuddy/skills/project-wiki/scripts/test_wiki_rebuild.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import wiki_rebuild  # noqa: E402
import wiki_query  # noqa: E402


REPO_ROOT = SCRIPTS_DIR.parents[2].parent  # repo
DOCS_DIR = REPO_ROOT / "Docs"


def _temp_db() -> Path:
    return Path(tempfile.mktemp(suffix=".db"))


# ---------------------------------------------------------------------------
# 单元：utility
# ---------------------------------------------------------------------------

def test_infer_category():
    assert wiki_rebuild.infer_category("30-tutorials/gas/01-foo") == "30-tutorials"
    assert wiki_rebuild.infer_category("60-decisions/0001-bar") == "60-decisions"
    assert wiki_rebuild.infer_category("unknown/foo/bar") == ""


def test_infer_domain():
    assert wiki_rebuild.infer_domain("30-tutorials/gas/01-foo") == "gas"
    assert wiki_rebuild.infer_domain("10-architecture/overview") == "overview"
    assert wiki_rebuild.infer_domain("foo") == ""


def test_cjk_space_insert():
    assert wiki_rebuild.cjk_space_insert("封装层") == "封 装 层"
    assert wiki_rebuild.cjk_space_insert("GAS的封装") == "GAS 的 封 装"
    assert wiki_rebuild.cjk_space_insert("ability system") == "ability system"


def test_normalize_link_id():
    assert wiki_rebuild.normalize_link_id("[[30-tutorials/gas/01]]") == "30-tutorials/gas/01"
    assert wiki_rebuild.normalize_link_id("30-tutorials/gas/01|alias") == "30-tutorials/gas/01"
    assert wiki_rebuild.normalize_link_id("30-tutorials/gas/01#anchor") == "30-tutorials/gas/01"


def test_should_exclude():
    assert wiki_rebuild.should_exclude("_raw/spec.md", "spec.md")
    assert wiki_rebuild.should_exclude("log.d/log-foo.md", "log-foo.md")
    assert wiki_rebuild.should_exclude("index.md", "index.md")  # 顶层 meta
    assert not wiki_rebuild.should_exclude("30-tutorials/gas/01-foo.md", "01-foo.md")


# ---------------------------------------------------------------------------
# 集成：build_full
# ---------------------------------------------------------------------------

def test_build_creates_valid_db():
    db = _temp_db()
    try:
        stats = wiki_rebuild.build_full(DOCS_DIR, db)
        assert db.exists()
        assert stats.pages_indexed > 0, f"no pages: {stats.pages_indexed}"
        assert stats.links_extracted > 0

        conn = sqlite3.connect(str(db))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        assert {"pages", "links", "build_meta"} <= tables, f"missing tables: {tables}"
        print(f"  PASS: {stats.pages_indexed} pages, {stats.links_extracted} edges")
    finally:
        if db.exists():
            db.unlink()


def test_pages_have_tutorial_fields():
    """教程页应正确填入 series / lesson_index / prerequisites。"""
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        # 至少应该有一个 series=gas 的教程
        row = conn.execute("""
            SELECT id, series, lesson_index, prerequisites
            FROM pages WHERE series = 'gas' AND lesson_index >= 0
            ORDER BY lesson_index LIMIT 1
        """).fetchone()
        conn.close()
        assert row is not None, "no gas series tutorials found"
        assert row["series"] == "gas"
        assert row["lesson_index"] >= 0
        # prerequisites 应该是合法 JSON 数组
        prereqs = json.loads(row["prerequisites"] or "[]")
        assert isinstance(prereqs, list)
        print(f"  PASS: gas series 教程字段正确 (id={row['id']}, lesson={row['lesson_index']})")
    finally:
        if db.exists():
            db.unlink()


def test_fts5_query():
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        results = wiki_query.query_database(db, ["ability"], max_candidates=10)
        assert len(results) > 0, "FTS5 query returned no results for 'ability'"
        # 至少应该命中 ability-system 架构页或 GAS 教程
        ids = [r.page_id for r in results]
        has_gas = any("ability" in i.lower() or "gas" in i.lower() for i in ids)
        assert has_gas, f"no ability/gas pages in results: {ids[:5]}"
        print(f"  PASS: FTS5 found {len(results)} results, top: {results[0].page_id}")
    finally:
        if db.exists():
            db.unlink()


def test_fts5_chinese_query():
    """中文查询应通过 CJK 预处理命中。"""
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        results = wiki_query.query_database(db, ["网络复制"], max_candidates=5)
        assert len(results) > 0, "中文查询 '网络复制' 返回空"
        # 应该有 GAS 网络复制相关页
        ids = [r.page_id for r in results]
        assert any("网络复制" in i or "复制" in i.lower() for i in ids), f"unexpected: {ids}"
        print(f"  PASS: 中文 FTS5 found {len(results)} results, top: {results[0].page_id}")
    finally:
        if db.exists():
            db.unlink()


def test_links_extraction_with_edge_types():
    """links 表应区分 wikilink / related / prerequisite 三种边类型。"""
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        conn = sqlite3.connect(str(db))
        edge_types = {r[0] for r in conn.execute(
            "SELECT DISTINCT edge_type FROM links"
        ).fetchall()}
        # 至少应有 wikilink；项目教程系列必有 prerequisite
        assert "wikilink" in edge_types
        assert "prerequisite" in edge_types, f"missing prerequisite edges: {edge_types}"
        # related 边可能存在
        prereq_count = conn.execute(
            "SELECT COUNT(*) FROM links WHERE edge_type='prerequisite'"
        ).fetchone()[0]
        conn.close()
        assert prereq_count > 0
        print(f"  PASS: edge types = {edge_types}, prerequisite={prereq_count}")
    finally:
        if db.exists():
            db.unlink()


def test_incremental_skips_unchanged():
    db = _temp_db()
    try:
        s1 = wiki_rebuild.build_full(DOCS_DIR, db)
        s2 = wiki_rebuild.build_incremental(DOCS_DIR, db)
        assert s2.pages_indexed == 0
        assert s2.skipped_unchanged == s1.pages_indexed
        print(f"  PASS: incremental skipped {s2.skipped_unchanged} unchanged pages")
    finally:
        if db.exists():
            db.unlink()


def test_check_rebuild_needed():
    db = _temp_db()
    try:
        needed, _ = wiki_rebuild.check_rebuild_needed(DOCS_DIR, db)
        assert needed, "should need rebuild when DB missing"

        wiki_rebuild.build_full(DOCS_DIR, db)
        needed, _ = wiki_rebuild.check_rebuild_needed(DOCS_DIR, db)
        assert not needed, "should not need rebuild after full build"
        print(f"  PASS: check_rebuild_needed works")
    finally:
        if db.exists():
            db.unlink()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ALL = [
    test_infer_category,
    test_infer_domain,
    test_cjk_space_insert,
    test_normalize_link_id,
    test_should_exclude,
    test_build_creates_valid_db,
    test_pages_have_tutorial_fields,
    test_fts5_query,
    test_fts5_chinese_query,
    test_links_extraction_with_edge_types,
    test_incremental_skips_unchanged,
    test_check_rebuild_needed,
]


def main() -> int:
    print("=" * 60)
    print("wiki_rebuild.py — Test Suite")
    print("=" * 60)
    if not DOCS_DIR.is_dir():
        print(f"SKIP: Docs/ not found at {DOCS_DIR}")
        return 0

    passed = 0
    failed = 0
    errors: list[str] = []
    for t in ALL:
        print(f"\n[TEST] {t.__name__}")
        try:
            t()
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append(f"  FAIL: {t.__name__} — {e}")
            print(f"  FAIL: {e}")
        except Exception as e:
            failed += 1
            errors.append(f"  ERROR: {t.__name__} — {type(e).__name__}: {e}")
            print(f"  ERROR: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if errors:
        print("\nFailures:")
        for e in errors:
            print(e)
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
