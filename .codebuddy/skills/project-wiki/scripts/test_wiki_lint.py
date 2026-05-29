#!/usr/bin/env python3
"""单元测试 wiki_lint.py 的所有新检测器（R18 + R19 累积）。

覆盖：
- check_menu_action_label (R18, v0.3): 6 case (干净 / 2-mount 冲突 /
  3-mount 冲突 / JSON 错 / 缺 main_menu / main_menu 类型错)
- check_bat_chcp_ascii   (R19, v0.4): 1 case 含 5 子场景（干净 / 缺 chcp /
  chcp 前中文 / 全 ASCII / 排除目录）
- check_last_synced_stale (R19, v0.4): 1 case 含 5 子场景（新 / 边界 /
  过期 / draft 豁免 / stale 豁免）
- check_duplicate_entity (R19, v0.4): 1 case 含 6 子场景（干净 / H1 重复 /
  meta 豁免 / 短标题跳过）

跑法：
    python .codebuddy/skills/project-wiki/scripts/test_wiki_lint_v04.py
    或者
    python .codebuddy/skills/project-wiki/scripts/test_wiki_lint.py  (R19 重命名)
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / ".codebuddy" / "skills" / "project-wiki" / "scripts"))

import wiki_lint as L  # noqa: E402


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
# check_bat_chcp_ascii
# ---------------------------------------------------------------------------

def make_bat(tmp_root: Path, rel: str, content: str, encoding="utf-8"):
    p = tmp_root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding=encoding)


def test_bat_chcp():
    print("\n=== check_bat_chcp_ascii ===")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # case 1: 干净（chcp 在前，后面才有中文 echo）
        make_bat(root, "good.bat", "@echo off\nsetlocal\nchcp 65001 >nul\necho 中文OK\n")
        # case 2: 缺 chcp 但有中文 → bat-missing-chcp
        make_bat(root, "missing.bat", "@echo off\nrem 中文注释\necho hi\n")
        # case 3: chcp 前有中文 rem → bat-non-ascii-before-chcp
        make_bat(root, "before.bat", "@echo off\nrem 这是中文注释\nrem 第二行也是\nchcp 65001\necho ok\n")
        # case 4: 全 ASCII → 不报
        make_bat(root, "ascii.bat", "@echo off\nrem pure ascii\necho hello\n")
        # case 5: 在排除目录里 → 跳过
        make_bat(root, ".venv/skip.bat", "@echo off\nrem 中文\n")

        issues = L.check_bat_chcp_ascii(root)
        codes = sorted(i.code for i in issues)
        assert_eq(codes, ["bat-missing-chcp", "bat-non-ascii-before-chcp", "bat-non-ascii-before-chcp"], "issue codes")

        before_issues = [i for i in issues if i.code == "bat-non-ascii-before-chcp"]
        assert_eq(len(before_issues), 2, "before-chcp count")
        lines = sorted(i.line for i in before_issues)
        assert_eq(lines, [2, 3], "before-chcp lines (rem L2, rem L3)")
        assert_in("L4", before_issues[0].detail, "detail mentions chcp line")

        missing = [i for i in issues if i.code == "bat-missing-chcp"]
        assert_eq(len(missing), 1, "missing-chcp count")
        assert_eq(missing[0].file, "missing.bat", "missing-chcp file")


# ---------------------------------------------------------------------------
# check_last_synced_stale
# ---------------------------------------------------------------------------

def fake_page(page_id: str, last_synced: str, status: str = "current") -> L.WikiPage:
    text = f"---\nid: {page_id}\nstatus: {status}\nlast_synced: {last_synced}\n---\n# T\n"
    return L.WikiPage(
        path=Path(f"/fake/{page_id}.md"),
        rel=f"Docs/{page_id}.md",
        page_id=page_id,
        text=text,
        fm={"id": page_id, "status": status, "last_synced": last_synced},
        fm_lines=4,
    )


def test_last_synced():
    print("\n=== check_last_synced_stale ===")
    today = date.today()
    fresh = (today - timedelta(days=10)).isoformat()
    edge_old = (today - timedelta(days=181)).isoformat()
    very_old = (today - timedelta(days=365)).isoformat()

    pages = [
        fake_page("a/fresh", fresh),
        fake_page("a/edge", edge_old),
        fake_page("a/old", very_old),
        fake_page("a/draft", very_old, status="draft"),
        fake_page("a/stale", very_old, status="stale"),
    ]
    issues = L.check_last_synced_stale(pages)
    files = sorted(i.file for i in issues)
    assert_eq(files, ["Docs/a/edge.md", "Docs/a/old.md"], "stale page rel paths (current only)")
    assert all(i.code == "last-synced-stale" for i in issues), "code"
    assert_in("181", issues[0].detail, "edge detail mentions 181")


# ---------------------------------------------------------------------------
# check_duplicate_entity
# ---------------------------------------------------------------------------

def fake_page_with_h1(page_id: str, h1: str) -> L.WikiPage:
    text = f"---\nid: {page_id}\n---\n# {h1}\n\nbody\n"
    return L.WikiPage(
        path=Path(f"/fake/{page_id}.md"),
        rel=f"Docs/{page_id}.md",
        page_id=page_id,
        text=text,
        fm={"id": page_id},
        fm_lines=3,
    )


def test_duplicate_entity():
    print("\n=== check_duplicate_entity ===")
    pages = [
        fake_page_with_h1("20-modules/python/A", "模块: Tools.foo"),
        fake_page_with_h1("20-modules/python/B", "模块: Tools.foo"),  # duplicate
        fake_page_with_h1("20-modules/python/C", "模块: Tools.bar"),
        fake_page_with_h1("00-meta/policy", "模块: Tools.foo"),  # exempt path
        fake_page_with_h1("60-topics/x", "短"),  # title < 4 chars → skip
        fake_page_with_h1("60-topics/y", "短"),
    ]
    issues = L.check_duplicate_entity(pages)
    assert_eq(len(issues), 1, "issue count (only Tools.foo dup, exempt + short skipped)")
    assert_eq(issues[0].code, "duplicate-entity", "code")
    assert_in("tools.foo", issues[0].detail.lower(), "title mentioned (case-insensitive)")
    assert_in("20-modules/python/A", issues[0].detail, "page A mentioned")
    assert_in("20-modules/python/B", issues[0].detail, "page B mentioned")


# ---------------------------------------------------------------------------
# check_menu_action_label (R18, v0.3)
# ---------------------------------------------------------------------------

def make_menu_cfg(env_label_a: str, env_label_b: str) -> dict:
    return {
        "main_menu": {
            "name": "Root",
            "label": "Root",
            "items": [
                {
                    "type": "submenu",
                    "name": "A",
                    "label": "PythonDev",
                    "items": [
                        {"type": "entry", "name": "X", "label": env_label_a, "action": "env.setup"},
                        {"type": "entry", "name": "Y", "label": "Reload", "action": "internal.reload_toolchain"},
                    ],
                },
                {
                    "type": "submenu",
                    "name": "B",
                    "label": "WebPlatform",
                    "items": [
                        {"type": "entry", "name": "Z", "label": env_label_b, "action": "env.setup"},
                    ],
                },
            ],
        }
    }


def run_menu_lint(cfg) -> list:
    import json as _json
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg_dir = root / "Content" / "Python" / "Config"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "menu_config.json").write_text(_json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        return L.check_menu_action_label(root)


def test_menu_label():
    print("\n=== check_menu_action_label (v0.3) ===")
    issues = run_menu_lint(make_menu_cfg("BackendDeps", "BackendDeps"))
    assert_eq(len(issues), 0, "clean: same label both mounts")

    issues = run_menu_lint(make_menu_cfg("Setup VirtualEnv", "Install Web Env"))
    assert_eq(len(issues), 1, "2-mount conflict")
    assert_eq(issues[0].code, "menu-label-mismatch", "code")
    assert_eq(issues[0].severity, "error", "severity (v0.5 升 error)")
    assert_in("env.setup", issues[0].detail, "action mentioned")

    cfg = make_menu_cfg("L1", "L2")
    cfg["main_menu"]["items"].append({
        "type": "entry", "name": "Q", "label": "L3", "action": "env.setup"
    })
    issues = run_menu_lint(cfg)
    assert_eq(len(issues), 1, "3-mount issue count")
    assert_in("3", issues[0].detail, "mount count in detail")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg_dir = root / "Content" / "Python" / "Config"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "menu_config.json").write_text("{not valid json", encoding="utf-8")
        issues = L.check_menu_action_label(root)
        assert_eq(len(issues), 1, "JSON error issue count")
        assert_eq(issues[0].code, "menu-config-invalid", "code")
        assert_eq(issues[0].severity, "error", "severity")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg_dir = root / "Content" / "Python" / "Config"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "menu_config.json").write_text('{"foo": 1}', encoding="utf-8")
        issues = L.check_menu_action_label(root)
        assert_eq(len(issues), 0, "missing main_menu = lenient empty walk")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg_dir = root / "Content" / "Python" / "Config"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "menu_config.json").write_text('{"main_menu": "wrong"}', encoding="utf-8")
        issues = L.check_menu_action_label(root)
        assert_eq(len(issues), 1, "main_menu wrong type issue count")
        assert_eq(issues[0].code, "menu-config-invalid", "code")


# ---------------------------------------------------------------------------
# check_prerequisites (R21, v0.5)
# ---------------------------------------------------------------------------

def fake_page_with_prereq(page_id: str, prereq) -> L.WikiPage:
    """构造带 prerequisites 字段的页(prereq 接 list / str / None / dict 都可测)。"""
    fm = {"id": page_id}
    if prereq is not None:
        fm["prerequisites"] = prereq
    text = f"---\nid: {page_id}\n---\n# T\n"
    return L.WikiPage(
        path=Path(f"/fake/{page_id}.md"),
        rel=f"Docs/{page_id}.md",
        page_id=page_id,
        text=text,
        fm=fm,
        fm_lines=3,
    )


def fake_page_status(page_id: str, status: str) -> L.WikiPage:
    fm = {"id": page_id, "status": status}
    text = f"---\nid: {page_id}\nstatus: {status}\n---\n# T\n"
    return L.WikiPage(
        path=Path(f"/fake/{page_id}.md"),
        rel=f"Docs/{page_id}.md",
        page_id=page_id,
        text=text,
        fm=fm,
        fm_lines=4,
    )


def test_prerequisites():
    print("\n=== check_prerequisites (v0.5) ===")
    target_current = fake_page_status("40-runbooks/setup", "current")
    target_stale = fake_page_status("40-runbooks/old", "stale")
    target_deprecated = fake_page_status("40-runbooks/dead", "deprecated")

    pages = [
        target_current,
        target_stale,
        target_deprecated,
        # 1. 无 prereq → 不报
        fake_page_with_prereq("40-runbooks/a", None),
        # 2. 自然语言 prereq → 不报
        fake_page_with_prereq("40-runbooks/b", ["Python 3.11", "已装 pnpm"]),
        # 3. 引 current 的 wikilink → 不报
        fake_page_with_prereq("40-runbooks/c", ["已读 [[40-runbooks/setup]]"]),
        # 4. 引不存在的 wikilink → warn
        fake_page_with_prereq("40-runbooks/d", ["已读 [[40-runbooks/missing]]"]),
        # 5. 引 stale → warn
        fake_page_with_prereq("40-runbooks/e", ["参考 [[40-runbooks/old]]"]),
        # 6. 引 deprecated → warn
        fake_page_with_prereq("40-runbooks/f", ["遵循 [[40-runbooks/dead]]"]),
        # 7. 字段类型不对(str 而非 list) → warn
        fake_page_with_prereq("40-runbooks/g", "应该是 list 但写成 str"),
        # 8. list 中含 dict → warn
        fake_page_with_prereq("40-runbooks/h", [{"foo": 1}]),
    ]
    issues = L.check_prerequisites(pages)
    files = sorted(i.file for i in issues)
    expected = sorted([
        "Docs/40-runbooks/d.md", "Docs/40-runbooks/e.md", "Docs/40-runbooks/f.md",
        "Docs/40-runbooks/g.md", "Docs/40-runbooks/h.md",
    ])
    assert_eq(files, expected, "files reported (5 cases out of 9 prereq pages)")
    assert all(i.code == "prerequisites-mismatch" for i in issues), "all code"
    assert all(i.severity == "warn" for i in issues), "all warn"

    detail_d = [i for i in issues if i.file == "Docs/40-runbooks/d.md"][0].detail
    assert_in("missing", detail_d, "missing target id mentioned")
    detail_e = [i for i in issues if i.file == "Docs/40-runbooks/e.md"][0].detail
    assert_in("stale", detail_e, "stale status mentioned")
    detail_g = [i for i in issues if i.file == "Docs/40-runbooks/g.md"][0].detail
    assert_in("list", detail_g, "type error mentioned")


# ---------------------------------------------------------------------------
# check_log_order (R25, v0.6)
# ---------------------------------------------------------------------------

def write_log(tmp_root: Path, lines: list[str]) -> Path:
    docs = tmp_root / "Docs"
    docs.mkdir(parents=True, exist_ok=True)
    p = docs / "log.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return docs


def test_log_order():
    print("\n=== check_log_order (v0.6) ===")
    with tempfile.TemporaryDirectory() as tmp:
        docs = write_log(Path(tmp), [
            "# 操作日志",
            "",
            "## [2026-05-13] init | 项目知识库初始化",
            "",
            "## [2026-05-14] crystallize | R20: 内容覆盖层",
            "",
            "## [2026-05-14] crystallize | R21: lint v0.5",
            "",
            "## [2026-05-14] crystallize | R22: Web 服务",
            "",
            "## [2026-05-14] crystallize | R23: nav_inject",
        ])
        issues = L.check_log_order(docs)
        assert_eq(len(issues), 0, "正序 R20→R21→R22→R23 无报警")

    with tempfile.TemporaryDirectory() as tmp:
        docs = write_log(Path(tmp), [
            "# 操作日志",
            "## [2026-05-14] crystallize | R20: x",
            "## [2026-05-14] crystallize | R23: y",
            "## [2026-05-14] crystallize | R22: z",
            "## [2026-05-14] crystallize | R21: w",
        ])
        issues = L.check_log_order(docs)
        assert_eq(len(issues), 2, "倒序 R20→R23→R22→R21 报 2 处(R23→R22, R22→R21)")
        assert all(i.code == "log-order" for i in issues), "code"
        assert all(i.severity == "warn" for i in issues), "severity"
        assert_in("R22", issues[0].detail, "首条 detail 提到 R22")
        assert_in("R23", issues[0].detail, "首条 detail 提到 R23")

    with tempfile.TemporaryDirectory() as tmp:
        docs = write_log(Path(tmp), [
            "## [2026-05-14] crystallize | R20: x",
            "## [2026-05-14] crystallize | R23: y",
            "## [2026-05-14] crystallize | R25: z",
        ])
        issues = L.check_log_order(docs)
        assert_eq(len(issues), 0, "跳号 R20→R23→R25 无报警(只校验单调性)")

    with tempfile.TemporaryDirectory() as tmp:
        docs = write_log(Path(tmp), [
            "## [2026-05-13] init | 项目知识库初始化",
            "## [2026-05-14] crystallize | R20: x",
        ])
        issues = L.check_log_order(docs)
        assert_eq(len(issues), 0, "单 R 段无报警(non-R 段不参与排序)")

    with tempfile.TemporaryDirectory() as tmp:
        docs = Path(tmp) / "Docs"
        docs.mkdir()
        issues = L.check_log_order(docs)
        assert_eq(len(issues), 0, "log.md 不存在不报")


# ---------------------------------------------------------------------------
# check_related_links (R25, v0.6)
# ---------------------------------------------------------------------------

def fake_page_with_related(page_id: str, related) -> L.WikiPage:
    fm = {"id": page_id}
    if related is not None:
        fm["related"] = related
    text = f"---\nid: {page_id}\n---\n# T\n"
    return L.WikiPage(
        path=Path(f"/fake/{page_id}.md"),
        rel=f"Docs/{page_id}.md",
        page_id=page_id,
        text=text,
        fm=fm,
        fm_lines=3,
    )


def test_related_links():
    print("\n=== check_related_links (v0.6) ===")
    target_current = fake_page_status("60-topics/alive", "current")
    target_stale = fake_page_status("60-topics/old", "stale")
    target_deprecated = fake_page_status("60-topics/dead", "deprecated")

    pages = [
        target_current, target_stale, target_deprecated,
        fake_page_with_related("60-topics/a", None),
        fake_page_with_related("60-topics/b", ["[[60-topics/alive]]"]),
        fake_page_with_related("60-topics/c", ["[[60-topics/old]]"]),
        fake_page_with_related("60-topics/d", ["[[60-topics/dead]]"]),
        fake_page_with_related("60-topics/e", ["[[60-topics/missing]]"]),
        fake_page_with_related("60-topics/f", "应该是 list"),
        fake_page_with_related("60-topics/g", [{"foo": 1}, "[[60-topics/old]]"]),
    ]
    issues = L.check_related_links(pages)
    files = sorted(i.file for i in issues)
    expected = sorted([
        "Docs/60-topics/c.md",
        "Docs/60-topics/d.md",
        "Docs/60-topics/f.md",
        "Docs/60-topics/g.md",
        "Docs/60-topics/g.md",
    ])
    assert_eq(files, expected, "files reported (5 issues: c stale, d deprecated, f type, g[1] dict + g[2] stale)")
    assert all(i.code == "related-mismatch" for i in issues), "all code"
    assert all(i.severity == "warn" for i in issues), "all warn"

    detail_c = [i for i in issues if i.file == "Docs/60-topics/c.md"][0].detail
    assert_in("stale", detail_c, "c stale mentioned")
    detail_d = [i for i in issues if i.file == "Docs/60-topics/d.md"][0].detail
    assert_in("deprecated", detail_d, "d deprecated mentioned")
    detail_f = [i for i in issues if i.file == "Docs/60-topics/f.md"][0].detail
    assert_in("list", detail_f, "f type mentioned")


# ---------------------------------------------------------------------------
# check_ascii_art markdown table 豁免 (R25, v0.6)
# ---------------------------------------------------------------------------

def fake_page_with_text(page_id: str, body: str) -> L.WikiPage:
    text = f"---\nid: {page_id}\ntype: topic\n---\n# T\n\n{body}\n"
    return L.WikiPage(
        path=Path(f"/fake/{page_id}.md"),
        rel=f"Docs/{page_id}.md",
        page_id=page_id,
        text=text,
        fm={"id": page_id, "type": "topic"},
        fm_lines=4,
    )


def test_ascii_art_markdown_table():
    print("\n=== check_ascii_art markdown table 豁免 (v0.6) ===")
    md_table_block = "```\n| 列1 | 列2 |\n|-----|-----|\n| 数据A | 数据B |\n```"
    p = fake_page_with_text("60-topics/table-demo", md_table_block)
    issues = L.check_ascii_art([p])
    assert_eq(len(issues), 0, "markdown table separator 豁免(原本会因 |...|...| 触发 fallback pattern)")

    box_block = "```\n+-----+-----+\n| a   | b   |\n+-----+-----+\n```"
    p = fake_page_with_text("60-topics/box-demo", box_block)
    issues = L.check_ascii_art([p])
    assert_eq(len(issues), 1, "纯 ASCII box(无 markdown separator)仍报")
    assert_eq(issues[0].code, "ascii-art", "code")

    no_sep_pipes = "```\n| a | b |\n| c | d |\n```"
    p = fake_page_with_text("60-topics/pipes-demo", no_sep_pipes)
    issues = L.check_ascii_art([p])
    assert_eq(len(issues), 1, "只有 |...|...| 但无 separator 仍按 ASCII art 处理(歧义降级 warn)")

    aligned_sep = "```\n| col1 | col2 | col3 |\n|:-----|:----:|------:|\n| x | y | z |\n```"
    p = fake_page_with_text("60-topics/aligned-demo", aligned_sep)
    issues = L.check_ascii_art([p])
    assert_eq(len(issues), 0, "对齐 separator (|:--|:--:|--:|) 也豁免")


if __name__ == "__main__":
    test_menu_label()
    test_bat_chcp()
    test_last_synced()
    test_duplicate_entity()
    test_prerequisites()
    test_log_order()
    test_related_links()
    test_ascii_art_markdown_table()
    print("\n[ALL OK] R18 + R19 + R21 + R25 lint 检测器单元测试全部通过")
