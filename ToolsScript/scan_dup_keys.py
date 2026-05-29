"""Scan all tutorial .md files for duplicate YAML frontmatter keys."""
import os, re
from pathlib import Path

root = Path(__file__).resolve().parent.parent / "Docs" / "30-tutorials"
found = False
for md in sorted(root.rglob("*.md")):
    content = md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        continue
    end = content.find("\n---", 3)
    if end == -1:
        continue
    fm = content[3:end]
    keys = re.findall(r"^(\w[\w_-]*):", fm, re.MULTILINE)
    seen = set()
    for k in keys:
        if k in seen:
            print(f"{md.relative_to(root.parent.parent)}: duplicate key '{k}'")
            found = True
        seen.add(k)

if not found:
    print("No duplicate keys found.")
