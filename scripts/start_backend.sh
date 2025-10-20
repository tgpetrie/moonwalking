#!/usr/bin/env bash
# start_backend.sh — helper to launch the Flask backend with optional offline fixtures
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage: scripts/start_backend.sh [--offline] [--port <port>] [--require-net]

Options:
  --offline       Enable fixture mode (sets USE_FIXTURES=1)
  --port <port>   Override BACKEND_PORT (defaults to 5001)
  --require-net   Fail fast if outbound HTTPS to Coinbase is blocked
  -h, --help      Show this help text
EOF
}

BACKEND_PORT="${BACKEND_PORT:-5001}"
REQUIRE_NET="${REQUIRE_NET:-0}"
OFFLINE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --offline)
      OFFLINE=1
      shift
      ;;
    --port)
      [[ $# -ge 2 ]] || { echo "[start_backend] --port requires an argument" >&2; usage; exit 1; }
      BACKEND_PORT="$2"
      shift 2
      ;;
    --require-net)
      REQUIRE_NET=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[start_backend] Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

export BACKEND_PORT

if [[ $OFFLINE -eq 1 ]]; then
  export USE_FIXTURES=1
  echo "[start_backend] Offline mode enabled (USE_FIXTURES=1)"
fi

if [[ "${REQUIRE_NET}" == "1" && "${USE_FIXTURES:-0}" != "1" ]]; then
  echo "[start_backend] Checking network egress..."
  if ! python3 "$ROOT_DIR/scripts/check_net.py"; then
    echo "[start_backend] No outbound network access detected. Re-run with --offline or set USE_FIXTURES=1." >&2
    exit 2
  fi
fi

# Ensure FLASK_APP points to the application module
export FLASK_APP=${FLASK_APP:-backend.app}
export FLASK_ENV=${FLASK_ENV:-development}

echo "[start_backend] Running: flask run --host=127.0.0.1 --port=${BACKEND_PORT}"
exec flask run --host=127.0.0.1 --port="${BACKEND_PORT}"
