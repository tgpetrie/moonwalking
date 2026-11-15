"""Elliott wave structure engine: pure, deterministic and non-repainting.

Reads swing structure from OHLCV candles and names the wave count that the
most recent confirmed swings fit, if any:

* ABC corrections, complete (``P0 -> A -> B -> C``) or with wave C still
  running (``P0 -> A -> B`` then a projected C zone). Bullish means a pullback
  inside an advance, bearish a relief bounce inside a decline.
* Five-wave impulses under the three hard rules: wave 2 never retraces more
  than 100% of wave 1, wave 3 is never the shortest of waves 1, 3 and 5, and
  wave 4 never enters wave 1's price territory.

Causality. Swings come from an ATR-adaptive ZigZag that looks only backward. A
swing extreme becomes a pivot when a later bar *closes* ``atr_mult * ATR(14)``
away from it (or closes through the previous opposite pivot). Each pivot
records the bar that confirmed it; ``confirmed_at_ts`` is that bar's close
time, the first moment the pivot is knowable. A confirmed pivot never moves,
and ``analyze_wave_structure(candles[: k + 1])`` reports exactly the pivots of
the full run that were confirmed by bar ``k``.

These reads are descriptive. They are not outcome-validated and carry no
advice. No network I/O happens here.

Candle shape (Coinbase Exchange): ``[time, low, high, open, close, volume]``,
``time`` being the candle open in unix seconds. Any order; sorted ascending here.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import median
from typing import Any, TypedDict

__all__ = [
    "SwingPivot",
    "WaveReadResult",
    "analyze_wave_structure",
    "detect_pivots",
    "resample_candles",
]

ATR_PERIOD = 14
MIN_CANDLES = 60
DEFAULT_ATR_MULT = 2.2

# ABC grammar. B must retrace part of A without exceeding its start; C must end
# beyond A, between 0.618 and 1.618 of A measured from B.
B_RETRACE_MIN = 0.236
C_PROJECTION_MIN = 0.618
C_PROJECTION_MAX = 1.618
C_LEVELS = (0.618, 1.0, 1.272, 1.618)

# Confluence weights. They sum to 1.0; an opposing higher-timeframe trend
# subtracts its weight, so a falling-knife read cannot reach the threshold.
WEIGHTS = {
    "higher_tf_trend": 0.30,
    "rsi_divergence": 0.20,
    "macd_divergence": 0.15,
    "volume_contraction": 0.15,
    "bollinger_reclaim": 0.10,
    "ema_reclaim": 0.05,
    "prior_impulse": 0.05,
}
CONFLUENCE_THRESHOLD = 0.50
RSI_PERIOD = 14
RSI_DIVERGENCE_MIN = 1.0
VOLUME_CONTRACTION_MAX = 0.85
FAST_EMA = 9
BOLLINGER_PERIOD = 20
MACD_MIN_BARS = 35
HTF_EMA = 20
HTF_SLOPE_BARS = 5
MAX_PIVOTS_OUT = 30

Row = tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class SwingPivot:
    """One confirmed swing extreme.

    ``index`` and ``ts`` locate the extreme bar. ``confirmed_at_index`` is the
    bar whose close confirmed it and ``confirmed_at_ts`` that bar's close time.
    """

    index: int
    ts: float
    price: float
    kind: str  # "high" | "low"
    confirmed_at_index: int
    confirmed_at_ts: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WaveReadResult(TypedDict, total=False):
    available: bool
    reason: str
    active_pattern: str
    status: str
    bias: str
    pivots: list[dict[str, Any]]
    wave_points: list[dict[str, Any]]
    projected_c_zone: dict[str, Any] | None
    invalidation_price: float | None
    target_price: float | None
    fib_ratios: dict[str, float]
    confluence_factors: list[dict[str, Any]]
    confluence_score: float
    confluence_confirmed: bool
    confidence: float
    confidence_label: str
    summary: str
    atr_mult: float
    bar_seconds: float | None
    candle_count: int
    as_of_ts: float | None
    outcome_validated: bool


# ─── candles ──────────────────────────────────────────────────────────────────


def _rows(candles: list[list[Any]] | None) -> list[Row]:
    """Parse, validate, de-duplicate and sort candles ascending by open time."""
    by_ts: dict[float, Row] = {}
    for candle in candles or []:
        if not candle or len(candle) < 6:
            continue
        try:
            ts, low, high, open_, close, volume = (float(candle[i]) for i in range(6))
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in (ts, low, high, open_, close, volume)):
            continue
        if low <= 0 or volume < 0 or not low <= min(open_, close):
            continue
        if not max(open_, close) <= high:
            continue
        by_ts[ts] = (ts, low, high, open_, close, volume)
    return [by_ts[ts] for ts in sorted(by_ts)]


def _bar_seconds(rows: list[Row]) -> float | None:
    gaps = [b[0] - a[0] for a, b in zip(rows, rows[1:]) if b[0] > a[0]]
    return float(median(gaps)) if gaps else None


def resample_candles(
    candles: list[list[Any]] | None, bucket_seconds: int
) -> list[list[float]]:
    """Aggregate candles into wall-clock buckets, keeping only closed buckets.

    A bucket is kept when its end is at or before the close of the last input
    bar, so the result never contains a bar that is still forming.
    """
    rows = _rows(candles)
    step = _bar_seconds(rows)
    if not rows or not step or bucket_seconds <= 0:
        return []
    closed_until = rows[-1][0] + step
    out: list[list[float]] = []
    for ts, low, high, open_, close, volume in rows:
        start = math.floor(ts / bucket_seconds) * bucket_seconds
        if out and out[-1][0] == start:
            bar = out[-1]
            bar[1], bar[2] = min(bar[1], low), max(bar[2], high)
            bar[4], bar[5] = close, bar[5] + volume
        else:
            out.append([float(start), low, high, open_, close, volume])
    while out and out[-1][0] + bucket_seconds > closed_until:
        out.pop()
    return out


# ─── causal ATR and ZigZag ────────────────────────────────────────────────────


def _atr_series(rows: list[Row], period: int = ATR_PERIOD) -> list[float]:
    """Wilder ATR. Entry ``i`` uses bars ``0..i`` only."""
    out: list[float] = []
    seed: list[float] = []
    prev_close: float | None = None
    for i, (_ts, low, high, _open, close, _vol) in enumerate(rows):
        tr = high - low
        if prev_close is not None:
            tr = max(tr, abs(high - prev_close), abs(low - prev_close))
        if i < period:
            seed.append(tr)
            out.append(sum(seed) / len(seed))
        else:
            out.append((out[-1] * (period - 1) + tr) / period)
        prev_close = close
    return out


def _extreme(rows: list[Row], lo: int, hi: int, col: int, pick_max: bool) -> int | None:
    """Index of the first max (or min) of ``col`` over bars ``lo..hi`` inclusive."""
    best: int | None = None
    for i in range(lo, hi + 1):
        if best is None:
            best = i
        elif pick_max and rows[i][col] > rows[best][col]:
            best = i
        elif not pick_max and rows[i][col] < rows[best][col]:
            best = i
    return best


def _zigzag(rows: list[Row], atr_mult: float, bar_s: float) -> list[SwingPivot]:
    """Confirmed pivots, in order. One pass, no lookahead, one pivot per bar."""
    atr = _atr_series(rows)
    pivots: list[SwingPivot] = []
    direction = 0  # +1 while tracking a high candidate, -1 a low candidate
    hi_i: int | None = None
    lo_i: int | None = None

    def confirm(extreme: int, kind: str, at: int) -> None:
        price = rows[extreme][2] if kind == "high" else rows[extreme][1]
        pivots.append(
            SwingPivot(extreme, rows[extreme][0], price, kind, at, rows[at][0] + bar_s)
        )

    for i in range(ATR_PERIOD, len(rows)):
        _ts, low, high, _open, close, _vol = rows[i]
        threshold = atr_mult * atr[i]
        if threshold <= 0:
            continue
        if direction >= 0 and (hi_i is None or high > rows[hi_i][2]):
            hi_i = i
        if direction <= 0 and (lo_i is None or low < rows[lo_i][1]):
            lo_i = i
        fell = hi_i is not None and rows[hi_i][2] - close >= threshold
        rose = lo_i is not None and close - rows[lo_i][1] >= threshold
        if direction == 0:
            if fell and rose:  # the earlier extreme is the first pivot
                fell, rose = (hi_i <= lo_i), (lo_i < hi_i)
        elif direction > 0:
            rose = False
            last_low = pivots[-1].price if pivots else None
            if hi_i is not None and last_low is not None and close < last_low:
                fell = True  # closing through the prior swing low
        else:
            fell = False
            last_high = pivots[-1].price if pivots else None
            if lo_i is not None and last_high is not None and close > last_high:
                rose = True
        if fell:
            confirm(hi_i, "high", i)
            direction = -1
            lo_i = _extreme(rows, hi_i + 1, i, 1, pick_max=False)
            hi_i = None
        elif rose:
            confirm(lo_i, "low", i)
            direction = 1
            hi_i = _extreme(rows, lo_i + 1, i, 2, pick_max=True)
            lo_i = None
    return pivots


def detect_pivots(
    candles: list[list[Any]] | None, *, atr_mult: float = DEFAULT_ATR_MULT
) -> list[SwingPivot]:
    """Causal ATR-adaptive ZigZag pivots for raw candles."""
    rows = _rows(candles)
    bar_s = _bar_seconds(rows)
    if len(rows) <= ATR_PERIOD or not bar_s:
        return []
    return _zigzag(rows, float(atr_mult), bar_s)


# ─── wave grammar ─────────────────────────────────────────────────────────────


def _kinds(sgn: int, count: int) -> tuple[str, ...]:
    """Expected pivot kinds for a structure whose trend runs in direction ``sgn``."""
    first, second = ("low", "high") if sgn > 0 else ("high", "low")
    return tuple(first if i % 2 == 0 else second for i in range(count))


def _after(rows: list[Row], start: int, sgn: int) -> tuple[float, float, int] | None:
    """Price action after bar ``start`` in trend-relative terms.

    Returns ``(q_adverse_min, q_favorable_max, adverse_index)`` where ``q`` is
    ``sgn * price``: adverse is the low in a bullish read, the high in a bearish.
    """
    if start + 1 >= len(rows):
        return None
    adv_col, fav_col = (1, 2) if sgn > 0 else (2, 1)
    adv_i = start + 1
    fav = sgn * rows[adv_i][fav_col]
    for i in range(start + 1, len(rows)):
        if sgn * rows[i][adv_col] < sgn * rows[adv_i][adv_col]:
            adv_i = i
        fav = max(fav, sgn * rows[i][fav_col])
    return sgn * rows[adv_i][adv_col], fav, adv_i


def _impulse_ok(q: list[float], complete: bool) -> bool:
    """Hard rules on trend-relative prices ``W0..W4`` (and ``W5`` if complete)."""
    w0, w1, w2, w3 = q[:4]
    if not (w1 > w0 and w2 > w0 and w3 > w1 and w2 < w1):
        return False  # wave 2 retraced 100% of wave 1, or wave 3 fell short
    if len(q) < 5:
        return True
    w4 = q[4]
    if not (w1 < w4 < w3):
        return False  # wave 4 entered wave 1's territory
    if not complete:
        return True
    w5 = q[5]
    len1, len3, len5 = w1 - w0, w3 - w2, w5 - w4
    return w5 > w3 and not (len3 < len1 and len3 < len5)


def _abc_base(tail: list[SwingPivot], sgn: int) -> dict[str, float] | None:
    """Checks shared by complete and in-progress ABC on ``O, P0, A, B``."""
    if tuple(p.kind for p in tail[:4]) != _kinds(sgn, 4):
        return None
    qo, qp, qa, qb = (sgn * p.price for p in tail[:4])
    impulse, a_len = qp - qo, qp - qa
    if impulse <= 0 or a_len <= 0 or qa <= qo:
        return None
    b_ret = (qb - qa) / a_len
    if not B_RETRACE_MIN <= b_ret < 1.0:
        return None
    return {
        "qo": qo,
        "qb": qb,
        "a_len": a_len,
        "b_retrace_of_a": b_ret,
        "a_retrace_of_prior_leg": a_len / impulse,
    }


def _c_zone(base: dict[str, float], sgn: int) -> dict[str, Any] | None:
    """Projected wave C prices, cut where the prior trend's origin would break."""
    qb, a_len, qo = base["qb"], base["a_len"], base["qo"]
    floor = max(qo, qb - C_PROJECTION_MAX * a_len)
    shallow = qb - C_PROJECTION_MIN * a_len
    if floor >= shallow:
        return None
    levels = {}
    for k in C_LEVELS:
        q = qb - k * a_len
        if q >= floor and sgn * q > 0:
            levels[f"{k:.3f}"] = sgn * q
    edge_a, edge_b = sgn * floor, sgn * shallow
    if min(edge_a, edge_b) <= 0:
        return None
    ext_a, ext_b = floor, qb - 1.272 * a_len
    extended = None
    if ext_a < ext_b:
        extended = {
            "low": min(sgn * ext_a, sgn * ext_b),
            "high": max(sgn * ext_a, sgn * ext_b),
        }
    return {
        "low": min(edge_a, edge_b),
        "high": max(edge_a, edge_b),
        "levels": levels,
        "extended": extended,
        "direction": "down" if sgn > 0 else "up",
    }


