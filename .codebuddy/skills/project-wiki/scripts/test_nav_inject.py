#!/usr/bin/env python3
"""单元测试 nav_inject.py 的全局模式 + ★R27 节内分组模式。

跑法：
    python .codebuddy/skills/project-wiki/scripts/test_nav_inject.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / ".codebuddy" / "skills" / "project-wiki" / "scripts"))

import nav_inject as N  # noqa: E402


def assert_eq(actual, expected, what: str):
    if actual == expected:
        print(f"  [OK] {what}: {actual!r}")
    else:
        print(f"  [FAIL] {what}: actual={actual!r} expected={expected!r}")
        sys.exit(1)


def assert_in(needle, haystack, what: str):
    if needle in haystack:
        print(f"  [OK] {what}")
    else:
        print(f"  [FAIL] {what}: {needle!r} not in {haystack!r}")
        sys.exit(1)


def assert_not_in(needle, haystack, what: str):
    if needle not in haystack:
        print(f"  [OK] {what}")
    else:
        print(f"  [FAIL] {what}: {needle!r} unexpectedly in {haystack!r}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# parse_index_with_sections (★R27)
# ---------------------------------------------------------------------------

def write_index(tmp_root: Path, content: str) -> Path:
    docs = tmp_root / "Docs"
    docs.mkdir(parents=True, exist_ok=True)
    p = docs / "index.md"
    p.write_text(content, encoding="utf-8")
    return docs


def test_parse_sections_basic():
    print("\n=== parse_index_with_sections: 基本 section 分组 ===")
    with tempfile.TemporaryDirectory() as tmp:
        docs = write_index(Path(tmp),
            "# Index\n\n"
            "## 20-modules/ — 模块\n\n"
            "- [[20-modules/a]]\n"
            "- [[20-modules/b]]\n\n"
            "## 30-decisions/ — ADR\n\n"
            "- [[30-decisions/0001]]\n"
        )
        sections = N.parse_index_with_sections(docs / "index.md")
        assert_eq(len(sections), 2, "section count")
        assert_eq(sections[0].name, "20-modules/ — 模块", "section[0] name")
        assert_eq(sections[0].page_ids, ["20-modules/a", "20-modules/b"], "section[0] pages")
        assert_eq(sections[1].name, "30-decisions/ — ADR", "section[1] name")
        assert_eq(sections[1].page_ids, ["30-decisions/0001"], "section[1] pages")


def test_parse_sections_dedup_cross():
    print("\n=== parse_index_with_sections: 跨 section 重复 [[id]] 只算首次 ===")
    with tempfile.TemporaryDirectory() as tmp:
        docs = write_index(Path(tmp),
            "## 入口\n- [[a]]\n## 模块\n- [[a]]\n- [[b]]\n"
        )
        sections = N.parse_index_with_sections(docs / "index.md")
        assert_eq(len(sections), 2, "section count")
        assert_eq(sections[0].page_ids, ["a"], "首次 [[a]] 在入口")
        assert_eq(sections[1].page_ids, ["b"], "模块 section 跳过 [[a]],只剩 [[b]]")


# ---------------------------------------------------------------------------
# _build_position_map
# ---------------------------------------------------------------------------

def test_position_map_global():
    print("\n=== _build_position_map: 全局模式 ===")
    flat = ["a", "b", "c", "d"]
    pm = N._build_position_map(None, flat, section_scope=False)
    assert_eq(pm["a"]["prev_id"], None, "a prev")
    assert_eq(pm["a"]["next_id"], "b", "a next")
    assert_eq(pm["c"]["prev_id"], "b", "c prev")
    assert_eq(pm["c"]["next_id"], "d", "c next")
    assert_eq(pm["d"]["next_id"], None, "d next (last)")
    for k in pm:
        assert_eq(pm[k]["section_ctx"], None, f"{k} section_ctx is None (global mode)")


def test_position_map_section_scope():
    print("\n=== _build_position_map: ★R27 节内分组模式 ===")
    sections = [
        N.IndexSection("S1", ["a", "b"]),
        N.IndexSection("S2", ["c", "d", "e"]),
        N.IndexSection("S3", ["f"]),
    ]
    flat = ["a", "b", "c", "d", "e", "f"]
    pm = N._build_position_map(sections, flat, section_scope=True)

    # a (S1 首页): prev=None, next=b, section_ctx 含 prev_section_last=None + next_section_first=None
    assert_eq(pm["a"]["prev_id"], None, "a prev within S1")
    assert_eq(pm["a"]["next_id"], "b", "a next within S1")
    assert_eq(pm["a"]["section_ctx"]["section_name"], "S1", "a section name")
    assert_eq(pm["a"]["section_ctx"]["prev_section_last"], None, "a 是 S1 首页且无前一节")

    # b (S1 末页): prev=a, next=None, section_ctx 含 next_section_first=c
    assert_eq(pm["b"]["next_id"], None, "b next None (S1 末页)")
    assert_eq(pm["b"]["section_ctx"]["next_section_first"], "c", "b 末页提示 S2 首页 c")

    # c (S2 首页): prev=None, next=d, section_ctx 含 prev_section_last=b
    assert_eq(pm["c"]["prev_id"], None, "c prev None (S2 首页)")
    assert_eq(pm["c"]["section_ctx"]["prev_section_last"], "b", "c 首页提示 S1 末页 b")
    assert_eq(pm["c"]["section_ctx"]["next_section_first"], None, "c 不是 S2 末页")

    # d (S2 中间): prev=c, next=e, no cross-section hint
    assert_eq(pm["d"]["prev_id"], "c", "d prev")
    assert_eq(pm["d"]["next_id"], "e", "d next")
    assert_eq(pm["d"]["section_ctx"]["prev_section_last"], None, "d 中间不提示前节")
    assert_eq(pm["d"]["section_ctx"]["next_section_first"], None, "d 中间不提示后节")

    # f (S3 唯一页 = 首+末): prev=None, next=None, 双向 cross-section 提示
    assert_eq(pm["f"]["prev_id"], None, "f prev None")
    assert_eq(pm["f"]["next_id"], None, "f next None")
    assert_eq(pm["f"]["section_ctx"]["prev_section_last"], "e", "f 首页提示 S2 末页 e")
    assert_eq(pm["f"]["section_ctx"]["next_section_first"], None, "f 末页(无后节)无 next_section_first")


# ---------------------------------------------------------------------------
# build_nav_block (含 section_ctx)
# ---------------------------------------------------------------------------

def test_build_nav_block_global():
    print("\n=== build_nav_block: 全局模式无 section_ctx ===")
    block = N.build_nav_block("a", "b", section_ctx=None)
    assert_in("[[a|a]]", block, "prev wikilink")
    assert_in("[[b|b]]", block, "next wikilink")
    assert_in("[[index|↑ index]]", block, "index link")
    assert_not_in("本节:", block, "no section info")


def test_build_nav_block_section():
    print("\n=== build_nav_block: ★R27 节内 section_ctx 中间页 ===")
    ctx = {"section_name": "S2", "prev_section_last": None, "next_section_first": None}
    block = N.build_nav_block("c", "e", section_ctx=ctx)
    assert_in("本节: S2", block, "section name shown")
    assert_not_in("上一节末页:", block, "no prev_section_last hint (中间页)")
    assert_not_in("下一节首页:", block, "no next_section_first hint (中间页)")


def test_build_nav_block_section_boundary():
    print("\n=== build_nav_block: ★R27 节内 section 末页 cross-section 提示 ===")
    ctx = {"section_name": "S1", "prev_section_last": None, "next_section_first": "c"}
    block = N.build_nav_block("a", None, section_ctx=ctx)
    assert_in("本节: S1", block, "section name")
    assert_in("下一节首页:", block, "next_section_first hint shown")
    assert_in("[[c|c]]", block, "next_section_first wikilink")


# ---------------------------------------------------------------------------
# 端到端 (★R27 节内分组真改 tempdir 文件)
# ---------------------------------------------------------------------------

def test_section_scope_e2e():
    print("\n=== ★R27 section-scope end-to-end (apply tempdir) ===")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs = root / "Docs"
        (docs / "20-modules").mkdir(parents=True)
        (docs / "30-decisions").mkdir(parents=True)

        (docs / "index.md").write_text(
            "# Index\n\n"
            "## 20-modules/ — 模块\n\n"
            "- [[20-modules/a]]\n"
            "- [[20-modules/b]]\n\n"
            "## 30-decisions/ — ADR\n\n"
            "- [[30-decisions/0001]]\n",
            encoding="utf-8",
        )
        for pid in ("20-modules/a", "20-modules/b"):
            (docs / f"{pid}.md").write_text(
                f"---\nid: {pid}\ntype: module\n---\n# {pid}\nbody\n",
                encoding="utf-8",
            )
        (docs / "30-decisions" / "0001.md").write_text(
            "---\nid: 30-decisions/0001\ntype: adr\n---\n# 0001\nbody\n",
            encoding="utf-8",
        )

        sections = N.parse_index_with_sections(docs / "index.md")
        pages = N.discover_pages(docs)
        entries = N.run_section_scope(sections, pages, strip_only=False, apply=True)

        actions = {e.action for e in entries if e.action != "skip-no-fm"}
        assert_in("add", actions, "至少有 add action")

        text_b = (docs / "20-modules" / "b.md").read_text(encoding="utf-8")
        assert_in("本节: 20-modules/ — 模块", text_b, "b 含本节名")
        assert_in("下一节首页:", text_b, "b 末页含跨节首页提示")
        assert_in("[[30-decisions/0001|0001]]", text_b, "b 末页指向 ADR 段首页")
        assert "→" not in text_b.split("**导航**:")[1].split("\n")[0], "b 末页 nav 行无 next 箭头"

        text_adr = (docs / "30-decisions" / "0001.md").read_text(encoding="utf-8")
        assert_in("本节: 30-decisions/ — ADR", text_adr, "ADR 含本节名")
        assert_in("上一节末页:", text_adr, "ADR 首页含跨节末页提示")
        assert_in("[[20-modules/b|b]]", text_adr, "ADR 首页指向模块段末页")


def test_global_mode_unchanged():
    print("\n=== 全局模式向后兼容 (默认行为不变) ===")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs = root / "Docs"
        (docs / "20-modules").mkdir(parents=True)
        (docs / "30-decisions").mkdir(parents=True)

        (docs / "index.md").write_text(
            "## A\n- [[20-modules/x]]\n## B\n- [[30-decisions/y]]\n",
            encoding="utf-8",
        )
        (docs / "20-modules" / "x.md").write_text(
            "---\nid: 20-modules/x\ntype: module\n---\n# X\n",
            encoding="utf-8",
        )
        (docs / "30-decisions" / "y.md").write_text(
            "---\nid: 30-decisions/y\ntype: adr\n---\n# Y\n",
            encoding="utf-8",
        )

        order = N.parse_index_order(docs / "index.md")
        pages = N.discover_pages(docs)
        entries = N.apply_nav(order, pages, strip_only=False)

        actions = {e.action for e in entries if e.action != "skip-no-fm"}
        assert_in("add", actions, "全局模式 add")

        text_x = (docs / "20-modules" / "x.md").read_text(encoding="utf-8")
        assert_in("[[30-decisions/y|y]]", text_x, "x 全局 next 跨 section 跳到 y")
        assert_not_in("本节:", text_x, "全局模式不写 section context")


if __name__ == "__main__":
    test_parse_sections_basic()
    test_parse_sections_dedup_cross()
    test_position_map_global()
    test_position_map_section_scope()
    test_build_nav_block_global()
    test_build_nav_block_section()
    test_build_nav_block_section_boundary()
    test_section_scope_e2e()
    test_global_mode_unchanged()
    print("\n[ALL OK] nav_inject 全局 + ★R27 节内分组单元测试全部通过")
