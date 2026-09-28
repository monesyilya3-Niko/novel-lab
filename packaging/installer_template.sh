#!/bin/sh
# novel-lab 自解压安装包（单文件）
#   构建: packaging/build_installer.sh
#   版本: __VERSION__
#
# 用法:
#   sh novel-lab-installer.sh [--prefix DIR] [--bin-dir DIR] [--uninstall] [--help]
#
#   --prefix DIR    安装位置（默认 ~/.local/share/novel-lab）
#   --bin-dir DIR   启动器安装位置（默认 ~/.local/bin）
#   --uninstall     卸载（删除安装目录与启动器）
#
# 要求: python3 >= 3.10（纯标准库，零第三方依赖）、unzip、base64、sha256sum
# Windows 用户请直接解压 zip 用 Start.bat；本安装器面向 Linux / macOS。
set -e

VERSION="__VERSION__"
PAYLOAD_SHA256="__PAYLOAD_SHA256__"

PREFIX="${HOME}/.local/share/novel-lab"
BIN_DIR="${HOME}/.local/bin"
UNINSTALL=0

while [ $# -gt 0 ]; do
    case "$1" in
        --prefix)   PREFIX="$2"; shift 2 ;;
        --bin-dir)  BIN_DIR="$2"; shift 2 ;;
        --uninstall) UNINSTALL=1; shift ;;
        -h|--help)
            sed -n '2,16p' "$0"
            exit 0 ;;
        *) echo "未知参数: $1（用 --help 查看用法）" >&2; exit 1 ;;
    esac
done

MARKER="$PREFIX/.novel-lab-install"

if [ "$UNINSTALL" = "1" ]; then
    if [ ! -f "$MARKER" ]; then
        echo "[novel-lab] $PREFIX 不是本安装器安装的目录（缺少安装标记），拒绝删除。" >&2
        exit 1
    fi
    rm -rf "$PREFIX"
    rm -f "$BIN_DIR/novel-lab" "$BIN_DIR/novel"
    rmdir "$BIN_DIR" 2>/dev/null || true  # 仅当空目录时回收
    echo "[novel-lab] 已卸载: $PREFIX"
    exit 0
fi

# ---- 环境检查 ----
if ! command -v python3 >/dev/null 2>&1; then
    echo "[novel-lab] 未找到 python3，请先安装 Python 3.10+。" >&2
    exit 1
fi
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo "[novel-lab] Python 版本过低（$(python3 -V 2>&1)），需要 3.10+。" >&2
    exit 1
fi
for cmd in unzip base64 sha256sum; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "[novel-lab] 缺少必需命令: $cmd" >&2
        exit 1
    fi
done

# ---- 释放 payload ----
PAYLOAD_LINE=$(awk '/^__PAYLOAD__$/{print NR + 1; exit}' "$0")
TMP_ZIP=$(mktemp /tmp/novel-lab-payload-XXXXXX.zip)
trap 'rm -f "$TMP_ZIP"' EXIT INT TERM
tail -n +"$PAYLOAD_LINE" "$0" | base64 -d > "$TMP_ZIP"
ACTUAL_SHA=$(sha256sum "$TMP_ZIP" | cut -d' ' -f1)
if [ "$ACTUAL_SHA" != "$PAYLOAD_SHA256" ]; then
    echo "[novel-lab] 安装包完整性校验失败（payload SHA-256 不匹配），中止安装。" >&2
    echo "  期望: $PAYLOAD_SHA256" >&2
    echo "  实际: $ACTUAL_SHA" >&2
    exit 1
fi

# ---- 安装文件 ----
mkdir -p "$PREFIX"
# 升级检测：已存在安装标记则先备份旧版本（代码部分），数据目录不受影响
if [ -f "$MARKER" ]; then
    OLD_VERSION=$(cat "$MARKER" 2>/dev/null || echo "未知")
    BACKUP_DIR="${PREFIX}.bak-$(date +%Y%m%d-%H%M%S)"
    echo "[novel-lab] 检测到已安装版本 $OLD_VERSION，正在备份到 $BACKUP_DIR ..."
    # 只备份代码文件，数据目录（gui_state/corpus/reports/config/novel）太大且无需回滚
    mkdir -p "$BACKUP_DIR"
    for d in gui scripts tests packaging novel.py run_tests.py; do
        [ -e "$PREFIX/$d" ] && cp -a "$PREFIX/$d" "$BACKUP_DIR/" 2>/dev/null || true
    done
    echo "[novel-lab] 升级：$OLD_VERSION -> $VERSION（旧代码已备份，数据目录原位保留）"
fi
unzip -q -o "$TMP_ZIP" -d "$PREFIX"
# 数据目录（不随 zip 分发，安装时创建）
mkdir -p "$PREFIX/gui_state" "$PREFIX/corpus" "$PREFIX/reports"
echo "$VERSION" > "$MARKER"

# ---- 启动器 ----
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/novel-lab" <<EOF
#!/bin/sh
# novel-lab 启动器（由安装器生成，不要手改）
exec python3 "$PREFIX/gui/launch.py" "\$@"
EOF
cat > "$BIN_DIR/novel" <<EOF
#!/bin/sh
# novel-lab CLI 启动器（由安装器生成，不要手改）
exec python3 "$PREFIX/novel.py" "\$@"
EOF
chmod +x "$BIN_DIR/novel-lab" "$BIN_DIR/novel"

# ---- 装后自检 ----
if ! python3 "$PREFIX/gui/launch.py" --check >/dev/null 2>&1; then
    echo "[novel-lab] 安装后自检失败，请检查 Python 环境。" >&2
    exit 1
fi

echo "[novel-lab] 安装成功: $VERSION -> $PREFIX"
echo ""
echo "启动图形工作台:  novel-lab                 （浏览器访问 http://127.0.0.1:8000/）"
echo "命令行工具:      novel --help"
echo "运行测试套件:    cd $PREFIX && python3 -m unittest discover -s tests"
echo "卸载:            sh $0 --prefix \"$PREFIX\" --bin-dir \"$BIN_DIR\" --uninstall"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo ""; echo "注意: $BIN_DIR 不在 PATH 中，启动器命令需用全路径或自行加入 PATH。" ;;
esac

exit 0

__PAYLOAD__
