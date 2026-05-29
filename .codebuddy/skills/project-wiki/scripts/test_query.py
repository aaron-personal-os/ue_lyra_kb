#!/usr/bin/env python3
"""单元测试 query.py（v1.0 LyraStarterGame 定制版）。

覆盖：
    - tokenize / 别名扩展 (parse_aliases / expand_tokens_with_alias)
    - normalize_wikilink_id
    - parse_index（本项目简化格式 + 兼容旧元组格式）
    - 边收集：related / prerequisites / anchors / series / lesson_index
    - inverse-prerequisites / series_index 构建
    - score_against_index_entry / score_against_page（含 anchors / type / boost）
    - status_warning + STATUS_MULTIPLIER
    - run_query 三种模式：keyword / seed / series（基于真实 Docs/ 集成 smoke）

跑法：
    python3 .codebuddy/skills/project-wiki/scripts/test_query.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SCRIPTS = REPO / ".codebuddy" / "skills" / "project-wiki" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import query as Q  # noqa: E402
import wiki_lint as L  # noqa: E402


# ---------------------------------------------------------------------------
# 断言辅助
# ---------------------------------------------------------------------------

_PASS = 0
_FAIL = 0


def assert_eq(actual, expected, what: str):
    global _PASS, _FAIL
    if actual == expected:
        print(f"  [OK] {what}")
        _PASS += 1
    else:
        print(f"  [FAIL] {what}: actual={actual!r} expected={expected!r}")
        _FAIL += 1


def assert_in(needle, haystack, what: str):
    global _PASS, _FAIL
    if needle in haystack:
        print(f"  [OK] {what}")
        _PASS += 1
    else:
        print(f"  [FAIL] {what}: {needle!r} not in {haystack!r}")
        _FAIL += 1


def assert_true(cond, what: str):
    global _PASS, _FAIL
    if cond:
        print(f"  [OK] {what}")
        _PASS += 1
    else:
        print(f"  [FAIL] {what}: condition is False")
        _FAIL += 1


# ---------------------------------------------------------------------------
# 工具：构造一个最小 WikiPage（不读盘）
# ---------------------------------------------------------------------------

def make_page(page_id: str, fm: dict, text: str = "") -> L.WikiPage:
    body = text or "# placeholder\n"
    return L.WikiPage(
        path=Path(f"/tmp/{page_id}.md"),
        rel=f"Docs/{page_id}.md",
        page_id=page_id,
        text=body,
        fm=fm,
        fm_lines=0,
    )


# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------

def test_tokenize():
    print("\n=== tokenize ===")
    assert_eq(Q.tokenize("spline procedural building"),
              ["spline", "procedural", "building"], "basic split")
    assert_eq(Q.tokenize("Spline Procedural BUILDING"),
              ["spline", "procedural", "building"], "case lowered")
    assert_eq(Q.tokenize("PCG, 样条, building"),
              ["pcg", "样条", "building"], "mixed cn/en + comma")
    assert_eq(Q.tokenize("a b cd"), ["cd"], "filter token len < 2")
    assert_eq(Q.tokenize("foo foo Foo"), ["foo"], "dedup")
    assert_eq(Q.tokenize(""), [], "empty input")
    assert_eq(Q.tokenize("  ,，;； \t  "), [], "whitespace + punct only")


# ---------------------------------------------------------------------------
# normalize_wikilink_id
# ---------------------------------------------------------------------------

def test_normalize_wikilink_id():
    print("\n=== normalize_wikilink_id ===")
    assert_eq(Q.normalize_wikilink_id("[[60-topics/foo]]"),
              "60-topics/foo", "strip [[ ]]")
    assert_eq(Q.normalize_wikilink_id("60-topics/foo"),
              "60-topics/foo", "no brackets")
    assert_eq(Q.normalize_wikilink_id("[[60-topics/foo|alias]]"),
              "60-topics/foo", "strip alias")
    assert_eq(Q.normalize_wikilink_id("[[60-topics/foo#section]]"),
              "60-topics/foo", "strip anchor")
    assert_eq(Q.normalize_wikilink_id("  [[a/b]]  "), "a/b", "outer whitespace")


# ---------------------------------------------------------------------------
# parse_index：本项目简化格式 + 兼容元组
# ---------------------------------------------------------------------------

def test_parse_index_simple_format():
    """本项目实际格式：`- [[id]] - desc`，无 (type, status, date) 元组。"""
    print("\n=== parse_index (本项目简化格式) ===")
    with tempfile.TemporaryDirectory() as tmp:
        idx = Path(tmp) / "index.md"
        idx.write_text("""# 目录

