"""
Alert text builder for consistent alert messages/titles.

This centralizes message formatting so alert emitters don't build strings inline.
"""

from __future__ import annotations

from typing import Any, Tuple


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _fmt_pct(value: Any, decimals: int = 2, signed: bool = True) -> str | None:
    num = _safe_float(value)
    if num is None:
        return None
    if signed:
        return f"{num:+.{decimals}f}%"
    return f"{num:.{decimals}f}%"


def _fmt_pct_from_fraction(value: Any, decimals: int = 1, signed: bool = True) -> str | None:
    num = _safe_float(value)
    if num is None:
        return None
    pct = num * 100
    if signed:
        return f"{pct:+.{decimals}f}%"
    return f"{pct:.{decimals}f}%"


def _fmt_ratio(value: Any, decimals: int = 1) -> str | None:
    num = _safe_float(value)
    if num is None:
        return None
    return f"{num:.{decimals}f}"


def _fmt_price(value: Any, decimals: int = 4) -> str | None:
    num = _safe_float(value)
    if num is None:
        return None
    return f"${num:,.{decimals}f}"


def build_alert_text(
    kind: str | None,
    *,
    symbol: str | None = None,
    window: str | None = None,
    direction: str | None = None,
    change_pct: Any | None = None,
    ret_1m: Any | None = None,
    ret_3m: Any | None = None,
    heat_score: Any | None = None,
    heat_label: str | None = None,
    fg_value: Any | None = None,
    candle_pct: Any | None = None,
    vol_ratio: Any | None = None,
    z_vol: Any | None = None,
    base_price: Any | None = None,
    pulses: int | None = None,
    vol1h_pct: Any | None = None,
    vol1h: Any | None = None,
    price_change_3m: Any | None = None,
    vol_change_pct: Any | None = None,
    volume_spike: Any | None = None,
    sentiment_change: Any | None = None,
    social_spike: Any | None = None,
    sentiment_score: Any | None = None,
    price_change: Any | None = None,
    title: str | None = None,
) -> Tuple[str, str | None]:
    """Return (message, title) for alert text. Always returns a non-empty message."""

    sym = (symbol or "MARKET").upper()
    key = (kind or "").strip().lower()

    # --- Impulse-style moves (app.py) ---
    if key.startswith("impulse") or key in {"moonshot", "crater", "breakout", "dump"}:
        if title is None:
            if key == "moonshot":
                title = f"🚀 Moonshot: {sym}"
            elif key == "crater":
                title = f"💥 Crater: {sym}"
            elif key == "breakout":
                title = f"📈 Breakout: {sym}"
            elif key == "dump":
                title = f"📉 Dump: {sym}"
            else:
                if window and direction:
                    title = f"{window} impulse {direction}"
                elif window:
                    title = f"{window} impulse"
                else:
                    title = "Impulse move"

        pct = _fmt_pct(change_pct, 2)
        if pct and window:
            return f"{sym} moved {pct} in {window}", title
        if pct:
            return f"{sym} moved {pct}", title
        return f"{sym} impulse move", title

    # --- Divergence (app.py) ---
    if key == "divergence":
        if title is None:
            title = f"⚡ Divergence: {sym}"
        r1 = _safe_float(ret_1m)
        r3 = _safe_float(ret_3m)
        if r1 is not None and r3 is not None:
            if r1 > 0 and r3 < 0:
                msg = f"{sym}: 1m up {_fmt_pct(r1, 2)} but 3m down {_fmt_pct(r3, 2)} — possible reversal"
            else:
                msg = f"{sym}: 1m down {_fmt_pct(r1, 2)} but 3m up {_fmt_pct(r3, 2)} — possible pullback"
            return msg, title
        return f"{sym} divergence detected", title

    # --- Volatility spike (app.py) ---
    if key == "volatility_spike":
        pct = _fmt_pct(vol_change_pct, 2, signed=False)
        if pct:
            return f"Market volatility spike ({pct})", title
        return "Market volatility spike", title

    # --- Whale alerts (app.py) ---
    if key == "whale_move":
        if title is None:
            title = f"🐋 Whale Move: {sym}"
        pct = _fmt_pct(candle_pct, 2)
        ratio = _fmt_ratio(vol_ratio, 1)
        zed = _fmt_ratio(z_vol, 1)
        price = _fmt_price(base_price, 4)
        if pct and ratio and zed and price:
            msg = f"{sym} {pct} in 1m · vol {ratio}x median ({zed}σ) · {price}"
            return msg, title
        return f"{sym} whale move detected", title

    if key == "whale_absorption":
        if title is None:
            title = f"🐋 Absorption: {sym}"
        pct = _fmt_pct(candle_pct, 2)
        ratio = _fmt_ratio(vol_ratio, 1)
        zed = _fmt_ratio(z_vol, 1)
        pulses_val = pulses or 1
        if pct and ratio and zed:
            msg = f"{sym} heavy tape · price flat ({pct}) · vol {ratio}x ({zed}σ) · {pulses_val} pulses"
            return msg, title
        return f"{sym} absorption detected", title

    if key == "whale_surge":
        if title is None:
            title = f"🐋 Whale Surge: {sym}"
        pct = _fmt_pct(vol1h_pct, 0)
        units = _safe_float(vol1h)
        if pct is not None and units is not None:
            msg = f"{sym} 1h volume {pct} vs prev hour ({units:,.0f} units)"
            return msg, title
        return f"{sym} whale surge detected", title

    # --- Stealth move (app.py) ---
    if key == "stealth_move":
        if title is None:
            title = f"👤 Stealth Move: {sym}"
        pct = _fmt_pct(price_change_3m, 2)
        vol_pct = _fmt_pct(vol1h_pct, 0)
        if pct and vol_pct:
            return f"{sym} up {pct} on quiet volume ({vol_pct} vol change)", title
        return f"{sym} stealth move detected", title

    # --- Market FOMO/Fear (app.py) ---
    if key in {"fomo_alert", "fear_alert"}:
        if title is None:
            title = "🔥 FOMO Alert: Market Overheating" if key == "fomo_alert" else "🥶 Extreme Fear: Market Frozen"
        if heat_score is not None:
            label = f" ({heat_label})" if heat_label else ""
            msg = f"Market Heat {heat_score}/100{label}"
        else:
            msg = "Market Heat alert"
        if fg_value is not None:
            msg = f"{msg}, Fear & Greed {fg_value}/100"
        return msg, title

    # --- Seed (app.py) ---
    if key == "seed":
        if title is None:
            title = "Seed alert (wiring check)"
        return "If you can read this, alerts are flowing end-to-end.", title

    # --- Moonwalking alert system (moonwalking_alert_system.py) ---
    if key == "moonshot_detected":
        if title is None:
            title = f"🚀 {sym} MOONSHOT DETECTED"
        change = _fmt_pct_from_fraction(change_pct, 1, signed=False)
        spike = _fmt_ratio(volume_spike, 1)
        if change and spike:
            return f"{sym} pumping {change} in 1h with {spike}x volume!", title
        return f"{sym} moonshot detected", title

    if key == "crater_detected":
        if title is None:
            title = f"📉 {sym} CRATER DETECTED"
        if change_pct is not None:
            change = _fmt_pct_from_fraction(abs(_safe_float(change_pct) or 0.0), 1, signed=False)
        else:
            change = None
        spike = _fmt_ratio(volume_spike, 1)
        if change and spike:
            return f"{sym} dumping {change} in 1h with {spike}x volume!", title
        return f"{sym} crater detected", title

    if key == "sentiment_spike":
        if title is None:
            title = f"🌊 {sym} SENTIMENT SPIKE"
        dir_label = direction or ""
        change = _fmt_pct_from_fraction(sentiment_change, 1, signed=False)
        spike = _fmt_ratio(social_spike, 1)
        if change and spike:
            return f"{sym} {dir_label} sentiment spike: {change} change, {spike}x social volume!", title
        return f"{sym} sentiment spike detected", title

    if key == "fomo_symbol":
        if title is None:
            title = f"🔥 {sym} FOMO ALERT"
        sent = _fmt_pct_from_fraction(sentiment_score, 0, signed=False)
        price = _fmt_pct_from_fraction(price_change, 1, signed=False)
        if sent and price:
            return f"{sym} hitting FOMO levels: {sent} sentiment + {price} price pump!", title
        return f"{sym} FOMO alert", title

    if key == "fear_symbol":
        if title is None:
            title = f"😱 {sym} FEAR EXTREME"
        sent = _fmt_pct_from_fraction(sentiment_score, 0, signed=False)
        price = _fmt_pct_from_fraction(price_change, 1, signed=False)
        if sent and price:
            return f"{sym} extreme fear: {sent} sentiment + {price} dump!", title
        return f"{sym} fear alert", title

    if key == "stealth_symbol":
        if title is None:
            title = f"👤 {sym} STEALTH ACCUMULATION"
        spike = _fmt_ratio(volume_spike, 1)
        price = _fmt_pct_from_fraction(price_change, 1, signed=False)
        if spike and price:
            return f"{sym} stealth activity: {spike}x volume but only {price} price change", title
        return f"{sym} stealth accumulation", title

    # --- Fallback ---
    return f"{sym} alert", title