def _point(label: str, p: SwingPivot) -> dict[str, Any]:
    return {
        "label": label,
        "ts": p.ts,
        "price": p.price,
        "kind": p.kind,
        "index": p.index,
        "confirmed": True,
    }


def _open_point(label: str, rows: list[Row], i: int, sgn: int) -> dict[str, Any]:
    """A developing (unconfirmed) wave extreme in the adverse direction."""
    return {
        "label": label,
        "ts": rows[i][0],
        "price": rows[i][1] if sgn > 0 else rows[i][2],
        "kind": "low" if sgn > 0 else "high",
        "index": i,
        "confirmed": False,
    }


def _abc_complete(
    pivots: list[SwingPivot], rows: list[Row], sgn: int
) -> dict[str, Any] | None:
    if len(pivots) < 5:
        return None
    tail = pivots[-5:]
    if tail[4].kind != _kinds(sgn, 5)[4]:
        return None
    base = _abc_base(tail, sgn)
    if base is None:
        return None
    o, p0, a, b, c = tail
    qa, qc = sgn * a.price, sgn * c.price
    c_proj = (base["qb"] - qc) / base["a_len"]
    if not (qc < qa and qc > base["qo"]):
        return None  # C must end beyond A and above the prior trend's origin
    if not C_PROJECTION_MIN <= c_proj <= C_PROJECTION_MAX:
        return None
    after = _after(rows, c.index, sgn)
    status = "confirmed"
    if after is not None:
        if after[0] < qc:
            return None  # traded through the end of C: the count is broken
        if after[1] >= base["qb"]:
            status = "target_reached"
    return {
        "pattern": "abc_complete",
        "status": status,
        "sgn": sgn,
        "points": [
            _point("start", o),
            _point("0", p0),
            _point("A", a),
            _point("B", b),
            _point("C", c),
        ],
        "legs": (p0.index, a.index, b.index, c.index),
        "invalidation": c.price,
        "target": b.price,
        "zone": _c_zone(base, sgn),
        "fib": {
            "b_retrace_of_a": base["b_retrace_of_a"],
            "c_projection_of_a": c_proj,
            "a_retrace_of_prior_leg": base["a_retrace_of_prior_leg"],
        },
        "pre": pivots[:-5],
    }


