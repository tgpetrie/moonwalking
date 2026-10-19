"""Robustness checks for the large-move study, answering Gemini's ranked critique.

All checks are post hoc and descriptive. They ask whether the headline result
(after a +10% day, coins trail volatility-matched peers) survives each
objection. Nothing here was preregistered.

  python scripts/move_study/robustness.py --daily-dir <daily_all> --archive <archive copy> \
      --causes data/move-study/cause_review_gemini_2026-10-19.csv --out data/move-study

Checks (numbering follows the critique):
  1 causes re-bucketed to sources dated on or before the event day
  2 medians, trimmed and winsorised means, sign shares
  3 calendar-time cohorts: each event day weighted once
  4 first hour after the close vs the rest of the next day (hourly archive)
  5 liquidity tiers by prior 20-day median dollar volume
  6 relative volume x idiosyncratic size
  7 new listings vs established, delisted vs online
  8 each coin's own average subtracted (coin fixed effect)
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import continuation_vs_reversal as cs  # noqa: E402

DAY = cs.DAY
SPLIT = "2025-01-01"
FIRST, LAST = "2022-01-03", "2026-10-17"


def day_of(text: str) -> int:
    return int(pd.Timestamp(text, tz="UTC").timestamp() // DAY)


def stats(x: pd.Series) -> dict:
    x = x.dropna()
    if len(x) < 10:
        return {"n": int(len(x))}
    s = np.sort(x.values)
    n = len(s)
    t5 = s[int(0.05 * n): n - int(0.05 * n)]
    t10 = s[int(0.10 * n): n - int(0.10 * n)]
    w5 = np.clip(s, s[int(0.05 * n)], s[n - 1 - int(0.05 * n)])
    return {"n": int(n), "mean_pct": round(float(s.mean()) * 100, 2), "median_pct": round(float(np.median(s)) * 100, 2),
            "trimmed5_pct": round(float(t5.mean()) * 100, 2), "trimmed10_pct": round(float(t10.mean()) * 100, 2),
            "winsor5_pct": round(float(w5.mean()) * 100, 2), "share_positive": round(float((s > 0).mean()), 3)}


def boot(ev: pd.DataFrame, days: np.ndarray, col: str, k: int, period: tuple[int, int], rng) -> dict:
    out = cs.summarise(ev.rename(columns={col: f"z{k}"}), days, k, period, rng, "z")
    return {key: out.get(key) for key in ("events", "mean_excess_pct", "ci95_pct", "median_excess_pct", "p_raw")}


def cohort(ev: pd.DataFrame, days: np.ndarray, col: str, period: tuple[int, int], k: int, rng, reps: int = 4000) -> dict:
    """Average each event day's events first, then average days (each day weighted once)."""
    start, end = period
    sel = ev[(ev.day >= start) & (ev.day + k <= end) & ev[col].notna()]
    by_day = sel.groupby("day")[col].mean()
    cal = pd.Series(np.nan, index=np.arange(start, end + 1))
    cal.loc[by_day.index] = by_day.values
    vals, have = np.nan_to_num(cal.values), (~np.isnan(cal.values)).astype(float)
    n, B = len(vals), cs.BLOCK
    nb = int(np.ceil(n / B))
    starts = rng.integers(0, max(1, n - B + 1), size=(reps, nb))
    idx = (starts[:, :, None] + np.arange(B)[None, None, :]).reshape(reps, -1)[:, :n]
    s, c = vals[idx].sum(axis=1), have[idx].sum(axis=1)
    bm = s[c > 0] / c[c > 0]
    mean = float(by_day.mean())
    lo, hi = np.percentile(bm, [2.5, 97.5])
    p = 2 * min((bm <= 0).mean(), (bm >= 0).mean())
    return {"event_days": int(len(by_day)), "mean_of_daily_means_pct": round(mean * 100, 2),
            "ci95_pct": [round(lo * 100, 2), round(hi * 100, 2)], "p_raw": round(max(p, 1 / reps), 5)}


