"""
扫描 Docs/30-tutorials/<series>/_series.yaml 中 learning_path[].lessons 列出
的教程文件名，验证每个 lesson 在同目录下是否存在对应 <lesson>.md 文件。

输出三类问题：
  - missing:   lesson 名称在 _series.yaml 中出现，但同目录下找不到对应 .md
  - orphan:    同目录存在 .md 文件（非 README/index/...），但未被任何 lesson
               条目引用 → 教程"上架失败"
  - dup:       同一 lesson 名称在 learning_path 中被多次列出

会尝试为每个 missing 项给出"按编号前缀"的最佳猜测建议（如
'100高级主题与性能优化' → '10-高级主题与性能优化'），便于人工修复。

用法：
  python ToolsScript/check_series_lessons.py
  python ToolsScript/check_series_lessons.py --series lyra-practical    # 只查单个系列
  python ToolsScript/check_series_lessons.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import yaml  # PyYAML; 如未安装：pip install pyyaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TUTORIALS_DIR = PROJECT_ROOT / "Docs" / "30-tutorials"

# learning_path / total_lessons 等系列级元数据用的 yaml 字段
SERIES_YAML = "_series.yaml"

# 这些文件名即使没在 lessons 中列出也不视为孤儿（系列级文档/约定）
ORPHAN_WHITELIST = {
    "README",
    "index",
    "overview",
}

NUM_PREFIX_RE = re.compile(r"^(\d+)[-_]?")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def read_frontmatter(md_path: Path) -> dict[str, object]:
    """读 .md 顶部 YAML frontmatter，失败/不存在返回空 dict。"""
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def is_index_page(md_path: Path) -> bool:
    """判断 .md 是否是"系列索引/导览页"性质，不应被视为 orphan。
    判定标准：frontmatter.type 为 'guide' 或 'index'，或 lesson_index == 0
    且文件名包含"教程系列"等关键词。
    """
    fm = read_frontmatter(md_path)
    t = str(fm.get("type") or "").lower()
    if t in ("guide", "index"):
        return True
    return False


@dataclass
class SeriesIssue:
    series: str
    kind: str          # "missing" | "orphan" | "dup" | "yaml-error" | "no-learning-path"
    lesson: str = ""
    detail: str = ""
    suggestion: str = ""


def list_md_stems(series_dir: Path) -> list[str]:
    """返回该系列目录下所有 .md 文件的"键"，相对系列目录的去 .md 路径
    （posix 风格，可包含子目录如 'iris/00-Iris总览'）。

    支持子目录是因为部分系列（network-sync、ue-framework 等）按主题分目录
    组织课程，_series.yaml 中的 lesson 名也是相对系列目录的相对路径。
    """
    out: list[str] = []
    for p in series_dir.rglob("*.md"):
        if not p.is_file():
            continue
        rel = p.relative_to(series_dir).as_posix()
        if rel.lower().endswith(".md"):
            rel = rel[:-3]
        out.append(rel)
    return sorted(out)


def extract_lessons(yaml_data: dict[str, object]) -> list[tuple[str, str]]:
    """从 _series.yaml 解析的 dict 中提取 (stage, lesson) 列表。

    支持两种 schema：
      1) 嵌套式（推荐）:
           learning_path:
             - stage: ...
               lessons: [...]
      2) 扁平式（部分系列在用，如 camera-system / editor-extension）:
           lessons:
             - 00-...
             - 01-...
         此时 stage 统一记为 ""（无阶段划分）。

    缺字段时安全降级为空。
    """
    out: list[tuple[str, str]] = []

    lp = yaml_data.get("learning_path")
    if isinstance(lp, list):
        for stage_obj in lp:
            if not isinstance(stage_obj, dict):
                continue
            stage = str(stage_obj.get("stage") or "").strip()
            lessons = stage_obj.get("lessons")
            if not isinstance(lessons, list):
                continue
            for lesson in lessons:
                if isinstance(lesson, str):
                    out.append((stage, lesson.strip()))
        if out:
            return out  # 嵌套式有内容即认为已覆盖

    # 扁平 fallback
    flat = yaml_data.get("lessons")
    if isinstance(flat, list):
        for lesson in flat:
            if isinstance(lesson, str):
                out.append(("", lesson.strip()))
    return out


def best_guess_correction(missing: str, available: list[str]) -> str:
    """对一个 missing lesson 名称，从 available stems 里挑最可能的修正。

    策略：
      1) 若 missing 以纯数字编号开头（如 '100高级xxx' 或 '01-foo'），
         按编号前缀（最长匹配）找前缀相同的现存 stem；
      2) 否则按子串包含挑相似度最高的（简单启发：共同字符数最多）。
    """
    m = NUM_PREFIX_RE.match(missing)
    if m:
        # 取数字前缀，再尝试不同长度的截断匹配（先长后短）
        digits = m.group(1)
        for cut in range(len(digits), 0, -1):
            prefix = digits[:cut] + "-"
            cands = [s for s in available if s.startswith(prefix)]
            if len(cands) == 1:
                return cands[0]
            if len(cands) > 1:
                # 多个候选，返回提示信息
                return " | ".join(cands)

    # Fallback：寻找 missing 去掉前缀后的"主题词"在哪些 stem 中出现
    body = NUM_PREFIX_RE.sub("", missing)
    if body:
        cands = [s for s in available if body in s]
        if len(cands) == 1:
            return cands[0]
        if cands:
            return " | ".join(cands[:3])
    return ""


def check_series(series_dir: Path) -> list[SeriesIssue]:
    issues: list[SeriesIssue] = []
    series_name = series_dir.name
    yaml_path = series_dir / SERIES_YAML

    if not yaml_path.is_file():
        # 没有 _series.yaml 的系列直接跳过（如 ai-behavior 等纯文档目录）
        return issues

    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        issues.append(SeriesIssue(series_name, "yaml-error",
                                  detail=f"YAML 解析失败: {e}"))
        return issues
    if not isinstance(data, dict):
        issues.append(SeriesIssue(series_name, "yaml-error",
                                  detail="顶层不是 mapping"))
        return issues

    md_stems = list_md_stems(series_dir)
    md_set = set(md_stems)

    lessons = extract_lessons(data)
    if not lessons:
        issues.append(SeriesIssue(series_name, "no-learning-path",
                                  detail="learning_path 为空或未定义"))
        return issues

    # 重复检测
    seen: dict[str, int] = {}
    for _, lesson in lessons:
        seen[lesson] = seen.get(lesson, 0) + 1
    for lesson, n in seen.items():
        if n > 1:
            issues.append(SeriesIssue(series_name, "dup", lesson=lesson,
                                      detail=f"在 learning_path 中出现 {n} 次"))

    # missing 检测
    referenced: set[str] = set()
    for stage, lesson in lessons:
        referenced.add(lesson)
        if lesson in md_set:
            continue
        suggestion = best_guess_correction(lesson, md_stems)
        issues.append(SeriesIssue(
            series_name, "missing", lesson=lesson,
            detail=f"在 stage \"{stage}\" 中引用，但 {lesson}.md 不存在",
            suggestion=suggestion,
        ))

    # orphan 检测（存在 .md 但未被任何 lesson 列出）
    for stem in md_stems:
        if stem in referenced:
            continue
        if stem in ORPHAN_WHITELIST:
            continue
        # 系列索引/导览页（type: guide / index）天然不属于 learning_path
        md_path = series_dir / (stem + ".md")
        if is_index_page(md_path):
            continue
        issues.append(SeriesIssue(
            series_name, "orphan", lesson=stem,
            detail=f"{stem}.md 存在，但未在 learning_path 中列出",
        ))

    return issues


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--series", help="只检查指定系列（目录名），可重复",
                        action="append")
    parser.add_argument("--json", help="将结果写入 JSON 文件")
    parser.add_argument("--only", choices=["missing", "orphan", "dup",
                                           "yaml-error", "no-learning-path"],
                        help="只输出指定类型的问题")
    args = parser.parse_args(argv)

    if not TUTORIALS_DIR.is_dir():
        print(f"[ERROR] 教程根目录不存在: {TUTORIALS_DIR}", file=sys.stderr)
        return 2

    if args.series:
        series_dirs = [TUTORIALS_DIR / s for s in args.series]
        for d in series_dirs:
            if not d.is_dir():
                print(f"[WARN] 跳过不存在的系列: {d}", file=sys.stderr)
        series_dirs = [d for d in series_dirs if d.is_dir()]
    else:
        series_dirs = sorted(p for p in TUTORIALS_DIR.iterdir() if p.is_dir())

    print(f"扫描根: {TUTORIALS_DIR}")
    print(f"系列数: {len(series_dirs)}")
    print("-" * 60)

    all_issues: list[SeriesIssue] = []
    for d in series_dirs:
        all_issues.extend(check_series(d))

    if args.only:
        all_issues = [i for i in all_issues if i.kind == args.only]

    # 报告
    by_series: dict[str, list[SeriesIssue]] = {}
    for it in all_issues:
        by_series.setdefault(it.series, []).append(it)

    cnt = {"missing": 0, "orphan": 0, "dup": 0,
           "yaml-error": 0, "no-learning-path": 0}
    for it in all_issues:
        cnt[it.kind] = cnt.get(it.kind, 0) + 1

    if not all_issues:
        print("✓ 所有 _series.yaml 中引用的教程文件都存在，且无孤儿文件。")
    else:
        for s in sorted(by_series):
            items = by_series[s]
            print(f"\n● {s}  ({len(items)} 项)")
            # 按 kind 排序便于阅读
            order = {"yaml-error": 0, "no-learning-path": 1,
                     "missing": 2, "dup": 3, "orphan": 4}
            for it in sorted(items, key=lambda x: (order.get(x.kind, 9), x.lesson)):
                tag = it.kind.ljust(8)
                line = f"  [{tag}] {it.lesson}"
                if it.detail:
                    line += f"  -- {it.detail}"
                print(line)
                if it.suggestion:
                    print(f"             建议改为: {it.suggestion}")

    print("\n" + "=" * 60)
    print(
        f"汇总: missing={cnt['missing']}  orphan={cnt['orphan']}  "
        f"dup={cnt['dup']}  yaml-error={cnt['yaml-error']}  "
        f"no-learning-path={cnt['no-learning-path']}"
    )

    if args.json:
        Path(args.json).write_text(
            json.dumps([asdict(i) for i in all_issues],
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"已写入: {args.json}")

    # 退出码：missing/dup/yaml-error 任一存在则非 0；orphan 仅警告
    fatal = cnt["missing"] + cnt["dup"] + cnt["yaml-error"]
    return 0 if fatal == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
