"""
Mermaid syntax checker & auto-fixer for Markdown files.

Scans all .md files under a target directory, extracts ```mermaid blocks,
validates them using the mermaid-js CLI (mmdc), and auto-fixes common issues:
  1. Node labels with unquoted parentheses: A[Foo()] -> A["Foo()"]
  2. Node labels with unquoted braces inside square brackets

Usage:
  python ToolsScript/check_mermaid.py                          # Check only
  python ToolsScript/check_mermaid.py --fix                    # Auto-fix & recheck
  python ToolsScript/check_mermaid.py --dir path/to/folder     # Custom directory
  python ToolsScript/check_mermaid.py --fix --dry-run          # Show fixes without writing

Requirements:
  - Node.js installed (for mmdc validation, optional)
  - pip install no external deps (pure Python for fix logic)

If mmdc (@mermaid-js/mermaid-cli) is not installed, the script will only
apply regex-based fixes and skip runtime validation.
"""

import os
import re
import sys
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_DIR = os.path.join(os.path.dirname(__file__), '..', 'Docs', '30-tutorials')

# ---------------------------------------------------------------------------
# Mermaid block extraction
# ---------------------------------------------------------------------------
MERMAID_FENCE_RE = re.compile(
    r'^```mermaid\s*\n(.*?)\n```',
    re.MULTILINE | re.DOTALL
)


def extract_mermaid_blocks(content: str) -> List[Tuple[int, int, str]]:
    """Return list of (start_pos, end_pos, mermaid_source) from markdown content."""
    blocks = []
    for m in MERMAID_FENCE_RE.finditer(content):
        blocks.append((m.start(), m.end(), m.group(1)))
    return blocks


# ---------------------------------------------------------------------------
# Auto-fix logic
# ---------------------------------------------------------------------------

def fix_unquoted_parens_in_labels(src: str) -> str:
    """
    Fix node labels inside [] that contain unquoted parentheses.
    A[PreInit()] --> A["PreInit()"]
    
    Also handles labels with content after parens like A[Foo(bar)Baz]
    """
    def replace_label(match):
        prefix = match.group(1)  # e.g. "A" or "    A"
        node_id = match.group(2)  # e.g. "A"
        label = match.group(3)    # e.g. "PreInit()"
        # Already quoted
        if label.startswith('"') or label.startswith("'"):
            return match.group(0)
        # Contains parens - needs quoting
        escaped = label.replace('"', '#quot;')
        return f'{prefix}["{escaped}"]'
    
    # Match: NodeId[...text containing parens...]
    # But NOT already quoted, and NOT in comments or style lines
    lines = src.split('\n')
    out_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip comment lines, style directives, classDef, etc.
        if stripped.startswith('%%') or stripped.startswith('style ') or \
           stripped.startswith('linkStyle ') or stripped.startswith('classDef '):
            out_lines.append(line)
            continue
        
        # Fix pattern: word[...(...)]  but not word["..."]
        # This regex finds NodeId[label] where label contains ( but is not quoted
        fixed = re.sub(
            r'(\b\w+)\[([^\]"]*\([^\]]*)\]',
            lambda m: _fix_single_bracket_label(m),
            line
        )
        out_lines.append(fixed)
    
    return '\n'.join(out_lines)


def _fix_single_bracket_label(m) -> str:
    """Fix a single [...] match that contains parentheses."""
    node_id = m.group(1)
    label = m.group(2)
    # Don't fix if already quoted
    if label.startswith('"') or label.startswith("'"):
        return m.group(0)
    # Escape internal double quotes
    escaped = label.replace('"', '#quot;')
    return f'{node_id}["{escaped}"]'


