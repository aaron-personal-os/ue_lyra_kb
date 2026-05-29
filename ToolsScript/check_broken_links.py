"""
扫描 Docs/30-tutorials/ 下所有 Markdown 文档的链接，报告：
  1. 链接目标文件不存在；
  2. 链接目标存在但不在 Docs/30-tutorials/ 范围内（即指向外部）。

支持两种链接：
  - Markdown 链接：[text](path) 或 [text](path#anchor)
  - WikiLink：     [[target]] 或 [[target|alias]] 或 [[target#anchor]]

会跳过文档头部的 YAML frontmatter（--- ... --- 之间的内容）。
也会跳过 ``` 代码块和行内代码 `...` 内的内容，避免误报。

用法：
  python ToolsScript/check_broken_links.py
  python ToolsScript/check_broken_links.py --json out.json
  python ToolsScript/check_broken_links.py --root Docs/30-tutorials/animation   # 限定子目录
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

# ========== 配置 ==========
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "Docs"
DEFAULT_SCAN_DIR = DOCS_DIR / "30-tutorials"

# 排除的链接协议/前缀（外部链接，不检查存在性）
EXTERNAL_PREFIXES = (
    "http://", "https://", "ftp://", "ftps://",
    "mailto:", "tel:", "javascript:", "data:", "file://",
)

# 视为"存在即可"的非 md 资源后缀（仍要求文件存在，但不要求在 30-tutorials 内）
ASSET_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico",
    ".pdf", ".zip", ".mp4", ".webm", ".mp3", ".wav",
    ".yaml", ".yml", ".json", ".txt", ".csv",
    ".cpp", ".h", ".hpp", ".c", ".cs", ".py", ".ini", ".uasset",
}

# ========== 数据结构 ==========

@dataclass
class BrokenLink:
    file: str          # 出现该链接的文件（相对项目根的 posix 路径）
    line: int          # 行号（1-based）
    kind: str          # "markdown" | "wikilink"
    raw: str           # 原始链接片段
    target: str        # 解析后的目标（去掉锚点）
    reason: str        # "missing" | "outside-scope"
    resolved: str | None = None  # 若文件存在，给出解析到的实际路径


# ========== Frontmatter 跳过 ==========

FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

def strip_frontmatter(text: str) -> tuple[str, int]:
    """剥离 YAML frontmatter，返回 (剩余正文, 起始行偏移)。
    若无 frontmatter 返回 (text, 0)。
    起始行偏移用于把正文行号映射回原文件行号。
    """
    if not text.startswith("---"):
        return text, 0
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text, 0
    fm_text = m.group(0)
    line_offset = fm_text.count("\n")
    return text[m.end():], line_offset


# ========== 代码块/行内代码屏蔽 ==========

FENCE_RE = re.compile(r"^(```|~~~)")

def mask_code(text: str) -> str:
    """把围栏代码块和行内代码替换为等长空格，避免误匹配链接。
    保留换行，确保行号不变。
    """
    out_lines: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in text.split("\n"):
        m = FENCE_RE.match(line)
        if m:
            if not in_fence:
                in_fence = True
                fence_marker = m.group(1)
                out_lines.append(" " * len(line))
                continue
            else:
                if line.lstrip().startswith(fence_marker):
                    in_fence = False
                    fence_marker = ""
                    out_lines.append(" " * len(line))
                    continue
        if in_fence:
            out_lines.append(" " * len(line))
        else:
            # 屏蔽行内代码 `...`
            line = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), line)
            out_lines.append(line)
    return "\n".join(out_lines)


# ========== 链接提取 ==========

# Markdown 链接：[text](url)，url 不含空格、不含未转义反引号
# 排除图片  ![](...) 也一并处理（图片资源也需要存在）
MD_LINK_RE = re.compile(
    r"!?\[(?P<text>(?:\\.|[^\[\]\n])*)\]\((?P<url><[^>]+>|[^)\s]+(?:\s+\"[^\"]*\")?)\)"
)

# WikiLink：[[target]] 或 [[target|alias]]
WIKI_LINK_RE = re.compile(r"\[\[(?P<target>[^\]\|\n]+?)(?:\|[^\]\n]+)?\]\]")


def iter_md_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.md"):
        # 跳过 .bak 等已忽略类型（rglob *.md 已经过滤）
        yield p


# ========== 解析与判定 ==========

def clean_url(url: str) -> str:
    """去掉 <...> 包裹和尾部 'title' 描述。"""
    url = url.strip()
    if url.startswith("<") and url.endswith(">"):
        url = url[1:-1]
    # 去掉  "title"
    if " " in url:
        url = url.split(" ", 1)[0]
    return url


def split_anchor(url: str) -> tuple[str, str]:
    """拆分 path 与 #anchor / ?query。"""
    path = url
    anchor = ""
    if "#" in path:
        path, anchor = path.split("#", 1)
    if "?" in path:
        path = path.split("?", 1)[0]
    return path, anchor


