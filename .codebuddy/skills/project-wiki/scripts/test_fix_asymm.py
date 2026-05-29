#!/usr/bin/env python3
"""单元测试 fix_asymm.py 的正向 (patch_related) + ★R26 反向 (patch_related_remove) 模式。

跑法：
    python .codebuddy/skills/project-wiki/scripts/test_fix_asymm.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / ".codebuddy" / "skills" / "project-wiki" / "scripts"))

import fix_asymm as F  # noqa: E402


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


# ---------------------------------------------------------------------------
# patch_related (正向追加)
# ---------------------------------------------------------------------------

def test_patch_related_append_to_existing():
    print("\n=== patch_related: 追加到已有 related block ===")
    lines = [
        "---",
        "id: a",
        "type: topic",
        'related:',
        '  - "[[b]]"',
        "---",
        "# A",
    ]
    new_lines, added, reason = F.patch_related(lines, ["c", "d"])
    assert_eq(reason, "added", "reason")
    assert_eq(added, 2, "added count")
    text = "\n".join(new_lines)
    assert_in('"[[c]]"', text, "c added")
    assert_in('"[[d]]"', text, "d added")
    assert_in('"[[b]]"', text, "b preserved")


def test_patch_related_create_block():
    print("\n=== patch_related: 创建新 related block (页本无 related) ===")
    lines = ["---", "id: a", "type: topic", "---", "# A"]
    new_lines, added, reason = F.patch_related(lines, ["b"])
    assert_eq(reason, "added", "reason")
    assert_eq(added, 1, "added count")
    text = "\n".join(new_lines)
    assert_in("related:", text, "related: block created")
    assert_in('"[[b]]"', text, "b added")


def test_patch_related_already_present():
    print("\n=== patch_related: 已存在 → already-present ===")
    lines = ["---", "id: a", 'related:', '  - "[[b]]"', "---", "# A"]
    new_lines, added, reason = F.patch_related(lines, ["b"])
    assert_eq(reason, "already-present", "reason")
    assert_eq(added, 0, "added count")
    assert_eq(new_lines, lines, "lines unchanged")


def test_patch_related_skip_if_in_body():
    print("\n=== patch_related: body 已有 wikilink → 跳过 (already-present) ===")
    lines = [
        "---", "id: a", "---",
        "# A",
        "see [[b]] for details",
    ]
    new_lines, added, reason = F.patch_related(lines, ["b"])
    assert_eq(reason, "already-present", "reason")
    assert_eq(added, 0, "added count")


# ---------------------------------------------------------------------------
# patch_related_remove (★R26 反向删除)
# ---------------------------------------------------------------------------

def test_patch_remove_partial():
    print("\n=== patch_related_remove: 删除部分项 (其余保留) ===")
    lines = [
        "---",
        "id: a",
        'related:',
        '  - "[[b]]"',
        '  - "[[c]]"',
        '  - "[[d]]"',
        "---",
        "# A",
    ]
    new_lines, removed, reason = F.patch_related_remove(lines, ["c"])
    assert_eq(reason, "removed", "reason")
    assert_eq(removed, 1, "removed count")
    text = "\n".join(new_lines)
    assert_in('"[[b]]"', text, "b preserved")
    assert "[[c]]" not in text, "c removed"
    assert_in('"[[d]]"', text, "d preserved")
    assert_in("related:", text, "related: header preserved")


def test_patch_remove_all_empties_block():
    print("\n=== patch_related_remove: 删除全部 → 整个 related: 节也删 ===")
    lines = [
        "---",
        "id: a",
        "type: topic",
        'related:',
        '  - "[[b]]"',
        '  - "[[c]]"',
        "---",
        "# A",
    ]
    new_lines, removed, reason = F.patch_related_remove(lines, ["b", "c"])
    assert_eq(reason, "removed-and-emptied", "reason")
    assert_eq(removed, 2, "removed count")
    text = "\n".join(new_lines)
    assert "related:" not in text, "related: header also removed"
    assert "[[b]]" not in text, "b removed"
    assert "[[c]]" not in text, "c removed"
    assert_in("type: topic", text, "other fm fields preserved")
    assert_in("# A", text, "body preserved")


def test_patch_remove_none_matched():
    print("\n=== patch_related_remove: 目标不在 related → none-matched ===")
    lines = ["---", "id: a", 'related:', '  - "[[b]]"', "---", "# A"]
    new_lines, removed, reason = F.patch_related_remove(lines, ["x"])
    assert_eq(reason, "none-matched", "reason")
    assert_eq(removed, 0, "removed count")
    assert_eq(new_lines, lines, "lines unchanged")


def test_patch_remove_no_related_block():
    print("\n=== patch_related_remove: 页无 related block → no-related-block ===")
    lines = ["---", "id: a", "type: topic", "---", "# A"]
    new_lines, removed, reason = F.patch_related_remove(lines, ["b"])
    assert_eq(reason, "no-related-block", "reason")
    assert_eq(removed, 0, "removed count")


def test_patch_remove_no_frontmatter():
    print("\n=== patch_related_remove: 无 frontmatter → no-frontmatter ===")
    lines = ["# A", "no fm"]
    new_lines, removed, reason = F.patch_related_remove(lines, ["b"])
    assert_eq(reason, "no-frontmatter", "reason")


# ---------------------------------------------------------------------------
# parse_pairs (lint issue → (src, target))
# ---------------------------------------------------------------------------

def test_parse_pairs():
    print("\n=== parse_pairs: 解析 lint issues ===")
    issues = [
        {"code": "asymm-link", "file": "Docs/40-runbooks/use-x.md",
         "detail": "related → [[20-modules/y]]，但 [[20-modules/y]] 没回引 [[40-runbooks/use-x]]"},
        {"code": "broken-link", "file": "Docs/foo.md", "detail": "[[bar]] 不存在"},
        {"code": "asymm-link", "file": "Docs/30-decisions/0001-x.md",
         "detail": "related → [[60-topics/z]]，但 [[60-topics/z]] 没回引 [[30-decisions/0001-x]]"},
    ]
    pairs = F.parse_pairs(issues)
    assert_eq(len(pairs), 2, "pair count (broken-link skipped)")
    assert_eq(pairs[0], ("40-runbooks/use-x", "20-modules/y"), "pair[0]")
    assert_eq(pairs[1], ("30-decisions/0001-x", "60-topics/z"), "pair[1]")


# ---------------------------------------------------------------------------
# 端到端 (反向模式 → 真改 tempdir 文件)
# ---------------------------------------------------------------------------

def test_reverse_end_to_end():
    print("\n=== reverse end-to-end (跑 _run_reverse 真改文件) ===")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs = root / "Docs"
        (docs / "40-runbooks").mkdir(parents=True)
        page_a = docs / "40-runbooks" / "use-x.md"
        page_a.write_text(
            '---\nid: 40-runbooks/use-x\ntype: runbook\n'
            'related:\n  - "[[20-modules/y]]"\n  - "[[20-modules/keep]]"\n'
            '---\n# X\n',
            encoding="utf-8",
        )
        pairs = [("40-runbooks/use-x", "20-modules/y")]

        report = F._run_reverse(pairs, docs, apply=False)
        assert_eq(report["mode"], "reverse", "mode")
        assert_eq(report["total_changed"], 1, "dry-run counts")
        text_after_dry = page_a.read_text(encoding="utf-8")
        assert_in("[[20-modules/y]]", text_after_dry, "dry-run 不写文件")

        report = F._run_reverse(pairs, docs, apply=True)
        assert_eq(report["total_changed"], 1, "apply counts")
        text_after = page_a.read_text(encoding="utf-8")
        assert "[[20-modules/y]]" not in text_after, "y removed after apply"
        assert_in("[[20-modules/keep]]", text_after, "keep preserved")


if __name__ == "__main__":
    test_patch_related_append_to_existing()
    test_patch_related_create_block()
    test_patch_related_already_present()
    test_patch_related_skip_if_in_body()
    test_patch_remove_partial()
    test_patch_remove_all_empties_block()
    test_patch_remove_none_matched()
    test_patch_remove_no_related_block()
    test_patch_remove_no_frontmatter()
    test_parse_pairs()
    test_reverse_end_to_end()
    print("\n[ALL OK] fix_asymm 正向 + ★R26 反向单元测试全部通过")
