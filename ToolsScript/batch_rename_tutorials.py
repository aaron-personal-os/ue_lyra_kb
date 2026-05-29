#!/usr/bin/env python3
"""
batch_rename_tutorials.py

批量重命名 Docs/30-tutorials/ 下所有教程文档：
  旧格式: XX-english-slug.md
  新格式: XX-中文标题.md（基于 frontmatter title 字段）

用法:
    python ToolsScript/batch_rename_tutorials.py              # dry-run（预览映射）
    python ToolsScript/batch_rename_tutorials.py --apply      # 执行重命名
    python ToolsScript/batch_rename_tutorials.py --mapping    # 仅输出映射表

依赖: .codebuddy/skills/project-wiki/scripts/rename_page.py
"""

import argparse
import re
import sys
import subprocess
from pathlib import Path

import yaml

# === 路径常量 ===
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "Docs"
TUTORIALS_DIR = DOCS_DIR / "30-tutorials"
RENAME_SCRIPT = PROJECT_ROOT / ".codebuddy" / "skills" / "project-wiki" / "scripts" / "rename_page.py"


# === 文件名清洗 ===

def sanitize_title(title: str) -> str:
    """
    将 frontmatter title 转为合法文件名（不含序号前缀）。

    规则:
    1. 去除版本号后缀: (UE 5.7)、（UE5.7）等
    2. 括号中的英文缩写 → 连字符连接: (GA) → -GA
    3. 去除剩余特殊符号
    4. 去除空格
    5. 清理多余连字符
    """
    # 1. 去除版本号后缀（各种格式）
    title = re.sub(r'\s*[（(]\s*UE\s*5[\.\d]*\s*[）)]\s*', '', title)

    # 2. 括号中的英文缩写 → 连字符连接
    title = re.sub(r'\s*[（(]([A-Za-z][A-Za-z0-9]*)[）)]\s*', r'-\1', title)

    # 3. 去除剩余特殊符号
    title = re.sub(r'[：:、，,。.！!？?；;—–~…|｜·•★☆「」【】\[\]（）()\{\}<>《》/\\\'\"＋+＝=]', '', title)

    # 4. 去除空格
    title = title.replace(' ', '')
    title = title.replace('　', '')  # 全角空格

    # 5. 清理多余连字符
    title = re.sub(r'-{2,}', '-', title)
    title = title.strip('-')

    return title


# === 读取 frontmatter ===

def read_frontmatter_title(filepath: Path) -> str | None:
    """从 .md 文件中提取 frontmatter 的 title 字段。"""
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?\n)---\n", text, re.DOTALL)
    if not match:
        return None
    fm = match.group(1)
    title_match = re.search(r'^title:\s*(.+)$', fm, re.MULTILINE)
    if not title_match:
        return None
    title = title_match.group(1).strip().strip('"').strip("'")
    return title


def read_frontmatter_id(filepath: Path) -> str | None:
    """从 .md 文件中提取 frontmatter 的 id 字段。"""
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?\n)---\n", text, re.DOTALL)
    if not match:
        return None
    fm = match.group(1)
    id_match = re.search(r'^id:\s*(.+)$', fm, re.MULTILINE)
    if not id_match:
        return None
    return id_match.group(1).strip().strip('"').strip("'")


# === _series.yaml 处理 ===

def load_series_yaml(series_dir: Path) -> dict | None:
    """加载 _series.yaml。"""
    yaml_path = series_dir / "_series.yaml"
    if not yaml_path.exists():
        return None
    return yaml.safe_load(yaml_path.read_text(encoding="utf-8"))


def get_series_lesson_order(series_data: dict) -> list[str]:
    """从 _series.yaml 的 learning_path 中提取所有 lesson 的顺序列表。"""
    lessons = []
    for stage in series_data.get("learning_path", []):
        for lesson in stage.get("lessons", []):
            lessons.append(lesson)
    return lessons


