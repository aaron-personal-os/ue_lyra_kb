#!/usr/bin/env python3
"""
sync_description_from_blockquote.py

批量将 Docs/30-tutorials/ 下 Markdown 文件的 frontmatter description 字段
替换为文档中第一个引用块（blockquote）的内容。

用法:
    python sync_description_from_blockquote.py              # dry-run 模式（默认）
    python sync_description_from_blockquote.py --apply      # 实际写入
    python sync_description_from_blockquote.py --verbose    # 显示详细信息
"""

import argparse
import re
import sys
from pathlib import Path


# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TUTORIALS_DIR = PROJECT_ROOT / "Docs" / "30-tutorials"


def extract_frontmatter_and_body(content: str) -> tuple[str | None, str | None]:
    """
    分离 YAML frontmatter 和正文。
    返回 (frontmatter_text, body_text)，不含 --- 分隔符。
    """
    match = re.match(r"^---\n(.*?\n)---\n(.*)", content, re.DOTALL)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def extract_first_blockquote(body: str) -> str | None:
    """
    从正文中提取第一个引用块的纯文本内容。
    连续的 > 行视为同一个引用块。
    空的 > 行（仅有 > 或 > 后跟空白）视为段落分隔。
    """
    lines = body.split("\n")
    blockquote_lines: list[str] = []
    in_blockquote = False

    for line in lines:
        # 匹配引用行: 以 > 开头
        if re.match(r"^>\s?", line):
            in_blockquote = True
            # 去除 > 前缀和一个可选空格
            text = re.sub(r"^>\s?", "", line)
            blockquote_lines.append(text)
        elif in_blockquote:
            # 引用块结束
            break

    if not blockquote_lines:
        return None

    # 处理多行引用块：合并为单行描述
    # 1. 去除纯空行
    # 2. 用空格连接非空行
    result_parts: list[str] = []
    for line in blockquote_lines:
        stripped = line.strip()
        if stripped:
            result_parts.append(stripped)

    if not result_parts:
        return None

    return " ".join(result_parts)


def strip_markdown_formatting(text: str) -> str:
    """
    去除 Markdown 格式标记，保留纯文本。
    - **bold** / __bold__ → bold
    - *italic* / _italic_ → italic
    - `code` → code
    - [text](url) → text
    """
    # 去除加粗
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    # 去除斜体
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"_(.*?)_", r"\1", text)
    # 去除行内代码
    text = re.sub(r"`(.*?)`", r"\1", text)
    # 去除链接，保留文字
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    return text.strip()


def update_description_in_frontmatter(frontmatter: str, new_desc: str) -> str:
    """
    替换 frontmatter 中 description 字段的值。
    处理单行 description: xxx 格式。
    """
    # 对描述中的特殊 YAML 字符进行转义（用双引号包裹）
    # 如果包含冒号、引号、换行等特殊字符，需要引号包裹
    needs_quoting = any(ch in new_desc for ch in [':', '#', '{', '}', '[', ']', ',', '&', '*', '?', '|', '-', '<', '>', '=', '!', '%', '@', '\\', '"', "'", '\n'])

    if needs_quoting:
        # 转义内部双引号
        escaped = new_desc.replace('\\', '\\\\').replace('"', '\\"')
        yaml_value = f'"{escaped}"'
    else:
        yaml_value = new_desc

    # 替换 description 行
    updated = re.sub(
        r"^(description:\s*).*$",
        f"description: {yaml_value}",
        frontmatter,
        count=1,
        flags=re.MULTILINE,
    )
    return updated


def process_file(filepath: Path, apply: bool, verbose: bool) -> dict:
    """
    处理单个文件。返回状态字典。
    """
    result = {
        "path": filepath,
        "status": "skipped",
        "old_desc": None,
        "new_desc": None,
        "reason": None,
    }

    content = filepath.read_text(encoding="utf-8")

    # 1. 分离 frontmatter
    frontmatter, body = extract_frontmatter_and_body(content)
    if frontmatter is None:
        result["reason"] = "无 frontmatter"
        return result

    # 2. 检查是否有 description 字段
    desc_match = re.search(r"^description:\s*(.*)$", frontmatter, re.MULTILINE)
    if not desc_match:
        result["reason"] = "无 description 字段"
        return result

    old_desc = desc_match.group(1).strip().strip('"').strip("'")

    # 3. 提取第一个引用块
    blockquote = extract_first_blockquote(body)
    if blockquote is None:
        result["reason"] = "无引用块"
        return result

    # 4. 清理 Markdown 格式
    new_desc = strip_markdown_formatting(blockquote)

    if not new_desc:
        result["reason"] = "引用块清理后为空"
        return result

    result["old_desc"] = old_desc
    result["new_desc"] = new_desc

    # 5. 检查是否有变化
    if old_desc == new_desc:
        result["status"] = "unchanged"
        result["reason"] = "description 已一致"
        return result

    # 6. 更新 frontmatter
    new_frontmatter = update_description_in_frontmatter(frontmatter, new_desc)
    new_content = f"---\n{new_frontmatter}---\n{body}"

    if apply:
        filepath.write_text(new_content, encoding="utf-8")
        result["status"] = "updated"
    else:
        result["status"] = "would_update"

    return result


def main():
    parser = argparse.ArgumentParser(
        description="将 30-tutorials/ 下 MD 文件的 description 替换为第一个引用块内容"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际写入文件（默认 dry-run）",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示每个文件的详细信息",
    )
    args = parser.parse_args()

    if not TUTORIALS_DIR.exists():
        print(f"❌ 目录不存在: {TUTORIALS_DIR}")
        sys.exit(1)

    # 收集所有 .md 文件（排除 _series.yaml 和 README）
    md_files = sorted(
        f for f in TUTORIALS_DIR.rglob("*.md")
        if f.name != "README.md" and not f.name.startswith("_")
    )

    print(f"{'🔧 执行模式' if args.apply else '👀 Dry-run 模式'}  |  共 {len(md_files)} 个文件")
    print("=" * 70)

    stats = {"updated": 0, "would_update": 0, "unchanged": 0, "skipped": 0}

    for filepath in md_files:
        result = process_file(filepath, apply=args.apply, verbose=args.verbose)
        stats[result["status"]] += 1

        rel_path = filepath.relative_to(PROJECT_ROOT)

        if result["status"] in ("updated", "would_update"):
            prefix = "✅" if result["status"] == "updated" else "📝"
            print(f"  {prefix} {rel_path}")
            if args.verbose:
                print(f"     旧: {result['old_desc']}")
                print(f"     新: {result['new_desc']}")
                print()
        elif result["status"] == "skipped" and args.verbose:
            print(f"  ⏭️  {rel_path} — {result['reason']}")
        elif result["status"] == "unchanged" and args.verbose:
            print(f"  ✓  {rel_path} — 已一致")

    print("=" * 70)
    print("统计:")
    if args.apply:
        print(f"  ✅ 已更新: {stats['updated']}")
    else:
        print(f"  📝 待更新: {stats['would_update']}")
    print(f"  ✓  已一致: {stats['unchanged']}")
    print(f"  ⏭️  跳过:   {stats['skipped']}")

    if not args.apply and stats["would_update"] > 0:
        print(f"\n💡 添加 --apply 参数以实际写入文件")


if __name__ == "__main__":
    main()
