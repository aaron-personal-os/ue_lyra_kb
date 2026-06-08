#!/usr/bin/env python
"""
Thin forwarder — delegates to MyRoguelikeGame ue_python.py (single source of truth).

Do not add Remote Execution logic here. Set MR_PROJECT_ROOT or use a sibling
MyRoguelikeGame checkout; otherwise this script exits 2 with a clear message.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _find_mr_root() -> Path | None:
    env = os.environ.get('MR_PROJECT_ROOT', '').strip()
    if env:
        candidate = Path(env)
        if (candidate / '.ue-py-config.json').is_file():
            return candidate
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        for name in ('MyRoguelikeGame',):
            for base in (parent, parent.parent):
                candidate = base / name
                if (candidate / '.ue-py-config.json').is_file():
                    return candidate
    return None


def main() -> int:
    mr_root = _find_mr_root()
    if not mr_root:
        print(
            'Error: MyRoguelikeGame project root not found.\n'
            '  Set MR_PROJECT_ROOT to the folder containing .ue-py-config.json\n'
            '  or run ue_python.py from MyRoguelikeGame/.cursor/skills/ue-py-run/scripts/\n'
            '  Do not maintain a separate Remote Execution implementation in ue_lyra_kb.',
            file=sys.stderr,
        )
        return 2

    delegate = mr_root / '.cursor' / 'skills' / 'ue-py-run' / 'scripts' / 'ue_python.py'
    if not delegate.is_file():
        print(f'Error: delegate missing at {delegate}', file=sys.stderr)
        return 2

    result = subprocess.run([sys.executable, str(delegate), *sys.argv[1:]])
    return int(result.returncode)


if __name__ == '__main__':
    sys.exit(main())
