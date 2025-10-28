#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-5173}"
if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -ti tcp:"${PORT}" || true)
  if [[ -n "${PIDS}" ]]; then
    echo "[fix_vite] terminating processes on port ${PORT}: ${PIDS}" >&2
    kill ${PIDS} || true
  else
    echo "[fix_vite] no processes detected on port ${PORT}" >&2
  fi
else
  echo "[fix_vite] lsof not available; nothing to do" >&2
fi
