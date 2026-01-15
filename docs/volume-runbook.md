**Volume Runbook**

Purpose: quick developer runbook to seed the 1-hour minute-bucket store, verify backend readiness, and understand "WARMING" behavior.

- **Seed (dev)**: enable gate and run seeder

  - Environment (example):

    ```bash
    export DEV_SEED_VOLUME_HISTORY=1
    export DEV_SEED_SYMBOLS=BTC-USD,ETH-USD
    export DEV_SEED_MINUTES=120
    python3 backend/scripts/seed_volume1h.py
    ```

- **Confirm DB has buckets** (from project root):

  ```bash
  sqlite3 backend/data/volume_1h.sqlite "SELECT product_id, COUNT(*) AS cnt FROM volume_minute GROUP BY product_id;"
  sqlite3 backend/data/volume_1h.sqlite "SELECT product_id, MIN(minute_ts), MAX(minute_ts) FROM volume_minute GROUP BY product_id;"
  ```

- **Confirm API readiness** (assumes backend on port 5003):

  ```bash
  curl -s localhost:5003/api/data | jq '.banner_1h_volume | length'
  curl -s localhost:5003/api/data | jq '.volume_1h_candles | length'
  ```

- **What "WARMING" means**

  - The 1h banner is sourced exclusively from minute-candle buckets (SQLite). The backend computes `compute_volume_1h()` and requires ~110 distinct minutes to consider the baseline ready. If that readiness threshold is not met, the banner returns an empty list (UI shows WARMING). This ensures no fallback to unrelated 24h rolling stats.

- **Logs and troubleshooting**

  - Backend logs: check `backend/gunicorn.stdout`, `/tmp/mw_backend_5003.log`, and the output of `./restart_dev.sh` when starting.
  - Grep for volume updater lines:

    ```bash
    rg "volume1h|volume_1h|refresh_product_minutes" -n backend || true
    tail -n 200 /tmp/mw_backend_5003.log || tail -n 200 /tmp/mw_backend.log || true
    ```

- **Quick operational checklist**

  1. Run seeder (set `DEV_SEED_VOLUME_HISTORY=1`).
 2. Restart backend (recommended) so the snapshot assembler picks up DB rows.
 3. Curl `/api/data` and verify `banner_1h_volume` length > 0.
 4. If empty: verify DB contents and that minute counts >= 110 per symbol.
