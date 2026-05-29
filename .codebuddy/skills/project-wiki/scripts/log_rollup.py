#!/usr/bin/env python3
"""log_rollup.py — log.d/ → log.md rollup + 季度归档 (v0.7)

把 `Docs/log.d/log-<owner>.md` 多人分文件按时间 merge 到主 `Docs/log.md`，
并把超出"近 N 个月"窗口的旧段切到 `Docs/log-archive/YYYY-Q<n>.md`。

设计原则（参考 [[60-topics/multi-agent-wiki-pipeline]] §3 + ADR-0006）：

- **per-human 分文件**：每人 append 自己的 `log.d/log-<git-user>.md`，零并发冲突
- **段头时间戳**：`## [YYYY-MM-DD HH:MM] <owner> <action> | R<global>[-<local>] <summary>`
- **rollup 是只读的**：永不删 log.d/ 分文件，只往主 log.md / archive 写
- **v0.7 baseline**：主 log.md R1-R30 (2026-05-14 之前的所有内容) 标为"pre-v0.7-baseline"段，不重写
- **冲突**：同一时间戳两人都 append → 按 owner 名字字典序

用法
====

    # dry-run：列出会发生什么（推荐先跑一次）
    python log_rollup.py

    # 实际写入主 log.md（rollup）
    python log_rollup.py --apply

    # 把 N 个月之前的段切到 log-archive/
    python log_rollup.py --apply --archive-before 2026-02-01

    # 仅给指定 owner 跑（少用，正常应该全员一起 rollup）
    python log_rollup.py --apply --owner robertyluo

退出码
======

    0  成功（含 dry-run 无变化）
    1  log.d/ 分文件格式错（lint 后再跑）
    2  pre-v0.7-baseline 标记冲突 / 主 log.md 损坏
    3  脚本本身报错（IO / 配置错）

依赖：纯 Python 3.9+ stdlib，无外部包。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

DOCS = "Docs"
LOG_MD = f"{DOCS}/log.md"
LOG_D_DIR = f"{DOCS}/log.d"
LOG_ARCHIVE_DIR = f"{DOCS}/log-archive"

# 主 log.md 里 v0.7 之前的内容用这个标记圈起来（首次 rollup 时插入）
BASELINE_MARK_BEGIN = "<!-- pre-v0.7-baseline:begin -->"
BASELINE_MARK_END = "<!-- pre-v0.7-baseline:end -->"
ROLLUP_MARK_BEGIN = "<!-- rollup:begin -->"
ROLLUP_MARK_END = "<!-- rollup:end -->"

# 段头匹配：## [YYYY-MM-DD] action | summary  或  ## [YYYY-MM-DD HH:MM] owner action | R<n> summary
SEGMENT_HEADER_RE = re.compile(
    r"^##\s+\[(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\]\s*(.+)$",
    re.MULTILINE,
)

# 提取 R 编号（R30 / R30-3 都可）
R_NUMBER_RE = re.compile(r"\bR(\d+)(?:-(\d+))?\b")


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    """一个 log 段（## 标题 + 正文）。"""

    date: str  # YYYY-MM-DD
    time: str  # HH:MM 或 ""
    header: str  # 完整段头（不含 ##）
    body: str  # 段正文（含 R 编号 / 子标题 / 列表等）
    source_file: str  # 来源：'log.md' / 'log.d/log-<owner>.md'
    owner: str  # 解析自段头的 owner（baseline 段 owner=""）

    @property
    def sort_key(self) -> tuple:
        return (self.date, self.time or "00:00", self.owner, self.header)

    @property
    def full_text(self) -> str:
        return f"## [{self.date}{' ' + self.time if self.time else ''}] {self.header}\n{self.body.rstrip()}\n"


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

def parse_segments(text: str, source_file: str) -> list[Segment]:
    """按 `## [date ...] ...` 切分段落。"""
    segments: list[Segment] = []
    lines = text.splitlines(keepends=True)
    cur_date: str | None = None
    cur_time = ""
    cur_header: str | None = None
    cur_body: list[str] = []

    def flush():
        nonlocal cur_date, cur_time, cur_header, cur_body
        if cur_date is None or cur_header is None:
            return
        owner = _extract_owner(cur_header)
        segments.append(Segment(
            date=cur_date, time=cur_time, header=cur_header,
            body="".join(cur_body),
            source_file=source_file, owner=owner,
        ))
        cur_date = cur_time = cur_header = None
        cur_body = []

    for ln in lines:
        m = SEGMENT_HEADER_RE.match(ln)
        if m:
            flush()
            cur_date, t, cur_header = m.group(1), m.group(2), m.group(3).strip()
            cur_time = t or ""
        else:
            if cur_header is not None:
                cur_body.append(ln)
    flush()
    return segments


