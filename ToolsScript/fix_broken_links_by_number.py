"""
根据"编号前缀（NN-）"修复 Docs/30-tutorials/ 下因文件改名导致失效的 Markdown 链接。

背景：
  原英文文件名（如 02-engine-foundation.md）被改名为中文文件名（如
  02-UE5动画系统引擎基础框架深度分析.md），导致旧链接全部失效。
  目录内所有教程文件都遵循 NN-xxx.md 命名约定，因此可以按编号前缀映射。

修复策略：
  1. 逐文件扫描 Markdown 链接和 WikiLink；
  2. 仅处理"目标不存在"的链接；
  3. 解析目标的 basename 起始两位数字编号 NN，在源文件所在目录里查找
     唯一匹配 ^NN- 开头的现存 .md 文件；
  4. 若找到唯一匹配 -> 替换；
  5. 若找不到或匹配不唯一 -> 打印出来人工处理。

运行方式：
  python ToolsScript/fix_broken_links_by_number.py             # dry-run，仅报告
  python ToolsScript/fix_broken_links_by_number.py --apply     # 实际写回文件
  python ToolsScript/fix_broken_links_by_number.py --apply --backup  # 写回前备份 .bak

只处理满足以下条件的链接：
  - 链接目标 basename 形如 ^\d{2}- 开头；
  - Markdown 链接 [text](path) 或 WikiLink [[target]] / [[target|alias]]；
  - frontmatter 不在替换范围内（链接也不会出现在 frontmatter 的 url 形式）；
  - 代码块/行内代码会被跳过。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# ========== 配置 ==========
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "Docs"
DEFAULT_SCAN_DIR = DOCS_DIR / "30-tutorials"

# 目标 basename 必须满足此正则才进行编号匹配
NUM_PREFIX_RE = re.compile(r"^(\d{2})-")

# Markdown 链接（与 check_broken_links.py 一致）
MD_LINK_RE = re.compile(
    r"(?P<bang>!?)\[(?P<text>(?:\\.|[^\[\]\n])*)\]\((?P<url><[^>]+>|[^)\s]+(?:\s+\"[^\"]*\")?)\)"
)
# WikiLink
WIKI_LINK_RE = re.compile(r"\[\[(?P<target>[^\]\|\n]+?)(?P<alias>\|[^\]\n]+)?\]\]")

# 跳过 frontmatter
FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

# 围栏代码块
FENCE_RE = re.compile(r"^(```|~~~)")


# ========== 数据结构 ==========

@dataclass
class Replacement:
    file: Path
    line: int
    kind: str          # "markdown" | "wikilink"
    old_raw: str
    new_raw: str
    old_target: str
    new_target: str    # 文件名（不含路径）


@dataclass
class Unresolved:
    file: Path
    line: int
    kind: str
    raw: str
    target: str
    reason: str        # "no-number-prefix" | "no-match" | "ambiguous"
    detail: str = ""


# ========== 工具函数 ==========

def split_frontmatter(text: str) -> tuple[str, str]:
    """返回 (frontmatter_block, body)。若无 frontmatter，frontmatter_block 为 ''。"""
    if not text.startswith("---"):
        return "", text
    m = FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    return m.group(0), text[m.end():]


def iter_md_files(root: Path) -> Iterable[Path]:
    return (p for p in root.rglob("*.md") if p.is_file())


def is_external(url: str) -> bool:
    low = url.lower()
    return any(low.startswith(p) for p in (
        "http://", "https://", "ftp://", "mailto:", "tel:",
        "javascript:", "data:", "file://",
    ))


def clean_md_url(url: str) -> tuple[str, str]:
    """返回 (path_part, suffix_after_path)。
    suffix_after_path 包含 #anchor 和 \" title \" 等，方便重建。
    """
    raw = url.strip()
    # <...> 包裹
    angle = raw.startswith("<") and raw.endswith(">")
    inner = raw[1:-1] if angle else raw

    # 切出 title 部分（按第一个未转义空格切开）
    path_part = inner
    title_part = ""
    sp_idx = inner.find(" ")
    if sp_idx != -1:
        path_part = inner[:sp_idx]
        title_part = inner[sp_idx:]

    # 切出 anchor / query
    anchor_part = ""
    if "#" in path_part:
        i = path_part.find("#")
        anchor_part = path_part[i:]
        path_part = path_part[:i]
    elif "?" in path_part:
        i = path_part.find("?")
        anchor_part = path_part[i:]
        path_part = path_part[:i]

    suffix = anchor_part + title_part
    return path_part, suffix


def maybe_rewrite_link_text(old_text: str, old_path: str, new_basename: str) -> str | None:
    """若链接显示文本看起来就是"文件名占位"（无意义的 slug），返回替换后的新文本；
    否则返回 None（保留原文本，可能是用户写的有意义标题）。

    判定（满足任一即视为占位文本）：
      A) 等于旧路径/旧 basename（含/不含 .md，含/不含 ./ 前缀）；
      B) 文本是"纯英文 slug"形态（仅包含 ASCII 字母数字、_/-/./空格），
         且匹配 ^\\d{2}-[A-Za-z0-9._-]*$ 这种典型旧文件名风格（如
         "02-engine-foundation"、"02-engine-foundation.md"、
         "02-EngineFoundation.md"）。

    替换为 new_basename 去 .md 形式（更自然的展示标题）。
    返回 None 表示不改动。
    """
    stripped = old_text.strip()
    if not stripped:
        return None

    new_base_noext = new_basename[:-3] if new_basename.endswith(".md") else new_basename

    # 已经等于新 stem 或新 basename 则不需要再换
    if stripped == new_base_noext or stripped == new_basename:
        return None

    # A) 旧路径占位
    old_base = Path(old_path).name
    old_base_noext = old_base[:-3] if old_base.endswith(".md") else old_base
    old_path_noext = old_path[:-3] if old_path.endswith(".md") else old_path
    placeholder_set = {
        old_base, old_base_noext,
        old_path, old_path_noext,
        "./" + old_base, "./" + old_base_noext,
    }
    if stripped in placeholder_set:
        return new_base_noext

    # B) 典型旧文件名 slug 形态：以两位数字编号开头，仅含 ASCII 字母数字 . _ -
    if re.match(r"^\d{2}-[A-Za-z0-9._-]*$", stripped):
        return new_base_noext

    return None


def find_by_number(src_dir: Path, basename: str) -> tuple[list[Path], str | None]:
    """根据 basename 中的两位编号在 src_dir 找候选文件。
    返回 (候选列表, 编号或 None)。
    """
    m = NUM_PREFIX_RE.match(basename)
    if not m:
        return [], None
    num = m.group(1)
    pattern = re.compile(rf"^{num}-")
    candidates = sorted(
        p for p in src_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".md" and pattern.match(p.name)
    )
    return candidates, num


# ========== 代码块掩码（仅用于"扫描定位"，替换时仍作用于原文） ==========

def build_skip_mask(text: str) -> list[bool]:
    """返回与 text 等长的列表，True 表示该字符位于代码块/行内代码内（应跳过）。"""
    mask = [False] * len(text)
    in_fence = False
    fence_marker = ""
    i = 0
    # 按行处理围栏
    line_starts = [0]
    for k, ch in enumerate(text):
        if ch == "\n":
            line_starts.append(k + 1)
    line_starts.append(len(text) + 1)

    for li in range(len(line_starts) - 1):
        s, e = line_starts[li], line_starts[li + 1] - 1  # e 为换行位置或末尾
        line = text[s:e]
        m = FENCE_RE.match(line)
        if m:
            if not in_fence:
                in_fence = True
                fence_marker = m.group(1)
                for j in range(s, min(e + 1, len(text))):
                    mask[j] = True
                continue
            else:
                if line.lstrip().startswith(fence_marker):
                    in_fence = False
                    fence_marker = ""
                    for j in range(s, min(e + 1, len(text))):
                        mask[j] = True
                    continue
        if in_fence:
            for j in range(s, min(e + 1, len(text))):
                mask[j] = True

    # 行内代码 `...`（仅在非围栏区域）
    for m in re.finditer(r"`[^`\n]*`", text):
        s, e = m.start(), m.end()
        if mask[s]:  # 已在围栏块中
            continue
        for j in range(s, e):
            mask[j] = True

    return mask


# ========== 核心处理 ==========

def process_file(md_path: Path, repls: list[Replacement], unresolved: list[Unresolved]) -> str | None:
    """扫描单个 md 文件并返回新内容（若无修改返回 None）。"""
    text = md_path.read_text(encoding="utf-8", errors="replace")
    fm, body = split_frontmatter(text)
    fm_line_offset = fm.count("\n")
    mask = build_skip_mask(body)

    # 行号映射
    line_starts = [0]
    for i, ch in enumerate(body):
        if ch == "\n":
            line_starts.append(i + 1)

    def pos_to_line(pos: int) -> int:
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1 + fm_line_offset

    # 收集本文件内的替换（按位置降序应用，避免位置漂移）
    edits: list[tuple[int, int, str]] = []  # (start, end, new_text)
    src_dir = md_path.parent

    # ----- Markdown 链接 -----
    for m in MD_LINK_RE.finditer(body):
        if mask[m.start()]:
            continue
        url_raw = m.group("url")

        # 特殊：畸形语法 [文字]([[wiki-target]])
        # 应改写为正确 wikilink: [[wiki-target|文字]]
        url_stripped = url_raw.strip()
        if url_stripped.startswith("[[") and url_stripped.endswith("]]"):
            text_alias = m.group("text").strip()
            inner = url_stripped[2:-2].strip()
            # 切 anchor
            inner_path = inner
            anchor = ""
            if "#" in inner_path:
                i = inner_path.find("#")
                anchor = inner_path[i:]
                inner_path = inner_path[:i]

            # 检查是否能解析（与 WikiLink 同逻辑）
            has_ext_inner = bool(Path(inner_path).suffix)
            cand_exists = []
            for base in (DOCS_DIR, src_dir, PROJECT_ROOT):
                p = (base / inner_path).resolve()
                cand_exists.append(p)
                if not has_ext_inner:
                    cand_exists.append(p.with_suffix(".md"))
            line_no = pos_to_line(m.start())

            if any(p.exists() and p.is_file() for p in cand_exists):
                # 目标存在，仅修正语法
                new_target_str = inner_path  # 保持原写法
                new_raw = f"[[{new_target_str}{anchor}|{text_alias}]]" if text_alias else f"[[{new_target_str}{anchor}]]"
                edits.append((m.start(), m.end(), new_raw))
                repls.append(Replacement(
                    file=md_path, line=line_no, kind="wikilink",
                    old_raw=m.group(0), new_raw=new_raw,
                    old_target=inner_path, new_target=Path(inner_path).name,
                ))
                continue

            # 不存在：按编号匹配修复
            basename_inner = Path(inner_path).name
            target_parent_rel_inner = Path(inner_path).parent
            same_dir_inner = (
                str(target_parent_rel_inner) in ("", ".")
                or target_parent_rel_inner.name == src_dir.name
            )
            if not same_dir_inner:
                unresolved.append(Unresolved(
                    file=md_path, line=line_no, kind="wikilink",
                    raw=m.group(0), target=inner_path,
                    reason="no-match",
                    detail="畸形语法 [文字]([[wiki]]) 且目标目录不在源目录内",
                ))
                continue
            cand_files, num_inner = find_by_number(src_dir, basename_inner)
            if num_inner is None:
                unresolved.append(Unresolved(
                    file=md_path, line=line_no, kind="wikilink",
                    raw=m.group(0), target=inner_path,
                    reason="no-number-prefix",
                    detail="畸形语法 [文字]([[wiki]])",
                ))
                continue
            if not cand_files:
                unresolved.append(Unresolved(
                    file=md_path, line=line_no, kind="wikilink",
                    raw=m.group(0), target=inner_path,
                    reason="no-match",
                    detail=f"畸形语法 [文字]([[wiki]])，目录中找不到 {num_inner}- 开头的 .md 文件",
                ))
                continue
            if len(cand_files) > 1:
                unresolved.append(Unresolved(
                    file=md_path, line=line_no, kind="wikilink",
                    raw=m.group(0), target=inner_path,
                    reason="ambiguous",
                    detail=f"畸形语法 [文字]([[wiki]])，匹配到多个: {[c.name for c in cand_files]}",
                ))
                continue

            new_file = cand_files[0]
            # 写回 wiki target：保持原相对形式（含路径段则保 Docs/ 相对）
            if "/" in inner_path:
                try:
                    rel = new_file.relative_to(DOCS_DIR).as_posix()
                except ValueError:
                    rel = new_file.name
                new_target_str = rel if has_ext_inner else rel[:-3]
            else:
                new_target_str = new_file.name if has_ext_inner else new_file.stem

            new_raw = (
                f"[[{new_target_str}{anchor}|{text_alias}]]"
                if text_alias else f"[[{new_target_str}{anchor}]]"
            )
            edits.append((m.start(), m.end(), new_raw))
            repls.append(Replacement(
                file=md_path, line=line_no, kind="wikilink",
                old_raw=m.group(0), new_raw=new_raw,
                old_target=inner_path, new_target=new_file.name,
            ))
            continue

        path_part, suffix = clean_md_url(url_raw)
        if not path_part:
            continue
        if is_external(path_part):
            continue
        if path_part.startswith("#"):
            continue

        # 解析目标绝对路径，先看是否存在
        if path_part.startswith("/"):
            target_abs = (PROJECT_ROOT / path_part.lstrip("/")).resolve()
        else:
            target_abs = (src_dir / path_part).resolve()
        if target_abs.exists():
            # 链接有效。但文本可能仍是旧英文文件名占位 -> 尝试同步文本
            if target_abs.is_file() and target_abs.suffix.lower() == ".md":
                old_text = m.group("text")
                # 这里"旧路径名"取的是 path_part 自身做占位判断，
                # 替换为目标文件的真实 basename。
                new_text_replacement = maybe_rewrite_link_text(
                    old_text, path_part, target_abs.name
                )
                if new_text_replacement is not None and new_text_replacement != old_text.strip():
                    text_start = m.start("text")
                    text_end = m.end("text")
                    new_full = (
                        body[m.start():text_start]
                        + new_text_replacement
                        + body[text_end:m.end()]
                    )
                    line_no = pos_to_line(m.start())
                    edits.append((m.start(), m.end(), new_full))
                    repls.append(Replacement(
                        file=md_path, line=line_no, kind="markdown",
                        old_raw=m.group(0), new_raw=new_full,
                        old_target=f"text={old_text.strip()!r}",
                        new_target=f"text={new_text_replacement!r}",
                    ))
            continue  # 链接有效，无需修复 url

        # basename 编号匹配
        basename = Path(path_part).name
        # 判定"目标目录是否就是源目录"：
        #   1) ./xx.md 或 xx.md 直接同目录；
        #   2) path_part 里含 "/"，但其末级目录段恰好等于源目录目录名
        #      （常见错误写法：相对项目根写成 "30-tutorials/<dir>/xx.md"
        #       却出现在 <dir>/ 内的文件中），此时仍按 basename 编号修复。
        target_parent_rel = Path(path_part).parent  # 基于字符串的目录段
        same_dir = False
        if target_parent_rel == Path(".") or str(target_parent_rel) in ("", "."):
            same_dir = True
        elif target_parent_rel.name == src_dir.name:
            same_dir = True

        if not same_dir:
            target_parent_abs = (src_dir / path_part).parent.resolve()
            unresolved.append(Unresolved(
                file=md_path, line=pos_to_line(m.start()), kind="markdown",
                raw=m.group(0), target=path_part,
                reason="no-match",
                detail=f"目标父目录不在源文件目录内（{target_parent_abs}），不按编号修复",
            ))
            continue

        candidates, num = find_by_number(src_dir, basename)
        line_no = pos_to_line(m.start())

        if num is None:
            unresolved.append(Unresolved(
                file=md_path, line=line_no, kind="markdown",
                raw=m.group(0), target=path_part,
                reason="no-number-prefix",
            ))
            continue
        if not candidates:
            unresolved.append(Unresolved(
                file=md_path, line=line_no, kind="markdown",
                raw=m.group(0), target=path_part,
                reason="no-match",
                detail=f"目录中找不到 {num}- 开头的 .md 文件",
            ))
            continue
        if len(candidates) > 1:
            unresolved.append(Unresolved(
                file=md_path, line=line_no, kind="markdown",
                raw=m.group(0), target=path_part,
                reason="ambiguous",
                detail=f"匹配到多个: {[c.name for c in candidates]}",
            ))
            continue

        new_name = candidates[0].name
        # 重建 url：
        #   - 若链接原本就是同目录形式（无 "/" 或仅 "./"），保留前缀，仅替换文件名；
        #   - 若链接是 "x/y/<dir>/xx.md" 这种错误的相对路径但末级目录==源目录，
        #     此时改写为同目录引用（仅 basename），结果链接才能正确工作。
        if "/" in path_part and target_parent_rel.name == src_dir.name and target_parent_rel != Path("."):
            new_path = new_name
        else:
            prefix_dir = path_part[: len(path_part) - len(basename)]
            new_path = prefix_dir + new_name
        new_url = new_path + suffix
        # 还原原始包裹
        if url_raw.strip().startswith("<"):
            new_url_str = f"<{new_url}>"
        else:
            new_url_str = new_url

        # 同步替换链接文本（仅当文本看起来就是旧文件名占位时）
        old_text = m.group("text")
        new_text_replacement = maybe_rewrite_link_text(old_text, path_part, new_name)
        text_start = m.start("text")
        text_end = m.end("text")
        url_start = m.start("url")
        url_end = m.end("url")

        if new_text_replacement is not None:
            new_full = (
                body[m.start():text_start]
                + new_text_replacement
                + body[text_end:url_start]
                + new_url_str
                + body[url_end:m.end()]
            )
        else:
            new_full = body[m.start():url_start] + new_url_str + body[url_end:m.end()]

        edits.append((m.start(), m.end(), new_full))
        repls.append(Replacement(
            file=md_path, line=line_no, kind="markdown",
            old_raw=m.group(0), new_raw=new_full,
            old_target=path_part, new_target=new_name,
        ))

    # ----- WikiLink -----
    for m in WIKI_LINK_RE.finditer(body):
        if mask[m.start()]:
            continue
        target = m.group("target").strip()
        alias = m.group("alias") or ""
        if not target:
            continue

        # 切 anchor
        target_path = target
        anchor = ""
        if "#" in target_path:
            i = target_path.find("#")
            anchor = target_path[i:]
            target_path = target_path[:i]
        if not target_path:
            continue

        # 检查是否已经能解析（与 check_broken_links 一致的优先序）
        has_ext = bool(Path(target_path).suffix)
        cand_exists = []
        for base in (DOCS_DIR, src_dir, PROJECT_ROOT):
            p = (base / target_path).resolve()
            cand_exists.append(p)
            if not has_ext:
                cand_exists.append(p.with_suffix(".md"))
        if any(p.exists() and p.is_file() for p in cand_exists):
            continue  # 已经能解析

        # 取 basename 编号匹配（仅当 target_path 看起来是同目录引用时）
        basename = Path(target_path).name
        # 我们要求 target_path 对应到 src_dir，否则不处理
        # 判定方法：若 target_path 不含 "/" 视为同目录；若含 "/" 但解析后的父目录==src_dir 也算
        target_parent_candidates = [
            (DOCS_DIR / target_path).resolve().parent,
            (src_dir / target_path).resolve().parent,
        ]
        if src_dir not in target_parent_candidates and "/" in target_path:
            unresolved.append(Unresolved(
                file=md_path, line=pos_to_line(m.start()), kind="wikilink",
                raw=m.group(0), target=target_path,
                reason="no-match",
                detail="目标目录不在源文件目录内，不按编号修复",
            ))
            continue

        candidates, num = find_by_number(src_dir, basename)
        line_no = pos_to_line(m.start())

        if num is None:
            unresolved.append(Unresolved(
                file=md_path, line=line_no, kind="wikilink",
                raw=m.group(0), target=target_path,
                reason="no-number-prefix",
            ))
            continue
        if not candidates:
            unresolved.append(Unresolved(
                file=md_path, line=line_no, kind="wikilink",
                raw=m.group(0), target=target_path,
                reason="no-match",
                detail=f"目录中找不到 {num}- 开头的 .md 文件",
            ))
            continue
        if len(candidates) > 1:
            unresolved.append(Unresolved(
                file=md_path, line=line_no, kind="wikilink",
                raw=m.group(0), target=target_path,
                reason="ambiguous",
                detail=f"匹配到多个: {[c.name for c in candidates]}",
            ))
            continue

        new_file = candidates[0]
        # 决定写回的 wiki target 形式：
        #   - 若原 target 含路径分隔符 "/"，保持相对 Docs/ 的全路径（更稳）；
        #   - 否则保持纯文件名（同目录引用）。
        # 去掉 .md 后缀以贴近 Wiki 习惯（除非原始 target 显式带 .md）
        keep_ext = has_ext
        if "/" in target_path:
            try:
                rel = new_file.relative_to(DOCS_DIR).as_posix()
            except ValueError:
                rel = new_file.name
            new_target = rel if keep_ext else rel[:-3]  # 去掉 .md
        else:
            new_target = new_file.name if keep_ext else new_file.stem

        new_raw = f"[[{new_target}{anchor}{alias}]]"
        edits.append((m.start(), m.end(), new_raw))
        repls.append(Replacement(
            file=md_path, line=line_no, kind="wikilink",
            old_raw=m.group(0), new_raw=new_raw,
            old_target=target_path, new_target=new_file.name,
        ))

    if not edits:
        return None

    # 按位置降序应用编辑
    edits.sort(key=lambda x: x[0], reverse=True)
    new_body = body
    for s, e, new_text in edits:
        new_body = new_body[:s] + new_text + new_body[e:]
    return fm + new_body


# ========== 主入口 ==========

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=str, default=str(DEFAULT_SCAN_DIR),
                        help="扫描根目录，默认 Docs/30-tutorials")
    parser.add_argument("--apply", action="store_true", help="实际写回文件（默认 dry-run）")
    parser.add_argument("--backup", action="store_true", help="写回前生成 .bak 备份（仅 --apply 生效）")
    args = parser.parse_args(argv)

    scan_root = Path(args.root).resolve()
    if not scan_root.exists():
        print(f"[ERROR] 目录不存在: {scan_root}", file=sys.stderr)
        return 2

    files = list(iter_md_files(scan_root))
    print(f"扫描根: {scan_root}")
    print(f"待扫描 Markdown 文件: {len(files)}")
    print(f"模式: {'APPLY (会写回)' if args.apply else 'DRY-RUN (仅打印)'}")
    print("-" * 60)

    all_repls: list[Replacement] = []
    all_unresolved: list[Unresolved] = []
    modified_files = 0

    for f in files:
        try:
            new_content = process_file(f, all_repls, all_unresolved)
        except Exception as e:
            print(f"[WARN] 处理失败 {f}: {e}", file=sys.stderr)
            continue
        if new_content is None:
            continue
        modified_files += 1
        if args.apply:
            if args.backup:
                bak = f.with_suffix(f.suffix + ".bak")
                bak.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            f.write_text(new_content, encoding="utf-8")

    # ---- 报告 ----
    print(f"\n=== 可自动替换的链接 ({len(all_repls)}) ===")
    if all_repls:
        by_file: dict[Path, list[Replacement]] = {}
        for r in all_repls:
            by_file.setdefault(r.file, []).append(r)
        for fp in sorted(by_file, key=lambda p: p.as_posix()):
            rel = fp.relative_to(PROJECT_ROOT).as_posix()
            print(f"\n  {rel}")
            for r in sorted(by_file[fp], key=lambda x: x.line):
                tag = "MD " if r.kind == "markdown" else "WIK"
                print(f"    L{r.line:<4} [{tag}] {r.old_target}  =>  {r.new_target}")
    else:
        print("  (无)")

    print(f"\n=== 无法自动替换 / 需人工处理 ({len(all_unresolved)}) ===")
    if all_unresolved:
        by_file2: dict[Path, list[Unresolved]] = {}
        for u in all_unresolved:
            by_file2.setdefault(u.file, []).append(u)
        for fp in sorted(by_file2, key=lambda p: p.as_posix()):
            rel = fp.relative_to(PROJECT_ROOT).as_posix()
            print(f"\n  {rel}")
            for u in sorted(by_file2[fp], key=lambda x: x.line):
                tag = "MD " if u.kind == "markdown" else "WIK"
                line = f"    L{u.line:<4} [{tag}] {u.target}  ({u.reason})"
                if u.detail:
                    line += f"  -- {u.detail}"
                print(line)
                raw = u.raw.replace("\n", " ")
                if len(raw) > 100:
                    raw = raw[:97] + "..."
                print(f"           raw: {raw}")
    else:
        print("  (无)")

    print("\n" + "=" * 60)
    print(
        f"汇总: 可替换 {len(all_repls)} 处, "
        f"待人工 {len(all_unresolved)} 处, "
        f"涉及文件 {modified_files} 个"
    )
    if not args.apply:
        print("提示: 当前为 dry-run，确认无误后加 --apply 写回（可加 --backup）")
    else:
        print(f"已写回 {modified_files} 个文件" + ("（已生成 .bak 备份）" if args.backup else ""))

    return 0 if not all_unresolved and not all_repls else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
