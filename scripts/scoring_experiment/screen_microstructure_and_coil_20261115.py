"""Microstructure gate and pre-pump coil screen (exploration).

Protocol: docs/research/RADAR_MICROSTRUCTURE_AND_COIL_PROTOCOL_20261115.md

    python scripts/scoring_experiment/screen_microstructure_and_coil_20261115.py

Reads the frozen production board capture and the one-minute candle archive
read-only and writes one JSON result. Changes no board, score or collector.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import freeze_live_contract as freeze  # noqa: E402
import live_movers_run as run  # noqa: E402
import screen_radar_candles_20261113 as carbon  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "docs/research/results/radar_microstructure_coil_20261115"
PROTOCOL = ROOT / "docs/research/RADAR_MICROSTRUCTURE_AND_COIL_PROTOCOL_20261115.md"
CAPTURE_DB = run.CAPTURE / "board_episodes.sqlite"
CANDLES = carbon.CANDLES


def stamp(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())


START, END = stamp("2026-09-07"), stamp("2026-10-12")
SCREEN, CHECK = ("2026-09-07", "2026-09-30"), ("2026-10-01", "2026-10-11")
SAME_DAY_WINDOWS = {"screen": SCREEN, "check": CHECK}
CAUSAL_WINDOWS = {
    "screen": ("2026-09-14", "2026-09-30"),
    "check": CHECK,
    "gate_reference_parity": ("2026-09-14", "2026-10-11"),
}
EXPECTED_ROWS = {"screen": 131684, "check": 60659}
BOARDS = ("confirmation_3m_up/up", "ignition_1m/up", "confirmation_3m_down/down")
Q, MIN_ROWS, MIN_RUNNERS = 0.25, 20, 2
SEED, REPS, BLOCK = 20261117, 5000, 3
A_MULT_MIN, GATE_Q30 = 1.5, 0.30
ARMS = ("a0", "a1", "a1_q30", "a2", "a2_backfill", "a3", "gate", "strict")
COMPARISONS = (
    ("a1_vs_a0", "a0", "a1"),
    ("a1_q30_vs_a0", "a0", "a1_q30"),
    ("a2_vs_a0", "a0", "a2"),
    ("a3_vs_a0", "a0", "a3"),
    ("a2_vs_a1", "a1", "a2"),
)
# Published values this run is checked against, in percent.
STEP2_B0 = {
    "confirmation_3m_up/up": (4.98, 9.53),
    "ignition_1m/up": (4.50, 8.10),
    "confirmation_3m_down/down": (5.44, 8.77),
}
GATE_REFERENCE_3M_UP = (1.19, -2.16)
HOLD_RULE = {"dp_mean": -0.0050, "dp_lo": -0.0100, "dc_mean": -0.0250, "dc_hi": -0.0150}

# Part B clock: minute indices are counted from FIRST_MINUTE.
FIRST_MINUTE, LAST_MINUTE = START // 60 - 1500, END // 60 + 20
STEP, COOLDOWN, LIVE_HORIZON, CAPTURE_GAP = 5, 60, 900, 600
LIVE_UP_BOARDS = ("ignition_1m", "confirmation_3m_up")
B_WINDOWS = {"screen": SCREEN, "check": CHECK, "all": (SCREEN[0], CHECK[1])}
MOVE_FLOOR = math.log1p(0.003)
FLAG_COLUMNS = [
    "cutoff",
    "product",
    "ts",
    "graded",
    "result",
    "synthetic_lead_min",
    "live_observable",
    "on_live_board",
    "live_lead_s",
]
BEAT_RULE = 0.0100


def num(x) -> float:
    ok = isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
    return float(x) if ok else math.nan


def utc_day(ts) -> pd.Index:
    return pd.to_datetime(np.asarray(ts), unit="s", utc=True).strftime("%Y-%m-%d")


# ---------- inputs ----------


def read_entries(db: Path, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Step 1 eligible entries, plus every recorded entry near the study dates."""
    cooldown, recs, hist = {}, [], []
    with closing(carbon.read_only(db)) as con:
        con.row_factory = sqlite3.Row
        for row in con.execute("SELECT * FROM episodes ORDER BY entered_ts, id"):
            ts = row["entered_ts"]
            if START - 86400 <= ts < END + 86400:
                hist.append(
                    (
                        row["board"],
                        row["product_id"],
                        row["direction"],
                        ts,
                        row["last_seen_ts"],
                        row["exited_ts"],
                        row["entry_rank"],
                    )
                )
            _, why, snap = freeze.classify(row, cfg, cooldown)
            if why or not START <= ts < END:
                continue
            unlabeled = not math.isfinite(num(row["gross_return_30m"]))
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
                    "B0": abs(num(row["start_change_pct"])),
                    "pct_1m": num(raw.get("pct_1m")),
                    "pct_3m": num(raw.get("pct_3m")),
                    "r5": num(row["gross_return_5m"]),
                    "r15": num(row["gross_return_15m"]),
                    "r30": num(row["gross_return_30m"]),
                    "fav15": num(row["max_favorable_15m"]),
                    "adv15": num(row["max_adverse_15m"]),
                }
            )
    df = add_labels(pd.DataFrame(recs))
    cols = ["board", "product_id", "direction", "entered_ts", "last_seen_ts"]
    return df, pd.DataFrame(hist, columns=cols + ["exited_ts", "entry_rank"])


def add_labels(df: pd.DataFrame) -> pd.DataFrame:
    best = np.maximum(df["fav15"], df["r30"])
    worst = np.minimum(df["adv15"], df["r30"])
    df["runner"] = ((df["r15"] >= 1.0) & (df["r5"] > -0.5) & (best >= 1.5)).astype(int)
    df["crasher"] = ((df["r15"] <= -1.0) & (df["r5"] < 0.5) & (worst <= -1.5)).astype(
        int
    )
    sign = np.where(df["direction"] == "down", -1.0, 1.0)
    board_move = np.where(df["board"] == "ignition_1m", df["pct_1m"], df["pct_3m"])
    df["S"] = sign * board_move
    df["day"] = utc_day(df["entered_ts"])
    return df