def _abc_in_progress(
    pivots: list[SwingPivot], rows: list[Row], sgn: int
) -> dict[str, Any] | None:
    if len(pivots) < 4:
        return None
    tail = pivots[-4:]
    base = _abc_base(tail, sgn)
    zone = _c_zone(base, sgn) if base else None
    after = _after(rows, tail[3].index, sgn)
    if base is None or zone is None or after is None:
        return None
    o, p0, a, b = tail
    q_c, q_fav, c_i = after
    q_inv = max(base["qo"], base["qb"] - C_PROJECTION_MAX * base["a_len"])
    if q_fav > base["qb"] or q_c < q_inv:
        return None
    in_zone = q_c <= base["qb"] - C_PROJECTION_MIN * base["a_len"]
    return {
        "pattern": "abc_in_progress",
        "status": "in_c_zone" if in_zone else "awaiting_c_zone",
        "sgn": sgn,
        "points": [
            _point("start", o),
            _point("0", p0),
            _point("A", a),
            _point("B", b),
            _open_point("C", rows, c_i, sgn),
        ],
        "legs": (p0.index, a.index, b.index, c_i),
        "invalidation": sgn * q_inv,
        "target": b.price,
        "zone": zone,
        "fib": {
            "b_retrace_of_a": base["b_retrace_of_a"],
            "c_projection_of_a": (base["qb"] - q_c) / base["a_len"],
            "a_retrace_of_prior_leg": base["a_retrace_of_prior_leg"],
        },
        "pre": pivots[:-4],
    }


