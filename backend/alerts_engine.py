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
    FOMO_ALERT   — market pressure index extreme (upside)
    FEAR_ALERT   — market pressure index extreme (downside)

Not implemented (require external sources):
    SENTIMENT_SPIKE, NEWS_CATALYST, ARBITRAGE

Storage:
    In-memory state with optional Redis for dedupe/TTL.
    Engine never depends on Redis for correctness — fails open.
"""

from __future__ import annotations

import time
import uuid
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
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
    "moonshot_1m_pct": 6.0,       # >= this on 1m -> moonshot/crater
    "moonshot_3m_pct": 8.0,       # >= this on 3m -> moonshot/crater
    "breakout_1m_pct": 2.5,       # >= this on 1m -> breakout/dump
    "breakout_3m_pct": 3.5,       # >= this on 3m -> breakout/dump
    "impulse_1m_pct": 1.25,       # minimum to even consider 1m impulse
    "impulse_3m_pct": 2.0,        # minimum to even consider 3m impulse

    # Whale (volume surge)
    "whale_z_score": 3.0,         # single-candle z-score vs rolling baseline
    "whale_cluster_z": 2.5,       # 3-candle cluster z-score
    "whale_candle_pct": 0.3,      # min abs(candle_pct) for whale move
    "whale_surge_1h_pct": 150.0,  # fallback: hourly vol change %
    "whale_min_abs_vol": 500,     # minimum absolute volume (units) to qualify

    # Absorption (sub-type of whale)
    "absorption_z": 2.5,
    "absorption_max_pct": 0.15,
    "absorption_max_range": 0.3,
    "absorption_min_pulses": 1,

    # Stealth (volume spike + muted price = early smoke)
    "stealth_vol_min_pct": 80.0,      # vol change must be ABOVE this (loud volume)
    "stealth_price_max_abs_pct": 1.2, # abs(pct_3m) must be BELOW this (quiet price)

    # Divergence
    "divergence_1m_threshold": 0.5,   # abs(ret_1m) must exceed
    "divergence_3m_threshold": 0.5,   # abs(ret_3m) must exceed (opposite sign)

    # FOMO / FEAR (Market Pressure Index)
    "fomo_heat_min": 80,
    "fear_heat_max": 20,
    "fomo_fg_min": 70,            # Fear & Greed min for FOMO (None = ignore)
    "fear_fg_max": 30,            # Fear & Greed max for FEAR

    # Cooldowns (seconds)
    "cooldown_impulse": 90,
    "cooldown_whale": 120,
    "cooldown_absorption": 300,
    "cooldown_whale_surge": 300,
    "cooldown_stealth": 300,
    "cooldown_divergence": 180,
    "cooldown_fomo": 600,

    # TTLs (minutes)
    "ttl_impulse_min": 5,
    "ttl_whale_min": 8,
    "ttl_absorption_min": 5,
    "ttl_whale_surge_min": 10,
    "ttl_stealth_min": 5,
    "ttl_divergence_min": 5,
    "ttl_fomo_min": 10,

    # Dedupe deltas (magnitude must change by at least this to re-fire within cooldown)
    "dedupe_impulse": 0.35,
    "dedupe_whale": 2.0,
    "dedupe_absorption": 1.0,
    "dedupe_whale_surge": 30.0,
    "dedupe_stealth": 0.5,
    "dedupe_divergence": 0.5,
}


# ---------------------------------------------------------------------------
# Engine state (persists across compute cycles)
# ---------------------------------------------------------------------------

@dataclass
class AlertEngineState:
    """Mutable state carried between compute_alerts() calls."""
    # Per-key cooldown tracking: key -> (last_ts, last_magnitude, last_direction)
    last_fired: dict[str, tuple[float, float, str | None]] = field(default_factory=dict)

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

    def record_fire(self, key: str, magnitude: float = 0.0, direction: str | None = None) -> None:
        self.last_fired[key] = (time.time(), magnitude, direction)


# ---------------------------------------------------------------------------
# Market Pressure Index (replaces external sentiment)
# ---------------------------------------------------------------------------

@dataclass
class MarketPressure:
    """Coinbase-only 'emotion' proxy derived from breadth + impulse density."""
    heat: float = 50.0       # 0-100
    bias: str = "neutral"    # "up" | "down" | "neutral"
    breadth_up: float = 0.0  # fraction of symbols with 1m > threshold
    breadth_down: float = 0.0
    impulse_count: int = 0   # how many symbols crossed impulse thresholds
    symbol_count: int = 0    # total symbols evaluated
    label: str = "Normal"    # human-readable


def compute_market_pressure(
    price_snapshot: dict[str, dict],
    thresholds: dict | None = None,
) -> MarketPressure:
    """Compute market-wide pressure from price snapshot alone."""
    t = thresholds or DEFAULT_THRESHOLDS
    impulse_1m = t["impulse_1m_pct"]

    symbols = [s for s, d in price_snapshot.items() if d.get("pct_1m") is not None]
    n = len(symbols)
    if n == 0:
        return MarketPressure()

    up = sum(1 for s in symbols if (price_snapshot[s].get("pct_1m") or 0) > impulse_1m)
    down = sum(1 for s in symbols if (price_snapshot[s].get("pct_1m") or 0) < -impulse_1m)
    impulse_total = up + down

    breadth_up = up / n
    breadth_down = down / n

    # Heat: 0-100 scale.  50 = neutral.
    # Up breadth pushes heat up, down breadth pushes heat down, impulse density amplifies.
    raw = 50.0 + (breadth_up - breadth_down) * 100.0
    density_boost = min(20.0, (impulse_total / max(n, 1)) * 80.0)
    if breadth_up > breadth_down:
        raw += density_boost
    else:
        raw -= density_boost
    heat = max(0.0, min(100.0, raw))

    if heat >= 80:
        bias, label = "up", "Overheated"
    elif heat >= 70:
        bias, label = "up", "Hot"
    elif heat <= 20:
        bias, label = "down", "Frozen"
    elif heat <= 30:
        bias, label = "down", "Cold"
    else:
        bias, label = "neutral", "Normal"

    return MarketPressure(
        heat=round(heat, 1),
        bias=bias,
        breadth_up=round(breadth_up, 3),
        breadth_down=round(breadth_down, 3),
        impulse_count=impulse_total,
        symbol_count=n,
        label=label,
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
    return {
        "id": f"{alert_type.value}_{product_id}_{uuid.uuid4().hex[:8]}",
        "ts": now.isoformat(),
        "ts_ms": int(now.timestamp() * 1000),
        "event_ts": now.isoformat(),
        "event_ts_ms": int(now.timestamp() * 1000),
        "symbol": product_id,
        "type": alert_type.value,
        "severity": severity.value,
        "title": title,
        "message": message,
        "direction": direction,
        "evidence": evidence,
        "ttl_seconds": ttl_minutes * 60,
        "expires_at": (now + timedelta(minutes=ttl_minutes)).isoformat(),
        "trade_url": trade_url or f"https://www.coinbase.com/advanced-trade/spot/{product_id}",
    }


def _to_float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        v = float(value)
        return v if (v == v and v not in (float("inf"), float("-inf"))) else None
    except Exception:
        return None


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
        if not state.check_cooldown(key, t["cooldown_impulse"], best_mag, direction, t["dedupe_impulse"]):
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
        mins = minute_volumes.get(product_id, [])

        # --- Mode 1: Per-minute z-score whale ---
        if len(mins) >= 15:
            vols = [m["vol"] for m in mins if m.get("vol", 0) > 0]
            if len(vols) >= 15:
                latest = mins[0]
                latest_vol = latest["vol"]
                latest_close = latest.get("close", 0)
                latest_open = latest.get("open", 0)

                baseline_vols = vols[1:61]
                n = len(baseline_vols)
                if n >= 10:
                    mean_vol = sum(baseline_vols) / n
                    variance = sum((v - mean_vol) ** 2 for v in baseline_vols) / n
                    std_vol = variance ** 0.5 if variance > 0 else 0
                    z_vol = (latest_vol - mean_vol) / std_vol if std_vol > 0 else 0

                    sorted_vols = sorted(baseline_vols)
                    median_vol = sorted_vols[n // 2]
                    vol_ratio = (latest_vol / median_vol) if median_vol > 0 else 0

                    candle_pct = ((latest_close - latest_open) / latest_open * 100) if latest_open > 0 else 0

                    # 3-candle cluster
                    cluster_vol = sum(m["vol"] for m in mins[:3]) if len(mins) >= 3 else latest_vol
                    cluster_z = (cluster_vol / 3 - mean_vol) / std_vol if std_vol > 0 else 0

                    # WHALE MOVE: z >= 3.0 + price impact
                    if (z_vol >= t["whale_z_score"] and abs(candle_pct) >= t["whale_candle_pct"] and latest_vol > 100) or \
                       (cluster_z >= t["whale_cluster_z"] and abs(candle_pct) >= 0.4 and cluster_vol > 300):
                        direction = "up" if candle_pct > 0 else "down"
                        whale_score = z_vol * abs(candle_pct)
                        sev = AlertSeverity.CRITICAL if z_vol >= 5.0 or whale_score >= 8 else AlertSeverity.HIGH
                        key = f"whale_move::{sym}"
                        if state.check_cooldown(key, t["cooldown_whale"], whale_score, direction, t["dedupe_whale"]):
                            alert = _make_alert(
                                symbol=sym,
                                alert_type=AlertType.WHALE_MOVE,
                                severity=sev,
                                title=f"WHALE: {sym} flow spike",
                                message=f"{sym} {candle_pct:+.2f}% in 1m, vol {vol_ratio:.1f}x median ({z_vol:.1f}\u03c3)",
                                direction=direction,
                                evidence={
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
                    if z_vol >= t["absorption_z"] and abs(candle_pct) < t["absorption_max_pct"] and latest_vol > 100:
                        # Check repeat pattern
                        absorption_count = 0
                        for m in mins[1:6]:
                            m_vol = m.get("vol", 0)
                            m_z = (m_vol - mean_vol) / std_vol if std_vol > 0 else 0
                            m_pct = ((m.get("close", 0) - m.get("open", 1)) / m.get("open", 1) * 100) if m.get("open", 0) > 0 else 0
                            if m_z >= 2.0 and abs(m_pct) < 0.2:
                                absorption_count += 1
                        if absorption_count >= t["absorption_min_pulses"]:
                            key = f"absorption::{sym}"
                            if state.check_cooldown(key, t["cooldown_absorption"], z_vol, "absorption", t["dedupe_absorption"]):
                                alert = _make_alert(
                                    symbol=sym,
                                    alert_type=AlertType.WHALE_MOVE,
                                    severity=AlertSeverity.MEDIUM,
                                    title=f"WHALE ABSORPTION: {sym}",
                                    message=f"{sym} heavy tape, price flat ({candle_pct:+.2f}%), vol {vol_ratio:.1f}x ({z_vol:.1f}\u03c3), {absorption_count + 1} pulses",
                                    direction="absorption",
                                    evidence={
                                        # Contract fields (always numeric-or-None)
                                        "volume_change_1h_pct": _to_float_or_none(vol1h_pct),
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
                sev = AlertSeverity.CRITICAL if vol1h_pct >= 400 else AlertSeverity.HIGH if vol1h_pct >= 250 else AlertSeverity.MEDIUM
                key = f"whale_surge::{sym}"
                if state.check_cooldown(key, t["cooldown_whale_surge"], vol1h_pct, "up", t["dedupe_whale_surge"]):
                    alert = _make_alert(
                        symbol=sym,
                        alert_type=AlertType.WHALE_MOVE,
                        severity=sev,
                        title=f"WHALE SURGE: {sym}",
                        message=f"{sym} 1h volume {vol1h_pct:+.0f}% vs prev hour ({vol1h_now:,.0f} units)",
                        direction="up",
                        evidence={
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
        if not state.check_cooldown(key, t["cooldown_stealth"], magnitude, direction, t["dedupe_stealth"]):
            continue

        alert = _make_alert(
            symbol=sym,
            alert_type=AlertType.STEALTH_MOVE,
            severity=AlertSeverity.MEDIUM,
            title=f"STEALTH: {sym} {direction}",
            message=f"{sym} vol {vol1h_pct:+.0f}% but price only {pct_3m:+.2f}% — quiet {direction}",
            direction=direction,
            evidence={
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
        if not ((ret_1m > thresh_1m and ret_3m < -thresh_3m) or (ret_1m < -thresh_1m and ret_3m > thresh_3m)):
            continue

        magnitude = abs(ret_1m - ret_3m)
        if ret_1m > 0:
            direction = "reversal_up"
            msg = f"{sym}: 1m up {ret_1m:+.2f}% but 3m down {ret_3m:+.2f}% — possible reversal"
        else:
            direction = "reversal_down"
            msg = f"{sym}: 1m down {ret_1m:+.2f}% but 3m up {ret_3m:+.2f}% — possible pullback"

        key = f"divergence::{sym}"
        if not state.check_cooldown(key, t["cooldown_divergence"], magnitude, direction, t["dedupe_divergence"]):
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
                "pct_1m": round(ret_1m, 4),
                "pct_3m": round(ret_3m, 4),
                "pct_1h": data.get("pct_1h"),
                "magnitude": round(magnitude, 2),
                "heat": _to_float_or_none(pressure.heat if pressure else None),
                "breadth_up": _to_float_or_none(pressure.breadth_up if pressure else None),
                "breadth_down": _to_float_or_none(pressure.breadth_down if pressure else None),
                "price": price,
            },
            ttl_minutes=t["ttl_divergence_min"],
        )
        alerts.append(alert)
        state.record_fire(key, magnitude, direction)

    return alerts


def _detect_fomo_fear_alerts(
    pressure: MarketPressure,
    fg_value: int | None,
    state: AlertEngineState,
    thresholds: dict,
) -> list[dict]:
    """Detect FOMO / FEAR from Market Pressure Index."""
    alerts: list[dict] = []
    t = thresholds

    fomo = pressure.heat >= t["fomo_heat_min"] and (fg_value is None or fg_value >= t["fomo_fg_min"])
    fear = pressure.heat <= t["fear_heat_max"] and (fg_value is None or fg_value <= t["fear_fg_max"])

    if not fomo and not fear:
        return alerts

    if fomo:
        atype = AlertType.FOMO_ALERT
        sev = AlertSeverity.HIGH
        title = "FOMO: Market Overheating"
        msg = f"Market Heat {pressure.heat}/100 ({pressure.label}), breadth {pressure.breadth_up:.0%} up"
        if fg_value is not None:
            msg += f", Fear & Greed {fg_value}/100"
        direction = "fomo"
    else:
        atype = AlertType.FEAR_ALERT
        sev = AlertSeverity.HIGH
        title = "FEAR: Market Extreme"
        msg = f"Market Heat {pressure.heat}/100 ({pressure.label}), breadth {pressure.breadth_down:.0%} down"
        if fg_value is not None:
            msg += f", Fear & Greed {fg_value}/100"
        direction = "fear"

    key = f"{atype.value}::MARKET"
    if not state.check_cooldown(key, t["cooldown_fomo"], pressure.heat, direction, 10.0):
        return alerts

    alert = _make_alert(
        symbol="MARKET",
        alert_type=atype,
        severity=sev,
        title=title,
        message=msg,
        direction=direction,
        evidence={
            "heat": pressure.heat,
            "bias": pressure.bias,
            "breadth_up": pressure.breadth_up,
            "breadth_down": pressure.breadth_down,
            "advancing": round(pressure.breadth_up * pressure.symbol_count, 2),
            "declining": round(pressure.breadth_down * pressure.symbol_count, 2),
            "impulse_count": pressure.impulse_count,
            "symbol_count": pressure.symbol_count,
            "fear_greed": fg_value,
        },
        ttl_minutes=t["ttl_fomo_min"],
    )
    alerts.append(alert)
    state.record_fire(key, pressure.heat, direction)
    return alerts


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
) -> tuple[list[dict], AlertEngineState, MarketPressure]:
    """Compute all alerts from current inputs.

    Args:
        include_impulse: If False, skip MOONSHOT/CRATER/BREAKOUT/DUMP.
            Use False in production while SWR builders still emit impulse alerts.

    Returns:
        (alerts, updated_state, market_pressure)
    """
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    all_alerts: list[dict] = []

    # 1. Impulse alerts — enabled by default; production call-site passes include_impulse=False
    if include_impulse:
        all_alerts.extend(_detect_impulse_alerts(price_snapshot, state, t))

    # 2. Whale alerts (aggregated flow spike)
    all_alerts.extend(_detect_whale_alerts(price_snapshot, volume_snapshot, minute_volumes, state, t))

    # 3. Stealth alerts (loud volume, quiet price)
    all_alerts.extend(_detect_stealth_alerts(price_snapshot, volume_snapshot, state, t))

    # 4. Market pressure + FOMO/FEAR
    pressure = compute_market_pressure(price_snapshot, t)

    # 5. Divergence alerts (timeframe disagreement + market pressure context)
    all_alerts.extend(_detect_divergence_alerts(price_snapshot, pressure, state, t))

    # 6. FOMO/FEAR alerts
    all_alerts.extend(_detect_fomo_fear_alerts(pressure, fg_value, state, t))

    return all_alerts, state, pressure