def load_candle_frame(path: Path) -> pd.DataFrame:
    sql = """SELECT product_id, ts, open, high, low, close, volume FROM candles
             WHERE granularity = 60 AND ts >= ? AND ts < ? ORDER BY product_id, ts"""
    with closing(carbon.read_only(path)) as con:
        df = pd.read_sql(sql, con, params=(60 * FIRST_MINUTE, 60 * LAST_MINUTE))
    prices = df[["open", "high", "low", "close", "volume"]].to_numpy()
    ok = np.isfinite(prices).all(axis=1) & (df["ts"].to_numpy() % 60 == 0)
    ok &= (prices[:, :4] > 0).all(axis=1) & (prices[:, 4] >= 0)
    return df[ok].reset_index(drop=True)


def product_arrays(frame: pd.DataFrame) -> dict:
    """Per product: open times, open, close, volume and dollars, sorted by time."""
    return {
        product: (
            g["ts"].to_numpy(),
            g["open"].to_numpy(),
            g["close"].to_numpy(),
            g["volume"].to_numpy(),
            (g["close"] * g["volume"]).to_numpy(),
        )
        for product, g in frame.groupby("product_id", sort=False)
    }


# ---------- Part A features ----------


def anchor_minute(entered_ts: int, delay_minutes: int = 0) -> int:
    """Open time of the last candle closed before entry."""
    return ((entered_ts - 60) // 60) * 60 - 60 * delay_minutes


def entry_features(entered_ts, pct_3m, candles, delay_minutes: int = 0) -> dict:
    """D3 and the absorption multiple. Missing bars are zero; nothing is dropped."""
    out = {"D3": 0.0, "n3": 0, "n60": 0, "K3": 0.0, "K_base": math.nan, "A": 0.0}
    if candles is None:
        return out
    ts, opened, close, volume, usd = candles
    m0 = anchor_minute(int(entered_ts), delay_minutes)
    lo3 = int(np.searchsorted(ts, m0 - 120))
    hi3 = int(np.searchsorted(ts, m0, side="right"))
    out["D3"] = float(usd[lo3:hi3].sum())
    out["n3"] = int((volume[lo3:hi3] > 0).sum())
    lo = int(np.searchsorted(ts, m0 - 62 * 60))
    hi = int(np.searchsorted(ts, m0 - 3 * 60, side="right"))
    traded = volume[lo:hi] > 0
    out["n60"] = int(traded.sum())
    if out["n60"] < 10 or not math.isfinite(pct_3m):
        return out
    move = np.abs(close[lo:hi][traded] / opened[lo:hi][traded] - 1.0) * 100.0
    out["K_base"] = float(np.median(usd[lo:hi][traded] / np.maximum(move, 0.05)))
    out["K3"] = out["D3"] / max(abs(pct_3m), 0.10)
    out["A"] = out["K3"] / out["K_base"]
    return out


def add_features(df: pd.DataFrame, candles: dict) -> pd.DataFrame:
    rows = list(zip(df["entered_ts"], df["pct_3m"], df["product_id"]))
    for suffix, delay in (("", 0), ("_delay", 1)):
        f = [entry_features(t, p, candles.get(pid), delay) for t, p, pid in rows]
        for col in ("D3", "A"):
            df[col + suffix] = [x[col] for x in f]
        if not delay:
            df["n3"], df["n60"] = [x["n3"] for x in f], [x["n60"] for x in f]
    return df


# ---------- Part A arms ----------


def gate_pass(d3: np.ndarray, threshold: float) -> np.ndarray:
    return (d3 > 0) & (d3 >= threshold)


def top_k(order: np.ndarray, mask: np.ndarray, k: int) -> np.ndarray:
    return order[mask[order]][:k]


def same_day_arms(rank, d3, amult, ids) -> dict:
    """Exact floor(Q*N) flags per arm, ranked within the whole day."""
    n = len(rank)
    k = int(np.floor(Q * n))
    order = np.lexsort((ids, -rank))
    out = {name: np.zeros(n, dtype=bool) for name in ARMS}
    out["gate"] = gate_pass(d3, float(np.median(d3)))
    out["strict"] = out["gate"] & (amult >= A_MULT_MIN)
    out["a0"][order[:k]] = True
    out["a1"][top_k(order, out["gate"], k)] = True
    wide = gate_pass(d3, float(np.quantile(d3, GATE_Q30)))
    out["a1_q30"][top_k(order, wide, k)] = True
    chosen = top_k(order, out["strict"], k)
    out["a2"][chosen] = True
    short = k - len(chosen)
    if short > 0:
        rest = np.flatnonzero(out["gate"] & ~out["strict"])
        score = d3[rest] * amult[rest]
        fill = rest[np.lexsort((ids[rest], -rank[rest], -score))][:short]
        out["a2"][fill] = out["a2_backfill"][fill] = True
    out["a3"] = out["a0"] & out["gate"]
    return out


def causal_arms(rank, d3, amult, w, today) -> dict:
    """Flags for `today` from thresholds set on the trailing rows `w` only."""
    out = {"a0": rank[today] >= np.quantile(rank[w], 1 - Q)}
    cuts = {
        "a1": float(np.median(d3[w])),
        "a1_q30": float(np.quantile(d3[w], GATE_Q30)),
    }
    for name, threshold in cuts.items():
        pw = gate_pass(d3[w], threshold)
        share = float(pw.mean())
        cut = np.quantile(rank[w][pw], 1 - Q / share) if share > Q else -np.inf
        out[name] = gate_pass(d3[today], threshold) & (rank[today] >= cut)
    pw, pt = gate_pass(d3[w], cuts["a1"]), gate_pass(d3[today], cuts["a1"])
    sw, st = pw & (amult[w] >= A_MULT_MIN), pt & (amult[today] >= A_MULT_MIN)
    share = float(sw.mean())
    fill = np.zeros(len(today), dtype=bool)
    if share > Q:
        strict = st & (rank[today] >= np.quantile(rank[w][sw], 1 - Q / share))
    else:
        strict = st
        rest = w[pw & ~sw]
        want = int(np.floor(Q * len(w))) - int(sw.sum())
        rest_today = pt & ~st
        if want >= len(rest):
            fill = rest_today
        elif want > 0:
            score = d3[rest] * amult[rest]
            last = rest[np.lexsort((-rank[rest], -score))[want - 1]]
            cut_score, cut_rank = d3[last] * amult[last], rank[last]
            today_score = d3[today] * amult[today]
            tied = (today_score == cut_score) & (rank[today] >= cut_rank)
            fill = rest_today & ((today_score > cut_score) | tied)
    out.update(
        a2=strict | fill, a2_backfill=fill, a3=out["a0"] & pt, gate=pt, strict=st
    )
    return out


def build_flags(g: pd.DataFrame, rank_col="B0", d3_col="D3", a_col="A") -> pd.DataFrame:
    """Both modes for one board. `sd_` is same-day quota, `ca_` is causal."""
    g = g.sort_values(["entered_ts", "id"]).reset_index(drop=True)
    rank, d3, amult = (g[c].to_numpy(float) for c in (rank_col, d3_col, a_col))
    ids, day = g["id"].to_numpy(), g["day"].to_numpy()
    idx = {d: np.flatnonzero(day == d) for d in np.unique(day)}
    cols = {
        f"{m}_{a}": np.zeros(len(g), dtype=bool) for m in ("sd", "ca") for a in ARMS
    }
    scored = np.zeros(len(g), dtype=bool)
    for d, today in idx.items():
        arms = same_day_arms(rank[today], d3[today], amult[today], ids[today])
        for name, mask in arms.items():
            cols[f"sd_{name}"][today] = mask
        prev = [
            (pd.Timestamp(d) - pd.Timedelta(days=j)).strftime("%Y-%m-%d")
            for j in range(1, 8)
        ]
        if not all(p in idx for p in prev):
            continue
        w = np.concatenate([idx[p] for p in prev])
        for name, mask in causal_arms(rank, d3, amult, w, today).items():
            cols[f"ca_{name}"][today] = mask
        scored[today] = True
    out = g[["id", "day", "runner", "crasher"]].copy()
    for name, mask in cols.items():
        out[name] = mask
    out["scored"] = scored
    return out


# ---------- Part A metrics ----------


def boot(v: np.ndarray, block: int) -> dict:
    """Percentile interval of the mean over resampled blocks of consecutive days."""
    if len(v) < 2 * block:
        return {"lo": None, "hi": None}
    chunks = [v[i : i + block] for i in range(0, len(v), block)]
    sums = np.array([c.sum() for c in chunks])
    counts = np.array([len(c) for c in chunks])
    pick = np.random.default_rng(SEED).integers(0, len(chunks), (REPS, len(chunks)))
    means = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"lo": float(lo), "hi": float(hi)}


