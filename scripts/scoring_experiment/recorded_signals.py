"""Short-horizon continuation/exhaustion check on RECORDED production signals (exploratory).

Population: signals the live system actually fired (so it is selected by the live rules and
covers about 13 weeks). Compares the live read `CONTINUATION FAVORED` (implied claim: the up
move continues) and `REVERSAL RISK RISING` (implied claim: the up move is failing) with clean
matched same-coin non-signal hours. The 13-week population was used in earlier audits, so
nothing here is independent confirmation; there is no discovery/test split, only a
first-half / second-half stability check.

Inputs (local, read-only, not in Git): ~/.moonwalking/analysis/recon.sqlite (candle-built
outcomes for signal and base hours) and the latest ~/.moonwalking/prod-backup/*/signal_outcomes.sqlite.
Their SHA-256 digests are written to the output.

    python scripts/scoring_experiment/recorded_signals.py
"""
from __future__ import annotations

import glob
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate as ev  # noqa: E402
import panel  # noqa: E402

HOME = Path.home() / ".moonwalking"
OUT = HERE.parents[1] / "docs" / "research" / "results" / "scoring_baseline"
CLEAN_HOURS = 3
READS = [("CONTINUATION FAVORED", "up", +1), ("REVERSAL RISK RISING", "up", -1),
         ("BREAKDOWN CONFIRMED", "down", +1), ("DOWNSIDE PRESSURE BUILDING", "down", +1)]
OUTCOMES = {"netR21": "net R (1 ATR stop / 2 ATR target, 0.2% cost)", "r4": "4h return in ATR",
            "r12": "12h return in ATR", "r24": "24h return in ATR"}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def bucket(b: float) -> int:
    return 0 if b < -0.005 else 2 if b > 0.005 else 1


def load():
    recon = sqlite3.connect(f"file:{HOME / 'analysis' / 'recon.sqlite'}?mode=ro", uri=True)
    q = "select kind, product_id, ts, label, direction, atr_pct, btc4h, netR21, r4, r12, r24 from recon where btc4h is not null"
    return pd.read_sql_query(q, recon)


