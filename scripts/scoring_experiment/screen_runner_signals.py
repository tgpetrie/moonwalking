"""Runner signal screen, step 1 (exploration).

Protocol: docs/research/RADAR_RUNNER_SIGNAL_SCREEN_PROTOCOL_20261113.md

    python scripts/scoring_experiment/screen_runner_signals.py

Reads the frozen production capture and the local ledger capture read-only. Writes one JSON result.
"""
from __future__ import annotations

import collections
import copy
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/research/results/radar_runner_signal_screen_20261113"
PROTOCOL = ROOT / "docs/research/RADAR_RUNNER_SIGNAL_SCREEN_PROTOCOL_20261113.md"
PRODUCTION = Path.home() / ".moonwalking/analysis/live_movers_contract_20261027_production/board_episodes.sqlite"
LOCAL = Path.home() / ".moonwalking/analysis/live_movers_fresh_replication_20261113/board_episodes.sqlite"
CHECK_PHASES = {"check": ["2026-10-18T00:00:00+00:00", "2026-10-28T00:00:00+00:00"]}
SIGNALS = ("B0", "1A", "1A-", "1B", "3A", "4A", "4B", "6", "6c")
Q, MIN_ROWS, MIN_RUNNERS = 0.25, 20, 2
SEED, REPS = 20261114, 5000
BOARDS = ("ignition_1m/up", "confirmation_3m_up/up", "confirmation_3m_down/down")


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/scoring_experiment/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def num(x) -> float:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and np.isfinite(x) else np.nan


