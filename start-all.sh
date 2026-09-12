#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# One-command startup for the WHOLE InfraWatch system:
#   satellite-service + InfraWatch backend + InfraWatch frontend
#
# Usage:
#   ./start-all.sh          -> demo mode (bundled sample images, no internet
#                               needed, always works — the safe default)
#   ./start-all.sh real     -> real mode (live Sentinel-2 imagery via
#                               satellite-service — needs internet access)
#
# First run does full setup automatically (venvs, pip/npm installs, .env
# files) — this can take a few minutes. Every run after that starts in
# seconds. The demo database and its 6 sample projects are created
# automatically the first time the backend starts — there is nothing to
# download, prepare, or configure by hand.
#
# Press Ctrl+C to stop all three services cleanly.
# ─────────────────────────────────────────────────────────────────────────
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SATELLITE_DIR="$(cd "$SCRIPT_DIR/../satellite-service" 2>/dev/null && pwd || true)"
MODE="${1:-demo}"

if [ -z "$SATELLITE_DIR" ]; then
  echo "ERROR: could not find ../satellite-service next to this InfraWatch folder."
  echo "InfraWatch and satellite-service must be sibling folders (same parent directory)."
  echo "See docs/03-developer-setup.md for the expected layout."
  exit 1
fi

if [ "$MODE" != "demo" ] && [ "$MODE" != "real" ]; then
  echo "Usage: ./start-all.sh [demo|real]"
  exit 1
fi

# ── Fail fast with a clear message instead of a confusing error mid-setup ──
missing=()
command -v python3 >/dev/null 2>&1 || missing+=("python3 (need 3.10+)")
command -v node >/dev/null 2>&1 || missing+=("node (need 18+)")
command -v npm >/dev/null 2>&1 || missing+=("npm")
if [ ${#missing[@]} -gt 0 ]; then
  echo "ERROR: missing required tool(s):"
  for m in "${missing[@]}"; do echo "  - $m"; done
  echo "Install the missing tool(s) above, then re-run this script."
  exit 1
fi

echo "=================================================================="
echo " InfraWatch — starting in '$MODE' mode"
echo "=================================================================="
echo ""

# ── One-time setup (skipped automatically on later runs) ─────────────────
if [ ! -d "$SATELLITE_DIR/.venv" ]; then
  echo "==> First-time setup: satellite-service (this can take a few minutes)..."
  (cd "$SATELLITE_DIR" && bash setup.sh)
fi

if [ ! -d "$SCRIPT_DIR/backend/.venv" ]; then
  echo "==> First-time setup: InfraWatch backend (this can take a few minutes)..."
  (cd "$SCRIPT_DIR/backend" && bash setup.sh)
fi

if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
  echo "==> First-time setup: InfraWatch frontend (this can take a minute or two)..."
  (cd "$SCRIPT_DIR/frontend" && bash setup.sh)
fi

# ── Apply the requested satellite mode without hand-editing .env ─────────
BACKEND_ENV="$SCRIPT_DIR/backend/.env"
if grep -q "^SATELLITE_MODE=" "$BACKEND_ENV" 2>/dev/null; then
  sed -i.bak "s/^SATELLITE_MODE=.*/SATELLITE_MODE=$MODE/" "$BACKEND_ENV" && rm -f "$BACKEND_ENV.bak"
else
  echo "SATELLITE_MODE=$MODE" >> "$BACKEND_ENV"
fi

# ── Start all three, cleaning up on Ctrl+C ────────────────────────────────
# Each service below runs inside a "(...) &" subshell, so $! is the subshell's
# PID, not the actual uvicorn/node process underneath it — killing just that
# PID leaves the real server orphaned and still holding the port open. Killing
# by port instead is simple and reliable for this script's fixed ports.
PIDS=()
kill_port() {
  local port="$1"
  local pids
  pids=$(lsof -ti "tcp:$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null || true
  fi
}
cleanup() {
  echo ""
  echo "Stopping all services..."
  kill_port 8001
  kill_port 8000
  kill_port 3000
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  sleep 1
  # Next.js's dev CLI can outlive the port it was bound to — reap it explicitly
  # so repeated start/stop cycles don't accumulate idle leftover processes.
  pkill -f "$SCRIPT_DIR/frontend/node_modules/.bin/next" 2>/dev/null || true
  echo "Stopped."
  exit 0
}
trap cleanup INT TERM

mkdir -p /tmp/infrawatch-logs

echo ""
echo "==> Starting satellite-service (port 8001)..."
(cd "$SATELLITE_DIR" && source .venv/bin/activate && uvicorn app:app --host 0.0.0.0 --port 8001) \
  > /tmp/infrawatch-logs/satellite-service.log 2>&1 &
PIDS+=($!)

echo "==> Starting InfraWatch backend (port 8000)..."
(cd "$SCRIPT_DIR/backend" && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000) \
  > /tmp/infrawatch-logs/backend.log 2>&1 &
PIDS+=($!)

echo "==> Starting InfraWatch frontend (port 3000)..."
(cd "$SCRIPT_DIR/frontend" && npm run dev) \
  > /tmp/infrawatch-logs/frontend.log 2>&1 &
PIDS+=($!)

echo ""
echo "=================================================================="
if [ "$MODE" = "demo" ]; then
  echo " Mode: DEMO — bundled sample images, works offline, always reliable."
  echo " (Run './start-all.sh real' instead for live Sentinel-2 imagery.)"
else
  echo " Mode: REAL — live Sentinel-2 imagery via satellite-service."
  echo " Needs internet access. First analysis per project takes 10-30s."
fi
echo "=================================================================="
echo ""
echo " Give it about 30-60 seconds on first run to finish starting up,"
echo " then open:"
echo ""
echo "   Dashboard:            http://localhost:3000"
echo "   Backend API docs:     http://localhost:8000/docs"
echo "   satellite-service docs: http://localhost:8001/docs"
echo ""
echo " Logs are in /tmp/infrawatch-logs/ if something looks wrong."
echo " Press Ctrl+C here to stop everything."
echo ""

wait
