"""Walk-forward evaluation of the Elliott ABC chart engine, frozen definitions.

    python scripts/scoring_experiment/evaluate_elliott_abc_20261115.py

The engine (`backend/elliott_wave_engine.py`) is used as shipped: ATR multiple
2.2, its fib bounds, its confluence weights and its 0.50 threshold. Nothing is
tuned here. The protocol is
`docs/research/ELLIOTT_ABC_CHART_ENGINE_PROTOCOL_20261115.md`, committed before
this script was first run on outcomes.

Declared before the run:

* Candles: one-minute candles from the archive and the 2026-11-13 backfill,
  merged at their seam, resampled to wall-clock 15m, 1h and 4h bars. Every read
  sees only bars closed by its decision time, in a trailing 300-bar window with
  up to 120 closed higher-timeframe bars (4h for 15m and 1h, 1d for 4h).
  Candles and entries from 2026-11-13 00:00 UTC stay sealed.
* Part A: the 100 USD products with the most dollar volume in the archive from
  2026-09-07 to 2026-10-11, pegged products excluded. Signals whose bar closes
  from 2026-10-13 00:00 to 2026-11-12 00:00 UTC, so each 24h outcome ends
  before the seal. Entry is the close of the signal bar, the target is the
  wave B extreme and the stop is the engine's invalidation price. Outcomes are
  read from one-minute candles opening at or after the entry time; a minute
  that touches both levels counts as the stop.
* Part B: the A1 flags of `confirm_a1_gate_20261115`, same population, same
  labels, same paired daily comparison. Arms keep the A1 flags whose 15m or 1h
  chart read, taken at the flag time, shows the stated structure.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import zlib
from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for extra in (HERE, ROOT / "backend"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import confirm_a1_gate_20261115 as a1  # noqa: E402
import elliott_wave_engine as engine  # noqa: E402

screen, run, carbon = a1.screen, a1.run, a1.carbon
OUT = ROOT / "docs/research/results/elliott_abc_20261115"
PROTOCOL = ROOT / "docs/research/ELLIOTT_ABC_CHART_ENGINE_PROTOCOL_20261115.md"
ARCHIVE, BACKFILL, SEAL = screen.CANDLES, a1.BACKFILL, a1.SEAL

HISTORY_START = screen.stamp("2026-09-07")
RANK_WINDOW = (screen.stamp("2026-09-07"), screen.stamp("2026-10-12"))
A_START = screen.stamp("2026-10-13")
HORIZONS = {"4h": 4 * 3600, "12h": 12 * 3600, "24h": 24 * 3600}
A_END = SEAL - max(HORIZONS.values())
A_HALVES = {
    "first_half": (A_START, screen.stamp("2026-10-28")),
    "second_half": (screen.stamp("2026-10-28"), A_END),
}
TIMEFRAMES = {"15m": 900, "1h": 3600, "4h": 14400}
HIGHER = {"15m": 14400, "1h": 14400, "4h": 86400}
WINDOW_BARS, HIGHER_BARS = 300, 120
UNIVERSE_N, CORE_N, PEG_RANGE = 100, 40, 0.02
PLACEBOS, COST = 20, 0.0025
PRIMARY_CELL = ("1h", "bullish", "complete")
MIN_EVENTS, MIN_CONFLUENCE_EVENTS = 100, 50
B_TIMEFRAMES = ("15m", "1h")
B_ARMS = ("w_abc_conf", "w_abc", "w_trend", "w_no_opp")
B_PRIMARY_ARM = "w_abc_conf"
B_RULE = {"dn_mean": 0.0100, "dn_lo": 0.0, "min_days": 20}
METRICS = [
    f"{m}_{h}" for h in HORIZONS for m in ("hit", "stop", "R", "Rnet", "mfe", "mae")
]
COMPARED = [
    "hit_24h",
    "R_24h",
    "mfe_24h",
    "mae_24h",
    "hit_4h",
    "R_4h",
    "hit_12h",
    "R_12h",
]


# ---------- candles ----------


def load_minutes(product: str, lo: int = HISTORY_START, hi: int = SEAL) -> np.ndarray:
    """One-minute candles `[ts, low, high, open, close, volume]`, archive first."""
    sql = """SELECT ts, low, high, open, close, volume FROM candles
             WHERE product_id = ? AND granularity = 60 AND ts >= ? AND ts < ?
             ORDER BY ts"""
    parts = []
    for path in (ARCHIVE, BACKFILL):
        with closing(carbon.read_only(path)) as con:
            rows = con.execute(sql, (product, lo, min(hi, SEAL))).fetchall()
        if rows:
            parts.append(np.asarray(rows, dtype=float))
    return merge_minutes(parts)


def merge_minutes(parts: list) -> np.ndarray:
    """Sorted, valid, one row per minute; the first store listed wins a tie."""
    if not parts:
        return np.empty((0, 6))
    m = np.concatenate(parts)
    ok = np.isfinite(m).all(axis=1) & (m[:, 1:5] > 0).all(axis=1) & (m[:, 5] >= 0)
    ok &= (m[:, 0] % 60 == 0) & (m[:, 0] < SEAL)
    m = m[ok]
    m = m[np.argsort(m[:, 0], kind="stable")]
    keep = np.r_[True, m[1:, 0] != m[:-1, 0]] if len(m) else np.zeros(0, dtype=bool)
    m = m[keep]
    a1.assert_sealed(m[:, 0])
    return m


def resample(minutes: np.ndarray, seconds: int) -> np.ndarray:
    """Wall-clock bars `[open_ts, low, high, open, close, volume]`."""
    if not len(minutes):
        return np.empty((0, 6))
    bucket = minutes[:, 0] // seconds * seconds
    starts = np.flatnonzero(np.r_[True, bucket[1:] != bucket[:-1]])
    ends = np.r_[starts[1:], len(minutes)] - 1
    return np.column_stack(
        [
            bucket[starts],
            np.minimum.reduceat(minutes[:, 1], starts),
            np.maximum.reduceat(minutes[:, 2], starts),
            minutes[starts, 3],
            minutes[ends, 4],
            np.add.reduceat(minutes[:, 5], starts),
        ]
    )


def closed_count(bars: np.ndarray, seconds: int, cut: float) -> int:
    """How many bars have closed by `cut` (bar close = open + seconds)."""
    return int(np.searchsorted(bars[:, 0] + seconds, cut, side="right"))


def read_at(bars, seconds, hbars, hseconds, cut) -> dict | None:
    """The engine's read at `cut`, from closed bars only."""
    n = closed_count(bars, seconds, cut)
    if n < engine.MIN_CANDLES:
        return None
    hn = closed_count(hbars, hseconds, cut)
    window = bars[max(0, n - WINDOW_BARS) : n].tolist()
    higher = hbars[max(0, hn - HIGHER_BARS) : hn].tolist()
    return engine.analyze_wave_structure(window, higher_tf_candles=higher)


