#!/bin/bash
# 隔离性能/边界检查：工作树 rsync 副本 → 独立端口 → 跑 perf_check.py → 删副本。
# 真实 gui_state/、corpus/、assets/ 零写入；跑完无残留。
#
# 端口说明：先选一个当前空闲端口；服务若仍顺延（--port 占用自动 +1），
# 则以服务实际打印的启动 URL 为准，绝不假设端口。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$HOME/workspace/.tmp/perf-$(date +%Y%m%d-%H%M%S)-$$"
PORT="${PERF_PORT:-$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()")}"

mkdir -p "$WORK"
rsync -a --delete \
  --exclude='.git/' \
  --exclude='gui/web/node_modules/' \
  --exclude='gui_state/' \
  --exclude='__pycache__/' \
  --exclude='.coverage' \
  "$ROOT/" "$WORK/"

SRV_LOG="$WORK/server.log"
cleanup() {
  kill "$SRV" 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT

cd "$WORK"
python3 -u -m gui.server --port "$PORT" --no-browser >"$SRV_LOG" 2>&1 &
SRV=$!

# 等服务打印启动 URL，以其实际端口为准
ACTUAL_PORT=""
for _ in $(seq 1 30); do
  if grep -q "已启动" "$SRV_LOG" 2>/dev/null; then
    ACTUAL_PORT="$(grep -o '127\.0\.0\.1:[0-9]*' "$SRV_LOG" | head -1 | cut -d: -f2)"
    break
  fi
  sleep 1
done
if [ -z "$ACTUAL_PORT" ]; then
  echo "性能检查服务未就绪"
  cat "$SRV_LOG"
  exit 1
fi
curl -sf "http://127.0.0.1:$ACTUAL_PORT/" >/dev/null \
  || { echo "性能检查服务端口 $ACTUAL_PORT 无响应"; cat "$SRV_LOG"; exit 1; }

python3 "$WORK/scripts/perf_check.py" --base-url "http://127.0.0.1:$ACTUAL_PORT" --server-pid "$SRV" --server-root "$WORK"
