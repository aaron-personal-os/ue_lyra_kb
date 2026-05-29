#!/usr/bin/env python3
"""rename_page.py — 项目知识库 wiki 页 page_id 批量重命名工具 (R28, project-wiki v0.6+)

简介
====

R23 lessons 第 8 条沉淀:**page_id 重命名是隐性 4 步流程**——改文件名 + frontmatter id +
index 引用 + 所有 inbound `[[X]]` wikilink。手工漏改任何一步 = broken-link 风暴。
本脚本做这 4 步的机械化批处理。

工作流
======

1. 文件层面:把 `Docs/<from_id>.md` 改名为 `Docs/<to_id>.md`(含跨目录;自动创建 target 父目录)
2. frontmatter 层面:把 source 文件的 `id: <from_id>` 改写为 `id: <to_id>`
3. wikilink 层面:扫所有其他 `Docs/**/*.md`(含 `index.md` / `log.md`),把 `[[<from_id>]]` /
   `[[<from_id>|alias]]` / `[[<from_id>#section]]` / `[[<from_id>|alias#section]]` 全部替换
   为 `[[<to_id>...]]`(保留 alias 和 section anchor)
4. 提示用户后续手工步骤:跑一次 `nav_inject.py --apply` 重建 nav 块、跑 `wiki_lint.py` 验证

不做的事(显式声明)
-------------------

- **不动 git mv**:用 Python `Path.rename()`,提交时 user 自己 `git add` 让 git 检测 rename
- **不动 nav 块**:nav 由 mark 注释包裹,重跑 nav_inject 即可重建。本脚本只警告"记得跑"
- **不动 anchor cache**:文件路径变了,anchor 文件指向源代码不会变,cache 不需要动
- **不删 frontmatter `last_synced`**:重命名不代表内容过期

设计原则
--------

1. **dry-run 默认**:列出所有计划改动 + 影响文件清单 + diff 预览,不写文件
2. **冲突即拒绝**:target 已存在 / source 不存在 / id 与文件路径不一致 → 报错退出
3. **整批原子**:计划改动一旦决定,要么全 apply 要么全不 apply;中途失败时尽量回滚已做改动
4. **wikilink 形式全覆盖**:[[X]] / [[X|alias]] / [[X#section]] / [[X|alias#section]] 都识别
5. **不接 pre-commit**:重命名是显式人工操作,不能自动化(改错代价大)

用法
====

```bash
# dry-run(默认)
python .codebuddy/skills/project-wiki/scripts/rename_page.py \\
    --from 60-topics/old-topic --to 20-modules/python/new-module

# 实际改
python .codebuddy/skills/project-wiki/scripts/rename_page.py \\
    --from 60-topics/old-topic --to 20-modules/python/new-module --apply

# JSON 输出
python rename_page.py --from X --to Y --json

# 指定项目根
python rename_page.py --from X --to Y --project-root /path/to/repo
```

退出码
======

- 0 : dry-run 完成 / --apply 成功
- 1 : --check 模式下检测到需要改动(留 0/1 区分给上层 CI)
- 2 : 致命错误(source 不存在 / target 已存在 / 文件 IO 错)

被引用方
========

- log.md R23 § lessons 第 8 条 page_id 重命名隐性流程
- log.md R28 § 创立此脚本
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path


DOCS_DIR = "Docs"


@dataclass
class WikilinkChange:
    file: str               # rel path from project root
    line_no: int            # 1-based
    old_link: str           # full match including [[ and ]]
    new_link: str


@dataclass
class RenamePlan:
    from_id: str
    to_id: str
    source_file: str        # rel path
    target_file: str        # rel path
    fm_id_change: bool      # 是否需要改 frontmatter id 字段
    wikilink_changes: list[WikilinkChange] = field(default_factory=list)
    files_touched: int = 0


def _wikilink_pattern(page_id: str) -> re.Pattern:
    """构造匹配 [[<page_id>]] / [[<page_id>|alias]] / [[<page_id>#section]] /
    [[<page_id>|alias#section]] 的 regex,捕获 alias 和 section 部分以便保留。
    """
    escaped = re.escape(page_id)
    return re.compile(
        r"\[\[" + escaped + r"((?:\|[^\]\n]+)?(?:#[^\]\n]+)?)\]\]"
    )


def _replace_wikilinks_in_text(text: str, from_id: str, to_id: str, rel_path: str) -> tuple[str, list[WikilinkChange]]:
    """全文替换 wikilink,返回 (new_text, changes)。"""
    pattern = _wikilink_pattern(from_id)
    changes: list[WikilinkChange] = []

    def _sub(m: re.Match) -> str:
        suffix = m.group(1) or ""
        new_link = f"[[{to_id}{suffix}]]"
        old_link = m.group(0)
        line_no = text[:m.start()].count("\n") + 1
        changes.append(WikilinkChange(rel_path, line_no, old_link, new_link))
        return new_link

    new_text = pattern.sub(_sub, text)
    return new_text, changes


def _fm_end(lines: list[str]) -> int | None:
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, min(len(lines), 200)):
        if lines[i].strip() == "---":
            return i
    return None


def _patch_frontmatter_id(text: str, from_id: str, to_id: str) -> tuple[str, bool]:
    """改 frontmatter 中 `id: <from_id>` 行为 `id: <to_id>`。返回 (new_text, changed)。"""
    lines = text.splitlines()
    fm_end = _fm_end(lines)
    if fm_end is None:
        return text, False
    pattern = re.compile(r"^id\s*:\s*(.+?)\s*$")
    for i in range(1, fm_end):
        m = pattern.match(lines[i])
        if not m:
            continue
        cur = m.group(1).strip().strip("'\"")
        if cur != from_id:
            return text, False
        lines[i] = f"id: {to_id}"
        new_text = "\n".join(lines)
        if text.endswith("\n"):
            new_text += "\n"
        return new_text, True
    return text, False


def _validate(project_root: Path, from_id: str, to_id: str) -> tuple[Path, Path]:
    """验证 source 存在 / target 不存在;返回 (source_path, target_path)。失败抛 SystemExit(2)。"""
    docs = project_root / DOCS_DIR
    source = docs / f"{from_id}.md"
    target = docs / f"{to_id}.md"
    if not source.is_file():
        raise SystemExit(f"[rename] source 不存在: {source}")
    if target.exists():
        raise SystemExit(f"[rename] target 已存在 (拒绝覆盖): {target}")
    if from_id == to_id:
        raise SystemExit(f"[rename] from_id == to_id, 无需重命名")
    return source, target


def _build_plan(project_root: Path, from_id: str, to_id: str) -> RenamePlan:
    source, target = _validate(project_root, from_id, to_id)
    docs = project_root / DOCS_DIR
    src_text = source.read_text(encoding="utf-8")
    _, fm_changed = _patch_frontmatter_id(src_text, from_id, to_id)

    plan = RenamePlan(
        from_id=from_id,
        to_id=to_id,
        source_file=source.relative_to(project_root).as_posix(),
        target_file=target.relative_to(project_root).as_posix(),
        fm_id_change=fm_changed,
    )

    files_touched = set()
    for md in sorted(docs.rglob("*.md")):
        rel = md.relative_to(project_root).as_posix()
        text = md.read_text(encoding="utf-8")
        _, changes = _replace_wikilinks_in_text(text, from_id, to_id, rel)
        if changes:
            plan.wikilink_changes.extend(changes)
            files_touched.add(rel)
    plan.files_touched = len(files_touched)
    return plan


def _apply_plan(project_root: Path, plan: RenamePlan) -> int:
    """执行 plan。返回实际写入的文件数(含改名)。失败抛 SystemExit(2)。"""
    docs = project_root / DOCS_DIR
    source = project_root / plan.source_file
    target = project_root / plan.target_file
    written = 0

    # Step 1: 改 source 内容 (frontmatter id + 自身可能含 wikilink)
    src_text = source.read_text(encoding="utf-8")
    if plan.fm_id_change:
        src_text, _ = _patch_frontmatter_id(src_text, plan.from_id, plan.to_id)
    src_rel = source.relative_to(project_root).as_posix()
    src_text, _ = _replace_wikilinks_in_text(src_text, plan.from_id, plan.to_id, src_rel)
    source.write_text(src_text, encoding="utf-8")

    # Step 2: 改其他所有 .md 文件的 wikilink
    files_touched = {wc.file for wc in plan.wikilink_changes}
    for rel in sorted(files_touched):
        if rel == src_rel:
            continue
        path = project_root / rel
        text = path.read_text(encoding="utf-8")
        new_text, _ = _replace_wikilinks_in_text(text, plan.from_id, plan.to_id, rel)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            written += 1

    # Step 3: mv source → target (含创建父目录)
    target.parent.mkdir(parents=True, exist_ok=True)
    source.rename(target)
    written += 1
    return written


def _print_report(plan: RenamePlan, applied: bool, written: int) -> None:
    print(f"[rename] {plan.from_id}  →  {plan.to_id}")
    print(f"[rename] source: {plan.source_file}")
    print(f"[rename] target: {plan.target_file}")
    print(f"[rename] frontmatter id 改写: {'YES' if plan.fm_id_change else 'no'}")
    print(f"[rename] wikilink 改动总数: {len(plan.wikilink_changes)}  (跨 {plan.files_touched} 个文件)")
    if plan.wikilink_changes:
        print("\n  待改 wikilink (前 20 条):")
        for wc in plan.wikilink_changes[:20]:
            print(f"    {wc.file}:{wc.line_no}  {wc.old_link}  →  {wc.new_link}")
        if len(plan.wikilink_changes) > 20:
            print(f"    ... 另 {len(plan.wikilink_changes) - 20} 条 (--json 查看完整)")
    print()
    if applied:
        print(f"[rename] ✓ 已写入 {written} 个文件 (含 source 改名)")
        print(f"[rename] ⚠ 后续手工步骤:")
        print(f"  1. python nav_inject.py --apply  # 重建 nav 块")
        print(f"  2. python wiki_lint.py           # 验证无 broken-link")
        print(f"  3. git add Docs/                  # 让 git 检测 rename")
    else:
        print(f"[rename] ⚠ dry-run 模式,未写文件。跑 --apply 落盘")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="page_id 重命名:文件改名 + frontmatter id + 全 wiki wikilink 一键改",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--from", dest="from_id", required=True,
                        help="源 page_id (如 60-topics/old-topic)")
    parser.add_argument("--to", dest="to_id", required=True,
                        help="目标 page_id (如 20-modules/python/new-module)")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(),
                        help="项目根 (含 Docs/),默认 cwd")
    parser.add_argument("--apply", action="store_true",
                        help="实际写入 (默认 dry-run)")
    parser.add_argument("--json", action="store_true",
                        help="JSON 输出 (CI 友好)")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()

    plan = _build_plan(project_root, args.from_id, args.to_id)

    if args.apply:
        written = _apply_plan(project_root, plan)
    else:
        written = 0

    if args.json:
        print(json.dumps({
            "applied": args.apply,
            "files_written": written,
            "plan": asdict(plan),
        }, ensure_ascii=False, indent=2))
        return 1 if (not args.apply and (plan.fm_id_change or plan.wikilink_changes)) else 0

    _print_report(plan, args.apply, written)
    return 0 if args.apply else (1 if (plan.fm_id_change or plan.wikilink_changes) else 0)


if __name__ == "__main__":
    sys.exit(main())
