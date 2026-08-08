"""User-scoped alert rules, events, and recommendations.

Persistence lives in the same SQLite file as ``users``/``watchlists`` so rule
ownership is a real foreign key rather than a convention. The legacy
``alerts.db`` is untouched.

Four concepts are stored separately, per the architecture directive:

* **rule**            a persistent user instruction (this module, ``alert_rules``)
* **candidate**       a market observation (``alerts_engine``, untouched)
* **event**           a rule that matched (``alert_events_user``)
* **delivery**        whether the event reached the user (``delivery_status``
                      on the event row; channels are Phase 4)

Deduplication is a database guarantee, not a heuristic. Every event carries a
fingerprint derived from the rule's *arm cycle*, and the column is UNIQUE — so
one arm cycle can produce exactly one event, and that holds across restarts.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from alert_evaluator import (
    DEFAULT_COOLDOWN_SECONDS,
    DEFAULT_PERCENT_REARM_RATIO,
    DEFAULT_RESET_PCT,
    WINDOW_SECONDS,
    validate_rule_params,
)

# Reuse the watchlist database connection so rules live beside their owner.
from watchlist import _DB_LOCK, _db_connect

__all__ = [
    "ensure_alert_schema",
    "create_rule",
    "list_rules",
    "list_evaluable_rules",
    "get_rule",
    "update_rule",
    "delete_rule",
    "set_rule_status",
    "record_event",
    "apply_decision",
    "set_rule_pending",
    "list_events",
    "build_recommendations",
    "list_recommendations",
    "accept_recommendation",
    "dismiss_recommendation",
    "suggest_threshold",
    "user_watchlist_symbols",
    "user_portfolio_symbols",
    "RuleError",
]

DEFAULT_RULE_TTL_DAYS = 90
DEFAULT_RECOMMENDATION_TTL_DAYS = 45

# Assets deep enough that a 5% day is genuinely notable. Everything else gets a
# wider default so a normal session does not generate constant alerts.
_LARGE_CAP = {"BTC", "ETH"}
_MID_CAP = {"SOL", "XRP", "ADA", "DOGE", "LINK", "AVAX", "DOT", "LTC", "BCH", "UNI"}


class RuleError(ValueError):
    """Raised for validation failures that should surface to the user."""


# ─── helpers ─────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


def _norm_symbol(value: Any) -> str:
    import re

    return re.sub(r"[^A-Z0-9.]", "", str(value or "").upper().strip())


def _loads(value: Any, fallback: Any) -> Any:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return fallback
    return parsed


# ─── schema ──────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alert_rules (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    recommendation_basis TEXT NOT NULL DEFAULT '',
    recommendation_reason TEXT NOT NULL DEFAULT '',
    symbol TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    params_json TEXT NOT NULL,
    repeat_mode TEXT NOT NULL DEFAULT 'once',
    cooldown_seconds INTEGER NOT NULL,
    reset_pct REAL NOT NULL,
    percent_rearm_ratio REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    delivery_json TEXT NOT NULL DEFAULT '{}',
    armed INTEGER NOT NULL DEFAULT 1,
    arm_cycle INTEGER NOT NULL DEFAULT 0,
    pending_since_ts INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,
    expires_ts INTEGER,
    last_evaluated_at TEXT,
    last_triggered_at TEXT,
    last_triggered_ts INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alert_events_user (
    id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    event_type TEXT NOT NULL,
    observed_value REAL,
    boundary_value REAL,
    comparison_value REAL,
    window_label TEXT,
    triggered_at TEXT NOT NULL,
    triggered_ts INTEGER NOT NULL,
    explanation TEXT NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'triggered',
    suppression_reason TEXT,
    delivery_status TEXT NOT NULL DEFAULT 'pending',
    FOREIGN KEY(rule_id) REFERENCES alert_rules(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alert_recommendations (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    params_json TEXT NOT NULL,
    basis TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    expires_ts INTEGER NOT NULL,
    decided_at TEXT,
    accepted_rule_id TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, symbol, trigger_type)
);

CREATE INDEX IF NOT EXISTS idx_alert_rules_user ON alert_rules(user_id);
CREATE INDEX IF NOT EXISTS idx_alert_rules_active ON alert_rules(status, symbol);
CREATE INDEX IF NOT EXISTS idx_alert_events_user ON alert_events_user(user_id, triggered_ts);
CREATE INDEX IF NOT EXISTS idx_alert_events_rule ON alert_events_user(rule_id);
CREATE INDEX IF NOT EXISTS idx_alert_recs_user ON alert_recommendations(user_id, status);
"""