def periods_for(days: np.ndarray) -> dict:
    split = day_of(SPLIT)
    return {"discovery_2022_2024": (int(days[0]), split - 1), "test_2025_2026": (split, int(days[-1]))}


def first_hour_check(archive: Path, hourly_events: pd.DataFrame) -> dict:
    """Split next-day relative return into 00:00-01:00 UTC and 01:00-24:00 UTC."""
    conn = sqlite3.connect(f"file:{archive.as_posix()}?mode=ro", uri=True)
    h = pd.read_sql_query("SELECT product_id, ts, close, volume FROM candles WHERE granularity=3600", conn)
    conn.close()
    close = h.pivot(index="ts", columns="product_id", values="close")
    up = hourly_events[hourly_events.direction == "up"]
    rows = []
    for _, e in up.iterrows():
        t_close = (e.day + 1) * DAY - 3600       # last hourly candle of day t (23:00 open, closes 24:00)
        h1 = (e.day + 1) * DAY                    # 00:00-01:00 of day t+1
        end = (e.day + 2) * DAY - 3600            # last hour of day t+1
        try:
            c0, c1, c24 = close.at[t_close, e["product"]], close.at[h1, e["product"]], close.at[end, e["product"]]
        except KeyError:
            continue
        if not all(np.isfinite([c0, c1, c24])):
            continue
        # market: equal-weight average of all coins with prices at those hours
        try:
            m0, m1, m24 = close.loc[t_close], close.loc[h1], close.loc[end]
        except KeyError:
            continue
        ok = m0.notna() & m1.notna() & m24.notna()
        mk_h1 = float((m1[ok] / m0[ok] - 1).clip(-0.5, 0.5).mean())
        mk_rest = float((m24[ok] / m1[ok] - 1).clip(-0.5, 0.5).mean())
        rows.append({"first_hour": c1 / c0 - 1 - mk_h1, "rest_of_day": c24 / c1 - 1 - mk_rest, "full_day": c24 / c0 - 1 - (mk_h1 + mk_rest)})
    df = pd.DataFrame(rows)
    out = {k: stats(df[k]) for k in ("first_hour", "rest_of_day", "full_day")}
    out["note"] = "Market-adjusted with the equal-weight hourly average of archived coins. Hourly archive Oct 2025 to Oct 2026 only."
    if out["full_day"].get("mean_pct"):
        out["share_of_day1_mean_in_first_hour"] = round(out["first_hour"]["mean_pct"] / out["full_day"]["mean_pct"], 2)
    return out


