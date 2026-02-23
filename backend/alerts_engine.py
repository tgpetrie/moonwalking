"""
alerts_engine.py — Canonical Moonwalking Alert Engine (Coinbase-only)

Pure-function design:
    compute_alerts(price_snapshot, volume_snapshot, state) -> (alerts, new_state)

Inputs:
    price_snapshot:  dict keyed by symbol -> {price, pct_1m, pct_3m, pct_1h, asof_ts}
    volume_snapshot: dict keyed by symbol -> {volume_1h_now, volume_1h_prev,
                     volume_change_1h_pct, baseline_ready, asof_ts}
    minute_volumes:  dict keyed by product_id -> list of {ts, vol, open, close, high, low}
    state:           AlertEngineState (mutable across calls)

Alert types implemented (Coinbase-only):
    WHALE_MOVE   — unusual aggregated volume surge (z-score or hourly comparison)
    STEALTH_MOVE — volume spike + muted price (early smoke)
    MOONSHOT     — massive upside impulse + optional volume/breadth confirmation
    CRATER       — massive downside impulse
    BREAKOUT     — strong 3m move aligned with 1h trend (not moonshot-scale)
    DIVERGENCE   — volume vs price disagreement OR timeframe disagreement
    COIN_REVERSAL_UP/DOWN   — fast direction flips after a strong 3m move
    COIN_FAKEOUT            — breakout rejection/trap pattern
    COIN_PERSISTENT_GAINER/LOSER — consecutive directional streaks
    COIN_VOLATILITY_EXPANSION — realized-volatility wake-up vs recent baseline
    COIN_LIQUIDITY_SHOCK    — minute-volume spike while price is still muted
    COIN_TREND_BREAK_UP/DOWN — fast/slow EMA crossover with volume support
    COIN_SQUEEZE_BREAK      — compression regime breaks with abrupt move
    COIN_EXHAUSTION_TOP/BOTTOM — persistent run loses energy and flips
    COIN_FOMO            — coin acceleration + volume confirmation in hot tape
    COIN_BREADTH_THRUST  — coin outperformance during broad participation
    COIN_BREADTH_FAILURE — coin underperformance in weak or failing breadth
    FOMO_ALERT / FEAR_ALERT — optional standalone market-only mood alerts (disabled by default)

Not implemented (require external sources):
    SENTIMENT_SPIKE, NEWS_CATALYST, ARBITRAGE

Storage:
    In-memory state with optional Redis for dedupe/TTL.
    Engine never depends on Redis for correctness — fails open.
"""

from __future__ import annotations

import time
import uuid
import math
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
from statistics import median
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Alert taxonomy
# ---------------------------------------------------------------------------


class AlertType(str, Enum):
    WHALE_MOVE = "whale_move"
    STEALTH_MOVE = "stealth_move"
    MOONSHOT = "moonshot"
    CRATER = "crater"
    BREAKOUT = "breakout"
    DUMP = "dump"
    DIVERGENCE = "divergence"
    COIN_FOMO = "coin_fomo"
    COIN_BREADTH_THRUST = "coin_breadth_thrust"
    COIN_BREADTH_FAILURE = "coin_breadth_failure"
    COIN_REVERSAL_UP = "coin_reversal_up"
    COIN_REVERSAL_DOWN = "coin_reversal_down"
    COIN_FAKEOUT = "coin_fakeout"
    COIN_PERSISTENT_GAINER = "coin_persistent_gainer"
    COIN_PERSISTENT_LOSER = "coin_persistent_loser"
    COIN_VOLATILITY_EXPANSION = "coin_volatility_expansion"
    COIN_LIQUIDITY_SHOCK = "coin_liquidity_shock"
    COIN_TREND_BREAK_UP = "coin_trend_break_up"
    COIN_TREND_BREAK_DOWN = "coin_trend_break_down"
    COIN_SQUEEZE_BREAK = "coin_squeeze_break"
    COIN_EXHAUSTION_TOP = "coin_exhaustion_top"
    COIN_EXHAUSTION_BOTTOM = "coin_exhaustion_bottom"
    MARKET_FOMO_SIREN = "market_fomo_siren"
    MARKET_FEAR_SIREN = "market_fear_siren"
    FOMO_ALERT = "fomo_alert"
    FEAR_ALERT = "fear_alert"
    # Future (disabled, require external sources)
    SENTIMENT_SPIKE = "sentiment_spike"
    NEWS_CATALYST = "news_catalyst"
    ARBITRAGE = "arbitrage"


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# ---------------------------------------------------------------------------
# Thresholds — per liquidity bucket when applicable
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS = {
    # Impulse (MOONSHOT / CRATER / BREAKOUT / DUMP)
    "moonshot_1m_pct": 1.00,  # >= this on 1m -> moonshot/crater
    "moonshot_3m_pct": 2.60,  # >= this on 3m -> moonshot/crater
    "breakout_1m_pct": 0.55,  # >= this on 1m -> breakout/dump
    "breakout_3m_pct": 1.90,  # >= this on 3m -> breakout/dump
    "impulse_1m_pct": 1.25,  # minimum to even consider 1m impulse
    "impulse_3m_pct": 2.0,  # minimum to even consider 3m impulse
    # Whale (volume surge)
    "whale_z_score": 3.0,  # single-candle z-score vs rolling baseline
    "whale_cluster_z": 2.5,  # 3-candle cluster z-score
    "whale_candle_pct": 0.3,  # min abs(candle_pct) for whale move
    "whale_surge_1h_pct": 150.0,  # fallback: hourly vol change %
    "whale_min_abs_vol": 500,  # minimum absolute volume (units) to qualify
    # Absorption (sub-type of whale)
    "absorption_z": 2.5,
    "absorption_max_pct": 0.15,
    "absorption_max_range": 0.3,
    "absorption_min_pulses": 1,
    # Stealth (volume spike + muted price = early smoke)
    "stealth_vol_min_pct": 110.0,  # vol change must be ABOVE this (loud volume)
    "stealth_price_max_abs_pct": 1.2,  # abs(pct_3m) must be BELOW this (quiet price)
    # Divergence
    "divergence_1m_threshold": 0.65,  # abs(ret_1m) must exceed
    "divergence_3m_threshold": 0.65,  # abs(ret_3m) must exceed (opposite sign)
    # FOMO / FEAR (Market Pressure Index)
    "fomo_heat_min": 80,
    "fear_heat_max": 20,
    "fomo_fg_min": 70,  # Fear & Greed min for FOMO (None = ignore)
    "fear_fg_max": 30,  # Fear & Greed max for FEAR
    # Rare market siren (standalone MARKET alerts only on strong confluence)
    "market_siren_score_min": 80.0,
    "market_siren_min_legs": 3,
    "market_siren_persist_polls": 3,
    "market_siren_cooldown_s": 900,
    "market_siren_extreme_heat_min": 0.75,
    "market_siren_extreme_fear_max": -0.75,
    # Coin mood alert thresholds (coin-scoped, market-aware)
    "vol_ratio_fomo": 2.0,
    "vol_score_mid": 0.60,
    "coin_fomo_mpi_min": 72,
    "coin_fomo_d_mpi_60s": 6.0,
    "coin_fomo_pct3m_min": 1.8,
    "coin_fomo_pct1m_min": 0.6,
    "coin_fomo_accel_min": 0.9,
    "coin_thrust_breadth_min": 0.65,
    "coin_thrust_pct3m_min": 1.2,
    "coin_thrust_rs3m_min": 0.8,
    "coin_thrust_persist_min": 0.35,
    "coin_failure_breadth_max": 0.35,
    "coin_failure_pct3m_max": -1.2,
    "coin_failure_rs3m_max": -0.9,
    "vol_regime_min": 0.20,
    "reversal_min_prev_pct": 2.0,
    "reversal_min_flip_pct": 0.6,
    "fakeout_min_breakout_pct": 1.6,
    "fakeout_min_reject_pct": 0.6,
    "persist_min_streak": 3,
    "persist_min_pct": 1.1,
    "volx_window_now": 10,
    "volx_window_prev": 20,
    "volx_ratio_min": 1.7,
    "volx_vol_floor": 0.25,
    "volx_prev_floor": 0.02,
    "liq_shock_z_min": 2.6,
    "liq_shock_price_max_abs_pct": 0.25,
    "liq_shock_min_samples": 30,
    "liq_shock_min_latest_vol": 75.0,
    "trend_break_fast_alpha": 0.3333,  # ~EMA(5) on 1m returns
    "trend_break_slow_alpha": 0.0952,  # ~EMA(20) on 1m returns
    "trend_break_min_abs_diff": 0.08,
    "trend_break_vol_confirm_pct": 15.0,
    "trend_break_vol_ratio_min": 1.20,
    "squeeze_window_n": 10,
    "squeeze_hist_n": 120,
    "squeeze_compress_percentile": 0.25,
    "squeeze_break_pct_1m_min": 0.8,
    "squeeze_break_vol_ratio_min": 1.6,
    "exhaustion_min_streak": 4,
    "exhaustion_flip_pct_1m": 0.6,
    "exhaustion_context_pct_3m": 1.0,
    "exhaustion_vol_drop_ratio": 0.20,
    # Return-history warmup + global alert shaping
    "return_hist_min_points": 12,
    "alerts_max_total": 24,
    "alerts_max_per_symbol": 2,
    # Family shaping (prevents whale/stealth dominating)
    "whale_symbol_cooldown_s": 180,
    "stealth_symbol_cooldown_s": 240,
    "family_global_cooldown_s": 20,
    "family_recent_window_s": 300,
    "family_recent_max": 14,
    # Market pressure (component calculation)
    "pressure_impulse_k": 20.0,  # scaling for impulse density component
    "pressure_vol_ratio_ref": 5.0,  # reference ratio for log scaling
    "pressure_volume_top_n": 10,  # robust aggregate over top-N volume scores
    "pressure_persistence_n": 10,  # top-N overlap for persistence
    "pressure_ema_alpha": 0.12,  # smoothing for pressure score
    # Cooldowns (seconds)
    "cooldown_impulse": 90,
    "cooldown_whale": 180,
    "cooldown_absorption": 300,
    "cooldown_whale_surge": 300,
    "cooldown_stealth": 420,
    "cooldown_divergence": 180,
    "cooldown_fomo": 600,
    "cooldown_market_siren": 900,  # legacy alias
    "cooldown_coin_fomo": 240,
    "cooldown_coin_thrust": 180,
    "cooldown_coin_failure": 180,
    "cooldown_reversal": 120,
    "cooldown_fakeout": 180,
    "cooldown_persist": 240,
    "cooldown_volx": 240,
    "cooldown_liq_shock": 150,
    "cooldown_trend_break": 240,
    "cooldown_squeeze_break": 240,
    "cooldown_exhaustion": 300,
    # TTLs (minutes)
    "ttl_impulse_min": 5,
    "ttl_whale_min": 8,
    "ttl_absorption_min": 5,
    "ttl_whale_surge_min": 10,
    "ttl_stealth_min": 5,
    "ttl_divergence_min": 5,
    "ttl_fomo_min": 10,
    "ttl_market_siren_min": 12,
    "ttl_coin_mood_min": 5,
    "ttl_reversal_min": 10,
    "ttl_fakeout_min": 8,
    "ttl_persist_min": 20,
    "ttl_volx_min": 7,
    "ttl_liq_shock_min": 6,
    "ttl_trend_break_min": 8,
    "ttl_squeeze_break_min": 8,
    "ttl_exhaustion_min": 10,
    # Dedupe deltas (magnitude must change by at least this to re-fire within cooldown)
    "dedupe_impulse": 0.35,
    "dedupe_whale": 2.4,
    "dedupe_absorption": 1.0,
    "dedupe_whale_surge": 30.0,
    "dedupe_stealth": 0.8,
    "dedupe_divergence": 0.5,
    "dedupe_market_siren": 4.0,  # legacy alias
    "dedupe_coin_fomo": 0.35,
    "dedupe_coin_thrust": 0.5,
    "dedupe_coin_failure": 0.5,
    "dedupe_reversal": 1.8,
    "dedupe_fakeout": 2.0,
    "dedupe_persist": 2.5,
    "dedupe_volx": 0.4,
    "dedupe_liq_shock": 0.75,
    "dedupe_trend_break": 0.08,
    "dedupe_squeeze_break": 0.6,
    "dedupe_exhaustion": 0.6,
}


# ---------------------------------------------------------------------------
# Engine state (persists across compute cycles)
# ---------------------------------------------------------------------------