def _impulse(
    pivots: list[SwingPivot], rows: list[Row], sgn: int
) -> dict[str, Any] | None:
    """Complete five waves, or wave 5 or wave 4 still running."""
    labels = ("0", "1", "2", "3", "4", "5")
    for count, complete in ((6, True), (5, False), (4, False)):
        if len(pivots) < count:
            continue
        tail = pivots[-count:]
        if tuple(p.kind for p in tail) != _kinds(sgn, count):
            continue
        q = [sgn * p.price for p in tail]
        if not _impulse_ok(q, complete):
            continue
        after = _after(rows, tail[-1].index, sgn)
        len1, len3 = q[1] - q[0], q[3] - q[2]
        fib = {
            "wave2_retrace_of_wave1": (q[1] - q[2]) / len1,
            "wave3_vs_wave1": len3 / len1,
        }
        points = [_point(labels[i], p) for i, p in enumerate(tail)]
        if complete:
            if after is not None and after[1] > q[5]:
                continue  # price is past wave 5; the pivot set is stale
            status, q_inv = "complete", q[0]
            fib["wave5_vs_wave1"] = (q[5] - q[4]) / len1
        elif count == 5:
            if after is None:
                continue
            # Wave 3 may not be the shortest, which caps wave 5 when 3 < 1.
            if after[0] <= q[1] or (len3 < len1 and after[1] - q[4] > len3):
                continue
            status, q_inv = "wave_5_underway", q[1]
            fib["wave4_retrace_of_wave3"] = (q[3] - q[4]) / len3
        else:
            if after is None or after[0] <= q[1] or after[1] > q[3]:
                continue
            status, q_inv = "wave_4_underway", q[1]
            points.append(_open_point("4", rows, after[2], sgn))
        return {
            "pattern": "impulse_complete" if complete else "impulse_in_progress",
            "status": status,
            "sgn": sgn,
            "points": points,
            "legs": None,
            "invalidation": sgn * q_inv,
            "target": None,
            "zone": None,
            "fib": fib,
            "pre": [],
        }
    return None