def delta(v: np.ndarray) -> dict:
    if not len(v):
        return {"mean": None, "n_days": 0}
    return {
        "mean": float(v.mean()),
        "n_days": int(len(v)),
        "days_negative": int((v < 0).sum()),
        "daily_sd": float(v.std(ddof=1)) if len(v) > 1 else None,
        "block3": boot(v, BLOCK),
        "daily": boot(v, 1),
    }


def tally(w: pd.DataFrame, mask: np.ndarray) -> dict:
    return {
        "flags": int(mask.sum()),
        "runners": int(w["runner"].to_numpy()[mask].sum()),
        "crashers": int(w["crasher"].to_numpy()[mask].sum()),
    }


def compare(f: pd.DataFrame, mode: str, base: str, arm: str, lo: str, hi: str) -> dict:
    """Paired daily comparison of `arm` against `base` for one board and window."""
    w = f[(f["day"] >= lo) & (f["day"] <= hi)]
    if mode == "ca":
        w = w[w["scored"]]
    days = []
    for _, gd in w.groupby("day"):
        mb, ma = gd[f"{mode}_{base}"].to_numpy(), gd[f"{mode}_{arm}"].to_numpy()
        r, c = gd["runner"].to_numpy(), gd["crasher"].to_numpy()
        ok = len(gd) >= MIN_ROWS and mb.any() and ma.any()
        if mode == "sd":
            ok = ok and r.sum() >= MIN_RUNNERS
        rec = {"flags_base": int(mb.sum()), "flags_arm": int(ma.sum()), "scored": ok}
        if ok:
            rec.update(
                rb=r[mb].mean(), cb=c[mb].mean(), ra=r[ma].mean(), ca=c[ma].mean()
            )
        days.append(rec)
    mb, ma = w[f"{mode}_{base}"].to_numpy(), w[f"{mode}_{arm}"].to_numpy()
    tb, ta = tally(w, mb), tally(w, ma)
    out = {
        "days_in_window": len(days),
        "days_scored": sum(d["scored"] for d in days),
        "entries": int(len(w)),
        "flags": {
            "base": tb["flags"],
            "arm": ta["flags"],
            "base_share": tb["flags"] / len(w) if len(w) else None,
            "arm_share": ta["flags"] / len(w) if len(w) else None,
            "base_per_day": spread([d["flags_base"] for d in days]),
            "arm_per_day": spread([d["flags_arm"] for d in days]),
        },
        "counts": {
            "base": tb,
            "arm": ta,
            "both": tally(w, mb & ma),
            "base_only": tally(w, mb & ~ma),
            "arm_only": tally(w, ~mb & ma),
        },
    }
    v = pd.DataFrame([d for d in days if d["scored"]])
    if len(v):
        dp, dc = (v["ra"] - v["rb"]).to_numpy(), (v["ca"] - v["cb"]).to_numpy()
        out["rates"] = {
            "runner_base": float(v["rb"].mean()),
            "crasher_base": float(v["cb"].mean()),
            "net_base": float((v["rb"] - v["cb"]).mean()),
            "runner_arm": float(v["ra"].mean()),
            "crasher_arm": float(v["ca"].mean()),
            "net_arm": float((v["ra"] - v["ca"]).mean()),
        }
        out.update(delta_P=delta(dp), delta_C=delta(dc), delta_N=delta(dp - dc))
    if arm == "a3":
        gone = out["counts"]["base_only"]
        out["veto"] = {
            "flags_dropped": gone["flags"],
            "runners_missed": gone["runners"],
            "crashers_avoided": gone["crashers"],
            "runner_recall": ratio(tb["runners"] - gone["runners"], tb["runners"]),
            "crashers_avoided_share": ratio(gone["crashers"], tb["crashers"]),
            "crashers_avoided_per_runner_missed": ratio(
                gone["crashers"], gone["runners"]
            ),
        }
    if arm == "a2":
        out["backfilled_flags"] = int(w[f"{mode}_a2_backfill"].sum())
    return out


