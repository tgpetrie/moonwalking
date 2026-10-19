"""Study 3a: perp funding at the moment of a +10% day vs the post-spike give-back.

Design is preregistered in docs/developer/FUNDING_STUDY.md (committed before
funding was joined to outcomes). Funding comes from fetch_funding.py.

  python scripts/move_study/funding_study.py --daily-dir <daily_all> --funding <funding dir> --out data/move-study
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import continuation_vs_reversal as cs  # noqa: E402
import level_study as ls  # noqa: E402

DAY = cs.DAY
MS = 1000
NEG, CROWD = 0.0, 0.0002          # 8h-equivalent thresholds (0.02%)
TAIL = 0.0005
SEED = 20261022


def multiplier(symbol: str) -> float:
    if symbol.startswith("1000000"):
        return 1e6
    if symbol.startswith("1000") or symbol.startswith("k"):
        return 1e3
    return 1.0


def read_csv_any(path: Path, names: list[str]) -> pd.DataFrame:
    text = path.read_text(encoding="utf-8", errors="replace")
    first = text.splitlines()[0] if text else ""
    header = 0 if any(c.isalpha() for c in first.split(",")[0]) else None
    df = pd.read_csv(io.StringIO(text), header=header)
    if header is None:
        df.columns = names[: df.shape[1]] + [f"x{i}" for i in range(df.shape[1] - len(names))]
    return df


def verify_binance(funding: Path, sym: str, base: str, close: pd.DataFrame) -> dict:
    p = funding / "binance" / f"klines-{sym}.csv"
    if not p.exists():
        return {"verified": False, "reason": "no klines month"}
    k = read_csv_any(p, ["open_time", "open", "high", "low", "close", "volume"])
    k["day"] = (pd.to_numeric(k["open_time"]) // (DAY * MS)).astype(int)
    cb = close.get(f"{base}-USD")
    if cb is None:
        return {"verified": False, "reason": "no coinbase series"}
    j = k.set_index("day")["close"].astype(float).to_frame("b").join(cb.rename("c"), how="inner").dropna()
    if len(j) < 10:
        return {"verified": False, "reason": f"only {len(j)} overlapping days"}
    err = float(np.median(np.abs(j.b / multiplier(sym) / j.c - 1)))
    return {"verified": err < 0.05, "median_abs_err": round(err, 4), "days": int(len(j))}


def verify_hl(funding: Path, coin: str, base: str, close: pd.DataFrame) -> dict:
    p = funding / "hl" / f"candles-{coin}.json"
    if not p.exists():
        return {"verified": False, "reason": "no candles"}
    data = json.loads(p.read_text())
    if not isinstance(data, list) or not data:
        return {"verified": False, "reason": "empty candles"}
    hl = pd.Series({int(x["t"]) // (DAY * MS): float(x["c"]) for x in data})
    cb = close.get(f"{base}-USD")
    if cb is None:
        return {"verified": False, "reason": "no coinbase series"}
    j = pd.concat([hl.rename("h"), cb.rename("c")], axis=1, join="inner").dropna()
    if len(j) < 10:
        return {"verified": False, "reason": f"only {len(j)} overlapping days"}
    err = float(np.median(np.abs(j.h / multiplier(coin) / j.c - 1)))
    return {"verified": err < 0.05, "median_abs_err": round(err, 4), "days": int(len(j))}


def binance_day_funding(funding: Path, sym: str, day: int, cache: dict) -> float:
    mo = pd.Timestamp(day * DAY, unit="s").strftime("%Y-%m")
    key = (sym, mo)
    if key not in cache:
        p = funding / "binance" / f"{sym}-{mo}.csv"
        if p.exists():
            f = read_csv_any(p, ["calc_time", "funding_interval_hours", "last_funding_rate"])
            f["t"] = pd.to_numeric(f["calc_time"]) // MS
            f["eq8"] = pd.to_numeric(f["last_funding_rate"]) * 8.0 / pd.to_numeric(f["funding_interval_hours"]).replace(0, np.nan)
            cache[key] = f[["t", "eq8"]].dropna()
        else:
            cache[key] = None
    f = cache[key]
    if f is None:
        return np.nan
    sel = f[(f.t > day * DAY) & (f.t <= (day + 1) * DAY)]
    return float(sel.eq8.mean()) if len(sel) else np.nan


def hl_day_funding(funding: Path, coin: str, day: int) -> float:
    p = funding / "hl" / f"{coin}-{day}.json"
    if not p.exists():
        return np.nan
    data = json.loads(p.read_text())
    if not isinstance(data, list):
        return np.nan
    rates = [float(x["fundingRate"]) * 8.0 for x in data
             if day * DAY * MS < int(x["time"]) <= (day + 1) * DAY * MS]
    return float(np.mean(rates)) if rates else np.nan


def regime(f: float) -> str | None:
    if not np.isfinite(f):
        return None
    return "negative" if f < NEG else "crowded" if f > CROWD else "neutral"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daily-dir", required=True)
    ap.add_argument("--funding", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    funding = Path(args.funding)
    rng = np.random.default_rng(SEED)

    d = cs.load_daily_dir(Path(args.daily_dir), "2022-01-03", "2026-10-17")
    frames: dict = {}
    ev, days, _ = cs.build_panel(d, frames)
    close = frames["close"]
    plan = json.loads((funding / "plan.json").read_text())
    bmap, hmap = plan["bmap"], plan["hmap"]

    checks = {"binance": {b: verify_binance(funding, s, b, close) for b, s in bmap.items()},
              "hyperliquid": {b: verify_hl(funding, s, b, close) for b, s in hmap.items()}}

    ev["base"] = ev["product"].str.replace("-USD", "", regex=False)
    cache: dict = {}
    b_val, h_val, status = [], [], []
    for b, dy in zip(ev.base, ev.day):
        bv = binance_day_funding(funding, bmap[b], int(dy), cache) if b in bmap and checks["binance"][b]["verified"] else np.nan
        hv = hl_day_funding(funding, hmap[b], int(dy)) if b in hmap and checks["hyperliquid"][b]["verified"] else np.nan
        unverified = (b in bmap and not checks["binance"][b]["verified"]) or (b in hmap and not checks["hyperliquid"][b]["verified"])
        b_val.append(bv); h_val.append(hv)
        status.append("perp" if np.isfinite(bv) or np.isfinite(hv) else ("unverified" if unverified else "spot_only"))
    ev["funding_binance"], ev["funding_hl"], ev["perp_status"] = b_val, h_val, status
    ev["funding"] = np.where(np.isfinite(ev.funding_binance), ev.funding_binance, ev.funding_hl)
    ev["funding_source"] = np.where(np.isfinite(ev.funding_binance), "binance", np.where(np.isfinite(ev.funding_hl), "hyperliquid", None))
    ev["regime"] = [regime(f) for f in ev.funding]
    ev["shock"] = (ev.vol_ratio >= 5) & ((ev.ret1 - ev.btc_ret) >= 0.15)
    ev["thin"] = ev.med20_usd < 1e6
    # Binance monthly archives for the current month are not published yet; keep October 2026 out of F2.
    f2_cut = ls.day_of("2026-10-01")

    split = ls.day_of(ls.SPLIT)
    periods = {"discovery": (int(days[0]), split - 1), "test": (split, int(days[-1]))}
    up = ev[ev.direction == "up"]
    pops = {"A_all": up, "B_shock": up[up.shock]}
    tests = []
    for pname, pop in pops.items():
        for k in (1, 3, 7):
            tests.append({"name": "F1_negative_minus_crowded", "population": pname, "horizon": k,
                          **{pn: ls.diff_boot(pop[pop.regime == "negative"], pop[pop.regime == "crowded"], f"m{k}", per, k, rng)
                             for pn, per in periods.items()}})
        f2 = pop[pop.day < f2_cut]
        for tier, mask in (("<$1M", f2.thin), (">=$1M", ~f2.thin)):
            g = f2[mask]
            tests.append({"name": "F2_perp_minus_spot_only", "population": pname, "tier": tier, "horizon": 7,
                          **{pn: ls.diff_boot(g[g.perp_status == "perp"], g[g.perp_status == "spot_only"], "m7", per, 7, rng)
                             for pn, per in periods.items()}})
    n, surv = len(tests), 0
    for t in tests:
        dsc = t["discovery"]
        if "p_raw" in dsc:
            dsc["p_bonferroni"] = round(min(1.0, dsc["p_raw"] * n), 4)
            surv += dsc["p_bonferroni"] < 0.05
    for t in tests:
        dsc, tst = t["discovery"], t["test"]
        if "p_raw" in tst:
            tst["p_bonferroni"] = round(min(1.0, tst["p_raw"] * max(1, surv)), 4)
        t["replicates"] = bool("p_bonferroni" in dsc and "p_bonferroni" in tst and dsc["p_bonferroni"] < 0.05
                               and tst["p_bonferroni"] < 0.05 and np.sign(dsc["diff_pct"]) == np.sign(tst["diff_pct"]))

    # secondary
    sec = {}
    ev["year"] = pd.to_datetime(ev.day * DAY, unit="s").dt.year
    sec["coverage"] = {str(y): {s: int((g.perp_status == s).sum()) for s in ("perp", "spot_only", "unverified")}
                       for y, g in ev[ev.direction == "up"].groupby("year")}
    sec["identity_checks"] = {v: {"verified": sum(1 for x in c.values() if x["verified"]), "failed": sum(1 for x in c.values() if not x["verified"])}
                              for v, c in checks.items()}
    sec["identity_failures"] = {v: {b: x for b, x in c.items() if not x["verified"]} for v, c in checks.items()}
    for pname, pop in pops.items():
        f = pop[np.isfinite(pop.funding)]
        sec[f"{pname} spearman funding vs m7"] = {pn: round(float(f[(f.day >= a) & (f.day + 7 <= b)][["funding", "m7"]].corr(method="spearman").iloc[0, 1]), 4)
                                                 for pn, (a, b) in periods.items()}
        sec[f"{pname} regimes"] = {r: {"n": int(len(g)), **ls.describe(g, "m7")} for r, g in f.groupby("regime")}
        sec[f"{pname} tails"] = {"<= -0.05%": ls.describe(f[f.funding <= -TAIL], "m7"), ">= +0.05%": ls.describe(f[f.funding >= TAIL], "m7")}
    down = ev[(ev.direction == "down") & np.isfinite(ev.funding)]
    sec["down days by regime"] = {r: {"n": int(len(g)), **ls.describe(g, "m7")} for r, g in down.groupby("regime")}
    sec["down days negative minus crowded 7d"] = {pn: ls.diff_boot(down[down.regime == "negative"], down[down.regime == "crowded"], "m7", per, 7, rng)
                                                  for pn, per in periods.items()}
    both = ev[np.isfinite(ev.funding_binance) & np.isfinite(ev.funding_hl)]
    sec["binance_vs_hl"] = {"n": int(len(both)), "pearson": round(float(both[["funding_binance", "funding_hl"]].corr().iloc[0, 1]), 3) if len(both) > 5 else None,
                            "same_regime_share": round(float(np.mean([regime(a) == regime(b) for a, b in zip(both.funding_binance, both.funding_hl)])), 3) if len(both) else None}

    out = {"design": "docs/developer/FUNDING_STUDY.md (preregistered)", "events": int(len(ev)), "tests": n,
           "discovery_survivors": int(surv), "primary": tests, "secondary": sec,
           "notes": ["F2 excludes events from 2026-10-01 (current-month Binance archive not yet published)."]}
    (Path(args.out) / "funding_study.json").write_text(json.dumps(out, indent=1, default=float) + "\n", encoding="utf-8", newline=cs.LF)
    print({k: out[k] for k in ("events", "tests", "discovery_survivors")})
    for t in tests:
        a, b = t["discovery"], t["test"]
        print(t["name"], t["population"], t.get("tier", ""), t["horizon"], "| disc", a.get("n_real"), a.get("n_placebo"), a.get("real_mean_pct"), a.get("placebo_mean_pct"),
              a.get("diff_pct"), a.get("ci95_pct"), a.get("p_bonferroni"), "| test", b.get("n_real"), b.get("n_placebo"), b.get("diff_pct"), b.get("ci95_pct"), b.get("p_bonferroni"),
              "REPL" if t["replicates"] else "")
    print(json.dumps({k: sec[k] for k in ("coverage", "identity_checks", "binance_vs_hl")}, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