def _find_pattern(pivots: list[SwingPivot], rows: list[Row]) -> dict[str, Any] | None:
    """The valid reads are mutually exclusive for a given pivot tail."""
    for finder in (_abc_complete, _abc_in_progress, _impulse):
        for sgn in (1, -1):
            found = finder(pivots, rows, sgn)
            if found is not None:
                return found
    return None


# ─── indicators and confluence ────────────────────────────────────────────────


def _technical_analysis():
    """``TechnicalAnalysis`` from the existing indicator module, if importable."""
    try:
        from technical_analysis import TechnicalAnalysis
    except Exception:  # pragma: no cover - optional heavy dependencies
        try:
            from backend.technical_analysis import TechnicalAnalysis
        except Exception:
            return None
    return TechnicalAnalysis


def _ema(values: list[float], span: int) -> list[float]:
    alpha = 2.0 / (span + 1.0)
    out: list[float] = []
    for v in values:
        out.append(v if not out else out[-1] + alpha * (v - out[-1]))
    return out


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _factor(name: str, state: str, detail: str, **values: Any) -> dict[str, Any]:
    """``state`` is present, absent, opposed or unavailable."""
    weight = WEIGHTS[name]
    score = {"present": weight, "opposed": -weight}.get(state, 0.0)
    return {
        "name": name,
        "state": state,
        "present": state == "present",
        "weight": weight,
        "score": score,
        "detail": detail,
        "values": {k: v for k, v in values.items() if v is not None},
    }


