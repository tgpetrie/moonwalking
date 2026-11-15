"""Activity gate at entry: historical test with causal thresholds.

Protocol: docs/research/RADAR_ACTIVITY_GATE_PROTOCOL_20261114.md

    python scripts/scoring_experiment/check_activity_gate.py

Reads the two board captures and the two candle stores read-only. Refuses entries from the seal onward.
"""
from __future__ import annotations

import collections
import copy
import importlib.util
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/research/results/radar_activity_gate_20261114"
PROTOCOL = ROOT / "docs/research/RADAR_ACTIVITY_GATE_PROTOCOL_20261114.md"
STEP1 = ROOT / "docs/research/results/radar_runner_signal_screen_20261113/RESULTS.json"
ARCHIVE = Path.home() / ".moonwalking/data/candle_archive.sqlite"
BACKFILL = Path.home() / ".moonwalking/analysis/radar_candle_backfill_20261113/radar_candles.sqlite"
BACKFILL_MANIFEST = BACKFILL.with_name("MANIFEST.json")


def stamp(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())


SEAL = stamp("2026-11-13")  # entries and candles from here on are reserved for confirmation
SPLIT = stamp("2026-10-18")  # production capture before, local ledger capture from here
FIRST_DAY = "2026-09-07"
WINDOWS = {"reference": ("2026-09-14", "2026-10-11"), "test": ("2026-10-13", "2026-11-12")}
BOARDS = ("confirmation_3m_up/up", "ignition_1m/up", "confirmation_3m_down/down")
PRIMARY = ("test", "confirmation_3m_up/up", "gate_M")
Q, MIN_ROWS, SEED, REPS, BLOCK = 0.25, 20, 20261116, 5000, 3
RULE = {"delta_P_mean_min": -0.0050, "delta_P_block_lo_min": -0.0100, "delta_C_mean_max": -0.0250, "delta_C_block_hi_max": -0.0150}
VARIANTS = {  # name: (activity column, unknown-gap column, gate, unknown policy, subset)
    "gate_M": ("D3", "unknown", "M", "zero", None),
    "gate_Z": ("D3", "unknown", "Z", "zero", None),
    "gate_M_unknown_gaps_removed": ("D3", "unknown", "M", "remove", None),
    "gate_M_unknown_gaps_pass": ("D3", "unknown", "M", "pass", None),
    "gate_M_three_traded_minutes_only": ("D3", "unknown", "M", "zero", "three"),
    "gate_M_one_minute_delay": ("D3_delay", "unknown_delay", "M", "zero", None),
    "gate_M_step2_score": ("S3B", "unknown", "M", "zero", None),
}


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/scoring_experiment/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def num(x) -> float:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and np.isfinite(x) else np.nan


def assert_sealed(ts) -> None:
    if len(ts) and int(np.max(ts)) >= SEAL:
        raise SystemExit("Refusing: an entry or candle at or after 2026-11-13 00:00 UTC was loaded.")


def read_entries(db: Path, cfg: dict, freeze, lo: int, hi: int) -> pd.DataFrame:
    """Every recorded entry in [lo, hi) with its eligibility status. Cooldown state runs over the whole capture."""
    con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cooldown, recs = {}, []
    for row in con.execute("select * from episodes where entered_ts < ? order by entered_ts,id", (SEAL,)):
        _, why, _ = freeze.classify(row, cfg, cooldown)
        if not why and (not np.isfinite(num(row["gross_return_30m"])) or row["outcome_15m"] == "interrupted"):
            why = "screen_label_unavailable"
        if not lo <= row["entered_ts"] < hi:
            continue
        ok = not why
        recs.append({
            "id": row["id"], "stratum": f"{row['board']}/{row['direction']}", "product_id": row["product_id"],
            "entered_ts": int(row["entered_ts"]), "status": why or "eligible", "B0": abs(num(row["start_change_pct"])),
            "r5": num(row["gross_return_5m"]) if ok else np.nan, "r15": num(row["gross_return_15m"]) if ok else np.nan,
            "r30": num(row["gross_return_30m"]) if ok else np.nan, "fav15": num(row["max_favorable_15m"]) if ok else np.nan,
            "adv15": num(row["max_adverse_15m"]) if ok else np.nan})
    con.close()
    df = pd.DataFrame(recs)
    assert_sealed(df["entered_ts"].to_numpy())
    return df


