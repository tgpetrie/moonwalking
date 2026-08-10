"""
interpretation_engine.py

Deterministic interpretation layer for intelligence events.
No LLM, no network I/O, pure functions only.

Contract:
  - Every claim in interpretation must be backed by a field in evidence.
  - Never speculate ("smart money", "whales") without evidence support.
  - Degrades gracefully: missing evidence → lower score, fewer factors.
  - add_interpretation() is the only public API.

Production categories (fully validated against live evidence payloads):
  MOONSHOT, CRATER, BREAKOUT, DUMP  (impulse family)
  WHALE_MOVE
  COIN_REVERSAL_UP, COIN_REVERSAL_DOWN
  COIN_LIQUIDITY_SHOCK

Experimental categories (implemented, evidence-gated, lower validation coverage):
  STEALTH_MOVE, COIN_PERSISTENT_GAINER/LOSER, COIN_TREND_BREAK_UP/DOWN,
  COIN_SQUEEZE_BREAK, COIN_EXHAUSTION_TOP/BOTTOM, COIN_FAKEOUT,
  COIN_VOLATILITY_EXPANSION

The 'interpretation_support' field in each result signals this to consumers.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _f(evidence: dict, *keys: str, default: float | None = None) -> float | None:
    """Return the first finite numeric value found across the given evidence keys."""
    for k in keys:
        v = evidence.get(k)
        if v is not None:
            try:
                n = float(v)
                if n == n and n not in (float("inf"), float("-inf")):
                    return n
            except (TypeError, ValueError):
                pass
    return default


def _clamp(n: int | float, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(n)))


def _vol_label(pct: float) -> str | None:
    if pct >= 200:
        return "extremely elevated"
    if pct >= 100:
        return "significantly above baseline"
    if pct >= 50:
        return "above baseline"
    if pct >= 20:
        return "moderately above baseline"
    return None


def _magnitude_verb(pct: float | None, is_up: bool) -> str:
    if pct is None:
        return "moved"
    abs_pct = abs(pct)
    if abs_pct >= 12:
        return "surged" if is_up else "crashed"
    if abs_pct >= 6:
        return "broke out" if is_up else "dumped"
    if abs_pct >= 3:
        return "moved" if is_up else "dropped"
    return "shifted"


# ---------------------------------------------------------------------------
# PRODUCTION: Impulse family — MOONSHOT, CRATER, BREAKOUT, DUMP
#
# Evidence: window, pct, pct_1m, pct_3m, pct_1h, price
# ---------------------------------------------------------------------------


def _interpret_impulse(type_key: str, direction: str, ev: dict) -> dict:
    is_moon = type_key in ("MOONSHOT", "CRATER")
    is_up = direction == "up"

    pct = _f(ev, "pct")
    pct_1m = _f(ev, "pct_1m")
    pct_3m = _f(ev, "pct_3m")
    pct_1h = _f(ev, "pct_1h")
    window = str(ev.get("window") or "").strip()

    pct_ref = next((v for v in (pct, pct_1m, pct_3m) if v is not None), None)

    supporting: list[str] = []
    caution: list[str] = []
    score = 40 if is_moon else 30

    if pct_ref is not None:
        abs_pct = abs(pct_ref)
        win_text = f" in {window}" if window else ""
        if abs_pct >= 12:
            score += 20
            supporting.append(f"Extreme move: {pct_ref:+.1f}%{win_text}")
        elif abs_pct >= 6:
            score += 15
            supporting.append(f"Large move: {pct_ref:+.1f}%{win_text}")
        elif abs_pct >= 3:
            score += 8
            supporting.append(f"Notable move: {pct_ref:+.1f}%{win_text}")
        else:
            score += 3

    aligned: list[str] = []
    conflicting: list[str] = []
    for label, val in [("1m", pct_1m), ("3m", pct_3m), ("1h", pct_1h)]:
        if val is not None and label != window:
            if (is_up and val > 0) or (not is_up and val < 0):
                aligned.append(label)
            elif (is_up and val < -1.0) or (not is_up and val > 1.0):
                conflicting.append(label)

    if len(aligned) >= 2:
        score += 20
        supporting.append(f"Momentum confirmed across {', '.join(aligned)} windows")
    elif len(aligned) == 1:
        score += 10
        supporting.append(f"Momentum aligned on {aligned[0]} window")

    if conflicting:
        score -= 10
        s = "s" if len(conflicting) > 1 else ""
        caution.append(f"Counter-trend in {', '.join(conflicting)} window{s}")

    if window == "1m" and pct_ref is not None and abs(pct_ref) >= 3:
        score += 10
        supporting.append("Move in 1-minute window — rapid timeframe")
    elif window == "3m":
        score += 5

    if pct_1h is not None:
        if is_up and pct_1h >= 15:
            caution.append("1h move already extended — potential for pullback")
        elif not is_up and pct_1h <= -15:
            caution.append("1h decline already extended — potential for bounce")

    verb = _magnitude_verb(pct_ref, is_up)
    pct_text = f" {pct_ref:+.1f}%" if pct_ref is not None else ""
    win_text = f" in {window}" if window else ""
    momentum_word = "confirmed" if aligned else "limited"
    summary = (
        f"Price {verb}{pct_text}{win_text} with {momentum_word} multi-window momentum."
    )

    inv_dir = "below" if is_up else "above"
    invalidation = (
        f"Move reverses {inv_dir} the {window} open"
        if window
        else "Price retreats to pre-event level"
    )

    return {
        "summary": summary,
        "supportingFactors": supporting,
        "cautionFactors": caution,
        "invalidationCondition": invalidation,
        "confidence": _clamp(score),
        "confidenceFactors": supporting[:3],
    }


# ---------------------------------------------------------------------------
# PRODUCTION: WHALE_MOVE
#
# Evidence: z_vol, vol_ratio, candle_pct, volume_change_1h_pct,
#           cluster_z, latest_vol, median_vol, baseline_ready, direction
# ---------------------------------------------------------------------------


def _interpret_whale(direction: str, ev: dict) -> dict:
    z_vol = _f(ev, "z_vol")
    candle_pct = _f(ev, "candle_pct")
    vol1h_pct = _f(ev, "volume_change_1h_pct")
    cluster_z = _f(ev, "cluster_z")
    baseline_ready = bool(ev.get("baseline_ready"))

    supporting: list[str] = []
    caution: list[str] = []
    score = 35

    if z_vol is not None:
        if z_vol >= 5.0:
            score += 25
            supporting.append(f"Volume deviation extreme: {z_vol:.1f}σ above average")
        elif z_vol >= 3.0:
            score += 18
            supporting.append(
                f"Volume deviation significant: {z_vol:.1f}σ above average"
            )
        elif z_vol >= 2.0:
            score += 10
            supporting.append(f"Volume elevated: {z_vol:.1f}σ")
        else:
            score += 3

    if cluster_z is not None and cluster_z >= 1.5:
        score += 12
        supporting.append(
            f"Cluster confirmation: sustained {cluster_z:.1f}σ multi-minute flow"
        )

    if candle_pct is not None:
        abs_pct = abs(candle_pct)
        dir_word = "rising" if candle_pct > 0 else "falling"
        if abs_pct >= 2.0:
            score += 15
            supporting.append(f"Price {dir_word} {abs_pct:.1f}% alongside volume surge")
        elif abs_pct >= 0.5:
            score += 8
            supporting.append(f"Price {dir_word} {abs_pct:.2f}% on volume")
        elif direction != "absorption":
            caution.append(
                "Price flat despite volume spike — possible absorption or slippage"
            )

    if baseline_ready:
        score += 8
        supporting.append(
            "Volume baseline established — deviation is statistically reliable"
        )
    else:
        score -= 10
        caution.append("Volume baseline still warming — comparison may be premature")

    if vol1h_pct is not None:
        lbl = _vol_label(vol1h_pct)
        if lbl:
            supporting.append(f"Hourly volume context: {lbl} ({vol1h_pct:.0f}%)")

    if direction == "absorption":
        caution.append("High volume with flat price — direction not yet established")
        summary = (
            "Unusual volume concentration with price holding steady — "
            "possible large-order absorption."
        )
    else:
        accum = "accumulation" if direction == "up" else "distribution"
        z_text = f"{z_vol:.1f}σ" if z_vol is not None else "elevated"
        summary = (
            f"Unusual volume surge ({z_text}) consistent with large-order {accum}."
        )

    return {
        "summary": summary,
        "supportingFactors": supporting,
        "cautionFactors": caution,
        "invalidationCondition": "Volume returns to baseline without price follow-through",
        "confidence": _clamp(score),
        "confidenceFactors": supporting[:3],
    }


# ---------------------------------------------------------------------------
# PRODUCTION: COIN_REVERSAL_UP, COIN_REVERSAL_DOWN
#
# Evidence: pct_1m, pct_3m, magnitude_bucket, price_now, price_ref
# ---------------------------------------------------------------------------


def _interpret_reversal(type_key: str, direction: str, ev: dict) -> dict:
    is_up = "UP" in type_key or direction == "up"
    pct_1m = _f(ev, "pct_1m")
    pct_3m = _f(ev, "pct_3m")

    supporting: list[str] = []
    caution: list[str] = []
    score = 30

    # magnitude_bucket is a float from _bucket_mag(pct_1m, 0.5) in production:
    # round(abs(pct_1m) / 0.5) * 0.5 — typical values: 0.5, 1.0, 1.5, 2.0, ...
    mag_val = _f(ev, "magnitude_bucket")
    if mag_val is not None:
        if mag_val >= 2.0:
            score += 20
            supporting.append(f"Strong reversal: {mag_val:.1f}% magnitude")
        elif mag_val >= 1.0:
            score += 12
            supporting.append(f"Moderate reversal: {mag_val:.1f}% magnitude")
        elif mag_val > 0:
            score += 5
            supporting.append(f"Developing reversal: {mag_val:.1f}% magnitude")

    if pct_1m is not None:
        dir_ok = (is_up and pct_1m > 0.5) or (not is_up and pct_1m < -0.5)
        dir_bad = (is_up and pct_1m < -0.3) or (not is_up and pct_1m > 0.3)
        if dir_ok:
            score += 20
            dir_word = "positive" if is_up else "negative"
            supporting.append(f"1m price confirms {dir_word} direction: {pct_1m:+.2f}%")
        elif dir_bad:
            score -= 10
            caution.append(f"1m price contradicts reversal direction: {pct_1m:+.2f}%")

    if pct_3m is not None:
        if (is_up and pct_3m > 0) or (not is_up and pct_3m < 0):
            score += 15
            supporting.append(f"3m trend aligned: {pct_3m:+.2f}%")
        else:
            score -= 5
            caution.append(f"3m trend still counter-directional: {pct_3m:+.2f}%")

    caution.append("Reversals can be fakeouts — confirm on next 1-3 candles")

    dir_text = "upward" if is_up else "downward"
    mag_text = f" ({mag_val:.1f}% magnitude)" if mag_val is not None else ""
    summary = f"Potential {dir_text} reversal detected{mag_text}."

    invalidation = (
        "Fails to hold and reverts to prior downtrend"
        if is_up
        else "Recovers back into prior uptrend without follow-through selling"
    )

    return {
        "summary": summary,
        "supportingFactors": supporting,
        "cautionFactors": caution,
        "invalidationCondition": invalidation,
        "confidence": _clamp(score),
        "confidenceFactors": supporting[:3],
    }


# ---------------------------------------------------------------------------
# PRODUCTION: COIN_LIQUIDITY_SHOCK
#
# Evidence: vol_z, vol_1m, avg_1m, std_1m, pct_1m, pct_3m, baseline_samples
# ---------------------------------------------------------------------------


def _interpret_liquidity_shock(ev: dict) -> dict:
    vol_z = _f(ev, "vol_z")
    pct_1m = _f(ev, "pct_1m")
    pct_3m = _f(ev, "pct_3m")
    baseline_samples = _f(ev, "baseline_samples")

    supporting: list[str] = []
    caution: list[str] = []
    score = 30

    if vol_z is not None:
        if vol_z >= 5.0:
            score += 25
            supporting.append(f"Extreme liquidity event: {vol_z:.1f}σ volume spike")
        elif vol_z >= 3.0:
            score += 18
            supporting.append(f"Significant liquidity surge: {vol_z:.1f}σ")
        elif vol_z >= 2.0:
            score += 10
            supporting.append(f"Elevated 1m volume: {vol_z:.1f}σ above baseline")

    if baseline_samples is not None:
        samples = int(baseline_samples)
        if samples >= 20:
            score += 15
            supporting.append(f"Statistically robust baseline: {samples} samples")
        elif samples >= 10:
            score += 8
            supporting.append(f"Baseline has {samples} samples")
        else:
            score -= 10
            caution.append(f"Thin baseline ({samples} samples) — z-score less reliable")

    if pct_1m is not None:
        abs_pct = abs(pct_1m)
        if abs_pct >= 2.0:
            score += 20
            supporting.append(f"Strong price reaction: {pct_1m:+.2f}% in 1m")
        elif abs_pct >= 0.5:
            score += 10
            supporting.append(f"Price reacted: {pct_1m:+.2f}% in 1m")
        else:
            caution.append("Volume spike without significant 1m price reaction")

    if pct_3m is not None and abs(pct_3m) >= 2.0:
        supporting.append(f"3m context: {pct_3m:+.2f}%")
        score += 5

    z_text = f"{vol_z:.1f}σ" if vol_z is not None else "unusual"
    summary = (
        f"Sudden liquidity surge ({z_text} volume spike) — "
        "potential large-order or demand-shock event."
    )

    return {
        "summary": summary,
        "supportingFactors": supporting,
        "cautionFactors": caution,
        "invalidationCondition": (
            "Volume normalizes within 1-2 minutes without sustained price impact"
        ),
        "confidence": _clamp(score),
        "confidenceFactors": supporting[:3],
    }


# ---------------------------------------------------------------------------
# EXPERIMENTAL: STEALTH_MOVE
#
# Evidence: pct_3m, abs_pct_3m, volume_change_1h_pct, baseline_ready
# ---------------------------------------------------------------------------


def _interpret_stealth(direction: str, ev: dict) -> dict:
    pct_3m = _f(ev, "pct_3m")
    vol1h_pct = _f(ev, "volume_change_1h_pct")
    baseline_ready = bool(ev.get("baseline_ready"))

    supporting: list[str] = []
    caution: list[str] = []
    score = 30

    if pct_3m is not None:
        abs_pct = abs(pct_3m)
        if abs_pct >= 2:
            score += 15
            supporting.append(f"Meaningful 3m move: {pct_3m:+.2f}%")
        elif abs_pct >= 1:
            score += 8
            supporting.append(f"Moderate 3m move: {pct_3m:+.2f}%")

    if vol1h_pct is not None:
        lbl = _vol_label(vol1h_pct)
        if lbl:
            score += 15
            supporting.append(
                f"Volume support: {lbl} ({vol1h_pct:.0f}% above prior hour)"
            )
        else:
            caution.append("Volume increase modest — move may lack broad participation")

    if baseline_ready:
        score += 8
        supporting.append("Volume baseline established")
    else:
        score -= 10
        caution.append("Volume baseline still warming")

    caution.append("Stealth moves can fade quickly without broadening participation")

    # Backend emits direction as "accumulation" or "distribution" directly
    if direction in ("accumulation", "distribution"):
        accum = direction
    else:
        accum = "accumulation" if direction == "up" else "distribution"
    pct_text = f"{pct_3m:+.2f}% (3m)" if pct_3m is not None else "a quiet move"
    summary = f"Quiet {accum} detected: {pct_text} with elevated volume and muted price action."

    return {
        "summary": summary,
        "supportingFactors": supporting,
        "cautionFactors": caution,
        "invalidationCondition": "Volume recedes without further directional price progress",
        "confidence": _clamp(score),
        "confidenceFactors": supporting[:3],
    }


# ---------------------------------------------------------------------------
# EXPERIMENTAL: COIN_PERSISTENT_GAINER, COIN_PERSISTENT_LOSER
#
# Evidence: streak, rank, pct_3m, polls
# ---------------------------------------------------------------------------


def _interpret_persistent(type_key: str, ev: dict) -> dict:
    is_gainer = "GAINER" in type_key
    streak = _f(ev, "streak")
    rank = _f(ev, "rank")
    pct_3m = _f(ev, "pct_3m")

    supporting: list[str] = []
    caution: list[str] = []
    score = 35

    if streak is not None:
        s = int(streak)
        dir_word = "up" if is_gainer else "down"
        if s >= 8:
            score += 25
            supporting.append(f"Persistent {dir_word}trend: {s} consecutive polls")
        elif s >= 5:
            score += 15
            supporting.append(f"Strong streak: {s} consecutive {dir_word} polls")
        elif s >= 3:
            score += 8
            supporting.append(f"Developing streak: {s} consecutive periods")

    if rank is not None:
        r = int(rank)
        side = "gainer" if is_gainer else "loser"
        if r <= 3:
            score += 20
            supporting.append(f"Top-{r} ranked {side} in tracked universe")
        elif r <= 10:
            score += 12
            supporting.append(f"Ranked #{r} {side} in tracked universe")

    if pct_3m is not None:
        abs_pct = abs(pct_3m)
        if abs_pct >= 3:
            score += 15
            supporting.append(f"3m cumulative move confirms trend: {pct_3m:+.2f}%")
        elif abs_pct >= 1.5:
            score += 8
            supporting.append(f"3m price confirms: {pct_3m:+.2f}%")
        else:
            caution.append(
                f"3m price move modest ({pct_3m:+.2f}%) relative to streak length"
            )

    if is_gainer:
        caution.append(
            "Persistent gainers can attract profit-taking — watch for volume fade"
        )
    else:
        caution.append(
            "Persistent losers can find relief — watch for oversold bounce signals"
        )

    rank_text = f"top-{int(rank)} " if rank is not None and rank <= 10 else ""
    streak_text = str(int(streak)) if streak is not None else "multiple"
    dir_word = "up" if is_gainer else "down"
    action = "outperforming" if is_gainer else "underperforming"
    summary = (
        f"Sustained {action}: ranked {rank_text}{'gainer' if is_gainer else 'loser'} "
        f"with {streak_text} consecutive {dir_word}-polls."
    )

    return {
        "summary": summary,
        "supportingFactors": supporting,
        "cautionFactors": caution,
        "invalidationCondition": "Streak breaks and rank drops out of top tier",
        "confidence": _clamp(score),
        "confidenceFactors": supporting[:3],
    }


# ---------------------------------------------------------------------------
# EXPERIMENTAL: COIN_TREND_BREAK_UP, COIN_TREND_BREAK_DOWN
#
# Evidence: ema_fast, ema_slow, diff, prev_diff, pct_1m, pct_3m, pct_1h, vol_ratio
# ---------------------------------------------------------------------------


def _interpret_trend_break(type_key: str, direction: str, ev: dict) -> dict:
    is_up = "UP" in type_key or direction == "up"
    ema_fast = _f(ev, "ema_fast")
    ema_slow = _f(ev, "ema_slow")
    diff = _f(ev, "diff")
    vol_ratio = _f(ev, "vol_ratio")
    pct_1m = _f(ev, "pct_1m")
    pct_1h = _f(ev, "pct_1h")

    supporting: list[str] = []
    caution: list[str] = []
    score = 35

    if diff is not None:
        abs_diff = abs(diff)
        dir_word = "bullish" if is_up else "bearish"
        if abs_diff >= 0.3:
            score += 20
            supporting.append(f"Decisive EMA cross: spread {diff:+.3f}% ({dir_word})")
        elif abs_diff >= 0.1:
            score += 12
            supporting.append(f"EMA cross confirmed: spread {diff:+.3f}%")
        else:
            score += 5
            caution.append(f"EMA spread tight ({diff:+.4f}%) — cross may be noise")

    if vol_ratio is not None:
        if vol_ratio >= 2.0:
            score += 20
            supporting.append(
                f"Volume {vol_ratio:.1f}x baseline — strong participation on cross"
            )
        elif vol_ratio >= 1.3:
            score += 12
            supporting.append(
                f"Volume {vol_ratio:.1f}x baseline — above-average participation"
            )
        else:
            caution.append(
                f"Volume ratio low ({vol_ratio:.1f}x) — cross may not sustain"
            )

    if pct_1h is not None:
        if (is_up and pct_1h > 0) or (not is_up and pct_1h < 0):
            score += 15
            supporting.append(f"1h trend aligned with cross: {pct_1h:+.2f}%")
        else:
            score -= 8
            caution.append(f"1h trend counter to cross direction: {pct_1h:+.2f}%")

    if pct_1m is not None:
        if (is_up and pct_1m > 0) or (not is_up and pct_1m < 0):
            score += 8
            supporting.append(f"1m price confirms: {pct_1m:+.2f}%")

    dir_text = "bullish" if is_up else "bearish"
    ema_text = ""
    if ema_fast is not None and ema_slow is not None:
        ema_text = f" (fast {ema_fast:.4f} vs slow {ema_slow:.4f})"
    summary = f"EMA crossover signals {dir_text} trend shift{ema_text}."

    inv_dir = "below" if is_up else "above"
    invalidation = f"Fast EMA crosses back {inv_dir} slow EMA without follow-through"

    return {
        "summary": summary,
        "supportingFactors": supporting,
        "cautionFactors": caution,
        "invalidationCondition": invalidation,
        "confidence": _clamp(score),
        "confidenceFactors": supporting[:3],
    }


# ---------------------------------------------------------------------------
# EXPERIMENTAL: COIN_SQUEEZE_BREAK
#
# Evidence: vol_jump_ratio, vol_percentile, break_change_1m, pct_3m, pct_1h
# ---------------------------------------------------------------------------


def _interpret_squeeze_break(ev: dict) -> dict:
    vol_jump = _f(ev, "vol_jump_ratio")
    vol_pct = _f(ev, "vol_percentile")
    break_pct = _f(ev, "break_change_1m")

    supporting: list[str] = []
    caution: list[str] = []
    score = 30

    if vol_jump is not None:
        if vol_jump >= 4.0:
            score += 25
            supporting.append(f"Volume exploded: {vol_jump:.1f}x prior 10m window")
        elif vol_jump >= 2.5:
            score += 18
            supporting.append(f"Volume surged: {vol_jump:.1f}x prior window")
        elif vol_jump >= 1.5:
            score += 10
            supporting.append(f"Volume elevated: {vol_jump:.1f}x prior window")
        else:
            caution.append("Volume expansion modest for a squeeze break")

    if vol_pct is not None:
        # Backend emits vol_percentile as a 0.0–1.0 fraction from _percentile_rank()
        pct_display = int(vol_pct * 100)
        if vol_pct >= 0.85:
            score += 20
            supporting.append(
                f"Rare volume event: {pct_display}th percentile of 10m windows"
            )
        elif vol_pct >= 0.70:
            score += 12
            supporting.append(f"Elevated volume: {pct_display}th percentile")
        else:
            caution.append(
                f"Volume percentile {pct_display} — not historically unusual"
            )

    if break_pct is not None:
        abs_pct = abs(break_pct)
        if abs_pct >= 2.0:
            score += 20
            supporting.append(f"Strong break candle: {break_pct:+.2f}% in 1m")
        elif abs_pct >= 0.5:
            score += 10
            supporting.append(f"Price confirmed break: {break_pct:+.2f}% in 1m")
        else:
            caution.append("Break candle small — possible false break")

    jump_text = f"{vol_jump:.1f}x" if vol_jump is not None else "sudden"
    break_text = (
        f" with {break_pct:+.2f}% break candle" if break_pct is not None else ""
    )
    summary = (
        f"Squeeze break: {jump_text} volume surge{break_text} "
        "after low-activity compression."
    )

    return {
        "summary": summary,
        "supportingFactors": supporting,
        "cautionFactors": caution,
        "invalidationCondition": (
            "Volume recedes to baseline within 1-2 minutes with no price continuation"
        ),
        "confidence": _clamp(score),
        "confidenceFactors": supporting[:3],
    }


# ---------------------------------------------------------------------------
# EXPERIMENTAL: COIN_EXHAUSTION_TOP, COIN_EXHAUSTION_BOTTOM
#
# Evidence: streak_len, pct_1m, pct_3m, volume_ratio, volume_drop, fakeout_hit
# ---------------------------------------------------------------------------


def _interpret_exhaustion(type_key: str, ev: dict) -> dict:
    is_top = "TOP" in type_key
    streak_len = _f(ev, "streak_len")
    pct_1m = _f(ev, "pct_1m")
    volume_drop = bool(ev.get("volume_drop"))
    fakeout_hit = bool(ev.get("fakeout_hit"))

    supporting: list[str] = []
    caution: list[str] = []
    score = 25

    if streak_len is not None:
        s = int(streak_len)
        dir_word = "up" if is_top else "down"
        if s >= 8:
            score += 25
            supporting.append(f"Exhaustion after {s} consecutive {dir_word} candles")
        elif s >= 5:
            score += 15
            supporting.append(f"Extended {s}-candle streak before signal")
        elif s >= 3:
            score += 8
            supporting.append(f"Short {s}-candle streak before exhaustion")

    if volume_drop:
        score += 20
        supporting.append("Volume declining on latest candle — participation fading")
    else:
        caution.append("Volume not yet confirming exhaustion")

    if fakeout_hit:
        score += 15
        supporting.append(
            "Prior fakeout level tagged — possible trap for late entrants"
        )

    if pct_1m is not None:
        flip_ok = (not is_top and pct_1m > 0) or (is_top and pct_1m < 0)
        if flip_ok:
            score += 15
            supporting.append(f"1m candle confirms direction flip: {pct_1m:+.2f}%")
        else:
            caution.append(f"1m candle not yet confirming flip: {pct_1m:+.2f}%")

    caution.append("Not every exhaustion leads to reversal — confirm on next candle")

    top_or_bottom = "top" if is_top else "bottom"
    fade_text = " with volume fading" if volume_drop else ""
    summary = f"Potential {top_or_bottom} exhaustion after extended move{fade_text}."

    invalidation = (
        "Price makes new high with renewed volume"
        if is_top
        else "Price makes new low with renewed volume"
    )

    return {
        "summary": summary,
        "supportingFactors": supporting,
        "cautionFactors": caution,
        "invalidationCondition": invalidation,
        "confidence": _clamp(score),
        "confidenceFactors": supporting[:3],
    }


# ---------------------------------------------------------------------------
# EXPERIMENTAL: COIN_FAKEOUT
# ---------------------------------------------------------------------------


def _interpret_fakeout(_ev: dict) -> dict:
    return {
        "summary": (
            "Price briefly exceeded a key level and reversed — "
            "potentially trapping late entrants."
        ),
        "supportingFactors": [],
        "cautionFactors": [
            "Fakeout patterns are time-sensitive — stale by next candle"
        ],
        "invalidationCondition": "Price reclaims the broken level and holds",
        "confidence": 40,
        "confidenceFactors": [],
    }


# ---------------------------------------------------------------------------
# EXPERIMENTAL: COIN_VOLATILITY_EXPANSION
# ---------------------------------------------------------------------------


def _interpret_volatility(_ev: dict) -> dict:
    return {
        "summary": (
            "Volatility expanded significantly — directional analysis less reliable "
            "until price stabilizes."
        ),
        "supportingFactors": [],
        "cautionFactors": [
            "Volatility expansion alone does not indicate direction",
            "Mean-reversion signals less reliable during expansion",
        ],
        "invalidationCondition": "Volatility contracts back to baseline range",
        "confidence": 35,
        "confidenceFactors": [],
    }


# ---------------------------------------------------------------------------
# True fallback — for unknown/unseen type keys only
# confidence: None signals "not yet scored" vs "scored low"
# ---------------------------------------------------------------------------


def _interpret_generic(type_key: str) -> dict:
    label = type_key.lower().replace("_", " ")
    return {
        "summary": f"Market signal detected ({label}).",
        "supportingFactors": [],
        "cautionFactors": [],
        "invalidationCondition": "",
        "confidence": None,
        "confidenceFactors": [],
    }


# ---------------------------------------------------------------------------
# Dispatch — adds interpretation_support to classify production vs experimental
# ---------------------------------------------------------------------------

_IMPULSE_TYPES = frozenset({"MOONSHOT", "CRATER", "BREAKOUT", "DUMP"})
_REVERSAL_TYPES = frozenset({"COIN_REVERSAL_UP", "COIN_REVERSAL_DOWN"})

_PRODUCTION_TYPES = (
    _IMPULSE_TYPES | {"WHALE_MOVE"} | _REVERSAL_TYPES | {"COIN_LIQUIDITY_SHOCK"}
)

_EXPERIMENTAL_TYPES = frozenset(
    {
        "STEALTH_MOVE",
        "COIN_PERSISTENT_GAINER",
        "COIN_PERSISTENT_LOSER",
        "COIN_TREND_BREAK_UP",
        "COIN_TREND_BREAK_DOWN",
        "COIN_SQUEEZE_BREAK",
        "COIN_EXHAUSTION_TOP",
        "COIN_EXHAUSTION_BOTTOM",
        "COIN_FAKEOUT",
        "COIN_VOLATILITY_EXPANSION",
    }
)


def _interpret_alert(type_key: str, direction: str, evidence: dict) -> dict:
    tk = (type_key or "").upper()
    ev = evidence if isinstance(evidence, dict) else {}

    if tk in _IMPULSE_TYPES:
        result = _interpret_impulse(tk, direction, ev)
    elif tk == "WHALE_MOVE":
        result = _interpret_whale(direction, ev)
    elif tk in _REVERSAL_TYPES:
        result = _interpret_reversal(tk, direction, ev)
    elif tk == "COIN_LIQUIDITY_SHOCK":
        result = _interpret_liquidity_shock(ev)
    elif tk == "STEALTH_MOVE":
        result = _interpret_stealth(direction, ev)
    elif tk in ("COIN_PERSISTENT_GAINER", "COIN_PERSISTENT_LOSER"):
        result = _interpret_persistent(tk, ev)
    elif tk in ("COIN_TREND_BREAK_UP", "COIN_TREND_BREAK_DOWN"):
        result = _interpret_trend_break(tk, direction, ev)
    elif tk == "COIN_SQUEEZE_BREAK":
        result = _interpret_squeeze_break(ev)
    elif tk in ("COIN_EXHAUSTION_TOP", "COIN_EXHAUSTION_BOTTOM"):
        result = _interpret_exhaustion(tk, ev)
    elif tk == "COIN_FAKEOUT":
        result = _interpret_fakeout(ev)
    elif tk == "COIN_VOLATILITY_EXPANSION":
        result = _interpret_volatility(ev)
    else:
        result = _interpret_generic(tk)

    result["interpretation_support_level"] = (
        "production"
        if tk in _PRODUCTION_TYPES
        else "experimental" if tk in _EXPERIMENTAL_TYPES else "none"
    )

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def add_interpretation(alert: dict) -> dict:
    """Return a copy of alert with an 'interpretation' key added.

    Pure: does not mutate the original dict.
    Always succeeds: degrades to empty interpretation on any error.
    """
    if not isinstance(alert, dict):
        return alert

    type_key = str(alert.get("type_key") or alert.get("type") or "")
    direction = str(alert.get("direction") or "")
    evidence = alert.get("evidence") or {}

    try:
        interp = _interpret_alert(type_key, direction, evidence)
    except Exception:
        interp = {
            "summary": "",
            "supportingFactors": [],
            "cautionFactors": [],
            "invalidationCondition": "",
            "confidence": None,
            "confidenceFactors": [],
            "interpretation_support_level": "none",
        }

    return {**alert, "interpretation": interp}