def _higher_tf_factor(
    higher_tf_candles: list[list[Any]] | None, rows: list[Row], bar_s: float, sgn: int
) -> dict[str, Any]:
    name = "higher_tf_trend"
    hrows = _rows(higher_tf_candles)
    h_step = _bar_seconds(hrows)
    if h_step:
        # Drop any higher-timeframe bar that has not closed by the last base close.
        now = rows[-1][0] + bar_s
        hrows = [r for r in hrows if r[0] + h_step <= now]
    if not h_step or len(hrows) < HTF_EMA + HTF_SLOPE_BARS + 1:
        return _factor(name, "unavailable", "Not enough higher-timeframe history.")
    closes = [r[4] for r in hrows]
    ema = _ema(closes, HTF_EMA)
    slope = ema[-1] / ema[-1 - HTF_SLOPE_BARS] - 1.0
    if closes[-1] > ema[-1] and slope > 0:
        trend = 1
    elif closes[-1] < ema[-1] and slope < 0:
        trend = -1
    else:
        trend = 0
    label = {1: "up", -1: "down", 0: "flat"}[trend]
    state = "absent" if trend == 0 else ("present" if trend == sgn else "opposed")
    detail = f"Higher-timeframe trend is {label}."
    return _factor(name, state, detail, trend=label, ema_slope_pct=slope * 100.0)


def _abc_factors(
    found: dict[str, Any],
    rows: list[Row],
    bar_s: float,
    higher_tf_candles: list[list[Any]] | None,
) -> list[dict[str, Any]]:
    sgn = found["sgn"]
    i_p0, i_a, i_b, i_c = found["legs"]
    closes = [r[4] for r in rows]
    scale = closes[-1]
    scaled = [c / scale for c in closes]  # keeps rounded indicators well-conditioned
    ta = _technical_analysis()
    factors = [_higher_tf_factor(higher_tf_candles, rows, bar_s, sgn)]
    c_beyond_a = sgn * (rows[i_c][1] if sgn > 0 else rows[i_c][2]) < sgn * (
        rows[i_a][1] if sgn > 0 else rows[i_a][2]
    )

    def rsi_at(i: int) -> float | None:
        if ta is None or i < RSI_PERIOD:
            return None
        return _num(ta.calculate_rsi(closes[i - RSI_PERIOD : i + 1], RSI_PERIOD))

    def macd_hist_at(i: int) -> float | None:
        if ta is None or i + 1 < MACD_MIN_BARS:
            return None
        return _num(ta.calculate_macd(scaled[: i + 1]).get("histogram"))

    for name, read, floor in (
        ("rsi_divergence", rsi_at, RSI_DIVERGENCE_MIN),
        ("macd_divergence", macd_hist_at, 0.0),
    ):
        at_a, at_c = read(i_a), read(i_c)
        if at_a is None or at_c is None:
            factors.append(_factor(name, "unavailable", "Indicator not available."))
            continue
        gain = sgn * (at_c - at_a)
        ok = c_beyond_a and gain > 0 and gain >= floor
        what = "RSI(14)" if name == "rsi_divergence" else "MACD histogram"
        detail = (
            f"{what} diverged from price between the A and C extremes."
            if ok
            else f"No {what} divergence between the A and C extremes."
        )
        factors.append(
            _factor(name, "present" if ok else "absent", detail, at_a=at_a, at_c=at_c)
        )

    vol_a = [r[5] for r in rows[i_p0 + 1 : i_a + 1]]
    vol_c = [r[5] for r in rows[i_b + 1 : i_c + 1]]
    mean_a = sum(vol_a) / len(vol_a) if vol_a else 0.0
    if not vol_c or mean_a <= 0:
        factors.append(
            _factor("volume_contraction", "unavailable", "Volume not available.")
        )
    else:
        ratio = (sum(vol_c) / len(vol_c)) / mean_a
        ok = ratio <= VOLUME_CONTRACTION_MAX
        detail = f"Wave C traded {ratio:.2f}x the per-bar volume of wave A."
        factors.append(
            _factor(
                "volume_contraction", "present" if ok else "absent", detail, ratio=ratio
            )
        )

    band_at_c = band_now = None
    if ta is not None and i_c + 1 >= BOLLINGER_PERIOD:
        key = "lower" if sgn > 0 else "upper"
        at_c = ta.calculate_bollinger_bands(
            scaled[i_c + 1 - BOLLINGER_PERIOD : i_c + 1]
        )
        now = ta.calculate_bollinger_bands(scaled[-BOLLINGER_PERIOD:])
        band_at_c, band_now = _num(at_c.get(key)), _num(now.get(key))
    if band_at_c is None or band_now is None:
        factors.append(
            _factor("bollinger_reclaim", "unavailable", "Bands not available.")
        )
    else:
        extreme = (rows[i_c][1] if sgn > 0 else rows[i_c][2]) / scale
        pierced = sgn * extreme < sgn * band_at_c
        back = sgn * scaled[-1] > sgn * band_now
        ok = pierced and back
        side = "lower" if sgn > 0 else "upper"
        detail = (
            f"Wave C pierced the {side} Bollinger Band and price closed back inside."
            if ok
            else f"No reclaim of the {side} Bollinger Band."
        )
        factors.append(
            _factor("bollinger_reclaim", "present" if ok else "absent", detail)
        )

    ema = _ema(closes, FAST_EMA)
    extreme = rows[i_c][1] if sgn > 0 else rows[i_c][2]
    ok = sgn * extreme < sgn * ema[i_c] and sgn * closes[-1] > sgn * ema[-1]
    side = "above" if sgn > 0 else "below"
    detail = (
        f"Price closed back {side} the fast EMA after wave C."
        if ok
        else "No reclaim of the fast EMA."
    )
    factors.append(_factor("ema_reclaim", "present" if ok else "absent", detail))

    pre = found["pre"]
    prior = (
        len(pre) >= 6
        and tuple(p.kind for p in pre[-6:]) == _kinds(sgn, 6)
        and _impulse_ok([sgn * p.price for p in pre[-6:]], complete=True)
    )
    detail = (
        "The move before the correction counts as five waves."
        if prior
        else "The move before the correction does not count as five waves."
    )
    factors.append(_factor("prior_impulse", "present" if prior else "absent", detail))
    return factors