def causes_check(causes: Path, hourly_events: pd.DataFrame) -> dict:
    with open(causes, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ev = hourly_events.assign(date=pd.to_datetime(hourly_events.day * DAY, unit="s").dt.strftime("%Y-%m-%d"))
    m = pd.DataFrame(rows).merge(ev[["date", "product", "m1", "m3", "m7"]], on=["date", "product"], how="left")
    m = m[m.group == "largest"]
    pub = m.source_published_utc.str.strip().str[:10]
    m["known_at_close"] = (m.cause_category != "no_known_cause") & (pub != "") & (pub <= m.date)
    m["protocol_at_close"] = m.known_at_close & (m.cause_category == "protocol_or_partnership_news")
    out = {}
    for label in ("known_at_close", "protocol_at_close"):
        g = {str(bool(v)): {k: stats(sub[k].astype(float)) | {"n": int(sub[k].notna().sum())} for k in ("m1", "m7")}
             for v, sub in m.groupby(label)}
        out[label] = g
    k, u = m[m.known_at_close].m7.dropna().values, m[~m.known_at_close].m7.dropna().values
    rng = np.random.default_rng(7)
    allv = np.concatenate([k, u])
    obs_mean, obs_med = k.mean() - u.mean(), np.median(k) - np.median(u)
    pm, pd_ = [], []
    for _ in range(20000):
        s = rng.permutation(allv)
        pm.append(s[: len(k)].mean() - s[len(k):].mean()); pd_.append(np.median(s[: len(k)]) - np.median(s[len(k):]))
    out["known_vs_unknown_7d"] = {"n_known": int(len(k)), "n_unknown": int(len(u)),
                                  "mean_diff_pts": round(obs_mean * 100, 1), "p_mean": round(float(np.mean(np.abs(pm) >= abs(obs_mean))), 3),
                                  "median_diff_pts": round(obs_med * 100, 1), "p_median": round(float(np.mean(np.abs(pd_) >= abs(obs_med))), 3)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daily-dir", required=True)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--causes", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    d = cs.load_daily_dir(Path(args.daily_dir), FIRST, LAST)
    ev, days, _ = cs.build_panel(d)
    status = {p["id"]: p["status"] for p in json.loads((Path(args.daily_dir) / "products.json").read_text(encoding="utf-8"))}
    up = ev[ev.direction == "up"].copy()
    rng = np.random.default_rng(cs.SEED)
    per = periods_for(days)
    res: dict = {"scope": "up-moves of +10% or more, Coinbase USD products 2022-2026 (daily), unless stated",
                 "events": int(len(up)), "post_hoc": True}

    # 2: distribution
    res["2_distribution"] = {pname: {f"{k}d": stats(up[(up.day >= a) & (up.day + k <= b)][f"m{k}"]) for k in cs.HORIZONS}
                             for pname, (a, b) in per.items()}
    # 3: calendar-time cohorts
    res["3_calendar_cohorts"] = {pname: {f"{k}d": cohort(up, days, f"m{k}", period, k, rng) for k in cs.HORIZONS}
                                 for pname, period in per.items()}
    # 5: liquidity tiers
    tiers = {"<$1M": up.med20_usd < 1e6, "$1M-$10M": (up.med20_usd >= 1e6) & (up.med20_usd < 1e7), ">=$10M": up.med20_usd >= 1e7}
    res["5_liquidity_tiers"] = {t: {pname: {f"{k}d": boot(up[mask], days, f"m{k}", k, period, rng) for k in (1, 7)}
                                    for pname, period in per.items()} for t, mask in tiers.items()}
    # 6: relative volume x idiosyncratic size
    idio = (up.ret1 - up.btc_ret) >= 0.15
    hv = up.vol_ratio >= 5
    cells = {"high volume, idiosyncratic": hv & idio, "high volume, beta-like": hv & ~idio,
             "low volume, idiosyncratic": ~hv & idio, "low volume, beta-like": ~hv & ~idio}
    res["6_volume_x_idiosyncratic"] = {c: {pname: {f"{k}d": boot(up[mask], days, f"m{k}", k, period, rng) for k in (1, 7)}
                                           for pname, period in per.items()} for c, mask in cells.items()}
    # 7: listing age and status
    seasoned = up.day - days[0] >= 90
    groups7 = {"listed < 90 days": seasoned & (up.listing_age_days < 90), "listed >= 90 days": seasoned & (up.listing_age_days >= 90),
               "delisted since": up["product"].map(status) != "online", "still online": up["product"].map(status) == "online"}
    res["7_listing_age_and_status"] = {g: {pname: {f"{k}d": boot(up[mask], days, f"m{k}", k, period, rng) for k in (1, 7)}
                                           for pname, period in per.items()} for g, mask in groups7.items()}
    # 8: coin fixed effect
    for k in cs.HORIZONS:
        up[f"fe{k}"] = up[f"m{k}"] - up[f"coin_mean{k}"]
    res["8_coin_fixed_effect"] = {pname: {f"{k}d": boot(up, days, f"fe{k}", k, period, rng) for k in cs.HORIZONS}
                                  for pname, period in per.items()}
    res["8_note"] = "coin average taken over the whole sample (in-sample), so this is a stress test, not a tradable adjustment"

    # 1 and 4 use the hourly-archive run (the cause table's events came from it)
    hd = cs.load_daily(Path(args.archive))
    hev, _, _ = cs.build_panel(hd)
    res["1_causes_at_close"] = causes_check(Path(args.causes), hev)
    res["4_first_hour"] = first_hour_check(Path(args.archive), hev)

    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "robustness.json").write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8", newline=cs.LF)
    print(json.dumps(res, indent=1, default=float)[:20000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
