#!/bin/zsh
# Backend smoke & health check (local dev)
# Targets backend on port 5002 and validates the contract we actually support.

set -euo pipefail

PORT=${PORT:-5002}
BASE="http://127.0.0.1:${PORT}"
JQ=${JQ:-jq}
CURL="curl -sS --fail --connect-timeout 2 --max-time 5"

red()  { print -P "%F{red}$*%f"; }
grn()  { print -P "%F{green}$*%f"; }
yel()  { print -P "%F{yellow}$*%f"; }

print "=== Checking backend on ${BASE} ==="

print "\n=== /api/health ==="
if ${=CURL} "${BASE}/api/health" | ${JQ} .; then
  grn "OK: /api/health"
else
  red "FAIL: /api/health"; exit 1
fi

print "\n=== /api/metrics (.data_integrity, .swr) ==="
if out=$(${=CURL} "${BASE}/api/metrics"); then
  print -- "$out" | ${JQ} '.data_integrity, .swr'
  grn "OK: /api/metrics"
else
  red "FAIL: /api/metrics"; exit 1
fi

print "\n=== /metrics.prom (pledge gauges) ==="
if ${=CURL} "${BASE}/metrics.prom" | grep -E 'data_integrity_(live_data_only|mocks_allowed)'; then
  grn "OK: pledge gauges present"
else
  yel "WARN: pledge gauges not found"
fi

print "\n=== /api/component/top-movers-bar (.swr) ==="
if ${=CURL} "${BASE}/api/component/top-movers-bar" | ${JQ} '.swr'; then
  grn "OK: component SWR present"
else
  yel "WARN: component missing SWR (endpoint may be throttled)"
fi

print "\n=== Done ==="