def fix_unquoted_parens_in_parens_nodes(src: str) -> str:
    """
    Fix node labels inside () that contain problematic nested parens.
    e.g. A(Foo()) -> A("Foo()")
    This is trickier because () is itself a shape delimiter.
    Only fix if there are nested parens that break parsing.
    
    SKIP: mindmap root((text)) is valid syntax (double-paren = circle shape).
    SKIP: sequence diagram loop/alt/opt content is not a node definition.
    """
    # Detect diagram type from first line
    first_line = src.strip().split('\n')[0].strip().lower()
    # Skip mindmap and sequence diagrams entirely for paren-node checks
    if first_line.startswith('mindmap') or first_line.startswith('sequencediagram'):
        return src
    
    lines = src.split('\n')
    out_lines = []
    in_loop_block = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('%%') or stripped.startswith('style ') or \
           stripped.startswith('linkStyle ') or stripped.startswith('classDef '):
            out_lines.append(line)
            continue
        
        # Track loop/alt/opt blocks in sequence diagrams (these are labels, not nodes)
        lower_stripped = stripped.lower()
        if lower_stripped.startswith('loop ') or lower_stripped.startswith('alt ') or \
           lower_stripped.startswith('opt ') or lower_stripped.startswith('rect '):
            out_lines.append(line)
            continue
        
        # Skip lines that are clearly not node definitions
        # (participant declarations, notes, messages with ->>)
        if '->>' in stripped or '->' in stripped and '(' not in stripped.split('->')[0]:
            out_lines.append(line)
            continue
        
        # Pattern: NodeId(label with nested parens)
        # Match word followed by (...(...) ...) - nested parens
        fixed = re.sub(
            r'(\b\w+)\(([^)"]*\([^)]*\)[^)"]*)\)',
            lambda m: _fix_single_paren_label(m),
            line
        )
        out_lines.append(fixed)
    
    return '\n'.join(out_lines)


def _fix_single_paren_label(m) -> str:
    """Fix a single (...) node match that contains nested parentheses."""
    node_id = m.group(1)
    label = m.group(2)
    
    # Skip known Mermaid keywords that use parens
    keywords = {'subgraph', 'end', 'click', 'class', 'style', 'linkStyle',
                'classDef', 'direction', 'participant', 'actor', 'note',
                'root', 'loop', 'alt', 'opt', 'rect', 'par', 'critical',
                'break', 'activate', 'deactivate', 'while'}
    if node_id.lower() in keywords:
        return m.group(0)
    
    # Skip if it looks like an arrow definition e.g. -->
    if '--' in label or '==' in label:
        return m.group(0)
    
    # Skip root((...)) which is valid mindmap/flowchart double-paren syntax
    if node_id.lower() == 'root' and label.startswith('('):
        return m.group(0)
    
    escaped = label.replace('"', '#quot;')
    return f'{node_id}("{escaped}")'


def apply_fixes(src: str) -> str:
    """Apply all auto-fix passes to mermaid source."""
    result = fix_unquoted_parens_in_labels(src)
    result = fix_unquoted_parens_in_parens_nodes(result)
    result = fix_colon_labels_in_flowchart(result)
    result = fix_edge_label_parens(result)
    return result


def fix_colon_labels_in_flowchart(src: str) -> str:
    """
    Fix `: label` syntax in graph/flowchart diagrams.
    e.g. A --> B : Creates  ->  A -->|Creates| B
    This syntax is only valid in classDiagram, not in graph/flowchart.
    """
    first_line = src.strip().split('\n')[0].strip().lower()
    if not (first_line.startswith('graph') or first_line.startswith('flowchart')):
        return src
    
    lines = src.split('\n')
    out_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip non-edge lines
        if stripped.startswith('%%') or stripped.startswith('style ') or \
           stripped.startswith('linkStyle ') or stripped.startswith('classDef ') or \
           stripped.startswith('subgraph') or not stripped:
            out_lines.append(line)
            continue
        
        # Pattern: NodeA -->/--> NodeB : Label
        # Replace with: NodeA -->|Label| NodeB
        fixed = re.sub(
            r'(\b\w+)\s*(--[->]+)\s*(\w+)\s+:\s+(.+?)$',
            lambda m: f'{m.group(1)} {m.group(2)}|{m.group(4).strip()}| {m.group(3)}',
            line
        )
        out_lines.append(fixed)
    
    return '\n'.join(out_lines)