def live_abc(res: dict | None) -> bool:
    """An ABC that is complete and unresolved, or has wave C inside its zone."""
    if not res:
        return False
    state = (res["active_pattern"], res["status"])
    return state in {("abc_complete", "confirmed"), ("abc_in_progress", "in_c_zone")}


# ---------- Part A: signals ----------


def walk_events(bars, seconds, hbars, hseconds, lo, hi) -> tuple[list, dict, dict]:
    """Signals whose bar closes in `[lo, hi)`, each read at its own bar close.

    `complete` fires on the bar that confirms wave C. `zone` fires on the first
    bar that finds wave C inside its projected zone. Also returns the bars that
    confirmed any swing low or high, for the pivot placebo.
    """
    closes = bars[:, 0] + seconds
    k0, k1 = (int(np.searchsorted(closes, t, side="left")) for t in (lo, hi))
    events, seen = [], set()
    pivot_bars = {"low": [], "high": []}
    tally = {"reads": 0, "target_already_reached": 0, "no_room": 0}
    for k in range(k0, k1):
        res = read_at(bars, seconds, hbars, hseconds, closes[k])
        if res is None or not res["available"]:
            continue
        tally["reads"] += 1
        n = min(k + 1, WINDOW_BARS)
        last = res["pivots"][-1] if res["pivots"] else None
        fresh = last is not None and last["confirmed_at_index"] == n - 1
        if fresh:
            pivot_bars[last["kind"]].append(k)
        pattern, status = res["active_pattern"], res["status"]
        if pattern == "abc_complete" and fresh:
            if status != "confirmed":
                tally["target_already_reached"] += 1
                continue
            kind, key = "complete", ("complete", res["bias"], last["ts"])
        elif pattern == "abc_in_progress" and status == "in_c_zone":
            pts = {p["label"]: p["ts"] for p in res["wave_points"]}
            kind, key = "zone", ("zone", res["bias"], pts["0"], pts["B"])
        else:
            continue
        if key in seen:
            continue
        seen.add(key)
        sgn = 1 if res["bias"] == "bullish" else -1
        entry, stop, target = bars[k, 4], res["invalidation_price"], res["target_price"]
        if not sgn * stop < sgn * entry < sgn * target:
            tally["no_room"] += 1
            continue
        events.append(
            {
                "k": k,
                "type": kind,
                "bias": res["bias"],
                "sgn": sgn,
                "entry_ts": int(closes[k]),
                "entry": float(entry),
                "stop": float(stop),
                "target": float(target),
                "conf": bool(res["confluence_confirmed"]),
                "score": res["confluence_score"],
                "confidence": res["confidence"],
                "b_retrace": res["fib_ratios"]["b_retrace_of_a"],
                "c_projection": res["fib_ratios"]["c_projection_of_a"],
                "factors": {f["name"]: f["state"] for f in res["confluence_factors"]},
            }
        )
    return events, pivot_bars, tally


