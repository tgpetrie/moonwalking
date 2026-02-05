#!/usr/bin/env bash
set -euo pipefail

if ! command -v lsof >/dev/null 2>&1; then
  printf "lsof is required but not installed. Please install it and rerun.\n" >&2
  exit 1
fi

printf "Scanning listening TCP/UDP ports owned by %s that originate from this repo...\n" "$USER"
ROOT="$(cd "$(dirname "$0")/.." >/dev/null && pwd)"
PORT_PIDS=$(lsof -tiTCP -sTCP:LISTEN -u "$USER" 2>/dev/null)
PORT_PIDS="$PORT_PIDS $(lsof -tiUDP -u "$USER" 2>/dev/null)"

SAFE_PIDS=()
for PID in $PORT_PIDS; do
  if [[ -z "$PID" ]]; then
    continue
  fi
  CMD=$(ps -p "$PID" -o args= 2>/dev/null)
  if [[ -n "$CMD" && "$CMD" == *"$ROOT"* ]]; then
    SAFE_PIDS+=("$PID")
  fi
done

if [[ ${#SAFE_PIDS[@]} -eq 0 ]]; then
  printf "No repo-scoped listeners were detected. Nothing to kill.\n"
  exit 0
fi

printf "Killing %s repo-scoped PIDs: %s\n" "${#SAFE_PIDS[@]}" "${SAFE_PIDS[*]}"
kill -9 "${SAFE_PIDS[@]}" >/dev/null 2>&1 || true
printf "Repo-scoped ports terminated. Re-run `lsof -i` to verify.\n"