@dataclass
class AlertEngineState:
    """Mutable state carried between compute_alerts() calls."""

    # Per-key cooldown tracking: key -> (last_ts, last_magnitude, last_direction)
    last_fired: dict[str, tuple[float, float, str | None]] = field(default_factory=dict)
    # Market pressure smoothing state
    market_pressure_ema: float | None = None
    market_pressure_abs_move_hist: list[float] = field(default_factory=list)
    market_pressure_index_hist: list[tuple[float, float]] = field(default_factory=list)
    market_siren_streak: int = 0
    market_siren_last_key: str | None = None
    market_siren_last_emit_ts: float = 0.0
    last_emit_by_symbol_family: dict[str, float] = field(default_factory=dict)
    last_emit_by_family: dict[str, float] = field(default_factory=dict)
    emit_ring: list[tuple[float, str]] = field(default_factory=list)
    # Coin persistence streaks: symbol -> (streak_count, direction)
    coin_persistence_streaks: dict[str, tuple[int, str]] = field(default_factory=dict)
    # Coin 1m return history used for volatility expansion detection.
    coin_return_hist: dict[str, list[float]] = field(default_factory=dict)
    # EMA state for micro-structure trend-break detection.
    coin_trend_ema_fast: dict[str, float] = field(default_factory=dict)
    coin_trend_ema_slow: dict[str, float] = field(default_factory=dict)
    coin_trend_last_diff: dict[str, float] = field(default_factory=dict)
    # Last seen per-coin volume ratio for exhaustion checks.
    coin_last_vol_ratio: dict[str, float] = field(default_factory=dict)

    def check_cooldown(
        self,
        key: str,
        cooldown_s: float,
        magnitude: float = 0.0,
        direction: str | None = None,
        dedupe_delta: float = 0.35,
    ) -> bool:
        """Return True if this alert is allowed to fire (not in cooldown or magnitude/direction changed enough)."""
        now = time.time()
        prev = self.last_fired.get(key)
        if prev is None:
            return True
        last_ts, last_mag, last_dir = prev
        within_cooldown = (now - last_ts) < cooldown_s
        if not within_cooldown:
            return True
        # Within cooldown — allow if magnitude jumped or direction flipped
        if magnitude > last_mag + dedupe_delta:
            return True
        if direction and last_dir and direction != last_dir:
            return True
        return False

    def record_fire(
        self, key: str, magnitude: float = 0.0, direction: str | None = None
    ) -> None:
        self.last_fired[key] = (time.time(), magnitude, direction)


# ---------------------------------------------------------------------------
# Market Pressure Index (replaces external sentiment)
# ---------------------------------------------------------------------------


@dataclass
class MarketPressure:
    """Coinbase-only 'emotion' proxy derived from breadth + impulse density."""

    heat: float = 50.0  # 0-100
    bias: str = "neutral"  # "up" | "down" | "neutral"
    breadth_up: float = 0.0  # fraction of symbols with 1m > threshold
    breadth_down: float = 0.0
    impulse_count: int = 0  # how many symbols crossed impulse thresholds
    symbol_count: int = 0  # total symbols evaluated
    label: str = "Normal"  # human-readable
    # Canonical payload shape for UI
    index: int = 50
    score01: float = 0.5
    components: dict[str, float] = field(default_factory=dict)
    ts: int = 0


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(median(values))