_schema_ready = False


def ensure_alert_schema() -> None:
    """Create alert tables if absent. Safe to call repeatedly."""
    global _schema_ready
    if _schema_ready:
        return
    with _DB_LOCK:
        conn = _db_connect()
        try:
            conn.executescript(_SCHEMA)
            # Additive migration for databases created before the sustained-
            # crossing guard existed.
            cols = {
                r["name"]
                for r in conn.execute("PRAGMA table_info(alert_rules)").fetchall()
            }
            if "pending_since_ts" not in cols:
                conn.execute(
                    "ALTER TABLE alert_rules ADD COLUMN pending_since_ts INTEGER"
                )
            conn.commit()
        finally:
            conn.close()
    _schema_ready = True


def _connect():
    ensure_alert_schema()
    return _db_connect()


# ─── serialization ───────────────────────────────────────────────────────────


def _serialize_rule(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "source": row["source"],
        "recommendation_basis": row["recommendation_basis"],
        "recommendation_reason": row["recommendation_reason"],
        "symbol": row["symbol"],
        "trigger_type": row["trigger_type"],
        "params": _loads(row["params_json"], {}),
        "repeat_mode": row["repeat_mode"],
        "cooldown_seconds": row["cooldown_seconds"],
        "reset_pct": row["reset_pct"],
        "percent_rearm_ratio": row["percent_rearm_ratio"],
        "status": row["status"],
        "delivery": _loads(row["delivery_json"], {}),
        "armed": bool(row["armed"]),
        "arm_cycle": row["arm_cycle"],
        "pending_since_ts": row["pending_since_ts"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "expires_at": row["expires_at"],
        "expires_ts": row["expires_ts"],
        "last_evaluated_at": row["last_evaluated_at"],
        "last_triggered_at": row["last_triggered_at"],
        "last_triggered_ts": row["last_triggered_ts"],
        "not_financial_advice": True,
    }


def _serialize_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "rule_id": row["rule_id"],
        "user_id": row["user_id"],
        "symbol": row["symbol"],
        "event_type": row["event_type"],
        "observed_value": row["observed_value"],
        "boundary_value": row["boundary_value"],
        "comparison_value": row["comparison_value"],
        "window_label": row["window_label"],
        "triggered_at": row["triggered_at"],
        "triggered_ts": row["triggered_ts"],
        "explanation": row["explanation"],
        "fingerprint": row["fingerprint"],
        "status": row["status"],
        "suppression_reason": row["suppression_reason"],
        "delivery_status": row["delivery_status"],
        "not_financial_advice": True,
    }


def _serialize_recommendation(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "symbol": row["symbol"],
        "trigger_type": row["trigger_type"],
        "params": _loads(row["params_json"], {}),
        "basis": row["basis"],
        "reason": row["reason"],
        "status": row["status"],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "decided_at": row["decided_at"],
        "accepted_rule_id": row["accepted_rule_id"],
        "not_financial_advice": True,
    }


# ─── fingerprints ────────────────────────────────────────────────────────────


def build_fingerprint(
    rule_id: str, arm_cycle: int, event_type: str, boundary: Any
) -> str:
    """Stable identity for one firing of one arm cycle.

    Deliberately excludes wall-clock time: a rule can only fire once per arm
    cycle, so this collides exactly when it should, including after a restart.
    """
    raw = f"{rule_id}|{arm_cycle}|{event_type}|{boundary}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


