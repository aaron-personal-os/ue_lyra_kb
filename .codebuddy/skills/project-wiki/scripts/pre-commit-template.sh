#!/usr/bin/env bash
# pre-commit hook —— wiki_lint.py --check + fix_asymm.py 集成版 (R21)
# 由 install_pre_commit_hook.sh 安装到 .git/hooks/pre-commit
#
# HOOK_VERSION: r21  (auto-detect by install script for upgrade prompts)
# HOOK_MARKER: wiki_lint.py --check (used by install script to verify ownership)
#
# 退出码：0 通过 / >0 拦截
#
# 工作流：
#   1. 触发判断：本次 staging 是否含 Docs/**/*.md 或 Source/Variant_*/**.{cpp,h}？
#      - 否 → 跳过（节省时间）
#      - 是 → 进入下面三步
#   2. ★v0.4★ 跑 wiki_lint --update-cache：让 anchor sha256 cache 跟当前
#      工作树同步。如果 cache 文件变了，自动 git add 进本次 commit。
#   3. ★v0.5★ 可选 fix_asymm autofix：
#      - 默认行为：跑 lint，如果有 asymm-link 提示用户跑 fix_asymm
#      - opt-in：设 WIKI_LINT_AUTOFIX_ASYMM=1 → 自动跑 fix_asymm --apply 并 stage
#      - 安全：fix_asymm 只 append 到 related，不删；R18+R19 实战零意外
#   4. 跑 wiki_lint --check（仅 ERROR）：拦截硬约束违反
#
# 想跳过单次：git commit --no-verify
# 想 opt-in autofix：WIKI_LINT_AUTOFIX_ASYMM=1 git commit -m "..."

set -e

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$HOOK_DIR/../.." && pwd)"

CHANGED=$(git diff --cached --name-only --diff-filter=ACMR \
    | grep -E '^(Docs/.*\.md$|Source/ue_ai_demo/Variant_.*\.(cpp|h)$)' || true)

if [ -z "$CHANGED" ]; then
    exit 0
fi

# Find Python: PYTHON env > python > python3 > py -3 > .venv (last resort).
# Notes:
#  - wiki_lint.py is pure stdlib so any Python 3.9+ works; no need for venv deps
#  - python3.exe on Windows is often MS Store stub that silently exits (R13);
#    so we try `python` first; verify each candidate with --version before use
#  - .venv last-resort because (a) it's a Windows .exe path that fails on WSL bash
#    and (b) git for windows bash usually has system Python on PATH already
find_python() {
    if [ -n "${PYTHON:-}" ]; then echo "$PYTHON"; return; fi
    if command -v python >/dev/null 2>&1 && python --version >/dev/null 2>&1; then
        echo "python"; return
    fi
    if command -v python3 >/dev/null 2>&1 && python3 --version >/dev/null 2>&1; then
        echo "python3"; return
    fi
    if command -v py >/dev/null 2>&1 && py -3 --version >/dev/null 2>&1; then
        echo "py -3"; return
    fi
    local venv_py="$PROJECT_ROOT/Content/Python/.venv/bin/python"
    if [ -f "$venv_py" ]; then echo "$venv_py"; return; fi
    venv_py="$PROJECT_ROOT/Content/Python/.venv/Scripts/python.exe"
    if [ -f "$venv_py" ]; then echo "$venv_py"; return; fi
    echo ""
}
PY_BIN=$(find_python)
if [ -z "$PY_BIN" ]; then
    echo "[pre-commit] [error] 找不到 python (尝试过 PYTHON env / .venv / python3 / python / py)" >&2
    exit 127
fi
LINT="$PROJECT_ROOT/.codebuddy/skills/project-wiki/scripts/wiki_lint.py"
FIX_ASYMM="$PROJECT_ROOT/.codebuddy/skills/project-wiki/scripts/fix_asymm.py"
CACHE_REL=".codebuddy/skills/project-wiki/.cache/anchors.json"
CACHE_ABS="$PROJECT_ROOT/$CACHE_REL"

# ★v0.4★ Step 2: update-cache 自动同步 + auto-stage
echo "[pre-commit] syncing anchor sha256 cache..."
"$PY_BIN" "$LINT" --project-root "$PROJECT_ROOT" --update-cache > /dev/null 2>&1 || true
if [ -f "$CACHE_ABS" ]; then
    cd "$PROJECT_ROOT"
    if ! git diff --quiet -- "$CACHE_REL" 2>/dev/null; then
        git add "$CACHE_REL"
        echo "[pre-commit] anchor cache 自动同步并加入本次 commit ($CACHE_REL)"
    fi
fi

# ★v0.5★ Step 3: opt-in fix_asymm autofix
if [ -n "$WIKI_LINT_AUTOFIX_ASYMM" ] && [ -f "$FIX_ASYMM" ]; then
    echo "[pre-commit] WIKI_LINT_AUTOFIX_ASYMM=1 -> running fix_asymm --apply..."
    cd "$PROJECT_ROOT"
    autofix_out=$("$PY_BIN" "$FIX_ASYMM" --project-root "$PROJECT_ROOT" --apply 2>&1 || true)
    added=$(echo "$autofix_out" | grep -E "共计追加 [0-9]+ 条" | grep -oE "[0-9]+" | head -1 || echo "0")
    if [ "${added:-0}" != "0" ]; then
        echo "[pre-commit] fix_asymm 自动补 $added 条 related，stage 受影响的 Docs/*.md"
        git diff --name-only -- 'Docs/*.md' | xargs -r git add
    fi
fi

# Step 4: lint --check 拦截 ERROR
echo "[pre-commit] running wiki_lint --check..."
set +e
"$PY_BIN" "$LINT" --project-root "$PROJECT_ROOT" --check
RC=$?
set -e

if [ $RC -ne 0 ]; then
    echo ""
    echo "[pre-commit] ✗ wiki_lint 拦截了本次 commit (exit=$RC)"
    # ★v0.5★ 给 asymm-link 用户友好提示（即使没 opt-in autofix 也建议跑）
    asymm_count=$("$PY_BIN" "$LINT" --project-root "$PROJECT_ROOT" --json 2>/dev/null | "$PY_BIN" -c "import json, sys; d = json.load(sys.stdin); issues = d.get('issues', d) if isinstance(d, dict) else d; print(sum(1 for i in issues if i.get('code') == 'asymm-link'))" 2>/dev/null || echo "0")
    if [ "${asymm_count:-0}" != "0" ]; then
        echo "[pre-commit]   提示: 有 $asymm_count 个 asymm-link，可一键修复："
        echo "[pre-commit]     $PY_BIN .codebuddy/skills/project-wiki/scripts/fix_asymm.py --apply"
        echo "[pre-commit]   或 opt-in 自动模式：WIKI_LINT_AUTOFIX_ASYMM=1 git commit ..."
    fi
    echo "[pre-commit]   修复后重 commit；或 'git commit --no-verify' 强制跳过（不推荐）"
    echo "[pre-commit]   完整报告：./lint_wiki.sh"
    exit $RC
fi

echo "[pre-commit] ✓ wiki_lint 通过"
exit 0
