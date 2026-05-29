"""
Docs/30-tutorials/ 教程 frontmatter 检查与修复（wiki_lint 集成版）。

本脚本是 wiki_lint.py 教程检查的便捷入口。核心逻辑已整合到:
  .codebuddy/skills/project-wiki/scripts/wiki_lint.py (check_tutorial_frontmatter / fix_tutorial_frontmatter)

用法：
  python ToolsScript/check_frontmatter.py            # 检查（调用 wiki_lint --scope wiki）
  python ToolsScript/check_frontmatter.py --fix      # 修复（调用 wiki_lint --fix）
  python ToolsScript/check_frontmatter.py --h1       # 输出所有文件的一级标题和 title 字段
  python ToolsScript/check_frontmatter.py --fix-id   # 自动修正 id 字段
"""

import argparse
import re
import sys
import subprocess
from pathlib import Path

# ========== 配置 ==========
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "Docs"
TUTORIALS_DIR = DOCS_DIR / "30-tutorials"
WIKI_LINT = PROJECT_ROOT / ".codebuddy" / "skills" / "project-wiki" / "scripts" / "wiki_lint.py"


# ========== 工具函数 ==========

def extract_frontmatter(content: str) -> tuple[dict | None, str]:
    """提取 YAML frontmatter 和正文(mini parser)"""
    if not content.startswith("---"):
        return None, content
    end = content.find("\n---", 3)
    if end == -1:
        return None, content
    fm_str = content[3:end]
    body = content[end + 4:]
    try:
        import yaml
        fm = yaml.safe_load(fm_str)
        return (fm if isinstance(fm, dict) else None), body
    except Exception:
        # fallback: mini parse
        fm = {}
        for line in fm_str.splitlines():
            m = re.match(r"^([\w-]+):\s*(.*)$", line)
            if m:
                fm[m.group(1)] = m.group(2).strip().strip("'\"")
        return fm, body


def extract_h1(body: str) -> str:
    """提取正文中第一个一级标题"""
    m = re.search(r"^[ \t]*#[ \t]+(.+?)\s*$", body, re.MULTILINE)
    return m.group(1).strip() if m else ""


def collect_md_files() -> list[Path]:
    """收集所有 .md 文件（排除 README 和 _ 前缀文件）"""
    md_files = sorted(TUTORIALS_DIR.rglob("*.md"))
    return [f for f in md_files if f.name != "README.md" and not f.name.startswith("_")]


def expected_id(file_path: Path) -> str:
    """根据文件路径计算期望的 id 值"""
    rel = file_path.relative_to(PROJECT_ROOT)
    return str(rel).replace("\\", "/").replace(".md", "").replace("Docs/", "")


# ========== --h1 报告 ==========

def print_h1_report(md_files: list[Path]):
    """输出所有文件的一级标题和 title 字段对比"""
    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  H1 与 Title 对比报告 — {len(md_files)} 个文件")
    print(f"╚══════════════════════════════════════════════════════╝")
    print()
    print(f"{'文件路径':<60} {'H1':<40} {'title 字段':<40}")
    print("─" * 140)

    mismatch_count = 0
    for f in md_files:
        content = f.read_text(encoding="utf-8")
        fm, body = extract_frontmatter(content)
        h1 = extract_h1(body)
        title = fm.get("title", "") if fm else ""
        rel = str(f.relative_to(PROJECT_ROOT)).replace("\\", "/")

        marker = ""
        if h1 and title and h1.strip() != title.strip():
            marker = " ⚠️"
            mismatch_count += 1
        elif not h1:
            marker = " ❌(无H1)"
        elif not title:
            marker = " ❌(无title)"

        print(f"{rel:<60} {h1[:38]:<40} {title[:38]:<40}{marker}")

    print()
    print("─" * 140)
    print(f"📊 汇总: {len(md_files)} 文件 | {mismatch_count} 个 H1/title 不一致")


# ========== --fix-id ==========

def fix_ids(md_files: list[Path]):
    """修正所有文件的 id 字段"""
    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  ID 字段修正 — {len(md_files)} 个文件")
    print(f"╚══════════════════════════════════════════════════════╝")
    print()

    fixed_count = 0
    for f in md_files:
        content = f.read_text(encoding="utf-8")
        fm, body = extract_frontmatter(content)
        if fm is None:
            continue
        exp = expected_id(f)
        if fm.get("id") != exp:
            # 替换 id 行
            new_content = re.sub(
                r"^id:\s*.*$",
                f"id: {exp}",
                content,
                count=1,
                flags=re.MULTILINE
            )
            if new_content == content and "id:" not in content[:500]:
                # 没有 id 字段，在第二行插入
                lines = content.splitlines()
                if len(lines) > 1:
                    lines.insert(1, f"id: {exp}")
                    new_content = "\n".join(lines)
            if new_content != content:
                f.write_text(new_content, encoding="utf-8")
                fixed_count += 1
                rel = str(f.relative_to(PROJECT_ROOT)).replace("\\", "/")
                print(f"  ✅ 已修正 id: {rel} → {exp}")

    print()
    print(f"📊 汇总: {fixed_count}/{len(md_files)} 文件已修正 id")


# ========== 主逻辑 ==========

def main():
    parser = argparse.ArgumentParser(description="检查/修复 Docs/30-tutorials/ 的 YAML frontmatter（wiki_lint 集成版）")
    parser.add_argument("--fix", action="store_true", help="自动修复 frontmatter（调用 wiki_lint --fix）")
    parser.add_argument("--fix-id", action="store_true", help="自动修正 id 字段")
    parser.add_argument("--h1", action="store_true", help="输出所有文件的一级标题和 title 字段")
    args = parser.parse_args()

    if not TUTORIALS_DIR.exists():
        print(f"❌ 目录不存在: {TUTORIALS_DIR}")
        sys.exit(1)

    md_files = collect_md_files()

    # --h1 模式
    if args.h1:
        print_h1_report(md_files)
        return 0

    # --fix-id 模式
    if args.fix_id:
        fix_ids(md_files)
        return 0

    # --fix 模式: 调用 wiki_lint --fix
    if args.fix:
        print("═" * 56)
        print("  调用 wiki_lint.py --fix --scope wiki ...")
        print("═" * 56)
        print()
        result = subprocess.run(
            [sys.executable, str(WIKI_LINT), "--fix", "--scope", "wiki",
             "--project-root", str(PROJECT_ROOT)],
            cwd=str(PROJECT_ROOT),
        )
        return result.returncode

    # 默认模式: 调用 wiki_lint --scope wiki 只看教程相关错误
    result = subprocess.run(
        [sys.executable, str(WIKI_LINT), "--scope", "wiki",
         "--project-root", str(PROJECT_ROOT)],
        cwd=str(PROJECT_ROOT),
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