def _stddev(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean_v = sum(values) / float(n)
    variance = sum((v - mean_v) ** 2 for v in values) / float(n)
    return float(variance**0.5)


def _top_positive_symbols(
    price_snapshot: dict[str, dict], key: str, n: int
) -> list[str]:
    scored: list[tuple[str, float]] = []
    for sym, data in (price_snapshot or {}).items():
        val = _to_float_or_none(data.get(key))
        if val is None or val <= 0:
            continue
        scored.append((sym, val))
    scored.sort(key=lambda item: item[1], reverse=True)
    return [sym for sym, _ in scored[: max(0, int(n))]]


def _overlap_ratio(a_syms: list[str], b_syms: list[str], n: int) -> float:
    n = int(n or 0)
    if n <= 0:
        return 0.0
    if not a_syms or not b_syms:
        return 0.0
    a = set(a_syms[:n])
    b = set(b_syms[:n])
    if not a or not b:
        return 0.0
    return len(a.intersection(b)) / float(n)


def _warm_return_hist(
    state: AlertEngineState,
    price_snapshot: dict[str, dict],
    thresholds: dict,
) -> None:
    """Warm and bound per-symbol 1m return history for downstream detectors."""
    keep = max(60, int(thresholds.get("return_hist_keep", 240) or 240))
    min_points = max(1, int(thresholds.get("return_hist_min_points", 12) or 12))
    for sym, pdata in (price_snapshot or {}).items():
        pct_1m = _to_float_or_none((pdata or {}).get("pct_1m"))
        if pct_1m is None:
            continue
        hist = state.coin_return_hist.setdefault(sym, [])
        hist.append(float(pct_1m))
        if len(hist) < min_points:
            hist[:0] = [0.0] * (min_points - len(hist))
        if len(hist) > keep:
            del hist[: len(hist) - keep]


def compute_market_pressure(
    price_snapshot: dict[str, dict],
    volume_snapshot: dict[str, dict] | None = None,
    thresholds: dict | None = None,
    state: AlertEngineState | None = None,
) -> MarketPressure:
    """Compute market pressure with component decomposition.

    The `heat`/`bias` fields keep backward-compatible semantics for alert rules,
    while `index`/`score01`/`components` expose the richer UI payload.
    """
    t = thresholds or DEFAULT_THRESHOLDS
    impulse_1m = t["impulse_1m_pct"]
    impulse_3m = t["impulse_3m_pct"]
    volume_snapshot = volume_snapshot or {}

    symbols_all = set(price_snapshot.keys()) | set(volume_snapshot.keys())
    if not symbols_all:
        now_ts = int(time.time())
        return MarketPressure(
            heat=50.0,
            bias="neutral",
            breadth_up=0.0,
            breadth_down=0.0,
            impulse_count=0,
            symbol_count=0,
            label="Neutral",
            index=50,
            score01=0.5,
            components={
                "breadth": 0.0,
                "impulse_density": 0.0,
                "volume_anomaly": 0.0,
                "vol_regime": 0.0,
                "persistence": 0.0,
            },
            ts=now_ts,
        )

    returns_1m: dict[str, float] = {}
    returns_3m: dict[str, float] = {}
    returns_1h: dict[str, float] = {}
    for sym in symbols_all:
        data = price_snapshot.get(sym) or {}
        r1 = _to_float_or_none(data.get("pct_1m"))
        r3 = _to_float_or_none(data.get("pct_3m"))
        r1h = _to_float_or_none(data.get("pct_1h"))
        if r1 is not None:
            returns_1m[sym] = r1
        if r3 is not None:
            returns_3m[sym] = r3
        if r1h is not None:
            returns_1h[sym] = r1h

    # Breadth components from directional win-rate (3m preferred for stability).
    breadth_source = returns_3m if returns_3m else returns_1m
    if breadth_source:
        up_sign = sum(1 for v in breadth_source.values() if v > 0.0)
        down_sign = sum(1 for v in breadth_source.values() if v < 0.0)
        source_n = len(breadth_source)
        breadth_up = up_sign / float(max(1, source_n))
        breadth_down = down_sign / float(max(1, source_n))
    else:
        up_sign = 0
        down_sign = 0
        source_n = 0
        breadth_up = 0.0
        breadth_down = 0.0
    # Breadth intensity: directional participation imbalance (0..1).
    breadth_component = _clamp(abs(breadth_up - breadth_down), 0.0, 1.0)
    # Breadth direction: +1 all-green, -1 all-red, 0 balanced/flat.
    breadth_bias_component = _clamp(breadth_up - breadth_down, -1.0, 1.0)

    # Impulse density (symbols crossing impulse thresholds).
    impulse_total = 0
    for sym in symbols_all:
        r1 = returns_1m.get(sym)
        r3 = returns_3m.get(sym)
        if (r1 is not None and abs(r1) >= impulse_1m) or (
            r3 is not None and abs(r3) >= impulse_3m
        ):
            impulse_total += 1
    impulse_k = max(1.0, float(t.get("pressure_impulse_k", 20.0) or 20.0))
    impulse_density = _clamp(impulse_total / impulse_k, 0.0, 1.0)

    # Volume anomaly via log-scaled vol ratio and robust top-N median.
    vol_scores: list[float] = []
    ratio_ref = max(1.01, float(t.get("pressure_vol_ratio_ref", 5.0) or 5.0))
    for sym, vdata in (volume_snapshot or {}).items():
        vol_now = _to_float_or_none(vdata.get("volume_1h_now"))
        vol_prev = _to_float_or_none(vdata.get("volume_1h_prev"))
        if vol_now is None or vol_prev is None or vol_prev <= 0:
            continue
        ratio = vol_now / vol_prev
        if ratio <= 0:
            continue
        score = _clamp(math.log(ratio) / math.log(ratio_ref), 0.0, 1.0)
        vol_scores.append(score)
    vol_scores.sort(reverse=True)
    volume_top_n = max(1, int(t.get("pressure_volume_top_n", 10) or 10))
    volume_anomaly = _clamp(_median(vol_scores[:volume_top_n]), 0.0, 1.0)

    # Volatility regime: median abs move vs rolling baseline.
    abs_moves = [abs(v) for v in returns_3m.values()] or [
        abs(v) for v in returns_1m.values()
    ]
    median_abs_move = _median(abs_moves)
    if state is not None:
        hist = state.market_pressure_abs_move_hist
        hist.append(float(median_abs_move))
        if len(hist) > 120:
            del hist[: len(hist) - 120]
        baseline_abs_move = _median(hist) if hist else max(median_abs_move, 1e-9)
    else:
        baseline_abs_move = max(median_abs_move, 1e-9)
    baseline_abs_move = max(baseline_abs_move, 1e-9)
    vol_ratio = _clamp(median_abs_move / baseline_abs_move, 0.0, 2.0)
    vol_regime = _clamp(vol_ratio / 2.0, 0.0, 1.0)

    # Persistence: overlap of top gainers across time windows.
    persistence_n = max(1, int(t.get("pressure_persistence_n", 10) or 10))
    top_1m = _top_positive_symbols(price_snapshot, "pct_1m", persistence_n)
    top_3m = _top_positive_symbols(price_snapshot, "pct_3m", persistence_n)
    top_1h = _top_positive_symbols(price_snapshot, "pct_1h", persistence_n)
    o1 = _overlap_ratio(top_1m, top_3m, persistence_n)
    o2 = _overlap_ratio(top_3m, top_1h, persistence_n) if top_1h else 0.0
    persistence = _clamp((0.5 * o1) + (0.5 * o2), 0.0, 1.0)

    # Component blend -> pressure score (0..1), then smooth with EMA.
    raw_score01 = _clamp(
        (0.30 * volume_anomaly)
        + (0.25 * breadth_component)
        + (0.20 * impulse_density)
        + (0.15 * persistence)
        + (0.10 * vol_regime)
        + (0.15 * breadth_bias_component),
        0.0,
        1.0,
    )
    alpha = _clamp(float(t.get("pressure_ema_alpha", 0.12) or 0.12), 0.01, 1.0)
    if state is not None and state.market_pressure_ema is not None:
        score01 = (alpha * raw_score01) + (
            (1.0 - alpha) * float(state.market_pressure_ema)
        )
    else:
        score01 = raw_score01
    if state is not None:
        state.market_pressure_ema = score01

    # Backward-compatible heat scale for existing alert thresholds.
    heat = _clamp(score01, 0.0, 1.0) * 100.0
    index = int(round(heat))

    # Coarse up/down breadth fractions for legacy consumers.
    breadth_up = (up_sign / float(source_n)) if source_n else 0.0
    breadth_down = (down_sign / float(source_n)) if source_n else 0.0

    if index <= 20:
        label = "Fear"
        bias = "down"
    elif index <= 40:
        label = "Cautious"
        bias = "down"
    elif index <= 60:
        label = "Neutral"
        bias = "neutral"
    elif index <= 80:
        label = "Risk-On"
        bias = "up"
    else:
        label = "Euphoria"
        bias = "up"

    now_ts = int(time.time())
    return MarketPressure(
        heat=round(heat, 1),
        bias=bias,
        breadth_up=round(breadth_up, 3),
        breadth_down=round(breadth_down, 3),
        impulse_count=impulse_total,
        symbol_count=len(symbols_all),
        label=label,
        index=index,
        score01=round(score01, 4),
        components={
            "breadth": round(breadth_component, 4),
            "breadth_bias": round(breadth_bias_component, 4),
            "impulse_density": round(impulse_density, 4),
            "volume_anomaly": round(volume_anomaly, 4),
            "vol_regime": round(vol_regime, 4),
            "persistence": round(persistence, 4),
        },
        ts=now_ts,
    )


# ---------------------------------------------------------------------------
# Alert builder helper
# ---------------------------------------------------------------------------


def _make_alert(
    *,
    symbol: str,
    alert_type: AlertType,
    severity: AlertSeverity,
    title: str,
    message: str,
    evidence: dict[str, Any],
    ttl_minutes: int = 5,
    direction: str = "",
    trade_url: str | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    product_id = symbol if "-" in symbol else f"{symbol}-USD"
    window = (
        str(evidence.get("window") or ("market" if symbol == "MARKET" else "")).strip()
        if isinstance(evidence, dict)
        else ""
    )
    return {
        "id": f"{alert_type.value}_{product_id}_{uuid.uuid4().hex[:8]}",
        "ts": now.isoformat(),
        "ts_ms": int(now.timestamp() * 1000),
        "event_ts": now.isoformat(),
        "event_ts_ms": int(now.timestamp() * 1000),
        "symbol": product_id,
        "type": alert_type.value,
        "type_key": alert_type.name,
        "window": window or None,
        "severity": severity.value,
        "title": title,
        "message": message,
        "direction": direction,
        "evidence": evidence,
        "ttl_seconds": ttl_minutes * 60,
        "expires_at": (now + timedelta(minutes=ttl_minutes)).isoformat(),
        "trade_url": trade_url
        or f"https://www.coinbase.com/advanced-trade/spot/{product_id}",
    }


def _to_float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        v = float(value)
        return v if (v == v and v not in (float("inf"), float("-inf"))) else None
    except Exception:
        return None


def _record_pressure_index(state: AlertEngineState, index_value: float) -> None:
    now = time.time()
    hist = state.market_pressure_index_hist
    hist.append((now, float(index_value)))
    cutoff = now - 600.0
    if len(hist) > 180:
        del hist[: len(hist) - 180]
    while hist and hist[0][0] < cutoff:
        hist.pop(0)


def _pressure_delta_seconds(state: AlertEngineState, seconds: int = 60) -> float:
    now = time.time()
    hist = state.market_pressure_index_hist
    if not hist:
        return 0.0
    current = float(hist[-1][1])
    cutoff = now - float(seconds)
    baseline = float(hist[0][1])
    for ts, idx in reversed(hist):
        if ts <= cutoff:
            baseline = float(idx)
            break
    return current - baseline


def _attach_coin_mood_context(alerts: list[dict], pressure: MarketPressure) -> None:
    mood_label = str(pressure.label or "Neutral")
    mood_index = float(pressure.index if pressure.index is not None else pressure.heat)
    mood_score01 = float(
        pressure.score01 if pressure.score01 is not None else (mood_index / 100.0)
    )
    mood_bias = str(pressure.bias or "neutral")
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        symbol = str(alert.get("symbol") or "").upper()
        if symbol in {"MARKET", "MARKET-USD"}:
            continue
        evidence = alert.get("evidence")
        if not isinstance(evidence, dict):
            evidence = {}
        evidence.setdefault("mood_label", mood_label)
        evidence.setdefault("mood_index", round(mood_index, 2))
        evidence.setdefault("mood_score01", round(mood_score01, 4))
        evidence.setdefault("mood_bias", mood_bias)
        alert["evidence"] = evidence


def _compute_vol_ratio(
    vdata: dict[str, Any], ratio_ref: float
) -> tuple[float | None, float | None]:
    vol_now = _to_float_or_none(vdata.get("volume_1h_now"))
    vol_prev = _to_float_or_none(vdata.get("volume_1h_prev"))
    if vol_now is None or vol_prev is None or vol_prev <= 0:
        return None, None
    ratio = vol_now / vol_prev
    if ratio <= 0:
        return None, None
    vol_score = _clamp(math.log(ratio) / math.log(max(1.01, ratio_ref)), 0.0, 1.0)
    return ratio, vol_score


def _bucket_mag(value: float | None, step: float = 0.5) -> float:
    if value is None:
        return 0.0
    try:
        return round(abs(float(value)) / float(step)) * float(step)
    except Exception:
        return 0.0


def _cooldown_key(
    atype: AlertType, symbol: str, window: str, mag_bucket: float | None = None
) -> str:
    base = f"{atype.value}::{symbol}::{window}"
    if mag_bucket is None:
        return base
    return f"{base}::b{mag_bucket:g}"


def _percentile_rank(value: float, samples: list[float]) -> float:
    if not samples:
        return 0.0
    le = sum(1 for s in samples if s <= value)
    return le / float(len(samples))


def _product_id_for_symbol(symbol: str) -> str:
    sym = str(symbol or "").strip().upper()
    if not sym:
        return ""
    return sym if "-" in sym else f"{sym}-USD"


# ---------------------------------------------------------------------------
# Individual detectors (pure functions, no side effects)
# ---------------------------------------------------------------------------


def _detect_impulse_alerts(
    price_snapshot: dict[str, dict],
    state: AlertEngineState,
    thresholds: dict,
) -> list[dict]:
    """Detect MOONSHOT / CRATER / BREAKOUT / DUMP from price returns.

    Per symbol, picks the single strongest impulse window (max abs among 1m/3m)
    to avoid duplicate alerts for the same move.
    """
    alerts: list[dict] = []
    t = thresholds

    for sym, data in price_snapshot.items():
        price = data.get("price")
        if price is None:
            continue

        # Pick the single strongest window per symbol
        best_window = None
        best_change = None
        best_mag = 0.0

        for window, pct_key in [("1m", "pct_1m"), ("3m", "pct_3m")]:
            change = data.get(pct_key)
            if change is None:
                continue
            mag = abs(change)
            # Must at least cross breakout threshold to be a candidate
            break_thresh = t.get(f"breakout_{window}_pct", t["breakout_1m_pct"])
            if mag >= break_thresh and mag > best_mag:
                best_window = window
                best_change = change
                best_mag = mag

        if best_window is None:
            continue

        direction = "up" if best_change >= 0 else "down"
        moon_thresh = t.get(f"moonshot_{best_window}_pct", t["moonshot_1m_pct"])

        if best_mag >= moon_thresh:
            atype = AlertType.MOONSHOT if direction == "up" else AlertType.CRATER
            sev = AlertSeverity.CRITICAL
        else:
            atype = AlertType.BREAKOUT if direction == "up" else AlertType.DUMP
            sev = AlertSeverity.HIGH

        key = f"{atype.value}::{sym}"
        if not state.check_cooldown(
            key, t["cooldown_impulse"], best_mag, direction, t["dedupe_impulse"]
        ):
            continue

        alert = _make_alert(
            symbol=sym,
            alert_type=atype,
            severity=sev,
            title=f"{atype.value.upper()}: {sym}",
            message=f"{sym} moved {best_change:+.2f}% in {best_window}",
            direction=direction,
            evidence={
                "window": best_window,
                "pct": round(best_change, 2),
                "pct_1m": data.get("pct_1m"),
                "pct_3m": data.get("pct_3m"),
                "pct_1h": data.get("pct_1h"),
                "price": price,
            },
            ttl_minutes=t["ttl_impulse_min"],
        )
        alerts.append(alert)
        state.record_fire(key, best_mag, direction)

    return alerts


def _detect_whale_alerts(
    price_snapshot: dict[str, dict],
    volume_snapshot: dict[str, dict],
    minute_volumes: dict[str, list],
    state: AlertEngineState,
    thresholds: dict,
) -> list[dict]:
    """Detect WHALE_MOVE (aggregated flow spike, NOT single-trade whale).

    Uses per-minute candle z-score or hourly volume comparison.
    "Whale" = unusual aggregated volume surge detected from Coinbase candles.
    To detect actual single large trades, trade-level/L2 data would be needed.
    """
    alerts: list[dict] = []
    t = thresholds

    for sym, vdata in volume_snapshot.items():
        price_data = price_snapshot.get(sym, {})
        price = price_data.get("price", 0)
        pct_3m = price_data.get("pct_3m")
        vol1h_pct = vdata.get("volume_change_1h_pct")
        vol1h_now = vdata.get("volume_1h_now", 0)
        vol1h_prev = vdata.get("volume_1h_prev")
        baseline_ready = vdata.get("baseline_ready", False)

        product_id = sym if "-" in sym else f"{sym}-USD"
        mins_raw = minute_volumes.get(product_id, [])
        rows: list[dict] = []
        if isinstance(mins_raw, list) and mins_raw:
            # Normalize to chronological order so baseline/latest slicing is stable
            # regardless of incoming series orientation.
            rows = [m for m in mins_raw if isinstance(m, dict)]
            if rows:
                has_ts = any(_to_float_or_none(m.get("ts")) is not None for m in rows)
                if has_ts:
                    rows = sorted(
                        rows,
                        key=lambda m: _to_float_or_none(m.get("ts")) or 0.0,
                    )
                elif len(rows) >= 2:
                    v0 = _to_float_or_none(rows[0].get("vol")) or 0.0
                    v1 = _to_float_or_none(rows[1].get("vol")) or 0.0
                    # Fallback heuristic: keep existing order unless clearly newest-first.
                    if v0 and v1 and v0 > (v1 * 4.0):
                        rows = list(reversed(rows))

        # --- Mode 1: Per-minute z-score whale ---
        if len(rows) >= 15:
            latest = rows[-1]
            latest_vol = latest.get("vol", 0) or 0
            latest_close = latest.get("close", 0)
            latest_open = latest.get("open", 0)

            baseline_rows = rows[-61:-1]
            baseline_vols = [
                (m.get("vol", 0) or 0)
                for m in baseline_rows
                if (m.get("vol", 0) or 0) > 0
            ]
            if len(baseline_vols) < 10:
                baseline_vols = [
                    (m.get("vol", 0) or 0)
                    for m in rows[-61:-1]
                    if (m.get("vol", 0) or 0) > 0
                ]
            n = len(baseline_vols)
            if n >= 10:
                mean_vol = sum(baseline_vols) / n
                variance = sum((v - mean_vol) ** 2 for v in baseline_vols) / n
                std_vol = variance**0.5 if variance > 0 else 0
                z_vol = (latest_vol - mean_vol) / std_vol if std_vol > 0 else 0

                sorted_vols = sorted(baseline_vols)
                median_vol = sorted_vols[n // 2]
                vol_ratio = (latest_vol / median_vol) if median_vol > 0 else 0

                candle_pct = (
                    ((latest_close - latest_open) / latest_open * 100)
                    if latest_open > 0
                    else 0
                )

                # 3-candle cluster
                cluster_vol = (
                    sum((m.get("vol", 0) or 0) for m in rows[-3:])
                    if len(rows) >= 3
                    else latest_vol
                )
                cluster_z = (cluster_vol / 3 - mean_vol) / std_vol if std_vol > 0 else 0

                # WHALE MOVE: z >= 3.0 + price impact
                if (
                    z_vol >= t["whale_z_score"]
                    and abs(candle_pct) >= t["whale_candle_pct"]
                    and latest_vol > 100
                ) or (
                    cluster_z >= t["whale_cluster_z"]
                    and abs(candle_pct) >= 0.4
                    and cluster_vol > 300
                ):
                    direction = "up" if candle_pct > 0 else "down"
                    whale_score = z_vol * abs(candle_pct)
                    sev = (
                        AlertSeverity.CRITICAL
                        if z_vol >= 5.0 or whale_score >= 8
                        else AlertSeverity.HIGH
                    )
                    key = f"whale_move::{sym}"
                    if state.check_cooldown(
                        key,
                        t["cooldown_whale"],
                        whale_score,
                        direction,
                        t["dedupe_whale"],
                    ):
                        alert = _make_alert(
                            symbol=sym,
                            alert_type=AlertType.WHALE_MOVE,
                            severity=sev,
                            title=f"WHALE: {sym} flow spike",
                            message=f"{sym} {candle_pct:+.2f}% in 1m, vol {vol_ratio:.1f}x median ({z_vol:.1f}\u03c3)",
                            direction=direction,
                            evidence={
                                "window": "1m",
                                # Contract fields (always numeric-or-None)
                                "volume_change_1h_pct": _to_float_or_none(vol1h_pct),
                                "vol1h_now": _to_float_or_none(vol1h_now),
                                "vol1h_prev": _to_float_or_none(vol1h_prev),
                                "pct_3m": _to_float_or_none(pct_3m),
                                "z_vol": round(z_vol, 2),
                                "vol_ratio": round(vol_ratio, 2),
                                "candle_pct": round(candle_pct, 4),
                                "cluster_z": round(cluster_z, 2),
                                "latest_vol": round(latest_vol, 2),
                                "median_vol": round(median_vol, 2),
                                "price": price,
                                "baseline_ready": baseline_ready,
                            },
                            ttl_minutes=t["ttl_whale_min"],
                        )
                        alerts.append(alert)
                        state.record_fire(key, whale_score, direction)
                        continue  # don't double-fire

                # ABSORPTION: high vol, flat price
                if (
                    z_vol >= t["absorption_z"]
                    and abs(candle_pct) < t["absorption_max_pct"]
                    and latest_vol > 100
                ):
                    # Check repeat pattern
                    absorption_count = 0
                    for m in rows[-6:-1]:
                        m_vol = m.get("vol", 0) or 0
                        m_z = (m_vol - mean_vol) / std_vol if std_vol > 0 else 0
                        m_pct = (
                            (
                                (m.get("close", 0) - m.get("open", 1))
                                / m.get("open", 1)
                                * 100
                            )
                            if m.get("open", 0) > 0
                            else 0
                        )
                        if m_z >= 2.0 and abs(m_pct) < 0.2:
                            absorption_count += 1
                    if absorption_count >= t["absorption_min_pulses"]:
                        key = f"absorption::{sym}"
                        if state.check_cooldown(
                            key,
                            t["cooldown_absorption"],
                            z_vol,
                            "absorption",
                            t["dedupe_absorption"],
                        ):
                            alert = _make_alert(
                                symbol=sym,
                                alert_type=AlertType.WHALE_MOVE,
                                severity=AlertSeverity.MEDIUM,
                                title=f"WHALE ABSORPTION: {sym}",
                                message=f"{sym} heavy tape, price flat ({candle_pct:+.2f}%), vol {vol_ratio:.1f}x ({z_vol:.1f}\u03c3), {absorption_count + 1} pulses",
                                direction="absorption",
                                evidence={
                                    "window": "1m",
                                    # Contract fields (always numeric-or-None)
                                    "volume_change_1h_pct": _to_float_or_none(
                                        vol1h_pct
                                    ),
                                    "vol1h_now": _to_float_or_none(vol1h_now),
                                    "vol1h_prev": _to_float_or_none(vol1h_prev),
                                    "pct_3m": _to_float_or_none(pct_3m),
                                    "z_vol": round(z_vol, 2),
                                    "vol_ratio": round(vol_ratio, 2),
                                    "candle_pct": round(candle_pct, 4),
                                    "absorption_pulses": absorption_count + 1,
                                    "latest_vol": round(latest_vol, 2),
                                    "median_vol": round(median_vol, 2),
                                    "price": price,
                                    "baseline_ready": baseline_ready,
                                },
                                ttl_minutes=t["ttl_absorption_min"],
                            )
                            alerts.append(alert)
                            state.record_fire(key, z_vol, "absorption")
                            continue

        # --- Mode 2: Hourly volume surge fallback ---
        if vol1h_pct is not None and vol1h_pct >= t["whale_surge_1h_pct"]:
            if vol1h_now >= t["whale_min_abs_vol"]:
                sev = (
                    AlertSeverity.CRITICAL
                    if vol1h_pct >= 400
                    else (
                        AlertSeverity.HIGH if vol1h_pct >= 250 else AlertSeverity.MEDIUM
                    )
                )
                key = f"whale_surge::{sym}"
                if state.check_cooldown(
                    key,
                    t["cooldown_whale_surge"],
                    vol1h_pct,
                    "up",
                    t["dedupe_whale_surge"],
                ):
                    alert = _make_alert(
                        symbol=sym,
                        alert_type=AlertType.WHALE_MOVE,
                        severity=sev,
                        title=f"WHALE SURGE: {sym}",
                        message=f"{sym} 1h volume {vol1h_pct:+.0f}% vs prev hour ({vol1h_now:,.0f} units)",
                        direction="up",
                        evidence={
                            "window": "1h",
                            # Contract fields (always numeric-or-None)
                            "vol1h_now": _to_float_or_none(vol1h_now),
                            "vol1h_prev": _to_float_or_none(vol1h_prev),
                            "pct_3m": _to_float_or_none(pct_3m),
                            "volume_change_1h_pct": round(vol1h_pct, 1),
                            "volume_1h_now": round(vol1h_now, 2),
                            "volume_1h_prev": vdata.get("volume_1h_prev"),
                            "price": price,
                            "baseline_ready": baseline_ready,
                        },
                        ttl_minutes=t["ttl_whale_surge_min"],
                    )
                    alerts.append(alert)
                    state.record_fire(key, vol1h_pct, "up")

    return alerts


def _detect_stealth_alerts(
    price_snapshot: dict[str, dict],
    volume_snapshot: dict[str, dict],
    state: AlertEngineState,
    thresholds: dict,
) -> list[dict]:
    """Detect STEALTH_MOVE: aggregated flow spike + muted price (early smoke).

    Stealth = volume is screaming, price is whispering.
    This is the opposite of a breakout — someone is accumulating/distributing
    without moving the price. The most interesting early signal.
    """
    alerts: list[dict] = []
    t = thresholds

    for sym, vdata in volume_snapshot.items():
        if not vdata.get("baseline_ready", False):
            continue
        vol1h_pct = vdata.get("volume_change_1h_pct")
        vol1h_now = vdata.get("volume_1h_now")
        vol1h_prev = vdata.get("volume_1h_prev")
        if vol1h_pct is None:
            continue
        # Volume must be LOUD (above min threshold)
        if vol1h_pct < t["stealth_vol_min_pct"]:
            continue

        pdata = price_snapshot.get(sym, {})
        pct_3m = pdata.get("pct_3m")
        if pct_3m is None:
            continue
        # Price must be QUIET (below max threshold)
        if abs(pct_3m) > t["stealth_price_max_abs_pct"]:
            continue

        price = pdata.get("price", 0)
        magnitude = vol1h_pct  # score by how loud the volume is
        # Slight positive price = accumulation, slight negative = distribution
        direction = "accumulation" if pct_3m >= 0 else "distribution"

        key = f"stealth_move::{sym}"
        if not state.check_cooldown(
            key, t["cooldown_stealth"], magnitude, direction, t["dedupe_stealth"]
        ):
            continue

        alert = _make_alert(
            symbol=sym,
            alert_type=AlertType.STEALTH_MOVE,
            severity=AlertSeverity.MEDIUM,
            title=f"STEALTH: {sym} {direction}",
            message=f"{sym} vol {vol1h_pct:+.0f}% but price only {pct_3m:+.2f}% — quiet {direction}",
            direction=direction,
            evidence={
                "window": "3m",
                "volume_change_1h_pct": round(vol1h_pct, 1),
                "pct_3m": round(pct_3m, 2),
                "abs_pct_3m": round(abs(pct_3m), 2),
                "vol1h_now": _to_float_or_none(vol1h_now),
                "vol1h_prev": _to_float_or_none(vol1h_prev),
                "pct_1m": pdata.get("pct_1m"),
                "pct_1h": pdata.get("pct_1h"),
                "price": price,
                "baseline_ready": True,
            },
            ttl_minutes=t["ttl_stealth_min"],
        )
        alerts.append(alert)
        state.record_fire(key, magnitude, direction)

    return alerts


def _detect_divergence_alerts(
    price_snapshot: dict[str, dict],
    pressure: MarketPressure | None,
    state: AlertEngineState,
    thresholds: dict,
) -> list[dict]:
    """Detect DIVERGENCE: 1m vs 3m timeframe disagreement."""
    alerts: list[dict] = []
    t = thresholds
    thresh_1m = t["divergence_1m_threshold"]
    thresh_3m = t["divergence_3m_threshold"]

    for sym, data in price_snapshot.items():
        ret_1m = data.get("pct_1m")
        ret_3m = data.get("pct_3m")
        if ret_1m is None or ret_3m is None:
            continue

        # Opposite directions with magnitude
        if not (
            (ret_1m > thresh_1m and ret_3m < -thresh_3m)
            or (ret_1m < -thresh_1m and ret_3m > thresh_3m)
        ):
            continue

        magnitude = abs(ret_1m - ret_3m)
        if ret_1m > 0:
            direction = "reversal_up"
            msg = f"{sym}: 1m up {ret_1m:+.2f}% but 3m down {ret_3m:+.2f}% — possible reversal"
        else:
            direction = "reversal_down"
            msg = f"{sym}: 1m down {ret_1m:+.2f}% but 3m up {ret_3m:+.2f}% — possible pullback"

        key = f"divergence::{sym}"
        if not state.check_cooldown(
            key, t["cooldown_divergence"], magnitude, direction, t["dedupe_divergence"]
        ):
            continue

        price = data.get("price", 0)
        alert = _make_alert(
            symbol=sym,
            alert_type=AlertType.DIVERGENCE,
            severity=AlertSeverity.MEDIUM,
            title=f"DIVERGENCE: {sym}",
            message=msg,
            direction=direction,
            evidence={
                "window": "1m_vs_3m",
                "pct_1m": round(ret_1m, 4),
                "pct_3m": round(ret_3m, 4),
                "pct_1h": data.get("pct_1h"),
                "magnitude": round(magnitude, 2),
                "heat": _to_float_or_none(pressure.heat if pressure else None),
                "breadth_up": _to_float_or_none(
                    pressure.breadth_up if pressure else None
                ),
                "breadth_down": _to_float_or_none(
                    pressure.breadth_down if pressure else None
                ),
                "price": price,
            },
            ttl_minutes=t["ttl_divergence_min"],
        )
        alerts.append(alert)
        state.record_fire(key, magnitude, direction)

    return alerts


def _detect_coin_reversal_alerts(
    price_snapshot: dict[str, dict],
    state: AlertEngineState,
    thresholds: dict,
) -> list[dict]:
    """Detect coin reversals: strong 3m move that flips direction on 1m."""
    alerts: list[dict] = []
    t = thresholds
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    for sym, data in (price_snapshot or {}).items():
        pct_1m = _to_float_or_none((data or {}).get("pct_1m"))
        pct_3m = _to_float_or_none((data or {}).get("pct_3m"))
        if pct_1m is None or pct_3m is None:
            continue
        if abs(pct_3m) < float(t.get("reversal_min_prev_pct", 2.0) or 2.0):
            continue
        if abs(pct_1m) < float(t.get("reversal_min_flip_pct", 0.6) or 0.6):
            continue
        if pct_3m >= 0 and pct_1m >= 0:
            continue
        if pct_3m <= 0 and pct_1m <= 0:
            continue

        direction = "down" if pct_1m < 0 else "up"
        atype = (
            AlertType.COIN_REVERSAL_DOWN
            if direction == "down"
            else AlertType.COIN_REVERSAL_UP
        )
        mag_bucket = _bucket_mag(pct_1m, 0.5)
        magnitude = abs(pct_1m)
        key = _cooldown_key(atype, sym, "1m", mag_bucket)
        if not state.check_cooldown(
            key, t["cooldown_reversal"], magnitude, direction, t["dedupe_reversal"]
        ):
            continue

        alert = _make_alert(
            symbol=sym,
            alert_type=atype,
            severity=AlertSeverity.HIGH if magnitude >= 1.5 else AlertSeverity.MEDIUM,
            title=f"REVERSAL: {sym}",
            message=f"{sym} flipped {pct_1m:+.2f}% in 1m after {pct_3m:+.2f}% over 3m",
            direction=direction,
            evidence={
                "window": "1m",
                "pct_1m": round(pct_1m, 4),
                "pct_3m": round(pct_3m, 4),
                "price_now": _to_float_or_none((data or {}).get("price")),
                "price_ref": _to_float_or_none((data or {}).get("price_3m_ago")),
                "turn_ts_ms": now_ms,
                "event_kind": "reversal",
                "magnitude_bucket": mag_bucket,
            },
            ttl_minutes=t["ttl_reversal_min"],
        )
        alerts.append(alert)
        state.record_fire(key, magnitude, direction)

    return alerts


def _detect_coin_fakeout_alerts(
    price_snapshot: dict[str, dict],
    state: AlertEngineState,
    thresholds: dict,
) -> list[dict]:
    """Detect fakeouts: strong 3m push immediately rejected on 1m."""
    alerts: list[dict] = []
    t = thresholds

    for sym, data in (price_snapshot or {}).items():
        pct_1m = _to_float_or_none((data or {}).get("pct_1m"))
        pct_3m = _to_float_or_none((data or {}).get("pct_3m"))
        if pct_1m is None or pct_3m is None:
            continue
        if abs(pct_3m) < float(t.get("fakeout_min_breakout_pct", 2.0) or 2.0):
            continue
        if abs(pct_1m) < float(t.get("fakeout_min_reject_pct", 0.8) or 0.8):
            continue
        if pct_3m >= 0 and pct_1m >= 0:
            continue
        if pct_3m <= 0 and pct_1m <= 0:
            continue

        direction = "down" if pct_1m < 0 else "up"
        mag_bucket = _bucket_mag(pct_1m, 0.5)
        magnitude = abs(pct_1m)
        key = _cooldown_key(AlertType.COIN_FAKEOUT, sym, "1m", mag_bucket)
        if not state.check_cooldown(
            key, t["cooldown_fakeout"], magnitude, direction, t["dedupe_fakeout"]
        ):
            continue

        alert = _make_alert(
            symbol=sym,
            alert_type=AlertType.COIN_FAKEOUT,
            severity=AlertSeverity.HIGH if magnitude >= 1.5 else AlertSeverity.MEDIUM,
            title=f"FAKEOUT: {sym}",
            message=f"{sym} rejected {pct_1m:+.2f}% in 1m after {pct_3m:+.2f}% over 3m",
            direction=direction,
            evidence={
                "window": "1m",
                "pct_1m": round(pct_1m, 4),
                "pct_3m": round(pct_3m, 4),
                "price_now": _to_float_or_none((data or {}).get("price")),
                "price_ref": _to_float_or_none((data or {}).get("price_3m_ago")),
                "reason": "breakout_rejection",
                "event_kind": "fakeout",
                "magnitude_bucket": mag_bucket,
            },
            ttl_minutes=t["ttl_fakeout_min"],
        )
        alerts.append(alert)
        state.record_fire(key, magnitude, direction)

    return alerts


def _detect_coin_persistence_alerts(
    price_snapshot: dict[str, dict],
    state: AlertEngineState,
    thresholds: dict,
) -> list[dict]:
    """Detect persistent gainers/losers from consecutive 3m-direction streaks."""
    alerts: list[dict] = []
    t = thresholds
    streaks = state.coin_persistence_streaks
    min_pct = float(t.get("persist_min_pct", 1.5) or 1.5)
    min_streak = int(t.get("persist_min_streak", 4) or 4)

    if not price_snapshot:
        streaks.clear()
        return alerts

    gainers: list[tuple[str, float]] = []
    losers: list[tuple[str, float]] = []
    active_symbols: set[str] = set()
    for sym, data in (price_snapshot or {}).items():
        pct_3m = _to_float_or_none((data or {}).get("pct_3m"))
        if pct_3m is None:
            streaks.pop(sym, None)
            continue
        if pct_3m >= min_pct:
            active_symbols.add(sym)
            gainers.append((sym, pct_3m))
            prev_n, prev_dir = streaks.get(sym, (0, ""))
            streaks[sym] = (prev_n + 1, "up") if prev_dir == "up" else (1, "up")
        elif pct_3m <= -min_pct:
            active_symbols.add(sym)
            losers.append((sym, pct_3m))
            prev_n, prev_dir = streaks.get(sym, (0, ""))
            streaks[sym] = (prev_n + 1, "down") if prev_dir == "down" else (1, "down")
        else:
            streaks.pop(sym, None)

    # Prune symbols that disappeared from the snapshot universe.
    for sym in list(streaks.keys()):
        if sym not in price_snapshot:
            streaks.pop(sym, None)

    gainers.sort(key=lambda item: item[1], reverse=True)
    losers.sort(key=lambda item: item[1])
    gain_rank = {sym: idx + 1 for idx, (sym, _pct) in enumerate(gainers)}
    lose_rank = {sym: idx + 1 for idx, (sym, _pct) in enumerate(losers)}

    for sym in active_symbols:
        streak_n, direction = streaks.get(sym, (0, ""))
        if streak_n < min_streak:
            continue
        pct_3m = _to_float_or_none((price_snapshot.get(sym) or {}).get("pct_3m"))
        if pct_3m is None:
            continue
        atype = (
            AlertType.COIN_PERSISTENT_GAINER
            if direction == "up"
            else AlertType.COIN_PERSISTENT_LOSER
        )
        rank = gain_rank.get(sym) if direction == "up" else lose_rank.get(sym)
        magnitude = abs(pct_3m) + float(streak_n)
        mag_bucket = _bucket_mag(pct_3m, 0.5)
        key = _cooldown_key(atype, sym, "3m", mag_bucket)
        if not state.check_cooldown(
            key, t["cooldown_persist"], magnitude, direction, t["dedupe_persist"]
        ):
            continue

        alert = _make_alert(
            symbol=sym,
            alert_type=atype,
            severity=(
                AlertSeverity.HIGH
                if streak_n >= (min_streak + 2)
                else AlertSeverity.MEDIUM
            ),
            title=f"PERSISTENCE: {sym}",
            message=f"{sym} stayed {direction} for {streak_n} cycles ({pct_3m:+.2f}% in 3m)",
            direction=direction,
            evidence={
                "window": "3m",
                "streak": streak_n,
                "rank": rank,
                "pct_3m": round(pct_3m, 4),
                "polls": streak_n,
                "event_kind": "persistence",
                "magnitude_bucket": mag_bucket,
                "price_now": _to_float_or_none(
                    (price_snapshot.get(sym) or {}).get("price")
                ),
            },
            ttl_minutes=t["ttl_persist_min"],
        )
        alerts.append(alert)
        state.record_fire(key, magnitude, direction)

    return alerts


def _detect_coin_volatility_expansion_alerts(
    price_snapshot: dict[str, dict],
    state: AlertEngineState,
    thresholds: dict,
) -> list[dict]:
    """Detect realized-vol expansion vs recent baseline for each coin."""
    alerts: list[dict] = []
    t = thresholds

    n_now = max(2, int(t.get("volx_window_now", 10) or 10))
    n_prev = max(2, int(t.get("volx_window_prev", 20) or 20))
    ratio_min = float(t.get("volx_ratio_min", 2.0) or 2.0)
    vol_floor = float(t.get("volx_vol_floor", 0.25) or 0.25)
    prev_floor = float(t.get("volx_prev_floor", 0.05) or 0.05)
    keep = max(120, (n_now + n_prev + 60))

    for sym, hist in list(state.coin_return_hist.items()):
        if sym not in price_snapshot:
            if len(hist) > keep:
                del hist[: len(hist) - keep]
            continue

        if len(hist) < (n_now + n_prev):
            continue
        now_vals = hist[-n_now:]
        prev_vals = hist[-(n_now + n_prev) : -n_now]
        if len(prev_vals) < n_prev:
            continue

        vol_now = _stddev(now_vals)
        vol_prev = _stddev(prev_vals)
        if vol_now < vol_floor or vol_prev < prev_floor:
            continue

        ratio = vol_now / max(vol_prev, 1e-9)
        if ratio < ratio_min:
            continue

        pdata = price_snapshot.get(sym) or {}
        mag_bucket = _bucket_mag(ratio, 0.5)
        key = _cooldown_key(AlertType.COIN_VOLATILITY_EXPANSION, sym, "10m", mag_bucket)
        direction = (
            "up" if (_to_float_or_none(pdata.get("pct_1m")) or 0.0) >= 0 else "down"
        )
        if not state.check_cooldown(
            key,
            t["cooldown_volx"],
            ratio,
            direction,
            t["dedupe_volx"],
        ):
            continue

        sev = AlertSeverity.HIGH if ratio >= (ratio_min + 1.0) else AlertSeverity.MEDIUM
        alert = _make_alert(
            symbol=sym,
            alert_type=AlertType.COIN_VOLATILITY_EXPANSION,
            severity=sev,
            title=f"VOL EXPANSION: {sym}",
            message=f"{sym} volatility expanded {ratio:.2f}x vs baseline",
            direction=direction,
            evidence={
                "window": "10m",
                "vol_ratio": round(ratio, 4),
                "vol_now": round(vol_now, 4),
                "vol_prev": round(vol_prev, 4),
                "pct_1m": _to_float_or_none(pdata.get("pct_1m")),
                "pct_3m": _to_float_or_none(pdata.get("pct_3m")),
                "pct_1h": _to_float_or_none(pdata.get("pct_1h")),
                "price": _to_float_or_none(pdata.get("price")),
                "samples_now": len(now_vals),
                "samples_prev": len(prev_vals),
            },
            ttl_minutes=t["ttl_volx_min"],
        )
        alerts.append(alert)
        state.record_fire(key, ratio, direction)

    return alerts


def _detect_coin_liquidity_shock_alerts(
    price_snapshot: dict[str, dict],
    volume_snapshot: dict[str, dict],
    minute_volumes: dict[str, list],
    state: AlertEngineState,
    thresholds: dict,
) -> list[dict]:
    """Detect coin minute-volume spikes while price remains muted."""
    alerts: list[dict] = []
    t = thresholds

    z_min = float(t.get("liq_shock_z_min", 3.0) or 3.0)
    price_cap = float(t.get("liq_shock_price_max_abs_pct", 0.25) or 0.25)
    min_samples = max(10, int(t.get("liq_shock_min_samples", 30) or 30))
    min_latest_vol = float(t.get("liq_shock_min_latest_vol", 50.0) or 50.0)

    for product_id, rows in (minute_volumes or {}).items():
        if not isinstance(rows, list) or len(rows) < (min_samples + 1):
            continue
        latest = rows[0] if rows else {}
        latest_vol = _to_float_or_none((latest or {}).get("vol"))
        if latest_vol is None or latest_vol < min_latest_vol:
            continue

        baseline_vals = [
            _to_float_or_none((m or {}).get("vol")) for m in rows[1 : min_samples + 1]
        ]
        baseline = [float(v) for v in baseline_vals if v is not None and v > 0]
        if len(baseline) < min_samples:
            continue

        base_mean = sum(baseline) / float(len(baseline))
        base_std = _stddev(baseline)
        if base_std <= 0:
            continue

        vol_z = (latest_vol - base_mean) / base_std
        if vol_z < z_min:
            continue

        sym_guess = str(product_id or "").upper()
        base_sym = sym_guess.split("-")[0] if "-" in sym_guess else sym_guess
        symbol_key = (
            sym_guess
            if sym_guess in price_snapshot
            else (base_sym if base_sym in price_snapshot else f"{base_sym}-USD")
        )
        pdata = price_snapshot.get(symbol_key) or {}
        vdata = volume_snapshot.get(symbol_key) or volume_snapshot.get(base_sym) or {}
        pct_1m = _to_float_or_none(pdata.get("pct_1m"))
        if pct_1m is None or abs(pct_1m) > price_cap:
            continue

        direction = "up" if pct_1m >= 0 else "down"
        mag_bucket = _bucket_mag(vol_z, 0.5)
        key = _cooldown_key(
            AlertType.COIN_LIQUIDITY_SHOCK, symbol_key, "1m", mag_bucket
        )
        if not state.check_cooldown(
            key,
            t["cooldown_liq_shock"],
            vol_z,
            direction,
            t["dedupe_liq_shock"],
        ):
            continue

        sev = AlertSeverity.HIGH if vol_z >= (z_min + 2.0) else AlertSeverity.MEDIUM
        alert = _make_alert(
            symbol=symbol_key,
            alert_type=AlertType.COIN_LIQUIDITY_SHOCK,
            severity=sev,
            title=f"LIQUIDITY SHOCK: {symbol_key}",
            message=f"{symbol_key} volume spiked {vol_z:.1f}σ with muted price ({pct_1m:+.2f}% 1m)",
            direction=direction,
            evidence={
                "window": "1m",
                "vol_z": round(vol_z, 4),
                "vol_1m": round(latest_vol, 4),
                "avg_1m": round(base_mean, 4),
                "std_1m": round(base_std, 4),
                "pct_1m": pct_1m,
                "pct_3m": _to_float_or_none(pdata.get("pct_3m")),
                "price": _to_float_or_none(pdata.get("price")),
                "volume_change_1h_pct": _to_float_or_none(
                    vdata.get("volume_change_1h_pct")
                ),
                "baseline_samples": len(baseline),
            },
            ttl_minutes=t["ttl_liq_shock_min"],
        )
        alerts.append(alert)
        state.record_fire(key, vol_z, direction)

    return alerts


def _detect_coin_trend_break_alerts(
    price_snapshot: dict[str, dict],
    volume_snapshot: dict[str, dict],
    state: AlertEngineState,
    thresholds: dict,
) -> list[dict]:
    """Detect micro-structure trend breaks via EMA fast/slow crossover on 1m returns."""
    alerts: list[dict] = []
    t = thresholds

    alpha_fast = _clamp(
        float(t.get("trend_break_fast_alpha", 0.3333) or 0.3333), 0.01, 1.0
    )
    alpha_slow = _clamp(
        float(t.get("trend_break_slow_alpha", 0.0952) or 0.0952), 0.01, 1.0
    )
    min_diff = float(t.get("trend_break_min_abs_diff", 0.08) or 0.08)
    vol_confirm_pct = float(t.get("trend_break_vol_confirm_pct", 10.0) or 10.0)
    vol_ratio_min = float(t.get("trend_break_vol_ratio_min", 1.20) or 1.20)
    ratio_ref = float(t.get("pressure_vol_ratio_ref", 5.0) or 5.0)

    for sym, pdata in (price_snapshot or {}).items():
        pct_1m = _to_float_or_none((pdata or {}).get("pct_1m"))
        if pct_1m is None:
            continue

        prev_fast = state.coin_trend_ema_fast.get(sym, pct_1m)
        prev_slow = state.coin_trend_ema_slow.get(sym, pct_1m)
        prev_diff = state.coin_trend_last_diff.get(sym, prev_fast - prev_slow)

        ema_fast = (alpha_fast * pct_1m) + ((1.0 - alpha_fast) * prev_fast)
        ema_slow = (alpha_slow * pct_1m) + ((1.0 - alpha_slow) * prev_slow)
        diff = ema_fast - ema_slow

        state.coin_trend_ema_fast[sym] = ema_fast
        state.coin_trend_ema_slow[sym] = ema_slow
        state.coin_trend_last_diff[sym] = diff

        crossed_up = prev_diff <= -min_diff and diff >= min_diff
        crossed_down = prev_diff >= min_diff and diff <= -min_diff
        if not crossed_up and not crossed_down:
            continue

        vdata = volume_snapshot.get(sym) or volume_snapshot.get(sym.split("-")[0]) or {}
        vol_ratio, _vol_score = _compute_vol_ratio(vdata, ratio_ref)
        vol1h_pct = _to_float_or_none(vdata.get("volume_change_1h_pct"))
        vol_confirmed = (vol1h_pct is not None and vol1h_pct >= vol_confirm_pct) or (
            vol_ratio is not None and vol_ratio >= vol_ratio_min
        )
        if not vol_confirmed:
            continue

        direction = "up" if crossed_up else "down"
        atype = (
            AlertType.COIN_TREND_BREAK_UP
            if crossed_up
            else AlertType.COIN_TREND_BREAK_DOWN
        )
        magnitude = abs(diff)
        key = _cooldown_key(atype, sym, "5m_vs_20m", _bucket_mag(diff, 0.05))
        if not state.check_cooldown(
            key,
            t["cooldown_trend_break"],
            magnitude,
            direction,
            t["dedupe_trend_break"],
        ):
            continue

        sev = (
            AlertSeverity.HIGH
            if (
                magnitude >= (2.0 * min_diff)
                and (vol_ratio or 0.0) >= (vol_ratio_min + 0.3)
            )
            else AlertSeverity.MEDIUM
        )
        alert = _make_alert(
            symbol=sym,
            alert_type=atype,
            severity=sev,
            title=f"TREND BREAK {direction.upper()}: {sym}",
            message=f"{sym} EMA fast/slow crossover with volume support",
            direction=direction,
            evidence={
                "window": "5m_vs_20m",
                "ema_fast": round(ema_fast, 6),
                "ema_slow": round(ema_slow, 6),
                "cross_dir": direction,
                "diff": round(diff, 6),
                "prev_diff": round(prev_diff, 6),
                "pct_1m": pct_1m,
                "pct_3m": _to_float_or_none((pdata or {}).get("pct_3m")),
                "pct_1h": _to_float_or_none((pdata or {}).get("pct_1h")),
                "vol_ratio": round(vol_ratio, 4) if vol_ratio is not None else None,
                "volume_change_1h_pct": vol1h_pct,
                "price": _to_float_or_none((pdata or {}).get("price")),
            },
            ttl_minutes=t["ttl_trend_break_min"],
        )
        alerts.append(alert)
        state.record_fire(key, magnitude, direction)

    return alerts


def _detect_coin_squeeze_break_alerts(
    price_snapshot: dict[str, dict],
    state: AlertEngineState,
    thresholds: dict,
) -> list[dict]:
    """Detect compression regime that breaks into a sharp move."""
    alerts: list[dict] = []
    t = thresholds

    window_n = max(3, int(t.get("squeeze_window_n", 10) or 10))
    hist_n = max(window_n * 3, int(t.get("squeeze_hist_n", 120) or 120))
    compress_pctile = _clamp(
        float(t.get("squeeze_compress_percentile", 0.25) or 0.25), 0.01, 0.95
    )
    break_pct_min = float(t.get("squeeze_break_pct_1m_min", 0.8) or 0.8)
    vol_jump_min = float(t.get("squeeze_break_vol_ratio_min", 1.6) or 1.6)

    for sym, pdata in (price_snapshot or {}).items():
        hist = state.coin_return_hist.get(sym) or []
        if len(hist) < (window_n * 3):
            continue

        pct_1m = _to_float_or_none((pdata or {}).get("pct_1m"))
        if pct_1m is None:
            continue

        now_vals = hist[-window_n:]
        prev_vals = hist[-(2 * window_n) : -window_n]
        if len(prev_vals) < window_n:
            continue

        vol_now = _stddev(now_vals)
        vol_prev = _stddev(prev_vals)
        if vol_prev <= 0:
            continue
        vol_jump_ratio = vol_now / max(vol_prev, 1e-9)

        # Compression percentile is measured on the prior window (before the break).
        hist_end = len(hist) - window_n
        hist_start = max(window_n, hist_end - hist_n)
        vol_hist: list[float] = []
        for end in range(hist_start + window_n, hist_end + 1):
            v = _stddev(hist[end - window_n : end])
            if v > 0:
                vol_hist.append(v)
        if not vol_hist:
            continue
        vol_percentile = _percentile_rank(vol_prev, vol_hist)

        compression = vol_percentile <= compress_pctile
        break_move = abs(pct_1m) >= break_pct_min
        if not (compression and break_move and vol_jump_ratio >= vol_jump_min):
            continue

        direction = "up" if pct_1m >= 0 else "down"
        magnitude = abs(pct_1m) + vol_jump_ratio
        key = _cooldown_key(
            AlertType.COIN_SQUEEZE_BREAK, sym, "10m", _bucket_mag(pct_1m, 0.5)
        )
        if not state.check_cooldown(
            key,
            t["cooldown_squeeze_break"],
            magnitude,
            direction,
            t["dedupe_squeeze_break"],
        ):
            continue

        sev = (
            AlertSeverity.HIGH
            if (
                abs(pct_1m) >= (break_pct_min * 1.8)
                or vol_jump_ratio >= (vol_jump_min * 1.5)
            )
            else AlertSeverity.MEDIUM
        )
        alert = _make_alert(
            symbol=sym,
            alert_type=AlertType.COIN_SQUEEZE_BREAK,
            severity=sev,
            title=f"SQUEEZE BREAK: {sym}",
            message=f"{sym} broke from compression with {pct_1m:+.2f}% 1m move",
            direction=direction,
            evidence={
                "window": "10m",
                "vol_10m": round(vol_now, 6),
                "vol_prev_10m": round(vol_prev, 6),
                "vol_jump_ratio": round(vol_jump_ratio, 4),
                "vol_percentile": round(vol_percentile, 4),
                "break_change_1m": round(pct_1m, 4),
                "pct_3m": _to_float_or_none((pdata or {}).get("pct_3m")),
                "pct_1h": _to_float_or_none((pdata or {}).get("pct_1h")),
                "price": _to_float_or_none((pdata or {}).get("price")),
            },
            ttl_minutes=t["ttl_squeeze_break_min"],
        )
        alerts.append(alert)
        state.record_fire(key, magnitude, direction)

    return alerts


def _detect_coin_exhaustion_alerts(
    price_snapshot: dict[str, dict],
    volume_snapshot: dict[str, dict],
    state: AlertEngineState,
    thresholds: dict,
    fakeout_symbols: set[str] | None = None,
) -> list[dict]:
    """Detect exhaustion after persistent directional runs."""
    alerts: list[dict] = []
    t = thresholds
    fakeout_symbols = {str(s or "").upper() for s in (fakeout_symbols or set())}

    min_streak = int(t.get("exhaustion_min_streak", 4) or 4)
    flip_pct_1m = float(t.get("exhaustion_flip_pct_1m", 0.6) or 0.6)
    context_pct_3m = float(t.get("exhaustion_context_pct_3m", 1.0) or 1.0)
    vol_drop_ratio = _clamp(
        float(t.get("exhaustion_vol_drop_ratio", 0.20) or 0.20), 0.01, 0.95
    )
    ratio_ref = float(t.get("pressure_vol_ratio_ref", 5.0) or 5.0)

    for sym, pdata in (price_snapshot or {}).items():
        streak_n, streak_dir = state.coin_persistence_streaks.get(sym, (0, ""))
        pct_1m = _to_float_or_none((pdata or {}).get("pct_1m"))
        pct_3m = _to_float_or_none((pdata or {}).get("pct_3m"))
        if pct_1m is None or pct_3m is None:
            continue

        vdata = volume_snapshot.get(sym) or volume_snapshot.get(sym.split("-")[0]) or {}
        vol_ratio, _vol_score = _compute_vol_ratio(vdata, ratio_ref)
        prev_vol_ratio = state.coin_last_vol_ratio.get(sym)
        if vol_ratio is not None:
            state.coin_last_vol_ratio[sym] = vol_ratio

        if streak_n < min_streak:
            continue

        if streak_dir == "up":
            flipped = pct_1m <= -flip_pct_1m and pct_3m >= context_pct_3m
            atype = AlertType.COIN_EXHAUSTION_TOP
            direction = "down"
        elif streak_dir == "down":
            flipped = pct_1m >= flip_pct_1m and pct_3m <= -context_pct_3m
            atype = AlertType.COIN_EXHAUSTION_BOTTOM
            direction = "up"
        else:
            continue
        if not flipped:
            continue

        product_id = _product_id_for_symbol(sym)
        fakeout_hit = sym.upper() in fakeout_symbols or product_id in fakeout_symbols
        volume_drop = (
            vol_ratio is not None
            and prev_vol_ratio is not None
            and prev_vol_ratio > 0
            and vol_ratio <= (prev_vol_ratio * (1.0 - vol_drop_ratio))
        )
        if not (fakeout_hit or volume_drop):
            continue

        magnitude = (
            abs(pct_1m) + (0.25 * float(streak_n)) + (0.5 if fakeout_hit else 0.0)
        )
        key = _cooldown_key(atype, sym, "1m", _bucket_mag(pct_1m, 0.5))
        if not state.check_cooldown(
            key,
            t["cooldown_exhaustion"],
            magnitude,
            direction,
            t["dedupe_exhaustion"],
        ):
            continue

        sev = (
            AlertSeverity.HIGH
            if (streak_n >= (min_streak + 2) or fakeout_hit)
            else AlertSeverity.MEDIUM
        )
        alert = _make_alert(
            symbol=sym,
            alert_type=atype,
            severity=sev,
            title=f"EXHAUSTION: {sym}",
            message=f"{sym} run exhausted after {streak_n} streak cycles ({pct_1m:+.2f}% 1m flip)",
            direction=direction,
            evidence={
                "window": "1m",
                "streak_len": streak_n,
                "flip": round(pct_1m, 4),
                "pct_1m": round(pct_1m, 4),
                "pct_3m": round(pct_3m, 4),
                "volume_ratio": round(vol_ratio, 4) if vol_ratio is not None else None,
                "prev_volume_ratio": (
                    round(prev_vol_ratio, 4) if prev_vol_ratio is not None else None
                ),
                "volume_drop": bool(volume_drop),
                "fakeout_hit": bool(fakeout_hit),
                "price": _to_float_or_none((pdata or {}).get("price")),
            },
            ttl_minutes=t["ttl_exhaustion_min"],
        )
        alerts.append(alert)
        state.record_fire(key, magnitude, direction)

    # Prune stale volume-ratio state for symbols no longer present.
    live = set(price_snapshot.keys())
    for sym in list(state.coin_last_vol_ratio.keys()):
        if sym not in live:
            state.coin_last_vol_ratio.pop(sym, None)

    return alerts


def _detect_coin_mood_alerts(
    price_snapshot: dict[str, dict],
    volume_snapshot: dict[str, dict],
    pressure: MarketPressure,
    state: AlertEngineState,
    thresholds: dict,
) -> list[dict]:
    """Detect coin-scoped mood alerts using market context, never MARKET symbol."""
    alerts: list[dict] = []
    t = thresholds

    breadth = _clamp(
        _to_float_or_none((pressure.components or {}).get("breadth")) or 0.0, 0.0, 1.0
    )
    persistence = _clamp(
        _to_float_or_none((pressure.components or {}).get("persistence")) or 0.0,
        0.0,
        1.0,
    )
    vol_regime = _clamp(
        _to_float_or_none((pressure.components or {}).get("vol_regime")) or 0.0,
        0.0,
        1.0,
    )
    mpi_index = float(pressure.index if pressure.index is not None else pressure.heat)
    mpi_delta_60s = _pressure_delta_seconds(state, 60)

    ratio_ref = float(t.get("pressure_vol_ratio_ref", 5.0) or 5.0)
    returns_3m = [
        r
        for r in (
            _to_float_or_none((pdata or {}).get("pct_3m"))
            for pdata in (price_snapshot or {}).values()
        )
        if r is not None
    ]
    median_pct_3m = _median(returns_3m)
    if not price_snapshot:
        return alerts

    for sym, pdata in price_snapshot.items():
        pct_1m = _to_float_or_none((pdata or {}).get("pct_1m"))
        pct_3m = _to_float_or_none((pdata or {}).get("pct_3m"))
        pct_1h = _to_float_or_none((pdata or {}).get("pct_1h"))
        price = _to_float_or_none((pdata or {}).get("price"))
        if pct_3m is None:
            continue

        vdata = volume_snapshot.get(sym) or {}
        vol_ratio, vol_score = _compute_vol_ratio(vdata, ratio_ref)
        rs3m = pct_3m - median_pct_3m

        accel = None
        if pct_1m is not None:
            denom = max(abs(pct_3m) / 3.0, 1e-9)
            accel = pct_1m / denom

        # Skip coin mood alerts when market volatility regime is effectively dead.
        if vol_regime < float(t.get("vol_regime_min", 0.20) or 0.20):
            continue

        # 1) COIN_FOMO: coin acceleration + volume confirmation in hot/accelerating market.
        fomo_rule = (
            pct_1m is not None
            and accel is not None
            and mpi_index >= float(t.get("coin_fomo_mpi_min", 72) or 72)
            and mpi_delta_60s >= float(t.get("coin_fomo_d_mpi_60s", 6.0) or 6.0)
            and pct_3m >= float(t.get("coin_fomo_pct3m_min", 2.2) or 2.2)
            and pct_1m >= float(t.get("coin_fomo_pct1m_min", 0.6) or 0.6)
            and accel >= float(t.get("coin_fomo_accel_min", 0.9) or 0.9)
            and (
                (
                    vol_ratio is not None
                    and vol_ratio >= float(t.get("vol_ratio_fomo", 2.0) or 2.0)
                )
                or (
                    vol_score is not None
                    and vol_score >= float(t.get("vol_score_mid", 0.60) or 0.60)
                )
            )
        )
        if fomo_rule:
            sev = (
                AlertSeverity.HIGH
                if pct_3m >= 3.5 or (vol_ratio is not None and vol_ratio >= 3.0)
                else AlertSeverity.MEDIUM
            )
            magnitude = max(0.0, pct_3m) + max(0.0, mpi_delta_60s)
            if vol_ratio is not None:
                magnitude += max(0.0, vol_ratio - 1.0)
            key = f"{AlertType.COIN_FOMO.value}::{sym}"
            if state.check_cooldown(
                key, t["cooldown_coin_fomo"], magnitude, "up", t["dedupe_coin_fomo"]
            ):
                alert = _make_alert(
                    symbol=sym,
                    alert_type=AlertType.COIN_FOMO,
                    severity=sev,
                    title=f"COIN FOMO: {sym}",
                    message=f"{sym} accelerating with volume confirmation ({pct_3m:+.2f}% 3m, MPI {mpi_index:.0f})",
                    direction="up",
                    evidence={
                        "window": "3m",
                        "pct_1m": pct_1m,
                        "pct_3m": pct_3m,
                        "pct_1h": pct_1h,
                        "rs3m": round(rs3m, 4),
                        "accel": round(accel, 4) if accel is not None else None,
                        "vol_ratio": (
                            round(vol_ratio, 4) if vol_ratio is not None else None
                        ),
                        "vol_score": (
                            round(vol_score, 4) if vol_score is not None else None
                        ),
                        "mpi_index": round(mpi_index, 2),
                        "mpi_delta_60s": round(mpi_delta_60s, 2),
                        "breadth": round(breadth, 4),
                        "persistence": round(persistence, 4),
                        "vol_regime": round(vol_regime, 4),
                        "price": price,
                    },
                    ttl_minutes=t["ttl_coin_mood_min"],
                )
                alerts.append(alert)
                state.record_fire(key, magnitude, "up")

        # 2) COIN_BREADTH_THRUST: broad strength + coin outperformance.
        thrust_rule = (
            breadth >= float(t.get("coin_thrust_breadth_min", 0.65) or 0.65)
            and pct_3m >= float(t.get("coin_thrust_pct3m_min", 1.6) or 1.6)
            and rs3m >= float(t.get("coin_thrust_rs3m_min", 0.8) or 0.8)
            and persistence >= float(t.get("coin_thrust_persist_min", 0.35) or 0.35)
        )
        if thrust_rule:
            sev = (
                AlertSeverity.HIGH
                if rs3m >= 1.6 or pct_3m >= 2.8
                else AlertSeverity.MEDIUM
            )
            magnitude = max(0.0, rs3m) + max(0.0, pct_3m)
            key = f"{AlertType.COIN_BREADTH_THRUST.value}::{sym}"
            if state.check_cooldown(
                key, t["cooldown_coin_thrust"], magnitude, "up", t["dedupe_coin_thrust"]
            ):
                alert = _make_alert(
                    symbol=sym,
                    alert_type=AlertType.COIN_BREADTH_THRUST,
                    severity=sev,
                    title=f"BREADTH THRUST: {sym}",
                    message=f"{sym} outrunning market breadth ({pct_3m:+.2f}% 3m, RS {rs3m:+.2f})",
                    direction="up",
                    evidence={
                        "window": "3m",
                        "pct_1m": pct_1m,
                        "pct_3m": pct_3m,
                        "pct_1h": pct_1h,
                        "rs3m": round(rs3m, 4),
                        "breadth": round(breadth, 4),
                        "persistence": round(persistence, 4),
                        "vol_ratio": (
                            round(vol_ratio, 4) if vol_ratio is not None else None
                        ),
                        "vol_score": (
                            round(vol_score, 4) if vol_score is not None else None
                        ),
                        "mpi_index": round(mpi_index, 2),
                        "price": price,
                    },
                    ttl_minutes=t["ttl_coin_mood_min"],
                )
                alerts.append(alert)
                state.record_fire(key, magnitude, "up")

        # 3) COIN_BREADTH_FAILURE: weak breadth + coin weakness or relative failure.
        failure_rule_a = breadth <= float(
            t.get("coin_failure_breadth_max", 0.35) or 0.35
        ) and pct_3m <= float(t.get("coin_failure_pct3m_max", -1.6) or -1.6)
        failure_rule_b = (
            rs3m <= float(t.get("coin_failure_rs3m_max", -0.9) or -0.9) and pct_3m < 0
        )
        if failure_rule_a or failure_rule_b:
            sev = (
                AlertSeverity.HIGH
                if pct_3m <= -2.8 or rs3m <= -1.6
                else AlertSeverity.MEDIUM
            )
            magnitude = abs(min(0.0, pct_3m)) + abs(min(0.0, rs3m))
            key = f"{AlertType.COIN_BREADTH_FAILURE.value}::{sym}"
            if state.check_cooldown(
                key,
                t["cooldown_coin_failure"],
                magnitude,
                "down",
                t["dedupe_coin_failure"],
            ):
                alert = _make_alert(
                    symbol=sym,
                    alert_type=AlertType.COIN_BREADTH_FAILURE,
                    severity=sev,
                    title=f"BREADTH FAILURE: {sym}",
                    message=f"{sym} lagging in weak tape ({pct_3m:+.2f}% 3m, RS {rs3m:+.2f})",
                    direction="down",
                    evidence={
                        "window": "3m",
                        "pct_1m": pct_1m,
                        "pct_3m": pct_3m,
                        "pct_1h": pct_1h,
                        "rs3m": round(rs3m, 4),
                        "breadth": round(breadth, 4),
                        "persistence": round(persistence, 4),
                        "vol_ratio": (
                            round(vol_ratio, 4) if vol_ratio is not None else None
                        ),
                        "vol_score": (
                            round(vol_score, 4) if vol_score is not None else None
                        ),
                        "mpi_index": round(mpi_index, 2),
                        "price": price,
                    },
                    ttl_minutes=t["ttl_coin_mood_min"],
                )
                alerts.append(alert)
                state.record_fire(key, magnitude, "down")

    return alerts


def _market_confluence_legs(
    pressure: MarketPressure, fg_value: int | None
) -> tuple[float, int, dict[str, Any]]:
    """Compute market siren confluence score + leg hits."""
    legs: dict[str, bool] = {}
    score = 0.0
    legs_hit = 0

    b_up = float(getattr(pressure, "breadth_up", 0.0) or 0.0)
    b_dn = float(getattr(pressure, "breadth_down", 0.0) or 0.0)
    breadth_intensity = abs(b_up - b_dn)
    breadth_points = min(30.0, breadth_intensity * 60.0)
    if breadth_points >= 12.0:
        legs_hit += 1
        legs["breadth"] = True
    else:
        legs["breadth"] = False
    score += breadth_points

    align = _to_float_or_none(getattr(pressure, "alignment", None))
    if align is None:
        align = (
            _to_float_or_none((pressure.components or {}).get("breadth_bias")) or 0.0
        )
    align = float(align)
    align_points = min(25.0, max(0.0, abs(align) * 25.0))
    if align_points >= 12.0:
        legs_hit += 1
        legs["alignment"] = True
    else:
        legs["alignment"] = False
    score += align_points

    vol = _to_float_or_none(getattr(pressure, "volatility", None))
    if vol is None:
        # Map internal 0..1 vol_regime into a rough 1..3 volatility axis.
        vr = _clamp(
            _to_float_or_none((pressure.components or {}).get("vol_regime")) or 0.5
        )
        vol = 3.0 - (2.0 * vr)
    vol = float(vol)
    if vol <= 1.5:
        vol_points = 20.0
    elif vol <= 2.5:
        vol_points = 10.0
    else:
        vol_points = 0.0
    if vol_points >= 10.0:
        legs_hit += 1
        legs["vol_regime"] = True
    else:
        legs["vol_regime"] = False
    score += vol_points

    if fg_value is not None:
        fg = float(fg_value)
        if fg >= 75.0:
            fg_points = min(25.0, (fg - 75.0) * 1.0 + 10.0)
            legs_hit += 1
            legs["fear_greed"] = True
            score += fg_points
        elif fg <= 25.0:
            fg_points = min(25.0, (25.0 - fg) * 1.0 + 10.0)
            legs_hit += 1
            legs["fear_greed"] = True
            score += fg_points
        else:
            legs["fear_greed"] = False

    detail = {
        "score": round(score, 2),
        "legs_hit": legs_hit,
        "legs": legs,
        "breadth_intensity": round(breadth_intensity, 3),
        "alignment": round(align, 3),
        "volatility": round(vol, 3),
        "fg_value": fg_value,
    }
    return score, legs_hit, detail


def _market_extreme_gate(pressure: MarketPressure, t: dict) -> str | None:
    """Return FOMO/FEAR if market is at an extreme, else None."""
    heat_raw = _to_float_or_none(getattr(pressure, "heat", 0.0)) or 0.0
    heat = heat_raw / 100.0 if heat_raw > 1.0 else heat_raw
    heat_min = float(t.get("market_siren_extreme_heat_min", 0.75) or 0.75)
    fear_max = float(t.get("market_siren_extreme_fear_max", -0.75) or -0.75)
    if heat >= heat_min:
        return "FOMO"
    if heat_raw < 0 and heat_raw <= fear_max:
        return "FEAR"

    bias_raw = getattr(pressure, "bias", 0.0)
    if isinstance(bias_raw, str):
        bias = (
            1.0
            if bias_raw.lower() == "up"
            else (-1.0 if bias_raw.lower() == "down" else 0.0)
        )
    else:
        bias = _to_float_or_none(bias_raw) or 0.0
    if heat <= (1.0 - heat_min) and bias < -0.4:
        return "FEAR"
    return None


def _detect_market_siren_alerts(
    pressure: MarketPressure,
    fg_value: int | None,
    state: AlertEngineState,
    t: dict,
) -> list[dict]:
    now = time.time()
    kind = _market_extreme_gate(pressure, t)
    if not kind:
        state.market_siren_streak = 0
        state.market_siren_last_key = None
        return []

    score, legs_hit, detail = _market_confluence_legs(pressure, fg_value)

    if state.market_siren_last_key != kind:
        state.market_siren_last_key = kind
        state.market_siren_streak = 0

    if score >= float(
        t.get("market_siren_score_min", 80.0) or 80.0
    ) and legs_hit >= int(t.get("market_siren_min_legs", 3) or 3):
        state.market_siren_streak += 1
    else:
        state.market_siren_streak = 0
        return []

    if state.market_siren_streak < int(t.get("market_siren_persist_polls", 3) or 3):
        return []

    cooldown_s = float(
        t.get("market_siren_cooldown_s", t.get("cooldown_market_siren", 900)) or 900
    )
    if (now - float(state.market_siren_last_emit_ts or 0.0)) < cooldown_s:
        return []

    atype = (
        AlertType.MARKET_FOMO_SIREN if kind == "FOMO" else AlertType.MARKET_FEAR_SIREN
    )
    dedupe_delta = float(t.get("dedupe_market_siren", 4.0) or 4.0)
    cooldown_key = f"{atype.value}::MARKET"
    if not state.check_cooldown(
        cooldown_key, cooldown_s, score, kind.lower(), dedupe_delta
    ):
        return []

    state.market_siren_last_emit_ts = now
    state.record_fire(cooldown_key, score, kind.lower())

    score_min = float(t.get("market_siren_score_min", 80.0) or 80.0)
    sev = AlertSeverity.HIGH if score >= (score_min + 10.0) else AlertSeverity.MEDIUM
    title = "Market FOMO" if kind == "FOMO" else "Market FEAR"
    msg = (
        f"{kind} confluence: {int(score)} score, {legs_hit} legs, "
        f"streak {state.market_siren_streak}"
    )
    detail = {
        **detail,
        "market_siren_streak": int(state.market_siren_streak),
        "market_siren_kind": kind.lower(),
    }

    return [
        _make_alert(
            symbol="MARKET",
            alert_type=atype,
            severity=sev,
            title=title,
            message=msg,
            direction=kind.lower(),
            evidence=detail,
            ttl_minutes=int(t.get("ttl_market_siren_min", 12) or 12),
        )
    ]


_SEV_WEIGHT = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}


_TYPE_BONUS = {
    # Structure (highest utility under cap)
    AlertType.COIN_REVERSAL_UP.value: 72.0,
    AlertType.COIN_REVERSAL_DOWN.value: 72.0,
    AlertType.COIN_FAKEOUT.value: 70.0,
    AlertType.COIN_TREND_BREAK_UP.value: 68.0,
    AlertType.COIN_TREND_BREAK_DOWN.value: 68.0,
    AlertType.COIN_EXHAUSTION_TOP.value: 66.0,
    AlertType.COIN_EXHAUSTION_BOTTOM.value: 66.0,
    AlertType.COIN_PERSISTENT_GAINER.value: 64.0,
    AlertType.COIN_PERSISTENT_LOSER.value: 64.0,
    # Whale / stealth (rare, high-signal)
    AlertType.WHALE_MOVE.value: 56.0,
    AlertType.STEALTH_MOVE.value: 52.0,
    # Impulse family
    AlertType.MOONSHOT.value: 46.0,
    AlertType.CRATER.value: 46.0,
    AlertType.BREAKOUT.value: 42.0,
    AlertType.DUMP.value: 42.0,
    # Coin mood and wake-up family
    AlertType.COIN_FOMO.value: 140.0,
    AlertType.COIN_BREADTH_THRUST.value: 36.0,
    AlertType.COIN_BREADTH_FAILURE.value: 36.0,
    AlertType.COIN_SQUEEZE_BREAK.value: 34.0,
    AlertType.COIN_VOLATILITY_EXPANSION.value: 32.0,
    AlertType.COIN_LIQUIDITY_SHOCK.value: 30.0,
    # Market-only mood (optional)
    AlertType.MARKET_FOMO_SIREN.value: 26.0,
    AlertType.MARKET_FEAR_SIREN.value: 26.0,
    AlertType.FOMO_ALERT.value: 22.0,
    AlertType.FEAR_ALERT.value: 22.0,
    # Lowest priority under cap
    AlertType.DIVERGENCE.value: 8.0,
}


def _family_of_alert(a: dict[str, Any]) -> str:
    typ = str((a or {}).get("type") or (a or {}).get("type_key") or "").lower()
    if typ.startswith("whale_") or typ == AlertType.WHALE_MOVE.value:
        return "whale"
    if typ.startswith("stealth_") or typ == AlertType.STEALTH_MOVE.value:
        return "stealth"
    return "other"


def _alert_rank(a: dict[str, Any]) -> float:
    sev = str((a or {}).get("severity") or "low").lower()
    w = _SEV_WEIGHT.get(sev, 2)
    typ = str((a or {}).get("type") or (a or {}).get("type_key") or "").lower()

    ev = (a or {}).get("evidence")
    ev = ev if isinstance(ev, dict) else {}
    mag = 0.0
    for k in (
        "pct",
        "magnitude",
        "pct_1m",
        "pct_3m",
        "vol_z",
        "vol_ratio",
        "vol_jump_ratio",
        "diff",
    ):
        v = _to_float_or_none(ev.get(k))
        if v is not None:
            mag = max(mag, abs(v))

    type_bonus = _TYPE_BONUS.get(typ, 0.0)
    if type_bonus == 0.0 and typ.startswith("coin_"):
        type_bonus = 24.0
    if typ in {AlertType.WHALE_MOVE.value, AlertType.STEALTH_MOVE.value}:
        type_bonus -= 10.0
    if (
        typ
        in {
            AlertType.COIN_LIQUIDITY_SHOCK.value,
            AlertType.COIN_FAKEOUT.value,
        }
        or typ.startswith("coin_reversal_")
        or typ.startswith("coin_trend_break_")
    ):
        type_bonus += 8.0
    if typ in {"divergence", "divergence_1m", "divergence_3m"}:
        type_bonus -= 8.0
    return (w * 100.0) + mag + type_bonus


def _shape_alert_stream(
    alerts: list[dict[str, Any]],
    state: AlertEngineState,
    t: dict[str, Any],
) -> list[dict[str, Any]]:
    if not alerts:
        return []

    now = time.time()
    window_s = float(t.get("family_recent_window_s", 300) or 300)

    # Keep only recent accepted family alerts.
    ring = [
        (float(ts), str(fam))
        for ts, fam in (state.emit_ring or [])
        if (now - float(ts)) <= window_s
    ]
    state.emit_ring = ring

    recent_counts: dict[str, int] = {}
    for _ts, fam in ring:
        recent_counts[fam] = recent_counts.get(fam, 0) + 1

    out: list[dict[str, Any]] = []
    for a in alerts:
        fam = _family_of_alert(a)
        if fam == "other":
            out.append(a)
            continue

        sym = str((a or {}).get("symbol") or "").upper()
        symbol_key = f"{fam}:{sym}"

        cd_sym = float(t.get(f"{fam}_symbol_cooldown_s", 180) or 180)
        last_sym = float(state.last_emit_by_symbol_family.get(symbol_key, 0.0) or 0.0)
        if (now - last_sym) < cd_sym:
            continue

        cd_fam = float(t.get("family_global_cooldown_s", 20) or 20)
        last_fam = float(state.last_emit_by_family.get(fam, 0.0) or 0.0)
        if (now - last_fam) < cd_fam:
            continue

        if recent_counts.get(fam, 0) >= int(t.get("family_recent_max", 14) or 14):
            continue

        out.append(a)
        state.last_emit_by_symbol_family[symbol_key] = now
        state.last_emit_by_family[fam] = now
        state.emit_ring.append((now, fam))
        recent_counts[fam] = recent_counts.get(fam, 0) + 1

    return out


def _prune_alerts(
    alerts: list[dict[str, Any]],
    max_total: int = 24,
    max_per_symbol: int = 2,
) -> list[dict[str, Any]]:
    if not alerts:
        return []

    # De-dupe exact (symbol,type) within the same cycle; keep best-ranked.
    best_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for a in alerts:
        sym = str((a or {}).get("symbol") or "").upper()
        typ = str((a or {}).get("type") or (a or {}).get("type_key") or "").lower()
        key = (sym, typ)
        if key not in best_by_key or _alert_rank(a) > _alert_rank(best_by_key[key]):
            best_by_key[key] = a

    deduped = list(best_by_key.values())
    deduped.sort(
        key=lambda a: (
            -_alert_rank(a),
            str((a or {}).get("symbol") or "").upper(),
            str((a or {}).get("type") or (a or {}).get("type_key") or "").lower(),
            str((a or {}).get("id") or ""),
        )
    )

    # Enforce per-symbol cap.
    out: list[dict[str, Any]] = []
    per_sym: dict[str, int] = {}
    for a in deduped:
        sym = str((a or {}).get("symbol") or "").upper()
        n = per_sym.get(sym, 0)
        if n >= max_per_symbol:
            continue
        out.append(a)
        per_sym[sym] = n + 1
        if len(out) >= max_total:
            break
    return out


# ---------------------------------------------------------------------------
# Main entry point — pure function
# ---------------------------------------------------------------------------


def compute_alerts(
    price_snapshot: dict[str, dict],
    volume_snapshot: dict[str, dict],
    minute_volumes: dict[str, list],
    state: AlertEngineState,
    fg_value: int | None = None,
    thresholds: dict | None = None,
    include_impulse: bool = True,
    include_market_mood: bool = False,
) -> tuple[list[dict], AlertEngineState, MarketPressure]:
    """Compute all alerts from current inputs.

    Args:
        include_impulse: If False, skip MOONSHOT/CRATER/BREAKOUT/DUMP.
            Use False in production while SWR builders still emit impulse alerts.
        include_market_mood: If True, allow rare standalone MARKET sirens
            (confluence + persistence + cooldown).

    Returns:
        (alerts, updated_state, market_pressure)
    """
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    _warm_return_hist(state, price_snapshot, t)

    all_alerts: list[dict] = []

    # 1. Impulse alerts — enabled by default; call-sites may disable via include_impulse=False
    if include_impulse:
        all_alerts.extend(_detect_impulse_alerts(price_snapshot, state, t))

    # 2. Whale alerts (aggregated flow spike)
    all_alerts.extend(
        _detect_whale_alerts(price_snapshot, volume_snapshot, minute_volumes, state, t)
    )

    # 3. Stealth alerts (loud volume, quiet price)
    all_alerts.extend(_detect_stealth_alerts(price_snapshot, volume_snapshot, state, t))

    # 4. Market pressure + FOMO/FEAR
    pressure = compute_market_pressure(
        price_snapshot=price_snapshot,
        volume_snapshot=volume_snapshot,
        thresholds=t,
        state=state,
    )
    _record_pressure_index(state, pressure.index)

    # 5. Coin-structure alerts (reversal/fakeout/trend-break/exhaustion/persistence)
    reversal_alerts = _detect_coin_reversal_alerts(price_snapshot, state, t)
    fakeout_alerts = _detect_coin_fakeout_alerts(price_snapshot, state, t)
    trend_break_alerts = _detect_coin_trend_break_alerts(
        price_snapshot, volume_snapshot, state, t
    )
    fakeout_symbols = {
        str((a or {}).get("symbol") or "").upper() for a in fakeout_alerts
    }
    exhaustion_alerts = _detect_coin_exhaustion_alerts(
        price_snapshot, volume_snapshot, state, t, fakeout_symbols
    )
    persistence_alerts = _detect_coin_persistence_alerts(price_snapshot, state, t)
    all_alerts.extend(reversal_alerts)
    all_alerts.extend(fakeout_alerts)
    all_alerts.extend(trend_break_alerts)
    all_alerts.extend(exhaustion_alerts)
    all_alerts.extend(persistence_alerts)

    # 6. Coin wake-up alerts (volatility expansion / liquidity shock / squeeze-break)
    all_alerts.extend(
        _detect_coin_volatility_expansion_alerts(price_snapshot, state, t)
    )
    all_alerts.extend(
        _detect_coin_liquidity_shock_alerts(
            price_snapshot, volume_snapshot, minute_volumes, state, t
        )
    )
    all_alerts.extend(_detect_coin_squeeze_break_alerts(price_snapshot, state, t))

    # 7. Coin-scoped mood alerts (market-aware context, never MARKET symbol)
    all_alerts.extend(
        _detect_coin_mood_alerts(price_snapshot, volume_snapshot, pressure, state, t)
    )

    # 8. Divergence alerts (timeframe disagreement + market pressure context)
    all_alerts.extend(_detect_divergence_alerts(price_snapshot, pressure, state, t))

    # 9. Optional standalone market sirens (disabled by default).
    if include_market_mood:
        all_alerts.extend(_detect_market_siren_alerts(pressure, fg_value, state, t))

    # Attach market mood context to all coin alerts for richer coin-popup display.
    _attach_coin_mood_context(all_alerts, pressure)

    # Hard guardrail: coin-scoped stream by default; permit only rare MARKET sirens
    # when include_market_mood=True.
    allowed_market_types = {
        AlertType.MARKET_FOMO_SIREN.value,
        AlertType.MARKET_FEAR_SIREN.value,
    }
    all_alerts = [
        a
        for a in all_alerts
        if str((a or {}).get("symbol") or "").upper() not in {"MARKET", "MARKET-USD"}
        or (
            include_market_mood
            and str((a or {}).get("type") or (a or {}).get("type_key") or "").lower()
            in allowed_market_types
        )
    ]

    # Family-level shaping pass (cooldowns + soft cap) before final ranking cap.
    all_alerts = _shape_alert_stream(all_alerts, state, t)

    # Final shaping: keep it lively, not spammy.
    all_alerts = _prune_alerts(
        all_alerts,
        max_total=int(t.get("alerts_max_total", 24)),
        max_per_symbol=int(t.get("alerts_max_per_symbol", 2)),
    )

    return all_alerts, state, pressure
