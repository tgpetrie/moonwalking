#!/usr/bin/env bash
set -euo pipefail

API_BASE="${1:-https://moonwalker.onrender.com}"
printf '[smoke] Using API base: %s\n' "$API_BASE" >&2

fail() { printf '[smoke][FAIL] %s\n' "$*" >&2; exit 1; }

hit() {
  local path="$1"; shift || true
  printf '[smoke] GET %s ... ' "$path"
  local body
  if ! body=$(curl -fsSL --max-time 10 "$API_BASE$path" 2>/dev/null); then
     printf 'FAIL\n'; fail "request failed: $path"; fi
  printf 'ok\n'
  # Minimal validation for JSON shape
  if [[ "$path" == "/api/health" ]]; then
     echo "$body" | grep -q '"status"' || fail 'health missing status'
  fi
}

hit /api/health
hit /api/server-info
hit /api/component/top-banner-scroll
hit /api/component/bottom-banner-scroll

printf '[smoke] All basic checks passed.\n' >&2
