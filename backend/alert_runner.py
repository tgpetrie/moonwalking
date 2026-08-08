"""Background evaluation of stored user alert rules.

One cycle = load evaluable rules, resolve the market data each one needs, call
the pure ``evaluate_rule``, and persist the outcome through ``apply_decision``.
Events land only in ``alert_events_user``, scoped to the rule's owner. Nothing
here reads or writes the legacy market-wide feed.

Market access is injected rather than imported so the whole runner is testable
with plain dicts — no network, no app import, no real clock:

``price_source()``            -> ``({product_id: price}, snapshot_ts)`` or None
``history_lookup(pid, ts)``   -> ``(observed_ts, price)`` or None

Failure isolation is per rule: one bad rule, symbol, or user increments an
error counter and the cycle continues.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import alert_rules
from alert_evaluator import MAX_PRICE_AGE_SECONDS, WINDOW_SECONDS, evaluate_rule

logger = logging.getLogger(__name__)

__all__ = [
    "CycleStats",
    "run_evaluation_cycle",
    "history_drift_tolerance",
    "DEFAULT_SUSTAIN_SECONDS",
]

# A trigger must still be true on a later cycle before it fires. One bad tick
# from the provider therefore cannot create an event: the spike is gone by the
# next scan and the pending state is discarded. Scans are ~30s apart, so any
# value below that simply means "a subsequent cycle".
DEFAULT_SUSTAIN_SECONDS = 1.0


def history_drift_tolerance(window_seconds: int) -> float:
    """How far off the requested target a historical price may be.

    ``price_db`` retains ~24h, so asking for "24h ago" on a freshly restarted
    process happily returns the *oldest row available* — possibly only a few
    hours old. Computing a "24h move" from 3h of history silently understates
    it, so a lookup that misses the target by more than this is treated as no
    comparison data at all.
    """
    return max(300.0, window_seconds * 0.2)


@dataclass
class CycleStats:
    rules_loaded: int = 0
    evaluated: int = 0
    fired: int = 0
    pending: int = 0  # conditions awaiting confirmation on a later cycle
    unconfirmed: int = 0  # pending conditions that went away (spikes)
    rearmed: int = 0
    errors: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "rules_loaded": self.rules_loaded,
            "evaluated": self.evaluated,
            "fired": self.fired,
            "pending": self.pending,
            "unconfirmed": self.unconfirmed,
            "rearmed": self.rearmed,
            "errors": self.errors,
            "skipped": dict(self.skipped),
            "duration_ms": round(self.duration_ms, 1),
        }


def _resolve_price(prices: dict[str, Any], symbol: str):
    """Look up a symbol in the price map, tolerating either key convention."""
    if not symbol:
        return None
    for key in (f"{symbol}-USD", symbol, f"{symbol}-USDC"):
        if key in prices:
            return prices[key]
    return None


def _past_price_for(
    rule: dict[str, Any],
    history_lookup: Callable[[str, int], tuple[int, float] | None],
    cache: dict[tuple[str, str], float | None],
    now: float,
) -> float | None:
    """Historical price for a percent_move rule, or None if unusable.

    Memoized per ``(product_id, window)`` so N users watching the same symbol
    and window cost one lookup per cycle, not N.
    """
    symbol = str(rule.get("symbol") or "").upper()
    window = str((rule.get("params") or {}).get("window") or "").lower()
    window_s = WINDOW_SECONDS.get(window)
    if not window_s:
        return None

    product_id = f"{symbol}-USD"
    key = (product_id, window)
    if key in cache:
        return cache[key]

    target_ts = int(now - window_s)
    result: float | None = None
    try:
        found = history_lookup(product_id, target_ts)
    except Exception:
        logger.exception("[alert-runner] history lookup failed for %s", product_id)
        found = None

    if found:
        observed_ts, price = found
        # Absolute drift: a row older than the target stretches the window
        # (overstating the move), a newer one shortens it (understating).
        # Both produce a number that is not the move the user asked about.
        drift = abs(target_ts - float(observed_ts))
        if drift <= history_drift_tolerance(window_s):
            result = price
        else:
            logger.debug(
                "[alert-runner] %s %s history off target by %.0fs; treating as missing",
                product_id,
                window,
                drift,
            )

    cache[key] = result
    return result


def _evaluate_one(
    rule: dict[str, Any],
    prices: dict[str, Any],
    snapshot_ts: int,
    history_lookup: Callable[[str, int], tuple[int, float] | None],
    cache: dict[tuple[str, str], float | None],
    now: float,
    stats: CycleStats,
    sustain_seconds: float,
) -> None:
    symbol = str(rule.get("symbol") or "").upper()
    price = _resolve_price(prices, symbol)
    if price is None:
        stats.skip("no_price")
        return

    obs: dict[str, Any] = {"price": price, "price_ts": snapshot_ts}

    if rule.get("trigger_type") == "percent_move":
        past = _past_price_for(rule, history_lookup, cache, now)
        if past is None:
            stats.skip("no_comparison_price")
            return
        obs["past_price"] = past

    decision = evaluate_rule(rule, obs, now_ts=now)
    stats.evaluated += 1

    if decision.suppression_reason and not decision.armed_changed:
        stats.skip(decision.suppression_reason)

    pending_since = rule.get("pending_since_ts")

    if decision.should_fire:
        # Sustained-crossing guard: a condition must survive to a later cycle.
        if pending_since is None:
            alert_rules.set_rule_pending(rule, now)
            stats.pending += 1
            logger.debug(
                "[alert-runner] rule %s condition pending confirmation (%s)",
                rule["id"],
                symbol,
            )
            return
        if (now - float(pending_since)) < sustain_seconds:
            stats.skip("awaiting_confirmation")
            return
        # Confirmed on a second consecutive cycle — fall through and fire.
    elif pending_since is not None:
        # The condition went away before confirming: a spike, not a move.
        alert_rules.set_rule_pending(rule, None)
        stats.unconfirmed += 1
        logger.info(
            "[alert-runner] rule %s condition vanished before confirmation (%s); "
            "no event created",
            rule["id"],
            symbol,
        )

    # Only write when something actually changed. A no-op write per rule per
    # cycle would be pure amplification; last_evaluated_at therefore reflects
    # the last state-changing evaluation.
    if not (decision.should_fire or decision.armed_changed):
        return

    event = alert_rules.apply_decision(rule, decision)

    if decision.should_fire:
        if event:
            stats.fired += 1
            logger.info(
                "[alert-runner] event %s rule=%s user=%s %s %s",
                event["id"],
                rule["id"],
                rule["user_id"],
                symbol,
                decision.event_type,
            )
        else:
            # Fingerprint collision: this arm cycle already produced an event.
            stats.skip("duplicate_event")
    elif decision.armed_changed and decision.next_armed:
        stats.rearmed += 1


def run_evaluation_cycle(
    *,
    price_source: Callable[[], tuple[dict[str, Any], int] | None],
    history_lookup: Callable[[str, int], tuple[int, float] | None],
    now_ts: float | None = None,
    max_rules: int = 500,
    sustain_seconds: float = DEFAULT_SUSTAIN_SECONDS,
) -> CycleStats:
    """Evaluate every stored rule once. Never raises."""
    stats = CycleStats()
    started = time.perf_counter()
    now = time.time() if now_ts is None else float(now_ts)

    try:
        snapshot = price_source()
    except Exception:
        logger.exception("[alert-runner] price source failed")
        stats.errors += 1
        snapshot = None

    if not snapshot:
        stats.skip("no_price_snapshot")
        stats.duration_ms = (time.perf_counter() - started) * 1000
        return stats

    prices, snapshot_ts = snapshot
    if not isinstance(prices, dict) or not prices:
        stats.skip("no_price_snapshot")
        stats.duration_ms = (time.perf_counter() - started) * 1000
        return stats

    # A stale snapshot invalidates the whole cycle — cheaper and safer than
    # re-checking per rule, and it keeps one log line instead of hundreds.
    age = now - float(snapshot_ts or 0)
    if age > MAX_PRICE_AGE_SECONDS:
        stats.skip("stale_snapshot")
        logger.warning(
            "[alert-runner] price snapshot is %.0fs old (max %ss); skipping cycle",
            age,
            MAX_PRICE_AGE_SECONDS,
        )
        stats.duration_ms = (time.perf_counter() - started) * 1000
        return stats

    try:
        rules = alert_rules.list_evaluable_rules(limit=max_rules)
    except Exception:
        logger.exception("[alert-runner] could not load rules")
        stats.errors += 1
        stats.duration_ms = (time.perf_counter() - started) * 1000
        return stats

    stats.rules_loaded = len(rules)
    cache: dict[tuple[str, str], float | None] = {}

    for rule in rules:
        try:
            _evaluate_one(
                rule,
                prices,
                snapshot_ts,
                history_lookup,
                cache,
                now,
                stats,
                sustain_seconds,
            )
        except Exception:
            stats.errors += 1
            logger.exception(
                "[alert-runner] rule %s (user %s) failed; continuing",
                rule.get("id"),
                rule.get("user_id"),
            )
            continue

    stats.duration_ms = (time.perf_counter() - started) * 1000
    if stats.fired or stats.errors or stats.rearmed or stats.unconfirmed:
        logger.info("[alert-runner] cycle %s", stats.as_dict())
    else:
        logger.debug("[alert-runner] cycle %s", stats.as_dict())
    return stats
