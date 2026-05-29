#!/usr/bin/env python3
"""fix_asymm.py — 机械化治理 wiki 页 frontmatter `related:` 的非对称双向链接

简介
====

`wiki_lint.py` 的 **asymm-link** 检查报告 "A 在 related 引了 B，但 B 没回引 A"。
当全项目 asymm-link 累积到几十个，逐页手动改成本太高 —— 本脚本接 lint `--json`
输出，提供两种修法：

- **正向模式（默认）**：在 target 页（B）的 related 末尾追加源页（A）的 `[[id]]`，
  让 B 回引 A（闭环为"B 也认 A 是同伴"）。**保守、零损失语义**，99% 场景适用。
- **★R26 反向模式（`--reverse`）**：在 src 页（A）的 related 中删除 target（B）的
  `[[id]]`，让 A 不再引 B（撤销原引用，接受 B 的视角"我不认 A"）。**有损操作**，
  适合"A 早期写时随手加了 B，但实际上 A 已不该引 B"的场景。

设计原则
--------

1. **只调 lint，不重新实现 wiki 解析**：source-of-truth 是 `wiki_lint.py`，
   所以 lint 算 asymm-link 时已经考虑了"target body 已有 wikilink"等豁免，
   本脚本不重复判断 → 永远跟 lint 视角一致。
2. **dry-run 默认**：先看会改什么，确认无误再 `--apply`。正向 / 反向都遵守。
3. **正向保守追加**：只往 `related:` 末尾加新条目，不动既有顺序。已经存在的跳过。
4. **反向保守删除**：只删除明确出现在 asymm-link pair 的 [[B]] 条目，不动其他
   related。删除后若 `related:` 变空列表，整个 `related:` 节也一并删除（避免空键
   污染 frontmatter）。
5. **反向必须 review 后再 apply**：删除是有损的，默认 dry-run + 列出每个待删
   pair，鼓励用户人工 review（尤其 ADR / 设计文档类引用，可能是历史性引用不该删）。
6. **frontmatter 缺失页面不处理**：这是 schema 设计（meta 类页约定无 fm），
   会被 lint 的 `asymm-link` 白名单跳过，所以一般遇不到。

用法
====

正向模式（默认）：

    # dry-run（默认，不改文件）
    python .codebuddy/skills/project-wiki/scripts/fix_asymm.py

    # 实际写入
    python .codebuddy/skills/project-wiki/scripts/fix_asymm.py --apply

反向模式（★R26）：

    # dry-run 看会删什么（强烈建议先跑这一步 review）
    python .codebuddy/skills/project-wiki/scripts/fix_asymm.py --reverse

    # 实际删除（需要人工 review 上一步输出后再跑）
    python .codebuddy/skills/project-wiki/scripts/fix_asymm.py --reverse --apply

通用：

    # JSON 输出（CI / 进一步处理）
    python .codebuddy/skills/project-wiki/scripts/fix_asymm.py --json

    # 指定项目根
    python .codebuddy/skills/project-wiki/scripts/fix_asymm.py --project-root /path/to/repo

    # 用现成的 lint json（避免重复跑 lint）
    python wiki_lint.py --json > /tmp/lint.json
    python fix_asymm.py --lint-json /tmp/lint.json

退出码
------

    0  无 pair 需要修复 / dry-run 完成
    0  --apply / --reverse --apply 成功（即便 0 修改）
    2  脚本本身错（lint 调不起来 / 解析失败）

典型工作流（R18 实战，52 → 0 asymm-link）：

    1. python wiki_lint.py            # 看到 52 个 asymm-link warnings
    2. python fix_asymm.py            # dry-run 看正向准备改什么
    3. python fix_asymm.py --apply    # 实际改（闭环大多数 pair）
    4. python wiki_lint.py            # 验证已清零（剩下的是 meta 页豁免）

★R26 反向场景：

    1. python wiki_lint.py | grep asymm-link  # 找剩下确认是历史包袱的 pair
    2. python fix_asymm.py --reverse          # dry-run 看会删谁
    3. 人工 review，确认是"误链 / 过时"而非"有意义的单向引用"
    4. python fix_asymm.py --reverse --apply  # 落盘

被引用方
--------

- [[40-runbooks/use-wiki-lint]] § asymm-link 治锁工作流
- log.md R18 § A1 创立此脚本（当时位于 .git/，R19 提升为正式 skill 工具）
- log.md R26 § 反向模式上线
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

WIKI_LINT_REL = ".codebuddy/skills/project-wiki/scripts/wiki_lint.py"
DOCS_DIR = "Docs"


def run_lint_json(project_root: Path, python_bin: str | None = None) -> list[dict]:
    """跑 wiki_lint.py --json 并返回 issues 列表。"""
    py = python_bin or sys.executable
    script = project_root / WIKI_LINT_REL
    if not script.is_file():
        raise SystemExit(f"[asymm-fix] lint 脚本不存在: {script}")
    proc = subprocess.run(
        [py, str(script), "--json", "--project-root", str(project_root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode > 1:  # 0 = clean, 1 = warn, 2+ = error or script crash
        sys.stderr.write(f"[asymm-fix] lint 退出码 {proc.returncode}, stderr:\n{proc.stderr[-500:]}\n")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise SystemExit(f"[asymm-fix] lint --json 输出非合法 JSON: {e}")
    issues = data.get("issues", data) if isinstance(data, dict) else data
    if not isinstance(issues, list):
        raise SystemExit("[asymm-fix] lint --json 输出无 issues 列表")
    return issues


def parse_pairs(issues: list[dict]) -> list[tuple[str, str]]:
    """从 lint issues 抽出 (src_id, target_id) pair。"""
    pairs: list[tuple[str, str]] = []
    for it in issues:
        if it.get("code") != "asymm-link":
            continue
        f = it.get("file", "")
        m_src = re.search(r"Docs/(.+)\.md", f.replace("\\", "/"))
        if not m_src:
            continue
        src_id = m_src.group(1)
        detail = it.get("detail", "")
        ids = re.findall(r"\[\[([^\]]+)\]\]", detail)
        if len(ids) < 2:
            continue
        target_id = ids[0].split("|")[0].split("#")[0]
        pairs.append((src_id, target_id))
    return pairs


def patch_related(lines: list[str], add_ids: list[str]) -> tuple[list[str], int, str]:
    """在 frontmatter `related:` block 末尾追加 add_ids 中尚未出现的项。

    返回 (new_lines, added_count, reason)
    reason ∈ {'no-frontmatter', 'no-frontmatter-end', 'already-present', 'added'}
    """
    if not lines or lines[0].strip() != "---":
        return lines, 0, "no-frontmatter"
    fm_end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm_end = i
            break
    if fm_end is None:
        return lines, 0, "no-frontmatter-end"

    related_start = None
    related_end = None
    for i in range(1, fm_end):
        s = lines[i]
        if related_start is None and re.match(r"^related\s*:\s*$", s):
            related_start = i
            j = i + 1
            while j < fm_end and (
                lines[j].startswith("  -")
                or (lines[j].startswith("  ") and lines[j].strip() != "")
            ):
                j += 1
            related_end = j
            break

    existing = set()
    if related_start is not None:
        for k in range(related_start + 1, related_end):
            mm = re.search(r"\[\[([^\]]+)\]\]", lines[k])
            if mm:
                existing.add(mm.group(1))

    body_text = "\n".join(lines[fm_end + 1:])
    body_links = {
        m.group(1).split("|")[0].split("#")[0]
        for m in re.finditer(r"\[\[([^\]]+)\]\]", body_text)
    }

    to_add = sorted({x for x in add_ids if x not in existing and x not in body_links})
    if not to_add:
        return lines, 0, "already-present"

    new_entries = [f'  - "[[{x}]]"' for x in to_add]
    if related_start is None:
        ins = fm_end
        new_block = ["related:"] + new_entries
        lines = lines[:ins] + new_block + lines[ins:]
    else:
        lines = lines[:related_end] + new_entries + lines[related_end:]
    return lines, len(to_add), "added"


def patch_related_remove(lines: list[str], remove_ids: list[str]) -> tuple[list[str], int, str]:
    """★R26 反向模式★ 从 frontmatter `related:` block 删除 remove_ids 中的项。

    返回 (new_lines, removed_count, reason)
    reason ∈ {'no-frontmatter', 'no-frontmatter-end', 'no-related-block',
              'none-matched', 'removed', 'removed-and-emptied'}

    设计:
    - 只删除明确出现在 remove_ids 中的 [[X]] 条目,不动其他 related
    - 如果 related: block 删完后变空,把整个 `related:` 节(从 'related:' 行到
      最后一项)也一并删除,避免空键污染 frontmatter
    """
    if not lines or lines[0].strip() != "---":
        return lines, 0, "no-frontmatter"
    fm_end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm_end = i
            break
    if fm_end is None:
        return lines, 0, "no-frontmatter-end"

    related_start = None
    related_end = None
    for i in range(1, fm_end):
        s = lines[i]
        if related_start is None and re.match(r"^related\s*:\s*$", s):
            related_start = i
            j = i + 1
            while j < fm_end and (
                lines[j].startswith("  -")
                or (lines[j].startswith("  ") and lines[j].strip() != "")
            ):
                j += 1
            related_end = j
            break

    if related_start is None:
        return lines, 0, "no-related-block"

    remove_set = set(remove_ids)
    keep_indices: list[int] = []
    removed = 0
    for k in range(related_start + 1, related_end):
        mm = re.search(r"\[\[([^\]]+)\]\]", lines[k])
        target_id = mm.group(1).split("|")[0].split("#")[0].strip() if mm else None
        if target_id in remove_set:
            removed += 1
        else:
            keep_indices.append(k)

    if removed == 0:
        return lines, 0, "none-matched"

    # 重建 lines:删掉 related block 中标记为"删除"的行
    if not keep_indices:
        # related: 全删空 -> 整个 related 节(包括 'related:' 行)删掉
        new_lines = lines[:related_start] + lines[related_end:]
        return new_lines, removed, "removed-and-emptied"

    # 部分保留:重组 related block
    kept_lines = [lines[k] for k in keep_indices]
    new_lines = lines[:related_start + 1] + kept_lines + lines[related_end:]
    return new_lines, removed, "removed"


def _run_forward(pairs: list[tuple[str, str]], docs: Path, *, apply: bool) -> dict:
    """正向模式:在 target 页追加 src wikilink。"""
    by_target: dict[str, list[str]] = defaultdict(list)
    for src, target in pairs:
        if src not in by_target[target]:
            by_target[target].append(src)

    report: dict = {
        "mode": "forward",
        "pairs": len(pairs),
        "targets": len(by_target),
        "applied": apply,
        "actions": [],
    }
    total = 0
    for target, srcs in sorted(by_target.items()):
        path = docs / f"{target}.md"
        if not path.exists():
            report["actions"].append({"target": target, "changed": 0, "reason": "page-missing", "wanted": srcs})
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        new_lines, added, reason = patch_related(lines, srcs)
        report["actions"].append({"target": target, "changed": added, "reason": reason, "wanted": srcs})
        if added > 0 and apply:
            path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        total += added
    report["total_changed"] = total
    return report


def _run_reverse(pairs: list[tuple[str, str]], docs: Path, *, apply: bool) -> dict:
    """★R26 反向模式★ 在 src 页删除 target wikilink。"""
    by_src: dict[str, list[str]] = defaultdict(list)
    for src, target in pairs:
        if target not in by_src[src]:
            by_src[src].append(target)

    report: dict = {
        "mode": "reverse",
        "pairs": len(pairs),
        "sources": len(by_src),
        "applied": apply,
        "actions": [],
    }
    total = 0
    for src, targets in sorted(by_src.items()):
        path = docs / f"{src}.md"
        if not path.exists():
            report["actions"].append({"source": src, "changed": 0, "reason": "page-missing", "to_remove": targets})
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        new_lines, removed, reason = patch_related_remove(lines, targets)
        report["actions"].append({"source": src, "changed": removed, "reason": reason, "to_remove": targets})
        if removed > 0 and apply:
            path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        total += removed
    report["total_changed"] = total
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="机械化治理 asymm-link 的双向 related (正向追加 / 反向删除)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--project-root", default=str(Path.cwd()),
                    help="项目根目录（默认当前目录）")
    ap.add_argument("--apply", action="store_true",
                    help="实际写入文件（默认 dry-run）")
    ap.add_argument("--reverse", action="store_true",
                    help="★R26★ 反向模式:删除 src 页 related 中的 target wikilink (有损,需 review)")
    ap.add_argument("--json", action="store_true",
                    help="JSON 输出报告（CI 友好）")
    ap.add_argument("--lint-json", default=None,
                    help="读现成的 lint --json 文件（不重新跑 lint）")
    ap.add_argument("--python", default=None,
                    help="跑 wiki_lint 的 python 解释器（默认当前 sys.executable）")
    args = ap.parse_args(argv)

    project_root = Path(args.project_root).resolve()

    if args.lint_json:
        try:
            data = json.loads(Path(args.lint_json).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[asymm-fix] 读 lint json 失败: {e}", file=sys.stderr)
            return 2
        issues = data.get("issues", data) if isinstance(data, dict) else data
    else:
        issues = run_lint_json(project_root, args.python)

    pairs = parse_pairs(issues)
    docs = project_root / DOCS_DIR

    if args.reverse:
        report = _run_reverse(pairs, docs, apply=args.apply)
    else:
        report = _run_forward(pairs, docs, apply=args.apply)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        mode_label = "REVERSE (delete)" if args.reverse else "FORWARD (append)"
        print(f"[asymm-fix] 模式: {mode_label}")
        print(f"[asymm-fix] 解析到 {len(pairs)} 个 asymm-link pair")
        if args.reverse:
            print(f"[asymm-fix] 涉及 {report['sources']} 个源页\n")
            for e in report["actions"]:
                tag = "DELETE" if (args.apply and e["changed"] > 0) else (
                    "DRY-RM" if e["changed"] > 0 else "skip  "
                )
                if e["changed"] > 0:
                    print(f"  [{tag}] {e['source']}: -{e['changed']} -> {e['to_remove']}  reason={e['reason']}")
                else:
                    print(f"  [{tag}] {e['source']}: 0 ({e['reason']}) to_remove={e['to_remove']}")
            verb = "删除"
        else:
            print(f"[asymm-fix] 涉及 {report['targets']} 个目标页\n")
            for e in report["actions"]:
                tag = "WRITE " if (args.apply and e["changed"] > 0) else (
                    "DRY-AD" if e["changed"] > 0 else "skip  "
                )
                if e["changed"] > 0:
                    print(f"  [{tag}] {e['target']}: +{e['changed']} <- {e['wanted']}")
                else:
                    print(f"  [{tag}] {e['target']}: 0 ({e['reason']}) wanted={e['wanted']}")
            verb = "追加"
        run_mode = "apply" if args.apply else "dry-run"
        print(f"\n[asymm-fix] 共计{verb} {report['total_changed']} 条 related ({run_mode})")
        if args.reverse and not args.apply and report["total_changed"] > 0:
            print(f"[asymm-fix] ⚠ 反向模式有损操作,务必 review 上方报告再跑 --apply")

    return 0


if __name__ == "__main__":
    sys.exit(main())