def update_series_yaml(series_dir: Path, old_to_new_map: dict[str, str]) -> bool:
    """更新 _series.yaml 中的 lesson 引用。返回是否有变更。"""
    yaml_path = series_dir / "_series.yaml"
    if not yaml_path.exists():
        return False

    text = yaml_path.read_text(encoding="utf-8")
    new_text = text
    for old_name, new_name in old_to_new_map.items():
        # 替换 lesson 引用（不含 .md 后缀，不含目录前缀）
        new_text = new_text.replace(old_name, new_name)

    if new_text != text:
        yaml_path.write_text(new_text, encoding="utf-8")
        return True
    return False


# === 生成重命名映射 ===

def generate_rename_mapping() -> list[dict]:
    """
    生成所有需要重命名的文件映射。

    Returns:
        list of {
            'old_id': str,       # 旧 page_id (如 30-tutorials/gas/01-ga-overview)
            'new_id': str,       # 新 page_id (如 30-tutorials/gas/01-GameplayAbility-GA简介与配置)
            'old_filename': str, # 旧文件名
            'new_filename': str, # 新文件名
            'series': str,       # 所属系列目录名
            'title': str,        # 原始 title
        }
    """
    mappings = []

    # 获取 mutable 系列的 _series.yaml 顺序
    mutable_series = load_series_yaml(TUTORIALS_DIR / "mutable")
    mutable_order = get_series_lesson_order(mutable_series) if mutable_series else []

    # 遍历所有教程 .md 文件
    for md_file in sorted(TUTORIALS_DIR.rglob("*.md")):
        # 跳过非教程文件
        if md_file.name == "README.md" or md_file.name.startswith("_"):
            continue

        # 获取 title
        title = read_frontmatter_title(md_file)
        if not title:
            continue

        # 获取当前 page_id
        page_id = read_frontmatter_id(md_file)
        if not page_id:
            continue

        # 获取当前文件名（不含 .md）
        old_stem = md_file.stem

        # 获取相对路径（不含 Docs/ 前缀和 .md 后缀）
        rel_to_docs = md_file.relative_to(DOCS_DIR)
        old_id = rel_to_docs.with_suffix('').as_posix()

        # 获取系列名
        rel_to_tutorials = md_file.relative_to(TUTORIALS_DIR)
        series_name = rel_to_tutorials.parts[0] if len(rel_to_tutorials.parts) > 1 else ""

        # 提取当前序号
        num_match = re.match(r'^(\d+)', old_stem)
        if not num_match:
            # 无序号文件(如 index.md) — 特殊处理
            new_stem = sanitize_title(title)
        else:
            current_num = num_match.group(1)

            # mutable 系列：重新编号
            if series_name == "mutable":
                new_num = _get_mutable_new_number(old_stem, mutable_order)
                if new_num is not None:
                    current_num = new_num

            new_stem = f"{current_num}-{sanitize_title(title)}"

        # 构建新 page_id
        new_rel = rel_to_docs.with_stem(new_stem) if hasattr(rel_to_docs, 'with_stem') else \
                  rel_to_docs.parent / f"{new_stem}.md"
        new_id = new_rel.with_suffix('').as_posix()

        # 跳过不需要改名的
        if old_id == new_id:
            continue

        mappings.append({
            'old_id': old_id,
            'new_id': new_id,
            'old_filename': md_file.name,
            'new_filename': f"{new_stem}.md",
            'series': series_name,
            'title': title,
            'filepath': md_file,
        })

    return mappings


def _get_mutable_new_number(old_stem: str, mutable_order: list[str]) -> str | None:
    """
    根据 mutable _series.yaml 顺序获取新编号。
    不在 series 中的文件（06-advanced-topics）追加到末尾。
    """
    if old_stem in mutable_order:
        idx = mutable_order.index(old_stem)
        return f"{idx:02d}"

    # 不在 series.yaml 中的文件追加到末尾
    if old_stem == "06-advanced-topics":
        return f"{len(mutable_order):02d}"

    return None


# === 执行重命名 ===

