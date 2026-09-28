#!/bin/sh
# novel-lab 自解压安装包（单文件）
#   构建: packaging/build_installer.sh <payload.zip> <version> <output.sh>
#   版本: __VERSION__
#
# 要求: python3 >= 3.10（纯标准库，零第三方依赖）、unzip、base64、sha256sum
# Windows 用户请直接解压 zip 用 Start.bat；本安装器面向 Linux / macOS。
#
# 升级语义（原子切换 + 自动回滚）：
#   1. 校验新 payload 的 SHA-256，不匹配直接中止（不碰旧安装）；
#   2. 解压到与安装目录同文件系统的 staging 目录；
#   3. 旧安装整体 mv 到带时间戳的备份目录（${PREFIX}.bak-YYYYmmdd-HHMMSS）；
#   4. staging 原子 mv 为正式安装目录（同文件系统 rename，不可分割）；
#   5. 用户数据目录从备份搬回新安装目录，原样保留；
#   6. 任一步失败 → 自动回滚到备份并以非零退出码退出；
#   7. 安装后自检失败 → 同样自动回滚。
# USAGE-BEGIN
# novel-lab 自解压安装包（单文件）
#
# 用法:
#   sh novel-lab-installer.sh [--prefix DIR] [--bin-dir DIR] [--uninstall] [--clean-backups] [--help]
#
#   --prefix DIR     安装位置（默认 ~/.local/share/novel-lab）
#   --bin-dir DIR    启动器安装位置（默认 ~/.local/bin）
#   --uninstall      卸载（删除安装目录与启动器；升级备份默认保留并报告）
#   --clean-backups  与 --uninstall 联用：同时删除升级备份目录（${PREFIX}.bak-*）
#   --help           显示本帮助
#
# 覆盖升级示例:
#   sh novel-lab-installer-2.0.1.sh
# 卸载示例:
#   sh novel-lab-installer-2.0.1.sh --uninstall
# USAGE-END
set -e

VERSION="__VERSION__"
PAYLOAD_SHA256="__PAYLOAD_SHA256__"

PREFIX="${HOME}/.local/share/novel-lab"
BIN_DIR="${HOME}/.local/bin"
UNINSTALL=0
CLEAN_BACKUPS=0

print_help() {
    awk '/^# USAGE-BEGIN$/{f=1; next} /^# USAGE-END$/{f=0} f{sub(/^# ?/, ""); print}' "$0"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --prefix)        PREFIX="$2"; shift 2 ;;
        --bin-dir)       BIN_DIR="$2"; shift 2 ;;
        --uninstall)     UNINSTALL=1; shift ;;
        --clean-backups) CLEAN_BACKUPS=1; shift ;;
        -h|--help)       print_help; exit 0 ;;
        *) echo "未知参数: $1（用 --help 查看用法）" >&2; exit 1 ;;
    esac
done

MARKER="$PREFIX/.novel-lab-install"

# 用户数据目录（相对安装根目录）。升级/回滚时原样保留，绝不删除；
# 对应 gui/config.py 的 STATE_ROOT / STATE_JSON_DIR / REPORTS_DIR /
# CORPUS_DIR / CONFIG_DIR / NOVEL_DIR / PROMPTS_DIR。
DATA_DIRS="gui_state gui/state corpus reports config novel prompts/generated"

move_data_dirs() {
    # move_data_dirs <源根> <目标根>：把存在的数据目录搬到目标（目标已存在则跳过，防覆盖）
    _src="$1"; _dst="$2"; _d=""
    for _d in $DATA_DIRS; do
        if [ -e "$_src/$_d" ] && [ ! -e "$_dst/$_d" ]; then
            mkdir -p "$_dst/$(dirname "$_d")"
            mv "$_src/$_d" "$_dst/$_d"
        fi
    done
}

STAGE=""
BACKUP=""
NEED_ROLLBACK=0
TMP_ZIP=""

do_rollback() {
    # 回滚到升级备份。幂等：执行后清空 BACKUP，重复调用无副作用。
    [ -n "$BACKUP" ] || return 0
    [ -d "$BACKUP" ] || { BACKUP=""; NEED_ROLLBACK=0; return 0; }
    echo "[novel-lab] 正在回滚到备份: $BACKUP" >&2
    if [ -e "$PREFIX" ]; then
        move_data_dirs "$PREFIX" "$BACKUP"
        rm -rf "$PREFIX"
    fi
    mv "$BACKUP" "$PREFIX"
    BACKUP=""
    NEED_ROLLBACK=0
    echo "[novel-lab] 已回滚到上一版本。" >&2
}

cleanup() {
    if [ -n "$TMP_ZIP" ]; then
        rm -f "$TMP_ZIP"
    fi
    # staging 残留兜底清理（切换成功后它已不存在）
    if [ -n "$STAGE" ] && [ -d "$STAGE" ]; then
        rm -rf "$STAGE"
    fi
    # 升级流程中途失败 → 自动回滚
    if [ "$NEED_ROLLBACK" = "1" ]; then
        do_rollback
    fi
}
trap 'cleanup' EXIT INT TERM