def add_labels(df: pd.DataFrame) -> pd.DataFrame:
    df["runner"] = ((df["r15"] >= 1.0) & (df["r5"] > -0.5) & (np.maximum(df["fav15"], df["r30"]) >= 1.5)).astype(int)
    df["crasher"] = ((df["r15"] <= -1.0) & (df["r5"] < 0.5) & (np.minimum(df["adv15"], df["r30"]) <= -1.5)).astype(int)
    df["day"] = pd.to_datetime(df["entered_ts"], unit="s", utc=True).dt.strftime("%Y-%m-%d")
    return df


def merge_windows(starts, ends) -> tuple[np.ndarray, np.ndarray]:
    """Union of fetch windows; window_end is the open time of the window's last minute."""
    order = np.argsort(starts)
    s_out, e_out = [], []
    for s, e in zip(np.asarray(starts)[order], np.asarray(ends)[order]):
        if s_out and s <= e_out[-1] + 60:
            e_out[-1] = max(e_out[-1], e)
        else:
            s_out.append(s)
            e_out.append(e)
    return np.array(s_out, dtype=np.int64), np.array(e_out, dtype=np.int64)


def load_candles(paths) -> tuple[dict, dict]:
    frames, wins = [], []
    for path in paths:
        con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        frames.append(pd.read_sql("select product_id, ts, close, volume from candles where granularity=60 and ts < ?", con, params=(SEAL,)))
        wins.append(pd.read_sql("select product_id, window_start, window_end from fetched_windows "
                                "where granularity=60 and status='ok' and candles > 0", con))
        con.close()
    c = pd.concat(frames, ignore_index=True).drop_duplicates(["product_id", "ts"]).sort_values(["product_id", "ts"])
    assert_sealed(c["ts"].to_numpy())
    candles = {p: (g["ts"].to_numpy(), (g["close"] * g["volume"]).to_numpy()) for p, g in c.groupby("product_id", sort=False)}
    w = pd.concat(wins, ignore_index=True)
    cover = {p: merge_windows(g["window_start"].to_numpy(), g["window_end"].to_numpy()) for p, g in w.groupby("product_id", sort=False)}
    return candles, cover


def covered(cover: tuple | None, minute: int) -> bool:
    if cover is None:
        return False
    starts, ends = cover
    i = int(np.searchsorted(starts, minute, side="right")) - 1
    return i >= 0 and minute <= ends[i]