def ratio(a, b):
    return float(a) / float(b) if b else None


def spread(values: list) -> dict | None:
    if not values:
        return None
    a = np.array(values)
    return {"mean": float(a.mean()), "min": int(a.min()), "max": int(a.max())}


def part_a_tables(flags: dict) -> dict:
    out = {"same_day_quota": {}, "causal_trailing_7d": {}}
    for label, mode, windows in (
        ("same_day_quota", "sd", SAME_DAY_WINDOWS),
        ("causal_trailing_7d", "ca", CAUSAL_WINDOWS),
    ):
        for window, (lo, hi) in windows.items():
            out[label][window] = {
                board: {
                    name: compare(flags[board], mode, base, arm, lo, hi)
                    for name, base, arm in COMPARISONS
                }
                for board in BOARDS
            }
    return out


def profile_a(df: pd.DataFrame, flags: dict) -> dict:
    """Outcome-blind description of the gate inputs."""
    out = {}
    for window, (lo, hi) in SAME_DAY_WINDOWS.items():
        out[window] = {}
        for board in BOARDS:
            w = df[(df["stratum"] == board) & (df["day"] >= lo) & (df["day"] <= hi)]
            f = flags[board]
            f = f[(f["day"] >= lo) & (f["day"] <= hi)]
            traded = Counter(w["n3"])
            out[window][board] = {
                "entries": int(len(w)),
                "traded_minutes_of_three": {str(i): int(traded[i]) for i in range(4)},
                "D3_zero_share": float((w["D3"] == 0).mean()),
                "D3_median_usd": float(w["D3"].median()),
                "baseline_10_traded_minutes_share": float((w["n60"] >= 10).mean()),
                "A_mult_ge_1p5_share": float((w["A"] >= A_MULT_MIN).mean()),
                "A_mult_median_when_defined": float(
                    w.loc[w["n60"] >= 10, "A"].median()
                ),
                "same_day_gate_share": float(f["sd_gate"].mean()),
                "same_day_strict_share": float(f["sd_strict"].mean()),
                "rank_spearman_B0_vs_snapshot_move": float(
                    w["B0"].rank().corr(w["S"].rank())  # no scipy in this env
                ),
            }
    return out


def reading_a(tables: dict) -> dict:
    board = "confirmation_3m_up/up"
    screen = tables["causal_trailing_7d"]["screen"][board]
    check = tables["causal_trailing_7d"]["check"][board]
    out = {"board": board, "mode": "causal_trailing_7d", "rule": HOLD_RULE, "arms": {}}
    for name in ("a1_vs_a0", "a1_q30_vs_a0", "a2_vs_a0"):
        s, c = screen[name], check[name]
        checks = {
            "screen_dP_mean": s["delta_P"]["mean"] >= HOLD_RULE["dp_mean"],
            "screen_dP_block_lo": s["delta_P"]["block3"]["lo"] >= HOLD_RULE["dp_lo"],
            "screen_dC_mean": s["delta_C"]["mean"] <= HOLD_RULE["dc_mean"],
            "screen_dC_block_hi": s["delta_C"]["block3"]["hi"] <= HOLD_RULE["dc_hi"],
            "check_dP": c["delta_P"]["mean"] >= HOLD_RULE["dp_mean"],
            "check_dC": c["delta_C"]["mean"] < 0,
        }
        out["arms"][name] = {"holds": all(checks.values()), "checks": checks}
    s, c = screen["a2_vs_a1"], check["a2_vs_a1"]
    checks = {
        "screen_dC_mean": s["delta_C"]["mean"] < 0,
        "screen_dC_block_hi": s["delta_C"]["block3"]["hi"] < 0,
        "screen_dP_mean": s["delta_P"]["mean"] >= HOLD_RULE["dp_mean"],
        "check_dC": c["delta_C"]["mean"] < 0,
        "check_dP": c["delta_P"]["mean"] >= HOLD_RULE["dp_mean"],
    }
    out["absorption_adds_to_dollar_gate"] = {
        "adds": all(checks.values()),
        "checks": checks,
    }
    return out