# ============================== 卸载 ==============================
if [ "$UNINSTALL" = "1" ]; then
    if [ ! -f "$MARKER" ]; then
        echo "[novel-lab] $PREFIX 不是本安装器安装的目录（缺少安装标记），拒绝删除。" >&2
        exit 1
    fi
    rm -rf "$PREFIX"
    rm -f "$BIN_DIR/novel-lab" "$BIN_DIR/novel"
    rmdir "$BIN_DIR" 2>/dev/null || true  # 仅当空目录时回收
    echo "[novel-lab] 已卸载: $PREFIX"

    # ---- 卸载残留检查 ----
    RESIDUAL=0
    # 1) 升级备份目录：默认保留并报告；--clean-backups 则一并清理
    for b in "${PREFIX}".bak-*; do
        [ -d "$b" ] || continue
        if [ "$CLEAN_BACKUPS" = "1" ]; then
            rm -rf "$b"
            echo "[novel-lab] 已清理升级备份: $b"
        else
            echo "[novel-lab] 残留升级备份（已保留）: $b"
            echo "           手动删除：rm -rf \"$b\"；或卸载时加 --clean-backups 一并删除"
            RESIDUAL=1
        fi
    done
    # 2) 中断安装遗留的 staging 目录：孤儿，可安全清理
    for s in "${PREFIX}".stage-*; do
        [ -d "$s" ] || continue
        rm -rf "$s"
        echo "[novel-lab] 已清理中断安装残留: $s"
    done
    # 3) 启动器残留复核
    for l in "$BIN_DIR/novel-lab" "$BIN_DIR/novel"; do
        if [ -e "$l" ]; then
            echo "[novel-lab] 警告：启动器残留未清理干净：$l" >&2
            RESIDUAL=1
        fi
    done
    if [ "$RESIDUAL" = "0" ]; then
        echo "[novel-lab] 残留检查通过：无残留文件。"
    else
        echo "[novel-lab] 残留检查：发现上述残留项（见上）。"
    fi
    exit 0
fi

# ============================== 环境检查 ==============================
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

# ============================== 释放 payload ==============================
PAYLOAD_LINE=$(awk '/^__PAYLOAD__$/{print NR + 1; exit}' "$0")
TMP_ZIP=$(mktemp /tmp/novel-lab-payload-XXXXXX.zip)
tail -n +"$PAYLOAD_LINE" "$0" | base64 -d > "$TMP_ZIP"
ACTUAL_SHA=$(sha256sum "$TMP_ZIP" | cut -d' ' -f1)
if [ "$ACTUAL_SHA" != "$PAYLOAD_SHA256" ]; then
    echo "[novel-lab] 安装包完整性校验失败（payload SHA-256 不匹配），中止安装。" >&2
    echo "  期望: $PAYLOAD_SHA256" >&2
    echo "  实际: $ACTUAL_SHA" >&2
    exit 1
fi

# 解压到 staging（与 PREFIX 同文件系统，保证后续 mv 为原子 rename）
STAGE="${PREFIX}.stage-$$"
rm -rf "$STAGE"
mkdir -p "$STAGE"
unzip -q "$TMP_ZIP" -d "$STAGE"

# ============================== 安装 / 原子升级 ==============================
UPGRADED=0
if [ -f "$MARKER" ]; then
    OLD_VERSION=$(cat "$MARKER" 2>/dev/null || echo "未知")
    BACKUP="${PREFIX}.bak-$(date +%Y%m%d-%H%M%S)"
    echo "[novel-lab] 检测到已安装版本 $OLD_VERSION，升级到 $VERSION ..."
    echo "[novel-lab] 备份旧版到: $BACKUP"
    mv "$PREFIX" "$BACKUP"      # 旧树整体搬走（含用户数据，稍后搬回新树）
    NEED_ROLLBACK=1             # 从此处起任何失败都自动回滚
    mv "$STAGE" "$PREFIX"       # 原子切换：同文件系统 rename，不可分割
    STAGE=""
    move_data_dirs "$BACKUP" "$PREFIX"
    echo "$VERSION" > "$MARKER"
    UPGRADED=1
    echo "[novel-lab] 升级：$OLD_VERSION -> $VERSION（用户数据目录原样保留）"
else
    case "$PREFIX" in
        */*) mkdir -p "${PREFIX%/*}" ;;
    esac
    mv "$STAGE" "$PREFIX"
    STAGE=""
    # 数据目录（不随 payload 分发，安装时创建）
    mkdir -p "$PREFIX/gui_state" "$PREFIX/gui/state" "$PREFIX/corpus" \
             "$PREFIX/reports" "$PREFIX/config" "$PREFIX/novel" \
             "$PREFIX/prompts/generated"
    echo "$VERSION" > "$MARKER"
fi

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

# ---- 装后自检（升级失败则自动回滚） ----
if ! python3 "$PREFIX/gui/launch.py" --check >/dev/null 2>&1; then
    echo "[novel-lab] 安装后自检失败。" >&2
    if [ "$UPGRADED" = "1" ]; then
        echo "[novel-lab] 正在自动回滚到上一版本…" >&2
        NEED_ROLLBACK=0
        do_rollback
    fi
    exit 1
fi

# 成功：解除回滚保护（升级备份保留在 $BACKUP，供用户手动回滚）
NEED_ROLLBACK=0
UPGRADE_BACKUP="$BACKUP"
BACKUP=""

echo "[novel-lab] 安装成功: $VERSION -> $PREFIX"
if [ -n "$UPGRADE_BACKUP" ]; then
    echo "[novel-lab] 旧版本备份保留在: $UPGRADE_BACKUP"
    echo "           如需手动回滚：rm -rf \"$PREFIX\" && mv \"$UPGRADE_BACKUP\" \"$PREFIX\""
fi
echo ""
echo "启动图形工作台:  novel-lab                 （浏览器访问 http://127.0.0.1:8000/）"
echo "命令行工具:      novel --help"
echo "运行测试套件:    cd $PREFIX && python3 -m unittest discover -s tests"
echo "卸载:            sh $0 --prefix \"$PREFIX\" --bin-dir \"$BIN_DIR\" --uninstall"
echo "注意: 如旧版本服务正在运行，请重启以生效新版本。"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo ""; echo "注意: $BIN_DIR 不在 PATH 中，启动器命令需用全路径或自行加入 PATH。" ;;
esac

exit 0

__PAYLOAD__