def fix_edge_label_parens(src: str) -> str:
    """
    Fix unquoted parentheses in edge labels.
    e.g. -->|Notify()| -> -->|"Notify()"|
    """
    first_line = src.strip().split('\n')[0].strip().lower()
    if not (first_line.startswith('graph') or first_line.startswith('flowchart')):
        return src
    
    lines = src.split('\n')
    out_lines = []
    for line in lines:
        # Find edge labels with parens: |...(...)| where content not already quoted
        fixed = re.sub(
            r'\|([^|"]*\([^|]*)\|',
            lambda m: m.group(0) if m.group(1).startswith('"') or m.group(1).startswith("'")
            else f'|"{m.group(1)}"|',
            line
        )
        out_lines.append(fixed)
    
    return '\n'.join(out_lines)


# ---------------------------------------------------------------------------
# mmdc validation (optional)
# ---------------------------------------------------------------------------

def find_mmdc() -> Optional[str]:
    """Find mmdc executable."""
    # Try npx
    try:
        result = subprocess.run(
            ['npx', '--yes', '@mermaid-js/mermaid-cli', '--version'],
            capture_output=True, text=True, timeout=30,
            shell=(os.name == 'nt')
        )
        if result.returncode == 0:
            return 'npx_mmdc'
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Try direct mmdc
    try:
        result = subprocess.run(
            ['mmdc', '--version'],
            capture_output=True, text=True, timeout=10,
            shell=(os.name == 'nt')
        )
        if result.returncode == 0:
            return 'mmdc'
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return None


