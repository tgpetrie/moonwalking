"""DeFiLlama series parsing and the frozen fundamentals features (FUNDAMENTALS_EXPERIMENT_PROTOCOL.md, section 4).

Past-only: the value for decision day d uses series dates up to L = d - lag. Dates absent from a response are missing and never filled;
explicit zeros stay zeros. Nothing here reads returns or labels.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

WINDOW = 30
MIN_PRESENT = 25
PIN_SHARE = 0.5


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_series(path: Path) -> tuple[pd.Series, dict]:
    """Daily values from any of the three DeFiLlama shapes: fees summary (`totalDataChart` [[ts, v]]),
    protocol (`tvl` [{date, totalLiquidityUSD}]) or chain TVL ([{date, tvl}]). Duplicate dates keep the last returned value."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, dict) and "totalDataChart" in doc:
        pairs = [(int(t), v) for t, v in doc["totalDataChart"]]
    elif isinstance(doc, dict) and "tvl" in doc:
        pairs = [(int(r["date"]), r.get("totalLiquidityUSD")) for r in doc["tvl"]]
    elif isinstance(doc, list):
        pairs = [(int(r["date"]), r.get("tvl")) for r in doc]
    else:
        raise ValueError(f"unrecognised DeFiLlama shape: {path.name}")
    dates = pd.to_datetime([t // 86400 * 86400 for t, _ in pairs], unit="s")
    vals = pd.to_numeric(pd.Series([v for _, v in pairs], index=dates, dtype="object"), errors="coerce")
    dup = int(vals.index.duplicated(keep="last").sum())
    vals = vals[~vals.index.duplicated(keep="last")].sort_index()
    info = {"returned_dates": int(len(vals)), "duplicate_dates": dup, "non_numeric": int(vals.isna().sum()),
            "zeros": int((vals == 0).sum()),
            "first": str(vals.index.min().date()) if len(vals) else None, "last": str(vals.index.max().date()) if len(vals) else None}
    if len(vals):
        full = pd.date_range(vals.index.min(), vals.index.max(), freq="D")
        info["missing_inside_span"] = int(len(full) - len(vals))
        vals = vals.reindex(full)
    return vals.astype(float), info


def _pinned(values: pd.Series) -> pd.Series:
    """True where more than half of the present values in the 60-day window ending at the date are identical."""
    arr = values.to_numpy()
    out = np.zeros(len(arr), bool)
    for i in range(len(arr)):
        w = arr[max(0, i - 2 * WINDOW + 1): i + 1]
        w = w[np.isfinite(w)]
        if len(w):
            _, counts = np.unique(w, return_counts=True)
            out[i] = counts.max() > PIN_SHARE * len(w)
    return pd.Series(out, index=values.index)


def trend(values: pd.Series) -> tuple[pd.Series, dict]:
    """log(mean of L-29..L) - log(mean of L-59..L-30); >= 25 present days per half, positive means, not pinned."""
    if values.empty:
        return pd.Series(dtype=float), {}
    recent = values.rolling(WINDOW, min_periods=MIN_PRESENT).mean()
    prior = recent.shift(WINDOW)
    ok_counts = recent.notna() & prior.notna()
    positive = (recent > 0) & (prior > 0)
    pinned = _pinned(values)
    out = (np.log(recent.where(positive)) - np.log(prior.where(positive))).where(ok_counts & positive & ~pinned)
    reasons = {"dates_defined": int(out.notna().sum()), "too_few_present_days": int((~ok_counts).sum()),
               "non_positive_mean": int((ok_counts & ~positive).sum()), "pinned_window": int((ok_counts & positive & pinned).sum())}
    return out, reasons


def level_change(values: pd.Series, days: int = WINDOW) -> pd.Series:
    """log(v_L / v_{L-days}) on exact dates, both positive; no filling."""
    if values.empty:
        return pd.Series(dtype=float)
    prev = values.shift(days)
    ok = (values > 0) & (prev > 0)
    return np.log(values.where(ok) / prev.where(ok)).where(~_pinned(values))


def to_decision_dates(series: pd.Series, lag_days: int) -> pd.Series:
    """Value computed on series date L applies to decision day L + lag."""
    return series.shift(lag_days, freq="D") if len(series) else series