def outcome(minutes, entry_ts, entry, stop, target, sgn) -> dict:
    """Forward path over each horizon from the first minute at or after entry."""
    if entry_ts + max(HORIZONS.values()) > SEAL:
        raise SystemExit("Refusing: an outcome window crosses the 2026-11-13 seal.")
    ts = minutes[:, 0]
    i0 = int(np.searchsorted(ts, entry_ts, side="left"))
    risk, reward = sgn * (entry - stop), sgn * (target - entry)
    out = {"rr": reward / risk, "risk_pct": risk / entry}
    fav_col, adv_col = (2, 1) if sgn > 0 else (1, 2)
    for name, span in HORIZONS.items():
        i1 = int(np.searchsorted(ts, entry_ts + span, side="left"))
        fav, adv = sgn * minutes[i0:i1, fav_col], sgn * minutes[i0:i1, adv_col]
        if i1 <= i0:
            vals = {"hit": 0.0, "stop": 0.0, "R": 0.0, "mfe": 0.0, "mae": 0.0}
        else:
            hit, cut = fav >= sgn * target, adv < sgn * stop
            t = int(np.argmax(hit)) if hit.any() else None
            s = int(np.argmax(cut)) if cut.any() else None
            if s is not None and (t is None or s <= t):
                won, lost, r = 0.0, 1.0, -1.0
            elif t is not None:
                won, lost, r = 1.0, 0.0, reward / risk
            else:
                won, lost = 0.0, 0.0
                r = sgn * (minutes[i1 - 1, 4] - entry) / risk
            vals = {
                "hit": won,
                "stop": lost,
                "R": r,
                # Signed so that favorable excursion is >= 0 and adverse <= 0.
                "mfe": sgn * (sgn * fav.max() / entry - 1.0),
                "mae": sgn * (sgn * adv.min() / entry - 1.0),
            }
        vals["Rnet"] = vals["R"] - COST * entry / risk
        out.update({f"{m}_{name}": v for m, v in vals.items()})
    return out


def placebo(minutes, bars, candidates, event, rng) -> dict:
    """Mean outcome of entries at other bars with the event's percent distances."""
    pool = np.asarray([k for k in candidates if k != event["k"]], dtype=int)
    if not len(pool):
        return {m: math.nan for m in METRICS}
    picks = rng.choice(pool, size=min(PLACEBOS, len(pool)), replace=False)
    stop_x, target_x = event["stop"] / event["entry"], event["target"] / event["entry"]
    seconds = int(event["seconds"])
    rows = []
    for k in picks:
        px = bars[k, 4]
        ts = int(bars[k, 0]) + seconds
        rows.append(outcome(minutes, ts, px, px * stop_x, px * target_x, event["sgn"]))
    return {m: float(np.mean([r[m] for r in rows])) for m in METRICS}