def validate_with_mmdc(src: str, mmdc_cmd: str) -> Optional[str]:
    """Validate mermaid source using mmdc. Returns error message or None."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False, encoding='utf-8') as f:
        f.write(src)
        tmp_input = f.name
    
    tmp_output = tmp_input + '.svg'
    
    try:
        if mmdc_cmd == 'npx_mmdc':
            cmd = ['npx', '--yes', '@mermaid-js/mermaid-cli', '-i', tmp_input, '-o', tmp_output]
        else:
            cmd = ['mmdc', '-i', tmp_input, '-o', tmp_output]
        
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            shell=(os.name == 'nt')
        )
        
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            return error if error else "Unknown error (non-zero exit)"
        return None
    except subprocess.TimeoutExpired:
        return "Validation timed out"
    except Exception as e:
        return f"Validation error: {e}"
    finally:
        try:
            os.unlink(tmp_input)
        except OSError:
            pass
        try:
            os.unlink(tmp_output)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Static analysis (no mmdc needed)
# ---------------------------------------------------------------------------

def static_check(src: str) -> List[str]:
    """
    Perform static regex-based checks on mermaid source.
    Returns list of warning/error messages.
    """
    issues = []
    lines = src.split('\n')
    
    # Detect diagram type
    first_line = src.strip().split('\n')[0].strip().lower() if src.strip() else ''
    is_mindmap = first_line.startswith('mindmap')
    is_sequence = first_line.startswith('sequencediagram')
    is_flowchart = first_line.startswith('graph') or first_line.startswith('flowchart')
    
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        
        # Skip non-node lines
        if stripped.startswith('%%') or stripped.startswith('style ') or \
           stripped.startswith('linkStyle ') or stripped.startswith('classDef ') or \
           stripped.startswith('class ') or not stripped:
            continue
        
        # Skip loop/alt/opt labels in sequence diagrams
        lower_stripped = stripped.lower()
        if lower_stripped.startswith('loop ') or lower_stripped.startswith('alt ') or \
           lower_stripped.startswith('opt ') or lower_stripped.startswith('rect ') or \
           lower_stripped.startswith('par ') or lower_stripped.startswith('critical '):
            continue
        
        # Check for unquoted parens in edge labels: -->|Foo()| 
        if is_flowchart:
            edge_label_matches = re.finditer(r'\|([^|"]*\([^|]*)\|', line)
            for m in edge_label_matches:
                label = m.group(1)
                if not label.startswith('"') and not label.startswith("'"):
                    if '(' in label:
                        issues.append(
                            f"  Line {i}: Unquoted () in edge label: |{label}|"
                            f' -> fix: use |"{label}"|'
                        )
        
        # Check for `: label` syntax in flowchart/graph (only valid in classDiagram)
        if is_flowchart:
            # Pattern: NodeA --> NodeB : Label (colon-space after target node)
            colon_label = re.search(r'(\w+)\s*--[->|.]+\s*(\w+)\s+:\s+\w+', stripped)
            if colon_label:
                issues.append(
                    f"  Line {i}: Colon label syntax in flowchart: '{stripped.strip()}'"
                    f" -> fix: use -->|label| syntax instead of ' : label'"
                )
        
        # Check for malformed edge label: --> X|Yes| Y (missing arrow before |label|)
        if is_flowchart:
            bad_edge = re.search(r'--[->]+\s+\w+\|[^|]+\|\s+\w+', stripped)
            if bad_edge:
                issues.append(
                    f"  Line {i}: Malformed edge label: '{bad_edge.group(0)}'"
                    f" -> fix: use -->|label| NodeId (no intermediate node)"
                )
        
        # Check for unquoted parens in square bracket labels (flowchart/graph)
        # Pattern: word[...(...)] where content is NOT quoted
        bracket_matches = re.finditer(r'\b\w+\[([^\]"]*\([^\]]*)\]', line)
        for m in bracket_matches:
            label = m.group(1)
            if not label.startswith('"') and not label.startswith("'"):
                issues.append(
                    f"  Line {i}: Unquoted () in [...] label: {m.group(0)}"
                    f" -> fix: use [\"{label}\"]"
                )
        
        # Check for unquoted nested parens in round bracket nodes
        # Skip mindmap (root((...)) is valid) and sequence diagrams
        if not is_mindmap and not is_sequence:
            paren_matches = re.finditer(r'\b(\w+)\(([^)"]*\([^)]*\)[^)"]*)\)', line)
            for m in paren_matches:
                node_id = m.group(1)
                full_match = m.group(0)
                keywords = {'subgraph', 'end', 'click', 'class', 'style',
                           'linkStyle', 'classDef', 'direction', 'participant',
                           'actor', 'note', 'root', 'loop', 'alt', 'opt',
                           'rect', 'par', 'critical', 'break', 'while',
                           'activate', 'deactivate'}
                if node_id.lower() not in keywords:
                    # Skip if this match is inside a quoted label ["..."]
                    match_start = m.start()
                    prefix = line[:match_start]
                    # Count unmatched [ and " before this match
                    # If we're inside ["..."], skip
                    in_quoted_bracket = False
                    for bracket_m in re.finditer(r'\w+\["[^"]*$', prefix):
                        in_quoted_bracket = True
                    if in_quoted_bracket:
                        continue
                    
                    label = m.group(2)
                    issues.append(
                        f"  Line {i}: Nested () in (...) node: {full_match}"
                        f" -> fix: use (\"{label}\")"
                    )
    
    return issues


# ---------------------------------------------------------------------------
# Main scanning logic
# ---------------------------------------------------------------------------

def scan_directory(target_dir: str, do_fix: bool = False, dry_run: bool = False,
                   use_mmdc: bool = False) -> Tuple[int, int, int]:
    """
    Scan directory for markdown files with mermaid blocks.
    Returns (total_blocks, error_blocks, fixed_blocks).
    """
    target = Path(target_dir).resolve()
    if not target.exists():
        print(f"ERROR: Directory not found: {target}")
        sys.exit(1)
    
    md_files = sorted(target.rglob('*.md'))
    
    # Find mmdc if requested
    mmdc_cmd = None
    if use_mmdc:
        print("Looking for mmdc (mermaid-cli)...")
        mmdc_cmd = find_mmdc()
        if mmdc_cmd:
            print(f"  Found: {mmdc_cmd}")
        else:
            print("  Not found. Using static analysis only.")
            print("  Install with: npm install -g @mermaid-js/mermaid-cli")
    
    total_blocks = 0
    error_blocks = 0
    fixed_blocks = 0
    files_with_errors = 0
    files_fixed = 0
    
    for md_file in md_files:
        rel_path = md_file.relative_to(target.parent.parent)
        content = md_file.read_text(encoding='utf-8')
        blocks = extract_mermaid_blocks(content)
        
        if not blocks:
            continue
        
        file_has_errors = False
        file_fixed = False
        new_content = content
        
        for start, end, src in blocks:
            total_blocks += 1
            
            # Static check
            issues = static_check(src)
            
            if issues:
                if not file_has_errors:
                    print(f"\n{'='*70}")
                    print(f"FILE: {rel_path}")
                    print(f"{'='*70}")
                    file_has_errors = True
                
                error_blocks += 1
                # Show first few lines of the block for context
                preview = '\n'.join(src.split('\n')[:3])
                print(f"\n  Block (line ~{content[:start].count(chr(10))+2}):")
                print(f"    {preview}...")
                print(f"  Issues:")
                for issue in issues:
                    print(f"    {issue}")
                
                if do_fix:
                    fixed_src = apply_fixes(src)
                    if fixed_src != src:
                        # Replace in content
                        fence_start = content.find('```mermaid', start if start == 0 else max(0, start - 5))
                        if fence_start == -1:
                            fence_start = start
                        
                        old_block = f"```mermaid\n{src}\n```"
                        new_block = f"```mermaid\n{fixed_src}\n```"
                        new_content = new_content.replace(old_block, new_block, 1)
                        
                        fixed_blocks += 1
                        file_fixed = True
                        print(f"  [FIXED] Auto-fixed {len(issues)} issue(s)")
                        
                        # Verify fix
                        remaining = static_check(fixed_src)
                        if remaining:
                            print(f"  [WARN] {len(remaining)} issue(s) remain after fix:")
                            for r in remaining:
                                print(f"    {r}")
            
            # Optional mmdc validation
            elif mmdc_cmd:
                error = validate_with_mmdc(src, mmdc_cmd)
                if error:
                    if not file_has_errors:
                        print(f"\n{'='*70}")
                        print(f"FILE: {rel_path}")
                        print(f"{'='*70}")
                        file_has_errors = True
                    
                    error_blocks += 1
                    preview = '\n'.join(src.split('\n')[:3])
                    print(f"\n  Block (line ~{content[:start].count(chr(10))+2}):")
                    print(f"    {preview}...")
                    print(f"  mmdc error: {error[:200]}")
        
        if file_has_errors:
            files_with_errors += 1
        
        if file_fixed and not dry_run:
            md_file.write_text(new_content, encoding='utf-8')
            files_fixed += 1
            print(f"  >> File saved.")
        elif file_fixed and dry_run:
            print(f"  >> [DRY-RUN] Would save file.")
    
    return total_blocks, error_blocks, fixed_blocks, files_with_errors, files_fixed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Fix Windows console encoding
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(
        description='Check and fix Mermaid syntax in Markdown files'
    )
    parser.add_argument(
        '--dir', '-d',
        default=DEFAULT_DIR,
        help='Target directory to scan (default: Docs/30-tutorials)'
    )
    parser.add_argument(
        '--fix', '-f',
        action='store_true',
        help='Auto-fix detectable issues'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show fixes without writing files (use with --fix)'
    )
    parser.add_argument(
        '--mmdc',
        action='store_true',
        help='Also validate using mmdc (mermaid-cli, requires Node.js)'
    )
    
    args = parser.parse_args()
    
    target = os.path.abspath(args.dir)
    print(f"Mermaid Syntax Checker")
    print(f"Target: {target}")
    print(f"Mode: {'FIX' if args.fix else 'CHECK'}{' (dry-run)' if args.dry_run else ''}")
    print(f"{'='*70}")
    
    total, errors, fixed, files_err, files_fixed = scan_directory(
        target,
        do_fix=args.fix,
        dry_run=args.dry_run,
        use_mmdc=args.mmdc
    )
    
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"  Total mermaid blocks scanned: {total}")
    print(f"  Blocks with issues: {errors}")
    print(f"  Files with issues: {files_err}")
    if args.fix:
        print(f"  Blocks auto-fixed: {fixed}")
        print(f"  Files saved: {files_fixed}")
        if errors > fixed:
            print(f"  Blocks needing manual fix: {errors - fixed}")
    
    if errors > 0 and not args.fix:
        print(f"\nRun with --fix to auto-fix detectable issues.")
    
    sys.exit(0 if errors == 0 else 1)


if __name__ == '__main__':
    main()
