"""A1 dollar gate against A0 on the backfilled window, frozen definitions.

    python scripts/scoring_experiment/confirm_a1_gate_20261115.py

A0 and A1 are imported unchanged from `screen_microstructure_and_coil_20261115`
(causal trailing-seven-day thresholds). Nothing is tuned here.

Declared before the run:

* Entries: frozen production capture to 2026-10-17, local ledger capture from
  2026-10-18, step 1 eligibility. Entries and candles from 2026-11-13 00:00 UTC
  are refused; the Nov 14 protocol sealed them for a prospective confirmation.
* Candles: the archive and the 2026-11-13 backfill, merged at their seam.
* Scored days: 2026-10-13 to 2026-11-12 (31). 2026-10-06 to 10-12 only set
  trailing thresholds. First half is the first 15 scored days, second half the
  last 16.
* Primary: 3m gainers. Reading rule, the Nov 14 one: mean dP >= -0.50 points
  with block lower bound >= -1.00, and mean dC <= -2.50 with block upper bound
  <= -1.50. Stable when each half has dP >= -0.50 and dC < 0.

These dates and this rule were already scored once, by the Nov 14 activity-gate
test. This run is an independent re-implementation of that result plus the
half split. It is not a new out-of-sample test.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import screen_microstructure_and_coil_20261115 as screen  # noqa: E402

carbon, freeze, run = screen.carbon, screen.freeze, screen.run
ROOT = HERE.parents[1]
OUT = ROOT / "docs/research/results/radar_a1_confirmation_20261115"
ANALYSIS = Path.home() / ".moonwalking/analysis"
LOCAL_DB = ANALYSIS / "live_movers_fresh_replication_20261113/board_episodes.sqlite"
BACKFILL = ANALYSIS / "radar_candle_backfill_20261113/radar_candles.sqlite"
BACKFILL_MANIFEST = BACKFILL.with_name("MANIFEST.json")
LOCAL_SHA256 = "7a3eca1482726d7b5bc431c41bb2fc73929f4abe3635afb2edf5e9315ddea82c"

SEAL = screen.stamp("2026-11-13")
SPLIT = screen.stamp("2026-10-18")
WARMUP = screen.stamp("2026-10-06")
LATE_PHASES = {"late": ["2026-10-18T00:00:00+00:00", "2026-11-13T00:00:00+00:00"]}
WINDOWS = {
    "all": ("2026-10-13", "2026-11-12"),
    "first_half": ("2026-10-13", "2026-10-27"),
    "second_half": ("2026-10-28", "2026-11-12"),
}
PRIMARY = "confirmation_3m_up/up"
# Nov 14 activity-gate test, 3m gainers: entries, A0 flags, A1 flags, dP, dC.
NOV14 = {"entries": 51997, "flags": [12773, 12465], "delta_pp": [0.30, -2.89]}


def assert_sealed(values) -> None:
    if len(values) and int(max(values)) >= SEAL:
        raise SystemExit("Refusing: data at or after 2026-11-13 00:00 UTC was loaded.")


def read_window(db: Path, cfg: dict, lo: int, hi: int) -> pd.DataFrame:
    """Step 1 eligible entries in [lo, hi). Cooldown runs over the whole capture."""
    cooldown, recs = {}, []
    sql = "SELECT * FROM episodes WHERE entered_ts < ? ORDER BY entered_ts, id"
    with closing(carbon.read_only(db)) as con:
        con.row_factory = sqlite3.Row
        for row in con.execute(sql, (SEAL,)):
            _, why, snap = freeze.classify(row, cfg, cooldown)
            ts = row["entered_ts"]
            if why or not lo <= ts < hi:
                continue
            unlabeled = not math.isfinite(screen.num(row["gross_return_30m"]))
            if unlabeled or row["outcome_15m"] == "interrupted":
                continue
            raw = snap["raw_inputs"]
            recs.append(
                {
                    "id": row["id"],
                    "stratum": f"{row['board']}/{row['direction']}",
                    "board": row["board"],
                    "product_id": row["product_id"],
                    "direction": row["direction"],
                    "entered_ts": int(ts),
                    "B0": abs(screen.num(row["start_change_pct"])),
                    "pct_1m": screen.num(raw.get("pct_1m")),
                    "pct_3m": screen.num(raw.get("pct_3m")),
                    "r5": screen.num(row["gross_return_5m"]),
                    "r15": screen.num(row["gross_return_15m"]),
                    "r30": screen.num(row["gross_return_30m"]),
                    "fav15": screen.num(row["max_favorable_15m"]),
                    "adv15": screen.num(row["max_adverse_15m"]),
                }
            )
    df = pd.DataFrame(recs)
    assert_sealed(df["entered_ts"].to_numpy())
    return df


def merge_candles(frames: list) -> pd.DataFrame:
    """One row per product and minute; the first store listed wins at the seam."""
    both = pd.concat(frames, ignore_index=True)
    both = both.drop_duplicates(["product_id", "ts"], keep="first")
    both = both[both["ts"] < SEAL]
    return both.sort_values(["product_id", "ts"]).reset_index(drop=True)


def load_candles(paths: list) -> pd.DataFrame:
    sql = """SELECT product_id, ts, open, high, low, close, volume FROM candles
             WHERE granularity = 60 AND ts >= ? AND ts < ?"""
    frames = []
    for path in paths:
        with closing(carbon.read_only(path)) as con:
            frames.append(pd.read_sql(sql, con, params=(WARMUP - 7200, SEAL)))
    merged = merge_candles(frames)
    prices = merged[["open", "high", "low", "close"]]
    ok = (prices > 0).all(axis=1) & (merged["volume"] >= 0) & (merged["ts"] % 60 == 0)
    assert_sealed(merged["ts"].to_numpy())
    return merged[ok].reset_index(drop=True)


def reading(board: dict) -> dict:
    full, rule = board["all"], screen.HOLD_RULE
    checks = {
        "dP_mean": full["delta_P"]["mean"] >= rule["dp_mean"],
        "dP_block_lo": full["delta_P"]["block3"]["lo"] >= rule["dp_lo"],
        "dC_mean": full["delta_C"]["mean"] <= rule["dc_mean"],
        "dC_block_hi": full["delta_C"]["block3"]["hi"] <= rule["dc_hi"],
    }
    halves = {
        name: board[name]["delta_P"]["mean"] >= rule["dp_mean"]
        and board[name]["delta_C"]["mean"] < 0
        for name in ("first_half", "second_half")
    }
    return {
        "meets_nov14_rule": all(checks.values()),
        "checks": checks,
        "stable_across_halves": all(halves.values()),
        "halves": halves,
        "rule": rule,
    }


def parity(full: dict) -> dict:
    got = {
        "entries": full["entries"],
        "flags": [full["flags"]["base"], full["flags"]["arm"]],
        "delta_pp": [
            round(100 * full["delta_P"]["mean"], 2),
            round(100 * full["delta_C"]["mean"], 2),
        ],
    }
    return {"nov14_published": NOV14, "this_run": got, "match": got == NOV14}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    frozen = run.verify_inputs()
    hashes = {
        "local_capture": run.digest(LOCAL_DB),
        "candle_archive": run.digest(screen.CANDLES),
        "candle_backfill": run.digest(BACKFILL),
    }
    manifest = json.loads(BACKFILL_MANIFEST.read_text(encoding="utf-8"))
    if hashes["local_capture"] != LOCAL_SHA256:
        raise SystemExit("Refusing: local capture differs from the Nov 13 snapshot.")
    if hashes["candle_backfill"] != manifest["archive_sha256"]:
        raise SystemExit("Refusing: candle backfill differs from its manifest.")
    contract = run.SPEC_DIR / "CONTRACT_PRODUCTION.json"
    cfg = json.loads(contract.read_text(encoding="utf-8"))
    late = copy.deepcopy(cfg)
    late["phases"] = LATE_PHASES
    parts = [
        read_window(screen.CAPTURE_DB, cfg, WARMUP, SPLIT),
        read_window(LOCAL_DB, late, SPLIT, SEAL),
    ]
    df = screen.add_labels(pd.concat(parts, ignore_index=True))
    frame = load_candles([screen.CANDLES, BACKFILL])
    df = screen.add_features(df, screen.product_arrays(frame))
    results = {}
    for board in screen.BOARDS:
        flags = screen.build_flags(df[df["stratum"] == board])
        results[board] = {
            name: screen.compare(flags, "ca", "a0", "a1", lo, hi)
            for name, (lo, hi) in WINDOWS.items()
        }
    last = pd.Timestamp(int(df["entered_ts"].max()), unit="s", tz="UTC")
    out = {
        "script_sha256": run.digest(Path(__file__)),
        "definitions_sha256": run.digest(Path(screen.__file__)),
        "frozen_inputs": frozen,
        "input_sha256": hashes,
        "seal_utc": "2026-11-13T00:00:00+00:00",
        "last_entry_loaded_utc": last.isoformat(),
        "candle_rows_loaded": int(len(frame)),
        "candle_products": int(frame["product_id"].nunique()),
        "last_candle_loaded_utc": pd.Timestamp(
            int(frame["ts"].max()), unit="s", tz="UTC"
        ).isoformat(),
        "seed": screen.SEED,
        "replicates": screen.REPS,
        "windows": WINDOWS,
        "primary_board": PRIMARY,
        "results": results,
        "reading": {board: reading(results[board]) for board in screen.BOARDS},
        "parity": parity(results[PRIMARY]["all"]),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(screen.clean(out), indent=1, allow_nan=False) + "\n"
    (args.out / "RESULTS.json").write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps(screen.clean({"reading": out["reading"][PRIMARY]})))
    print(json.dumps(screen.clean(out["parity"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