def part_a_product(product: str) -> dict:
    """Every Part A signal for one product, with outcomes and both placebos."""
    minutes = load_minutes(product)
    rows, tallies = [], {}
    for tf_i, (tf, seconds) in enumerate(TIMEFRAMES.items()):
        bars = resample(minutes, seconds)
        hbars = resample(minutes, HIGHER[tf])
        events, pivot_bars, tally = walk_events(
            bars, seconds, hbars, HIGHER[tf], A_START, A_END
        )
        tallies[tf] = tally
        closes = bars[:, 0] + seconds
        every = range(
            int(np.searchsorted(closes, A_START, side="left")),
            int(np.searchsorted(closes, A_END, side="left")),
        )
        fired = {(e["bias"], e["k"]) for e in events if e["type"] == "complete"}
        for n, e in enumerate(events):
            e.update(product=product, tf=tf, seconds=seconds)
            e.update(
                outcome(
                    minutes, e["entry_ts"], e["entry"], e["stop"], e["target"], e["sgn"]
                )
            )
            seed = [screen.SEED, zlib.crc32(product.encode()), tf_i, n]
            rng = np.random.default_rng(seed)
            same_kind = pivot_bars["low" if e["sgn"] > 0 else "high"]
            plain = [k for k in same_kind if (e["bias"], k) not in fired]
            for tag, pool in (("rand", every), ("piv", plain)):
                got = placebo(minutes, bars, pool, e, rng)
                e.update({f"{tag}_{m}": v for m, v in got.items()})
            factors = e.pop("factors")
            e.update({f"f_{name}": state for name, state in factors.items()})
            rows.append(e)
    return {
        "product": product,
        "rows": rows,
        "tallies": tallies,
        "minutes": len(minutes),
    }


# ---------- Part A: universe and statistics ----------


def universe() -> dict:
    """USD products ranked by pre-window dollar volume, pegged ones excluded."""
    sql = """SELECT product_id, SUM(close * volume), MIN(low), MAX(high) FROM candles
             WHERE granularity = 60 AND ts >= ? AND ts < ? GROUP BY product_id"""
    with closing(carbon.read_only(ARCHIVE)) as con:
        rows = con.execute(sql, RANK_WINDOW).fetchall()
    with closing(carbon.read_only(BACKFILL)) as con:
        later = {r[0] for r in con.execute("SELECT DISTINCT product_id FROM candles")}
    return rank_universe(rows, later)


def rank_universe(rows: list, later: set) -> dict:
    ranked, pegged = [], []
    for product, dollars, low, high in rows:
        if not product.endswith("-USD") or product not in later or not dollars:
            continue
        if high / low - 1.0 < PEG_RANGE:
            pegged.append(product)
            continue
        ranked.append((-dollars, product))
    ranked.sort()
    names = [p for _, p in ranked[:UNIVERSE_N]]
    return {
        "products": names,
        "core": names[:CORE_N],
        "pegged_excluded": sorted(pegged),
    }


