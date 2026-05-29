#!/bin/bash
# OA Pages 一键部署脚本 (macOS/Linux)
# 用法：./deploy.sh
# 直接上传 dist/ 目录内容，无需中间拷贝

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"
TMP_FILE="$SCRIPT_DIR/_tmp_body.json"

CNAME="ue-lyra-kb.pages.woa.com"
DESCRIPTION="Lyra UE Knowledge Base"
MAX_BATCH_SIZE=3145728  # 3MB (JSON serialization adds ~30-50% overhead, server limit is 5MB)

echo "╔══════════════════════════════════════════╗"
echo "║  Lyra KB — Deploy to OA Pages            ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# === 获取 API Key ===
if [ -z "$OA_PAGES_API_KEY" ]; then
    echo "❌ OA_PAGES_API_KEY 未配置，请先设置环境变量"
    echo "   export OA_PAGES_API_KEY=your_key_here"
    exit 1
fi

# === 检查 dist 目录 ===
if [ ! -d "$DIST_DIR" ]; then
    echo "❌ dist/ 目录不存在，请先运行 ./build.sh 构建项目"
    exit 1
fi

FILE_COUNT=$(find "$DIST_DIR" -type f | wc -l | tr -d ' ')
if [ "$FILE_COUNT" -eq 0 ]; then
    echo "❌ dist/ 目录为空，请先运行 ./build.sh 构建项目"
    exit 1
fi

echo "部署目录: $DIST_DIR"
echo "目标站点: https://$CNAME"
echo "待上传文件: $FILE_COUNT 个"
echo ""

# === 检查网站是否已存在 ===
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "X-Api-Key: $OA_PAGES_API_KEY" "https://pages.woa.com/api/repos/$CNAME")
if [ "$HTTP_CODE" = "200" ]; then
    echo "网站已存在，将更新所有文件..."
    SITE_EXISTS=true
else
    echo "网站不存在，将创建新网站..."
    SITE_EXISTS=false
fi

# === 二进制扩展名 ===
is_binary() {
    case "${1##*.}" in
        png|jpg|jpeg|gif|webp|ico|woff|woff2|ttf|eot|otf|pf_fragment|pf_index|pf_meta|pagefind|wasm)
            return 0 ;;
        *)
            return 1 ;;
    esac
}

# === 构建 JSON 并分批上传 ===
BATCH_NUM=0
BATCH_SIZE=0
BATCH_FILES=""
FIRST_BATCH=true
FAILED=0
UPLOADED=0

upload_batch() {
    BATCH_NUM=$((BATCH_NUM + 1))
    local files_json="{$BATCH_FILES}"
    local body=""

    if [ "$FIRST_BATCH" = true ] && [ "$SITE_EXISTS" = false ]; then
        body="{\"cname\":\"$CNAME\",\"description\":\"$DESCRIPTION\",\"files\":$files_json}"
        URL="https://pages.woa.com/api/sites"
        METHOD="POST"
        FIRST_BATCH=false
    else
        body="{\"files\":$files_json}"
        URL="https://pages.woa.com/api/sites/$CNAME"
        METHOD="PUT"
        FIRST_BATCH=false
    fi

    echo "$body" > "$TMP_FILE"
    local size_mb=$(echo "scale=2; $(wc -c < "$TMP_FILE") / 1048576" | bc 2>/dev/null || echo "?")
    printf "Batch %d: %s MB..." "$BATCH_NUM" "$size_mb"

    RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X "$METHOD" "$URL" \
        -H "X-Api-Key: $OA_PAGES_API_KEY" \
        -H "Content-Type: application/json" \
        --data-binary "@$TMP_FILE" \
        --max-time 120)

    RESP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | sed 's/HTTP_CODE://')

    if [ "$RESP_CODE" = "200" ]; then
        echo " OK ✅"
    else
        RESP_BODY=$(echo "$RESPONSE" | grep -v "HTTP_CODE:")
        echo " FAILED ($RESP_CODE) ❌"
        echo "  $RESP_BODY"
        FAILED=$((FAILED + 1))
    fi

    sleep 1
    BATCH_SIZE=0
    BATCH_FILES=""
}

# === 遍历文件 ===
while IFS= read -r -d '' file; do
    # 跳过 serve 脚本
    basename=$(basename "$file")
    if [ "$basename" = "serve.bat" ] || [ "$basename" = "serve.sh" ]; then
        continue
    fi

    rel_path="${file#$DIST_DIR/}"

    # 编码内容
    if is_binary "$file"; then
        content=$(base64 < "$file" | tr -d '\n')
    else
        # JSON-escape the content
        content=$(python3 -c "
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8', errors='replace') as f:
    print(json.dumps(f.read())[1:-1])
" "$file")
    fi

    # 估算大小
    entry_size=$(( ${#rel_path} + ${#content} + 50 ))

    # 如果当前批次加上这个文件会超限，先上传当前批次
    if [ $((BATCH_SIZE + entry_size)) -gt $MAX_BATCH_SIZE ] && [ -n "$BATCH_FILES" ]; then
        upload_batch
    fi

    # 追加到当前批次
    if [ -n "$BATCH_FILES" ]; then
        BATCH_FILES="$BATCH_FILES,"
    fi
    BATCH_FILES="$BATCH_FILES\"$rel_path\":\"$content\""
    BATCH_SIZE=$((BATCH_SIZE + entry_size))
    UPLOADED=$((UPLOADED + 1))

done < <(find "$DIST_DIR" -type f -print0 | sort -z)

# 上传最后一批
if [ -n "$BATCH_FILES" ]; then
    upload_batch
fi

# === 清理 ===
rm -f "$TMP_FILE"

# === 结果 ===
echo ""
if [ $FAILED -eq 0 ]; then
    echo "╔══════════════════════════════════════════╗"
    echo "║  ✅ 部署成功!                            ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""
    echo "共上传 $UPLOADED 个文件（$BATCH_NUM 批）"
    echo "网站地址: https://$CNAME"
else
    echo "❌ $FAILED 个批次失败"
    echo "请重新运行脚本重试（PUT 是幂等的，不会重复创建）"
fi
