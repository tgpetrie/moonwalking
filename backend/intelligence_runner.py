"""Scheduled portfolio change intelligence runner.

The detector can find things; the feed can show things. This module is the part
that makes Bhabit check on its own, without a user opening the app.

Deliberately boring infrastructure: one daemon thread with a sleep loop, exactly
like the existing ``background_crypto_updates`` and ``_volume1h_updater_loop``
workers in ``app.py``. No Celery, no queue, no new service.

Everything is opt-in and configured by environment:

    MW_ENABLE_INTELLIGENCE_RUNNER   "1" to start the thread at boot (default off)
    INTELLIGENCE_RUN_INTERVAL       seconds between cycles (default 900)
    PORTFOLIO_CHANGE_INTELLIGENCE_EVENT_WINDOW
                                    seconds an emitted event suppresses another
                                    for the same user (default 21600/6h)
    OVERNIGHT_DELTA_WINDOW          legacy fallback for the same setting
    INTELLIGENCE_SNAPSHOT_MIN_GAP   seconds between portfolio snapshots for one
                                    user (default 3600/1h)
    PORTFOLIO_CHANGE_INTELLIGENCE_WINDOW_HOURS
                                    comparison window for the engine itself
                                    (default 12h)
    INTELLIGENCE_RUN_USER_IDS       optional explicit comma-separated user ids

Guardrails, in order of application per user:

1. snapshot window  — do not re-snapshot the same user inside the min gap
2. event window     — do not emit a second delta event inside the delta window
3. fingerprint      — do not re-emit the *same condition* even when the windows
                      have expired
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
import threading
import time
from typing import Any

try:
    from intelligence_memory import get_intelligence_memory_store
except ImportError:  # package imports under pytest
    from backend.intelligence_memory import get_intelligence_memory_store

try:
    from portfolio_change_intelligence import (
        EVENT_TYPE,
        DEFAULT_OVERNIGHT_HOURS,
        run_portfolio_intelligence_check,
    )
except ImportError:  # package imports under pytest
    from backend.portfolio_change_intelligence import (
        EVENT_TYPE,
        DEFAULT_OVERNIGHT_HOURS,
        run_portfolio_intelligence_check,
    )


logger = logging.getLogger(__name__)

ENV_ENABLED = "MW_ENABLE_INTELLIGENCE_RUNNER"
ENV_INTERVAL = "INTELLIGENCE_RUN_INTERVAL"
ENV_DELTA_WINDOW = "PORTFOLIO_CHANGE_INTELLIGENCE_EVENT_WINDOW"
ENV_DELTA_WINDOW_LEGACY = "OVERNIGHT_DELTA_WINDOW"
ENV_SNAPSHOT_GAP = "INTELLIGENCE_SNAPSHOT_MIN_GAP"
ENV_USER_IDS = "INTELLIGENCE_RUN_USER_IDS"
ENV_COMPARISON_WINDOW_HOURS = "PORTFOLIO_CHANGE_INTELLIGENCE_WINDOW_HOURS"


def _credentials_module():
    """Single lookup seam for the credential service.

    ``portfolio_credentials`` and ``backend.portfolio_credentials`` resolve to
    two distinct module objects depending on how the app was started, so every
    caller goes through here rather than importing inline. Tests patch this.
    """
    try:
        import portfolio_credentials as module
    except ImportError:  # package imports under pytest
        from backend import portfolio_credentials as module
    return module


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class RunnerConfig:
    """Timing policy. No production assumptions are hard-coded — every value is
    an environment override with a conservative default."""

    interval_seconds: int = 900  # 15 minutes
    delta_window_seconds: int = 21600  # 6 hours
    snapshot_min_gap_seconds: int = 3600  # 1 hour
    comparison_window_hours: float = DEFAULT_OVERNIGHT_HOURS

    @classmethod
    def from_env(cls) -> "RunnerConfig":
        return cls(
            interval_seconds=max(30, _env_int(ENV_INTERVAL, cls.interval_seconds)),
            delta_window_seconds=max(
                0,
                _env_int(
                    ENV_DELTA_WINDOW,
                    _env_int(ENV_DELTA_WINDOW_LEGACY, cls.delta_window_seconds),
                ),
            ),
            snapshot_min_gap_seconds=max(
                0, _env_int(ENV_SNAPSHOT_GAP, cls.snapshot_min_gap_seconds)
            ),
            comparison_window_hours=max(
                0.0,
                _env_float(ENV_COMPARISON_WINDOW_HOURS, cls.comparison_window_hours),
            ),
        )


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _age_seconds(value: Any, *, now: datetime | None = None) -> float | None:
    parsed = _parse_iso(value)
    if parsed is None:
        return None
    now = now or datetime.now(timezone.utc)
    return (now - parsed).total_seconds()


def resolve_intelligence_user_ids() -> list[int]:
    """Users the runner should check.

    Explicit ``INTELLIGENCE_RUN_USER_IDS`` wins. Otherwise eligibility comes
    from the shared credential service, which decides from stored connection
    state without any network calls. Ineligible users are logged with a reason
    rather than quietly dropped.
    """
    explicit = str(os.getenv(ENV_USER_IDS) or "").strip()
    if explicit:
        ids: list[int] = []
        for chunk in explicit.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                ids.append(int(chunk))
            except ValueError:
                continue
        return ids

    try:
        credentials = _credentials_module()
    except Exception:
        logger.warning(
            "[IntelligenceRunner] credential service unavailable; no users checked",
            exc_info=True,
        )
        return []

    eligible, ineligible = credentials.list_snapshot_eligible_users()
    for entry in ineligible:
        # Explicit, not silent: a user who must reconnect should be visible.
        logger.info(
            "[IntelligenceRunner] user %s not eligible (%s): %s",
            entry.get("user_id"),
            entry.get("reason"),
            entry.get("detail"),
        )
    return [int(entry["user_id"]) for entry in eligible]


def _recent_delta_event(store: Any, user_id: int) -> dict[str, Any] | None:
    events = store.list_intelligence_events(
        user_id=user_id,
        event_type=EVENT_TYPE,
        limit=1,
        include_packet=False,
    )
    return events[0] if events else None


def run_portfolio_intelligence_for_user(
    user_id: int,
    *,
    store: Any = None,
    config: RunnerConfig | None = None,
    now: datetime | None = None,
    **detector_kwargs: Any,
) -> dict[str, Any]:
    """Run one user's portfolio intelligence pass with all guardrails applied.

    Returns a structured status dict and never raises: one user's broken
    Coinbase connection must not stop the cycle for everybody else.
    """
    config = config or RunnerConfig.from_env()
    store = store or get_intelligence_memory_store()
    now = now or datetime.now(timezone.utc)

    # --- Guardrail 1: do not duplicate snapshots inside the same window ------
    try:
        latest = store.latest_portfolio_snapshot(user_id)
    except Exception:
        logger.debug("[IntelligenceRunner] snapshot lookup failed", exc_info=True)
        latest = None
    if latest and config.snapshot_min_gap_seconds > 0:
        # Prefer created_at: that is when *we* recorded the row. captured_at is
        # supplied by the portfolio provider, and a stale or fixed provider
        # timestamp would otherwise defeat the throttle entirely.
        age = _age_seconds(
            latest.get("created_at") or latest.get("captured_at"), now=now
        )
        if age is not None and age < config.snapshot_min_gap_seconds:
            return {
                "user_id": user_id,
                "status": "skipped_snapshot_window",
                "triggered": False,
                "seconds_since_last_snapshot": int(age),
            }

    # --- Guardrail 2: do not re-emit inside the delta window -----------------
    try:
        last_event = _recent_delta_event(store, user_id)
    except Exception:
        logger.debug("[IntelligenceRunner] event lookup failed", exc_info=True)
        last_event = None

    within_window = False
    if last_event and config.delta_window_seconds > 0:
        age = _age_seconds(last_event.get("observed_at"), now=now)
        within_window = age is not None and age < config.delta_window_seconds
    last_fingerprint = ((last_event or {}).get("payload") or {}).get("fingerprint")

    def emit_guard(fingerprint: str, _delta: dict, _detection: dict) -> bool:
        # Guardrail 2: another event already fired recently.
        if within_window:
            return False
        # Guardrail 3: the window expired, but the condition is unchanged.
        if last_fingerprint and fingerprint == last_fingerprint:
            return False
        return True

    # --- Credentials: same refresh path the interactive route uses -----------
    # Only resolve when the caller has not injected a snapshot/service (tests
    # and manual runs supply their own).
    if not detector_kwargs.get("current_snapshot") and not detector_kwargs.get(
        "service"
    ):
        try:
            service, resolved = _credentials_module().resolve_portfolio_service(user_id)
        except Exception:
            logger.warning(
                "[IntelligenceRunner] credential resolution crashed for user %s",
                user_id,
                exc_info=True,
            )
            return {
                "user_id": user_id,
                "status": "auth_error",
                "triggered": False,
                "detail": "Credential resolution failed.",
            }

        if service is None:
            # Explicit: name the auth outcome instead of collapsing everything
            # into "portfolio unavailable".
            logger.info(
                "[IntelligenceRunner] user %s skipped (%s): %s",
                user_id,
                resolved.status,
                resolved.detail,
            )
            return {
                "user_id": user_id,
                "status": "auth_unavailable",
                "credential_status": resolved.status,
                "triggered": False,
                "detail": resolved.detail,
            }
        detector_kwargs["service"] = service
        credential_status = resolved.status
    else:
        credential_status = "injected"

    try:
        result = run_portfolio_intelligence_check(
            user_id,
            hours=config.comparison_window_hours,
            store=store,
            emit_guard=emit_guard,
            **detector_kwargs,
        )
    except Exception:
        logger.debug("[IntelligenceRunner] detector failed", exc_info=True)
        return {"user_id": user_id, "status": "detector_error", "triggered": False}

    return {"user_id": user_id, "credential_status": credential_status, **result}


def run_intelligence_cycle(
    *,
    user_ids: list[int] | None = None,
    store: Any = None,
    config: RunnerConfig | None = None,
    **detector_kwargs: Any,
) -> dict[str, Any]:
    """One full pass over every eligible user. Failures are isolated per user."""
    config = config or RunnerConfig.from_env()
    store = store or get_intelligence_memory_store()
    if user_ids is None:
        user_ids = resolve_intelligence_user_ids()

    started_at = datetime.now(timezone.utc)
    results = []
    for user_id in user_ids:
        try:
            results.append(
                run_portfolio_intelligence_for_user(
                    user_id, store=store, config=config, **detector_kwargs
                )
            )
        except Exception:
            logger.debug("[IntelligenceRunner] user %s failed", user_id, exc_info=True)
            results.append({"user_id": user_id, "status": "error", "triggered": False})

    def _count(*statuses: str) -> int:
        return sum(1 for r in results if r.get("status") in statuses)

    summary = {
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "duration_seconds": round(
            (datetime.now(timezone.utc) - started_at).total_seconds(), 3
        ),
        "users_checked": len(user_ids),
        # A snapshot is written whenever detection actually evaluated state.
        "snapshots_created": _count("evaluated", "suppressed"),
        "events_created": sum(1 for r in results if r.get("triggered")),
        "events_suppressed": _count("suppressed"),
        "users_skipped_window": _count("skipped_snapshot_window"),
        "auth_failures": _count("auth_unavailable", "auth_error"),
        "portfolio_unavailable": _count("portfolio_unavailable"),
        "errors": _count("error", "detector_error"),
        "results": results,
    }
    _log_cycle_summary(summary)
    return summary


def _log_cycle_summary(summary: dict[str, Any]) -> None:
    """One line per cycle, always — a quiet market and a broken runner must not
    look identical in the logs."""
    logger.info(
        "[IntelligenceRunner] cycle complete in %ss: %s checked, %s snapshots, "
        "%s events (%s suppressed), %s window-skipped, %s auth failures, "
        "%s portfolio unavailable, %s errors",
        summary["duration_seconds"],
        summary["users_checked"],
        summary["snapshots_created"],
        summary["events_created"],
        summary["events_suppressed"],
        summary["users_skipped_window"],
        summary["auth_failures"],
        summary["portfolio_unavailable"],
        summary["errors"],
    )
    # Auth failures are the beta-killer: never let them sit at debug level.
    if summary["auth_failures"]:
        for result in summary["results"]:
            if result.get("status") in ("auth_unavailable", "auth_error"):
                logger.warning(
                    "[IntelligenceRunner] user %s auth failure (%s): %s",
                    result.get("user_id"),
                    result.get("credential_status"),
                    result.get("detail"),
                )


# =============================================================================
# BACKGROUND THREAD (mirrors the existing app.py worker pattern)
# =============================================================================

_RUNNER_THREAD: threading.Thread | None = None
_RUNNER_LOCK = threading.Lock()
_RUNNER_STOP = threading.Event()


def intelligence_runner_loop(config: RunnerConfig | None = None) -> None:
    config = config or RunnerConfig.from_env()
    logger.info(
        "Intelligence runner started: every %ss, delta window %ss, snapshot gap %ss",
        config.interval_seconds,
        config.delta_window_seconds,
        config.snapshot_min_gap_seconds,
    )
    while not _RUNNER_STOP.is_set():
        try:
            # run_intelligence_cycle logs its own per-cycle summary line.
            run_intelligence_cycle(config=config)
        except Exception:
            logger.warning("[IntelligenceRunner] cycle failed", exc_info=True)
        # Event-based sleep so shutdown is not blocked for a whole interval.
        _RUNNER_STOP.wait(config.interval_seconds)


def start_intelligence_runner(force: bool = False) -> bool:
    """Start the daemon thread if enabled. Idempotent; returns True if running."""
    global _RUNNER_THREAD
    if not force and os.getenv(ENV_ENABLED, "0") != "1":
        logger.info("Intelligence runner disabled (%s != 1)", ENV_ENABLED)
        return False

    with _RUNNER_LOCK:
        if _RUNNER_THREAD is not None and _RUNNER_THREAD.is_alive():
            return True
        _RUNNER_STOP.clear()
        try:
            thread = threading.Thread(
                target=intelligence_runner_loop,
                name="mw-intelligence-runner",
                daemon=True,
            )
            thread.start()
            _RUNNER_THREAD = thread
            return True
        except Exception:
            logger.warning("Failed to start intelligence runner thread", exc_info=True)
            return False


def stop_intelligence_runner() -> None:
    """Signal the loop to exit (used by tests and graceful shutdown)."""
    _RUNNER_STOP.set()


__all__ = [
    "RunnerConfig",
    "intelligence_runner_loop",
    "resolve_intelligence_user_ids",
    "run_intelligence_cycle",
    "run_portfolio_intelligence_for_user",
    "start_intelligence_runner",
    "stop_intelligence_runner",
]