def parity_a(tables: dict) -> dict:
    """Compare A0 and A1 with the numbers earlier screens published."""
    out = {"step2_same_day_B0_screen": {}}
    for board, (runner, crasher) in STEP2_B0.items():
        rates = tables["same_day_quota"]["screen"][board]["a1_vs_a0"]["rates"]
        got = (
            round(100 * rates["runner_base"], 2),
            round(100 * rates["crasher_base"], 2),
        )
        out["step2_same_day_B0_screen"][board] = {
            "published": [runner, crasher],
            "this_run": list(got),
            "match": got == (runner, crasher),
        }
    ref = tables["causal_trailing_7d"]["gate_reference_parity"]["confirmation_3m_up/up"]
    ref = ref["a1_vs_a0"]
    got = (
        round(100 * ref["delta_P"]["mean"], 2),
        round(100 * ref["delta_C"]["mean"], 2),
    )
    out["nov14_gate_reference_3m_up"] = {
        "published": list(GATE_REFERENCE_3M_UP),
        "this_run": list(got),
        "match": got == GATE_REFERENCE_3M_UP,
    }
    return out


def primary_flags(df: pd.DataFrame) -> dict:
    return {b: build_flags(df[df["stratum"] == b]) for b in BOARDS}


def part_a(df: pd.DataFrame, flags: dict) -> dict:
    by_board = {b: df[df["stratum"] == b] for b in BOARDS}
    tables = part_a_tables(flags)
    sens = {
        "rank_by_snapshot_move": part_a_tables(
            {b: build_flags(g, rank_col="S") for b, g in by_board.items()}
        ),
        "candle_one_minute_earlier": part_a_tables(
            {
                b: build_flags(g, d3_col="D3_delay", a_col="A_delay")
                for b, g in by_board.items()
            }
        ),
    }
    return {
        "profile": profile_a(df, flags),
        "results": tables,
        "reading": reading_a(tables),
        "parity": parity_a(tables),
        "sensitivities": sens,
    }


# ---------- Part B market ----------


