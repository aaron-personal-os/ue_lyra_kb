#!/usr/bin/env python3
"""
sync_title_and_aliases.py

批量同步 Docs/30-tutorials/ 下教程文档的：
1. frontmatter title 字段 → 与文件名一致（去除序号前缀）
2. 一级标题 (# xxx) → 与 title 一致
3. wikilink 中的旧英文别名 → 更新为新中文文件名

用法:
    python ToolsScript/sync_title_and_aliases.py              # dry-run
    python ToolsScript/sync_title_and_aliases.py --apply      # 实际写入
"""

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "Docs"
TUTORIALS_DIR = DOCS_DIR / "30-tutorials"


def filename_to_title(filename: str) -> str:
    """从文件名（不含.md）提取标题：去除序号前缀。"""
    # 去除 XX- 前缀
    match = re.match(r'^\d+-(.+)$', filename)
    if match:
        return match.group(1)
    return filename


def build_page_id_to_filename_map() -> dict[str, str]:
    """构建 page_id → 文件名(不含.md) 的映射。"""
    mapping = {}
    for md_file in TUTORIALS_DIR.rglob("*.md"):
        if md_file.name == "README.md" or md_file.name.startswith("_"):
            continue
        rel = md_file.relative_to(DOCS_DIR)
        page_id = rel.with_suffix('').as_posix()
        filename_stem = md_file.stem
        mapping[page_id] = filename_stem
    return mapping


def fix_title_and_h1(content: str, new_title: str) -> tuple[str, bool, bool]:
    """
    修复 frontmatter title 和一级标题。
    返回 (new_content, title_changed, h1_changed)
    """
    title_changed = False
    h1_changed = False

    # 1. 修复 frontmatter title
    def replace_title(m):
        nonlocal title_changed
        old_val = m.group(1).strip().strip('"').strip("'")
        if old_val != new_title:
            title_changed = True
            # 检查是否需要引号
            needs_quoting = any(ch in new_title for ch in [':', '#', '{', '}', '[', ']', ',', '&', '*', '?', '|', '-', '<', '>', '=', '!', '%', '@', '"', "'", '+'])
            if needs_quoting:
                escaped = new_title.replace('"', '\\"')
                return f'title: "{escaped}"'
            return f'title: {new_title}'
        return m.group(0)

    content = re.sub(r'^(title:\s*.+)$', lambda m: replace_title(m), content, count=1, flags=re.MULTILINE)

    # 2. 修复一级标题
    def replace_h1(m):
        nonlocal h1_changed
        old_h1 = m.group(1)
        if old_h1 != new_title:
            h1_changed = True
            return f'# {new_title}'
        return m.group(0)

    # 只替换 frontmatter 后的第一个 # 标题
    parts = content.split('---\n', 2)
    if len(parts) >= 3:
        body = parts[2]
        body = re.sub(r'^# (.+)$', replace_h1, body, count=1, flags=re.MULTILINE)
        content = f'{parts[0]}---\n{parts[1]}---\n{body}'

    return content, title_changed, h1_changed