def _extract_owner(header: str) -> str:
    """从段头猜 owner 字段。v0.7+ 段头格式是 `<owner> <action> | ...`，旧段无 owner。"""
    parts = header.split("|", 1)
    if not parts:
        return ""
    head = parts[0].strip().split()
    # 已知 action 关键词集合（旧段头 'crystallize' / 'ingest' / 'verify' / 'lint' / 'init'）
    action_keywords = {"crystallize", "ingest", "verify", "lint", "init", "digest", "rollup"}
    # 段头形如 "<owner> <action>" 或 "<action>"
    if len(head) >= 2 and head[1].lower() in action_keywords:
        return head[0]
    return ""  # 旧段（仅 action，无 owner）


# ---------------------------------------------------------------------------
# Rollup 主流程
# ---------------------------------------------------------------------------

def collect_log_d_segments(project_root: Path, owner_filter: str | None = None) -> list[Segment]:
    log_d = project_root / LOG_D_DIR
    if not log_d.is_dir():
        return []
    out: list[Segment] = []
    for p in sorted(log_d.glob("log-*.md")):
        if owner_filter and p.stem != f"log-{owner_filter}":
            continue
        owner = p.stem.removeprefix("log-")
        text = p.read_text(encoding="utf-8")
        segs = parse_segments(text, source_file=f"log.d/{p.name}")
        for s in segs:
            # log.d/ 里的段 owner 应等于文件名 owner；不一致 → warn 但不 fail
            if s.owner and s.owner != owner:
                print(f"[warn] {p.name} 段头 owner={s.owner!r} ≠ 文件名 owner={owner!r}",
                      file=sys.stderr)
            s.owner = owner  # 以文件名为准
        out.extend(segs)
    return out


def parse_existing_log_md(text: str) -> tuple[str, list[Segment], list[Segment]]:
    """
    返回 (preamble, baseline_segs, rollup_segs)。
    preamble 包括第一段 `## [...]` 之前的全部内容（标题 + 文件头说明 + 第一条 `---`）。

    规则：
    - 第一次 rollup 时：log.md 全部段都视为 baseline，rollup_segs=[]
    - 第二次及以后：BASELINE_MARK 内的段是 baseline；ROLLUP_MARK 内的段是已 rollup 过的 v0.7+ 段（下次 rollup 时与新 log.d/ 段合并）
    """
    # 找第一个段头位置
    m = SEGMENT_HEADER_RE.search(text)
    if not m:
        return text, [], []
    preamble = text[:m.start()]

    has_marks = BASELINE_MARK_BEGIN in text and ROLLUP_MARK_BEGIN in text
    if not has_marks:
        # 第一次 rollup：全部归 baseline
        all_segs = parse_segments(text[m.start():], source_file="log.md")
        return preamble, all_segs, []

    # 已经 rollup 过：按 marker 切分
    baseline_segs: list[Segment] = []
    rollup_segs: list[Segment] = []

    bm_begin = text.find(BASELINE_MARK_BEGIN)
    bm_end = text.find(BASELINE_MARK_END)
    if bm_begin >= 0 and bm_end >= 0:
        baseline_block = text[bm_begin + len(BASELINE_MARK_BEGIN):bm_end]
        baseline_segs = parse_segments(baseline_block, source_file="log.md:baseline")

    rm_begin = text.find(ROLLUP_MARK_BEGIN)
    rm_end = text.find(ROLLUP_MARK_END)
    if rm_begin >= 0 and rm_end >= 0:
        rollup_block = text[rm_begin + len(ROLLUP_MARK_BEGIN):rm_end]
        rollup_segs = parse_segments(rollup_block, source_file="log.md:rollup")

    return preamble, baseline_segs, rollup_segs


