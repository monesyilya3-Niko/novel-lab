#!/bin/bash
# 隔离 E2E：工作树 rsync 副本 → 独立端口 → 跑 Playwright → 删副本。
# 真实 gui_state/、corpus/、assets/ 零写入；跑完无残留。
# 空库用例：E2E_EMPTY_LIBRARY=1 bash scripts/e2e_isolated.sh e2e/onboarding.spec.ts
#
# 端口说明：先选一个当前空闲端口；服务若仍顺延（--port 占用自动 +1），
# 则以服务实际打印的启动 URL 为准，绝不假设端口。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$HOME/workspace/.tmp/e2e-$(date +%Y%m%d-%H%M%S)-$$"
PORT="${E2E_PORT:-$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()")}"

mkdir -p "$WORK"
# rsync 工作树（含未提交改动），排除大体积/运行时目录。
# E2E_EMPTY_LIBRARY=1：额外排除仓库种子数据（corpus/、assets/、reports/），
# 得到真正空库（OnboardingWizard 首启引导用例需要；smoke/journey 依赖种子
# assets/，不得默认排除）。
RSYNC_EXTRA=()
if [ "${E2E_EMPTY_LIBRARY:-0}" = "1" ]; then
  # 注意：必须用 / 锚定到同步根，否则 'assets/' 会误伤 gui/web/dist/assets/（前端产物）。
  RSYNC_EXTRA=(--exclude='/corpus/' --exclude='/assets/' --exclude='/reports/' --exclude='/gui/state/')
fi
rsync -a --delete \
  --exclude='.git/' \
  --exclude='gui/web/node_modules/' \
  --exclude='gui_state/' \
  --exclude='__pycache__/' \
  --exclude='.coverage' \
  "${RSYNC_EXTRA[@]}" \
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
  echo "E2E 服务未就绪"
  cat "$SRV_LOG"
  exit 1
fi
curl -sf "http://127.0.0.1:$ACTUAL_PORT/" >/dev/null \
  || { echo "E2E 服务端口 $ACTUAL_PORT 无响应"; cat "$SRV_LOG"; exit 1; }

cd "$ROOT/gui/web"
E2E_BASE_URL="http://127.0.0.1:$ACTUAL_PORT" E2E_SERVER_ROOT="$WORK" npx playwright test "$@"
