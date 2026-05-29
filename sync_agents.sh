#!/usr/bin/env bash
# 一键执行 sync_agent_config.py —— 把 .codebuddy 的 Agent 配置软链给
# ClaudeCode / Codex / Cursor。适用于 macOS / Linux（Windows 请用 sync_agents.bat）。
#
# 用法（在项目根目录下执行）：
#   ./sync_agents.sh                    # 默认执行，内置 excludes
#   ./sync_agents.sh --targets claude,codex
#   ./sync_agents.sh -e 'skills/private-*'
#   ./sync_agents.sh --dry-run
#   ./sync_agents.sh --force
#   ./sync_agents.sh --unlink
#
# 环境变量：
#   PYTHON=python3.12  ./sync_agents.sh   # 指定 python 可执行文件

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

PY_BIN="${PYTHON:-python3}"
if ! command -v "$PY_BIN" >/dev/null 2>&1; then
    echo "[error] 找不到 python 可执行文件 '$PY_BIN'，请先安装 Python 3.9+ 或设置 PYTHON 环境变量" >&2
    exit 127
fi

# 当前脚本无第三方依赖，纯标准库即可运行；不强制建 venv。
exec "$PY_BIN" "$PROJECT_ROOT/ToolsScript/misc_tools/sync_agent_config.py" --project-root "$PROJECT_ROOT" "$@"
