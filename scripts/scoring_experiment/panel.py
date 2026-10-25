"""Load the frozen daily panel and build past-only features and next-period labels.

Every feature at row (date d, product p) uses candles dated d or earlier. Labels use
the open of d+1 (entry) and the open of d+1+h (exit); they are never used as features.
Missing days are never filled: a return that needs a missing candle is NaN.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scoring_data"))
import freeze_daily_panel as codex_panel  # noqa: E402  (read-only reuse of Codex's parser)

FEATURES = ["r1", "r7", "r30", "vol30", "relvol", "beta90", "res7", "ext30", "pos30", "streak", "thin"]
CORE = ["r1", "r7", "vol30", "beta90", "relvol"]
BENCHMARK = "BTC-USD"
FACTOR_GROUPS = {
    "momentum": ["r1", "r7", "r30", "res7", "streak"],
    "extension": ["ext30", "pos30"],
    "volume_liquidity": ["relvol", "thin"],
    "volatility_beta": ["vol30", "beta90"],
}


def load_config(path: Path | None = None) -> dict:
    path = path or HERE / "config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]


def expand(path: str) -> Path:
    return Path(path.replace("~", str(Path.home()), 1)) if path.startswith("~") else Path(path)


def load_raw_frames(root: Path, verify: bool = True) -> tuple[dict, dict]:
    """Return ({'open','high','low','close','volume'} wide frames, provenance)."""
    provenance = {"root": str(root)}
    if verify:
        provenance["verification"] = codex_panel.verify(root)
        provenance["manifest_sha256"] = codex_panel.digest(root / "MANIFEST.json")
    products, summaries = codex_panel.inspect_panel(root / "raw")
    first = min(t for rows in products.values() for t in rows)
    last = max(t for rows in products.values() for t in rows)
    index = pd.date_range(pd.Timestamp(first, unit="s"), pd.Timestamp(last, unit="s"), freq="D")
    cols = sorted(products)
    shape = (len(index), len(cols))
    arrays = {k: np.full(shape, np.nan) for k in ("open", "high", "low", "close", "volume")}
    day0 = first
    for j, pid in enumerate(cols):
        for t, (_, low, high, op, close, vol) in products[pid].items():
            i = (t - day0) // codex_panel.DAY
            arrays["open"][i, j], arrays["high"][i, j] = op, high
            arrays["low"][i, j], arrays["close"][i, j], arrays["volume"][i, j] = low, close, vol
    frames = {k: pd.DataFrame(v, index=index, columns=cols) for k, v in arrays.items()}
    provenance.update(products=len(cols), first_date=str(index[0].date()), last_date=str(index[-1].date()),
                      usable_candles=int(np.isfinite(arrays["close"]).sum()))
    return frames, provenance


def _streak(ret1: pd.DataFrame, cap: int = 7) -> pd.DataFrame:
    sign = np.sign(ret1.to_numpy())
    out = np.full(sign.shape, np.nan)
    prev = np.full(sign.shape[1], np.nan)
    for i in range(sign.shape[0]):
        cur = sign[i]
        same = np.isfinite(prev) & np.isfinite(cur) & (cur != 0) & (np.sign(prev) == cur)
        val = np.where(same, prev + cur, cur)
        val = np.where(np.isfinite(cur), np.clip(val, -cap, cap), np.nan)
        out[i] = val
        prev = val
    return pd.DataFrame(out, index=ret1.index, columns=ret1.columns)


def build_features(frames: dict, cfg: dict) -> dict:
    """Past-only feature matrices (wide) plus label matrices (wide) and an eligibility mask."""
    op, hi, lo, cl, vo = (frames[k] for k in ("open", "high", "low", "close", "volume"))
    vw, bw, rw = cfg["vol_window"], cfg["beta_window"], cfg["relvol_window"]
    logc = np.log(cl)
    ret1 = logc.diff()
    vol30 = ret1.rolling(vw, min_periods=int(vw * 2 / 3)).std()
    btc1 = ret1[BENCHMARK]
    minp = int(bw * 2 / 3)
    cov = ret1.rolling(bw, min_periods=minp).cov(btc1)
    beta90 = cov.div(btc1.rolling(bw, min_periods=minp).var(), axis=0)

    def lr(k):
        return logc - logc.shift(k)

    r1raw, r7raw, r30raw = lr(1), lr(7), lr(30)
    btc7 = r7raw[BENCHMARK]
    res7 = (r7raw.sub(beta90.mul(btc7, axis=0))) / vol30
    dv = (vo * cl).where(vo * cl > 0)
    med20 = dv.shift(1).rolling(rw, min_periods=15).median()
    relvol = np.log(dv / med20)
    ma30 = cl.rolling(vw, min_periods=20).mean()
    hi30, lo30 = hi.rolling(vw, min_periods=20).max(), lo.rolling(vw, min_periods=20).min()
    feat = {
        "r1": r1raw / vol30, "r7": r7raw / vol30, "r30": r30raw / vol30, "vol30": vol30,
        "relvol": relvol, "beta90": beta90, "res7": res7, "ext30": np.log(cl / ma30) / vol30,
        "pos30": (cl - lo30) / (hi30 - lo30).where(hi30 > lo30), "streak": _streak(ret1),
        "thin": (med20 < cfg["thin_dollar_volume_usd"]).astype(float).where(med20.notna()),
    }
    # eligibility: history, window completeness, decision-day candle, core features, not pegged
    have = cl.notna()
    first_date = have.idxmax().where(have.any())
    age = pd.DataFrame({c: (cl.index - first_date[c]).days for c in cl.columns}, index=cl.index)
    window_days = have.rolling(cfg["min_history_days"], min_periods=1).sum()
    core_ok = feat[CORE[0]].notna()
    for k in CORE[1:]:
        core_ok &= feat[k].notna()
    floor = vol30 >= cfg.get("min_vol30", 0.003)
    elig = (have & (age >= cfg["min_history_days"]) & (window_days >= cfg["min_usable_days_in_window"])
            & core_ok & floor)
    elig[BENCHMARK] = False
    reasons = {
        "decision_day_candle_missing": int((~have).sum().sum()),
        "history_under_min": int((have & (age < cfg["min_history_days"])).sum().sum()),
        "window_gaps_over_limit": int((have & (age >= cfg["min_history_days"])
                                       & (window_days < cfg["min_usable_days_in_window"])).sum().sum()),
        "core_feature_missing": int((have & ~core_ok).sum().sum()),
        "pegged_or_near_zero_volatility": int((have & core_ok & ~floor).sum().sum()),
        "benchmark_row_BTC-USD": int(have[BENCHMARK].sum()),
        "eligible_coin_days": int(elig.sum().sum()),
    }
    coverage = (0.6 * (window_days / cfg["min_history_days"]).clip(upper=1.0)
                + 0.4 * sum(feat[k].notna().astype(float) for k in FEATURES) / len(FEATURES)) * 100
    # labels
    labels = {}
    o1 = op.shift(-1)
    for h in cfg["horizons_days"]:
        oh = op.shift(-(1 + h))
        coin = np.log(oh / o1)
        btc = coin[BENCHMARK]
        yraw = coin.sub(beta90.mul(btc, axis=0))
        labels[f"yraw{h}"] = yraw
        labels[f"y{h}"] = yraw / vol30
        labels[f"rawret{h}"] = oh / o1 - 1.0
    btc30 = lr(30)[BENCHMARK]
    return {"features": feat, "labels": labels, "eligible": elig, "coverage": coverage,
            "exclusions": reasons, "btc7": btc7, "btc30": btc30, "close": cl}


def winsor(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    a, b = np.nanpercentile(x, [lo, hi])
    return np.clip(x, a, b)


_A = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
      1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
_B = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
      6.680131188771972e+01, -1.328068155288572e+01]
_C = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
      -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
_D = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]


def norm_ppf(p: np.ndarray) -> np.ndarray:
    """Acklam's inverse normal CDF (relative error about 1e-9); vectorised, no scipy."""
    p = np.asarray(p, float)
    out = np.empty_like(p)
    lo, hi = 0.02425, 1 - 0.02425
    m = p < lo
    q = np.sqrt(-2 * np.log(p[m]))
    out[m] = (((((_C[0]*q+_C[1])*q+_C[2])*q+_C[3])*q+_C[4])*q+_C[5]) / ((((_D[0]*q+_D[1])*q+_D[2])*q+_D[3])*q+1)
    m = p > hi
    q = np.sqrt(-2 * np.log(1 - p[m]))
    out[m] = -(((((_C[0]*q+_C[1])*q+_C[2])*q+_C[3])*q+_C[4])*q+_C[5]) / ((((_D[0]*q+_D[1])*q+_D[2])*q+_D[3])*q+1)
    m = (p >= lo) & (p <= hi)
    q = p[m] - 0.5
    r = q * q
    out[m] = (((((_A[0]*r+_A[1])*r+_A[2])*r+_A[3])*r+_A[4])*r+_A[5])*q / (((((_B[0]*r+_B[1])*r+_B[2])*r+_B[3])*r+_B[4])*r+1)
    return out


def stack_long(built: dict, cfg: dict) -> pd.DataFrame:
    """One row per eligible (date, product): raw features, within-day rank-normal features, labels."""
    elig = built["eligible"]
    mask = elig.stack()
    idx = mask[mask].index
    raw = pd.DataFrame({k: built["features"][k].stack().reindex(idx) for k in FEATURES})
    raw.index.names = ["date", "product"]
    df = raw.copy()
    day = df.index.get_level_values("date")
    for k in FEATURES:
        g = raw[k].groupby(day)
        n = g.transform("count")
        r = g.rank(method="average")
        z = pd.Series(np.nan, index=df.index)
        ok = raw[k].notna() & (n > 1)
        z[ok] = norm_ppf(((r[ok] - 0.5) / n[ok]).to_numpy())
        df["z_" + k] = z
    for k, v in built["labels"].items():
        df[k] = v.stack().reindex(idx)
    df["coverage"] = built["coverage"].stack().reindex(idx)
    df["btc7"] = built["btc7"].reindex(day).to_numpy()
    df["btc30"] = built["btc30"].reindex(day).to_numpy()
    df["n_day"] = df.groupby(level="date")["r1"].transform("size")
    return df