def run() -> dict:
    cfg = panel.load_config()
    df = load()
    sig = df[df.kind == "sig"].copy()
    base = df[df.kind == "base"].copy()
    sig["hour"] = sig.ts // 3600
    # a base hour is clean for a coin if that coin had no signal in the previous CLEAN_HOURS hours
    sig_hours = {p: np.sort(g.hour.unique()) for p, g in sig.groupby("product_id")}
    base["hour"] = base.ts // 3600
    clean = np.ones(len(base), bool)
    for p, g in base.groupby("product_id"):
        sh = sig_hours.get(p)
        if sh is None:
            continue
        pos = np.searchsorted(sh, g.hour.to_numpy(), side="right") - 1
        last = np.where(pos >= 0, sh[np.clip(pos, 0, len(sh) - 1)], -10**9)
        clean[base.index.get_indexer(g.index)] = (g.hour.to_numpy() - last) > CLEAN_HOURS
    base["clean"] = clean
    out = {"n_base_hours": int(len(base)), "share_base_hours_clean": float(clean.mean()),
           "clean_rule": f"no signal on the same coin in the previous {CLEAN_HOURS} hours",
           "inputs_sha256": {"recon.sqlite": sha(HOME / "analysis" / "recon.sqlite")}, "reads": {}}
    pools = {}
    for (p, d), g in base[base.clean].groupby(["product_id", "direction"]):
        a = g.sort_values("ts")
        pools[(p, d)] = (a.ts.to_numpy(), a.atr_pct.to_numpy(), a.btc4h.map(bucket).to_numpy(),
                         a[list(OUTCOMES)].to_numpy())
    rng_seed = cfg["bootstrap"]["seed"]
    for label, direction, expected in READS:
        s = sig[(sig.label == label) & (sig.direction == direction)].copy()
        s["blk"] = s.ts // 14400
        s = s.drop_duplicates(["product_id", "blk"])  # one signal per coin per 4 hours
        rows = []
        for r in s.itertuples():
            pool = pools.get((r.product_id, direction))
            if pool is None:
                continue
            ts, atr, bk, vals = pool
            lo, hi = np.searchsorted(ts, [r.ts - 7 * 86400, r.ts + 7 * 86400])
            w = slice(lo, hi)
            m = (np.abs(ts[w] - r.ts) >= 86400) & (atr[w] >= r.atr_pct * 0.75) & (atr[w] <= r.atr_pct / 0.75) \
                & (bk[w] == bucket(r.btc4h))
            if m.sum() < 3:
                continue
            c = vals[w][m]
            rows.append((r.ts, r.product_id, *[getattr(r, k) for k in OUTCOMES], *np.nanmean(c, axis=0), int(m.sum())))
        e = {"expected_sign_of_excess_if_read_is_right": expected, "signals_deduplicated": int(len(s)),
             "matched": len(rows)}
        if rows:
            t = pd.DataFrame(rows, columns=["ts", "prod", *[f"s_{k}" for k in OUTCOMES], *[f"c_{k}" for k in OUTCOMES], "k"])
            t["week"] = ev.week_key(pd.to_datetime(t.ts, unit="s"))
            e["distinct_coins"] = int(t["prod"].nunique())
            e["distinct_weeks"] = int(t.week.nunique())
            e["largest_coin_share"] = float(t["prod"].value_counts(normalize=True).iloc[0])
            mid = t.ts.median()
            for k, desc in OUTCOMES.items():
                x = t[f"s_{k}"] - t[f"c_{k}"]
                est = ev.boot(x.groupby(t.week).mean(), cfg, 1000)
                halves = {}
                for name, mask in (("first_half", t.ts <= mid), ("second_half", t.ts > mid)):
                    h = ev.boot(x[mask].groupby(t.week[mask]).mean(), cfg, 1100)
                    halves[name] = {kk: h.get(kk) for kk in ("mean", "lo", "hi", "n_blocks")}
                e[k] = {"description": desc, "signal_mean": float(t[f"s_{k}"].mean()),
                        "control_mean": float(t[f"c_{k}"].mean()),
                        "excess": {kk: est.get(kk) for kk in ("mean", "lo", "hi", "n_blocks")}, **halves}
        out["reads"][f"{label} ({direction})"] = e
    # 15- and 60-minute graded returns: within-signal contrast only (no control at that horizon)
    path = sorted(glob.glob(str(HOME / "prod-backup" / "*" / "signal_outcomes.sqlite")))[-1]
    out["inputs_sha256"]["signal_outcomes.sqlite"] = sha(Path(path))
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    g = pd.read_sql_query(
        "select product_id, started_ts ts, direction, read_label, return_15m, return_60m, last_ts from signal_outcomes "
        "where complete=1 and direction in ('up','down')", con)
    g["ontime"] = (g.last_ts - g.ts) <= 3900
    g = g[g.ontime]
    g["week"] = ev.week_key(pd.to_datetime(g.ts, unit="s"))
    short = {}
    for label, direction, _ in READS[:2]:
        s = g[(g.read_label == label) & (g.direction == direction)]
        short[f"{label} ({direction})"] = {
            "n": int(len(s)),
            "return_15m_pct": ev.boot(s.groupby("week").return_15m.mean(), cfg, 1200),
            "return_60m_pct": ev.boot(s.groupby("week").return_60m.mean(), cfg, 1201)}
    all_up = g[g.direction == "up"]
    short["all_up_signals_for_context"] = {"n": int(len(all_up)),
                                           "return_15m_pct": ev.boot(all_up.groupby("week").return_15m.mean(), cfg, 1202),
                                           "return_60m_pct": ev.boot(all_up.groupby("week").return_60m.mean(), cfg, 1203)}
    out["short_horizon_within_signal"] = short
    out["limitations"] = [
        "Selected population: only moments when the live rules fired, about 13 weeks, many overlapping per day.",
        "Outcomes begin at the signal-time price; a delayed fill would differ.",
        "15/60-minute returns have no matched non-signal comparison here; they are a within-signal contrast.",
        "The population was inspected in earlier audits, so these results are not independent confirmation.",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "recorded_signals.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    return out


if __name__ == "__main__":
    res = run()
    for name, e in res["reads"].items():
        print(name, {k: e.get(k) for k in ("signals_deduplicated", "matched", "distinct_weeks")})
        for k in OUTCOMES:
            if k in e:
                x = e[k]["excess"]
                print(f"   {k:7} signal {e[k]['signal_mean']:+.3f} control {e[k]['control_mean']:+.3f} "
                      f"excess {x['mean']:+.3f} [{x['lo']:+.3f}, {x['hi']:+.3f}]")