def read(db: Path, cfg: dict, freeze) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Eligible rows with snapshot inputs and outcomes, plus every recorded row for history features."""
    con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cooldown, recs, hist, rejects = {}, [], [], collections.Counter()
    for row in con.execute("select * from episodes order by entered_ts,id"):
        hist.append((row["id"], row["board"], row["product_id"], row["direction"], row["entered_ts"]))
        phase, why, snap = freeze.classify(row, cfg, cooldown)
        if why:
            rejects[why] += 1
            continue
        if not np.isfinite(num(row["gross_return_30m"])) or row["outcome_15m"] == "interrupted":
            rejects["screen_label_unavailable"] += 1
            continue
        raw = snap["raw_inputs"]
        recs.append({
            "id": row["id"], "board": row["board"], "product_id": row["product_id"], "direction": row["direction"],
            "entered_ts": row["entered_ts"], "phase": phase, "start_change_pct": num(row["start_change_pct"]),
            "pct_1m": num(raw.get("pct_1m")), "pct_3m": num(raw.get("pct_3m")), "vol": num(raw.get("volume_change_1h_pct")),
            "liquidity": str(raw.get("liquidity") or "normal").lower(), "trend_streak": num(raw.get("trend_streak")),
            "bull": num(raw.get("bullish_alerts")), "bear": num(raw.get("bearish_alerts")),
            "r5": num(row["gross_return_5m"]), "r15": num(row["gross_return_15m"]), "r30": num(row["gross_return_30m"]),
            "fav15": num(row["max_favorable_15m"]), "adv15": num(row["max_adverse_15m"])})
    con.close()
    df = pd.DataFrame(recs)
    allrows = pd.DataFrame(hist, columns=["id", "board", "product_id", "direction", "entered_ts"])
    return df, allrows, dict(rejects)


def window_counts(keys: pd.DataFrame, ref: pd.DataFrame, by: list[str], lo: int, hi: int, closed_hi: bool) -> np.ndarray:
    """For each row of keys, count ref rows with the same `by` values and entered_ts in [t+lo, t+hi] (or [t+lo, t+hi))."""
    out = np.zeros(len(keys), dtype=int)
    groups = {k: np.sort(g["entered_ts"].to_numpy()) for k, g in ref.groupby(by)}
    for k, g in keys.groupby(by):
        arr = groups.get(k)
        if arr is None:
            continue
        t = g["entered_ts"].to_numpy()
        right = np.searchsorted(arr, t + hi, side="right" if closed_hi else "left")
        out[keys.index.get_indexer(g.index)] = right - np.searchsorted(arr, t + lo, side="left")
    return out


def add_signals(df: pd.DataFrame, allrows: pd.DataFrame) -> pd.DataFrame:
    df = df.reset_index(drop=True)
    d = np.where(df["direction"] == "down", -1.0, 1.0)
    a1, a3 = d * df["pct_1m"], d * df["pct_3m"]
    df["B0"] = df["start_change_pct"].abs()
    df["1A"] = a1 / np.maximum(a3, 0.25)
    df["1A-"] = -df["1A"]
    df["1B"] = a3 - 2 * np.maximum(0, a1 - 0.60 * a3) - 2 * np.maximum(0, 0.15 * a3 - a1)
    df["3A"] = np.where(df["liquidity"] == "normal", np.log(1 + np.maximum(df["vol"], -99) + 100), 0.0)
    aligned = np.where(d > 0, df["bull"], df["bear"])
    opposing = np.where(d > 0, df["bear"], df["bull"])
    df["4A"] = np.minimum(df["trend_streak"].fillna(0), 6) + 2 * np.nan_to_num(aligned) - 2 * np.nan_to_num(opposing)
    same_pd = window_counts(df, allrows, ["product_id", "direction"], -180, 180, True)
    same_pdb = window_counts(df, allrows, ["product_id", "direction", "board"], -180, 180, True)
    simultaneous = (same_pd - same_pdb) > 0
    repeat_6h = window_counts(df, allrows, ["product_id", "direction"], -21600, 0, False)
    df["simultaneous"], df["repeat_6h"] = simultaneous.astype(int), repeat_6h
    df["4B"] = 2 * simultaneous + (repeat_6h == 1) - 2 * (repeat_6h >= 3)
    a_board = np.where(df["board"] == "ignition_1m", a1, a3)
    chase = np.maximum(0, df["B0"] - np.abs(a_board))
    w60 = window_counts(df, allrows, ["board", "direction"], -60, 0, True)
    df["W60"] = w60
    df["6c"] = -chase
    df["6"] = -chase - 0.15 * np.maximum(0, w60 - 3) + 0.01 * df["vol"]
    df["runner"] = ((df["r15"] >= 1.0) & (df["r5"] > -0.5) & (np.maximum(df["fav15"], df["r30"]) >= 1.5)).astype(int)
    df["crasher"] = ((df["r15"] <= -1.0) & (df["r5"] < 0.5) & (np.minimum(df["adv15"], df["r30"]) <= -1.5)).astype(int)
    df["stratum"] = df["board"] + "/" + df["direction"]
    df["day"] = pd.to_datetime(df["entered_ts"], unit="s", utc=True).dt.strftime("%Y-%m-%d")
    return df


def flagged(g: pd.DataFrame, signal: str, k: int) -> pd.Index:
    order = g.sort_values([signal, "B0", "id"], ascending=[False, False, True], kind="mergesort")
    return order.index[:k]


def daily(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (stratum, day), g in df.groupby(["stratum", "day"]):
        if len(g) < MIN_ROWS or g["runner"].sum() < MIN_RUNNERS:
            continue
        k = int(np.floor(Q * len(g)))
        rec = {"stratum": stratum, "day": day, "n": len(g), "k": k, "X": g["runner"].mean(), "Xc": g["crasher"].mean()}
        for s in SIGNALS:
            f = g.loc[flagged(g, s, k)]
            rec[f"Y_{s}"], rec[f"C_{s}"] = f["runner"].mean(), f["crasher"].mean()
        rows.append(rec)
    return pd.DataFrame(rows)


def boot(v: np.ndarray) -> dict:
    v = v[np.isfinite(v)]
    if len(v) < 3:
        return {"mean": float(v.mean()) if len(v) else None, "n_days": int(len(v)), "lo": None, "hi": None}
    m = v[np.random.default_rng(SEED).integers(0, len(v), (REPS, len(v)))].mean(axis=1)
    lo, hi = np.percentile(m, [2.5, 97.5])
    return {"mean": float(v.mean()), "n_days": int(len(v)), "days_positive": int((v > 0).sum()), "lo": float(lo), "hi": float(hi)}


def summarize(days: pd.DataFrame) -> dict:
    out = {}
    for stratum, g in days.groupby("stratum"):
        res = {"days": int(len(g)), "rows": int(g["n"].sum()), "runner_base_rate": float(g["X"].mean()),
               "crasher_base_rate": float(g["Xc"].mean()), "signals": {}}
        for s in SIGNALS:
            dp = (g[f"Y_{s}"] - g["Y_B0"]).to_numpy()
            dn = ((g[f"Y_{s}"] - g[f"C_{s}"]) - (g["Y_B0"] - g["C_B0"])).to_numpy()
            res["signals"][s] = {"runner_rate": float(g[f"Y_{s}"].mean()), "crasher_rate": float(g[f"C_{s}"].mean()),
                                 "lift_vs_base": float(g[f"Y_{s}"].mean() / g["X"].mean()) if g["X"].mean() else None,
                                 "delta_P_vs_B0": boot(dp), "delta_net_vs_B0": boot(dn)}
        out[stratum] = res
    return out


def screen_call(screen: dict, check: dict) -> dict:
    calls = {}
    for stratum in BOARDS:
        for s in SIGNALS[1:]:
            a = screen.get(stratum, {}).get("signals", {}).get(s)
            b = check.get(stratum, {}).get("signals", {}).get(s)
            if not a or not b:
                continue
            dp, dn, cp = a["delta_P_vs_B0"], a["delta_net_vs_B0"], b["delta_P_vs_B0"]
            ok = (dp["mean"] is not None and dp["mean"] >= 0.010 and dp["lo"] is not None and dp["lo"] > 0
                  and dn["mean"] is not None and dn["mean"] > 0 and cp["mean"] is not None and cp["mean"] > 0)
            calls[f"{stratum}|{s}"] = {"passes": bool(ok), "screen_delta_P": dp["mean"], "screen_lo": dp["lo"],
                                       "screen_delta_net": dn["mean"], "check_delta_P": cp["mean"]}
    passing = sorted((v["screen_delta_P"], k) for k, v in calls.items() if v["passes"])[::-1]
    forward, seen = [], set()
    for _, key in passing:
        sig = key.split("|")[1]
        if sig not in seen and len(seen) < 3:
            seen.add(sig)
        if sig in seen:
            forward.append(key)
    return {"by_board_signal": calls, "signals_forward": sorted(seen), "board_signal_pairs_forward": forward}


def main() -> int:
    run, freeze = load("live_movers_run"), load("freeze_live_contract")
    cfg = json.loads((run.SPEC_DIR / "CONTRACT_PRODUCTION.json").read_text(encoding="utf-8"))
    check_cfg = copy.deepcopy(cfg)
    check_cfg["phases"] = CHECK_PHASES
    run.verify_inputs()
    p_df, p_all, p_rej = read(PRODUCTION, cfg, freeze)
    c_df, c_all, c_rej = read(LOCAL, check_cfg, freeze)
    p_df, c_df = add_signals(p_df, p_all), add_signals(c_df, c_all)
    p_days, c_days = daily(p_df), daily(c_df)
    screen, check = summarize(p_days), summarize(c_days)
    out = {"protocol_sha256": run.digest(PROTOCOL), "script_sha256": run.digest(Path(__file__)),
           "production_capture_sha256": run.digest(PRODUCTION), "local_capture_sha256": run.digest(LOCAL),
           "seed": SEED, "replicates": REPS, "flag_share": Q,
           "rejections": {"screen": p_rej, "check": c_rej},
           "eligible_rows": {"screen": int(len(p_df)), "check": int(len(c_df))},
           "screen_dates": [p_df["day"].min(), p_df["day"].max()], "check_dates": [c_df["day"].min(), c_df["day"].max()],
           "screen": screen, "check": check, "call": screen_call(screen, check),
           "daily": {"screen": p_days.round(6).to_dict(orient="records"), "check": c_days.round(6).to_dict(orient="records")}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "RESULTS.json").write_text(json.dumps(out, indent=1, allow_nan=False, default=float) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out["call"]["signals_forward"]), json.dumps(out["eligible_rows"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
