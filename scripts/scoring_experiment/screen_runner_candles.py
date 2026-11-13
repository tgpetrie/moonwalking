"""Runner candle screen, step 2 (exploration).

Protocol: docs/research/RADAR_RUNNER_CANDLE_SCREEN_PROTOCOL_20261113.md
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/research/results/radar_runner_candle_screen_20261113"
PROTOCOL = ROOT / "docs/research/RADAR_RUNNER_CANDLE_SCREEN_PROTOCOL_20261113.md"
CANDLES = Path.home() / ".moonwalking/data/candle_archive.sqlite"
WINDOWS = {"screen": ("2026-09-07", "2026-09-30"), "check": ("2026-10-01", "2026-10-11")}
SIGNALS = ("2A", "3B", "5A", "2Ax3B")
Q, MIN_ROWS, MIN_RUNNERS, SEED, REPS = 0.25, 20, 2, 20261115, 5000


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/scoring_experiment/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_candles(path: Path) -> dict:
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    df = pd.read_sql("select product_id, ts, open, close, volume from candles where granularity=60 order by product_id, ts", con)
    con.close()
    return {p: (g["ts"].to_numpy(), g["open"].to_numpy(), g["close"].to_numpy(), g["volume"].to_numpy())
            for p, g in df.groupby("product_id", sort=False)}


def at(ts: np.ndarray, t: int) -> int:
    """Index of the candle with open time exactly t, or -1."""
    i = int(np.searchsorted(ts, t))
    return i if i < len(ts) and ts[i] == t else -1


def candle_features(entered_ts: int, product: tuple | None, btc: tuple | None, d: float, pct_3m: float) -> dict:
    out = {"2A": np.nan, "3B": np.nan, "5A": np.nan, "active15": np.nan}
    if product is None:
        return out
    ts, o, c, v = product
    k = (entered_ts // 60) * 60 - 60
    hi = int(np.searchsorted(ts, k, side="right"))
    if hi == 0:
        return out
    lo60 = int(np.searchsorted(ts, k - 3540))
    lo15 = int(np.searchsorted(ts, k - 840))
    lo3 = int(np.searchsorted(ts, k - 120))
    out["active15"] = hi - lo15
    out["3B"] = np.log1p(float(np.sum(c[lo3:hi] * v[lo3:hi]))) * (hi - lo15) / 15.0
    if hi - lo60 >= 10:
        sigma = max(0.001, float(np.sqrt(np.sum(np.log(c[lo60:hi] / o[lo60:hi]) ** 2) / 60.0)))
        out["2A"] = d * pct_3m / 100.0 / (np.sqrt(3.0) * sigma)
    if btc is not None:
        i1, i0 = at(ts, k), at(ts, k - 120)
        b1, b0 = at(btc[0], k), at(btc[0], k - 120)
        if min(i1, i0, b1, b0) >= 0:
            r = (c[i1] / o[i0] - 1) * 100
            rb = (btc[2][b1] / btc[1][b0] - 1) * 100
            out["5A"] = d * (r - rb) if abs(rb) < 0.75 else 0.0
    return out


def boot(v: np.ndarray) -> dict:
    if len(v) < 3:
        return {"mean": float(v.mean()) if len(v) else None, "n_days": int(len(v)), "lo": None, "hi": None}
    m = v[np.random.default_rng(SEED).integers(0, len(v), (REPS, len(v)))].mean(axis=1)
    lo, hi = np.percentile(m, [2.5, 97.5])
    return {"mean": float(v.mean()), "n_days": int(len(v)), "days_positive": int((v > 0).sum()), "lo": float(lo), "hi": float(hi)}


def rate(g: pd.DataFrame, col: str):
    return float(g[col].mean()) if len(g) else None


def evaluate(df: pd.DataFrame, signal: str, screen) -> dict:
    res = {}
    for stratum, g_all in df.groupby("stratum"):
        ok = np.isfinite(g_all[signal])
        g, dr = g_all[ok], g_all[~ok]
        rows = []
        for _, gd in g.groupby("day"):
            if len(gd) < MIN_ROWS or gd["runner"].sum() < MIN_RUNNERS:
                continue
            k = int(np.floor(Q * len(gd)))
            fs, fb = gd.loc[screen.flagged(gd, signal, k)], gd.loc[screen.flagged(gd, "B0", k)]
            rows.append((gd["runner"].mean(), fs["runner"].mean(), fs["crasher"].mean(), fb["runner"].mean(), fb["crasher"].mean()))
        a = np.array(rows) if rows else np.zeros((0, 5))
        mean = lambda i: float(a[:, i].mean()) if len(a) else None
        res[stratum] = {
            "eligible": int(len(g_all)), "kept": int(len(g)), "kept_share": float(len(g) / len(g_all)),
            "kept_runner_rate": rate(g, "runner"), "kept_crasher_rate": rate(g, "crasher"),
            "dropped_runner_rate": rate(dr, "runner"), "dropped_crasher_rate": rate(dr, "crasher"),
            "days": int(len(a)), "runner_base": mean(0), "signal_runner": mean(1), "signal_crasher": mean(2),
            "b0_runner": mean(3), "b0_crasher": mean(4),
            "delta_P": boot(a[:, 1] - a[:, 3]), "delta_net": boot((a[:, 1] - a[:, 2]) - (a[:, 3] - a[:, 4]))}
    return res


def main() -> int:
    screen, run, freeze = load("screen_runner_signals"), load("live_movers_run"), load("freeze_live_contract")
    cfg = json.loads((run.SPEC_DIR / "CONTRACT_PRODUCTION.json").read_text(encoding="utf-8"))
    run.verify_inputs()
    df, allrows, _ = screen.read(screen.PRODUCTION, cfg, freeze)
    df = screen.add_signals(df, allrows)
    df = df[(df["day"] >= WINDOWS["screen"][0]) & (df["day"] <= WINDOWS["check"][1])].reset_index(drop=True)
    candles = load_candles(CANDLES)
    btc = candles.get("BTC-USD")
    d = np.where(df["direction"] == "down", -1.0, 1.0)
    f = pd.DataFrame([candle_features(int(t), candles.get(p), btc, float(s), float(x))
                      for t, p, s, x in zip(df["entered_ts"], df["product_id"], d, df["pct_3m"])])
    for col in ("2A", "3B", "5A", "active15"):
        df[col] = f[col].to_numpy()
    floor = df.groupby(["stratum", "day"])["2A"].transform("min")
    df["2Ax3B"] = np.where(np.isfinite(df["2A"]) & (df["active15"] < 10), floor, df["2A"])
    out = {"protocol_sha256": run.digest(PROTOCOL), "script_sha256": run.digest(Path(__file__)), "seed": SEED, "windows": WINDOWS}
    for name, (a, b) in WINDOWS.items():
        w = df[(df["day"] >= a) & (df["day"] <= b)]
        out[name] = {"rows": int(len(w)), "signals": {s: evaluate(w, s, screen) for s in SIGNALS}}
    calls = {}
    for s in SIGNALS:
        for stratum, r in out["screen"]["signals"][s].items():
            cp = out["check"]["signals"][s].get(stratum, {}).get("delta_P", {})
            dp, dn = r["delta_P"], r["delta_net"]
            calls[f"{stratum}|{s}"] = bool(dp["mean"] is not None and dp["lo"] is not None and dp["mean"] >= 0.010
                                           and dp["lo"] > 0 and dn["mean"] > 0 and cp.get("mean") is not None and cp["mean"] > 0)
    out["passes"] = calls
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "RESULTS.json").write_text(json.dumps(out, indent=1, allow_nan=False, default=float) + "\n", encoding="utf-8", newline="\n")
    print([k for k, v in calls.items() if v], out["screen"]["rows"], out["check"]["rows"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