# ─── rule CRUD ───────────────────────────────────────────────────────────────


def create_rule(
    user_id: int,
    *,
    symbol: str,
    trigger_type: str,
    params: dict[str, Any],
    repeat_mode: str = "once",
    cooldown_seconds: int | None = None,
    expires_in_days: int | None = DEFAULT_RULE_TTL_DAYS,
    source: str = "manual",
    recommendation_basis: str = "",
    recommendation_reason: str = "",
    delivery: dict[str, Any] | None = None,
    current_price: float | None = None,
    reset_pct: float | None = None,
    percent_rearm_ratio: float | None = None,
) -> dict[str, Any]:
    """Validate and persist a new rule. Raises RuleError on invalid input."""
    sym = _norm_symbol(symbol)
    if not sym:
        raise RuleError("A coin symbol is required.")

    ttype = str(trigger_type or "").strip().lower()
    ok, err, norm_params = validate_rule_params(
        ttype, params or {}, current_price=current_price
    )
    if not ok:
        raise RuleError(err or "Invalid alert settings.")

    mode = str(repeat_mode or "once").strip().lower()
    if mode not in {"once", "recurring"}:
        raise RuleError("Repeat mode must be 'once' or 'recurring'.")

    if cooldown_seconds is None:
        cooldown_seconds = DEFAULT_COOLDOWN_SECONDS.get(ttype, 3_600)
    try:
        cooldown_seconds = int(cooldown_seconds)
    except (TypeError, ValueError):
        raise RuleError("Cooldown must be a whole number of seconds.")
    if cooldown_seconds < 0:
        raise RuleError("Cooldown cannot be negative.")

    now = _now()
    expires_at = expires_ts = None
    if expires_in_days is not None:
        try:
            days = int(expires_in_days)
        except (TypeError, ValueError):
            raise RuleError("Expiration must be a whole number of days.")
        if days <= 0:
            raise RuleError("Expiration must be at least one day after creation.")
        exp = now + timedelta(days=days)
        expires_at, expires_ts = _iso(exp), _ts(exp)

    conn = _connect()
    try:
        if _find_duplicate_rule(conn, user_id, sym, ttype, norm_params):
            raise RuleError(
                f"You already have a similar alert for {sym}. "
                f"Edit the existing one instead of creating a duplicate."
            )

        rule_id = f"rule_{uuid.uuid4().hex[:16]}"
        conn.execute(
            """
            INSERT INTO alert_rules (
                id, user_id, source, recommendation_basis, recommendation_reason,
                symbol, trigger_type, params_json, repeat_mode, cooldown_seconds,
                reset_pct, percent_rearm_ratio, status, delivery_json,
                armed, arm_cycle, created_at, updated_at, expires_at, expires_ts
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rule_id,
                user_id,
                source,
                recommendation_basis,
                recommendation_reason,
                sym,
                ttype,
                json.dumps(norm_params),
                mode,
                cooldown_seconds,
                DEFAULT_RESET_PCT if reset_pct is None else float(reset_pct),
                (
                    DEFAULT_PERCENT_REARM_RATIO
                    if percent_rearm_ratio is None
                    else float(percent_rearm_ratio)
                ),
                "active",
                json.dumps(delivery or {"in_app": True}),
                1,
                0,
                _iso(now),
                _iso(now),
                expires_at,
                expires_ts,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alert_rules WHERE id = ?", (rule_id,)
        ).fetchone()
        return _serialize_rule(row)
    finally:
        conn.close()


def _find_duplicate_rule(conn, user_id, symbol, trigger_type, params) -> bool:
    """Near-duplicate detection: same asset, type, direction and close threshold."""
    rows = conn.execute(
        """
        SELECT params_json FROM alert_rules
        WHERE user_id = ? AND symbol = ? AND trigger_type = ?
          AND status IN ('active','paused','cooling_down')
        """,
        (user_id, symbol, trigger_type),
    ).fetchall()
    new_dir = params.get("direction")
    new_thr = float(params.get("threshold") or 0)
    new_win = params.get("window")
    for row in rows:
        existing = _loads(row["params_json"], {})
        if existing.get("direction") != new_dir:
            continue
        if existing.get("window") != new_win:
            continue
        old_thr = float(existing.get("threshold") or 0)
        if old_thr <= 0:
            continue
        # Within 1% of an existing threshold counts as a duplicate.
        if abs(old_thr - new_thr) / old_thr <= 0.01:
            return True
    return False


def list_rules(user_id: int, *, status: str | None = None) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        sql = "SELECT * FROM alert_rules WHERE user_id = ?"
        args: list[Any] = [user_id]
        if status:
            sql += " AND status = ?"
            args.append(status)
        sql += " ORDER BY created_at DESC"
        return [_serialize_rule(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def list_evaluable_rules(*, limit: int = 500) -> list[dict[str, Any]]:
    """Every rule the background runner should evaluate, across all users.

    This is the one deliberately cross-user *read* in the module: the scan loop
    is a system process, not a user request. Writes stay per-owner — callers
    pass each rule straight back to ``apply_decision``, which scopes by
    ``user_id``.

    ``cooling_down`` is included on purpose: that is the only state from which
    a recurring rule can observe its reset boundary and re-arm.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT * FROM alert_rules
            WHERE status IN ('active','cooling_down')
              AND (expires_ts IS NULL OR expires_ts > ?)
            ORDER BY symbol ASC, id ASC
            LIMIT ?
            """,
            (_ts(_now()), max(1, min(int(limit), 5_000))),
        ).fetchall()
        return [_serialize_rule(r) for r in rows]
    finally:
        conn.close()


def get_rule(user_id: int, rule_id: str) -> dict[str, Any] | None:
    """Always scoped by user_id — a rule id alone never grants access."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM alert_rules WHERE id = ? AND user_id = ?", (rule_id, user_id)
        ).fetchone()
        return _serialize_rule(row) if row else None
    finally:
        conn.close()


