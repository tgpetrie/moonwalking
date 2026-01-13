from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math
import time


@dataclass
class SourceValue:
    """
    Canonical input unit for sentiment scoring.

    value:
      - kind="signed": in [-1, +1] where -1 bearish, +1 bullish
      - kind="unsigned": in [0, 1] where higher = more bullish/greedy
    weight:
      - relative importance before freshness + tier confidence curves
    meta:
      - may include: tier, confidence (0..1), data_points, etc.
    """
    name: str
    ok: bool
    value: float
    asof_ts: float
    weight: float = 1.0
    kind: str = "signed"  # "signed" | "unsigned"
    meta: Dict[str, Any] = field(default_factory=dict)


# -------------------------------
# Tier confidence decay curves
# -------------------------------

TIER_CURVES: Dict[str, Dict[str, float]] = {
    # Half-life: how fast signal goes stale
    # Min floor: stale-but-not-dead residual trust (prevents cliff drops)
    # Base trust: applied to source weight before freshness decay
    "tier1": {"half_life_s": 60 * 30, "min_floor": 0.35, "base_trust": 1.10},
    "tier2": {"half_life_s": 60 * 20, "min_floor": 0.25, "base_trust": 0.95},
    "fringe": {"half_life_s": 60 * 12, "min_floor": 0.15, "base_trust": 0.75},
    # Non-tier sources
    "fear_greed": {"half_life_s": 60 * 60 * 3, "min_floor": 0.50, "base_trust": 1.05},
    "funding": {"half_life_s": 60 * 25, "min_floor": 0.35, "base_trust": 1.10},
    "google_ai": {"half_life_s": 60 * 18, "min_floor": 0.25, "base_trust": 1.00},
    # default fallback for unknown
    "default": {"half_life_s": 60 * 15, "min_floor": 0.20, "base_trust": 0.90},
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _half_life_decay(age_s: float, half_life_s: float) -> float:
    """Standard half-life exponential: 0.5 every half_life_s seconds."""
    if half_life_s <= 0:
        return 1.0
    return math.exp(-math.log(2) * (age_s / half_life_s))


def _tier_curve(source: SourceValue) -> Tuple[str, Dict[str, float]]:
    # Prefer explicit tier in meta if present
    tier = (source.meta.get("tier") or "").strip().lower()
    if tier in TIER_CURVES:
        return tier, TIER_CURVES[tier]

    # Otherwise map by known source names
    key = source.name.strip().lower()
    if key in TIER_CURVES:
        return key, TIER_CURVES[key]

    return "default", TIER_CURVES["default"]


def _normalize_value(source: SourceValue) -> float:
    """
    Returns signed sentiment in [-1, +1].
    - signed stays as-is (clamped)
    - unsigned maps 0..1 to -1..+1 with 0.5 neutral
    """
    if source.kind == "unsigned":
        v = float(source.value)
        v = _clamp(v, 0.0, 1.0)
        return (v - 0.5) * 2.0
    v = float(source.value)
    return _clamp(v, -1.0, 1.0)


def _market_adjustment(market_features: Dict[str, Any]) -> Dict[str, float]:
    """
    Market features should be gentle steering, not a takeover.
    Inputs expected (percent values as numbers):
      mom_1m, mom_3m, mom_15m, mom_1h, vol_z_1h, rv_15m, breakout_15m, streak_1m
    Returns a dict of components in [-1, +1].
    """
    mom_3m = float(market_features.get("mom_3m", 0.0))
    mom_15m = float(market_features.get("mom_15m", 0.0))
    mom_1h = float(market_features.get("mom_1h", 0.0))
    vol_z = float(market_features.get("vol_z_1h", 0.0))
    breakout = float(market_features.get("breakout_15m", 0.0))
    streak = float(market_features.get("streak_1m", 0.0))

    # Convert % momentum to a bounded signed signal. 3% over 15m is strong.
    def mom_sig(pct: float, scale: float) -> float:
        return _clamp(pct / scale, -1.0, 1.0)

    s_mom = 0.45 * mom_sig(mom_3m, 2.0) + 0.35 * mom_sig(mom_15m, 3.0) + 0.20 * mom_sig(mom_1h, 6.0)
    s_vol = _clamp(vol_z / 3.0, -1.0, 1.0)  # vol_z ~3 is loud
    s_break = _clamp(breakout, 0.0, 1.0) * (1.0 if s_mom >= 0 else -1.0)
    s_streak = _clamp(streak / 6.0, -1.0, 1.0)

    return {
        "market_mom": _clamp(s_mom, -1.0, 1.0),
        "market_vol": _clamp(s_vol, -1.0, 1.0),
        "market_breakout": _clamp(s_break, -1.0, 1.0),
        "market_streak": _clamp(s_streak, -1.0, 1.0),
    }


def _confidence_from_coverage(ok_sources: List[SourceValue]) -> float:
    """
    Coverage confidence: rewards multiple independent signals.
    Uses diminishing returns so 12 sources isn't 4x stronger than 3.
    """
    n = len(ok_sources)
    if n <= 0:
        return 0.0
    # Diminishing return curve: 1 - exp(-n/k)
    k = 5.0
    return _clamp(1.0 - math.exp(-(n / k)), 0.0, 1.0)


def compute_final_sentiment(
    symbol: str,
    market_features: Dict[str, Any],
    sources: List[SourceValue],
    now_ts: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Canonical scorer.

    Output fields are stable and should be the only thing alerts + UI rely on:
      score_total_0_100: 0..100
      score_signed: -1..+1
      tier: "T1"|"T2"|"T3" (confidence band, not source-tier)
      confidence_0_1: 0..1 (freshness + coverage + source-level confidence)
      components: breakdown (sentiment vs market)
      sources_used / sources_missing: transparency
    """
    now = float(now_ts or time.time())

    used: List[Dict[str, Any]] = []
    missing: List[str] = []
    ok_sources: List[SourceValue] = []

    for s in sources:
        if not s.ok:
            missing.append(s.name)
            continue
        ok_sources.append(s)

    if not ok_sources:
        # No sources: fall back only to market features, with low confidence.
        comps = _market_adjustment(market_features)
        market_score = (
            0.55 * comps["market_mom"]
            + 0.20 * comps["market_vol"]
            + 0.15 * comps["market_breakout"]
            + 0.10 * comps["market_streak"]
        )
        market_score = _clamp(market_score, -1.0, 1.0)

        score_signed = 0.60 * market_score
        score_0_100 = int(round((score_signed + 1.0) * 50.0))
        confidence = 0.18  # deliberately low if we have no sentiment sources

        return {
            "symbol": symbol,
            "score_signed": score_signed,
            "score_total_0_100": score_0_100,
            "tier": "T3",
            "confidence_0_1": confidence,
            "components": {"sentiment": 0.0, "market": market_score, **comps},
            "sources_used": [],
            "sources_missing": missing,
            "asof_ts": now,
        }

    # 1) Aggregate sentiment sources with tier confidence decay
    weighted_sum = 0.0
    weight_total = 0.0

    for s in ok_sources:
        tier_key, curve = _tier_curve(s)
        base_conf = float(s.meta.get("confidence", 1.0))
        base_conf = _clamp(base_conf, 0.0, 1.0)

        age_s = max(0.0, now - float(s.asof_ts))
        freshness = _half_life_decay(age_s, curve["half_life_s"])
        freshness = max(curve["min_floor"], freshness)

        trust = curve["base_trust"] * base_conf * freshness
        w = float(s.weight) * trust

        v = _normalize_value(s)

        weighted_sum += v * w
        weight_total += abs(w)

        used.append({
            "name": s.name,
            "tier_key": tier_key,
            "value_signed": v,
            "weight": float(s.weight),
            "trust": trust,
            "age_s": age_s,
            "confidence": base_conf,
            "freshness": freshness,
            "asof_ts": float(s.asof_ts),
            "meta": s.meta or {},
        })

    sentiment_score = (weighted_sum / weight_total) if weight_total > 1e-9 else 0.0
    sentiment_score = _clamp(sentiment_score, -1.0, 1.0)

    # 2) Market adjustment (candle-derived)
    comps = _market_adjustment(market_features)
    market_score = (
        0.55 * comps["market_mom"]
        + 0.20 * comps["market_vol"]
        + 0.15 * comps["market_breakout"]
        + 0.10 * comps["market_streak"]
    )
    market_score = _clamp(market_score, -1.0, 1.0)

    # 3) Final mix: sentiment is king, market is steering wheel
    score_signed = _clamp(0.72 * sentiment_score + 0.28 * market_score, -1.0, 1.0)
    score_0_100 = int(round((score_signed + 1.0) * 50.0))

    # 4) Confidence: coverage * average trust (already includes freshness)
    cov = _confidence_from_coverage(ok_sources)

    # Average trust proxy from used list
    trusts = [u["trust"] for u in used if u.get("trust") is not None]
    avg_trust = (sum(trusts) / max(1, len(trusts))) if trusts else 0.0
    avg_trust = _clamp(avg_trust / 1.10, 0.0, 1.0)  # normalize around tier1 base_trust

    confidence = _clamp(0.55 * cov + 0.45 * avg_trust, 0.0, 1.0)

    # 5) Tier (confidence band for UI / alert gating)
    # T1 = high-confidence signal; T2 = decent; T3 = noisy/low-confidence
    if confidence >= 0.72:
        tier = "T1"
    elif confidence >= 0.45:
        tier = "T2"
    else:
        tier = "T3"

    return {
        "symbol": symbol,
        "score_signed": score_signed,
        "score_total_0_100": score_0_100,
        "tier": tier,
        "confidence_0_1": confidence,
        "components": {"sentiment": sentiment_score, "market": market_score, **comps},
        "sources_used": used,
        "sources_missing": missing,
        "asof_ts": now,
    }
