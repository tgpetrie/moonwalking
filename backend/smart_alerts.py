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

from contextlib import closing
from email.header import Header
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Callable, Iterable, Mapping
from urllib.request import Request, urlopen

try:
    from .macro_industry_scanner import BUCKETS, STAGES
except ImportError:
    from macro_industry_scanner import BUCKETS, STAGES


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "smart_alerts.sqlite"
URGENCIES = ("wake_up", "action_queue", "watch")
NTFY_PRIORITY = {"wake_up": "urgent", "action_queue": "high", "watch": "default"}
SCOPES = ("market", "held", "watchlist", "universe", "symbols")
STAGE_NUMBERS = {stage: number for stage, (number, _label) in STAGES.items()}
RSI_REGIMES = ("oversold_compression", "no_mans_land", "growth_expansion")
STOCH_DIRECTIONS = ("oversold_turn_up", "overbought_turn_down", "bullish_expansion", "high_to_low_drift")
BOOLEAN_PREDICATES = ("daily_macd_kiss", "weekly_macd_cross", "confirmation_pivot_break")
DEFAULT_COOLDOWN_SECONDS = 6 * 3600
MAX_COOLDOWN_SECONDS = 365 * 86400
TEST_EVIDENCE = {"test": True}
SYMBOL_PATTERN = re.compile(r"[A-Z0-9]{1,15}")
RULE_FIELDS = frozenset({
    "name", "enabled", "urgency", "scope", "symbols", "conditions", "match",
    "cooldown_seconds", "quiet_hours",
})


class DuplicateRuleName(ValueError):
    pass

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
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return out if out == out and abs(out) != float("inf") else None


def _symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper().removesuffix("-USD").removesuffix("/USD")
    return symbol if SYMBOL_PATTERN.fullmatch(symbol) else None


