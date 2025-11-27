#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${SENTIMENT_PORT:-8001}"
HOST="${SENTIMENT_HOST:-0.0.0.0}"
LOG_LEVEL="${SENTIMENT_LOG_LEVEL:-info}"

python -m backend.sentiment_api \
  --host "$HOST" \
  --port "$PORT" \
  --log-level "$LOG_LEVEL" \
  "$@"