def is_external(url: str) -> bool:
    low = url.lower()
    return any(low.startswith(p) for p in EXTERNAL_PREFIXES)


def resolve_md_target(src_file: Path, target: str) -> Path | None:
    """以源文件为基准，解析相对/绝对路径。返回归一化后的绝对 Path（不保证存在）。"""
    if not target:
        return None
    # 绝对路径（以 / 开头）：相对项目根
    if target.startswith("/"):
        return (PROJECT_ROOT / target.lstrip("/")).resolve()
    return (src_file.parent / target).resolve()


def resolve_wiki_target(src_file: Path, target: str) -> list[Path]:
    """WikiLink 的 target 解析。常见形式：
       - 30-tutorials/animation/02-xxx        (相对 Docs/ 的路径，无后缀)
       - 02-xxx                                (同目录文件名，无后缀)
       - some/page                             (相对 Docs/ 的路径)
       返回候选实际文件路径列表（按优先级）。
    """
    candidates: list[Path] = []
    t = target.strip()
    if not t:
        return candidates

    # 显式带后缀
    has_ext = bool(Path(t).suffix)

    def add(p: Path):
        candidates.append(p)
        if not has_ext:
            candidates.append(p.with_suffix(".md"))

    # 1) 视为相对 Docs/ 根
    add((DOCS_DIR / t).resolve())
    # 2) 视为相对源文件目录
    add((src_file.parent / t).resolve())
    # 3) 视为相对项目根
    add((PROJECT_ROOT / t).resolve())

    # 去重保持顺序
    seen = set()
    uniq: list[Path] = []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


# ========== 主扫描 ==========