def _one_of(actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    if isinstance(expected, (list, tuple, set)):
        return actual in expected
    return actual == expected


def _range(actual: float | None, expected: Any) -> bool:
    """``expected`` is a number (exact) or ``{"min": a, "max": b}``."""
    if actual is None:
        return False
    if isinstance(expected, Mapping):
        low, high = _num(expected.get("min")), _num(expected.get("max"))
        if not expected or any(key not in {"min", "max"} or _num(v) is None for key, v in expected.items()):
            return False
        return (low is None or actual >= low) and (high is None or actual <= high)
    target = _num(expected)
    return target is not None and actual == target


# ─── predicates ──────────────────────────────────────────────────────────────
# Each takes the snapshot for one coin (or the market) and the rule's value.


def _p_cycle_bucket(snap, value):
    return _one_of(snap.get("bucket"), value)


def _p_rotation_stage(snap, value):
    stage = snap.get("liquidity_rotation_stage")
    if not isinstance(stage, str):
        return False
    if isinstance(value, str) or isinstance(value, (list, tuple)):
        return _one_of(stage, value)
    return _range(_num(STAGE_NUMBERS.get(stage)), value)


def _p_rsi_regime(snap, value):
    if isinstance(value, Mapping):
        timeframe, regime = value.get("timeframe", "1w"), value.get("regime")
    else:
        timeframe, regime = "1w", value
    if not isinstance(timeframe, str):
        return False
    return _one_of((snap.get("rsi_regimes") or {}).get(timeframe), regime)


def _p_stoch_turn(snap, value):
    expected = "oversold_turn_up" if value is None or value is True else value
    return _one_of(snap.get("weekly_stoch_direction"), expected)


def _p_bool(key):
    def check(snap, value):
        actual = snap.get(key)
        return type(actual) is bool and actual is (True if value is None else value)

    return check


def _p_fib_zone(snap, value):
    price = _num(snap.get("price"))
    if price is None:
        return False
    if value in (None, "rollover_target_box"):
        box = snap.get("rollover_target_box")
        if not isinstance(box, Mapping):
            return False
        low, high = _num(box.get("low")), _num(box.get("high"))
    elif value == "at_multi_year_support":
        return snap.get("at_multi_year_support") is True
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
    """Flatten the scan's structured RSI evidence and optional position stop."""
    stop = row.get("accumulation_invalidation_stop")
    stop = stop if isinstance(stop, Mapping) else {}
    price = _num(row.get("price"))
    own_stop = _num((position or {}).get("stop_price"))
    cycle_stop = _num(stop.get("stop_price"))
    effective_stop = own_stop if own_stop is not None and own_stop > 0 else cycle_stop
    distance = _num(stop.get("stop_distance_pct"))
    if effective_stop is not None and effective_stop > 0 and price is not None and price > 0:
        distance = _num((price - effective_stop) / price * 100.0)

    cycle = row.get("multi_year_context")
    cycle_regimes = cycle.get("rsi_regimes") if isinstance(cycle, Mapping) else None
    regimes = {"1w": row.get("weekly_rsi_regime")}
    if isinstance(cycle_regimes, Mapping):
        for timeframe in ("1d", "1w", "1m"):
            block = cycle_regimes.get(timeframe)
            if isinstance(block, Mapping):
                regimes[timeframe] = block.get("regime")
    return {
        **row,
        "liquidity_rotation_stage": industry.get("liquidity_rotation_stage"),
        "rsi_regimes": {timeframe: regime for timeframe, regime in regimes.items() if regime in RSI_REGIMES},
        "stop_distance_pct": distance,
    }


def _enum_value(value: Any, choices: Iterable[str]) -> bool:
    values = value if isinstance(value, (list, tuple)) else [value]
    return bool(values) and all(isinstance(item, str) and item in choices for item in values)


def _numeric_value(value: Any, *, minimum: float | None = None, maximum: float | None = None) -> bool:
    if type(value) not in (int, float):
        return False
    number = _num(value)
    return (
        number is not None
        and (minimum is None or number >= minimum)
        and (maximum is None or number <= maximum)
    )


def _range_value(value: Any, **bounds) -> bool:
    if not isinstance(value, Mapping):
        return _numeric_value(value, **bounds)
    if not value or any(key not in {"min", "max"} or not _numeric_value(v, **bounds) for key, v in value.items()):
        return False
    return len(value) == 1 or value["min"] <= value["max"]


def _condition_value_valid(predicate: str, value: Any) -> bool:
    if predicate == "cycle_bucket":
        return _enum_value(value, BUCKETS)
    if predicate == "liquidity_rotation_stage":
        if _enum_value(value, STAGE_NUMBERS):
            return True
        values = value.values() if isinstance(value, Mapping) else (value,)
        return _range_value(value, minimum=1, maximum=4) and all(
            float(number).is_integer() for number in values
        )
    if predicate == "rsi_regime":
        if not isinstance(value, Mapping):
            return _enum_value(value, RSI_REGIMES)
        return (
            set(value) <= {"timeframe", "regime"}
            and value.get("timeframe", "1w") in ("1d", "1w", "1m")
            and _enum_value(value.get("regime"), RSI_REGIMES)
        )
    if predicate == "weekly_stoch_rsi_turn":
        return value is None or value is True or _enum_value(value, STOCH_DIRECTIONS)
    if predicate in BOOLEAN_PREDICATES:
        return value is None or type(value) is bool
    if predicate == "fib_zone_hit":
        if not isinstance(value, Mapping):
            return value in (None, "rollover_target_box", "at_multi_year_support")
        return (
            set(value) == {"low", "high"}
            and all(_numeric_value(value[key]) and value[key] > 0 for key in ("low", "high"))
            and value["low"] <= value["high"]
        )
    if predicate == "stop_proximity_pct":
        # Negative values express a stop already breached. Distance above a positive stop is <100%.
        return _range_value(value, maximum=100)
    return _numeric_value(value) and value > 0  # price_above and price_below


def validate_rule(rule: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(rule, Mapping) or set(rule) - RULE_FIELDS:
        raise ValueError("invalid rule fields")
    name = rule.get("name")
    if not isinstance(name, str) or not name.strip() or any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise ValueError("rule name must be nonempty text without control characters")
    name = name.strip()
    urgency = rule.get("urgency", "watch")
    if urgency not in URGENCIES:
        raise ValueError("invalid urgency")
    scope = rule.get("scope", "universe")
    if scope not in SCOPES:
        raise ValueError("invalid scope")
    enabled = rule.get("enabled", True)
    if type(enabled) is not bool:
        raise ValueError("enabled must be a boolean")
    conditions = rule.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("at least one condition is required")
    for condition in conditions:
        predicate = condition.get("predicate") if isinstance(condition, Mapping) else None
        if not isinstance(predicate, str) or predicate not in PREDICATES:
            raise ValueError("unknown predicate")
        if set(condition) - {"predicate", "value"} or not _condition_value_valid(predicate, condition.get("value")):
            raise ValueError(f"invalid value for {predicate}")
    match = rule.get("match", "all")
    if match not in ("all", "any"):
        raise ValueError("match must be 'all' or 'any'")
    cooldown = rule.get("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS)
    if type(cooldown) is not int or not 0 <= cooldown <= MAX_COOLDOWN_SECONDS:
        raise ValueError(f"cooldown_seconds must be an integer from 0 to {MAX_COOLDOWN_SECONDS}")
    quiet = rule.get("quiet_hours")
    if quiet is not None:
        if not isinstance(quiet, Mapping) or set(quiet) != {"start_hour", "end_hour"} or not all(
            type(hour) is int and 0 <= hour <= 23 for hour in quiet.values()
        ):
            raise ValueError("quiet_hours needs start_hour and end_hour from 0 to 23")
    raw_symbols = rule.get("symbols", [])
    if not isinstance(raw_symbols, list):
        raise ValueError("symbols must be a list")
    symbols = list(dict.fromkeys(_symbol(symbol) for symbol in raw_symbols))
    if None in symbols or (scope == "symbols" and not symbols):
        raise ValueError("expected valid symbols in the symbols list")
    if scope == "market" and any(c["predicate"] != "liquidity_rotation_stage" for c in conditions):
        raise ValueError("market rules require liquidity_rotation_stage conditions")
    return {
        "name": name,
        "enabled": enabled,
        "urgency": urgency,
        "scope": scope,
        "symbols": symbols,
        "conditions": [dict(c) for c in conditions],
        "match": match,
        "cooldown_seconds": cooldown,
        "quiet_hours": dict(quiet) if quiet is not None else None,
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
        with closing(self._connect()) as conn, conn:
            if conn.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
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
        """Insert missing defaults once, preserving user rules with the same name."""
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute(
                "SELECT 1 FROM smart_alert_meta WHERE key = 'defaults_seeded'"
            ).fetchone():
                return 0
            now = int(time.time())
            inserted = 0
            for rule in DEFAULT_RULES:
                inserted += self._insert_rule(
                    conn, validate_rule(rule), now, seeded=True, on_conflict="DO NOTHING"
                ).rowcount
            conn.execute(
                "INSERT INTO smart_alert_meta(key, value) VALUES ('defaults_seeded', ?)",
                (str(now),),
            )
        return inserted

    @staticmethod
    def _insert_rule(conn, clean, now, *, seeded=False, on_conflict=""):
        return conn.execute(
            """
            INSERT INTO smart_alert_rules(
                name, enabled, urgency, scope, rule_json, seeded, created_ts, updated_ts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """ + (f"ON CONFLICT(name) {on_conflict}" if on_conflict else ""),
            (
                clean["name"],
                int(clean["enabled"]),
                clean["urgency"],
                clean["scope"],
                json.dumps(clean, sort_keys=True, allow_nan=False),
                int(seeded),
                now,
                now,
            ),
        )

    def create_rule(self, rule: Mapping[str, Any]) -> dict:
        clean = validate_rule(rule)
        try:
            with closing(self._connect()) as conn, conn:
                cur = self._insert_rule(conn, clean, int(time.time()))
                row = conn.execute(
                    "SELECT * FROM smart_alert_rules WHERE id = ?", (cur.lastrowid,)
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise DuplicateRuleName("A rule with that name already exists.") from exc
        return self._rule(row)

    def upsert_rule(self, rule: Mapping[str, Any], *, seeded: bool = False) -> dict:
        clean = validate_rule(rule)
        with closing(self._connect()) as conn, conn:
            self._insert_rule(
                conn,
                clean,
                int(time.time()),
                seeded=seeded,
                on_conflict="""DO UPDATE SET
                    enabled = excluded.enabled,
                    urgency = excluded.urgency,
                    scope = excluded.scope,
                    rule_json = excluded.rule_json,
                    updated_ts = excluded.updated_ts""",
            )
            row = conn.execute(
                "SELECT * FROM smart_alert_rules WHERE name = ?", (clean["name"],)
            ).fetchone()
        return self._rule(row)

    @staticmethod
    def _rule_id(rule_id: int) -> int:
        if type(rule_id) is not int or not 0 < rule_id < 2**63:
            raise ValueError("rule_id must be a positive SQLite integer")
        return rule_id

    def set_enabled(self, rule_id: int, enabled: bool) -> dict:
        rule_id = self._rule_id(rule_id)
        if type(enabled) is not bool:
            raise ValueError("enabled must be a boolean")
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
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
        rule_id = self._rule_id(rule_id)
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM smart_alert_rules WHERE id = ?", (int(rule_id),)
            ).fetchone()
        return self._rule(row) if row else None

    def update_rule(self, rule_id: int, changes: Mapping[str, Any]) -> dict:
        """Validate and write the patch against the current rule in one transaction."""
        rule_id = self._rule_id(rule_id)
        if not isinstance(changes, Mapping):
            raise ValueError("rule changes must be an object")
        try:
            with closing(self._connect()) as conn, conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT * FROM smart_alert_rules WHERE id = ?", (rule_id,)
                ).fetchone()
                if row is None:
                    raise KeyError(rule_id)
                existing = self._rule(row)
                existing.pop("id")
                existing.pop("seeded")
                clean = validate_rule({**existing, **changes})
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
                        json.dumps(clean, sort_keys=True, allow_nan=False),
                        int(time.time()),
                        rule_id,
                    ),
                )
                updated = conn.execute(
                    "SELECT * FROM smart_alert_rules WHERE id = ?", (rule_id,)
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise DuplicateRuleName("A rule with that name already exists.") from exc
        return self._rule(updated)

    def send_test(
        self,
        *,
        urgency: str = "wake_up",
        rule_id: int | None = None,
        now: float | None = None,
    ) -> dict:
        """Record and try one delivery without consulting a real rule's cooldown."""
        if rule_id is not None:
            rule = self.get_rule(rule_id)
            if rule is None:
                raise KeyError(rule_id)
        else:
            if urgency not in URGENCIES:
                raise ValueError("invalid urgency")
            rule = {"id": 0, "name": "Test Alert", "urgency": urgency}
        now = float(now if now is not None else time.time())
        message = f"TEST · {rule['name']} · delivery check"
        with closing(self._connect()) as conn, conn:
            alert = self._insert_history(
                conn, rule, "TEST", now, message, dict(TEST_EVIDENCE), suppressed=None
            )
        return self._send_and_record(rule, alert, now)

    def delete_rule(self, rule_id: int) -> bool:
        """Delete the rule while preserving its historical alerts."""
        rule_id = self._rule_id(rule_id)
        with closing(self._connect()) as conn, conn:
            cur = conn.execute("DELETE FROM smart_alert_rules WHERE id = ?", (int(rule_id),))
        return cur.rowcount > 0

    def list_rules(self) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM smart_alert_rules ORDER BY id").fetchall()
        return [self._rule(row) for row in rows]

    def history(self, *, limit: int = 100, symbol: str | None = None) -> list[dict]:
        limit = min(max(int(limit), 1), 500)
        where, params = "", []
        if symbol:
            where, params = "WHERE symbol = ?", [_symbol(symbol)]
        with closing(self._connect()) as conn:
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
        industry = scan.get("industry")
        industry = industry if isinstance(industry, Mapping) else {}
        if rule["scope"] == "market":
            if industry.get("available"):
                yield "MARKET", {
                    **industry,
                    "liquidity_rotation_stage": industry.get("liquidity_rotation_stage"),
                }
            return
        coins = scan.get("coins")
        if not isinstance(coins, (list, tuple)):
            return
        rows = {
            symbol: row
            for row in coins
            if isinstance(row, Mapping)
            and row.get("available")
            and (symbol := _symbol(row.get("symbol")))
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
        for stored in self.list_rules():
            if not stored["enabled"]:
                continue
            try:
                rule = validate_rule({key: value for key, value in stored.items() if key not in {"id", "seeded"}})
            except ValueError:
                # Older versions allowed invalid predicate values to be persisted.
                logging.warning("Ignoring invalid smart alert rule %s", stored["id"])
                continue
            rule["id"] = stored["id"]
            for symbol, snapshot in self._targets(rule, scan, held, watch):
                if not self.matches(rule, snapshot):
                    continue
                alert = self._fire(rule, symbol, snapshot, now, deliver, stored)
                if alert is not None:
                    fired.append(alert)
        return fired

    def _fire(self, rule, symbol, snapshot, now, deliver, stored) -> dict | None:
        quiet = rule["quiet_hours"] if rule["quiet_hours"] is not None else self.default_quiet_hours
        quiet_push = rule["urgency"] == "action_queue" and in_quiet_hours(quiet, self.local_hour(now))
        suppressed = "quiet_hours" if quiet_push else None
        price = _num(snapshot.get("price"))
        message = f"{symbol} · {rule['name']}" + (f" · ${price:,.6g}" if price else "")
        evidence = {
            key: snapshot[key]
            for key in (
                "price",
                "bucket",
                "liquidity_rotation_stage",
                "rsi_regimes",
                "weekly_rsi",
                "weekly_stoch_direction",
                "daily_macd_kiss",
                "weekly_macd_bullish_cross",
                "breaking_confirmation_pivot",
                "at_multi_year_support",
                "stop_distance_pct",
                "rollover_target_box",
            )
            if snapshot.get(key) is not None
        }
        fired_ts = int(now)
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            latest = conn.execute(
                "SELECT * FROM smart_alert_rules WHERE id = ?", (rule["id"],)
            ).fetchone()
            if latest is None or self._rule(latest) != stored:
                return None
            last = conn.execute(
                """
                SELECT MAX(fired_ts) FROM smart_alert_history
                WHERE rule_id = ? AND symbol = ?
                  AND NOT (symbol = 'TEST' AND evidence_json = ?)
                  AND (suppressed_reason IS NULL OR ?)
                """,
                (rule["id"], symbol, json.dumps(TEST_EVIDENCE), quiet_push),
            ).fetchone()[0]
            if last is not None and fired_ts - last < rule["cooldown_seconds"]:
                return None
            alert = self._insert_history(conn, rule, symbol, now, message, evidence, suppressed)

        if deliver and suppressed is None:
            self._send_and_record(rule, alert, now)
        return alert

    @staticmethod
    def _insert_history(conn, rule, symbol, now, message, evidence, suppressed) -> dict:
        fired_ts = int(now)
        cur = conn.execute(
            """
            INSERT INTO smart_alert_history(
                rule_id, rule_name, symbol, urgency, fired_ts, message,
                evidence_json, delivered_json, suppressed_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, '{}', ?)
            """,
            (
                rule["id"],
                rule["name"],
                symbol,
                rule["urgency"],
                fired_ts,
                message,
                json.dumps(evidence, sort_keys=True, default=str),
                suppressed,
            ),
        )
        return {
            "id": cur.lastrowid,
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "symbol": symbol,
            "urgency": rule["urgency"],
            "fired_ts": fired_ts,
            "message": message,
            "evidence": evidence,
            "delivered": {},
            "suppressed_reason": suppressed,
        }

    def _send_and_record(self, rule, alert, now) -> dict:
        # Reserve the cooldown first and release SQLite before any network I/O.
        if rule["urgency"] == "watch":
            return alert
        delivered = self._deliver(rule, alert, now)
        if delivered:
            with closing(self._connect()) as conn, conn:
                conn.execute(
                    "UPDATE smart_alert_history SET delivered_json = ? WHERE id = ?",
                    (json.dumps(delivered, sort_keys=True), alert["id"]),
                )
            alert["delivered"] = delivered
        return alert

    def _deliver(self, rule, alert, now) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.ntfy_url:
            try:
                title = f"Moonwalking: {rule['name']}"[:200]
                if not title.isascii():
                    # ntfy supports RFC 2047 headers for non-ASCII titles.
                    title = Header(title, "utf-8", maxlinelen=1000).encode(linesep="")
                headers = {
                    "Title": title,
                    "Priority": NTFY_PRIORITY[rule["urgency"]],
                    "Tags": "rotating_light" if rule["urgency"] == "wake_up" else "chart",
                }
                self.http_post(self.ntfy_url, alert["message"], headers)
                out["ntfy"] = "sent"
            except Exception as exc:
                out["ntfy"] = f"failed:{type(exc).__name__}"
        if self.dispatcher is not None:
            event = {
                "id": f"smart:{rule['id']}:{alert['symbol']}:{alert['fired_ts']}:{alert['id']}",
                "symbol": alert["symbol"],
                "is_test": alert["evidence"].get("test", False),
                "primary_state": rule["name"],
                "modifier": rule["urgency"],
                "message": alert["message"],
                "confidence": 100 if rule["urgency"] == "wake_up" else 70,
                "event_ts_ms": int(now * 1000),
            }
            try:
                out["dispatcher"] = int(self.dispatcher.dispatch([event], now=now))
            except Exception as exc:
                out["dispatcher"] = f"failed:{type(exc).__name__}"
        return out