def dense_market(frame: pd.DataFrame) -> SimpleNamespace:
    """Product by minute arrays. No bar: close NaN, high -inf, low +inf, dollars 0."""
    products = sorted(
        p
        for p in frame["product_id"].unique()
        if p.endswith("-USD") and p[:-4] not in carbon.STABLECOINS
    )
    index = {p: i for i, p in enumerate(products)}
    sub = frame[frame["product_id"].isin(index)]
    row = sub["product_id"].map(index).to_numpy()
    col = (sub["ts"] // 60 - FIRST_MINUTE).to_numpy()
    shape = (len(products), LAST_MINUTE - FIRST_MINUTE)
    close = np.full(shape, np.nan)
    high, low, dollar = np.full(shape, -np.inf), np.full(shape, np.inf), np.zeros(shape)
    close[row, col], high[row, col], low[row, col] = (
        sub["close"],
        sub["high"],
        sub["low"],
    )
    dollar[row, col] = sub["close"] * sub["volume"]
    return market(products, close, high, low, dollar)


def market(products, close, high, low, dollar) -> SimpleNamespace:
    with np.errstate(invalid="ignore"):
        log_close = np.log(close)
    traded = np.isfinite(close)
    observed = np.pad(np.cumsum(traded, axis=1, dtype=np.int32), ((0, 0), (1, 0)))
    dollar_sum = np.pad(np.cumsum(dollar, axis=1), ((0, 0), (1, 0)))
    return SimpleNamespace(
        products=list(products),
        close=close,
        high=high,
        low=low,
        log_close=log_close,
        observed=observed,
        dollar_sum=dollar_sum,
    )


def volume_pace(mk, m0: int, rows) -> np.ndarray:
    """15m dollars over the 15m-equivalent of the 4h before them; NaN if no baseline."""
    recent = mk.dollar_sum[rows, m0 + 1] - mk.dollar_sum[rows, m0 - 14]
    earlier = mk.dollar_sum[rows, m0 - 14] - mk.dollar_sum[rows, m0 - 254]
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(earlier > 0, recent / (earlier / 16.0), np.nan)


def coil_features(mk, m0: int, rows) -> dict:
    """B1 inputs at the last usable minute m0. Windows are inclusive minute bins."""
    h4 = mk.high[rows, m0 - 243 : m0 - 2].max(axis=1)
    l4 = mk.low[rows, m0 - 243 : m0 - 2].min(axis=1)
    h24 = mk.high[rows, m0 - 1443 : m0 - 2].max(axis=1)
    l24 = mk.low[rows, m0 - 1443 : m0 - 2].min(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        range4, range24 = np.log(h4 / l4), np.log(h24 / l24)
        ok = np.isfinite(range4) & np.isfinite(range24) & (range24 > 0)
        c_ratio = np.where(ok, range4 / (math.sqrt(4 / 24) * range24), np.nan)
    return {"H4": h4, "C_ratio": c_ratio, "V_pace": volume_pace(mk, m0, rows)}


def grind_features(mk, m0: int, rows) -> dict:
    """B2 inputs: 15m return and where the close sits in the 15m range."""
    close = mk.close[rows, m0]
    h15 = mk.high[rows, m0 - 14 : m0 + 1].max(axis=1)
    l15 = mk.low[rows, m0 - 14 : m0 + 1].min(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        position = np.where(h15 > l15, (close - l15) / (h15 - l15), np.nan)
        r15 = close / mk.close[rows, m0 - 15] - 1.0
    return {"r15": r15, "position": position, "V_pace": volume_pace(mk, m0, rows)}


def ordered(rows: np.ndarray, keep: np.ndarray, score: np.ndarray) -> np.ndarray:
    """Qualifying products, best score first, ties to the lower product index."""
    picked, values = rows[keep], score[keep]
    return picked[np.argsort(-values, kind="stable")]


def universe_rows(mk, m0: int) -> tuple:
    """Active products with a trade at m0, outside the synthetic top eight."""
    one, three, active = carbon.ranked_movers(mk.log_close, mk.observed, m0)
    universe = active & np.isfinite(mk.close[:, m0])
    universe[list(carbon.top_eight(one, three, active, 1))] = False
    return np.flatnonzero(universe), one, three


def cutoff_candidates(mk, cutoff: int) -> dict:
    """Each arm's qualifying products at one cutoff, ranked, before cooldown."""
    m0 = cutoff - 2
    rows, one, three = universe_rows(mk, m0)
    close, move = mk.close[rows, m0], three[rows]
    with np.errstate(invalid="ignore"):
        moving = move >= MOVE_FLOOR
        coil = coil_features(mk, m0, rows)
        near = (close >= coil["H4"] * (1 - 0.0015)) & moving
        b1 = (coil["C_ratio"] <= 0.75) & (coil["V_pace"] >= 2.0)
        b1 &= (close > coil["H4"]) | near
        grind = grind_features(mk, m0, rows)
        b2 = (grind["r15"] >= 0.002) & (grind["r15"] <= 0.012)
        b2 &= (grind["V_pace"] >= 2.5) & (grind["position"] >= 0.75)
        coil_score = coil["V_pace"] / np.maximum(coil["C_ratio"], 0.05)
    return {
        "baseline": ordered(rows, moving & np.isfinite(one[rows]), move),
        "b1": ordered(rows, b1, coil_score),
        "b2": ordered(rows, b2, grind["V_pace"]),
    }


def replay(candidates: dict, cutoffs, n_products: int) -> list:
    """One flag per cutoff: the best candidate not flagged in the last hour."""
    last = np.full(n_products, -(10**9))
    flags = []
    for cutoff in cutoffs:
        for product in candidates.get(cutoff, ()):
            if cutoff - last[product] >= COOLDOWN:
                last[product] = cutoff
                flags.append((cutoff, int(product)))
                break
    return flags


# ---------- Part B live board ----------


def live_index(hist: pd.DataFrame) -> tuple[dict, np.ndarray]:
    """Per product: live up-board entry times and episode ends. Plus capture gaps."""
    up = hist[hist["board"].isin(LIVE_UP_BOARDS) & (hist["direction"] == "up")]
    end = up["exited_ts"].fillna(up["last_seen_ts"]).fillna(up["entered_ts"])
    up = up.assign(end_ts=end.astype("int64")).sort_values("entered_ts")
    spans = {
        product: (g["entered_ts"].to_numpy(), g["end_ts"].to_numpy())
        for product, g in up.groupby("product_id", sort=False)
    }
    return spans, capture_gaps(np.sort(hist["entered_ts"].to_numpy()))


def capture_gaps(entered: np.ndarray) -> np.ndarray:
    """Intervals with no recorded entry on any board for more than CAPTURE_GAP."""
    edges = np.concatenate([[START - 86400], entered, [END + 86400]])
    wide = np.flatnonzero(np.diff(edges) > CAPTURE_GAP)
    return np.column_stack([edges[wide], edges[wide + 1]])


def live_observable(gaps: np.ndarray, t: int) -> bool:
    """False when (t, t + LIVE_HORIZON] overlaps a capture gap."""
    return not bool(((gaps[:, 0] < t + LIVE_HORIZON) & (gaps[:, 1] > t)).any())


def live_graduation(span: tuple | None, t: int) -> tuple[bool, int | None]:
    """(already on a live up board at t, seconds to the first entry in (t, t+900])."""
    if span is None:
        return False, None
    entered, end = span
    on_board = bool(((entered <= t) & (end >= t)).any())
    i = int(np.searchsorted(entered, t, side="right"))
    if i < len(entered) and entered[i] <= t + LIVE_HORIZON:
        return on_board, int(entered[i] - t)
    return on_board, None


def grade_flags(
    flags: list, mk, spans: dict, gaps: np.ndarray, cache: dict
) -> pd.DataFrame:
    rows = []
    for cutoff, product in flags:
        key = (cutoff, product)
        if key not in cache:
            t = (FIRST_MINUTE + cutoff) * 60
            grade = carbon.early_grade(
                mk.close, mk.log_close, mk.observed, product, cutoff, cutoff - 2
            )
            on_board, lead = live_graduation(spans.get(mk.products[product]), t)
            cache[key] = {
                "cutoff": cutoff,
                "product": mk.products[product],
                "ts": t,
                "graded": grade is not None,
                "result": grade[0] if grade else 0,
                "synthetic_lead_min": grade[1] if grade else None,
                "live_observable": live_observable(gaps, t),
                "on_live_board": on_board,
                "live_lead_s": lead,
            }
        rows.append(cache[key])
    df = pd.DataFrame(rows, columns=FLAG_COLUMNS)
    df["day"] = utc_day(df["ts"])
    return df


def day_counts(flags: pd.DataFrame, days: list) -> pd.DataFrame:
    seen = flags["live_observable"]
    grad = seen & flags["live_lead_s"].notna()
    fresh = seen & ~flags["on_live_board"]
    cols = {
        "flags": np.ones(len(flags), dtype=int),
        "graded": flags["graded"],
        "runners": flags["graded"] & (flags["result"] == 1),
        "reversals": flags["graded"] & (flags["result"] == -1),
        "live_seen": seen,
        "live_grads": grad,
        "fresh_seen": fresh,
        "fresh_grads": fresh & grad,
    }
    table = pd.DataFrame({k: np.asarray(v, dtype=int) for k, v in cols.items()})
    table["net"] = table["runners"] - table["reversals"]
    return table.groupby(flags["day"].to_numpy()).sum().reindex(days, fill_value=0)


def summarize_flags(flags: pd.DataFrame, lo: str, hi: str) -> dict:
    w = flags[(flags["day"] >= lo) & (flags["day"] <= hi)]
    c = day_counts(w, sorted(w["day"].unique())).sum()
    winners = w[w["graded"] & (w["result"] == 1)]
    synth = winners["synthetic_lead_min"].dropna()
    grads = w.loc[w["live_observable"], "live_lead_s"].dropna()
    fresh = w.loc[w["live_observable"] & ~w["on_live_board"], "live_lead_s"].dropna()
    return {
        "flags": int(c["flags"]),
        "graded": int(c["graded"]),
        "runners": int(c["runners"]),
        "reversals": int(c["reversals"]),
        "runner_rate": ratio(c["runners"], c["graded"]),
        "reversal_rate": ratio(c["reversals"], c["graded"]),
        "net": ratio(c["runners"] - c["reversals"], c["graded"]),
        "synthetic_graduates_among_runners": int(len(synth)),
        "synthetic_median_lead_min": float(synth.median()) if len(synth) else None,
        "live_observable_flags": int(c["live_seen"]),
        "already_on_live_board": int((w["live_observable"] & w["on_live_board"]).sum()),
        "live_graduations": int(c["live_grads"]),
        "live_graduation_rate": ratio(c["live_grads"], c["live_seen"]),
        "live_median_lead_s": float(grads.median()) if len(grads) else None,
        "fresh_live_graduation_rate": ratio(c["fresh_grads"], c["fresh_seen"]),
        "fresh_live_median_lead_s": float(fresh.median()) if len(fresh) else None,
    }


def block_sums(table: pd.DataFrame, col: str) -> np.ndarray:
    values = table[col].to_numpy(float)
    return np.add.reduceat(values, np.arange(0, len(values), BLOCK))


def pooled_delta(
    a: pd.DataFrame, b: pd.DataFrame, numerator: str, denominator: str
) -> dict:
    """Arm rate minus baseline rate, with a three-day block interval over days."""
    na, da = block_sums(a, numerator), block_sums(a, denominator)
    nb, db = block_sums(b, numerator), block_sums(b, denominator)
    out = {"delta": None, "block3": {"lo": None, "hi": None}}
    if da.sum() and db.sum():
        out["delta"] = float(na.sum() / da.sum() - nb.sum() / db.sum())
    if len(na) >= 2:
        pick = np.random.default_rng(SEED).integers(0, len(na), (REPS, len(na)))
        with np.errstate(divide="ignore", invalid="ignore"):
            draws = na[pick].sum(axis=1) / da[pick].sum(axis=1)
            draws = draws - nb[pick].sum(axis=1) / db[pick].sum(axis=1)
        usable = np.isfinite(draws)
        if usable.mean() >= 0.95:
            lo, hi = np.percentile(draws[usable], [2.5, 97.5])
            out["block3"] = {"lo": float(lo), "hi": float(hi)}
    return out


def compare_flags(arm: pd.DataFrame, base: pd.DataFrame, lo: str, hi: str) -> dict:
    days = list(pd.date_range(lo, hi).strftime("%Y-%m-%d"))
    a, b = day_counts(arm, days), day_counts(base, days)
    return {
        "runner_rate": pooled_delta(a, b, "runners", "graded"),
        "reversal_rate": pooled_delta(a, b, "reversals", "graded"),
        "net": pooled_delta(a, b, "net", "graded"),
        "live_graduation_rate": pooled_delta(a, b, "live_grads", "live_seen"),
        "fresh_live_graduation_rate": pooled_delta(a, b, "fresh_grads", "fresh_seen"),
    }


def reading_b(matched: dict) -> dict:
    out = {"min_gain": BEAT_RULE, "arms": {}}
    for arm, block in matched.items():
        s, c = block["delta"]["screen"], block["delta"]["check"]

        def beats(key):
            lo = s[key]["block3"]["lo"]
            ok = s[key]["delta"] is not None and s[key]["delta"] >= BEAT_RULE
            ok = ok and lo is not None and lo > 0
            return bool(ok and c[key]["delta"] is not None and c[key]["delta"] > 0)

        net = s["net"]["delta"]
        out["arms"][arm] = {
            "beats_on_sustained_runner": beats("runner_rate")
            and net is not None
            and net > 0,
            "beats_on_live_graduation": beats("live_graduation_rate"),
        }
    return out


def part_b(frame: pd.DataFrame, hist: pd.DataFrame) -> dict:
    mk = dense_market(frame)
    spans, gaps = live_index(hist)
    cutoffs = range(START // 60 - FIRST_MINUTE, END // 60 - FIRST_MINUTE, STEP)
    found = {arm: {} for arm in ("baseline", "b1", "b2")}
    for cutoff in cutoffs:
        for arm, picked in cutoff_candidates(mk, cutoff).items():
            if len(picked):
                found[arm][cutoff] = picked
    cache, n = {}, len(mk.products)

    def run_arm(arm, where):
        return grade_flags(replay(found[arm], where, n), mk, spans, gaps, cache)

    def table(flags):
        return {
            name: summarize_flags(flags, lo, hi) for name, (lo, hi) in B_WINDOWS.items()
        }

    def deltas(arm, base):
        return {
            name: compare_flags(arm, base, lo, hi)
            for name, (lo, hi) in B_WINDOWS.items()
        }

    everywhere = {arm: run_arm(arm, cutoffs) for arm in found}
    out = {
        "profile": {
            "products": n,
            "traded_minute_bars": int(np.isfinite(mk.close).sum()),
            "cutoffs": len(cutoffs),
            "cutoffs_with_candidates": {arm: len(v) for arm, v in found.items()},
            "mean_candidates_when_any": {
                arm: float(np.mean([len(x) for x in v.values()])) if v else None
                for arm, v in found.items()
            },
            "capture_gaps_over_600s": int(len(gaps)),
            "live_entry_rank_max": {
                board: int(g["entry_rank"].max())
                for board, g in hist[hist["board"].isin(LIVE_UP_BOARDS)].groupby(
                    "board"
                )
            },
        },
        "all_cutoffs": {
            "arms": {arm: table(flags) for arm, flags in everywhere.items()},
            "delta_vs_baseline": {
                arm: deltas(everywhere[arm], everywhere["baseline"])
                for arm in ("b1", "b2")
            },
        },
        "matched_cutoffs": {},
    }
    for arm in ("b1", "b2"):
        both = [c for c in cutoffs if c in found[arm] and c in found["baseline"]]
        mine, base = run_arm(arm, both), run_arm("baseline", both)
        out["matched_cutoffs"][arm] = {
            "cutoffs": len(both),
            "arm": table(mine),
            "baseline": table(base),
            "delta": deltas(mine, base),
        }
    out["reading"] = reading_b(out["matched_cutoffs"])
    counts = live_base_counts(mk, spans, gaps, found["baseline"], cutoffs)
    return out, live_base_rate(counts)


# ---------- post hoc, added after the declared results were read ----------

BASE_GROUPS = ("universe", "baseline_candidates")
BASE_FIELDS = ("seen", "grads", "fresh_seen", "fresh_grads")


def live_base_counts(mk, spans: dict, gaps: np.ndarray, baseline: dict, cutoffs):
    """Live graduation of every universe product at each cutoff, flagged or not."""
    rows = []
    for cutoff in cutoffs:
        t = (FIRST_MINUTE + cutoff) * 60
        if not live_observable(gaps, t):
            continue
        members, _, _ = universe_rows(mk, cutoff - 2)
        qualified = {int(p) for p in baseline.get(cutoff, ())}
        rec = {f"{g}_{f}": 0 for g in BASE_GROUPS for f in BASE_FIELDS}
        for product in members:
            on_board, lead = live_graduation(spans.get(mk.products[product]), t)
            groups = BASE_GROUPS if int(product) in qualified else BASE_GROUPS[:1]
            for group in groups:
                rec[f"{group}_seen"] += 1
                rec[f"{group}_grads"] += lead is not None
                rec[f"{group}_fresh_seen"] += not on_board
                rec[f"{group}_fresh_grads"] += not on_board and lead is not None
        rows.append({"ts": t, **rec})
    names = ["ts"] + [f"{g}_{f}" for g in BASE_GROUPS for f in BASE_FIELDS]
    out = pd.DataFrame(rows, columns=names)
    out["day"] = utc_day(out["ts"])
    return out


def live_base_rate(counts: pd.DataFrame) -> dict:
    """Share of universe products, and of all baseline candidates, that graduate."""
    out = {}
    for window, (lo, hi) in B_WINDOWS.items():
        c = counts[(counts["day"] >= lo) & (counts["day"] <= hi)].sum(numeric_only=True)
        out[window] = {
            group: {
                "product_cutoffs": int(c[f"{group}_seen"]),
                "live_graduation_rate": ratio(c[f"{group}_grads"], c[f"{group}_seen"]),
                "fresh_live_graduation_rate": ratio(
                    c[f"{group}_fresh_grads"], c[f"{group}_fresh_seen"]
                ),
            }
            for group in BASE_GROUPS
        }
    return out


def median(values: np.ndarray) -> float | None:
    return float(np.median(values)) if len(values) else None


def flag_inputs(df: pd.DataFrame, flags: dict) -> dict:
    """Outcome-blind: median displayed move and 3m dollars of each arm's causal flags."""
    values = df.set_index("id")[["B0", "D3"]]
    out = {}
    for window in ("screen", "check"):
        lo, hi = CAUSAL_WINDOWS[window]
        out[window] = {}
        for board in BOARDS:
            f = flags[board]
            f = f[f["scored"] & (f["day"] >= lo) & (f["day"] <= hi)]
            v = values.reindex(f["id"])
            masks = {arm: f[f"ca_{arm}"].to_numpy() for arm in ("a0", "a1", "a2", "a3")}
            masks["a0_dropped_by_gate"] = masks["a0"] & ~f["ca_gate"].to_numpy()
            masks["all_entries"] = np.ones(len(f), dtype=bool)
            out[window][board] = {
                name: {
                    "flags": int(mask.sum()),
                    "median_B0_pct": median(v["B0"].to_numpy()[mask]),
                    "median_D3_usd": median(v["D3"].to_numpy()[mask]),
                }
                for name, mask in masks.items()
            }
    return out


# ---------- driver ----------


def clean(obj):
    """Plain JSON types; NaN and infinities become null."""
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return float(obj) if math.isfinite(obj) else None
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    frozen = run.verify_inputs()
    contract = run.SPEC_DIR / "CONTRACT_PRODUCTION.json"
    cfg = json.loads(contract.read_text(encoding="utf-8"))
    df, hist = read_entries(CAPTURE_DB, cfg)
    rows = {
        name: int(((df["day"] >= lo) & (df["day"] <= hi)).sum())
        for name, (lo, hi) in SAME_DAY_WINDOWS.items()
    }
    if rows != EXPECTED_ROWS:
        raise SystemExit(
            f"Refusing: eligible entries {rows} differ from {EXPECTED_ROWS}."
        )
    frame = load_candle_frame(CANDLES)
    df = add_features(df, product_arrays(frame))
    flags = primary_flags(df)
    early_watch, base_rate = part_b(frame, hist)
    out = {
        "protocol_sha256": run.digest(PROTOCOL),
        "script_sha256": run.digest(Path(__file__)),
        "frozen_inputs": frozen,
        "candle_archive_sha256": run.digest(CANDLES),
        "seed": SEED,
        "replicates": REPS,
        "flag_share": Q,
        "eligible_entries": rows,
        "candle_rows_loaded": int(len(frame)),
        "part_a": part_a(df, flags),
        "part_b": early_watch,
        "post_hoc_added_after_declared_results": {
            "part_a_flag_inputs_causal": flag_inputs(df, flags),
            "part_b_live_base_rate": base_rate,
        },
    }
    args.out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(clean(out), indent=1, allow_nan=False) + "\n"
    (args.out / "RESULTS.json").write_text(text, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            clean({"a": out["part_a"]["reading"], "b": out["part_b"]["reading"]})
        )
    )
    print(json.dumps(clean(out["part_a"]["parity"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
