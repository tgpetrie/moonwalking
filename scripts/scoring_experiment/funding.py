"""Funding features from the stored Hyperliquid responses, aligned to the baseline's decision days.

Past-only: the value used for decision day d (decision time 00:00 UTC on d+1) comes only from prints stamped on UTC day d-offset
(offset 1 = primary, one-day lag; offset 0 = same-day sensitivity). Missing hours are never filled.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import panel

DAY_MS = 86_400_000


def load_product(folder: Path) -> tuple[pd.DataFrame, dict]:
    rows = []
    for p in sorted(folder.glob("page_*.json")):
        rows.extend(json.loads(json.loads(p.read_text(encoding="utf-8"))["response_text"]))
    stats = {"raw_rows": len(rows), "complete": (folder / "COMPLETE").exists()}
    if not rows:
        return pd.DataFrame(columns=["time", "rate", "premium"]), {**stats, "duplicates_identical": 0, "conflicting_stamps": 0}
    d = pd.DataFrame({"time": [r["time"] for r in rows], "rate": [float(r["fundingRate"]) for r in rows],
                      "premium": [float(r["premium"]) for r in rows]})
    stats["duplicates_identical"] = int(d.duplicated().sum())
    d = d.drop_duplicates()
    conflict = d["time"].duplicated(keep=False)
    stats["conflicting_stamps"] = int(d.loc[conflict, "time"].nunique())
    d["conflict"] = conflict
    return d.sort_values("time").reset_index(drop=True), stats


def daily_series(d: pd.DataFrame, min_prints: int) -> tuple[pd.Series, pd.Series]:
    """Daily mean hourly rate (NaN unless >= min_prints and no conflicting stamp) and daily print counts."""
    if d.empty:
        return pd.Series(dtype=float), pd.Series(dtype=int)
    day = pd.to_datetime(d["time"] // DAY_MS * DAY_MS, unit="ms")
    cnt = d.groupby(day)["rate"].size()
    mean = d.groupby(day)["rate"].mean()
    bad = d.groupby(day)["conflict"].any()
    mean = mean.where((cnt >= min_prints) & (~bad))
    full = pd.date_range(mean.index.min(), mean.index.max(), freq="D")
    return mean.reindex(full), cnt.reindex(full).fillna(0).astype(int)


def rolling_z(mean: pd.Series, window: int, min_valid: int) -> pd.Series:
    mu = mean.rolling(window, min_periods=min_valid).mean()
    sd = mean.rolling(window, min_periods=min_valid).std()
    return ((mean - mu) / sd.where(sd > 0))


def decision_series(daily_level: pd.Series, z: pd.Series, offset: int) -> pd.DataFrame:
    """Shift to decision dates: decision day d uses funding day d - offset."""
    return pd.DataFrame({"fl_raw": daily_level.shift(offset, freq="D"), "fz_raw": z.shift(offset, freq="D")})


def build_matched(base: pd.DataFrame, amap: dict, root: Path, fcfg: dict, offset: int, tag: str = "") -> tuple[pd.DataFrame, dict]:
    """Rows of `base` for approved products with a valid funding feature, plus rank-normal funding inputs."""
    pieces, per_product = [], {}
    prods = base.index.get_level_values("product")
    for pid in sorted(amap):
        folder = root / "raw" / pid
        d, st = load_product(folder) if folder.exists() else (pd.DataFrame(), {"raw_rows": 0})
        mean, cnt = daily_series(d, fcfg["min_prints_per_day"])
        info = {**st, "first_utc": None if d.empty else str(pd.to_datetime(d.time.min(), unit="ms")),
                "last_utc": None if d.empty else str(pd.to_datetime(d.time.max(), unit="ms")),
                "days_with_valid_mean": int(mean.notna().sum()) if len(mean) else 0,
                "days_below_print_minimum": int(((cnt > 0) & (cnt < fcfg["min_prints_per_day"])).sum()) if len(cnt) else 0}
        if not len(mean):
            per_product[pid] = {**info, "matched_rows": 0}
            continue
        z = rolling_z(mean, fcfg["z_window_days"], fcfg["z_min_valid_days"])
        dec = decision_series(mean, z, offset)
        sub = base[prods == pid]
        dates = sub.index.get_level_values("date")
        vals = dec.reindex(dates)
        sub = sub.assign(fl_raw=vals["fl_raw"].to_numpy(), fz_raw=vals["fz_raw"].to_numpy())
        sub = sub[sub["fz_raw"].notna()]
        info["eligible_baseline_rows"] = int((prods == pid).sum())
        info["matched_rows"] = int(len(sub))
        per_product[pid] = info
        if len(sub):
            pieces.append(sub)
    dm = pd.concat(pieces) if pieces else base.iloc[:0].copy()
    dm = dm.sort_index()
    day = dm.index.get_level_values("date")
    dm["n_matched_day"] = dm.groupby(level="date")["r1"].transform("size")
    for src, dst in (("fz_raw", "z_fz" + tag), ("fl_raw", "z_fl" + tag)):
        g = dm[src].groupby(day)
        n = g.transform("count")
        r = g.rank(method="average")
        ok = dm[src].notna() & (n > 1)
        out = pd.Series(np.nan, index=dm.index)
        out[ok] = panel.norm_ppf(((r[ok] - 0.5) / n[ok]).to_numpy())
        dm[dst] = out
    return dm, per_product
