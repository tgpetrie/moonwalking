"""Early-watch screen on one-minute candles (exploration).

Protocol: docs/research/RADAR_EARLY_WATCH_SCREEN_PROTOCOL_20261113.md

Matrices are products x minutes. Column j is the candle that opens at T0 + 60*j and closes at decision time
tau_j = T0 + 60*(j+1). Features at column j read columns <= j only; outcomes read columns > j.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/research/results/radar_early_watch_screen_20261113"
PROTOCOL = ROOT / "docs/research/RADAR_EARLY_WATCH_SCREEN_PROTOCOL_20261113.md"
CANDLES = Path.home() / ".moonwalking/data/candle_archive.sqlite"
WINDOWS = {"screen": ("2026-09-07", "2026-09-30"), "check": ("2026-10-01", "2026-10-11")}
STABLE = {"USDC", "USDT", "DAI", "PYUSD", "GUSD", "USDS", "EURC"}
SIGNALS = ("R3", "EW1", "EW2", "EW3", "EW4", "EW5", "EW12")
Q, MIN_ROWS, MIN_RUNNERS, SEED, REPS, TOP = 0.25, 200, 5, 20261116, 5000, 8


def trailing_sum(x: np.ndarray, n: int) -> np.ndarray:
    """Sum over columns j-n+1..j."""
    c = np.cumsum(x, axis=1, dtype=np.float64)
    out = c.copy()
    out[:, n:] = c[:, n:] - c[:, :-n]
    return out


def shift(x: np.ndarray, n: int, fill=np.nan) -> np.ndarray:
    """out[:, j] = x[:, j-n]; n may be negative."""
    out = np.full(x.shape, fill, dtype=x.dtype if fill is not np.nan else np.float64)
    if n > 0:
        out[:, n:] = x[:, :-n]
    elif n < 0:
        out[:, :n] = x[:, -n:]
    else:
        out[:] = x
    return out


def rolling_ext(x: np.ndarray, n: int, fn) -> np.ndarray:
    """fn (np.fmax or np.fmin) over columns j-n+1..j."""
    out = x.copy()
    for k in range(1, n):
        out = fn(out, shift(x, k))
    return out


def top_mask(r: np.ndarray, universe: np.ndarray) -> np.ndarray:
    """True where the coin is among the TOP highest r in its column, within the universe."""
    v = np.where(universe & np.isfinite(r), r, -np.inf)
    kth = np.partition(v, -TOP, axis=0)[-TOP]
    return (v >= kth) & np.isfinite(v)


def features(close: np.ndarray, high: np.ndarray, low: np.ndarray, vol: np.ndarray, traded: np.ndarray,
             btc: int, eligible: np.ndarray) -> dict:
    """Everything known at each decision time. close/high/low are carried forward over no-trade minutes."""
    r1 = (close / shift(close, 1) - 1) * 100
    r3 = (close / shift(close, 3) - 1) * 100
    universe = eligible[:, None] & (trailing_sum(traded, 1440) >= 30) & (trailing_sum(traded, 60) >= 5) & np.isfinite(r3)
    top1, top3 = top_mask(r1, universe), top_mask(r3, universe)
    cand = universe & ~top1 & ~top3 & (r3 > 0.30)
    sigma = np.maximum(0.001, np.sqrt(trailing_sum(np.nan_to_num(r1 / 100) ** 2, 60) / 60))
    dv = np.nan_to_num(close * vol)
    dv3 = trailing_sum(dv, 3)
    dv_prior = shift(trailing_sum(dv, 57), 3, 0.0) / 19.0
    hi3, lo3 = rolling_ext(high, 3, np.fmax), rolling_ext(low, 3, np.fmin)
    rng = hi3 - lo3
    hi15, lo15 = shift(rolling_ext(high, 15, np.fmax), 3), shift(rolling_ext(low, 15, np.fmin), 3)
    with np.errstate(divide="ignore", invalid="ignore"):
        ew3 = np.where(rng > 0, (close - lo3) / rng, 0.5)
        ew4 = np.log(hi3 / lo3) / np.maximum(0.002, np.log(hi15 / lo15))
    return {"universe": universe, "cand": cand, "top": top1 | top3, "r3": r3,
            "R3": r3, "EW1": r3 / 100 / (np.sqrt(3) * sigma), "EW2": np.log((dv3 + 500) / (dv_prior + 500)),
            "EW3": ew3, "EW4": ew4, "EW5": r3 - r3[btc][None, :]}


def outcomes(close: np.ndarray, top: np.ndarray) -> dict:
    r5 = (shift(close, -5) / close - 1) * 100
    r15 = (shift(close, -15) / close - 1) * 100
    fwd_max = shift(rolling_ext(close, 15, np.fmax), -15)   # max close over columns j+1..j+15
    fwd_min = shift(rolling_ext(close, 15, np.fmin), -15)
    graduated = shift(rolling_ext(top.astype(np.float64), 10, np.fmax), -10, 0.0) > 0
    peak, trough = (fwd_max / close - 1) * 100, (fwd_min / close - 1) * 100
    runner = (r15 >= 1.0) & (r5 > -0.5) & ((peak >= 1.5) | graduated)
    crasher = (r15 <= -1.0) & (r5 < 0.5) & (trough <= -1.5)
    return {"runner": runner, "crasher": crasher, "gradable": np.isfinite(r15) & np.isfinite(fwd_max)}


def load_matrices(path: Path):
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    df = pd.read_sql("select product_id, ts, high, low, close, volume from candles where granularity=60", con)
    con.close()
    df = df[df["product_id"].str.endswith("-USD")]
    products = sorted(df["product_id"].unique())
    t0, t1 = int(df["ts"].min()), int(df["ts"].max())
    n = (t1 - t0) // 60 + 1
    pi = df["product_id"].map({p: i for i, p in enumerate(products)}).to_numpy()
    ti = ((df["ts"].to_numpy() - t0) // 60).astype(int)
    mats = {}
    for col in ("close", "high", "low", "volume"):
        m = np.full((len(products), n), np.nan)
        m[pi, ti] = df[col].to_numpy()
        mats[col] = m
    traded = np.isfinite(mats["close"]).astype(np.float64)
    close = pd.DataFrame(mats["close"]).ffill(axis=1).to_numpy()
    high = np.where(np.isfinite(mats["high"]), mats["high"], close)
    low = np.where(np.isfinite(mats["low"]), mats["low"], close)
    return products, t0, close, high, low, np.nan_to_num(mats["volume"]), traded


def boot(v: np.ndarray) -> dict:
    if len(v) < 3:
        return {"mean": float(v.mean()) if len(v) else None, "n_days": int(len(v)), "lo": None, "hi": None}
    m = v[np.random.default_rng(SEED).integers(0, len(v), (REPS, len(v)))].mean(axis=1)
    lo, hi = np.percentile(m, [2.5, 97.5])
    return {"mean": float(v.mean()), "n_days": int(len(v)), "days_positive": int((v > 0).sum()), "lo": float(lo), "hi": float(hi)}


def evaluate(rows: pd.DataFrame) -> dict:
    per = []
    for day, g in rows.groupby("day"):
        if len(g) < MIN_ROWS or g["runner"].sum() < MIN_RUNNERS:
            continue
        g = g.copy()
        g["EW12"] = (g["EW1"].rank() + g["EW2"].rank()) / 2
        k = int(np.floor(Q * len(g)))
        rec = {"day": day, "n": len(g), "X": g["runner"].mean(), "Xc": g["crasher"].mean()}
        for s in SIGNALS:
            f = g.nlargest(k, s, keep="first")
            rec[f"Y_{s}"], rec[f"C_{s}"] = f["runner"].mean(), f["crasher"].mean()
        per.append(rec)
    d = pd.DataFrame(per)
    res = {"days": int(len(d)), "rows": int(d["n"].sum()), "runner_base": float(d["X"].mean()), "crasher_base": float(d["Xc"].mean()),
           "signals": {}}
    for s in SIGNALS:
        res["signals"][s] = {"runner_rate": float(d[f"Y_{s}"].mean()), "crasher_rate": float(d[f"C_{s}"].mean()),
                             "lift_vs_candidates": float(d[f"Y_{s}"].mean() / d["X"].mean()),
                             "delta_P": boot((d[f"Y_{s}"] - d["Y_R3"]).to_numpy()),
                             "delta_net": boot(((d[f"Y_{s}"] - d[f"C_{s}"]) - (d["Y_R3"] - d["C_R3"])).to_numpy())}
    return res


def main() -> int:
    products, t0, close, high, low, vol, traded = load_matrices(CANDLES)
    eligible = np.array([p.split("-")[0] not in STABLE for p in products])
    f = features(close, high, low, vol, traded, products.index("BTC-USD"), eligible)
    o = outcomes(close, f["top"])
    tau = t0 + 60 * (np.arange(close.shape[1]) + 1)
    day = pd.to_datetime(tau, unit="s", utc=True).strftime("%Y-%m-%d").to_numpy()
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    out = {"protocol_sha256": sha(PROTOCOL), "script_sha256": sha(Path(__file__)), "seed": SEED, "windows": WINDOWS,
           "products": len(products)}
    for name, (a, b) in WINDOWS.items():
        cols = (day >= a) & (day <= b)
        grad = o["gradable"] & cols[None, :]
        uni, cand = f["universe"] & grad, f["cand"] & grad
        pi, ji = np.nonzero(cand)
        rows = pd.DataFrame({"day": day[ji], "runner": o["runner"][pi, ji], "crasher": o["crasher"][pi, ji],
                             **{s: f[s][pi, ji] for s in SIGNALS if s != "EW12"}}).replace([np.inf, -np.inf], np.nan).dropna()
        res = evaluate(rows)
        res.update(universe_coin_minutes=int(uni.sum()), universe_runner_rate=float(o["runner"][uni].mean()),
                   universe_crasher_rate=float(o["crasher"][uni].mean()), candidate_coin_minutes=int(cand.sum()),
                   candidates_per_minute=float(cand.sum() / cols.sum()),
                   top8_runner_rate=float(o["runner"][f["top"] & uni].mean()), top8_crasher_rate=float(o["crasher"][f["top"] & uni].mean()))
        out[name] = res
    passes = {}
    for s in SIGNALS[1:]:
        a, c = out["screen"]["signals"][s], out["check"]["signals"][s]
        passes[s] = bool(a["delta_P"]["mean"] >= 0.010 and a["delta_P"]["lo"] > 0 and a["delta_net"]["mean"] > 0 and c["delta_P"]["mean"] > 0)
    out["passes"] = passes
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "RESULTS.json").write_text(json.dumps(out, indent=1, allow_nan=False, default=float) + "\n", encoding="utf-8", newline="\n")
    print(passes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
