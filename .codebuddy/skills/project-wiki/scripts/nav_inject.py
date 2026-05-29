#!/usr/bin/env python3
"""nav_inject.py — 给 wiki 页底部注入"上一页 / 下一页"导航 (R23 创立, R32 简化, R33 移除 index 链接)

简介
====

知识库 50+ 页面在 markdown 渲染器(GitHub / VSCode preview / cursor agent
chat)里没有"按 index.md 顺序串浏览"的能力 —— 跳页只能回 index.md 找下一页。
本脚本扫 `Docs/index.md` 中所有 `[[id]]` 出现顺序作为权威序,在每个目标
wiki 页底部注入由 mark 注释包裹的 nav 块。

★ R33 重要变更:
- 导航块中 **移除中间的 `[[index|↑ index]]` 链接**:
  index 跳转对中间页用处不大,且占据视觉空间。
- 仅保留 prev/next 两个方向链接。
- 当 prev/next 都为 None 时(孤立页 / 单页分组),不再写入空 nav 块。

★ R32 行为(保留):
- "目录段分组"单一模式
- prev/next 绝不跨组: 组首页 prev=None, 组末页 next=None
- 详见 [[60-decisions/0005-tutorial-cross-link-policy]] §"导航分组策略"

导航分组规则 (nav group)
------------------------

按 page_id **目录路径** 的前两级作为 group key (不足两级时取实际深度,
末段视为文件名不计入分组):

| page_id 形式                        | group key                   | 说明                                                  |
|-------------------------------------|----------------------------|-------------------------------------------------------|
| `30-tutorials/<series>/<lesson>`    | `30-tutorials/<series>`    | 教程系列内连续翻页                                    |
| `30-tutorials/<series>/<sub>/<l>`   | `30-tutorials/<series>`    | 教程子目录(如 network-sync/iris/...)仍归属系列        |
| `20-modules/<lang>/<class>`         | `20-modules/<lang>`        | C++/Python 模块各成一组                               |
| `10-architecture/<sub>/<page>`      | `10-architecture/<sub>`    | architecture 子目录各成一组                           |
| `10-architecture/overview`          | `10-architecture`          | 顶层页(无子目录) → 取一级目录                         |
| `40-runbooks/<page>`                | `40-runbooks`              | 单层目录 → 取一级目录,内部连续                        |
| `60-decisions/<page>`               | `60-decisions`             | ADR 内连续                                            |
| `70-topics/<page>`                  | `70-topics`                | topics 内连续                                         |
| `80-gotchas/<page>`                 | `80-gotchas`               | gotchas 内连续                                        |

效果对比 (R32 → R33):

| 页面                                       | R32                                                         | R33(本版本)                                  |
|--------------------------------------------|-------------------------------------------------------------|----------------------------------------------|
| 中间页                                     | `← prev · ↑ index · next →`                                 | `← prev · next →`                            |
| 组首页                                     | `↑ index · next →`                                          | `next →`                                     |
| 组末页                                     | `← prev · ↑ index`                                          | `← prev`                                     |
| 单页分组(prev=None, next=None)             | `↑ index`(只剩 index 链接,无意义但仍写入)                  | 不写入 nav 块                                |

输出格式
--------

```
<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ALyraCharacter|ALyraCharacter]] · [[20-modules/cpp/ALyraGameMode|ALyraGameMode]] →

<!-- /nav:auto -->
```

设计原则
--------

1. **index.md 是单一事实源**: nav 顺序完全派生自 index.md `[[id]]` 出现顺序;
   不打乱、不分类、不排序。改 index 即改 nav。

2. **mark 注释包裹**: `<!-- nav:auto -->` ... `<!-- /nav:auto -->` 之间的内容
   完全由本脚本管理。block 之外的内容**绝对不动**。重跑 `--apply` 是幂等的。

3. **dry-run 默认**: `--check` (或不带参数) 模式只报会改什么,不写文件。
   `--apply` 才落盘。

4. **`--strip` 模式**: 移除所有页的 nav 块(回滚 / 项目放弃 nav 概念时用)。

5. **跳过场景**:
   - index.md / overview.md / 00-meta/* (这些是导航源/元页本身,不需要 nav)
   - 没有 frontmatter 的页(meta 类约定无 fm)
   - 不在 index.md 出现的页(orphan 页;由 lint 单独处理)
   - prev/next 都为 None(孤立页 / 单页分组) → 不写 nav

6. **链接形式**: 用 wikilink `[[id|短显示名]]`,显示名取 id 最后一段
   (`20-modules/cpp/ALyraCharacter` → `ALyraCharacter`)。

7. **链不计入 asymm-link**: wiki_lint.py 看 `related:` frontmatter 字段算
   双向链,nav 块在 body 不影响 frontmatter,所以新增 nav 不会引发 asymm-link
   告警风暴。

为什么不挂 pre-commit
---------------------

- nav 注入是 "wiki 浏览体验" 装饰,不是 "知识完整性" 红线
- index.md 改一次就要重跑一次(改 frontmatter / 加新页),挂 pre-commit 会
  让所有 wiki commit 都自动改 50+ 文件,diff 噪音大
- 推荐工作流:
  - 写 wiki 期间: `nav_inject.py` (dry-run) 看会改哪些
  - 改完一批 wiki + index 后: 手动跑一次 `nav_inject.py --apply` + commit

用法
----

```bash
# 查看会改哪些(dry-run,默认)
python nav_inject.py

# 应用 nav 注入到所有页
python nav_inject.py --apply

# 移除所有 nav 块
python nav_inject.py --strip

# JSON 输出(给上层工具消费)
python nav_inject.py --json
```

退出码
------

- 0 : 没有任何页需要更新(已是最新 nav 状态)
- 0 : `--apply` / `--strip` 跑完无错误
- 1 : `--check` (dry-run) 模式下检测到有页需要更新(给 CI 用)
- 2 : 致命错误(index.md 不存在 / 解析失败 / I/O 错)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:\|[^\]]+)?(?:#[^\]]+)?\]\]")

NAV_BEGIN = "<!-- nav:auto -->"
NAV_END = "<!-- /nav:auto -->"

# 跳过 nav 注入的页(导航源 / 元页 / 模板)
SKIP_PAGE_IDS = {
    "index",
    "overview",
}
SKIP_PAGE_PREFIXES = (
    "00-meta/",
)


# ---------------------------------------------------------------------------
# 数据
# ---------------------------------------------------------------------------


@dataclass
class WikiPage:
    page_id: str
    abs_path: Path
    rel_path: str  # 仓库根的相对路径,统一 / 分隔


@dataclass
class NavEntry:
    file: str
    action: str  # "add" / "update" / "remove" / "skip-not-in-index" / "skip-no-fm"
    detail: str = ""


# ---------------------------------------------------------------------------
# 解析 index.md 顺序
# ---------------------------------------------------------------------------


def parse_index_order(index_path: Path) -> list[str]:
    """从 Docs/index.md 提取所有 [[id]] 的出现顺序(去重,保持首次出现位置)。"""
    seen: dict[str, int] = {}
    text = index_path.read_text(encoding="utf-8")
    for m in WIKILINK_RE.finditer(text):
        raw_id = m.group(1).strip()
        if not raw_id or raw_id in seen:
            continue
        seen[raw_id] = len(seen)
    return list(seen.keys())


def discover_pages(docs_root: Path) -> dict[str, WikiPage]:
    """扫 Docs/ 下所有 .md 文件,按 page_id 索引(page_id = 相对 Docs/ 的去 .md 路径)。"""
    pages: dict[str, WikiPage] = {}
    for f in sorted(docs_root.rglob("*.md")):
        if f.name.startswith("."):
            continue
        rel = f.relative_to(docs_root).as_posix()
        page_id = rel[:-3] if rel.endswith(".md") else rel
        pages[page_id] = WikiPage(
            page_id=page_id,
            abs_path=f,
            rel_path=f.as_posix(),
        )
    return pages


# ---------------------------------------------------------------------------
# 导航分组 (R32)
# ---------------------------------------------------------------------------


def nav_group(page_id: str) -> str:
    """返回 page_id 的导航分组 key (取目录路径,最多前两级)。

    规则:
    - page_id 末段视为"文件",前面视为"目录路径"
    - 取目录路径的前两级作为 group key (不足则取实际深度)
    - 若 page_id 只有一级(无目录),返回该顶层名(几乎不出现于本项目)

    Examples:
        '30-tutorials/gas/00-GAS系统总览'      → '30-tutorials/gas'
        '30-tutorials/network-sync/iris/00-x'  → '30-tutorials/network-sync'
        '20-modules/cpp/ALyraCharacter'        → '20-modules/cpp'
        '10-architecture/overview'             → '10-architecture'
        '10-architecture/subsystems/x'         → '10-architecture/subsystems'
        '80-gotchas/networking-ue57-x'         → '80-gotchas'
        '40-runbooks/how-to-x'                 → '40-runbooks'
        '60-decisions/0005-x'                  → '60-decisions'
        '70-topics/x'                          → '70-topics'
    """
    parts = page_id.split("/")
    # 末段是文件,丢弃;剩下的是目录路径
    dirs = parts[:-1]
    if not dirs:
        # 顶层文件(本项目仅 index/overview/log/README,均已被 SKIP 兜底)
        return parts[0]
    # 取最多前两级目录
    return "/".join(dirs[:2])


# ---------------------------------------------------------------------------
# nav 块构造 / 替换
# ---------------------------------------------------------------------------


def short_name(page_id: str) -> str:
    """从 page_id 提取最后一段作为短显示名。"""
    return page_id.rsplit("/", 1)[-1]


def build_nav_block(prev_id: str | None, next_id: str | None) -> str | None:
    """构造 nav 块文本(含 mark 注释 + 分隔线)。

    R33: 不再注入 `[[index|↑ index]]` 中间链。仅保留 prev/next 双向链。
    若 prev 与 next 都为 None(孤立页 / 单页分组),返回 None,由调用方
    决定不写入 nav 块。
    """
    if not prev_id and not next_id:
        return None

    parts: list[str] = []
    if prev_id:
        parts.append(f"← [[{prev_id}|{short_name(prev_id)}]]")
    if next_id:
        parts.append(f"[[{next_id}|{short_name(next_id)}]] →")
    nav_line = " · ".join(parts)

    return (
        f"{NAV_BEGIN}\n"
        f"\n"
        f"---\n"
        f"\n"
        f"**导航**: {nav_line}\n"
        f"\n"
        f"{NAV_END}\n"
    )


def has_frontmatter(text: str) -> bool:
    return text.startswith("---\n") and text.find("\n---", 4) > 0


def strip_existing_nav(text: str) -> str:
    """移除已有的 nav 块(含前后空行清理)。"""
    pattern = re.compile(
        r"\n*" + re.escape(NAV_BEGIN) + r".*?" + re.escape(NAV_END) + r"\n*",
        re.DOTALL,
    )
    return pattern.sub("\n", text).rstrip() + "\n"


def inject_nav(text: str, nav_block: str) -> str:
    """把 nav_block 写到文件末尾(strip 旧的之后)。"""
    cleaned = strip_existing_nav(text)
    if not cleaned.endswith("\n"):
        cleaned += "\n"
    return cleaned + "\n" + nav_block


def existing_nav_block(text: str) -> str | None:
    """提取已存在的 nav 块文本(用于幂等检测,无则返回 None)。"""
    m = re.search(
        re.escape(NAV_BEGIN) + r".*?" + re.escape(NAV_END),
        text,
        re.DOTALL,
    )
    return m.group(0) if m else None


# ---------------------------------------------------------------------------
# 主逻辑
# ---------------------------------------------------------------------------


def should_skip(page_id: str) -> bool:
    if page_id in SKIP_PAGE_IDS:
        return True
    return any(page_id.startswith(p) for p in SKIP_PAGE_PREFIXES)


def build_position_map(flat_order: list[str]) -> dict[str, dict]:
    """返回 page_id → {prev_id, next_id} 的查找表。

    ★ R32 行为: prev/next **不跨 nav_group**。
    - 当前页与前一页同组 → prev = 前一页;否则 prev = None
    - 当前页与后一页同组 → next = 后一页;否则 next = None
    """
    out: dict[str, dict] = {}
    for i, pid in enumerate(flat_order):
        cur_grp = nav_group(pid)
        prev_pid = flat_order[i - 1] if i > 0 else None
        next_pid = flat_order[i + 1] if i + 1 < len(flat_order) else None

        same_grp_prev = prev_pid if prev_pid and nav_group(prev_pid) == cur_grp else None
        same_grp_next = next_pid if next_pid and nav_group(next_pid) == cur_grp else None

        out[pid] = {
            "prev_id": same_grp_prev,
            "next_id": same_grp_next,
        }
    return out


def process_pages(
    pos_map: dict[str, dict],
    pages: dict[str, WikiPage],
    *,
    strip_only: bool,
    apply: bool,
) -> list[NavEntry]:
    """统一处理函数: dry-run 或 apply 由 apply 参数控制。"""
    entries: list[NavEntry] = []
    for page_id, page in pages.items():
        if should_skip(page_id):
            continue
        text = page.abs_path.read_text(encoding="utf-8")
        if not has_frontmatter(text):
            entries.append(NavEntry(page.rel_path, "skip-no-fm"))
            continue

        existing = existing_nav_block(text)
        if strip_only:
            if existing:
                if apply:
                    page.abs_path.write_text(strip_existing_nav(text), encoding="utf-8")
                entries.append(NavEntry(page.rel_path, "remove"))
            continue

        info = pos_map.get(page_id)
        if info is None:
            entries.append(NavEntry(
                page.rel_path,
                "skip-not-in-index",
                f"page_id {page_id!r} 不在 index.md 出现 → 不注入 nav (建议先在 index 上架)",
            ))
            continue

        new_block = build_nav_block(info["prev_id"], info["next_id"])

        # R33: prev 与 next 都为 None 时 build_nav_block 返回 None,
        # 此时若已有 nav 块需移除,否则跳过。
        if new_block is None:
            if existing:
                if apply:
                    page.abs_path.write_text(strip_existing_nav(text), encoding="utf-8")
                entries.append(NavEntry(
                    page.rel_path,
                    "remove",
                    "孤立页/单页分组,无 prev/next → 移除 nav 块",
                ))
            continue

        if existing and existing == new_block.strip():
            continue

        action = "update" if existing else "add"
        new_text = inject_nav(text, new_block)
        if new_text == text:
            continue
        if apply:
            page.abs_path.write_text(new_text, encoding="utf-8")
        entries.append(NavEntry(page.rel_path, action))
    return entries


def compute_nav_actions(
    order: list[str],
    pages: dict[str, WikiPage],
    *,
    strip_only: bool,
) -> list[NavEntry]:
    """dry-run 入口(向后兼容旧 API 名)。"""
    pos_map = build_position_map(order)
    return process_pages(pos_map, pages, strip_only=strip_only, apply=False)


def apply_nav(
    order: list[str],
    pages: dict[str, WikiPage],
    *,
    strip_only: bool,
) -> list[NavEntry]:
    """apply 入口(向后兼容旧 API 名)。"""
    pos_map = build_position_map(order)
    return process_pages(pos_map, pages, strip_only=strip_only, apply=True)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="给 wiki 页底部注入 prev/up/next 导航 (R23 创立 / R32 简化为目录段分组单一模式)",
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd(),
                        help="项目根(含 Docs/),默认 cwd")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true", help="实际写入(默认 dry-run)")
    g.add_argument("--strip", action="store_true", help="移除所有 nav 块")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args(argv)

    docs_root = args.project_root / "Docs"
    index_md = docs_root / "index.md"
    if not index_md.is_file():
        print(f"[error] 找不到 {index_md}", file=sys.stderr)
        return 2

    try:
        order = parse_index_order(index_md)
    except OSError as e:
        print(f"[error] 读取 {index_md} 失败: {e}", file=sys.stderr)
        return 2

    pages = discover_pages(docs_root)

    apply_flag = args.apply or args.strip
    if apply_flag:
        entries = apply_nav(order, pages, strip_only=args.strip)
    else:
        entries = compute_nav_actions(order, pages, strip_only=False)

    relevant = [e for e in entries if e.action in ("add", "update", "remove")]
    skipped_no_fm = sum(1 for e in entries if e.action == "skip-no-fm")
    skipped_not_in_index = sum(1 for e in entries if e.action == "skip-not-in-index")

    if args.json:
        # 统计独立分组数(给上层工具用)
        groups = {nav_group(pid) for pid in order}
        print(json.dumps({
            "summary": {
                "needs_change": len(relevant),
                "skipped_no_fm": skipped_no_fm,
                "skipped_not_in_index": skipped_not_in_index,
                "total_pages": len(pages),
                "indexed_ids": len(order),
                "nav_groups": len(groups),
                "applied": args.apply or args.strip,
            },
            "entries": [
                {"file": e.file, "action": e.action, "detail": e.detail}
                for e in entries
            ],
        }, ensure_ascii=False, indent=2))
        return 1 if (relevant and not (args.apply or args.strip)) else 0

    mode = "apply" if args.apply else ("strip" if args.strip else "check (dry-run)")
    groups = {nav_group(pid) for pid in order}

    print(f"[nav_inject] 模式: {mode}")
    print(f"[nav_inject] index 顺序条目: {len(order)}  /  nav 分组: {len(groups)}")
    print(f"[nav_inject] Docs/ 下 .md 总数: {len(pages)}")
    print(f"[nav_inject] 跳过(meta/无fm): {skipped_no_fm}")
    print(f"[nav_inject] 跳过(不在 index): {skipped_not_in_index}")
    print()

    if not relevant:
        print("[nav_inject] ✓ 所有页 nav 已最新,无需变更")
        return 0

    print(f"[nav_inject] {len(relevant)} 个页需要 {'remove' if args.strip else '更新/新增'}:")
    for e in relevant:
        marker = {"add": "+", "update": "~", "remove": "-"}.get(e.action, "?")
        print(f"  [{marker}] {e.file}")

    if args.apply or args.strip:
        print(f"\n[nav_inject] ✓ 已写入 {len(relevant)} 个页")
        return 0

    print(f"\n[nav_inject] ⚠ dry-run 模式,未写文件。跑 --apply 落盘")
    return 1


if __name__ == "__main__":
    sys.exit(main())
