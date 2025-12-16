#!/usr/bin/env bash
set -euo pipefail

kill_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then
    echo "[strict] killing port ${port}: ${pids}"
    # shellcheck disable=SC2086
    kill -9 ${pids} 2>/dev/null || true
  fi
}

wait_http() {
  local url="$1"
  local tries="${2:-40}"
  local sleep_s="${3:-0.25}"

  for _ in $(seq 1 "$tries"); do
    if curl -sS -m 2 -o /dev/null "$url"; then
      return 0
    fi
    sleep "$sleep_s"
  done

  echo "[strict] FAIL: did not become reachable: $url" >&2
  return 1
}

export -f kill_port
export -f wait_http
