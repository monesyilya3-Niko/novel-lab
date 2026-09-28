#!/bin/sh
# 构建 novel-lab 单文件自解压安装器
# 用法: sh packaging/build_installer.sh <payload.zip> <version> <output.sh>
set -e

if [ $# -ne 3 ]; then
    echo "用法: $0 <payload.zip> <version> <output.sh>" >&2
    exit 1
fi

PAYLOAD_ZIP="$1"
VERSION="$2"
OUTPUT="$3"
TEMPLATE="$(dirname "$0")/installer_template.sh"

if [ ! -f "$TEMPLATE" ]; then
    echo "模板不存在: $TEMPLATE" >&2
    exit 1
fi
if [ ! -f "$PAYLOAD_ZIP" ]; then
    echo "payload 不存在: $PAYLOAD_ZIP" >&2
    exit 1
fi

SHA=$(sha256sum "$PAYLOAD_ZIP" | cut -d' ' -f1)

# 替换占位符（保留模板末尾的 __PAYLOAD__ 标记行）
sed -e "s/__VERSION__/$VERSION/" -e "s/__PAYLOAD_SHA256__/$SHA/" "$TEMPLATE" > "$OUTPUT"
base64 "$PAYLOAD_ZIP" >> "$OUTPUT"
chmod +x "$OUTPUT"

echo "构建完成: $OUTPUT"
echo "  版本: $VERSION"
echo "  payload SHA-256: $SHA"
ls -la "$OUTPUT"