- [[overview]] - 项目顶层概览
- [[10-architecture/overview]] - 架构概览
- [[30-tutorials/gas/19-Tag网络复制]] - GAS Tag 网络复制详解
- [[20-modules/cpp/ALyraCharacter]] - Lyra 角色基类

不是条目的行
- 普通列表项不是 wiki 条目
""", encoding="utf-8")
        entries = Q.parse_index(idx)
        ids = [e.page_id for e in entries]
        assert_eq(len(entries), 4, "parse 4 simple-format entries")
        assert_in("overview", ids, "id overview present")
        assert_in("30-tutorials/gas/19-Tag网络复制", ids, "Chinese id present")
        desc_map = {e.page_id: e.description for e in entries}
        assert_eq(desc_map["overview"], "项目顶层概览", "desc parsed")
        assert_eq(desc_map["30-tutorials/gas/19-Tag网络复制"],
                  "GAS Tag 网络复制详解", "Chinese desc parsed")


def test_parse_index_legacy_tuple_format():
    """兼容旧版 `(type, status, YYYY-MM-DD)` 元组格式（移植版用过）。"""
    print("\n=== parse_index (兼容元组格式) ===")
    with tempfile.TemporaryDirectory() as tmp:
        idx = Path(tmp) / "index.md"
        idx.write_text("""
- [[60-topics/foo]] — 描述 (topic, current, 2026-05-13)
- [[60-topics/bar]] — 没有元数据
- [[40-runbooks/baz]] — runbook (runbook, draft, 2026-05-14)
""", encoding="utf-8")
        entries = Q.parse_index(idx)
        assert_eq(len(entries), 3, "parse 3 legacy entries")
        # 元组格式仍可解析（type/status/date 不再写入 IndexEntry，但行不丢）
        ids = [e.page_id for e in entries]
        assert_in("60-topics/foo", ids, "tuple-format id parsed")


def test_parse_index_dedup():
    """同一 id 出现两次（如某页同时挂在多个分类下），只保留第一次。"""
    print("\n=== parse_index dedup ===")
    with tempfile.TemporaryDirectory() as tmp:
        idx = Path(tmp) / "index.md"
        idx.write_text("""
- [[60-topics/foo]] - 第一次出现

## 别处

- [[60-topics/foo]] - 第二次出现（应忽略）
""", encoding="utf-8")
        entries = Q.parse_index(idx)
        assert_eq(len(entries), 1, "dedup keeps first")
        assert_eq(entries[0].description, "第一次出现", "first occurrence wins")


# ---------------------------------------------------------------------------
# alias 扩展
# ---------------------------------------------------------------------------

def test_parse_aliases_and_expand():
    print("\n=== parse_aliases + expand_tokens_with_alias ===")
    with tempfile.TemporaryDirectory() as tmp:
        schema = Path(tmp) / ".wiki-schema.md"
        schema.write_text("""# Schema

## 别名词表（Alias Table）

```
Lyra = LyraStarterGame = UE5 示例项目
GAS = Gameplay Ability System
StateTree = 状态树（UE 5.x 新行为树）
```