def fix_wikilink_aliases(content: str, page_id_map: dict[str, str]) -> tuple[str, int]:
    """
    修复 wikilink 中使用旧英文别名的情况。

    检测模式：[[page-id|旧英文别名]] 中别名匹配 XX-english-slug 格式
    替换为：[[page-id|新中文文件名]]

    返回 (new_content, fix_count)
    """
    fix_count = 0

    # 匹配 [[xxx|alias]] 格式
    def replace_alias(m):
        nonlocal fix_count
        page_id = m.group(1)
        alias = m.group(2)

        # 检查 alias 是否是旧英文格式 (XX-english-slug)
        if not re.match(r'^\d{2}-[a-z][a-z0-9-]*$', alias):
            # 不是旧格式，跳过（但也检查带箭头的格式）
            arrow_match = re.match(r'^[←→]?\s*\d{2}-[a-z][a-z0-9-]*\s*[←→]?$', alias.strip())
            if not arrow_match:
                # 再检查一下是否是 "← XX-slug" 或 "XX-slug →" 格式
                prefix_arrow = re.match(r'^(←\s*)\d{2}-[a-z][a-z0-9-]+$', alias)
                suffix_arrow = re.match(r'^\d{2}-[a-z][a-z0-9-]+(\s*→)$', alias)
                if not prefix_arrow and not suffix_arrow:
                    return m.group(0)

        # 查找该 page_id 对应的新文件名
        if page_id in page_id_map:
            new_filename = page_id_map[page_id]
            new_title = filename_to_title(new_filename)

            # 保留箭头
            prefix = ""
            suffix = ""
            if alias.strip().startswith("←"):
                prefix = "← "
            if alias.strip().endswith("→"):
                suffix = " →"

            new_alias = f"{prefix}{new_title}{suffix}"
            fix_count += 1
            return f"[[{page_id}|{new_alias}]]"

        return m.group(0)

    # 匹配 [[page-id|alias]] 格式的 wikilink
    content = re.sub(
        r'\[\[([^\]|#]+)\|([^\]]+)\]\]',
        replace_alias,
        content
    )

    return content, fix_count


def process_file(filepath: Path, page_id_map: dict[str, str], apply: bool) -> dict:
    """处理单个文件。"""
    result = {
        'path': filepath,
        'title_changed': False,
        'h1_changed': False,
        'alias_fixes': 0,
    }

    content = filepath.read_text(encoding="utf-8")
    new_title = filename_to_title(filepath.stem)

    # 1. 修复 title 和 H1
    content, title_changed, h1_changed = fix_title_and_h1(content, new_title)
    result['title_changed'] = title_changed
    result['h1_changed'] = h1_changed

    # 2. 修复 wikilink 别名
    content, alias_fixes = fix_wikilink_aliases(content, page_id_map)
    result['alias_fixes'] = alias_fixes

    # 写入
    if apply and (title_changed or h1_changed or alias_fixes > 0):
        filepath.write_text(content, encoding="utf-8")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="同步 title/H1 与文件名，修复 wikilink 旧英文别名"
    )
    parser.add_argument("--apply", action="store_true", help="实际写入文件")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细信息")
    args = parser.parse_args()

    print(f"{'🔧 执行模式' if args.apply else '👀 Dry-run 模式'}")
    print("=" * 70)

    # 构建映射
    page_id_map = build_page_id_to_filename_map()

    # 收集文件
    md_files = sorted(
        f for f in TUTORIALS_DIR.rglob("*.md")
        if f.name != "README.md" and not f.name.startswith("_")
    )

    stats = {'title': 0, 'h1': 0, 'alias': 0, 'files_touched': 0}

    for filepath in md_files:
        result = process_file(filepath, page_id_map, apply=args.apply)

        any_change = result['title_changed'] or result['h1_changed'] or result['alias_fixes'] > 0
        if any_change:
            stats['files_touched'] += 1

        if result['title_changed']:
            stats['title'] += 1
        if result['h1_changed']:
            stats['h1'] += 1
        stats['alias'] += result['alias_fixes']

        rel = filepath.relative_to(PROJECT_ROOT)
        if any_change:
            changes = []
            if result['title_changed']:
                changes.append("title")
            if result['h1_changed']:
                changes.append("H1")
            if result['alias_fixes'] > 0:
                changes.append(f"alias×{result['alias_fixes']}")
            prefix = "✅" if args.apply else "📝"
            print(f"  {prefix} {rel}  [{', '.join(changes)}]")
        elif args.verbose:
            print(f"  ✓  {rel}")

    print("\n" + "=" * 70)
    print(f"统计:")
    print(f"  title 修正: {stats['title']}")
    print(f"  H1 修正:    {stats['h1']}")
    print(f"  alias 修正: {stats['alias']}")
    print(f"  涉及文件:   {stats['files_touched']}")

    if not args.apply and stats['files_touched'] > 0:
        print(f"\n💡 添加 --apply 参数以实际写入文件")


if __name__ == "__main__":
    main()
