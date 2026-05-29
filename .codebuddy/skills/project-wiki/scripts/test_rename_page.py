#!/usr/bin/env python3
"""单元测试 rename_page.py 的 wikilink 替换 + frontmatter id 改写 + e2e。

跑法：
    python .codebuddy/skills/project-wiki/scripts/test_rename_page.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / ".codebuddy" / "skills" / "project-wiki" / "scripts"))

import rename_page as R  # noqa: E402


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
# _replace_wikilinks_in_text
# ---------------------------------------------------------------------------

def test_replace_simple():
    print("\n=== _replace_wikilinks_in_text: 简单 [[X]] ===")
    text = "see [[60-topics/old]] and [[60-topics/old]] for refs"
    new, changes = R._replace_wikilinks_in_text(text, "60-topics/old", "20-modules/new", "Docs/test.md")
    assert_eq(len(changes), 2, "2 occurrences")
    assert_eq(new, "see [[20-modules/new]] and [[20-modules/new]] for refs", "both replaced")


def test_replace_with_alias_and_section():
    print("\n=== _replace_wikilinks_in_text: 保留 alias + section ===")
    text = "[[60-topics/old]] · [[60-topics/old|短名]] · [[60-topics/old#section]] · [[60-topics/old|短名#section]]"
    new, changes = R._replace_wikilinks_in_text(text, "60-topics/old", "20-modules/new", "Docs/test.md")
    assert_eq(len(changes), 4, "4 occurrences")
    assert_in("[[20-modules/new]]", new, "plain replaced")
    assert_in("[[20-modules/new|短名]]", new, "alias preserved")
    assert_in("[[20-modules/new#section]]", new, "section preserved")
    assert_in("[[20-modules/new|短名#section]]", new, "alias+section preserved")


def test_replace_skip_partial_match():
    print("\n=== _replace_wikilinks_in_text: 跳过部分匹配 ===")
    text = "[[60-topics/old]] vs [[60-topics/old-but-different]] vs [[60-topics/older]]"
    new, changes = R._replace_wikilinks_in_text(text, "60-topics/old", "20-modules/new", "Docs/test.md")
    assert_eq(len(changes), 1, "only exact id match (1 of 3)")
    assert_in("[[20-modules/new]]", new, "exact replaced")
    assert_in("[[60-topics/old-but-different]]", new, "partial preserved")
    assert_in("[[60-topics/older]]", new, "longer prefix preserved")


def test_replace_track_line_no():
    print("\n=== _replace_wikilinks_in_text: 行号跟踪 ===")
    text = "L1\nL2 with [[60-topics/old]]\nL3\nL4 with [[60-topics/old]]\n"
    _, changes = R._replace_wikilinks_in_text(text, "60-topics/old", "X", "Docs/test.md")
    lines = sorted(c.line_no for c in changes)
    assert_eq(lines, [2, 4], "line numbers tracked")


# ---------------------------------------------------------------------------
# _patch_frontmatter_id
# ---------------------------------------------------------------------------

def test_fm_id_basic():
    print("\n=== _patch_frontmatter_id: 基本改写 ===")
    text = "---\nid: 60-topics/old\ntype: topic\n---\n# T\n"
    new, changed = R._patch_frontmatter_id(text, "60-topics/old", "20-modules/new")
    assert_eq(changed, True, "changed flag")
    assert_in("id: 20-modules/new", new, "id changed")
    assert_in("type: topic", new, "other fm preserved")


def test_fm_id_mismatch():
    print("\n=== _patch_frontmatter_id: id 与 from_id 不符不动 ===")
    text = "---\nid: 60-topics/different\n---\n# T\n"
    new, changed = R._patch_frontmatter_id(text, "60-topics/old", "X")
    assert_eq(changed, False, "no change")
    assert_eq(new, text, "text unchanged")


def test_fm_id_no_frontmatter():
    print("\n=== _patch_frontmatter_id: 无 frontmatter ===")
    text = "# T\nbody\n"
    new, changed = R._patch_frontmatter_id(text, "X", "Y")
    assert_eq(changed, False, "no change")
    assert_eq(new, text, "text unchanged")


# ---------------------------------------------------------------------------
# _build_plan + _apply_plan e2e
# ---------------------------------------------------------------------------

def setup_minimal_repo(tmp_root: Path) -> Path:
    """构造最小 wiki: 5 个页 + index.md。返回 docs root。"""
    docs = tmp_root / "Docs"
    (docs / "60-topics").mkdir(parents=True)
    (docs / "20-modules" / "python").mkdir(parents=True)
    (docs / "40-runbooks").mkdir(parents=True)

    (docs / "60-topics" / "old.md").write_text(
        "---\nid: 60-topics/old\ntype: topic\n"
        'related:\n  - "[[40-runbooks/setup]]"\n'
        "---\n"
        "# Old Topic\nbody refs [[40-runbooks/setup]]\n",
        encoding="utf-8",
    )
    (docs / "40-runbooks" / "setup.md").write_text(
        "---\nid: 40-runbooks/setup\ntype: runbook\n"
        'related:\n  - "[[60-topics/old]]"\n'
        "---\n"
        "# Setup\nsee [[60-topics/old]] and [[60-topics/old|short]] and [[60-topics/old#sec]]\n",
        encoding="utf-8",
    )
    (docs / "20-modules" / "python" / "Tools.foo.md").write_text(
        "---\nid: 20-modules/python/Tools.foo\ntype: module\n---\n"
        "# Tools.foo\nrelated topic [[60-topics/old]]\n",
        encoding="utf-8",
    )
    (docs / "index.md").write_text(
        "# Index\n## 20-modules/\n- [[20-modules/python/Tools.foo]]\n## 40-runbooks/\n"
        "- [[40-runbooks/setup]]\n## 60-topics/\n- [[60-topics/old]]\n",
        encoding="utf-8",
    )
    (docs / "log.md").write_text(
        "# Log\n## [2026-05-14] init\nseed page [[60-topics/old]]\n",
        encoding="utf-8",
    )
    return tmp_root


def test_build_plan():
    print("\n=== _build_plan: dry-run plan 完整性 ===")
    with tempfile.TemporaryDirectory() as tmp:
        root = setup_minimal_repo(Path(tmp))
        plan = R._build_plan(root, "60-topics/old", "20-modules/python/new-module")
        assert_eq(plan.from_id, "60-topics/old", "from_id")
        assert_eq(plan.to_id, "20-modules/python/new-module", "to_id")
        assert_eq(plan.fm_id_change, True, "fm id will change")
        # source(自身), setup, Tools.foo, index, log = 5 个文件含 [[old]]
        # source 自身的 [[old]] 不存在(只有 fm id),其他 4 个文件全有
        assert_eq(plan.files_touched, 4, "4 files touched (setup/foo/index/log,source 自身无 [[old]])")
        # setup 文件: fm 1 + body 3 = 4 处; Tools.foo 1; index 1; log 1 → 共 7
        assert_eq(len(plan.wikilink_changes), 7, "7 wikilink occurrences")


def test_apply_plan_e2e():
    print("\n=== _apply_plan: e2e 真改文件 ===")
    with tempfile.TemporaryDirectory() as tmp:
        root = setup_minimal_repo(Path(tmp))
        plan = R._build_plan(root, "60-topics/old", "20-modules/python/new-module")
        written = R._apply_plan(root, plan)

        docs = root / "Docs"
        assert not (docs / "60-topics" / "old.md").exists(), "source removed"
        target = docs / "20-modules" / "python" / "new-module.md"
        assert target.exists(), "target created"

        target_text = target.read_text(encoding="utf-8")
        assert_in("id: 20-modules/python/new-module", target_text, "target frontmatter id changed")

        setup_text = (docs / "40-runbooks" / "setup.md").read_text(encoding="utf-8")
        assert_in("[[20-modules/python/new-module]]", setup_text, "setup body wikilink changed")
        assert_in("[[20-modules/python/new-module|short]]", setup_text, "alias preserved")
        assert_in("[[20-modules/python/new-module#sec]]", setup_text, "section preserved")
        assert_in('"[[20-modules/python/new-module]]"', setup_text, "setup frontmatter related changed")
        assert_not_in("[[60-topics/old", setup_text, "no leftover [[60-topics/old in setup")

        foo_text = (docs / "20-modules" / "python" / "Tools.foo.md").read_text(encoding="utf-8")
        assert_in("[[20-modules/python/new-module]]", foo_text, "Tools.foo wikilink changed")

        index_text = (docs / "index.md").read_text(encoding="utf-8")
        assert_in("[[20-modules/python/new-module]]", index_text, "index changed")
        assert_not_in("[[60-topics/old]]", index_text, "no leftover in index")

        log_text = (docs / "log.md").read_text(encoding="utf-8")
        assert_in("[[20-modules/python/new-module]]", log_text, "log changed")

        # 4 modified + 1 renamed (source -> target counted once via mv) = 5
        assert written >= 4, f"written count >= 4 (got {written})"


def test_validate_target_exists():
    print("\n=== _validate: target 已存在拒绝 ===")
    with tempfile.TemporaryDirectory() as tmp:
        root = setup_minimal_repo(Path(tmp))
        # 已有 setup.md -> 用它当 to_id 应该被拒
        try:
            R._validate(root, "60-topics/old", "40-runbooks/setup")
            print("  [FAIL] should have raised")
            sys.exit(1)
        except SystemExit as e:
            assert "已存在" in str(e), "error mentions exists"
            print(f"  [OK] target exists raises: {e}")


def test_validate_source_missing():
    print("\n=== _validate: source 不存在拒绝 ===")
    with tempfile.TemporaryDirectory() as tmp:
        root = setup_minimal_repo(Path(tmp))
        try:
            R._validate(root, "60-topics/nonexistent", "X")
            print("  [FAIL] should have raised")
            sys.exit(1)
        except SystemExit as e:
            assert "不存在" in str(e), "error mentions missing"
            print(f"  [OK] source missing raises: {e}")


if __name__ == "__main__":
    test_replace_simple()
    test_replace_with_alias_and_section()
    test_replace_skip_partial_match()
    test_replace_track_line_no()
    test_fm_id_basic()
    test_fm_id_mismatch()
    test_fm_id_no_frontmatter()
    test_build_plan()
    test_apply_plan_e2e()
    test_validate_target_exists()
    test_validate_source_missing()
    print("\n[ALL OK] rename_page 单元测试 (11 case) 全部通过")
