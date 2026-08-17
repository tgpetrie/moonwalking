"""Full-universe live strength ranking for the dashboard.

The score is deliberately descriptive rather than predictive: it ranks the
current tape using only data that is available now.  It never fills missing
market, volume, or alert inputs with fabricated observations.
"""

from __future__ import annotations

import json
from math import isfinite
from typing import Any


LIVE_RANKING_MODEL_VERSION = "live-strength-v1"
LIVE_RANKING_SNAPSHOT_VERSION = "live-strength-v1-snapshot-v2"

# Retention-only fields. They are collected solely so a historical outcome can
# be explained later, and must never reach the public ranking payload — the
# frontend contract predates them. build_live_rankings() therefore omits them
# unless a caller opts in, and public_ranking_rows() strips them if it did.
INTERNAL_RANKING_FIELDS = ("raw_inputs", "scoring_detail")

_STABLECOINS = {
    "USDC",
    "USDT",
    "DAI",
    "PYUSD",
    "GUSD",
    "USDS",
    "EURC",
}

_BULLISH_ALERTS = {
    "moonshot",
    "breakout",
    "building",
    "heating",
    "fomo",
    "bullish_reversal",
    "squeeze",
    "trend_break_up",
    "volume_surge",
}

_BEARISH_ALERTS = {
    "crater",
    "dump",
    "critical",
    "cooling",
    "rapid_drop",
    "reversal_risk",
    "failure",
    "trend_break_down",
}


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _symbol(value: Any) -> str:
    raw = str(value or "").strip().upper()
    for suffix in ("-USD", "-USDT", "-USDC", "-PERP"):
        if raw.endswith(suffix):
            return raw[: -len(suffix)]
    return raw


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _signed_score(value: float | None, full_scale: float) -> float:
    if value is None:
        return 50.0
    return _clamp(50.0 + (50.0 * value / full_scale))


def _label(score: int) -> str:
    if score >= 80:
        return "Leading"
    if score >= 65:
        return "Strong"
    if score >= 55:
        return "Building"
    if score >= 45:
        return "Mixed"
    if score >= 35:
        return "Weak"
    return "Fading"


