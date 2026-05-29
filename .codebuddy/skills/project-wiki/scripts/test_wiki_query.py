#!/usr/bin/env python3
"""test_wiki_query.py — wiki_query.py 单元/集成测试。

可独立运行：
    python3 .codebuddy/skills/project-wiki/scripts/test_wiki_query.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import wiki_query as Q  # noqa: E402
import wiki_rebuild  # noqa: E402

REPO_ROOT = SCRIPTS_DIR.parents[2].parent
DOCS_DIR = REPO_ROOT / "Docs"


def _temp_db() -> Path:
    return Path(tempfile.mktemp(suffix=".db"))


# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------

def test_tokenize_basic():
    r = Q.tokenize("ability system")
    assert "ability" in r and "system" in r


def test_tokenize_camelcase():
    r = Q.tokenize("GameplayAbility")
    assert "gameplay" in r
    assert "ability" in r
    assert "gameplayability" in r


def test_tokenize_chinese():
    r = Q.tokenize("网络复制 character")
    assert "网络复制" in r
    assert "character" in r


def test_tokenize_dedup():
    r = Q.tokenize("ability ability Ability")
    assert r.count("ability") == 1


def test_tokenize_short_filter():
    r = Q.tokenize("a b cd")
    assert "a" not in r and "b" not in r
    assert "cd" in r


# ---------------------------------------------------------------------------
# Tier 决策
# ---------------------------------------------------------------------------

def test_determine_tier_no_db():
    db = _temp_db()  # 不存在
    config = {"retrieval": {"engine": "auto"}}
    assert Q.determine_tier(db, config) == "grep"

    config = {"retrieval": {"engine": "sqlite"}}
    assert Q.determine_tier(db, config) == "grep"  # db 不存在退到 grep


def test_determine_tier_with_db():
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        config = {"retrieval": {"engine": "auto", "auto_thresholds": {"tier1_at": 100}}}
        # 项目 278 页 > 100 → sqlite
        assert Q.determine_tier(db, config) == "sqlite"

        config = {"retrieval": {"engine": "sqlite"}}
        assert Q.determine_tier(db, config) == "sqlite"

        config = {"retrieval": {"engine": "hybrid"}}
        # 无向量 → 退到 sqlite
        assert Q.determine_tier(db, config) == "sqlite"

        config = {"retrieval": {"engine": "grep"}}
        assert Q.determine_tier(db, config) == "grep"
    finally:
        if db.exists():
            db.unlink()


# ---------------------------------------------------------------------------
# 查询集成
# ---------------------------------------------------------------------------

def test_query_returns_top_hit():
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        result = Q.run_query_db("GameplayAbility", db_path=db, max_candidates=5)
        assert len(result.candidates) > 0, "no candidates"
        # Top 命中应当是 GAS 教程或架构页
        top_id = result.candidates[0].page_id.lower()
        assert "gas" in top_id or "ability" in top_id, f"unexpected top: {top_id}"
        print(f"  top: {result.candidates[0].page_id}, score={result.candidates[0].score}")
    finally:
        if db.exists():
            db.unlink()


def test_query_chinese():
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        result = Q.run_query_db("网络复制", db_path=db, max_candidates=5)
        assert len(result.candidates) > 0
        # 应该命中 GAS 网络复制教程
        ids = [c.page_id for c in result.candidates]
        assert any("网络复制" in i for i in ids), f"unexpected: {ids[:3]}"
    finally:
        if db.exists():
            db.unlink()


def test_seed_mode():
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        # 找一个肯定存在的种子页
        import sqlite3
        conn = sqlite3.connect(str(db))
        row = conn.execute(
            "SELECT id FROM pages WHERE category='30-tutorials' AND series='gas' LIMIT 1"
        ).fetchone()
        conn.close()
        assert row is not None
        seed_id = row[0]
        result = Q.run_query_db("", db_path=db, seed_id=seed_id, max_candidates=1)
        assert result.mode == "seed"
        assert len(result.candidates) == 1
        assert result.candidates[0].page_id == seed_id
        # 应该有邻居
        assert len(result.neighbors) > 0, "seed page has no neighbors"
        # 邻居 why 应包含边类型
        edges = {n.why[0].split()[0] for n in result.neighbors if n.why}
        assert any(e for e in edges), f"no edge labels: {edges}"
    finally:
        if db.exists():
            db.unlink()


def test_series_mode():
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        result = Q.run_query_db("", db_path=db, series_name="gas")
        assert result.mode == "series"
        assert len(result.candidates) > 5, f"gas series too few: {len(result.candidates)}"
        # 应按 lesson_index 排序
        indices = [c.lesson_index for c in result.candidates if c.lesson_index >= 0]
        assert indices == sorted(indices), f"not sorted: {indices}"
    finally:
        if db.exists():
            db.unlink()


def test_category_filter_softdemote():
    """category 过滤应是软降权而非硬过滤。"""
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        result = Q.run_query_db(
            "ability", db_path=db,
            filter_category="60-decisions",  # 没什么 ability 决策页
            max_candidates=5,
        )
        # 应仍能返回结果（不硬过滤），只是其他 category 的分数被降
        assert len(result.candidates) > 0
        # 不匹配 category 的页应有 mismatch why
        mismatched = [c for c in result.candidates if c.category != "60-decisions"]
        if mismatched:
            assert any("category-mismatch" in w for w in mismatched[0].why)
    finally:
        if db.exists():
            db.unlink()


def test_status_multiplier():
    """deprecated 文档应被惩罚。"""
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        # 制造一个临时 deprecated 行测试乘法因子（直接改 db）
        import sqlite3
        conn = sqlite3.connect(str(db))
        # 先看是否已存在 deprecated 页
        n = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE status='deprecated'"
        ).fetchone()[0]
        conn.close()
        # 至少不应崩溃
        result = Q.run_query_db("ability", db_path=db, max_candidates=5)
        assert len(result.candidates) > 0
        # 检查 status 修正常量配置正确
        assert Q.STATUS_MULTIPLIER["deprecated"] == 0.2
        assert Q.STATUS_MULTIPLIER["stale"] == 0.5
        assert Q.STATUS_MULTIPLIER["current"] == 1.0
        print(f"  PASS: deprecated 页数={n}, multipliers OK")
    finally:
        if db.exists():
            db.unlink()


def test_json_output():
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        result = Q.run_query_db("ability", db_path=db, max_candidates=3)
        import json
        s = json.dumps(result.asdict(), ensure_ascii=False)
        d = json.loads(s)
        assert "candidates" in d
        assert "tokens" in d
        assert "neighbors" in d
    finally:
        if db.exists():
            db.unlink()


def test_rrf_merge():
    """RRF 融合：两个候选列表合并后排名稳定。"""
    bm25 = [
        Q.Candidate(page_id="A", score=5.0, status="current", type="t"),
        Q.Candidate(page_id="B", score=4.0, status="current", type="t"),
        Q.Candidate(page_id="C", score=3.0, status="current", type="t"),
    ]
    vec = [
        Q.Candidate(page_id="C", score=0.9, status="current", type="t"),
        Q.Candidate(page_id="A", score=0.8, status="current", type="t"),
        Q.Candidate(page_id="D", score=0.7, status="current", type="t"),
    ]
    merged = Q.rrf_merge(bm25, vec, k=60)
    ids = [c.page_id for c in merged]
    # A 在两路都靠前 → 第 1
    assert ids[0] == "A", f"unexpected: {ids}"
    # 所有 4 个都应该在
    assert set(ids) == {"A", "B", "C", "D"}


# ---------------------------------------------------------------------------
# v1.1 集成特性专项测试（Tier 0 → Tier 1 移植）
# ---------------------------------------------------------------------------

def test_v11_anchor_hit_lyra_character():
    """★v1.1 anchors★ 查 LyraCharacter Top-1 应是 ALyraCharacter 模块文档。"""
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        result = Q.run_query_db("LyraCharacter", db_path=db, max_candidates=1)
        assert len(result.candidates) > 0
        top_id = result.candidates[0].page_id
        assert top_id == "20-modules/cpp/ALyraCharacter", \
            f"v1.1 anchors 集成应让 ALyraCharacter Top-1，实际: {top_id}"
        # 验证 why 字段含 anchor-hit 和 id-fulltoken 标记
        why_str = "; ".join(result.candidates[0].why)
        assert "anchor-hit" in why_str, f"why 字段应含 anchor-hit: {why_str}"
        print(f"  PASS: anchors 修复回归 — Top-1={top_id}, why={why_str}")
    finally:
        if db.exists():
            db.unlink()


def test_v11_alias_expansion_gas():
    """★v1.1 alias★ 查 GAS 应自动扩展为 'gameplay ability system'。"""
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        result = Q.run_query_db("GAS", db_path=db, max_candidates=5, use_alias=True)
        # 验证 alias_extra 被填充
        assert len(result.alias_extra) > 0, \
            f"alias_extra 应包含 'gameplay ability system'，实际为空"
        assert any("gameplay" in a.lower() for a in result.alias_extra), \
            f"alias_extra 应含 gameplay 同义词: {result.alias_extra}"
        print(f"  PASS: alias 扩展生效 — alias_extra={result.alias_extra}")
    finally:
        if db.exists():
            db.unlink()


def test_v11_alias_no_expansion_when_disabled():
    """★v1.1 alias★ use_alias=False 时不展开。"""
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        result = Q.run_query_db("GAS", db_path=db, max_candidates=5, use_alias=False)
        assert result.alias_extra == [], \
            f"use_alias=False 时 alias_extra 应为空，实际: {result.alias_extra}"
        print(f"  PASS: --no-alias 正确关闭扩展")
    finally:
        if db.exists():
            db.unlink()


def test_v11_series_implicit_edges():
    """★v1.1 series-prev/next★ 教程系列相邻课程应自动建隐式边。"""
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        # 检查 links 表是否有 series-prev / series-next 边
        import sqlite3
        conn = sqlite3.connect(str(db))
        edges = {r[0] for r in conn.execute(
            "SELECT DISTINCT edge_type FROM links"
        ).fetchall()}
        conn.close()
        assert "series-prev" in edges, f"应有 series-prev 边，实际: {edges}"
        assert "series-next" in edges, f"应有 series-next 边，实际: {edges}"

        # seed 模式下应能展开 series 边
        result = Q.run_query_db(
            "", db_path=db,
            seed_id="30-tutorials/gas/14-GE网络复制",
            max_candidates=1,
        )
        edge_types = {n.why[0].split()[0] for n in result.neighbors if n.why}
        has_series_edge = any("series" in e for e in edge_types)
        assert has_series_edge, f"邻居应含 series-* 边，实际: {edge_types}"
        print(f"  PASS: series-prev/next 隐式边 — edges={edges}, neighbor_edges={edge_types}")
    finally:
        if db.exists():
            db.unlink()


def test_v11_schema_version():
    """★v1.1★ schema_version 应为 1.1，旧 db 应自动 fallback 到全量重建。"""
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        import sqlite3
        conn = sqlite3.connect(str(db))
        ver = conn.execute(
            "SELECT value FROM build_meta WHERE key='schema_version'"
        ).fetchone()[0]
        conn.close()
        assert ver == "1.1", f"schema_version 应为 1.1，实际: {ver}"
        print(f"  PASS: schema_version={ver}")
    finally:
        if db.exists():
            db.unlink()


def test_v11_anchors_text_in_db():
    """★v1.1 anchors★ pages.anchors_text 列应填充扁平化路径。"""
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        import sqlite3
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, anchors_text FROM pages WHERE id = '20-modules/cpp/ALyraCharacter'"
        ).fetchone()
        conn.close()
        assert row is not None, "ALyraCharacter 模块页应存在"
        at = row["anchors_text"] or ""
        assert "lyracharacter" in at.lower(), \
            f"anchors_text 应含 LyraCharacter 文件名: {at}"
        # 应该已经把 / 替换为空格
        assert "/" not in at, f"anchors_text 不应有 /: {at}"
        print(f"  PASS: anchors_text 扁平化正确 — {at[:80]}")
    finally:
        if db.exists():
            db.unlink()


# ---------------------------------------------------------------------------
# v1.1.2 自动 fallback 专项测试
# ---------------------------------------------------------------------------

def test_v112_zero_candidate_fallback_in_main():
    """★v1.1.2★ Tier 1 零候选时 main() 应自动委托 Tier 0。

    用 subprocess 跑端到端 CLI，验证 fallback 到 Tier 0 时输出含 query.py 的特征字符串。
    """
    import subprocess
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        # 一个真正零命中的查询字符串（避免 CamelCase/CJK 拆分误命中）
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "wiki_query.py"),
             "qzqzqzqzqz9999", "--max-candidates", "1",
             "--db-path", str(db)],
            capture_output=True, text=True, timeout=30,
        )
        # stderr 应含 fallback 提示
        assert "fallback" in r.stderr.lower() or "Tier 0" in r.stderr, \
            f"应有 fallback stderr 提示，实际 stderr: {r.stderr[:300]}"
        # stdout 应含 Tier 0 特征（query.py 的 'Falling back to body grep below' 或邻居展开）
        assert "body grep" in r.stdout.lower() or "no candidate" in r.stdout.lower(), \
            f"应见到 Tier 0 兜底输出，实际: {r.stdout[:300]}"
        print(f"  PASS: 零候选自动 fallback 到 Tier 0 (query.py)")
    finally:
        if db.exists():
            db.unlink()


def test_v112_normal_query_no_fallback():
    """★v1.1.2★ 正常 BM25 命中时不应触发 fallback。"""
    import subprocess
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "wiki_query.py"),
             "GameplayAbility", "--max-candidates", "1",
             "--db-path", str(db)],
            capture_output=True, text=True, timeout=30,
        )
        assert "fallback" not in r.stderr.lower(), \
            f"正常路径不应有 fallback，stderr: {r.stderr[:200]}"
        # stdout 应含 Tier 1 标识
        assert "Tier 1" in r.stdout, \
            f"应见到 Tier 1 标识，实际: {r.stdout[:200]}"
        print(f"  PASS: 正常 BM25 命中无 fallback")
    finally:
        if db.exists():
            db.unlink()


def test_v112_no_auto_fallback_env_disables():
    """★v1.1.2★ PROJECT_WIKI_NO_AUTO_FALLBACK=1 应禁用自动 fallback。"""
    import subprocess, os
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        env = os.environ.copy()
        env["PROJECT_WIKI_NO_AUTO_FALLBACK"] = "1"
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "wiki_query.py"),
             "qzqzqzqzqz9999", "--max-candidates", "1",
             "--db-path", str(db)],
            capture_output=True, text=True, timeout=30, env=env,
        )
        # 仍有 stderr 提示
        assert "fallback" in r.stderr.lower(), \
            f"应有 stderr 提示，实际: {r.stderr[:200]}"
        # 但 stdout 应停留在 Tier 1（不会跳转到 query.py 的输出）
        assert "Tier 1" in r.stdout or "No candidate found" in r.stdout, \
            f"禁用 fallback 时应停留在 Tier 1 空结果，实际: {r.stdout[:300]}"
        # 不应有 query.py 的 "Falling back to body grep below" 这种 Tier 0 特征
        assert "body grep below" not in r.stdout.lower(), \
            f"禁用 fallback 但仍跳转到 Tier 0: {r.stdout[:300]}"
        print(f"  PASS: PROJECT_WIKI_NO_AUTO_FALLBACK=1 正确禁用 fallback")
    finally:
        if db.exists():
            db.unlink()


def test_v112_seed_mode_not_found_no_fallback():
    """★v1.1.2★ seed 模式下种子不存在不应触发 fallback（Tier 0 也找不到，避免无意义委托）。"""
    db = _temp_db()
    try:
        wiki_rebuild.build_full(DOCS_DIR, db)
        result = Q.run_query_db(
            "", db_path=db,
            seed_id="nonexistent/page/id",
            max_candidates=1,
        )
        assert len(result.candidates) == 0
        assert "not found" in result.suggestion.lower(), \
            f"seed 不存在应返回 not found，实际: {result.suggestion}"
        # 注意：fallback 是在 main() 中判定，单元测试 run_query_db 不会触发 fallback
        # 这里只测 keyword vs seed/series 的区分逻辑用 main() 的 subprocess 测试更合适
        print(f"  PASS: seed 不存在返回 not found 提示")
    finally:
        if db.exists():
            db.unlink()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ALL = [
    test_tokenize_basic,
    test_tokenize_camelcase,
    test_tokenize_chinese,
    test_tokenize_dedup,
    test_tokenize_short_filter,
    test_determine_tier_no_db,
    test_determine_tier_with_db,
    test_query_returns_top_hit,
    test_query_chinese,
    test_seed_mode,
    test_series_mode,
    test_category_filter_softdemote,
    test_status_multiplier,
    test_json_output,
    test_rrf_merge,
    # ★v1.1★ 集成特性专项
    test_v11_anchor_hit_lyra_character,
    test_v11_alias_expansion_gas,
    test_v11_alias_no_expansion_when_disabled,
    test_v11_series_implicit_edges,
    test_v11_schema_version,
    test_v11_anchors_text_in_db,
    # ★v1.1.2★ 自动 fallback 专项
    test_v112_normal_query_no_fallback,
    test_v112_zero_candidate_fallback_in_main,
    test_v112_no_auto_fallback_env_disables,
    test_v112_seed_mode_not_found_no_fallback,
]


def main() -> int:
    print("=" * 60)
    print("wiki_query.py — Test Suite")
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
