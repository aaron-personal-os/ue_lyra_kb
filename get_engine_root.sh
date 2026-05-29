#!/usr/bin/env bash
# get_engine_root.sh
# ------------------------------------------------------------------
# 解析 .uproject 的 EngineAssociation，得到 UE 引擎根目录。
# 平台：macOS / Linux。
#
# EngineAssociation 形式 -> 数据源：
#   - GUID（"{A20C...}"）   -> ~/Library/Application Support/Epic/UnrealEngine/Install.ini  (macOS)
#                              ~/.config/Epic/UnrealEngine/Install.ini                       (Linux)
#                              [Installations] 段，键名为 GUID（去掉花括号），值为路径
#   - 版本号（"5.7"）       -> EpicGamesLauncher 在 macOS/Linux 没有标准注册表机制，
#                              通常源码版本才以 GUID 形式注册；如遇版本号请手动指定 -e
#
# 用法：
#   ./get_engine_root.sh                          # 自动定位 .uproject，人类可读输出
#   ./get_engine_root.sh --json                   # JSON 输出（AI 调用推荐）
#   ./get_engine_root.sh -p /path/to/Foo.uproject # 指定 .uproject
#   ./get_engine_root.sh -e /path/to/UnrealEngine # 强制指定引擎根目录（跳过查表）
# ------------------------------------------------------------------
set -euo pipefail

UPROJECT=""
ENGINE_OVERRIDE=""
JSON=0

# ---- 解析参数 ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--uproject) UPROJECT="$2"; shift 2 ;;
        -e|--engine)   ENGINE_OVERRIDE="$2"; shift 2 ;;
        --json)        JSON=1; shift ;;
        -h|--help)
            sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "未知参数: $1" >&2; exit 2 ;;
    esac
done

fail() {
    local msg="$1"
    if [[ "$JSON" -eq 1 ]]; then
        printf '{"ok":false,"error":%s}\n' "$(printf '%s' "$msg" | _json_escape)"
    else
        echo "ERROR: $msg" >&2
    fi
    exit 1
}

_json_escape() {
    # 极简 JSON 字符串转义（足够路径/错误信息使用）
    python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))' 2>/dev/null \
        || sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/^/"/' -e 's/$/"/'
}

# ---- 1. 定位 .uproject ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "$UPROJECT" ]]; then
    UPROJECT="$(find "$SCRIPT_DIR" -maxdepth 1 -name '*.uproject' -type f | head -n 1 || true)"
    [[ -z "$UPROJECT" ]] && fail "未在脚本目录找到 .uproject，请用 -p 指定。"
fi
[[ ! -f "$UPROJECT" ]] && fail ".uproject 不存在: $UPROJECT"

# ---- 2. 读取 EngineAssociation ----
_read_assoc() {
    if command -v python3 >/dev/null 2>&1; then
        python3 -c '
import json,sys
with open(sys.argv[1]) as f:
    data = json.load(f)
print(data.get("EngineAssociation",""))
' "$UPROJECT"
    elif command -v jq >/dev/null 2>&1; then
        jq -r '.EngineAssociation // ""' "$UPROJECT"
    else
        # 兜底正则（不严谨，但绝大多数 .uproject 可用）
        grep -oE '"EngineAssociation"[[:space:]]*:[[:space:]]*"[^"]*"' "$UPROJECT" \
            | sed -E 's/.*"EngineAssociation"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/'
    fi
}

ASSOC="$(_read_assoc)"
[[ -z "$ASSOC" ]] && fail ".uproject 中 EngineAssociation 为空。"

# ---- 3. 解析引擎根目录 ----
ENGINE_ROOT=""
ASSOC_TYPE=""

if [[ -n "$ENGINE_OVERRIDE" ]]; then
    ENGINE_ROOT="$ENGINE_OVERRIDE"
    ASSOC_TYPE="override"
elif [[ "$ASSOC" =~ ^\{[0-9A-Fa-f-]+\}$ ]]; then
    # GUID 形式 -> 查 Install.ini
    ASSOC_TYPE="source-build"
    if [[ "$(uname)" == "Darwin" ]]; then
        INSTALL_INI="$HOME/Library/Application Support/Epic/UnrealEngine/Install.ini"
    else
        INSTALL_INI="$HOME/.config/Epic/UnrealEngine/Install.ini"
    fi
    [[ ! -f "$INSTALL_INI" ]] && fail "未找到 Install.ini: $INSTALL_INI"

    # 去掉花括号后用作查找键
    KEY="${ASSOC#\{}"; KEY="${KEY%\}}"
    # Install.ini 的 [Installations] 段以 GUID（无花括号）为键
    ENGINE_ROOT="$(awk -v k="$KEY" '
        /^\[Installations\]/ {in_sec=1; next}
        /^\[/ {in_sec=0}
        in_sec && tolower($0) ~ tolower("^"k"=") {
            sub(/^[^=]*=/,""); print; exit
        }
    ' "$INSTALL_INI")"

    [[ -z "$ENGINE_ROOT" ]] && fail "Install.ini 中未找到 GUID $ASSOC 对应路径。"
else
    # 版本号 -> macOS/Linux 一般无固定注册位置
    ASSOC_TYPE="installed"
    fail "EngineAssociation=\"$ASSOC\" 是版本号，macOS/Linux 无标准注册位置。请用 -e <engine-root> 指定。"
fi

# 去掉末尾斜杠
ENGINE_ROOT="${ENGINE_ROOT%/}"
ENGINE_ROOT="${ENGINE_ROOT%\\}"

ENGINE_SOURCE="$ENGINE_ROOT/Engine/Source"
ENGINE_PLUGINS="$ENGINE_ROOT/Engine/Plugins"

# ---- 4. 输出 ----
if [[ "$JSON" -eq 1 ]]; then
    cat <<EOF
{
  "ok": true,
  "uproject": "$UPROJECT",
  "engineAssociation": "$ASSOC",
  "associationType": "$ASSOC_TYPE",
  "engineRoot": "$ENGINE_ROOT",
  "engineSource": "$ENGINE_SOURCE",
  "enginePlugins": "$ENGINE_PLUGINS"
}
EOF
else
    cat <<EOF
EngineAssociation : $ASSOC
Association Type  : $ASSOC_TYPE
Engine Root       : $ENGINE_ROOT
Engine Source     : $ENGINE_SOURCE
Engine Plugins    : $ENGINE_PLUGINS
EOF
fi
