"""Customizable cycle alert rules with wake-up urgency, cooldowns and quiet hours.

Rules live in SQLite (``smart_alert_rules``); every firing, delivered or
suppressed, is written to ``smart_alert_history``. Rules are evaluated
against a ``scan_universe_cycles`` result plus the held positions and the
watchlist.

A rule is a list of conditions, each ``{"predicate": name, "value": ...}``,
joined by ``match`` (``all`` or ``any``). Its ``scope`` picks the coins it
reads: ``market`` (the industry regime, fired once as ``MARKET``), ``held``,
``watchlist``, ``universe`` or an explicit ``symbols`` list.

Urgency decides delivery:

- ``wake_up``      ntfy push with ``Priority: urgent`` and the alert
                   dispatcher; ignores quiet hours
- ``action_queue`` ntfy push with ``Priority: high`` and the dispatcher;
                   held back during quiet hours
- ``watch``        recorded in history only

Delivery is opt-in: ntfy needs ``MW_NTFY_URL``; the dispatcher in
``alert_delivery`` keeps its own enable flag and hourly budget.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable, Iterable, Mapping
from urllib.request import Request, urlopen


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "smart_alerts.sqlite"
URGENCIES = ("wake_up", "action_queue", "watch")
NTFY_PRIORITY = {"wake_up": "urgent", "action_queue": "high", "watch": "default"}
SCOPES = ("market", "held", "watchlist", "universe", "symbols")
STAGE_NUMBERS = {
    "stage_1_macro_compression": 1,
    "stage_2_btc_majors_lead": 2,
    "stage_3_alt_index_breakout": 3,
    "stage_4_alt_season_expansion": 4,
}
DEFAULT_COOLDOWN_SECONDS = 6 * 3600

DEFAULT_RULES = (
    {
        "name": "Stage 3 Industry Breakout Wake-Up",
        "urgency": "wake_up",
        "scope": "market",
        "conditions": [{"predicate": "liquidity_rotation_stage", "value": {"min": 3}}],
        "cooldown_seconds": 24 * 3600,
    },
    {
        "name": "Held Position Rollover Trim Alert",
        "urgency": "action_queue",
        "scope": "held",
        "conditions": [{"predicate": "fib_zone_hit", "value": "rollover_target_box"}],
        "cooldown_seconds": 12 * 3600,
    },
    {
        "name": "Held Position Stop-Proximity Alert",
        "urgency": "wake_up",
        "scope": "held",
        "conditions": [{"predicate": "stop_proximity_pct", "value": {"max": 3.0}}],
        "cooldown_seconds": 4 * 3600,
    },
    {
        "name": "Watchlist Deep Accumulation + StochRSI Turn Alert",
        "urgency": "action_queue",
        "scope": "watchlist",
        "conditions": [
            {"predicate": "cycle_bucket", "value": "deep_accumulation_exhaustion"},
            {"predicate": "weekly_stoch_rsi_turn", "value": "oversold_turn_up"},
        ],
        "cooldown_seconds": 24 * 3600,
    },
)


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and abs(out) != float("inf") else None


def _symbol(value: Any) -> str | None:
    return str(value).upper().split("-")[0] if value else None


def _one_of(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (list, tuple, set)):
        return actual in expected
    return actual == expected


def _range(actual: float | None, expected: Any) -> bool:
    """``expected`` is a number (exact) or ``{"min": a, "max": b}``."""
    if actual is None:
        return False
    if isinstance(expected, Mapping):
        low, high = _num(expected.get("min")), _num(expected.get("max"))
        return (low is None or actual >= low) and (high is None or actual <= high)
    target = _num(expected)
    return target is not None and actual == target


# ─── predicates ──────────────────────────────────────────────────────────────
# Each takes the snapshot for one coin (or the market) and the rule's value.


def _p_cycle_bucket(snap, value):
    return _one_of(snap.get("bucket"), value)


def _p_rotation_stage(snap, value):
    stage = snap.get("liquidity_rotation_stage")
    if isinstance(value, str) or isinstance(value, (list, tuple)):
        return _one_of(stage, value)
    return _range(_num(STAGE_NUMBERS.get(stage)), value)


def _p_rsi_regime(snap, value):
    if isinstance(value, Mapping):
        timeframe, regime = value.get("timeframe", "1w"), value.get("regime")
    else:
        timeframe, regime = "1w", value
    return _one_of((snap.get("rsi_regimes") or {}).get(timeframe), regime)


def _p_stoch_turn(snap, value):
    expected = "oversold_turn_up" if value in (None, True) else value
    return _one_of(snap.get("weekly_stoch_direction"), expected)


def _p_bool(key):
    def check(snap, value):
        return bool(snap.get(key)) is (True if value is None else bool(value))

    return check


def _p_fib_zone(snap, value):
    price = _num(snap.get("price"))
    if price is None:
        return False
    if value in (None, "rollover_target_box"):
        box = snap.get("rollover_target_box") or {}
        low, high = _num(box.get("low")), _num(box.get("high"))
    elif value == "at_multi_year_support":
        return bool(snap.get("at_multi_year_support"))
    elif isinstance(value, Mapping):
        low, high = _num(value.get("low")), _num(value.get("high"))
    else:
        return False
    return low is not None and high is not None and low <= price <= high


def _p_stop_proximity(snap, value):
    return _range(_num(snap.get("stop_distance_pct")), value)


def _p_price_above(snap, value):
    price, level = _num(snap.get("price")), _num(value)
    return price is not None and level is not None and price > level


def _p_price_below(snap, value):
    price, level = _num(snap.get("price")), _num(value)
    return price is not None and level is not None and price < level


PREDICATES: dict[str, Callable[[Mapping[str, Any], Any], bool]] = {
    "cycle_bucket": _p_cycle_bucket,
    "liquidity_rotation_stage": _p_rotation_stage,
    "rsi_regime": _p_rsi_regime,
    "weekly_stoch_rsi_turn": _p_stoch_turn,
    "daily_macd_kiss": _p_bool("daily_macd_kiss"),
    "weekly_macd_cross": _p_bool("weekly_macd_bullish_cross"),
    "fib_zone_hit": _p_fib_zone,
    "confirmation_pivot_break": _p_bool("breaking_confirmation_pivot"),
    "stop_proximity_pct": _p_stop_proximity,
    "price_above": _p_price_above,
    "price_below": _p_price_below,
}


def coin_snapshot(row, industry, position=None) -> dict[str, Any]:
    """Flatten a scanner row, the industry regime and an optional position."""
    stop = row.get("accumulation_invalidation_stop") or {}
    distance = _num(stop.get("stop_distance_pct"))
    price = _num(row.get("price"))
    own_stop = _num((position or {}).get("stop_price"))
    if own_stop is not None and price:
        # The position's own stop wins over the generic cycle invalidation.
        distance = round((price - own_stop) / price * 100.0, 2)
    return {
        **row,
        "liquidity_rotation_stage": industry.get("liquidity_rotation_stage"),
        "rsi_regimes": {"1w": row.get("weekly_rsi_regime")},
        "stop_distance_pct": distance,
    }


def validate_rule(rule: Mapping[str, Any]) -> dict[str, Any]:
    name = str(rule.get("name") or "").strip()
    if not name:
        raise ValueError("rule name is required")
    urgency = rule.get("urgency", "watch")
    if urgency not in URGENCIES:
        raise ValueError(f"invalid urgency: {urgency}")
    scope = rule.get("scope", "universe")
    if scope not in SCOPES:
        raise ValueError(f"invalid scope: {scope}")
    conditions = rule.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("at least one condition is required")
    for condition in conditions:
        if not isinstance(condition, Mapping) or condition.get("predicate") not in PREDICATES:
            raise ValueError(f"unknown predicate: {condition!r}")
    match = rule.get("match", "all")
    if match not in ("all", "any"):
        raise ValueError("match must be 'all' or 'any'")
    cooldown = int(rule.get("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS))
    if cooldown < 0:
        raise ValueError("cooldown_seconds cannot be negative")
    quiet = rule.get("quiet_hours")
    if quiet is not None:
        start, end = quiet.get("start_hour"), quiet.get("end_hour")
        if not all(type(h) is int and 0 <= h <= 23 for h in (start, end)):
            raise ValueError("quiet_hours needs start_hour and end_hour from 0 to 23")
    symbols = [_symbol(s) for s in rule.get("symbols") or [] if _symbol(s)]
    if scope == "symbols" and not symbols:
        raise ValueError("scope 'symbols' needs a symbols list")
    return {
        "name": name,
        "enabled": bool(rule.get("enabled", True)),
        "urgency": urgency,
        "scope": scope,
        "symbols": symbols,
        "conditions": [dict(c) for c in conditions],
        "match": match,
        "cooldown_seconds": cooldown,
        "quiet_hours": dict(quiet) if quiet else None,
    }


def in_quiet_hours(quiet: Mapping[str, Any] | None, hour: int) -> bool:
    if not quiet:
        return False
    start, end = quiet["start_hour"], quiet["end_hour"]
    if start == end:
        return False
    return start <= hour < end if start < end else hour >= start or hour < end


def _default_quiet_hours() -> dict[str, int] | None:
    raw = str(os.getenv("MW_SMART_ALERT_QUIET_HOURS") or "").strip()
    try:
        start, end = (int(part) for part in raw.split("-", 1))
    except ValueError:
        return None
    if 0 <= start <= 23 and 0 <= end <= 23:
        return {"start_hour": start, "end_hour": end}
    return None


def _post_ntfy(url: str, body: str, headers: dict[str, str]) -> None:
    request = Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
    with urlopen(request, timeout=8) as response:  # nosec B310 - operator-configured topic
        if int(getattr(response, "status", 200)) >= 400:
            raise RuntimeError("ntfy_http_error")


class SmartAlertEngine:
    def __init__(
        self,
        db_path: str | os.PathLike | None = None,
        *,
        ntfy_url: str | None = None,
        dispatcher: Any = None,
        http_post: Callable[[str, str, dict[str, str]], None] = _post_ntfy,
        local_hour: Callable[[float], int] | None = None,
        default_quiet_hours: Mapping[str, int] | None = None,
        seed_defaults: bool = True,
    ):
        env_path = os.environ.get("MW_SMART_ALERTS_DB")
        self.db_path = Path(db_path or env_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ntfy_url = ntfy_url if ntfy_url is not None else os.getenv("MW_NTFY_URL", "")
        self.dispatcher = dispatcher
        self.http_post = http_post
        self.local_hour = local_hour or (lambda ts: time.localtime(ts).tm_hour)
        self.default_quiet_hours = (
            dict(default_quiet_hours) if default_quiet_hours else _default_quiet_hours()
        )
        self._ensure_db()
        if seed_defaults:
            self.seed_default_rules()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS smart_alert_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    urgency TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    rule_json TEXT NOT NULL,
                    seeded INTEGER NOT NULL DEFAULT 0,
                    created_ts INTEGER NOT NULL,
                    updated_ts INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS smart_alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_id INTEGER NOT NULL,
                    rule_name TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    urgency TEXT NOT NULL,
                    fired_ts INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    delivered_json TEXT NOT NULL,
                    suppressed_reason TEXT,
                    FOREIGN KEY(rule_id) REFERENCES smart_alert_rules(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_smart_alert_history_rule "
                "ON smart_alert_history(rule_id, symbol, fired_ts DESC)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS smart_alert_meta (key TEXT PRIMARY KEY, value TEXT)"
            )

    # ─── rules ────────────────────────────────────────────────────────────

    def seed_default_rules(self) -> int:
        """Insert the default rules once; a rule the user deleted stays deleted."""
        with self._connect() as conn:
            if conn.execute(
                "SELECT 1 FROM smart_alert_meta WHERE key = 'defaults_seeded'"
            ).fetchone():
                return 0
        for rule in DEFAULT_RULES:
            self.upsert_rule(rule, seeded=True)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO smart_alert_meta(key, value) VALUES ('defaults_seeded', ?)",
                (str(int(time.time())),),
            )
        return len(DEFAULT_RULES)

    def upsert_rule(self, rule: Mapping[str, Any], *, seeded: bool = False) -> dict:
        clean = validate_rule(rule)
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO smart_alert_rules(
                    name, enabled, urgency, scope, rule_json, seeded, created_ts, updated_ts
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    enabled = excluded.enabled,
                    urgency = excluded.urgency,
                    scope = excluded.scope,
                    rule_json = excluded.rule_json,
                    updated_ts = excluded.updated_ts
                """,
                (
                    clean["name"],
                    int(clean["enabled"]),
                    clean["urgency"],
                    clean["scope"],
                    json.dumps(clean, sort_keys=True),
                    int(seeded),
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM smart_alert_rules WHERE name = ?", (clean["name"],)
            ).fetchone()
        return self._rule(row)

    def set_enabled(self, rule_id: int, enabled: bool) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM smart_alert_rules WHERE id = ?", (int(rule_id),)
            ).fetchone()
            if row is None:
                raise KeyError(rule_id)
            rule = {**json.loads(row["rule_json"]), "enabled": bool(enabled)}
            conn.execute(
                "UPDATE smart_alert_rules SET enabled = ?, rule_json = ?, updated_ts = ? "
                "WHERE id = ?",
                (int(enabled), json.dumps(rule, sort_keys=True), int(time.time()), int(rule_id)),
            )
            row = conn.execute(
                "SELECT * FROM smart_alert_rules WHERE id = ?", (int(rule_id),)
            ).fetchone()
        return self._rule(row)

    def get_rule(self, rule_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM smart_alert_rules WHERE id = ?", (int(rule_id),)
            ).fetchone()
        return self._rule(row) if row else None

    def update_rule(self, rule_id: int, changes: Mapping[str, Any]) -> dict:
        """Merge ``changes`` into an existing rule, re-validating the result."""
        existing = self.get_rule(rule_id)
        if existing is None:
            raise KeyError(rule_id)
        merged = {
            key: value
            for key, value in {**existing, **dict(changes)}.items()
            if key not in {"id", "seeded"}
        }
        clean = validate_rule(merged)
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE smart_alert_rules
                    SET name = ?, enabled = ?, urgency = ?, scope = ?, rule_json = ?,
                        updated_ts = ?
                    WHERE id = ?
                    """,
                    (
                        clean["name"],
                        int(clean["enabled"]),
                        clean["urgency"],
                        clean["scope"],
                        json.dumps(clean, sort_keys=True),
                        int(time.time()),
                        int(rule_id),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("a rule with that name already exists") from exc
        return self.get_rule(rule_id)  # type: ignore[return-value]

    def send_test(
        self,
        *,
        urgency: str = "wake_up",
        rule_id: int | None = None,
        now: float | None = None,
    ) -> dict:
        """Deliver a one-off test alert, ignoring quiet hours and cooldowns.

        Recorded in history under the symbol ``TEST`` so it can never reset a
        real coin's cooldown.
        """
        if rule_id is not None:
            rule = self.get_rule(rule_id)
            if rule is None:
                raise KeyError(rule_id)
        else:
            if urgency not in URGENCIES:
                raise ValueError(f"invalid urgency: {urgency}")
            rule = {"id": 0, "name": "Test Alert", "urgency": urgency}
        now = float(now if now is not None else time.time())
        message = f"TEST · {rule['name']} · delivery check"
        delivered: dict[str, Any] = {}
        if rule["urgency"] != "watch":
            delivered = self._deliver(rule, "TEST", message, now)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO smart_alert_history(
                    rule_id, rule_name, symbol, urgency, fired_ts, message,
                    evidence_json, delivered_json, suppressed_reason
                )
                VALUES (?, ?, 'TEST', ?, ?, ?, ?, ?, NULL)
                """,
                (
                    rule["id"],
                    rule["name"],
                    rule["urgency"],
                    int(now),
                    message,
                    json.dumps({"test": True}),
                    json.dumps(delivered, sort_keys=True),
                ),
            )
        return {
            "id": cur.lastrowid,
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "symbol": "TEST",
            "urgency": rule["urgency"],
            "fired_ts": int(now),
            "message": message,
            "evidence": {"test": True},
            "delivered": delivered,
            "suppressed_reason": None,
        }

    def delete_rule(self, rule_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM smart_alert_rules WHERE id = ?", (int(rule_id),))
        return cur.rowcount > 0

    def list_rules(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM smart_alert_rules ORDER BY id").fetchall()
        return [self._rule(row) for row in rows]

    def history(self, *, limit: int = 100, symbol: str | None = None) -> list[dict]:
        limit = min(max(int(limit), 1), 500)
        where, params = "", []
        if symbol:
            where, params = "WHERE symbol = ?", [_symbol(symbol)]
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM smart_alert_history {where} "
                "ORDER BY fired_ts DESC, id DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["evidence"] = json.loads(item.pop("evidence_json"))
            item["delivered"] = json.loads(item.pop("delivered_json"))
            out.append(item)
        return out

    @staticmethod
    def _rule(row: sqlite3.Row) -> dict:
        return {
            **json.loads(row["rule_json"]),
            "id": row["id"],
            "enabled": bool(row["enabled"]),
            "seeded": bool(row["seeded"]),
        }

    # ─── evaluation ───────────────────────────────────────────────────────

    def _targets(self, rule, scan, held, watchlist) -> Iterable[tuple[str, dict]]:
        industry = scan.get("industry") or {}
        if rule["scope"] == "market":
            if industry.get("available"):
                yield "MARKET", {
                    **industry,
                    "liquidity_rotation_stage": industry.get("liquidity_rotation_stage"),
                }
            return
        rows = {
            _symbol(row.get("symbol")): row
            for row in scan.get("coins") or []
            if isinstance(row, dict) and row.get("available")
        }
        if rule["scope"] == "held":
            symbols = sorted(held)
        elif rule["scope"] == "watchlist":
            symbols = sorted(watchlist)
        elif rule["scope"] == "symbols":
            symbols = rule["symbols"]
        else:
            symbols = sorted(rows)
        for symbol in symbols:
            if symbol in rows:
                yield symbol, coin_snapshot(rows[symbol], industry, held.get(symbol))

    @staticmethod
    def matches(rule: Mapping[str, Any], snapshot: Mapping[str, Any]) -> bool:
        results = (
            PREDICATES[c["predicate"]](snapshot, c.get("value"))
            for c in rule["conditions"]
        )
        return all(results) if rule.get("match", "all") == "all" else any(results)

    def _last_fired(self, rule_id: int, symbol: str) -> int | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT MAX(fired_ts) FROM smart_alert_history
                WHERE rule_id = ? AND symbol = ? AND suppressed_reason IS NULL
                """,
                (rule_id, symbol),
            ).fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def evaluate(
        self,
        scan: Mapping[str, Any] | None,
        *,
        positions: Iterable[Mapping[str, Any]] | None = None,
        watchlist: Iterable[str] | None = None,
        now: float | None = None,
        deliver: bool = True,
    ) -> list[dict]:
        """Fire every matching enabled rule; returns the history rows written."""
        if not isinstance(scan, Mapping):
            return []
        now = float(now if now is not None else time.time())
        held = {
            _symbol(p.get("symbol") or p.get("product_id")): dict(p)
            for p in positions or []
            if isinstance(p, Mapping) and _symbol(p.get("symbol") or p.get("product_id"))
        }
        watch = {_symbol(s) for s in watchlist or [] if _symbol(s)}
        fired = []
        for rule in self.list_rules():
            if not rule["enabled"]:
                continue
            for symbol, snapshot in self._targets(rule, scan, held, watch):
                if not self.matches(rule, snapshot):
                    continue
                last = self._last_fired(rule["id"], symbol)
                if last is not None and now - last < rule["cooldown_seconds"]:
                    continue
                fired.append(self._fire(rule, symbol, snapshot, now, deliver))
        return fired

    def _fire(self, rule, symbol, snapshot, now, deliver) -> dict:
        quiet = rule.get("quiet_hours") or self.default_quiet_hours
        suppressed = None
        if rule["urgency"] != "wake_up" and in_quiet_hours(quiet, self.local_hour(now)):
            suppressed = "quiet_hours"
        price = _num(snapshot.get("price"))
        message = f"{symbol} · {rule['name']}" + (f" · ${price:,.6g}" if price else "")
        evidence = {
            key: snapshot.get(key)
            for key in (
                "price",
                "bucket",
                "liquidity_rotation_stage",
                "weekly_rsi",
                "weekly_stoch_direction",
                "stop_distance_pct",
                "rollover_target_box",
            )
            if snapshot.get(key) is not None
        }
        delivered: dict[str, Any] = {}
        if deliver and suppressed is None and rule["urgency"] != "watch":
            delivered = self._deliver(rule, symbol, message, now)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO smart_alert_history(
                    rule_id, rule_name, symbol, urgency, fired_ts, message,
                    evidence_json, delivered_json, suppressed_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule["id"],
                    rule["name"],
                    symbol,
                    rule["urgency"],
                    int(now),
                    message,
                    json.dumps(evidence, sort_keys=True, default=str),
                    json.dumps(delivered, sort_keys=True),
                    suppressed,
                ),
            )
        return {
            "id": cur.lastrowid,
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "symbol": symbol,
            "urgency": rule["urgency"],
            "fired_ts": int(now),
            "message": message,
            "evidence": evidence,
            "delivered": delivered,
            "suppressed_reason": suppressed,
        }

    def _deliver(self, rule, symbol, message, now) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.ntfy_url:
            headers = {
                "Title": f"Moonwalking: {rule['name']}"[:200],
                "Priority": NTFY_PRIORITY[rule["urgency"]],
                "Tags": "rotating_light" if rule["urgency"] == "wake_up" else "chart",
            }
            try:
                self.http_post(self.ntfy_url, message, headers)
                out["ntfy"] = "sent"
            except Exception as exc:
                out["ntfy"] = f"failed:{type(exc).__name__}"
        if self.dispatcher is not None:
            event = {
                "id": f"smart:{rule['id']}:{symbol}:{int(now)}",
                "symbol": symbol,
                "primary_state": rule["name"],
                "modifier": rule["urgency"],
                "message": message,
                "confidence": 100 if rule["urgency"] == "wake_up" else 70,
                "event_ts_ms": int(now * 1000),
            }
            try:
                out["dispatcher"] = int(self.dispatcher.dispatch([event], now=now))
            except Exception as exc:
                out["dispatcher"] = f"failed:{type(exc).__name__}"
        return out
