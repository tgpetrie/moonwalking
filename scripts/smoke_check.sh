#!/usr/bin/env bash
set -euo pipefail

API_BASE=${API_BASE:-http://127.0.0.1:5001}

echo "[smoke] health..."
curl -sS -D - "${API_BASE}/api/health" -o /tmp/health.json >/dev/null
python3 ./scripts/count_data.py "${API_BASE}/api/health" || true

echo "[smoke] top banner..."
python3 ./scripts/count_data.py "${API_BASE}/api/component/top-banner-scroll" || true

echo "[smoke] bottom banner..."
python3 ./scripts/count_data.py "${API_BASE}/api/component/bottom-banner-scroll" || true

echo "[smoke] snapshot volume..."
python3 ./scripts/count_data.py "${API_BASE}/api/snapshots/one-hour-volume" || true

echo "[smoke] gainers 1m..."
python3 ./scripts/count_data.py "${API_BASE}/api/component/gainers-table-1min" || true

echo "[smoke] losers 3m..."
python3 ./scripts/count_data.py "${API_BASE}/api/component/losers-table-3min" || true

echo "[smoke] done."