# ─── assembly ─────────────────────────────────────────────────────────────────


def _fmt(price: float) -> str:
    if price >= 1000:
        return f"${price:,.0f}"
    if price >= 1:
        return f"${price:,.2f}"
    return f"${price:.4g}"


_SUPPORT_TEXT = {
    "higher_tf_trend": "the higher-timeframe trend agrees",
    "rsi_divergence": "RSI divergence",
    "macd_divergence": "MACD divergence",
    "volume_contraction": "lighter volume on the last swing",
    "bollinger_reclaim": "a Bollinger Band reclaim",
    "ema_reclaim": "a fast-EMA reclaim",
    "prior_impulse": "a five-wave move before it",
}


def _summary(found: dict[str, Any], factors: list[dict[str, Any]]) -> str:
    sgn, pattern, status = found["sgn"], found["pattern"], found["status"]
    inv = _fmt(found["invalidation"])
    side = "below" if sgn > 0 else "above"
    if pattern.startswith("impulse"):
        move = "advance" if sgn > 0 else "decline"
        stage = {
            "complete": "looks complete, which often precedes a three-swing correction",
            "wave_5_underway": "is in progress with the fifth swing underway",
            "wave_4_underway": "is in progress with the fourth swing underway",
        }[status]
        return (
            f"A five-swing {move} {stage}. "
            f"This count no longer applies if price trades {side} {inv}."
        )
    shape = (
        "pullback inside a larger advance"
        if sgn > 0
        else "relief bounce inside a larger decline"
    )
    zone = found["zone"]
    if pattern == "abc_complete":
        ratio = found["fib"]["c_projection_of_a"]
        text = (
            f"A three-swing {shape} (A-B-C) looks complete. The third swing ended "
            f"near {inv}, {ratio:.2f} times the size of the first. "
            f"This count no longer applies if price trades {side} {inv}."
        )
        if status == "target_reached":
            text += f" Price has since returned to the wave B level near {_fmt(found['target'])}."
    else:
        area = f"{_fmt(zone['low'])}–{_fmt(zone['high'])}"
        where = "has entered" if status == "in_c_zone" else "has not yet reached"
        text = (
            f"A three-swing {shape} (A-B-C) is unfolding. The third swing {where} "
            f"the {area} area where such moves commonly end. "
            f"This count no longer applies if price trades {side} {inv}."
        )
    present = [_SUPPORT_TEXT[f["name"]] for f in factors if f["state"] == "present"]
    opposed = any(
        f["name"] == "higher_tf_trend" and f["state"] == "opposed" for f in factors
    )
    if present:
        text += " Supporting signs: " + ", ".join(present) + "."
    else:
        text += (
            " No supporting signs from momentum, volume or the higher timeframe yet."
        )
    if opposed:
        text += " The higher-timeframe trend runs against this read."
    return text