def execute_rename(old_id: str, new_id: str, apply: bool) -> tuple[bool, str]:
    """
    调用 rename_page.py 执行单个重命名。

    Returns:
        (success, output_message)
    """
    cmd = [
        sys.executable,
        str(RENAME_SCRIPT),
        "--from", old_id,
        "--to", new_id,
        "--project-root", str(PROJECT_ROOT),
    ]
    if apply:
        cmd.append("--apply")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 2:
            return False, result.stdout + result.stderr
        return True, result.stdout
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)


# === 主流程 ===

def main():
    parser = argparse.ArgumentParser(
        description="批量重命名 30-tutorials/ 下教程文档为中文命名"
    )
    parser.add_argument("--apply", action="store_true",
                        help="实际执行重命名（默认 dry-run）")
    parser.add_argument("--mapping", action="store_true",
                        help="仅输出映射表，不执行任何操作")
    parser.add_argument("--limit", type=int, default=0,
                        help="限制处理数量（调试用）")
    args = parser.parse_args()

    print(f"{'🔧 执行模式' if args.apply else '👀 Dry-run 模式'}")
    print("=" * 80)

    # 1. 生成映射
    mappings = generate_rename_mapping()

    if args.limit > 0:
        mappings = mappings[:args.limit]

    print(f"共 {len(mappings)} 个文件需要重命名\n")

    if args.mapping:
        # 仅输出映射表
        for m in mappings:
            print(f"  {m['old_id']}")
            print(f"  → {m['new_id']}")
            print()
        return

    # 2. 检查冲突
    new_ids = [m['new_id'] for m in mappings]
    duplicates = [x for x in new_ids if new_ids.count(x) > 1]
    if duplicates:
        print("❌ 检测到新文件名冲突:")
        for dup in set(duplicates):
            conflicts = [m for m in mappings if m['new_id'] == dup]
            for c in conflicts:
                print(f"  {c['old_id']} → {dup}")
        sys.exit(2)

    # 3. 执行重命名
    success_count = 0
    fail_count = 0
    series_updates: dict[str, dict[str, str]] = {}  # series_name → {old_lesson: new_lesson}

    for i, m in enumerate(mappings, 1):
        old_id = m['old_id']
        new_id = m['new_id']

        if args.apply:
            ok, output = execute_rename(old_id, new_id, apply=True)
            if ok:
                print(f"  ✅ [{i}/{len(mappings)}] {m['old_filename']} → {m['new_filename']}")
                success_count += 1

                # 记录需要更新 _series.yaml 的映射
                series = m['series']
                old_lesson = Path(m['old_filename']).stem
                new_lesson = Path(m['new_filename']).stem
                if series not in series_updates:
                    series_updates[series] = {}
                series_updates[series][old_lesson] = new_lesson
            else:
                print(f"  ❌ [{i}/{len(mappings)}] {m['old_filename']}: {output.strip()}")
                fail_count += 1
        else:
            print(f"  📝 [{i}/{len(mappings)}] {m['old_filename']}")
            print(f"       → {m['new_filename']}")

    # 4. 更新 _series.yaml
    if args.apply and series_updates:
        print("\n更新 _series.yaml 文件:")
        for series_name, lesson_map in series_updates.items():
            # 找到 series 目录
            series_dir = TUTORIALS_DIR / series_name
            if not series_dir.is_dir():
                # 处理嵌套目录情况（如 ue-framework/10-engine-layer）
                # lesson_map 中的 key 可能包含子路径
                series_dir = TUTORIALS_DIR / series_name

            if update_series_yaml(series_dir, lesson_map):
                print(f"  ✅ {series_name}/_series.yaml")
            else:
                print(f"  ⏭️  {series_name}/_series.yaml (无变化或不存在)")

    # 5. 统计
    print("\n" + "=" * 80)
    if args.apply:
        print(f"✅ 成功: {success_count}  ❌ 失败: {fail_count}")
        if success_count > 0:
            print("\n后续步骤:")
            print("  1. git add -A && git status  # 检查变更")
            print("  2. python .codebuddy/skills/project-wiki/scripts/wiki_lint.py  # 验证链接")
    else:
        print(f"📝 待重命名: {len(mappings)} 个文件")
        print("\n💡 添加 --apply 参数以实际执行重命名")


if __name__ == "__main__":
    main()