## 下一节
""", encoding="utf-8")
        groups = Q.parse_aliases(schema)
        assert_true(len(groups) == 3, "parse 3 alias groups")
        # 找 GAS 那组
        gas_group = next((g for g in groups if "gas" in g), None)
        assert_true(gas_group is not None, "gas alias group exists")
        assert_in("gameplay ability system", gas_group, "GAS aliased to full name")

        # 扩展：用户输入 "gas" → 应自动加入 "gameplay ability system"
        expanded, extra = Q.expand_tokens_with_alias(["gas"], groups)
        assert_in("gameplay ability system", expanded, "expanded contains alias")
        assert_in("gameplay ability system", extra, "extra reports alias-only token")

        # StateTree 含括注，应被剥离后解析
        st_group = next((g for g in groups if "statetree" in g), None)
        assert_true(st_group is not None, "statetree group exists")
        assert_in("状态树", st_group, "Chinese alias parsed (paren stripped)")


def test_expand_no_alias_match():
    print("\n=== expand_tokens_with_alias no-match ===")
    groups = [{"gas", "gameplay ability system"}]
    expanded, extra = Q.expand_tokens_with_alias(["spline"], groups)
    assert_eq(expanded, ["spline"], "no expansion when no match")
    assert_eq(extra, [], "no extra")


# ---------------------------------------------------------------------------
# 边收集：related / prerequisites / anchors / series / lesson_index
# ---------------------------------------------------------------------------

def test_collect_edges():
    print("\n=== collect related / prerequisites / anchors / series ===")
    page = make_page("30-tutorials/gas/19-Tag网络复制", fm={
        "id": "30-tutorials/gas/19-Tag网络复制",
        "type": "tutorial",
        "status": "current",
        "series": "gas",
        "lesson_index": 19,
        "prerequisites": ["30-tutorials/gas/18-tag-query"],
        "related": ["[[30-tutorials/gas/14-GE网络复制]]", "30-tutorials/gas/15-Tag简介与配置"],
        "anchors": [{"path": "Source/LyraGame/Foo.cpp"}, {"path": "Source/LyraGame/Bar.h"}],
        "tags": ["GAS", "GameplayTag", "网络复制"],
    })
    assert_eq(Q.collect_related(page),
              ["30-tutorials/gas/14-GE网络复制", "30-tutorials/gas/15-Tag简介与配置"],
              "related normalized (strip [[ ]])")
    assert_eq(Q.collect_prerequisites(page),
              ["30-tutorials/gas/18-tag-query"],
              "prerequisites normalized")
    assert_eq(Q.collect_anchors(page),
              ["Source/LyraGame/Foo.cpp", "Source/LyraGame/Bar.h"],
              "anchors paths from list-of-dict")
    assert_eq(Q.collect_series(page), "gas", "series")
    assert_eq(Q.collect_lesson_index(page), 19, "lesson_index int")
    assert_eq(Q.collect_tags(page),
              ["GAS", "GameplayTag", "网络复制"], "tags")


def test_collect_lesson_index_edge_cases():
    print("\n=== collect_lesson_index edge cases ===")
    assert_eq(Q.collect_lesson_index(make_page("x", {"lesson_index": "07"})), 7, "string '07' -> 7")
    assert_eq(Q.collect_lesson_index(make_page("x", {"lesson_index": ""})), None, "empty string -> None")
    assert_eq(Q.collect_lesson_index(make_page("x", {})), None, "missing -> None")
    assert_eq(Q.collect_lesson_index(make_page("x", {"lesson_index": "abc"})), None, "non-numeric -> None")


# ---------------------------------------------------------------------------
# inverse-prerequisites / series_index
# ---------------------------------------------------------------------------

def test_build_inverse_prerequisites():
    print("\n=== build_inverse_prerequisites ===")
    pages = [
        make_page("a", {"prerequisites": ["b", "c"]}),
        make_page("b", {"prerequisites": ["c"]}),
        make_page("c", {}),
        make_page("d", {"prerequisites": ["a"]}),
    ]
    inv = Q.build_inverse_prerequisites(pages)
    assert_eq(sorted(inv.get("c", [])), ["a", "b"], "c is needed by a + b")
    assert_eq(inv.get("a", []), ["d"], "a is needed by d")
    assert_eq(inv.get("d", []), [], "d needed-by nothing -> not in dict")


def test_build_series_index():
    print("\n=== build_series_index sorting ===")
    pages = [
        make_page("30-tutorials/gas/03-c", {"series": "gas", "lesson_index": 3}),
        make_page("30-tutorials/gas/01-a", {"series": "gas", "lesson_index": 1}),
        make_page("30-tutorials/gas/02-b", {"series": "gas", "lesson_index": 2}),
        make_page("30-tutorials/network/00", {"series": "network-sync", "lesson_index": 0}),
        make_page("60-topics/no-series", {}),
    ]
    idx = Q.build_series_index(pages)
    gas_ids = [p.page_id for p in idx["gas"]]
    assert_eq(gas_ids,
              ["30-tutorials/gas/01-a", "30-tutorials/gas/02-b", "30-tutorials/gas/03-c"],
              "gas series sorted by lesson_index")
    assert_in("network-sync", idx, "network-sync series present")
    assert_true("no-series" not in idx, "page without series not indexed")


# ---------------------------------------------------------------------------
# score_against_index_entry
# ---------------------------------------------------------------------------

def test_score_against_index_entry():
    print("\n=== score_against_index_entry ===")
    e = Q.IndexEntry(
        page_id="60-topics/pcg-spline-building",
        description="pcg procedural building 样条驱动程序化建筑",
    )
    s, why = Q.score_against_index_entry(e, ["spline", "building"], alias_set=set())
    expected = 2 * Q.W_ID_HIT + 1 * Q.W_DESC_HIT  # spline 命中 id；building 命中 id+desc
    assert_eq(s, expected, "id-hit x 2 + desc-hit x 1")
    assert_in("id-hit:spline,building", why, "why id-hit")
    assert_in("desc-hit:building", why, "why desc-hit")

    s, why = Q.score_against_index_entry(e, ["procedural"], alias_set=set())
    assert_eq(s, Q.W_DESC_HIT, "desc-hit only")

    s, why = Q.score_against_index_entry(e, ["样条"], alias_set=set())
    assert_eq(s, Q.W_DESC_HIT, "Chinese desc-hit")

    s, _ = Q.score_against_index_entry(e, ["nonexistent"], alias_set=set())
    assert_eq(s, 0.0, "no hit -> 0")


def test_score_alias_damped():
    """alias-only token 的命中权重应被打折（W_ALIAS_DAMP）。"""
    print("\n=== score alias dampen ===")
    e = Q.IndexEntry(
        page_id="30-tutorials/gas/01",
        description="gameplay ability system 入门",
    )
    # 用户输入 "gas"，alias 扩展出 "gameplay ability system"
    # "gas" 命中 id（全权重），"gameplay ability system" 命中 desc（0.6 折扣）
    alias_extra = ["gameplay ability system"]
    tokens = ["gas"] + alias_extra
    s, why = Q.score_against_index_entry(e, tokens, alias_set=set(alias_extra))
    # gas 命中 id (W_ID_HIT × 1.0) + desc-hit: "gas" not in desc, but alias is →
    #   只有 "gameplay ability system" 在 desc 中，权重 W_DESC_HIT × W_ALIAS_DAMP
    expected = Q.W_ID_HIT * 1.0 + Q.W_DESC_HIT * Q.W_ALIAS_DAMP
    assert_true(abs(s - expected) < 1e-6, f"score with alias damp ≈ {expected}")


# ---------------------------------------------------------------------------
# score_against_page（tag / anchors / type / boost）
# ---------------------------------------------------------------------------

def test_score_against_page_tag_and_anchor():
    print("\n=== score_against_page (tag + anchor + type) ===")
    page = make_page("20-modules/cpp/ALyraCharacter", fm={
        "type": "module",
        "tags": ["character", "pawn", "ability-system"],
        "anchors": [{"path": "Source/LyraGame/Character/LyraCharacter.cpp"}],
    })
    # tag 命中
    s, why = Q.score_against_page(page, ["pawn"], alias_set=set())
    assert_true(s >= Q.W_TAG_HIT, "tag hit gives W_TAG_HIT")
    assert_in("tag-hit:pawn", why, "why tag-hit")

    # anchor 文件名命中（用户查 "lyracharacter" 应能命中）
    s2, why2 = Q.score_against_page(page, ["lyracharacter"], alias_set=set())
    assert_true(s2 >= Q.W_ANCHOR_HIT, "anchor hit gives W_ANCHOR_HIT")
    assert_in("anchor-hit:lyracharacter", why2, "why anchor-hit")

    # type 精确匹配
    s3, why3 = Q.score_against_page(page, ["module"], alias_set=set())
    assert_true(s3 >= Q.W_TYPE_HIT, "type-hit gives at least W_TYPE_HIT")
    assert_in("type-hit:module", why3, "why type-hit")


def test_core_type_boost():
    print("\n=== core type boost ===")
    page_tut = make_page("30-tutorials/gas/01", {"type": "tutorial", "tags": ["foo"]})
    page_unknown = make_page("xx/yy", {"type": "weird-type", "tags": ["foo"]})
    # 用同一个命中 token "foo"，看 boost 差别
    s_tut, _ = Q.score_against_page(page_tut, ["foo"], alias_set=set())
    s_unk, _ = Q.score_against_page(page_unknown, ["foo"], alias_set=set())
    assert_true(s_tut > s_unk, "tutorial boosted higher than weird-type")


# ---------------------------------------------------------------------------
# status_warning + STATUS_MULTIPLIER
# ---------------------------------------------------------------------------

def test_status_warning():
    print("\n=== status_warning + multiplier ===")
    assert_eq(Q.status_warning("current"), None, "current -> no warn")
    assert_in("re-verify", Q.status_warning("stale"), "stale warns re-verify")
    assert_in("do not cite", Q.status_warning("deprecated"), "deprecated warns")
    assert_in("work in progress", Q.status_warning("draft"), "draft warns")
    assert_eq(Q.status_warning(""), None, "empty -> None")
    # multiplier 关系：deprecated < stale < draft < current
    m = Q.STATUS_MULTIPLIER
    assert_true(m["deprecated"] < m["stale"] < m["draft"] < m["current"],
                "STATUS_MULTIPLIER monotonic")


# ---------------------------------------------------------------------------
# 集成：跑真实 Docs/ 三种模式 smoke
# ---------------------------------------------------------------------------

def test_real_keyword_smoke():
    print("\n=== run_query keyword smoke (real Docs/) ===")
    if not (REPO / "Docs" / "index.md").is_file():
        print("  [SKIP] Docs/index.md not present; skipping smoke test")
        return
    result = Q.run_query("log rollup", max_candidates=3, body_search=False)
    assert_true(bool(result.candidates), "returns at least 1 candidate")
    assert_eq(result.tokens[:2], ["log", "rollup"], "first two tokens")
    top = result.candidates[0]
    assert_in("log", top.page_id.lower(), "top candidate id contains 'log'")
    assert_eq(result.mode, "keyword", "mode=keyword")


def test_real_keyword_alias_expansion():
    """实测：用户输入 'GAS'，应能通过 alias 扩展把 GAS 教程系列命中。"""
    print("\n=== run_query alias expansion smoke ===")
    if not (REPO / "Docs" / "index.md").is_file():
        print("  [SKIP] Docs/index.md not present; skipping")
        return
    result = Q.run_query("GAS 网络复制", max_candidates=5, body_search=False)
    # 至少应该命中 GAS 教程系列下的页
    pids = [c.page_id for c in result.candidates]
    assert_true(any("gas/" in p.lower() or "gas-" in p.lower() or "/gas" in p.lower() for p in pids),
                "至少一个候选属于 gas 教程系列")
    # 顶部候选应含 prereq 或 related（v1.0 新增展示）
    top = result.candidates[0]
    assert_true(top.related or top.prerequisites or top.tags,
                "top candidate exposes graph edges (related/prereq/tags)")


def test_real_seed_smoke():
    print("\n=== run_query seed smoke ===")
    if not (REPO / "Docs" / "00-meta" / "ai-playbook.md").is_file():
        print("  [SKIP] ai-playbook.md not present; skipping")
        return
    result = Q.run_query("", seed_id="00-meta/ai-playbook", max_candidates=1)
    assert_eq(len(result.candidates), 1, "seed mode returns exactly seed")
    assert_eq(result.candidates[0].page_id, "00-meta/ai-playbook", "seed id matches")
    assert_in("seed-id", result.candidates[0].why, "why contains seed-id")
    assert_eq(result.mode, "seed", "mode=seed")


def test_real_seed_neighbors_multi_edge():
    """种子模式下，neighbors 应包含多类型边（related / prereq / series-prev/next / needed-by）。"""
    print("\n=== run_query seed multi-edge neighbors ===")
    seed = "30-tutorials/gas/19-Tag网络复制"
    seed_path = REPO / "Docs" / f"{seed}.md"
    if not seed_path.is_file():
        print(f"  [SKIP] {seed} not present; skipping")
        return
    result = Q.run_query("", seed_id=seed, max_candidates=1)
    edges_seen = set()
    for n in result.neighbors:
        if n.why:
            edges_seen.add(n.why[0].split()[0])
    # 至少应展开出 prereq 或 series-prev/next 之一
    assert_true(
        any(e in edges_seen for e in ("prereq", "series-prev", "series-next", "related", "needed-by")),
        f"seed neighbors include graph edges, got={edges_seen}"
    )


def test_real_series_smoke():
    print("\n=== run_query series smoke ===")
    if not (REPO / "Docs" / "30-tutorials" / "gas").is_dir():
        print("  [SKIP] gas series dir not present; skipping")
        return
    result = Q.run_query("", series_name="gas")
    assert_eq(result.mode, "series", "mode=series")
    assert_eq(result.series_name, "gas", "series_name=gas")
    assert_true(len(result.candidates) >= 5, "gas series has enough lessons (>=5)")
    # 同系列邻居应被过滤掉
    for n in result.neighbors:
        assert_true(n.series != "gas",
                    f"cross-series neighbor only, got {n.page_id} series={n.series}")
    # 课程应按 lesson_index 升序排
    li_seq = [c.lesson_index for c in result.candidates if c.lesson_index is not None]
    assert_eq(li_seq, sorted(li_seq), "lessons sorted by lesson_index")


def test_real_body_grep_skips_meta():
    """body grep 不应把 index / log / overview 排在前面（移植版 bug）。"""
    print("\n=== body grep meta skip ===")
    if not (REPO / "Docs" / "index.md").is_file():
        print("  [SKIP] not present; skipping")
        return
    result = Q.run_query("ability", max_candidates=3, body_search=True)
    body_ids = {m["page_id"] for m in result.body_matches}
    for skip_id in ("index", "log", "overview", "README"):
        assert_true(skip_id not in body_ids,
                    f"body matches must not include meta '{skip_id}'")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_tokenize()
    test_normalize_wikilink_id()
    test_parse_index_simple_format()
    test_parse_index_legacy_tuple_format()
    test_parse_index_dedup()
    test_parse_aliases_and_expand()
    test_expand_no_alias_match()
    test_collect_edges()
    test_collect_lesson_index_edge_cases()
    test_build_inverse_prerequisites()
    test_build_series_index()
    test_score_against_index_entry()
    test_score_alias_damped()
    test_score_against_page_tag_and_anchor()
    test_core_type_boost()
    test_status_warning()
    test_real_keyword_smoke()
    test_real_keyword_alias_expansion()
    test_real_seed_smoke()
    test_real_seed_neighbors_multi_edge()
    test_real_series_smoke()
    test_real_body_grep_skips_meta()

    print(f"\n=== Summary: {_PASS} passed, {_FAIL} failed ===")
    if _FAIL:
        sys.exit(1)
    print("✓ all query.py tests passed")