def update_rule(user_id: int, rule_id: str, **changes: Any) -> dict[str, Any] | None:
    existing = get_rule(user_id, rule_id)
    if not existing:
        return None

    now = _now()
    sets: list[str] = ["updated_at = ?"]
    args: list[Any] = [_iso(now)]

    if "params" in changes or "trigger_type" in changes:
        ttype = str(changes.get("trigger_type") or existing["trigger_type"]).lower()
        merged = {**existing["params"], **(changes.get("params") or {})}
        ok, err, norm = validate_rule_params(
            ttype, merged, current_price=changes.get("current_price")
        )
        if not ok:
            raise RuleError(err or "Invalid alert settings.")
        sets += ["trigger_type = ?", "params_json = ?"]
        args += [ttype, json.dumps(norm)]
        # Editing the trigger invalidates the old arm cycle.
        sets += ["armed = ?", "arm_cycle = ?"]
        args += [1, existing["arm_cycle"] + 1]

    if "repeat_mode" in changes:
        mode = str(changes["repeat_mode"]).lower()
        if mode not in {"once", "recurring"}:
            raise RuleError("Repeat mode must be 'once' or 'recurring'.")
        sets.append("repeat_mode = ?")
        args.append(mode)

    if "cooldown_seconds" in changes:
        try:
            cd = int(changes["cooldown_seconds"])
        except (TypeError, ValueError):
            raise RuleError("Cooldown must be a whole number of seconds.")
        if cd < 0:
            raise RuleError("Cooldown cannot be negative.")
        sets.append("cooldown_seconds = ?")
        args.append(cd)

    if "status" in changes:
        st = str(changes["status"]).lower()
        if st not in {"active", "paused"}:
            raise RuleError("Status must be 'active' or 'paused'.")
        sets.append("status = ?")
        args.append(st)

    conn = _connect()
    try:
        args += [rule_id, user_id]
        conn.execute(
            f"UPDATE alert_rules SET {', '.join(sets)} WHERE id = ? AND user_id = ?",
            args,
        )
        conn.commit()
    finally:
        conn.close()
    return get_rule(user_id, rule_id)