def activity(entered_ts: int, candles: tuple | None, cover: tuple | None, delay_minutes: int = 0) -> dict:
    """Dollar activity over the three minutes closed before entry. Missing rows are zero; unknown gaps are flagged."""
    k = (entered_ts // 60) * 60 - 60 - 60 * delay_minutes
    out = {"D3": 0.0, "n3": 0, "a15": 0, "unknown": not all(covered(cover, m) for m in (k - 120, k - 60, k))}
    if candles is not None:
        ts, usd = candles
        hi = int(np.searchsorted(ts, k, side="right"))
        lo3, lo15 = int(np.searchsorted(ts, k - 120)), int(np.searchsorted(ts, k - 840))
        out.update(D3=float(usd[lo3:hi].sum()), n3=hi - lo3, a15=hi - lo15)
    return out


def add_activity(df: pd.DataFrame, candles: dict, cover: dict) -> pd.DataFrame:
    a = [activity(t, candles.get(p), cover.get(p)) for t, p in zip(df["entered_ts"], df["product_id"])]
    b = [activity(t, candles.get(p), cover.get(p), 1) for t, p in zip(df["entered_ts"], df["product_id"])]
    for col in ("D3", "n3", "a15", "unknown"):
        df[col] = [x[col] for x in a]
    df["D3_delay"], df["unknown_delay"] = [x["D3"] for x in b], [x["unknown"] for x in b]
    df["S3B"] = np.log1p(df["D3"]) * df["a15"] / 15.0
    return df


def passes(act: np.ndarray, unk: np.ndarray, thr: float, gate: str, policy: str) -> np.ndarray:
    p = act > 0
    if gate == "M":
        p &= act >= thr
    if policy == "pass":
        p |= unk
    return p


def build_flags(g: pd.DataFrame, act_col: str, unk_col: str, gate: str, policy: str) -> pd.DataFrame:
    """Flags for one board. Every threshold for a day comes from the seven previous UTC days only."""
    g = g.sort_values(["entered_ts", "id"]).reset_index(drop=True)
    act, unk = g[act_col].to_numpy(float), g[unk_col].to_numpy(bool)
    b0, ids, day = g["B0"].to_numpy(float), g["id"].to_numpy(), g["day"].to_numpy()
    idx = {d: np.flatnonzero(day == d) for d in np.unique(day)}
    cols = {c: np.zeros(len(g), dtype=bool) for c in ("scored", "pass", "a0", "a1", "a0_full_day", "a1_full_day")}
    thr_col = np.full(len(g), np.nan)
    for d, today in idx.items():
        prev = [(pd.Timestamp(d) - pd.Timedelta(days=j)).strftime("%Y-%m-%d") for j in range(1, 8)]
        if not all(p in idx for p in prev):
            continue
        w = np.concatenate([idx[p] for p in prev])
        thr = float(np.median(act[w]))
        pw = passes(act[w], unk[w], thr, gate, policy)
        share = float(pw.mean())
        cut0 = np.quantile(b0[w], 1 - Q)
        cut1 = np.quantile(b0[w][pw], 1 - Q / share) if share > Q else -np.inf
        pt = passes(act[today], unk[today], thr, gate, policy)
        cols["scored"][today], cols["pass"][today], thr_col[today] = True, pt, thr
        cols["a0"][today] = b0[today] >= cut0
        cols["a1"][today] = pt & (b0[today] >= cut1)
        k = int(np.floor(Q * len(today)))
        order = today[np.lexsort((ids[today], -b0[today]))]
        cols["a0_full_day"][order[:k]] = True
        cols["a1_full_day"][order[cols["pass"][order]][:k]] = True
    for c, v in cols.items():
        g[c] = v
    g["gate_threshold"] = thr_col
    return g


def boot(v: np.ndarray, block: int) -> dict:
    if len(v) < 2 * block:
        return {"lo": None, "hi": None}
    chunks = [v[i:i + block] for i in range(0, len(v), block)]
    sums, counts = np.array([c.sum() for c in chunks]), np.array([len(c) for c in chunks])
    pick = np.random.default_rng(SEED).integers(0, len(chunks), (REPS, len(chunks)))
    lo, hi = np.percentile(sums[pick].sum(axis=1) / counts[pick].sum(axis=1), [2.5, 97.5])
    return {"lo": float(lo), "hi": float(hi)}


def delta(v: np.ndarray) -> dict:
    if not len(v):
        return {"mean": None, "n_days": 0}
    return {"mean": float(v.mean()), "n_days": int(len(v)), "days_negative": int((v < 0).sum()),
            "daily_sd": float(v.std(ddof=1)) if len(v) > 1 else None, "block3": boot(v, BLOCK), "daily": boot(v, 1)}


def tally(w: pd.DataFrame, mask: np.ndarray) -> dict:
    return {"alerts": int(mask.sum()), "runners": int(w["runner"].to_numpy()[mask].sum()), "crashers": int(w["crasher"].to_numpy()[mask].sum())}


def summarize(f: pd.DataFrame, a0c: str, a1c: str, lo: str, hi: str, keep_daily: bool) -> dict:
    w = f[f["scored"] & (f["day"] >= lo) & (f["day"] <= hi)]
    days = []
    for d, gd in w.groupby("day"):
        m0, m1 = gd[a0c].to_numpy(), gd[a1c].to_numpy()
        rec = {"day": d, "entries": int(len(gd)), "alerts_a0": int(m0.sum()), "alerts_a1": int(m1.sum()), "scored": False}
        if len(gd) >= MIN_ROWS and m0.any() and m1.any():
            r, c = gd["runner"].to_numpy(), gd["crasher"].to_numpy()
            rec.update(scored=True, runner_a0=float(r[m0].mean()), crasher_a0=float(c[m0].mean()),
                       runner_a1=float(r[m1].mean()), crasher_a1=float(c[m1].mean()))
        days.append(rec)
    v = pd.DataFrame([d for d in days if d["scored"]])
    a0, a1, gate = w[a0c].to_numpy(), w[a1c].to_numpy(), w["pass"].to_numpy()
    t0, t1 = tally(w, a0), tally(w, a1)
    veto = tally(w, a0 & ~gate)
    n0 = np.array([d["alerts_a0"] for d in days])
    n1 = np.array([d["alerts_a1"] for d in days])
    out = {
        "days_in_window": len(days), "days_scored": int(len(v)), "entries": int(len(w)), "gate_pass_share": float(gate.mean()) if len(w) else None,
        "alerts": {"a0_total": t0["alerts"], "a1_total": t1["alerts"], "a0_share_of_entries": t0["alerts"] / len(w) if len(w) else None,
                   "a1_share_of_entries": t1["alerts"] / len(w) if len(w) else None,
                   "a0_per_day": {"mean": float(n0.mean()), "min": int(n0.min()), "max": int(n0.max())} if len(days) else None,
                   "a1_per_day": {"mean": float(n1.mean()), "min": int(n1.min()), "max": int(n1.max())} if len(days) else None},
        "counts": {"a0": t0, "a1": t1, "raised_by_both": tally(w, a0 & a1), "a0_only_removed": tally(w, a0 & ~a1),
                   "a1_only_added": tally(w, ~a0 & a1), "net_runners_missed": t0["runners"] - t1["runners"],
                   "net_reversals_avoided": t0["crashers"] - t1["crashers"],
                   "veto_without_replacement": {**veto, "runner_recall": 1 - veto["runners"] / t0["runners"] if t0["runners"] else None,
                                                "reversals_avoided_per_runner_missed": veto["crashers"] / veto["runners"] if veto["runners"] else None}},
    }
    if len(v):
        dp = (v["runner_a1"] - v["runner_a0"]).to_numpy()
        dc = (v["crasher_a1"] - v["crasher_a0"]).to_numpy()
        out["rates"] = {k: float(v[k].mean()) for k in ("runner_a0", "crasher_a0", "runner_a1", "crasher_a1")}
        out.update(delta_P=delta(dp), delta_C=delta(dc), delta_N=delta(dp - dc))
    if keep_daily:
        out["daily"] = days
    return out


def run_variant(g: pd.DataFrame, name: str) -> pd.DataFrame:
    act_col, unk_col, gate, policy, subset = VARIANTS[name]
    if policy == "remove":
        g = g[~g[unk_col]]
    if subset == "three":
        g = g[g["n3"] == 3]
    return build_flags(g, act_col, unk_col, gate, "zero" if policy == "remove" else policy)


def minutes(w: pd.DataFrame) -> dict:
    return {"entries": int(len(w)), "traded_minutes_of_three": {str(i): int((w["n3"] == i).sum()) for i in range(4)},
            "unknown_gap": int(w["unknown"].sum()), "no_closed_candle_dollars": int((w["D3"] == 0).sum())}


def coverage(allrows: pd.DataFrame, flags: dict, lo: str, hi: str) -> dict:
    w = allrows[(allrows["day"] >= lo) & (allrows["day"] <= hi)]
    out = {}
    for board in BOARDS:
        b = w[w["stratum"] == board]
        e = b[b["status"] == "eligible"]
        rec = {"recorded": minutes(b), "eligibility": dict(collections.Counter(b["status"]).most_common()), "eligible": minutes(e)}
        for gate in ("gate_M", "gate_Z"):
            f = flags[board][gate]
            f = f[f["scored"] & (f["day"] >= lo) & (f["day"] <= hi)]
            rec[f"{gate}_pass_share"] = float(f["pass"].mean())
        f = flags[board]["gate_M"]
        thr = f[f["scored"] & (f["day"] >= lo) & (f["day"] <= hi)].groupby("day")["gate_threshold"].first()
        rec["gate_M_threshold_usd"] = {"median": float(thr.median()), "min": float(thr.min()), "max": float(thr.max())}
        out[board] = rec
    out["other_board_or_direction"] = int((~w["stratum"].isin(BOARDS)).sum())
    return out


def decide(primary: dict) -> dict:
    dp, dc = primary.get("delta_P"), primary.get("delta_C")
    if not dp or not dc or dp["block3"]["lo"] is None:
        return {"survives": False, "reason": "primary comparison not scored"}
    checks = {"delta_P_mean": dp["mean"] >= RULE["delta_P_mean_min"], "delta_P_block_lo": dp["block3"]["lo"] >= RULE["delta_P_block_lo_min"],
              "delta_C_mean": dc["mean"] <= RULE["delta_C_mean_max"], "delta_C_block_hi": dc["block3"]["hi"] <= RULE["delta_C_block_hi_max"]}
    return {"survives": bool(all(checks.values())), "checks": {k: bool(v) for k, v in checks.items()}, "rule": RULE}


def main() -> int:
    screen, run, freeze = load("screen_runner_signals"), load("live_movers_run"), load("freeze_live_contract")
    cfg = json.loads((run.SPEC_DIR / "CONTRACT_PRODUCTION.json").read_text(encoding="utf-8"))
    late = copy.deepcopy(cfg)
    late["phases"] = {"late": ["2026-10-18T00:00:00+00:00", "2026-11-13T00:00:00+00:00"]}
    frozen = run.verify_inputs()
    hashes = {"local_capture": run.digest(screen.LOCAL), "candle_archive": run.digest(ARCHIVE), "candle_backfill": run.digest(BACKFILL)}
    if hashes["local_capture"] != json.loads(STEP1.read_text(encoding="utf-8"))["local_capture_sha256"]:
        raise SystemExit("Refusing: local capture differs from the one step 1 recorded.")
    if hashes["candle_backfill"] != json.loads(BACKFILL_MANIFEST.read_text(encoding="utf-8"))["archive_sha256"]:
        raise SystemExit("Refusing: candle backfill differs from its manifest.")
    allrows = pd.concat([read_entries(screen.PRODUCTION, cfg, freeze, stamp(FIRST_DAY), SPLIT),
                         read_entries(screen.LOCAL, late, freeze, SPLIT, SEAL)], ignore_index=True)
    candles, cover = load_candles([ARCHIVE, BACKFILL])
    allrows = add_activity(add_labels(allrows), candles, cover)
    elig = allrows[allrows["status"] == "eligible"]
    flags = {b: {name: run_variant(elig[elig["stratum"] == b], name) for name in VARIANTS} for b in BOARDS}
    out = {"protocol_sha256": run.digest(PROTOCOL), "script_sha256": run.digest(Path(__file__)), "frozen_inputs": frozen, "input_sha256": hashes,
           "seal_utc": "2026-11-13T00:00:00+00:00", "last_entry_loaded_utc": datetime.fromtimestamp(int(allrows["entered_ts"].max()), timezone.utc).isoformat(),
           "seed": SEED, "replicates": REPS, "flag_share": Q, "windows": WINDOWS, "coverage": {}, "results": {}}
    for wname, (lo, hi) in WINDOWS.items():
        out["coverage"][wname] = coverage(allrows, flags, lo, hi)
        out["results"][wname] = {b: {name: {
            "entry_time": summarize(flags[b][name], "a0", "a1", lo, hi, name in ("gate_M", "gate_Z")),
            "retrospective_full_day_ranking": summarize(flags[b][name], "a0_full_day", "a1_full_day", lo, hi, False)}
            for name in VARIANTS} for b in BOARDS}
    w, b, name = PRIMARY
    out["decision"] = {"primary": {"window": w, "board": b, "variant": name, "comparison": "entry_time"},
                       **decide(out["results"][w][b][name]["entry_time"])}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "RESULTS.json").write_text(json.dumps(out, indent=1, allow_nan=False, default=float) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out["decision"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
