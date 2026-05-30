#!/usr/bin/env python3
"""
Validate UE agent knowledge graph: frontmatter tags, related_concepts links,
concept page structure. Read-only; does not modify files.

Usage:
  python knowledge_graph_check.py --check
  python knowledge_graph_check.py --check --strict
  python knowledge_graph_check.py --print-tags
  python knowledge_graph_check.py --inventory
  python knowledge_graph_check.py --root docs/ue-agent-knowledge
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ALLOWED_TAG_PREFIXES = ("concept:", "pitfall:", "api:", "script:", "gate:", "asset:")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
LIST_ITEM_RE = re.compile(r"^\s*-\s+(.+)$")
CASE_CONCEPT_RE = re.compile(r"^>\s*\*\*相关概念\*\*")
CASE_HEADING_RE = re.compile(r"^##\s+案例\s+\d+")


def find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / ".ue-py-config.json").is_file():
            return p
    return start


def parse_simple_yaml_block(block: str) -> dict[str, list[str]]:
    data: dict[str, list[str]] = {}
    current_key: str | None = None
    for line in block.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith(" ") and current_key:
            m = LIST_ITEM_RE.match(line)
            if m:
                data.setdefault(current_key, []).append(m.group(1).strip().strip('"').strip("'"))
            continue
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            current_key = key
            if val:
                data[key] = [val.strip('"').strip("'")]
            elif key not in data:
                data[key] = []
    return data


def extract_frontmatter(text: str) -> dict[str, list[str]] | None:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    return parse_simple_yaml_block(m.group(1))


def collect_md_files(kb_root: Path) -> list[Path]:
    files: list[Path] = []
    for sub in ("concepts", "modules"):
        d = kb_root / sub
        if d.is_dir():
            files.extend(sorted(d.glob("*.md")))
    kb = kb_root / "knowledge-base.md"
    if kb.is_file():
        files.insert(0, kb)
    return files


def resolve_link(from_file: Path, link: str, kb_root: Path) -> Path | None:
    link = link.split("#")[0].strip()
    if not link or link.startswith("http"):
        return None
    if link.startswith("/"):
        return None
    base = (from_file.parent / link).resolve()
    try:
        base.relative_to(kb_root.resolve())
    except ValueError:
        return None
    return base


def concept_has_case_links(text: str) -> bool:
    if "## 关联案例" in text or "## 相关文档" in text:
        return True
    return bool(re.search(r"\]\(\.\./modules/[^\)]+\)", text))


def count_case_concept_links(text: str) -> tuple[int, int]:
    """Return (total_case_headings, cases_with_concept_block)."""
    lines = text.splitlines()
    cases = 0
    with_link = 0
    i = 0
    while i < len(lines):
        if CASE_HEADING_RE.match(lines[i]):
            cases += 1
            j = i + 1
            found = False
            while j < len(lines) and not CASE_HEADING_RE.match(lines[j]):
                if CASE_CONCEPT_RE.match(lines[j]):
                    found = True
                    break
                if lines[j].startswith("## ") and not lines[j].startswith("## 案例"):
                    break
                j += 1
            if found:
                with_link += 1
        i += 1
    return cases, with_link


def has_related_docs_section(text: str) -> bool:
    return "## 相关文档" in text


def run_inventory(kb_root: Path) -> int:
    rows: list[dict] = []
    for md in collect_md_files(kb_root):
        text = md.read_text(encoding="utf-8")
        fm = extract_frontmatter(text)
        rel = str(md.relative_to(kb_root))
        kb_type = (fm.get("kb_type") or [""])[0] if fm else ""
        row = {
            "path": rel,
            "frontmatter": fm is not None,
            "kb_type": kb_type,
            "tag_count": len(fm.get("tags", [])) if fm else 0,
            "related_concepts": len(fm.get("related_concepts", [])) if fm else 0,
            "concept_case_links": (
                concept_has_case_links(text)
                if md.parent.name == "concepts" and md.name != "index.md"
                else None
            ),
            "related_docs_section": has_related_docs_section(text),
            "in_index": (
                md.name in (kb_root / "concepts" / "index.md").read_text(encoding="utf-8")
                if (kb_root / "concepts" / "index.md").is_file()
                else False
            ),
        }
        rows.append(row)

    print("=== Knowledge graph inventory ===")
    print(f"Root: {kb_root}\n")
    print("| path | FM | kb_type | tags | rel_concepts | case_links | 相关文档 | in_index |")
    print("|------|----|---------|------|--------------|------------|----------|----------|")
    for r in rows:
        cl = "" if r["concept_case_links"] is None else ("Y" if r["concept_case_links"] else "N")
        idx = "Y" if r["in_index"] or r["path"] == "knowledge-base.md" else "-"
        rd = "Y" if r["related_docs_section"] else "N"
        print(
            f"| {r['path']} | {'Y' if r['frontmatter'] else 'N'} | {r['kb_type'] or '-'} | "
            f"{r['tag_count']} | {r['related_concepts']} | {cl or '-'} | {rd} | {idx} |"
        )
    inv_path = kb_root / "concepts" / "inventory.generated.json"
    inv_path.parent.mkdir(parents=True, exist_ok=True)
    inv_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {inv_path.relative_to(kb_root)}")
    return 0


def run_check(kb_root: Path, strict: bool) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    tag_registry: dict[str, list[str]] = {}
    concept_files: set[Path] = set()
    module_files: set[Path] = set()
    referenced_from_fm: set[Path] = set()

    kb = kb_root / "knowledge-base.md"
    if kb.is_file():
        kb_text = kb.read_text(encoding="utf-8")
        if "concepts/index" not in kb_text and "concepts/index.md" not in kb_text:
            errors.append("knowledge-base.md: missing link to concepts/index")

    for md in collect_md_files(kb_root):
        text = md.read_text(encoding="utf-8")
        fm = extract_frontmatter(text)
        rel = md.relative_to(kb_root)

        if md.parent.name == "concepts" and md.name != "index.md":
            concept_files.add(md)
            if not concept_has_case_links(text):
                msg = f"{rel}: concept page has no case links (../modules/)"
                (errors if strict else warnings).append(msg)

        if md.parent.name == "modules":
            module_files.add(md)

        if not fm:
            if md.parent.name == "modules":
                msg = f"{rel}: no YAML frontmatter (required for modules)"
                (errors if strict else warnings).append(msg)
            elif md.parent.name == "concepts" and md.name != "index.md":
                msg = f"{rel}: no YAML frontmatter"
                (errors if strict else warnings).append(msg)
            continue

        kb_type = (fm.get("kb_type") or [""])[0]
        if kb_type in ("module", "concept") and not fm.get("tags"):
            warnings.append(f"{rel}: kb_type={kb_type} but no tags")

        for tag in fm.get("tags", []):
            if not tag or tag in ("[]", "{}"):
                continue
            if ":" not in tag:
                errors.append(f"{rel}: tag must use prefix:value form '{tag}'")
                continue
            if not any(tag.startswith(p) for p in ALLOWED_TAG_PREFIXES):
                errors.append(f"{rel}: invalid tag prefix '{tag}'")
            tag_registry.setdefault(tag, []).append(str(rel))

        for key in ("related_concepts", "related_modules", "related_cases"):
            for link in fm.get(key, []):
                target = resolve_link(md, link, kb_root)
                if target is None:
                    if link and not link.startswith("http"):
                        errors.append(f"{rel}: broken {key} link '{link}'")
                    continue
                referenced_from_fm.add(target)
                if not target.is_file():
                    errors.append(f"{rel}: missing file for {key}: {link}")

        for m in re.finditer(r"\]\((\.\./concepts/[^)]+)\)", text):
            target = resolve_link(md, m.group(1), kb_root)
            if target and target.is_file():
                referenced_from_fm.add(target)

    index = kb_root / "concepts" / "index.md"
    if index.is_file():
        index_text = index.read_text(encoding="utf-8")
        for c in concept_files:
            if c.name not in index_text:
                warnings.append(f"concepts/index.md: no table row for {c.name}")

    orphan_concepts = concept_files - referenced_from_fm
    for c in sorted(orphan_concepts):
        warnings.append(f"{c.relative_to(kb_root)}: not in any related_concepts (orphan concept)")

    print("=== Knowledge graph check ===")
    print(f"Root: {kb_root} (strict={strict})")
    print(f"Concept pages: {len(concept_files)}")
    print(f"Module pages: {len(module_files)}")
    print(f"Unique tags: {len(tag_registry)}")

    if warnings:
        print("\n--- Warnings ---")
        for w in warnings:
            print(f"  WARN: {w}")

    if errors:
        print("\n--- Errors ---")
        for e in errors:
            print(f"  ERR: {e}")
        print(f"\nFAILED ({len(errors)} error(s))")
        return 1

    print("\nOK (no errors)")
    if warnings:
        print(f"({len(warnings)} warning(s))")
    return 0


def run_print_tags(kb_root: Path) -> int:
    by_prefix: dict[str, list[str]] = {}
    for md in collect_md_files(kb_root):
        fm = extract_frontmatter(md.read_text(encoding="utf-8"))
        if not fm:
            continue
        rel = str(md.relative_to(kb_root))
        for tag in fm.get("tags", []):
            if not tag or ":" not in tag:
                continue
            prefix = tag.split(":", 1)[0] + ":"
            by_prefix.setdefault(prefix, []).append(f"{tag}  ({rel})")

    print("=== Tags by prefix ===")
    for prefix in sorted(by_prefix):
        print(f"\n[{prefix}]")
        for line in sorted(set(by_prefix[prefix])):
            print(f"  {line}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="UE knowledge graph validator")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors where applicable")
    parser.add_argument("--print-tags", action="store_true")
    parser.add_argument("--inventory", action="store_true", help="Write compliance matrix + inventory.generated.json")
    args = parser.parse_args()

    repo = find_repo_root(Path.cwd())
    kb_root = args.root
    if kb_root is None:
        cfg = repo / ".ue-py-config.json"
        if cfg.is_file():
            import json as _json
            data = _json.loads(cfg.read_text(encoding="utf-8"))
            kb_rel = data.get("knowledge_base", "docs/ue-agent-knowledge/knowledge-base.md")
            kb_root = repo / Path(kb_rel).parent
        else:
            kb_root = repo / "docs" / "ue-agent-knowledge"

    kb_root = kb_root.resolve()
    if not kb_root.is_dir():
        print(f"ERROR: knowledge root not found: {kb_root}", file=sys.stderr)
        return 2

    if args.inventory:
        return run_inventory(kb_root)
    if args.print_tags:
        return run_print_tags(kb_root)
    return run_check(kb_root, strict=args.strict or args.check)


if __name__ == "__main__":
    sys.exit(main())