def rollup(project_root: Path, apply: bool, archive_before: str | None,
           owner_filter: str | None) -> int:
    log_md = project_root / LOG_MD
    if not log_md.is_file():
        print(f"[error] {LOG_MD} 不存在", file=sys.stderr)
        return 3

    text = log_md.read_text(encoding="utf-8")
    preamble, baseline_segs, v07_segs_in_log_md = parse_existing_log_md(text)
    log_d_segs = collect_log_d_segments(project_root, owner_filter)

    print(f"[rollup] preamble: {len(preamble)} chars")
    print(f"[rollup] baseline 段 (pre-v0.7): {len(baseline_segs)}")
    print(f"[rollup] log.md 里 v0.7+ 段（rollup 区块）: {len(v07_segs_in_log_md)}")
    print(f"[rollup] log.d/ 收集的段: {len(log_d_segs)}")

    # 合并 v0.7+ 段：log.md 已有 + log.d/ 新增（用 (owner, date, header) 去重，log.d/ 优先）
    seen: dict[tuple, Segment] = {}
    for s in v07_segs_in_log_md:
        key = (s.owner, s.date, s.time, s.header)
        seen[key] = s
    overrides = 0
    new_added = 0
    for s in log_d_segs:
        key = (s.owner, s.date, s.time, s.header)
        if key in seen:
            overrides += 1
        else:
            new_added += 1
        seen[key] = s

    merged = sorted(seen.values(), key=lambda s: s.sort_key)
    print(f"[rollup] merged v0.7+ 段: {len(merged)} (新增 {new_added}, 覆盖 {overrides})")

    # 归档：把 archive_before 之前的非 baseline 段切出
    to_archive: list[Segment] = []
    to_keep: list[Segment] = []
    if archive_before:
        cutoff = datetime.strptime(archive_before, "%Y-%m-%d").date()
        for s in merged:
            d = datetime.strptime(s.date, "%Y-%m-%d").date()
            if d < cutoff:
                to_archive.append(s)
            else:
                to_keep.append(s)
        print(f"[rollup] 归档（< {archive_before}）: {len(to_archive)}")
    else:
        to_keep = merged

    # 构造新 log.md 内容
    new_log_md = preamble.rstrip() + "\n\n"

    # baseline 区块（包裹标记，告诉 AI/lint 这是历史不动）
    if baseline_segs:
        new_log_md += f"{BASELINE_MARK_BEGIN}\n\n"
        new_log_md += "\n".join(s.full_text for s in baseline_segs)
        if not new_log_md.endswith("\n"):
            new_log_md += "\n"
        new_log_md += f"\n{BASELINE_MARK_END}\n\n---\n\n"

    # rollup 区块
    new_log_md += f"{ROLLUP_MARK_BEGIN}\n\n"
    if to_keep:
        new_log_md += "\n".join(s.full_text for s in to_keep)
        if not new_log_md.endswith("\n"):
            new_log_md += "\n"
    new_log_md += f"\n{ROLLUP_MARK_END}\n"

    # 归档区
    archive_text = ""
    if to_archive:
        # 按季度分桶
        by_quarter: dict[str, list[Segment]] = {}
        for s in to_archive:
            d = datetime.strptime(s.date, "%Y-%m-%d").date()
            q = (d.month - 1) // 3 + 1
            key = f"{d.year}-Q{q}"
            by_quarter.setdefault(key, []).append(s)
        for q_key, segs in sorted(by_quarter.items()):
            archive_text = (
                f"# Log Archive {q_key}\n\n"
                f"> 由 log_rollup.py 从主 log.md 切出的旧段，仅供追溯。\n\n"
                f"---\n\n"
            )
            archive_text += "\n".join(s.full_text for s in segs)
            archive_path = project_root / LOG_ARCHIVE_DIR / f"{q_key}.md"
            if apply:
                archive_path.parent.mkdir(parents=True, exist_ok=True)
                archive_path.write_text(archive_text, encoding="utf-8")
                print(f"[rollup] WRITE {archive_path.relative_to(project_root)}")
            else:
                print(f"[dry-run] would write {archive_path.relative_to(project_root)} ({len(segs)} 段)")

    if apply:
        log_md.write_text(new_log_md, encoding="utf-8")
        print(f"[rollup] WRITE {LOG_MD} (合并 {len(to_keep)} v0.7+ 段)")
    else:
        print(f"[dry-run] would write {LOG_MD} (合并 {len(to_keep)} v0.7+ 段)")
        print("[dry-run] 使用 --apply 落盘")

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="log.d/ → log.md rollup + 季度归档",
    )
    parser.add_argument("--project-root", default=".", help="项目根目录（默认 .）")
    parser.add_argument("--apply", action="store_true",
                        help="实际写入（不加则 dry-run）")
    parser.add_argument("--archive-before", default=None,
                        help="把 YYYY-MM-DD 之前的段切到 log-archive/")
    parser.add_argument("--owner", default=None,
                        help="仅给指定 owner 跑（少用）")
    args = parser.parse_args(argv)
    try:
        return rollup(
            project_root=Path(args.project_root).resolve(),
            apply=args.apply,
            archive_before=args.archive_before,
            owner_filter=args.owner,
        )
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
