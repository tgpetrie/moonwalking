"""Purged walk-forward ridge on within-day rank-normal features, and 0-100 percentile scores.

The model is linear, so each prediction is exactly the sum of per-feature contributions
(`z_feature * coefficient`). No fit ever sees a row whose label window reaches the first
prediction day of the month being predicted (8-day purge/embargo).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from panel import FEATURES, winsor

EMBARGO = pd.Timedelta(days=8)
VALIDATION_DAYS = 180
MIN_TRAIN_ROWS = 5000


def daily_ic(pred: pd.Series, y: pd.Series, min_n: int = 20) -> pd.Series:
    """Tie-aware cross-sectional Spearman IC per date (average ranks)."""
    d = pd.DataFrame({"p": pred, "y": y}).dropna()
    if d.empty:
        return pd.Series(dtype=float)
    day = d.index.get_level_values("date")
    rp = d["p"].groupby(day).rank()
    ry = d["y"].groupby(day).rank()
    rp = rp - rp.groupby(day).transform("mean")
    ry = ry - ry.groupby(day).transform("mean")
    num = (rp * ry).groupby(day).sum()
    den = np.sqrt((rp ** 2).groupby(day).sum() * (ry ** 2).groupby(day).sum())
    ic = (num / den.where(den > 0))
    cnt = d["p"].groupby(day).size()
    return ic[cnt >= min_n].dropna()


def ridge(X: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    return np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)


def _prepare_target(df: pd.DataFrame, mask: np.ndarray, ycol: str, pct) -> np.ndarray:
    y = df[ycol].to_numpy()
    day = df.index.get_level_values("date")
    sub = pd.Series(y[mask], index=day[mask])
    sub = sub - sub.groupby(level=0).transform("mean")  # remove the market-wide component
    return winsor(sub.to_numpy(), pct[0], pct[1])


def _fit_best(df, Z, dates, cutoff, ycol, cfg, grid):
    ok = df[ycol].notna().to_numpy()
    full = (dates < cutoff) & ok
    if full.sum() < MIN_TRAIN_ROWS:
        return None
    val_start = cutoff - pd.Timedelta(days=VALIDATION_DAYS)
    sub = (dates < val_start - EMBARGO) & ok
    val = (dates >= val_start) & (dates < cutoff) & ok
    best_lam = grid[len(grid) // 2]
    if sub.sum() >= MIN_TRAIN_ROWS and val.sum() > 1000:
        y_sub = _prepare_target(df, sub, ycol, cfg["winsor_pct"])
        scores = []
        for lam in grid:
            b = ridge(Z[sub], y_sub, lam)
            ic = daily_ic(pd.Series(Z[val] @ b, index=df.index[val]), df.loc[val, ycol], cfg["min_cross_section"])
            scores.append(ic.mean() if len(ic) else -np.inf)
        best_lam = grid[int(np.nanargmax(scores))]
    y_full = _prepare_target(df, full, ycol, cfg["winsor_pct"])
    return ridge(Z[full], y_full, best_lam), best_lam, int(full.sum())


def walk_forward(df: pd.DataFrame, horizon: int, cfg: dict, start: str, end: str,
                 features: list[str] | None = None):
    """Monthly refits. Returns (prediction Series, contribution DataFrame, fit log list)."""
    features = features or FEATURES
    ycol = f"y{horizon}"
    zcols = ["z_" + f for f in features]
    Z = df[zcols].fillna(0.0).to_numpy()
    dates = df.index.get_level_values("date").to_numpy()
    dates = pd.DatetimeIndex(dates)
    pred = pd.Series(np.nan, index=df.index)
    contrib = pd.DataFrame(np.nan, index=df.index, columns=["c_" + f for f in features], dtype="float32")
    log = []
    for m in pd.date_range(start, end, freq="MS"):
        nxt = m + pd.offsets.MonthBegin(1)
        cutoff = m - EMBARGO
        fit = _fit_best(df, Z, dates, cutoff, ycol, cfg, cfg["ridge_grid"])
        if fit is None:
            continue
        beta, lam, n_train = fit
        rows = (dates >= m) & (dates < nxt)
        pred.iloc[np.flatnonzero(rows)] = Z[rows] @ beta
        contrib.iloc[np.flatnonzero(rows)] = (Z[rows] * beta).astype("float32")
        log.append({"month": str(m.date()), "lambda": lam, "train_rows": n_train,
                    "train_label_end_before": str(cutoff.date()),
                    "coef": {f: round(float(b), 6) for f, b in zip(features, beta)}})
    return pred, contrib, log


def to_score(pred: pd.Series) -> pd.Series:
    """Same-day percentile rank scaled to 1-100 (ordinal; not a probability)."""
    p = pred.dropna()
    day = p.index.get_level_values("date")
    r = p.groupby(day).rank(method="average")
    n = p.groupby(day).transform("size")
    return np.ceil(100.0 * r / n).clip(1, 100).reindex(pred.index)
