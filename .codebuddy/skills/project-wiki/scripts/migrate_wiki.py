#!/usr/bin/env python3
"""migrate_wiki.py — 知识库架构重构一次性迁移脚本

将原"AI 开发助手"架构迁移为"UE 技术学习知识库"架构。

功能:
1. 按映射表移动 .md 文件到新路径
2. 更新所有被移动文件的 frontmatter id 字段
3. 全局替换所有 .md 文件中的 wikilink 引用
4. 报告迁移结果

用法:
    # dry-run (默认)
    python migrate_wiki.py

    # 实际执行
    python migrate_wiki.py --apply

    # 指定项目根
    python migrate_wiki.py --project-root /path/to/repo --apply
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# 路径映射表（长路径优先，避免短前缀误匹配）
# ---------------------------------------------------------------------------

PREFIX_RENAMES = [
    # 教程系列: 50-references 下迁入 30-tutorials
    ("50-references/ue-framework/",     "30-tutorials/ue-framework/"),
    ("50-references/gas-tutorial/",     "30-tutorials/gas/"),
    ("50-references/network-sync/",     "30-tutorials/network-sync/"),
    ("50-references/animation-system/", "30-tutorials/animation/"),
    ("50-references/niagara-system/",   "30-tutorials/niagara/"),
    # 注意: 50-references/ 下其余内容(ue-official, articles, third-party)保留不动
    # 级联重编号
    ("30-decisions/",                   "60-decisions/"),
    ("60-topics/",                      "70-topics/"),
    ("70-gotchas/",                     "80-gotchas/"),
    ("80-snapshots/",                   "90-snapshots/"),
]


def map_page_id(old_id: str) -> str | None:
    """如果 old_id 匹配某个映射规则，返回 new_id；否则返回 None。"""
    for old_prefix, new_prefix in PREFIX_RENAMES:
        if old_id.startswith(old_prefix):
            return new_prefix + old_id[len(old_prefix):]
    return None


# ---------------------------------------------------------------------------
# Wikilink 替换
# ---------------------------------------------------------------------------

# 匹配 [[id]], [[id|alias]], [[id#section]], [[id#section|alias]] 等形态
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)((?:[#|][^\]]*)?)\]\]")


def replace_wikilinks_in_text(text: str) -> tuple[str, int]:
    """替换文本中所有匹配映射的 wikilink。返回 (new_text, change_count)。"""
    count = 0

    def _sub(m: re.Match) -> str:
        nonlocal count
        target = m.group(1).strip()
        suffix = m.group(2)  # #section 或 |alias 或 #section|alias
        new_target = map_page_id(target)
        if new_target is not None:
            count += 1
            return f"[[{new_target}{suffix}]]"
        return m.group(0)

    new_text = WIKILINK_RE.sub(_sub, text)
    return new_text, count


# ---------------------------------------------------------------------------
# Frontmatter id 替换
# ---------------------------------------------------------------------------

FM_ID_RE = re.compile(r"^(id\s*:\s*)(.+?)\s*$", re.MULTILINE)


def replace_fm_id(text: str) -> tuple[str, bool]:
    """替换 frontmatter 中的 id 字段。返回 (new_text, changed)。"""
    changed = False

    def _sub(m: re.Match) -> str:
        nonlocal changed
        old_id = m.group(2).strip().strip("'\"")
        new_id = map_page_id(old_id)
        if new_id is not None:
            changed = True
            return f"{m.group(1)}{new_id}"
        return m.group(0)

    # 只在 frontmatter 区域内替换 (开头 --- 到第二个 ---)
    if not text.startswith("---"):
        return text, False

    lines = text.split("\n")
    fm_end = -1
    for i in range(1, min(len(lines), 200)):
        if lines[i].strip() == "---":
            fm_end = i
            break
    if fm_end < 0:
        return text, False

    fm_text = "\n".join(lines[:fm_end + 1])
    body_text = "\n".join(lines[fm_end + 1:])

    new_fm = FM_ID_RE.sub(_sub, fm_text)
    return new_fm + "\n" + body_text, changed


# ---------------------------------------------------------------------------
# 收集 Docs/ 下所有 .md 文件
# ---------------------------------------------------------------------------

def collect_all_md(docs_root: Path) -> list[Path]:
    """收集 Docs/ 下所有 .md 文件（含 _raw/）。"""
    return sorted(docs_root.rglob("*.md"))


# ---------------------------------------------------------------------------
# 迁移逻辑
# ---------------------------------------------------------------------------

def build_file_moves(docs_root: Path) -> list[tuple[Path, Path, str, str]]:
    """构建文件移动列表。返回 [(src_path, dst_path, old_id, new_id)]。"""
    moves = []
    for md_file in collect_all_md(docs_root):
        rel = md_file.relative_to(docs_root).as_posix()
        old_id = rel.removesuffix(".md")
        new_id = map_page_id(old_id)
        if new_id is not None:
            dst = docs_root / f"{new_id}.md"
            moves.append((md_file, dst, old_id, new_id))
    return moves


def run_migration(project_root: Path, apply: bool) -> int:
    docs_root = project_root / "Docs"
    if not docs_root.is_dir():
        print(f"[ERROR] Docs/ 不存在: {docs_root}", file=sys.stderr)
        return 2

    # Phase 1: 构建文件移动计划
    moves = build_file_moves(docs_root)
    print(f"\n{'='*60}")
    print(f"知识库架构迁移 {'[APPLY]' if apply else '[DRY-RUN]'}")
    print(f"{'='*60}")
    print(f"\n文件移动: {len(moves)} 个")
    for src, dst, old_id, new_id in moves:
        print(f"  {old_id}  →  {new_id}")

    # Phase 2: 如果 apply，先移动文件
    if apply:
        print(f"\n--- 移动文件 ---")
        for src, dst, old_id, new_id in moves:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f"  ✓ {old_id} → {new_id}")

        # 清理可能留下的空目录
        for old_prefix, _ in PREFIX_RENAMES:
            old_dir = docs_root / old_prefix.rstrip("/")
            if old_dir.is_dir():
                try:
                    _remove_empty_dirs(old_dir)
                except Exception:
                    pass

    # Phase 3: 全局替换所有 .md 文件中的 wikilink 和 frontmatter id
    all_md = collect_all_md(docs_root)
    # 也扫描 _raw/ 下的文件（它们可能包含 wikilink）
    # 以及 Docs/ 外的关键文件
    extra_files = [
        project_root / "CODEBUDDY.md",
        project_root / "Docs" / "log.md",
    ]
    scan_files = list(all_md)
    for ef in extra_files:
        if ef.is_file() and ef not in scan_files:
            scan_files.append(ef)

    total_wikilink_changes = 0
    total_fm_changes = 0
    files_modified = []

    print(f"\n--- 扫描 wikilink + frontmatter id ({len(scan_files)} 个文件) ---")
    for md_file in scan_files:
        try:
            text = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        new_text, wl_count = replace_wikilinks_in_text(text)
        new_text, fm_changed = replace_fm_id(new_text)

        if wl_count > 0 or fm_changed:
            total_wikilink_changes += wl_count
            if fm_changed:
                total_fm_changes += 1
            rel = md_file.relative_to(project_root).as_posix()
            files_modified.append((rel, wl_count, fm_changed))
            if apply:
                md_file.write_text(new_text, encoding="utf-8")

    print(f"\n--- 替换统计 ---")
    print(f"  wikilink 替换: {total_wikilink_changes} 处")
    print(f"  frontmatter id 替换: {total_fm_changes} 个文件")
    print(f"  影响文件数: {len(files_modified)}")

    if files_modified:
        print(f"\n  影响文件清单:")
        for rel, wl_count, fm_changed in files_modified:
            parts = []
            if wl_count:
                parts.append(f"{wl_count} wikilinks")
            if fm_changed:
                parts.append("frontmatter id")
            print(f"    {rel}  ({', '.join(parts)})")

    print(f"\n{'='*60}")
    if apply:
        print(f"✓ 迁移完成！")
        print(f"  后续步骤:")
        print(f"  1. 运行 wiki_lint.py 验证")
        print(f"  2. 更新 index.md section 标题")
        print(f"  3. 更新基础设施文件 (wiki_lint.py, templates, workflows)")
    else:
        print(f"⚠ DRY-RUN 模式，未写文件。运行 --apply 执行迁移。")
    print(f"{'='*60}")

    return 0


def _remove_empty_dirs(path: Path):
    """递归删除空目录。"""
    if not path.is_dir():
        return
    for child in path.iterdir():
        if child.is_dir():
            _remove_empty_dirs(child)
    # 如果目录现在是空的（只有 .gitkeep 也算空）
    remaining = list(path.iterdir())
    if not remaining:
        path.rmdir()
    elif len(remaining) == 1 and remaining[0].name == ".gitkeep":
        remaining[0].unlink()
        path.rmdir()


def main():
    parser = argparse.ArgumentParser(description="知识库架构重构迁移脚本")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[4]),
                        help="项目根目录")
    parser.add_argument("--apply", action="store_true",
                        help="实际执行迁移（默认 dry-run）")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    sys.exit(run_migration(project_root, args.apply))


if __name__ == "__main__":
    main()