def chunk_of(entry_ts) -> np.ndarray:
    """Three-day block index, counted from the first Part A day."""
    return ((np.asarray(entry_ts) - A_START) // 86400 // screen.BLOCK).astype(int)


def boot_diff(chunk_a, a, chunk_b=None, b=None) -> dict:
    """Mean of `a` (minus mean of `b`) with a three-day block percentile interval."""
    a = np.asarray(a, dtype=float)
    keep = np.isfinite(a)
    a, chunk_a = a[keep], np.asarray(chunk_a)[keep]
    two = b is not None
    if two:
        b = np.asarray(b, dtype=float)
        keep = np.isfinite(b)
        b, chunk_b = b[keep], np.asarray(chunk_b)[keep]
    if not len(a) or (two and not len(b)):
        return {"mean": None, "lo": None, "hi": None, "n": int(len(a))}
    n_chunks = math.ceil((A_END - A_START) / 86400 / screen.BLOCK)
    sa, na = np.bincount(chunk_a, a, n_chunks), np.bincount(chunk_a, None, n_chunks)
    point = a.mean()
    pick = np.random.default_rng(screen.SEED).integers(
        0, n_chunks, (screen.REPS, n_chunks)
    )
    with np.errstate(invalid="ignore", divide="ignore"):
        means = sa[pick].sum(axis=1) / na[pick].sum(axis=1)
        if two:
            sb, nb = np.bincount(chunk_b, b, n_chunks), np.bincount(
                chunk_b, None, n_chunks
            )
            point -= b.mean()
            means = means - sb[pick].sum(axis=1) / nb[pick].sum(axis=1)
    lo, hi = np.nanpercentile(means, [2.5, 97.5])
    out = {"mean": float(point), "lo": float(lo), "hi": float(hi), "n": int(len(a))}
    if two:
        out["n_other"] = int(len(b))
    return out


def describe(g: pd.DataFrame, prefix: str = "") -> dict:
    out = {"n": int(len(g))}
    if not len(g):
        return out
    for m in METRICS:
        out[m] = float(g[prefix + m].mean())
    if not prefix:
        out["open_24h"] = float(1.0 - g["hit_24h"].mean() - g["stop_24h"].mean())
        out["R_24h_median"] = float(g["R_24h"].median())
        out["rr_planned_median"] = float(g["rr"].median())
        out["risk_pct_median"] = float(g["risk_pct"].median())
        out["products"] = int(g["product"].nunique())
        out["days"] = int((g["entry_ts"] // 86400).nunique())
    return out


def cell_summary(g: pd.DataFrame) -> dict:
    """One timeframe, bias and signal type: groups, placebos and comparisons."""
    conf, plain = g[g["conf"]], g[~g["conf"]]
    ch, ch_c, ch_p = (
        chunk_of(g["entry_ts"]),
        chunk_of(conf["entry_ts"]),
        chunk_of(plain["entry_ts"]),
    )
    out = {
        "groups": {
            "abc_geometry_all": describe(g),
            "abc_with_confluence": describe(conf),
            "abc_without_confluence": describe(plain),
            "placebo_random_bar": describe(g, "rand_"),
            "placebo_other_pivot": describe(g, "piv_"),
            "placebo_random_bar_for_confluence": describe(conf, "rand_"),
        },
        "compare": {},
    }
    for m in COMPARED:
        out["compare"][m] = {
            "confluence_minus_all_geometry": boot_diff(ch_c, conf[m], ch, g[m]),
            "confluence_minus_without": boot_diff(ch_c, conf[m], ch_p, plain[m]),
            "geometry_minus_random_placebo": boot_diff(ch, g[m] - g["rand_" + m]),
            "confluence_minus_random_placebo": boot_diff(
                ch_c, conf[m] - conf["rand_" + m]
            ),
            "geometry_minus_pivot_placebo": boot_diff(ch, g[m] - g["piv_" + m]),
            "confluence_minus_pivot_placebo": boot_diff(
                ch_c, conf[m] - conf["piv_" + m]
            ),
        }
    out["halves"] = {
        name: {
            "abc_geometry_all": describe(
                g[(g["entry_ts"] >= lo) & (g["entry_ts"] < hi)]
            ),
            "abc_with_confluence": describe(
                conf[(conf["entry_ts"] >= lo) & (conf["entry_ts"] < hi)]
            ),
        }
        for name, (lo, hi) in A_HALVES.items()
    }
    states = {}
    for col in [c for c in g.columns if c.startswith("f_")]:
        states[col[2:]] = {k: int(v) for k, v in g[col].value_counts().items()}
    out["factor_states"] = states
    return out


def positive(ci: dict) -> bool:
    return (
        ci["mean"] is not None
        and ci["mean"] > 0
        and ci["lo"] is not None
        and ci["lo"] > 0
    )


def reading_a(cell: dict | None) -> dict:
    """The declared reading of the primary cell."""
    if cell is None:
        return {"status": "underpowered", "n": 0, "n_confluence": 0}
    n = cell["groups"]["abc_geometry_all"]["n"]
    n_conf = cell["groups"]["abc_with_confluence"]["n"]
    cmp_hit, cmp_r = cell["compare"]["hit_24h"], cell["compare"]["R_24h"]

    def both(key: str) -> bool:
        return positive(cmp_hit[key]) and positive(cmp_r[key])

    out = {
        "n": n,
        "n_confluence": n_conf,
        "min_events": MIN_EVENTS,
        "min_confluence_events": MIN_CONFLUENCE_EVENTS,
        "geometry_beats_random_placebo": n >= MIN_EVENTS
        and both("geometry_minus_random_placebo"),
        "confluence_beats_random_placebo": n_conf >= MIN_CONFLUENCE_EVENTS
        and both("confluence_minus_random_placebo"),
        "confluence_adds_to_geometry": n_conf >= MIN_CONFLUENCE_EVENTS
        and both("confluence_minus_without"),
    }
    powered = n >= MIN_EVENTS and n_conf >= MIN_CONFLUENCE_EVENTS
    out["status"] = "read" if powered else "underpowered"
    return out


def part_a(workers: int) -> dict:
    uni = universe()
    with ProcessPoolExecutor(workers) as pool:
        done = list(pool.map(part_a_product, uni["products"]))
    df = pd.DataFrame([r for d in done for r in d["rows"]])
    if len(df):
        a1.assert_sealed(df["entry_ts"].to_numpy() + max(HORIZONS.values()) - 1)
    cells, core_cells = {}, {}
    if len(df):
        for (tf, bias, kind), g in df.groupby(["tf", "bias", "type"]):
            cells[f"{tf}/{bias}/{kind}"] = cell_summary(g)
            core = g[g["product"].isin(uni["core"])]
            core_cells[f"{tf}/{bias}/{kind}"] = {
                "abc_geometry_all": describe(core),
                "abc_with_confluence": describe(core[core["conf"]]),
                "placebo_random_bar": describe(core, "rand_"),
            }
    tallies = {}
    for d in done:
        for tf, t in d["tallies"].items():
            agg = tallies.setdefault(tf, {})
            for key, v in t.items():
                agg[key] = agg.get(key, 0) + v
    primary = "/".join(PRIMARY_CELL)
    return {
        "universe": uni,
        "window_utc": ["2026-10-13T00:00:00+00:00", "2026-11-12T00:00:00+00:00"],
        "signals": int(len(df)),
        "read_tallies": tallies,
        "products_with_signals": int(df["product"].nunique()) if len(df) else 0,
        "primary_cell": primary,
        "cells": cells,
        "core_40_cells": core_cells,
        "reading": reading_a(cells.get(primary)),
    }


# ---------- Part B: A1 flags and chart structure ----------


def classify_product(args: tuple) -> list:
    """Chart reads at each flag time for one product. `rows` is `[(uid, entered_ts)]`."""
    product, rows = args
    minutes = load_minutes(product)
    bars = {tf: resample(minutes, TIMEFRAMES[tf]) for tf in B_TIMEFRAMES}
    hbars = {tf: resample(minutes, HIGHER[tf]) for tf in B_TIMEFRAMES}
    out = []
    for row_id, entered_ts in rows:
        rec = {"uid": row_id}
        for tf in B_TIMEFRAMES:
            res = read_at(bars[tf], TIMEFRAMES[tf], hbars[tf], HIGHER[tf], entered_ts)
            rec.update(structure(res, tf))
        out.append(rec)
    return out


def structure(res: dict | None, tf: str) -> dict:
    """The parts of one read that Part B uses."""
    if not res or not res["available"] or res["active_pattern"] == "none":
        return {
            f"{tf}_sgn": 0,
            f"{tf}_abc": False,
            f"{tf}_conf": False,
            f"{tf}_trend": False,
        }
    sgn = 1 if res["bias"] == "bullish" else -1
    abc = live_abc(res)
    return {
        f"{tf}_sgn": sgn,
        f"{tf}_abc": abc,
        f"{tf}_conf": bool(abc and res["confluence_confirmed"]),
        f"{tf}_trend": res["active_pattern"] == "impulse_in_progress",
    }


def wave_arms(reads: pd.DataFrame, want: int) -> pd.DataFrame:
    """Structure tests per row. `want` is +1 for up boards, -1 for the down board."""
    out = pd.DataFrame({"uid": reads["uid"]})
    aligned = {tf: reads[f"{tf}_sgn"] == want for tf in B_TIMEFRAMES}
    against = {tf: reads[f"{tf}_sgn"] == -want for tf in B_TIMEFRAMES}

    def either(col: str, side: dict) -> pd.Series:
        hits = [side[tf] & reads[f"{tf}_{col}"] for tf in B_TIMEFRAMES]
        return hits[0] | hits[1]

    out["abc"] = either("abc", aligned)
    out["abc_conf"] = either("conf", aligned)
    out["opp"] = either("abc", against)
    out["trend"] = either("trend", aligned) & ~out["opp"]
    return out


def structure_class(arms: pd.DataFrame) -> pd.Series:
    cls = np.select(
        [arms["abc_conf"], arms["abc"], arms["opp"], arms["trend"]],
        ["abc_with_confluence", "abc_geometry_only", "opposing_abc", "trend_impulse"],
        "no_structure",
    )
    return pd.Series(cls, index=arms.index)


def reading_b(windows: dict) -> dict:
    full = windows["all"]
    if "delta_N" not in full or full["delta_N"]["mean"] is None:
        return {"status": "no_scored_days", "improves_a1": False}
    dn = full["delta_N"]
    checks = {
        "days_scored": full["days_scored"] >= B_RULE["min_days"],
        "dN_mean": dn["mean"] >= B_RULE["dn_mean"],
        "dN_block_lo": dn["block3"]["lo"] is not None
        and dn["block3"]["lo"] > B_RULE["dn_lo"],
    }
    halves = {
        name: "delta_N" in windows[name]
        and windows[name]["delta_N"]["mean"] is not None
        and windows[name]["delta_N"]["mean"] > 0
        for name in ("first_half", "second_half")
    }
    return {
        "status": "read",
        "improves_a1": all(checks.values()),
        "checks": checks,
        "same_sign_in_both_halves": all(halves.values()),
        "halves": halves,
        "rule": B_RULE,
    }


def part_b_population() -> tuple[dict, dict]:
    """The confirm script's rows and flags, rebuilt without change."""
    frozen = run.verify_inputs()
    cfg = json.loads(
        (run.SPEC_DIR / "CONTRACT_PRODUCTION.json").read_text(encoding="utf-8")
    )
    late = copy.deepcopy(cfg)
    late["phases"] = a1.LATE_PHASES
    parts = [
        a1.read_window(screen.CAPTURE_DB, cfg, a1.WARMUP, a1.SPLIT),
        a1.read_window(a1.LOCAL_DB, late, a1.SPLIT, a1.SEAL),
    ]
    df = screen.add_labels(pd.concat(parts, ignore_index=True))
    frame = a1.load_candles([screen.CANDLES, a1.BACKFILL])
    df = screen.add_features(df, screen.product_arrays(frame))
    boards = {board: attach_rows(df[df["stratum"] == board]) for board in screen.BOARDS}
    return boards, frozen


def attach_rows(g: pd.DataFrame) -> pd.DataFrame:
    """`build_flags` output with each row's product, entry time and a unique key.

    Row ids repeat across the two captures, so rows are matched by position:
    `build_flags` returns them sorted by entry time then id.
    """
    flags = screen.build_flags(g)
    ordered = g.sort_values(["entered_ts", "id"]).reset_index(drop=True)
    if not (flags["id"].to_numpy() == ordered["id"].to_numpy()).all():
        raise SystemExit("Refusing: flag rows are not in entry order.")
    flags["product_id"] = ordered["product_id"].to_numpy()
    flags["entered_ts"] = ordered["entered_ts"].to_numpy()
    flags["uid"] = np.arange(len(flags))
    return flags


def part_b(workers: int) -> dict:
    boards, frozen = part_b_population()
    lo, hi = a1.WINDOWS["all"]
    base = screen.compare(boards[a1.PRIMARY], "ca", "a0", "a1", lo, hi)
    parity = a1.parity(base)
    if not parity["match"]:
        raise SystemExit("Refusing: the A1 population differs from the published run.")
    out = {"frozen_inputs": frozen, "parity": parity, "boards": {}}
    for board, flags in boards.items():
        want = -1 if board.endswith("/down") else 1
        need = flags[flags["scored"] & (flags["ca_a1"] | flags["ca_a0"])]
        jobs = [
            (
                product,
                list(zip(g["uid"].tolist(), g["entered_ts"].astype(int).tolist())),
            )
            for product, g in need.groupby("product_id")
        ]
        with ProcessPoolExecutor(workers) as pool:
            reads = pd.DataFrame(
                [r for rows in pool.map(classify_product, jobs) for r in rows]
            )
        arms = wave_arms(reads, want)
        arms["structure"] = structure_class(arms)
        f = flags.merge(arms, on="uid", how="left", validate="one_to_one")
        for col in ("abc", "abc_conf", "opp", "trend"):
            f[col] = f[col].fillna(False).astype(bool)
        f["ca_w_abc"] = f["ca_a1"] & f["abc"]
        f["ca_w_abc_conf"] = f["ca_a1"] & f["abc_conf"]
        f["ca_w_trend"] = f["ca_a1"] & (f["abc"] | f["trend"])
        f["ca_w_no_opp"] = f["ca_a1"] & ~f["opp"]
        result = {"aligned_bias": "bullish" if want > 0 else "bearish", "arms": {}}
        for arm in B_ARMS:
            windows = {
                name: screen.compare(f, "ca", "a1", arm, w_lo, w_hi)
                for name, (w_lo, w_hi) in a1.WINDOWS.items()
            }
            result["arms"][arm] = {"windows": windows, "reading": reading_b(windows)}
        inside = f[f["scored"] & f["ca_a1"] & (f["day"] >= lo) & (f["day"] <= hi)]
        table = {}
        for name, g in inside.groupby(inside["structure"].fillna("no_structure")):
            table[name] = {
                "flags": int(len(g)),
                "runners": int(g["runner"].sum()),
                "crashers": int(g["crasher"].sum()),
                "runner_rate": float(g["runner"].mean()),
                "crasher_rate": float(g["crasher"].mean()),
                "net": float(g["runner"].mean() - g["crasher"].mean()),
            }
        result["a1_flags_by_structure_pooled"] = table
        result["a1_flags"] = int(len(inside))
        out["boards"][board] = result
    out["primary_board"] = a1.PRIMARY
    out["primary_arm"] = B_PRIMARY_ARM
    out["reading"] = out["boards"][a1.PRIMARY]["arms"][B_PRIMARY_ARM]["reading"]
    return out


# ---------- driver ----------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    hashes = {
        "local_capture": run.digest(a1.LOCAL_DB),
        "candle_archive": run.digest(ARCHIVE),
        "candle_backfill": run.digest(BACKFILL),
    }
    manifest = json.loads(a1.BACKFILL_MANIFEST.read_text(encoding="utf-8"))
    if hashes["local_capture"] != a1.LOCAL_SHA256:
        raise SystemExit("Refusing: local capture differs from the Nov 13 snapshot.")
    if hashes["candle_backfill"] != manifest["archive_sha256"]:
        raise SystemExit("Refusing: candle backfill differs from its manifest.")
    out = {
        "script_sha256": run.digest(Path(__file__)),
        "engine_sha256": run.digest(Path(engine.__file__)),
        "protocol_sha256": run.digest(PROTOCOL),
        "a1_definitions_sha256": run.digest(Path(screen.__file__)),
        "input_sha256": hashes,
        "seal_utc": "2026-11-13T00:00:00+00:00",
        "engine": {
            "atr_mult": engine.DEFAULT_ATR_MULT,
            "weights": engine.WEIGHTS,
            "confluence_threshold": engine.CONFLUENCE_THRESHOLD,
        },
        "seed": screen.SEED,
        "replicates": screen.REPS,
        "block_days": screen.BLOCK,
        "placebos_per_signal": PLACEBOS,
        "round_trip_cost": COST,
        "part_a": part_a(args.workers),
        "part_b": part_b(args.workers),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(screen.clean(out), indent=1, allow_nan=False) + "\n"
    (args.out / "RESULTS.json").write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps(screen.clean({"part_a": out["part_a"]["reading"]})))
    print(json.dumps(screen.clean({"part_b": out["part_b"]["reading"]})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