def scan_file(md_path: Path, scope_root: Path) -> list[BrokenLink]:
    text = md_path.read_text(encoding="utf-8", errors="replace")
    body, line_offset = strip_frontmatter(text)
    masked = mask_code(body)

    broken: list[BrokenLink] = []

    # 行号查找：用 masked 文本累计 \n
    # 我们直接基于位置 -> 行号
    line_starts = [0]
    for i, ch in enumerate(masked):
        if ch == "\n":
            line_starts.append(i + 1)

    def pos_to_line(pos: int) -> int:
        # 二分查找
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        # 行号（在 body 内为 lo+1），加上 frontmatter 偏移
        return lo + 1 + line_offset

    # ---- Markdown 链接 ----
    for m in MD_LINK_RE.finditer(masked):
        raw = m.group(0)
        url = clean_url(m.group("url"))
        if not url:
            continue
        if is_external(url):
            continue
        # 纯锚点 #xxx 跳过（页内跳转）
        if url.startswith("#"):
            continue

        path_part, _anchor = split_anchor(url)
        if not path_part:
            continue

        target_abs = resolve_md_target(md_path, path_part)
        line_no = pos_to_line(m.start())

        if target_abs is None or not target_abs.exists():
            broken.append(BrokenLink(
                file=md_path.relative_to(PROJECT_ROOT).as_posix(),
                line=line_no,
                kind="markdown",
                raw=raw,
                target=path_part,
                reason="missing",
            ))
            continue

        # 资源类（图片等）：只要存在即可，不限制范围
        if target_abs.suffix.lower() in ASSET_EXTS:
            continue

        if not is_within(target_abs, scope_root):
            broken.append(BrokenLink(
                file=md_path.relative_to(PROJECT_ROOT).as_posix(),
                line=line_no,
                kind="markdown",
                raw=raw,
                target=path_part,
                reason="outside-scope",
                resolved=target_abs.relative_to(PROJECT_ROOT).as_posix()
                if is_within(target_abs, PROJECT_ROOT) else str(target_abs),
            ))

    # ---- WikiLink ----
    for m in WIKI_LINK_RE.finditer(masked):
        raw = m.group(0)
        target = m.group("target").strip()
        if not target:
            continue
        path_part, _anchor = split_anchor(target)
        if not path_part:
            continue

        candidates = resolve_wiki_target(md_path, path_part)
        hit = next((p for p in candidates if p.exists() and p.is_file()), None)

        line_no = pos_to_line(m.start())

        if hit is None:
            broken.append(BrokenLink(
                file=md_path.relative_to(PROJECT_ROOT).as_posix(),
                line=line_no,
                kind="wikilink",
                raw=raw,
                target=path_part,
                reason="missing",
            ))
            continue

        if hit.suffix.lower() in ASSET_EXTS:
            continue

        if not is_within(hit, scope_root):
            broken.append(BrokenLink(
                file=md_path.relative_to(PROJECT_ROOT).as_posix(),
                line=line_no,
                kind="wikilink",
                raw=raw,
                target=path_part,
                reason="outside-scope",
                resolved=hit.relative_to(PROJECT_ROOT).as_posix()
                if is_within(hit, PROJECT_ROOT) else str(hit),
            ))

    return broken


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=str, default=str(DEFAULT_SCAN_DIR),
                        help="扫描根目录，默认 Docs/30-tutorials")
    parser.add_argument("--scope", type=str, default=None,
                        help="链接合法范围根目录，默认与 --root 相同（即链接必须在该目录内）")
    parser.add_argument("--json", type=str, default=None, help="将结果写入 JSON 文件")
    parser.add_argument("--only", choices=["missing", "outside-scope"], default=None,
                        help="只输出指定类型")
    args = parser.parse_args(argv)

    scan_root = Path(args.root).resolve()
    scope_root = Path(args.scope).resolve() if args.scope else scan_root

    if not scan_root.exists():
        print(f"[ERROR] 扫描目录不存在: {scan_root}", file=sys.stderr)
        return 2

    files = list(iter_md_files(scan_root))
    print(f"扫描根: {scan_root}")
    print(f"合法范围: {scope_root}")
    print(f"待扫描 Markdown 文件: {len(files)}")
    print("-" * 60)

    all_broken: list[BrokenLink] = []
    for f in files:
        try:
            issues = scan_file(f, scope_root)
        except Exception as e:
            print(f"[WARN] 解析失败 {f}: {e}", file=sys.stderr)
            continue
        if args.only:
            issues = [b for b in issues if b.reason == args.only]
        all_broken.extend(issues)

    # ---- 输出 ----
    missing = [b for b in all_broken if b.reason == "missing"]
    outside = [b for b in all_broken if b.reason == "outside-scope"]

    def print_group(title: str, items: list[BrokenLink]):
        print(f"\n=== {title} ({len(items)}) ===")
        if not items:
            print("  (无)")
            return
        # 按文件聚合
        by_file: dict[str, list[BrokenLink]] = {}
        for b in items:
            by_file.setdefault(b.file, []).append(b)
        for fp in sorted(by_file):
            print(f"\n  {fp}")
            for b in sorted(by_file[fp], key=lambda x: x.line):
                tag = "MD " if b.kind == "markdown" else "WIK"
                extra = f"  -> {b.resolved}" if b.resolved else ""
                print(f"    L{b.line:<4} [{tag}] {b.target}{extra}")
                # 显示原始链接（截断）
                raw = b.raw.replace("\n", " ")
                if len(raw) > 100:
                    raw = raw[:97] + "..."
                print(f"           raw: {raw}")

    if args.only != "outside-scope":
        print_group("不存在的链接 (missing)", missing)
    if args.only != "missing":
        print_group("超出范围的链接 (outside-scope)", outside)

    print("\n" + "=" * 60)
    print(f"汇总: 共 {len(all_broken)} 处问题  "
          f"(missing={len(missing)}, outside-scope={len(outside)})")

    if args.json:
        out = Path(args.json)
        out.write_text(
            json.dumps([asdict(b) for b in all_broken], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"已写入: {out}")

    return 0 if not all_broken else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
