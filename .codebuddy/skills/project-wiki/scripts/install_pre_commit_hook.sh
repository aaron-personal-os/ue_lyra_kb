#!/usr/bin/env bash
# install_pre_commit_hook.sh —— 把 pre-commit-template.sh 装到 .git/hooks/pre-commit
# 适用于 macOS / Linux（Windows 请用 install_pre_commit_hook.bat）
#
# 用法（在项目根或脚本所在目录均可）：
#   ./install_pre_commit_hook.sh
#   ./install_pre_commit_hook.sh --uninstall   # 移除已安装的 hook
#
# 安装策略：
#   - .git/hooks/pre-commit 不存在 → 直接复制 template
#   - 已存在但是本脚本装的（识别 marker 行）→ 用新 template 覆盖
#   - 已存在且不是本脚本装的（用户自己写的）→ 报错并提示手动合并

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
TEMPLATE="$SCRIPT_DIR/pre-commit-template.sh"
HOOK="$PROJECT_ROOT/.git/hooks/pre-commit"
MARKER="wiki_lint.py --check"   # 识别"是本脚本装的 hook"(template 内必含此串)
VERSION_KEY="# HOOK_VERSION:"      # ★v0.5★ 每个 template 携带版本号,用于检测老版本

# 从给定文件提取 HOOK_VERSION,无则返回 "pre-r21" (老版本约定)
extract_version() {
    grep -E "^${VERSION_KEY}" "$1" 2>/dev/null | sed -E "s/^${VERSION_KEY} *([^ ]+).*/\1/" | head -1
}

if [ ! -d "$PROJECT_ROOT/.git" ]; then
    echo "[error] 未找到 .git/ 目录: $PROJECT_ROOT" >&2
    exit 2
fi

if [ "${1:-}" = "--uninstall" ]; then
    if [ ! -f "$HOOK" ]; then
        echo "[install] 没有 pre-commit hook,无需移除"
        exit 0
    fi
    if grep -q "$MARKER" "$HOOK"; then
        rm -f "$HOOK"
        echo "[install] 已移除 pre-commit hook: $HOOK"
        exit 0
    else
        echo "[error] $HOOK 不是本脚本装的(找不到 marker '$MARKER'),不会动它" >&2
        exit 2
    fi
fi

# ★v0.5★ --check-version: 仅检查不安装,给 lint_wiki.sh / 其他工具调用
if [ "${1:-}" = "--check-version" ]; then
    if [ ! -f "$HOOK" ]; then
        echo "uninstalled"
        exit 0
    fi
    if ! grep -q "$MARKER" "$HOOK"; then
        echo "foreign"
        exit 0
    fi
    installed_ver=$(extract_version "$HOOK")
    template_ver=$(extract_version "$TEMPLATE")
    if [ "$installed_ver" = "$template_ver" ]; then
        echo "current ($installed_ver)"
        exit 0
    fi
    echo "outdated (installed: ${installed_ver:-pre-r21}, latest: $template_ver)"
    exit 0
fi

if [ ! -f "$TEMPLATE" ]; then
    echo "[error] template 不存在: $TEMPLATE" >&2
    exit 2
fi

if [ -f "$HOOK" ]; then
    if grep -q "$MARKER" "$HOOK"; then
        installed_ver=$(extract_version "$HOOK")
        template_ver=$(extract_version "$TEMPLATE")
        if [ "$installed_ver" = "$template_ver" ]; then
            echo "[install] hook 已是最新版本 ($template_ver),无需更新"
            exit 0
        fi
        echo "[install] 检测到旧版 pre-commit hook (${installed_ver:-pre-r21} → $template_ver),覆盖更新"
    else
        echo "[error] $HOOK 已存在且不是本脚本装的" >&2
        echo "        请手动合并;或先备份后跑 ./install_pre_commit_hook.sh --uninstall" >&2
        exit 2
    fi
fi

cp "$TEMPLATE" "$HOOK"
chmod +x "$HOOK"
template_ver=$(extract_version "$TEMPLATE")
echo "[install] ✓ 已安装 pre-commit hook ($template_ver) → $HOOK"
echo "[install]   下次 git commit 会自动跑 wiki_lint --update-cache + --check"
echo "[install]   ★v0.5★ opt-in autofix: WIKI_LINT_AUTOFIX_ASYMM=1 git commit ..."
echo "[install]   想跳过单次:git commit --no-verify"
echo "[install]   想卸载:./install_pre_commit_hook.sh --uninstall"
echo "[install]   想检查版本:./install_pre_commit_hook.sh --check-version"