def public_ranking_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return copies of ``rows`` with retention-only fields removed.

    Used on the publish path so enabling internal feature collection for
    retention never changes the shape of the payload the frontend receives.
    The originals are left intact for the snapshot writer.
    """
    return [
        {key: value for key, value in row.items() if key not in INTERNAL_RANKING_FIELDS}
        for row in rows
    ]


def build_feature_snapshot(
    ranking_row: dict[str, Any],
    captured_ts: int,
) -> tuple[str, str] | tuple[None, None]:
    """Return (schema_version, json_text) capturing a full point-in-time feature state.

    ``captured_ts`` must be the instant the ranking calculation that produced
    ``ranking_row`` was started — never a later observer timestamp, or the
    stored record would misdate the state it claims to describe.

    Serialised with sort_keys=True so the same input always produces the same bytes.
    Only call with a row that was returned by build_live_rankings() and has already
    had live_rank and universe_size attached (i.e. after the post-sort loop).

    Returns (None, None) when the row was built without internal feature
    collection. A snapshot missing raw_inputs/scoring_detail cannot explain an
    outcome, so it is refused outright rather than stored half-empty.
    """
    if any(field not in ranking_row for field in INTERNAL_RANKING_FIELDS):
        return None, None
    snapshot = {
        "schema_version": LIVE_RANKING_SNAPSHOT_VERSION,
        "captured_ts": captured_ts,
        "model_version": ranking_row.get("model_version"),
        "live_score": ranking_row.get("live_score"),
        "live_label": ranking_row.get("live_label"),
        "live_rank": ranking_row.get("live_rank"),
        "universe_size": ranking_row.get("universe_size"),
        "data_quality": ranking_row.get("data_quality"),
        "observed_inputs": ranking_row.get("observed_inputs"),
        "expected_inputs": ranking_row.get("expected_inputs"),
        "live_risks": ranking_row.get("live_risks"),
        "components": ranking_row.get("live_components"),
        "raw_inputs": ranking_row.get("raw_inputs"),
        "scoring_detail": ranking_row.get("scoring_detail"),
    }
    return LIVE_RANKING_SNAPSHOT_VERSION, json.dumps(snapshot, sort_keys=True)


def _alert_direction(alert: dict[str, Any]) -> int:
    kind = (
        str(
            alert.get("type_key")
            or alert.get("type")
            or alert.get("class_key")
            or alert.get("category")
            or ""
        )
        .strip()
        .lower()
        .replace(" ", "_")
    )
    if kind in _BULLISH_ALERTS:
        return 1
    if kind in _BEARISH_ALERTS:
        return -1

    evidence = alert.get("evidence") if isinstance(alert.get("evidence"), dict) else {}
    for key in ("pct_1m", "pct_3m", "pct_1h", "pct"):
        value = _finite(evidence.get(key))
        if value is not None and value != 0:
            return 1 if value > 0 else -1
    return 0


def build_live_rankings(
    *,
    price_snapshot: dict[str, dict[str, Any]] | None,
    volume_snapshot: dict[str, dict[str, Any]] | None = None,
    context_snapshot: dict[str, dict[str, Any]] | None = None,
    alerts: list[dict[str, Any]] | None = None,
    include_internal_features: bool = False,
    volatility_snapshot: dict[str, dict[str, Any]] | None = None,
    liquidity_snapshot: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return strongest-to-weakest live setup rows for the tracked universe.

    ``include_internal_features`` adds the retention-only ``raw_inputs`` and
    ``scoring_detail`` keys.  It changes nothing that is scored: both are built
    from values the scorer has already computed.  It defaults to False so the
    published payload keeps its original shape.
    """

    prices = price_snapshot if isinstance(price_snapshot, dict) else {}
    volumes = volume_snapshot if isinstance(volume_snapshot, dict) else {}
    contexts = context_snapshot if isinstance(context_snapshot, dict) else {}
    alert_rows = alerts if isinstance(alerts, list) else []
    volatilities = volatility_snapshot if isinstance(volatility_snapshot, dict) else {}
    liquidities = liquidity_snapshot if isinstance(liquidity_snapshot, dict) else {}

    alert_counts: dict[str, dict[str, int]] = {}
    for alert in alert_rows:
        if not isinstance(alert, dict):
            continue
        sym = _symbol(alert.get("symbol") or alert.get("product_id"))
        if not sym:
            continue
        direction = _alert_direction(alert)
        counts = alert_counts.setdefault(sym, {"bullish": 0, "bearish": 0})
        if direction > 0:
            counts["bullish"] += 1
        elif direction < 0:
            counts["bearish"] += 1

    rankings: list[dict[str, Any]] = []
    for raw_symbol, raw_row in prices.items():
        sym = _symbol(raw_symbol)
        if not sym or sym in _STABLECOINS or not isinstance(raw_row, dict):
            continue

        volume_row = volumes.get(sym) if isinstance(volumes.get(sym), dict) else {}
        context_row = contexts.get(sym) if isinstance(contexts.get(sym), dict) else {}
        one_min = _finite(raw_row.get("pct_1m"))
        three_min = _finite(raw_row.get("pct_3m"))
        one_hour = _finite(raw_row.get("pct_1h"))
        volume_pct = _finite(
            volume_row.get("volume_change_1h_pct")
            if volume_row
            else raw_row.get("volume_change_1h_pct")
        )
        streak = _finite(raw_row.get("trend_streak") or raw_row.get("streak"))

        one_min_score = _signed_score(one_min, 1.25)
        three_min_score = _signed_score(three_min, 3.0)
        one_hour_score = _signed_score(one_hour, 6.0)
        volume_score = _signed_score(volume_pct, 200.0)

        directions = [
            value for value in (one_min, three_min) if value is not None and value != 0
        ]
        if len(directions) >= 2 and all(value > 0 for value in directions):
            confirmation_score = 80.0
        elif len(directions) >= 2 and all(value < 0 for value in directions):
            confirmation_score = 20.0
        elif len(directions) >= 2:
            confirmation_score = 35.0
        elif directions:
            confirmation_score = 60.0 if directions[0] > 0 else 40.0
        else:
            confirmation_score = 50.0

        counts = alert_counts.get(sym, {"bullish": 0, "bearish": 0})
        confirmation_score = _clamp(
            confirmation_score
            + min(18, counts["bullish"] * 6)
            - min(18, counts["bearish"] * 6)
        )
        spot_pressure = str(context_row.get("spot_pressure") or "neutral").lower()
        market_relation = str(context_row.get("market_relation") or "neutral").lower()
        if spot_pressure == "buying":
            confirmation_score += 10.0
        elif spot_pressure == "selling":
            confirmation_score -= 10.0
        if market_relation == "breaking_away":
            confirmation_score += 7.0 if (three_min or one_min or 0) > 0 else -7.0
        confirmation_score = _clamp(confirmation_score)

        dominant_move = three_min if three_min not in (None, 0) else one_min
        dominant_sign = (
            1 if (dominant_move or 0) > 0 else -1 if (dominant_move or 0) < 0 else 0
        )
        persistence_score = 50.0
        if streak is not None and dominant_sign:
            persistence_score = _clamp(
                50.0 + dominant_sign * min(5.0, abs(streak)) * 9.0
            )

        weighted = (
            one_min_score * 0.20
            + three_min_score * 0.25
            + one_hour_score * 0.15
            + volume_score * 0.15
            + confirmation_score * 0.15
            + persistence_score * 0.10
        )

        chase_penalty = 0.0
        if one_min is not None and one_min > 1.6:
            chase_penalty += min(7.0, (one_min - 1.6) * 2.5)
        if three_min is not None and three_min > 4.0:
            chase_penalty += min(7.0, (three_min - 4.0) * 1.5)
        liquidity = str(context_row.get("liquidity") or "normal").lower()
        if liquidity == "thin":
            chase_penalty += 5.0
        elif liquidity == "wide":
            chase_penalty += 2.0

        raw_score = _clamp(weighted - chase_penalty, 1.0, 99.0)
        observed = sum(
            value is not None
            for value in (one_min, three_min, one_hour, volume_pct, streak)
        )
        if counts["bullish"] or counts["bearish"]:
            observed += 1
        if (
            spot_pressure != "neutral"
            or market_relation != "neutral"
            or liquidity != "normal"
        ):
            observed += 1
        expected_inputs = 6
        observed_inputs = min(expected_inputs, observed)
        data_quality = min(100, int(round((observed_inputs / expected_inputs) * 100.0)))
        # Sparse evidence must not beat a genuinely aligned setup simply because
        # one available metric is extreme. Pull incomplete rows toward neutral;
        # keep a small floor so a real early move can still surface as Building.
        reliability = max(0.35, data_quality / 100.0)
        score = int(round(_clamp(50.0 + ((raw_score - 50.0) * reliability), 1.0, 99.0)))

        reasons: list[str] = []
        if three_min is not None:
            reasons.append(f"3m {three_min:+.2f}%")
        if one_min is not None:
            reasons.append(f"1m {one_min:+.2f}%")
        if volume_pct is not None:
            reasons.append(f"1h volume {volume_pct:+.0f}%")
        if spot_pressure == "buying":
            reasons.append("spot buying")
        elif spot_pressure == "selling":
            reasons.append("spot selling")
        if market_relation == "breaking_away":
            reasons.append("breaking away from market")
        if counts["bullish"]:
            reasons.append(
                f"{counts['bullish']} bullish alert{'s' if counts['bullish'] != 1 else ''}"
            )
        if counts["bearish"]:
            reasons.append(
                f"{counts['bearish']} bearish alert{'s' if counts['bearish'] != 1 else ''}"
            )
        if streak is not None and streak > 1:
            reasons.append(f"{int(streak)}x tape hold")

        risks: list[str] = []
        if chase_penalty > 0:
            risks.append("extended move")
        if one_min is not None and three_min is not None and one_min * three_min < 0:
            risks.append("timeframes disagree")
        if (
            volume_pct is not None
            and volume_pct < 0
            and (three_min or one_min or 0) > 0
        ):
            risks.append("volume fading")
        if liquidity == "thin":
            risks.append("thin liquidity")
        elif liquidity == "wide":
            risks.append("wide spread")

        row = {
            "symbol": sym,
            "product_id": f"{sym}-USD",
            "live_score": score,
            "live_label": _label(score),
            "data_quality": data_quality,
            "observed_inputs": observed_inputs,
            "expected_inputs": expected_inputs,
            "live_reasons": reasons[:4],
            "live_risks": risks[:3],
            "live_components": {
                "momentum_1m": round(one_min_score, 1),
                "momentum_3m": round(three_min_score, 1),
                "trend_1h": round(one_hour_score, 1),
                "volume": round(volume_score, 1),
                "confirmation": round(confirmation_score, 1),
                "persistence": round(persistence_score, 1),
            },
            "model_version": LIVE_RANKING_MODEL_VERSION,
            "price": _finite(raw_row.get("price")),
        }
        if include_internal_features:
            # Matching inputs for the control benchmark. Every liquidity
            # candidate is recorded rather than one being chosen here: which is
            # usable depends on measured universe coverage and post-match
            # balance, and that selection is made by the dry-run, never inline
            # and never with outcomes in view.
            vol_row = volatilities.get(sym) or volatilities.get(f"{sym}-USD") or {}
            liq_row = liquidities.get(f"{sym}-USD") or liquidities.get(sym) or {}
            row["raw_inputs"] = {
                "pct_1m": one_min,
                "pct_3m": three_min,
                "pct_1h": one_hour,
                "volume_change_1h_pct": volume_pct,
                "trend_streak": streak,
                "bullish_alerts": counts["bullish"],
                "bearish_alerts": counts["bearish"],
                "spot_pressure": spot_pressure,
                "market_relation": market_relation,
                # Categorical liquidity bucket: universe-wide but coarse.
                "liquidity": liquidity,
                # Quantitative liquidity: precise but far narrower coverage.
                "quote_volume_usd": liq_row.get("quote_volume_usd"),
                "quote_volume_age_seconds": liq_row.get("age_seconds"),
                "quote_volume_minute_coverage": liq_row.get("minute_coverage"),
                "realized_volatility_pct_hour": vol_row.get("volatility_pct_hour"),
                "realized_volatility_observations": vol_row.get("observations"),
                "realized_volatility_staleness_seconds": vol_row.get(
                    "staleness_seconds"
                ),
                # None when volatility is available; a reason string otherwise,
                # so unavailable is never confused with low.
                "realized_volatility_unavailable_reason": vol_row.get("reason"),
            }
            row["scoring_detail"] = {
                "weighted_before_penalty": round(weighted, 4),
                "chase_penalty": round(chase_penalty, 4),
                "raw_score": round(float(raw_score), 4),
                "reliability": round(reliability, 6),
            }
        rankings.append(row)

    rankings.sort(
        key=lambda row: (
            -row["live_score"],
            -row["data_quality"],
            row["symbol"],
        )
    )
    universe_size = len(rankings)
    for index, row in enumerate(rankings, start=1):
        row["live_rank"] = index
        row["universe_size"] = universe_size
    return rankings
