#!/usr/bin/env python3
"""
Dev seeder for 1-hour volume minute buckets.

Gate: set DEV_SEED_VOLUME_HISTORY=1 to enable.
Optional knobs via env:
  DEV_SEED_SYMBOLS=BTC-USD,ETH-USD
  DEV_SEED_MINUTES=90

This script writes deterministic minute buckets into the same sqlite used by
the production code so `compute_volume_1h()` and the candle pipeline can
operate immediately during development.
"""
import os
import time
import random
from typing import List

from pathlib import Path

import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
# Add backend/ (the directory containing volume_1h_store.py) to sys.path
sys.path.insert(0, str(BACKEND_DIR))

import volume_1h_store as store


def _get_env_list(key: str, default: str) -> List[str]:
    v = os.getenv(key, default)
    return [s.strip() for s in v.split(",") if s.strip()]


def main():
    if os.getenv("DEV_SEED_VOLUME_HISTORY") not in ("1", "true", "True"):
        print("DEV_SEED_VOLUME_HISTORY not set - refusing to seed. Set to 1 to enable.")
        return

    symbols = _get_env_list("DEV_SEED_SYMBOLS", "BTC-USD,ETH-USD")
    minutes = int(os.getenv("DEV_SEED_MINUTES", "90"))
    seed = int(os.getenv("DEV_SEED_SEED", "12345"))

    rng = random.Random(seed)

    now_ts = int(time.time())
    now_floor = store.floor_minute(now_ts)
    start_ts = now_floor - (minutes - 1) * 60

    print(f"Seeding {minutes} minutes for {symbols} into {store.DB_PATH}")
    store.ensure_db()

    for product_id in symbols:
        # deterministic per-product offset so symbols differ predictably
        offset = abs(hash(product_id)) % 100
        for i in range(minutes):
            minute_ts = start_ts + i * 60
            # ramp base volume plus small seeded noise
            base = 1000.0 + i * 5.0 + offset
            noise = rng.uniform(-base * 0.05, base * 0.05)
            vol_base = max(0.0, base + noise)
            close = 50000.0 + offset + (i * 0.01) + rng.uniform(-50.0, 50.0)
            store.upsert_minute(product_id, minute_ts, vol_base, close)

    print("Seeding complete.")


if __name__ == "__main__":
    main()
