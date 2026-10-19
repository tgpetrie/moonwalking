"""Do large one-day moves continue or reverse? A pre-registered, out-of-sample study.

Data: a read-only copy of the candle archive (hourly Coinbase USD candles,
~407 products, 2025-10 to 2026-10). Hourly candles are rebuilt into UTC days.

Design (fixed before any result was looked at; see docs/developer/MOVE_STUDY.md):
  event      a coin's close-to-close daily move >= +10% (up) or <= -10% (down)
  outcome    forward close-to-close return over 1, 3 and 7 days, minus the
             equal-weight average forward return of all liquid coins that same
             day (so market-wide drift is removed)
  features   six yes/no splits with thresholds fixed in advance (FEATURES below)
  split      discovery = first period, test = later period; forward windows that
             would cross the boundary are dropped (embargo)
  inference  moving-block bootstrap over calendar days (7-day blocks), so events
             on the same or neighbouring days are not counted as independent
  family     every hypothesis is reported; the number of tests is stated and
             Bonferroni-adjusted p-values are shown next to the raw ones

  python scripts/move_study/continuation_vs_reversal.py --archive archive_copy.sqlite --out data/move-study
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DAY = 86400
MOVE = 0.10
HORIZONS = (1, 3, 7)
COOLDOWN_DAYS = 7
MIN_EVENT_USD_VOLUME = 100_000
MIN_MEDIAN_USD_VOLUME = 50_000
FIRST_DAY, LAST_DAY = "2025-10-02", "2026-10-10"  # days wholly inside fetched hourly ranges
SPLIT_DAY = "2026-04-01"  # discovery < split <= test
BLOCK = 7
BOOT = 4000
SEED = 20261018

# name: (description, function(df) -> boolean Series). Fixed thresholds, chosen
# before looking at outcomes. Each is tested as "yes" and "no".
FEATURES = {
    "volume_spike": ("event-day $ volume >= 3x its 20-day median", lambda d: d.vol_ratio >= 3),
    "uptrend_into_event": ("prior 7-day return >= 0", lambda d: d.prior7 >= 0),
    "near_prior_high": ("close within 10% of the prior 30-day high", lambda d: d.close >= 0.9 * d.prior_high30),
    "closed_at_extreme": ("close in the move's direction: top 25% of range (up) / bottom 25% (down)", None),
    "broad_market_day": ("share of liquid coins with a positive day >= 60%", lambda d: d.breadth >= 0.6),
    "btc_up_day": ("BTC-USD close-to-close return >= 0", lambda d: d.btc_ret >= 0),
}


def load_daily(archive: Path) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{archive.as_posix()}?mode=ro", uri=True)
    h = pd.read_sql_query(
        "SELECT product_id, ts, open, high, low, close, volume FROM candles WHERE granularity=3600", conn
    )
    conn.close()
    h["day"] = h.ts // DAY
    h = h.sort_values(["product_id", "ts"])
    g = h.groupby(["product_id", "day"])
    d = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), vol=("volume", "sum"), hours=("ts", "count")).reset_index()
    first = pd.Timestamp(FIRST_DAY, tz="UTC").timestamp() // DAY
    last = pd.Timestamp(LAST_DAY, tz="UTC").timestamp() // DAY
    d = d[(d.day >= first) & (d.day <= last)].copy()
    d["usd_vol"] = d.vol * d.close
    return d


def build_panel(d: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    days = np.arange(int(d.day.min()), int(d.day.max()) + 1)
    close = d.pivot(index="day", columns="product_id", values="close").reindex(days)
    high = d.pivot(index="day", columns="product_id", values="high").reindex(days)
    low = d.pivot(index="day", columns="product_id", values="low").reindex(days)
    usd = d.pivot(index="day", columns="product_id", values="usd_vol").reindex(days)

    ret1 = close / close.shift(1) - 1  # NaN if either day had no trades
    med20 = usd.shift(1).rolling(20, min_periods=15).median()
    liquid = (usd >= MIN_EVENT_USD_VOLUME) & (med20 >= MIN_MEDIAN_USD_VOLUME)
    breadth = (ret1.where(liquid) > 0).sum(axis=1) / ret1.where(liquid).notna().sum(axis=1)
    btc_ret = ret1["BTC-USD"]

    # Added after the first run (see docs): trailing 20-day volatility quintile, ranked among
    # liquid coins each day. Volatile coins can lag the average for reasons unrelated to a move.
    vol20 = ret1.shift(1).rolling(20, min_periods=15).std()
    vol_q = np.floor(vol20.where(liquid).rank(axis=1, pct=True).clip(upper=0.9999) * 5)

    fwd, fwd_vm = {}, {}
    for k in HORIZONS:
        raw = close.shift(-k) / close - 1
        lo, hi = raw.where(liquid).stack().quantile([0.01, 0.99])
        raw = raw.clip(lo, hi)  # winsorise: a handful of thin-coin blow-ups must not decide a result
        market = raw.where(liquid).mean(axis=1)
        fwd[k] = raw.sub(market, axis=0)
        # same-day average forward return of liquid coins in the same volatility quintile
        matched = pd.DataFrame(np.nan, index=raw.index, columns=raw.columns)
        for q in range(5):
            cell = vol_q == q
            avg = raw.where(cell & liquid).mean(axis=1)
            matched = matched.where(~cell, pd.DataFrame(np.tile(avg.values[:, None], (1, raw.shape[1])), index=raw.index, columns=raw.columns))
        fwd_vm[k] = raw - matched

    feat = {
        "vol_ratio": usd / med20,
        "prior7": close.shift(1) / close.shift(8) - 1,
        "prior_high30": high.shift(1).rolling(30, min_periods=20).max(),
        "close": close,
        "range_pos": (close - low) / (high - low),
    }
    rows = []
    for direction, mask in (("up", ret1 >= MOVE), ("down", ret1 <= -MOVE)):
        ev = (mask & liquid).stack()
        ev = ev[ev].index
        last_event = {}
        for day, prod in sorted(ev):
            if prod in last_event and day - last_event[prod][0] <= COOLDOWN_DAYS and last_event[prod][1] == direction:
                last_event[prod] = (day, direction)  # chain inside the cooldown, count only the first
                continue
            last_event[prod] = (day, direction)
            rec = {"day": day, "product": prod, "direction": direction, "ret1": ret1.at[day, prod],
                   "btc_ret": btc_ret.at[day], "breadth": breadth.at[day]}
            for name, frame in feat.items():
                rec[name] = frame.at[day, prod]
            for k in HORIZONS:
                rec[f"x{k}"] = fwd[k].at[day, prod]
                rec[f"m{k}"] = fwd_vm[k].at[day, prod]
            rows.append(rec)
    ev = pd.DataFrame(rows)
    ev["closed_at_extreme"] = np.where(ev.direction == "up", ev.range_pos >= 0.75, ev.range_pos <= 0.25)
    return ev, days


def block_bootstrap_p(sums: np.ndarray, counts: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float, float]:
    """Mean excess per event, with a moving-block bootstrap over calendar days."""
    n = len(sums)
    total = counts.sum()
    if total == 0:
        return float("nan"), float("nan"), float("nan"), float("nan")
    obs = sums.sum() / total
    nblocks = int(np.ceil(n / BLOCK))
    starts = rng.integers(0, max(1, n - BLOCK + 1), size=(BOOT, nblocks))
    idx = (starts[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(BOOT, -1)[:, :n]
    s, c = sums[idx].sum(axis=1), counts[idx].sum(axis=1)
    ok = c > 0
    boot = s[ok] / c[ok]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    p = 2 * min((boot <= 0).mean(), (boot >= 0).mean())
    return float(obs), float(lo), float(hi), float(min(1.0, p))


def summarise(ev: pd.DataFrame, days: np.ndarray, k: int, period: tuple[int, int], rng, col: str = "x") -> dict | None:
    start, end = period
    sel = ev[(ev.day >= start) & (ev.day + k <= end) & ev[f"{col}{k}"].notna()]
    if len(sel) < 20:
        return {"events": int(len(sel)), "note": "fewer than 20 events"}
    idx = sel.day.values - days[0]
    sums = np.bincount(idx, weights=sel[f"{col}{k}"].values, minlength=len(days))
    counts = np.bincount(idx, minlength=len(days)).astype(float)
    window = slice(start - days[0], end - days[0] + 1)
    mean, lo, hi, p = block_bootstrap_p(sums[window], counts[window], rng)
    x = sel[f"{col}{k}"]
    top = sel["product"].value_counts()
    return {"events": int(len(sel)), "dates": int((counts > 0).sum()), "mean_excess_pct": round(mean * 100, 2),
            "ci95_pct": [round(lo * 100, 2), round(hi * 100, 2)], "median_excess_pct": round(float(x.median()) * 100, 2),
            "share_positive": round(float((x > 0).mean()), 3), "p_raw": round(max(p, 1 / BOOT), 5),
            "top_coin_share": round(float(top.iloc[0] / len(sel)), 3), "distinct_coins": int(len(top))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archive", required=True, help="read-only copy of candle_archive.sqlite")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    d = load_daily(Path(args.archive))
    ev, days = build_panel(d)
    first, split, last = int(days[0]), int(pd.Timestamp(SPLIT_DAY, tz="UTC").timestamp() // DAY), int(days[-1])
    periods = {"discovery": (first, split - 1), "test": (split, last)}
    rng = np.random.default_rng(SEED)

    splits = [("all events", None, None)]
    for name, (_, fn) in FEATURES.items():
        splits += [(f"{name}=yes", name, True), (f"{name}=no", name, False)]

    results = []
    for direction in ("up", "down"):
        e = ev[ev.direction == direction]
        for label, name, val in splits:
            sub = e
            if name is not None:
                flag = e["closed_at_extreme"] if name == "closed_at_extreme" else FEATURES[name][1](e)
                sub = e[flag.fillna(False).astype(bool) == val]
            for k in HORIZONS:
                for adj, col in (("market_adjusted", "x"), ("volatility_matched", "m")):
                    row = {"direction": direction, "split": label, "horizon_days": k, "adjustment": adj}
                    for pname, period in periods.items():
                        row[pname] = summarise(sub, days, k, period, rng, col)
                    results.append(row)

    n_tests = len(results) // 2  # tests per adjustment
    survivors = {"market_adjusted": 0, "volatility_matched": 0}
    for r in results:
        first_half = r["discovery"]
        if first_half and "p_raw" in first_half:
            first_half["p_bonferroni"] = round(min(1.0, first_half["p_raw"] * n_tests), 4)
            if first_half["p_bonferroni"] < 0.05:
                survivors[r["adjustment"]] += 1
    for r in results:
        disc, test = r["discovery"], r["test"]
        if test and "p_raw" in test:
            # confirmation family = only what survived discovery
            test["p_bonferroni"] = round(min(1.0, test["p_raw"] * max(1, survivors[r["adjustment"]])), 4)
        ok = disc and test and "p_raw" in disc and "p_raw" in test
        r["replicates"] = bool(
            ok and disc["p_bonferroni"] < 0.05 and test["p_bonferroni"] < 0.05
            and np.sign(disc["mean_excess_pct"]) == np.sign(test["mean_excess_pct"])
        )

    out = {
        "design": {"move": MOVE, "horizons": HORIZONS, "cooldown_days": COOLDOWN_DAYS, "block_days": BLOCK, "bootstrap": BOOT, "seed": SEED,
                   "days": [FIRST_DAY, LAST_DAY], "split_day": SPLIT_DAY, "tests_per_adjustment": n_tests, "discovery_survivors": survivors,
                   "liquidity": {"event_usd_volume_min": MIN_EVENT_USD_VOLUME, "median_usd_volume_min": MIN_MEDIAN_USD_VOLUME},
                   "features": {k: v[0] for k, v in FEATURES.items()}, "replicates_means": "Bonferroni p<0.05 over all tests in discovery, AND Bonferroni p<0.05 in test over only the discovery survivors, AND same sign",
                   "post_hoc": "The volatility_matched adjustment and the stricter test-period family were added after the first run, which showed up and down moves both lagging the market average.",
                   "p_floor": "p-values cannot go below 1/bootstrap resamples"},
        "panel": {"products": int(d.product_id.nunique()), "coin_days": int(len(d))},
        "event_counts": {f"{dr}": int((ev.direction == dr).sum()) for dr in ("up", "down")},
        "results": results,
    }
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "continuation_vs_reversal.json").write_text(json.dumps(out, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    print(out["panel"], out["event_counts"], "tests", n_tests)
    print("survivors", survivors)
    for r in results:
        if r["replicates"] or r["split"] == "all events":
            a, t = r["discovery"], r["test"]
            print(("REPL " if r["replicates"] else "     "), r["adjustment"][:6], r["direction"], r["split"], r["horizon_days"],
                  a.get("events"), a.get("mean_excess_pct"), a.get("p_bonferroni"), "|", t.get("events"), t.get("mean_excess_pct"), t.get("p_bonferroni"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