def set_rule_status(user_id: int, rule_id: str, status: str) -> dict[str, Any] | None:
    return update_rule(user_id, rule_id, status=status)


def delete_rule(user_id: int, rule_id: str) -> bool:
    conn = _connect()
    try:
        cur = conn.execute(
            "DELETE FROM alert_rules WHERE id = ? AND user_id = ?", (rule_id, user_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ─── events ──────────────────────────────────────────────────────────────────


def set_rule_pending(rule: dict[str, Any], pending_ts: float | None) -> None:
    """Record (or clear) an unconfirmed trigger for the sustained-crossing guard.

    Deliberately a single nullable column on the rule, not a second table: a
    pending trigger is not an event and must never become one. The load-bearing
    guarantees stay where they are — arm-cycle fingerprints, persistent
    cooldown/hysteresis, and user-scoped events.
    """
    conn = _connect()
    try:
        conn.execute(
            "UPDATE alert_rules SET pending_since_ts = ? WHERE id = ? AND user_id = ?",
            (
                int(pending_ts) if pending_ts is not None else None,
                rule["id"],
                rule["user_id"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def record_event(rule: dict[str, Any], decision, *, now: datetime | None = None):
    """Persist a fired decision as an event. Returns None if already recorded.

    The UNIQUE fingerprint makes duplicate suppression a storage guarantee, so
    a restart mid-cycle cannot produce a second event for the same firing.
    """
    now = now or _now()
    fingerprint = build_fingerprint(
        rule["id"],
        rule.get("arm_cycle", 0),
        decision.event_type,
        decision.boundary_value,
    )
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO alert_events_user (
                id, rule_id, user_id, symbol, event_type, observed_value,
                boundary_value, comparison_value, window_label, triggered_at,
                triggered_ts, explanation, fingerprint, status, delivery_status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                f"evt_{uuid.uuid4().hex[:16]}",
                rule["id"],
                rule["user_id"],
                rule["symbol"],
                decision.event_type,
                decision.observed_value,
                decision.boundary_value,
                decision.comparison_value,
                decision.window_label,
                _iso(now),
                _ts(now),
                decision.explanation,
                fingerprint,
                "triggered",
                "pending",
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alert_events_user WHERE fingerprint = ?", (fingerprint,)
        ).fetchone()
        return _serialize_event(row) if row else None
    except sqlite3.IntegrityError:
        return None  # duplicate — already recorded for this arm cycle
    finally:
        conn.close()


def apply_decision(rule: dict[str, Any], decision, *, now: datetime | None = None):
    """Persist rule state after evaluation, and the event if one fired.

    Returns the created event dict, or None when nothing fired.
    """
    now = now or _now()
    event = None
    conn = _connect()
    try:
        sets = ["last_evaluated_at = ?"]
        args: list[Any] = [_iso(now)]

        if decision.should_fire:
            sets += ["last_triggered_at = ?", "last_triggered_ts = ?"]
            args += [_iso(now), _ts(now)]
            # A confirmed trigger consumes its pending state.
            sets.append("pending_since_ts = ?")
            args.append(None)
            # A one-time rule is finished; a recurring rule cools down.
            new_status = (
                "triggered"
                if str(rule.get("repeat_mode")).lower() == "once"
                else "cooling_down"
            )
            sets.append("status = ?")
            args.append(new_status)

        if decision.armed_changed:
            sets.append("armed = ?")
            args.append(1 if decision.next_armed else 0)
            if decision.next_armed:
                # Re-arming opens a new cycle, allowing a genuinely new event.
                sets.append("arm_cycle = ?")
                args.append(rule.get("arm_cycle", 0) + 1)
                if str(rule.get("status")) == "cooling_down":
                    sets.append("status = ?")
                    args.append("active")

        args += [rule["id"], rule["user_id"]]
        conn.execute(
            f"UPDATE alert_rules SET {', '.join(sets)} WHERE id = ? AND user_id = ?",
            args,
        )
        conn.commit()
    finally:
        conn.close()

    if decision.should_fire:
        event = record_event(rule, decision, now=now)
    return event


def list_events(user_id: int, *, limit: int = 50, symbol: str | None = None):
    conn = _connect()
    try:
        sql = "SELECT * FROM alert_events_user WHERE user_id = ?"
        args: list[Any] = [user_id]
        if symbol:
            sql += " AND symbol = ?"
            args.append(_norm_symbol(symbol))
        sql += " ORDER BY triggered_ts DESC LIMIT ?"
        args.append(max(1, min(int(limit), 200)))
        return [_serialize_event(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


# ─── user interest sources (never the global watchlist_db) ───────────────────


def user_watchlist_symbols(user_id: int) -> set[str]:
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT wi.item_key AS sym
            FROM watchlist_items wi
            JOIN watchlists w ON w.id = wi.watchlist_id
            WHERE w.user_id = ?
            """,
            (user_id,),
        ).fetchall()
        return {_norm_symbol(r["sym"]) for r in rows if _norm_symbol(r["sym"])}
    finally:
        conn.close()


def user_portfolio_symbols(user_id: int) -> set[str]:
    """Per-user holdings from manual cost basis.

    Deliberately does not consult the process-global ``watchlist_db`` set or a
    shared portfolio service: personalized output must never mix users.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT symbol FROM manual_cost_basis WHERE user_id = ?", (user_id,)
        ).fetchall()
        return {_norm_symbol(r["symbol"]) for r in rows if _norm_symbol(r["symbol"])}
    finally:
        conn.close()


# ─── recommendations ─────────────────────────────────────────────────────────


def suggest_threshold(
    symbol: str, *, daily_volatility_pct: float | None = None
) -> float:
    """Deterministic suggested percentage for a 24h move alert.

    Prefers observed volatility when the caller can supply it, so a quiet
    large-cap and a jumpy micro-cap do not get the same number. Falls back to
    conservative liquidity tiers when no volatility data is available — a wider
    default is the safe direction, since too-tight is what causes fatigue.
    """
    sym = _norm_symbol(symbol)
    if daily_volatility_pct is not None:
        try:
            vol = float(daily_volatility_pct)
        except (TypeError, ValueError):
            vol = None
        if vol is not None and vol > 0:
            # A notable day is meaningfully bigger than a typical one.
            suggested = vol * 1.5
            return float(max(3.0, min(25.0, round(suggested * 2) / 2)))
    if sym in _LARGE_CAP:
        return 5.0
    if sym in _MID_CAP:
        return 8.0
    return 12.0


def _recommendation_reason(symbol: str, basis: str, threshold: float) -> str:
    where = "in your portfolio" if basis == "portfolio" else "on your watchlist"
    return (
        f"Because {symbol} is {where}, Moonwalkings can notify you if it makes "
        f"an unusually large move of {threshold:g}% or more during a rolling "
        f"24-hour period."
    )


def build_recommendations(
    user_id: int,
    *,
    volatility_by_symbol: dict[str, float] | None = None,
    portfolio_symbols: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Create pending recommendations for portfolio + watchlist assets.

    Never activates anything. Skips assets the user already has a rule for,
    and will not resurrect a recommendation the user dismissed.
    """
    vol_map = volatility_by_symbol or {}
    portfolio = (
        portfolio_symbols
        if portfolio_symbols is not None
        else user_portfolio_symbols(user_id)
    )
    watchlist = user_watchlist_symbols(user_id)

    # Portfolio wins when an asset is in both — the reason is more specific.
    basis_by_symbol = {s: "watchlist" for s in watchlist}
    basis_by_symbol.update({s: "portfolio" for s in portfolio})
    if not basis_by_symbol:
        return []

    now = _now()
    exp = now + timedelta(days=DEFAULT_RECOMMENDATION_TTL_DAYS)

    conn = _connect()
    try:
        # A manual rule always takes precedence over a suggestion.
        covered = {
            r["symbol"]
            for r in conn.execute(
                """
                SELECT DISTINCT symbol FROM alert_rules
                WHERE user_id = ? AND trigger_type = 'percent_move'
                  AND status IN ('active','paused','cooling_down')
                """,
                (user_id,),
            ).fetchall()
        }
        decided = {
            r["symbol"]
            for r in conn.execute(
                """
                SELECT symbol FROM alert_recommendations
                WHERE user_id = ? AND status IN ('accepted','dismissed')
                """,
                (user_id,),
            ).fetchall()
        }

        for symbol, basis in sorted(basis_by_symbol.items()):
            if symbol in covered or symbol in decided:
                continue
            threshold = suggest_threshold(
                symbol, daily_volatility_pct=vol_map.get(symbol)
            )
            params = {"direction": "either", "threshold": threshold, "window": "24h"}
            try:
                conn.execute(
                    """
                    INSERT INTO alert_recommendations (
                        id, user_id, symbol, trigger_type, params_json, basis,
                        reason, status, created_at, expires_at, expires_ts
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        f"rec_{uuid.uuid4().hex[:16]}",
                        user_id,
                        symbol,
                        "percent_move",
                        json.dumps(params),
                        basis,
                        _recommendation_reason(symbol, basis, threshold),
                        "pending",
                        _iso(now),
                        _iso(exp),
                        _ts(exp),
                    ),
                )
            except sqlite3.IntegrityError:
                continue  # already recommended for this asset+type
        conn.commit()
    finally:
        conn.close()

    return list_recommendations(user_id)


def list_recommendations(user_id: int, *, include_expired: bool = False):
    """Pending recommendations only. Expired ones are filtered, not deleted."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT * FROM alert_recommendations
            WHERE user_id = ? AND status = 'pending'
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
        now_ts = _ts(_now())
        out = []
        for row in rows:
            if not include_expired and row["expires_ts"] <= now_ts:
                continue
            out.append(_serialize_recommendation(row))
        return out
    finally:
        conn.close()


def accept_recommendation(
    user_id: int,
    rec_id: str,
    *,
    current_price: float | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Turn a pending recommendation into a real active rule.

    This is the only path by which a recommendation becomes active; nothing
    else in this module sets a recommended rule to 'active'.
    """
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM alert_recommendations WHERE id = ? AND user_id = ?",
            (rec_id, user_id),
        ).fetchone()
        if not row:
            raise RuleError("That suggestion no longer exists.")
        if row["status"] != "pending":
            raise RuleError(f"That suggestion was already {row['status']}.")
        if row["expires_ts"] <= _ts(_now()):
            raise RuleError("That suggestion has expired.")
        rec = _serialize_recommendation(row)
    finally:
        conn.close()

    params = {**rec["params"], **(overrides or {})}
    rule = create_rule(
        user_id,
        symbol=rec["symbol"],
        trigger_type=rec["trigger_type"],
        params=params,
        repeat_mode="recurring",
        source="recommended",
        recommendation_basis=rec["basis"],
        recommendation_reason=rec["reason"],
        current_price=current_price,
    )

    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE alert_recommendations
            SET status = 'accepted', decided_at = ?, accepted_rule_id = ?
            WHERE id = ? AND user_id = ?
            """,
            (_iso(_now()), rule["id"], rec_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()
    return rule


def dismiss_recommendation(user_id: int, rec_id: str) -> bool:
    """Dismissed suggestions stay dismissed — they do not come back."""
    conn = _connect()
    try:
        cur = conn.execute(
            """
            UPDATE alert_recommendations
            SET status = 'dismissed', decided_at = ?
            WHERE id = ? AND user_id = ? AND status = 'pending'
            """,
            (_iso(_now()), rec_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