def _empty(
    reason: str, rows: list[Row], atr_mult: float, summary: str
) -> WaveReadResult:
    bar_s = _bar_seconds(rows)
    return {
        "available": False,
        "reason": reason,
        "active_pattern": "none",
        "status": "none",
        "bias": "neutral",
        "pivots": [],
        "wave_points": [],
        "projected_c_zone": None,
        "invalidation_price": None,
        "target_price": None,
        "fib_ratios": {},
        "confluence_factors": [],
        "confluence_score": 0.0,
        "confluence_confirmed": False,
        "confidence": 0.0,
        "confidence_label": "low",
        "summary": summary,
        "atr_mult": atr_mult,
        "bar_seconds": bar_s,
        "candle_count": len(rows),
        "as_of_ts": rows[-1][0] + bar_s if rows and bar_s else None,
        "outcome_validated": False,
    }


def _geometry_score(found: dict[str, Any]) -> float:
    fib, pattern = found["fib"], found["pattern"]
    if pattern.startswith("impulse"):
        score = 0.5
        if fib.get("wave3_vs_wave1", 0.0) >= 1.0:
            score += 0.25
        if 0.382 <= fib.get("wave2_retrace_of_wave1", 0.0) <= 0.786:
            score += 0.25
        return score
    score = 0.5 if pattern == "abc_complete" or found["status"] == "in_c_zone" else 0.25
    if 0.382 <= fib["b_retrace_of_a"] <= 0.786:
        score += 0.25
    c = fib["c_projection_of_a"]
    if 0.9 <= c <= 1.1 or 1.272 <= c <= 1.618:
        score += 0.25
    return score


def analyze_wave_structure(
    candles: list[list[Any]] | None,
    *,
    higher_tf_candles: list[list[Any]] | None = None,
    atr_mult: float = DEFAULT_ATR_MULT,
) -> WaveReadResult:
    """Read the wave structure of ``candles`` as of the last bar's close.

    Pass completed bars only. ``higher_tf_candles`` (for example 4h or 1d bars
    of the same product) adds a trend check; bars not closed by the last base
    close are ignored. Always returns a JSON-serializable dict; when history is
    too short ``available`` is False and ``active_pattern`` is ``"none"``.
    """
    atr_mult = float(atr_mult)
    rows = _rows(candles)
    bar_s = _bar_seconds(rows)
    if len(rows) < MIN_CANDLES or not bar_s:
        return _empty(
            "insufficient_history",
            rows,
            atr_mult,
            "Not enough candle history to read the wave structure.",
        )
    pivots = _zigzag(rows, atr_mult, bar_s)
    found = _find_pattern(pivots, rows)
    out = _empty(
        "no_pattern", rows, atr_mult, "No clear wave structure in the recent swings."
    )
    out["available"] = True
    out["pivots"] = [p.to_dict() for p in pivots[-MAX_PIVOTS_OUT:]]
    if found is None:
        return out
    del out["reason"]
    sgn = found["sgn"]
    if found["legs"] is not None:
        factors = _abc_factors(found, rows, bar_s, higher_tf_candles)
    else:
        factors = [_higher_tf_factor(higher_tf_candles, rows, bar_s, sgn)]
    score = max(0.0, min(1.0, sum(f["score"] for f in factors)))
    confidence = round(0.4 * _geometry_score(found) + 0.6 * score, 3)
    out.update(
        active_pattern=found["pattern"],
        status=found["status"],
        bias="bullish" if sgn > 0 else "bearish",
        wave_points=found["points"],
        projected_c_zone=found["zone"],
        invalidation_price=found["invalidation"],
        target_price=found["target"],
        fib_ratios={k: round(v, 4) for k, v in found["fib"].items()},
        confluence_factors=factors,
        confluence_score=round(score, 3),
        confluence_confirmed=bool(
            found["legs"] is not None and score >= CONFLUENCE_THRESHOLD
        ),
        confidence=confidence,
        confidence_label=(
            "high" if confidence >= 0.66 else "medium" if confidence >= 0.4 else "low"
        ),
        summary=_summary(found, factors),
    )
    return out
