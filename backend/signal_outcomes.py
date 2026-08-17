"""Durable forward-outcome measurement for Event Evolution transitions."""

from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Any, Iterable
import math
import os
import sqlite3
import threading
import time

from live_ranking import build_feature_snapshot


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "signal_outcomes.sqlite"
CHECKPOINTS = (
    (300, "return_5m"),
    (900, "return_15m"),
    (1800, "return_30m"),
    (3600, "return_60m"),
)

# --- Methodology versioning -------------------------------------------------
#
# Every row records the methodology that produced it.  A rate may only be
# published from rows whose methodology carries a control group; rows without
# one can never be made honest after the fact, because the matched-peer
# behaviour they would need was never recorded and the price tape holding it is
# pruned at 24h.
#
# Phase 0 collects no controls yet, so new rows are still uncontrolled and the
# publishable version is None: no rate is publishable from any row. Phase 1
# introduces "v2_peer_controlled" and moves both constants together.
LEGACY_METHODOLOGY_VERSION = "v1_uncontrolled"
COLLECTION_METHODOLOGY_VERSION = (
    os.getenv("MW_COLLECTION_METHODOLOGY") or LEGACY_METHODOLOGY_VERSION
)

# Table that will hold the matched-peer and placebo controls. Its absence is
# the structural proof that no row has a control behind it, and publication is
# gated on it existing rather than on a configuration string. Phase 0 does not
# create it, so Phase 0 cannot publish a rate by any configuration.
CONTROL_TABLE_NAME = "signal_controls"


def _sanitise_publishable(value: str | None) -> str | None:
    """Refuse to accept a version that is uncontrolled by definition.

    Without this, `MW_PUBLISHABLE_METHODOLOGY=v1_uncontrolled` would republish
    the entire legacy history — the precise outcome this module exists to
    prevent — from a single environment variable.
    """
    version = (value or "").strip()
    if not version:
        return None
    if version == LEGACY_METHODOLOGY_VERSION:
        raise ValueError(
            f"{LEGACY_METHODOLOGY_VERSION!r} can never be publishable: those rows "
            "have no control group and none can be reconstructed."
        )
    return version


PUBLISHABLE_METHODOLOGY_VERSION: str | None = _sanitise_publishable(
    os.getenv("MW_PUBLISHABLE_METHODOLOGY")
)

# Evidence gate.  These size the "still collecting" progress readout; they are
# not headline thresholds and no claim is made from them.
MARKET_PERIOD_SECONDS = 7200
EVIDENCE_GATE_MARKET_PERIODS = max(
    1, int(os.getenv("MW_EVIDENCE_GATE_MARKET_PERIODS", "100"))
)
EVIDENCE_GATE_SPAN_DAYS = max(1, int(os.getenv("MW_EVIDENCE_GATE_SPAN_DAYS", "14")))

# Shape returned for any category whose track has not cleared the evidence
# gate.  Every performance field is None by construction, so a learning
# category cannot render a percentage no matter what a client does with it.
_NULL_PERFORMANCE: dict[str, Any] = {
    "win_rate": None,
    "recent_win_rate": None,
    "recent_sample": None,
    "median_favorable_pct": None,
    "median_adverse_pct": None,
    "median_return": {"5m": None, "15m": None, "30m": None, "60m": None},
}


def _number(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except Exception:
        return None


class SignalOutcomeStore:
    """Record each published event transition and grade its next hour."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        collection_methodology: str | None = None,
        publishable_methodology: str | None = None,
    ):
        configured = os.getenv("MW_SIGNAL_OUTCOMES_DB")
        self.db_path = Path(db_path or configured or DEFAULT_DB_PATH)
        # Carried per-store rather than read from module globals so that any
        # caller electing to publish has to say so explicitly. A test or a
        # future phase opts in; nothing gets there by default.
        self.collection_methodology = (
            collection_methodology or COLLECTION_METHODOLOGY_VERSION
        )
        self.publishable_methodology = (
            _sanitise_publishable(publishable_methodology)
            if publishable_methodology is not None
            else PUBLISHABLE_METHODOLOGY_VERSION
        )
        self.target_pct = max(0.1, float(os.getenv("MW_OUTCOME_TARGET_PCT", "2.0")))
        self.adverse_pct = max(0.1, float(os.getenv("MW_OUTCOME_ADVERSE_PCT", "1.0")))
        self.horizon_seconds = max(
            300, int(os.getenv("MW_OUTCOME_HORIZON_SECONDS", "3600"))
        )
        self._init_lock = threading.Lock()
        self._history_lock = threading.Lock()
        self._history_cache: dict[
            tuple[str, str, str], tuple[float, dict[str, Any]]
        ] = {}
        self.ensure_db()

    def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_db(self):
        with self._init_lock:
            conn = self._connect()
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS signal_outcomes (
                        signal_id TEXT PRIMARY KEY,
                        event_id TEXT NOT NULL,
                        product_id TEXT NOT NULL,
                        primary_state TEXT NOT NULL,
                        read_label TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        confidence INTEGER NOT NULL,
                        started_ts INTEGER NOT NULL,
                        start_price REAL NOT NULL,
                        last_ts INTEGER NOT NULL,
                        last_price REAL NOT NULL,
                        return_5m REAL,
                        return_15m REAL,
                        return_30m REAL,
                        return_60m REAL,
                        max_favorable_pct REAL NOT NULL DEFAULT 0,
                        max_adverse_pct REAL NOT NULL DEFAULT 0,
                        target_hit_ts INTEGER,
                        adverse_hit_ts INTEGER,
                        outcome TEXT,
                        complete INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_signal_outcomes_compare "
                    "ON signal_outcomes(primary_state, direction, read_label, complete)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_signal_outcomes_open "
                    "ON signal_outcomes(complete, started_ts)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_signal_outcomes_product "
                    "ON signal_outcomes(product_id, complete)"
                )
                # Safe additive migration: no-op on a fresh DB; adds columns to
                # existing DBs without disturbing current rows (they remain NULL).
                existing = {
                    row[1] for row in conn.execute("PRAGMA table_info(signal_outcomes)")
                }
                for col_def in (
                    "feature_schema_version TEXT",
                    "feature_snapshot_json TEXT",
                    "methodology_version TEXT",
                ):
                    if col_def.split()[0] not in existing:
                        conn.execute(
                            f"ALTER TABLE signal_outcomes ADD COLUMN {col_def}"
                        )
                # Existing rows were graded without a control group.  Label them
                # rather than deleting them: they remain useful for research and
                # for measuring attrition, and are simply never publishable.
                conn.execute(
                    "UPDATE signal_outcomes SET methodology_version = ? "
                    "WHERE methodology_version IS NULL",
                    (LEGACY_METHODOLOGY_VERSION,),
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_signal_outcomes_methodology "
                    "ON signal_outcomes(methodology_version, complete)"
                )
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _product(event: dict[str, Any]) -> str:
        raw = str(event.get("product_id") or event.get("symbol") or "").upper()
        return raw if "-" in raw else f"{raw}-USD"

    @staticmethod
    def _event_price(event: dict[str, Any], prices: dict[str, Any]) -> float | None:
        product_id = SignalOutcomeStore._product(event)
        symbol = product_id.split("-")[0]
        parsed = _number(
            prices.get(product_id) if product_id in prices else prices.get(symbol)
        )
        return parsed if parsed is not None and parsed > 0 else None

    @staticmethod
    def _directional_return(direction: str, start: float, current: float) -> float:
        raw = ((current / start) - 1.0) * 100.0
        return -raw if str(direction).lower() == "down" else raw

    def observe(
        self,
        events: Iterable[dict[str, Any]],
        current_prices: dict[str, Any],
        *,
        now_ts: int | None = None,
        ranking_snapshot: dict[str, dict[str, Any]] | None = None,
        ranking_captured_ts: int | None = None,
    ) -> None:
        """Record new transitions and advance grading for open ones.

        ``ranking_snapshot`` maps bare symbol -> a build_live_rankings() row
        built with include_internal_features=True.  ``ranking_captured_ts`` is
        the instant that ranking calculation started; both are required
        together, because a snapshot dated by this method's own clock would
        misdate the state it claims to describe.  Snapshots are attached only
        to rows created by this call — the INSERT OR IGNORE below leaves an
        existing row, and its original snapshot, untouched.
        """
        now_ts = int(now_ts or time.time())
        prices = current_prices if isinstance(current_prices, dict) else {}
        rankings = ranking_snapshot if isinstance(ranking_snapshot, dict) else {}
        if ranking_captured_ts is None:
            rankings = {}
        conn = self._connect()
        try:
            for event in events or []:
                if not isinstance(event, dict) or not event.get("id"):
                    continue
                price = self._event_price(event, prices)
                if price is None:
                    continue
                started_ts = now_ts
                read = (
                    event.get("the_read")
                    if isinstance(event.get("the_read"), dict)
                    else {}
                )
                product_id = self._product(event)
                symbol = product_id.split("-")[0]
                ranking_row = rankings.get(symbol)
                if ranking_row is not None:
                    feat_ver, feat_json = build_feature_snapshot(
                        ranking_row, int(ranking_captured_ts)
                    )
                else:
                    feat_ver, feat_json = None, None
                conn.execute(
                    """
                    INSERT OR IGNORE INTO signal_outcomes (
                        signal_id, event_id, product_id, primary_state, read_label,
                        direction, confidence, started_ts, start_price, last_ts, last_price,
                        feature_schema_version, feature_snapshot_json, methodology_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(event["id"]),
                        str(event.get("event_id") or event["id"]),
                        product_id,
                        str(event.get("primary_state") or "Building"),
                        str(read.get("label") or "UNCLASSIFIED"),
                        str(event.get("direction") or "neutral"),
                        int(_number(event.get("confidence")) or 0),
                        started_ts,
                        price,
                        now_ts,
                        price,
                        feat_ver,
                        feat_json,
                        self.collection_methodology,
                    ),
                )

            open_rows = conn.execute(
                "SELECT * FROM signal_outcomes WHERE complete = 0 AND started_ts <= ?",
                (now_ts,),
            ).fetchall()
            for row in open_rows:
                product_id = str(row["product_id"])
                symbol = product_id.split("-")[0]
                current = _number(
                    prices.get(product_id)
                    if product_id in prices
                    else prices.get(symbol)
                )
                age = max(0, now_ts - int(row["started_ts"]))
                if current is None or current <= 0:
                    if age >= self.horizon_seconds:
                        target_hit = row["target_hit_ts"]
                        adverse_hit = row["adverse_hit_ts"]
                        won = target_hit is not None and (
                            adverse_hit is None or int(target_hit) < int(adverse_hit)
                        )
                        outcome = (
                            "followed_through" if won else "did_not_follow_through"
                        )
                        conn.execute(
                            "UPDATE signal_outcomes SET outcome = ?, complete = 1 "
                            "WHERE signal_id = ?",
                            (outcome, row["signal_id"]),
                        )
                    continue
                directional = self._directional_return(
                    row["direction"], float(row["start_price"]), current
                )
                max_favorable = float(row["max_favorable_pct"] or 0)
                max_adverse = float(row["max_adverse_pct"] or 0)
                target_hit = row["target_hit_ts"]
                adverse_hit = row["adverse_hit_ts"]
                if age <= self.horizon_seconds:
                    max_favorable = max(max_favorable, directional)
                    max_adverse = min(max_adverse, directional)
                    if target_hit is None and directional >= self.target_pct:
                        target_hit = now_ts
                    if adverse_hit is None and directional <= -self.adverse_pct:
                        adverse_hit = now_ts

                updates: dict[str, Any] = {
                    "last_ts": now_ts,
                    "last_price": current,
                    "max_favorable_pct": max_favorable,
                    "max_adverse_pct": max_adverse,
                    "target_hit_ts": target_hit,
                    "adverse_hit_ts": adverse_hit,
                }
                checkpoint = next(
                    (
                        (seconds, column)
                        for seconds, column in reversed(CHECKPOINTS)
                        if age >= seconds
                    ),
                    None,
                )
                if checkpoint is not None:
                    _, column = checkpoint
                    if row[column] is None:
                        updates[column] = directional
                if age >= self.horizon_seconds:
                    won = target_hit is not None and (
                        adverse_hit is None or int(target_hit) < int(adverse_hit)
                    )
                    updates["outcome"] = (
                        "followed_through" if won else "did_not_follow_through"
                    )
                    updates["complete"] = 1

                assignments = ", ".join(f"{key} = ?" for key in updates)
                conn.execute(
                    f"UPDATE signal_outcomes SET {assignments} WHERE signal_id = ?",
                    [*updates.values(), row["signal_id"]],
                )
            conn.commit()
        finally:
            conn.close()
        with self._history_lock:
            self._history_cache.clear()

    def history_for(self, event: dict[str, Any]) -> dict[str, Any]:
        read = event.get("the_read") if isinstance(event.get("the_read"), dict) else {}
        state = str(event.get("primary_state") or "Building")
        direction = str(event.get("direction") or "neutral")
        read_label = str(read.get("label") or "UNCLASSIFIED")
        cache_key = (state, direction, read_label)
        with self._history_lock:
            cached = self._history_cache.get(cache_key)
            if cached and (time.monotonic() - cached[0]) < 30:
                return dict(cached[1])

        # Single chokepoint.  This method feeds the popup, the portfolio card,
        # alert evidence and event enrichment; returning a null rate here takes
        # every one of them to "collecting" at once, so no surface can quote an
        # uncontrolled number by having been missed.
        if not self.publication_enabled():
            result = self._learning_history()
            with self._history_lock:
                self._history_cache[cache_key] = (time.monotonic(), dict(result))
            return result

        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT outcome, max_favorable_pct, max_adverse_pct, started_ts
                FROM signal_outcomes
                WHERE complete = 1 AND methodology_version = ?
                  AND primary_state = ? AND direction = ? AND read_label = ?
                ORDER BY started_ts DESC LIMIT 500
                """,
                (self.publishable_methodology, state, direction, read_label),
            ).fetchall()
            if len(rows) < 5:
                rows = conn.execute(
                    """
                    SELECT outcome, max_favorable_pct, max_adverse_pct, started_ts
                    FROM signal_outcomes
                    WHERE complete = 1 AND methodology_version = ?
                      AND primary_state = ? AND direction = ?
                    ORDER BY started_ts DESC LIMIT 500
                    """,
                    (self.publishable_methodology, state, direction),
                ).fetchall()
        finally:
            conn.close()

        # Same evidence gate the scorecard applies. Without it a single
        # controlled row would publish a 100% rate to four surfaces at once.
        if not self._evidence_gate_met([dict(row) for row in rows]):
            result = self._learning_history()
            with self._history_lock:
                self._history_cache[cache_key] = (time.monotonic(), dict(result))
            return result

        sample_size = len(rows)
        wins = sum(1 for row in rows if row["outcome"] == "followed_through")
        favorable = [float(row["max_favorable_pct"] or 0) for row in rows]
        adverse = [float(row["max_adverse_pct"] or 0) for row in rows]
        result = {
            "sample_size": sample_size,
            "follow_through_rate": (wins / sample_size) if sample_size else None,
            "target_pct": self.target_pct,
            "adverse_pct": self.adverse_pct,
            "median_favorable_pct": round(median(favorable), 3) if favorable else None,
            "median_adverse_pct": round(median(adverse), 3) if adverse else None,
            "horizon_minutes": int(self.horizon_seconds / 60),
            "rule": "target_before_adverse_within_horizon",
            "methodology_version": self.publishable_methodology,
            "measurement_status": "measured",
        }
        with self._history_lock:
            self._history_cache[cache_key] = (time.monotonic(), dict(result))
        return result

    def _learning_history(self) -> dict[str, Any]:
        """History payload for a signal with no publishable evidence behind it.

        Deliberately keeps ``sample_size`` at 0 rather than reporting the
        legacy row count.  A large count beside a missing rate still reads as
        accumulated evidence, and none of those rows can ever back a rate.
        """
        return {
            "sample_size": 0,
            "follow_through_rate": None,
            "target_pct": self.target_pct,
            "adverse_pct": self.adverse_pct,
            "median_favorable_pct": None,
            "median_adverse_pct": None,
            "horizon_minutes": int(self.horizon_seconds / 60),
            "rule": "target_before_adverse_within_horizon",
            "methodology_version": self.publishable_methodology,
            "measurement_status": "learning",
            "required_market_periods": EVIDENCE_GATE_MARKET_PERIODS,
            "market_periods": 0,
        }

    def _controls_available(self, conn) -> bool:
        """True only when the control tables physically exist."""
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (CONTROL_TABLE_NAME,),
        ).fetchone()
        return row is not None

    def publication_enabled(self, conn=None) -> bool:
        """Whether any rate may be published at all.

        Fail-closed by construction: a configured version is necessary but not
        sufficient. Controls must structurally exist, so no combination of
        environment variables can open a publishing path before the machinery
        that makes a rate meaningful has been built.
        """
        if not self.publishable_methodology:
            return False
        if self.publishable_methodology == LEGACY_METHODOLOGY_VERSION:
            return False
        if conn is not None:
            return self._controls_available(conn)
        owned = self._connect()
        try:
            return self._controls_available(owned)
        finally:
            owned.close()

    @staticmethod
    def _evidence_gate_met(entries: list[dict[str, Any]]) -> bool:
        """Per-category evidence gate: enough market periods over enough days.

        Row count is deliberately not a criterion — thousands of rows inside a
        handful of hours is the pseudo-replication that made the old numbers
        meaningless.
        """
        if not entries:
            return False
        periods = {int(e["started_ts"]) // MARKET_PERIOD_SECONDS for e in entries}
        if len(periods) < EVIDENCE_GATE_MARKET_PERIODS:
            return False
        oldest = min(int(e["started_ts"]) for e in entries)
        newest = max(int(e["started_ts"]) for e in entries)
        return (newest - oldest) / 86400.0 >= EVIDENCE_GATE_SPAN_DAYS

    def _publishable_counts(
        self, conn, product_id: str | None = None
    ) -> tuple[int, int, int]:
        """Return (rows, market_periods, span_days) over publishable rows only."""
        if self.publishable_methodology is None:
            return 0, 0, 0
        where = "complete = 1 AND methodology_version = ?"
        params: list[Any] = [self.publishable_methodology]
        if product_id:
            where += " AND product_id = ?"
            params.append(product_id)
        row = conn.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT started_ts / {MARKET_PERIOD_SECONDS}), "
            f"MIN(started_ts), MAX(started_ts) FROM signal_outcomes WHERE {where}",
            params,
        ).fetchone()
        rows = int(row[0] or 0)
        periods = int(row[1] or 0)
        span = 0
        if row[2] is not None and row[3] is not None:
            span = int(max(0, int(row[3]) - int(row[2])) / 86400)
        return rows, periods, span

    def status(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            total = int(
                conn.execute("SELECT COUNT(*) FROM signal_outcomes").fetchone()[0]
            )
            complete = int(
                conn.execute(
                    "SELECT COUNT(*) FROM signal_outcomes WHERE complete = 1"
                ).fetchone()[0]
            )
            excluded = int(
                conn.execute(
                    "SELECT COUNT(*) FROM signal_outcomes WHERE complete = 1 AND "
                    "(methodology_version IS NULL OR methodology_version != ?)",
                    (self.publishable_methodology or "",),
                ).fetchone()[0]
            )
            _, periods, span_days = self._publishable_counts(conn)
        finally:
            conn.close()
        return {
            "total": total,
            "complete": complete,
            "collecting": total - complete,
            "target_pct": self.target_pct,
            "adverse_pct": self.adverse_pct,
            "horizon_minutes": int(self.horizon_seconds / 60),
            "collection_methodology": self.collection_methodology,
            "publishable_methodology": self.publishable_methodology,
            # Surfaced so the exclusion is auditable, never as evidence for a
            # category: these rows have no control group and never will.
            "research_only_rows_excluded": excluded,
            "market_periods": periods,
            "required_market_periods": EVIDENCE_GATE_MARKET_PERIODS,
            "span_days": span_days,
            "required_span_days": EVIDENCE_GATE_SPAN_DAYS,
        }

    @staticmethod
    def _med(entries: list[dict[str, Any]], col: str) -> float | None:
        vals = [float(e[col]) for e in entries if e[col] is not None]
        return round(median(vals), 3) if vals else None

    @staticmethod
    def _build_signal_card(
        state: str, direction: str, label: str, entries: list[dict[str, Any]]
    ) -> dict[str, Any]:
        n = len(entries)
        wins = sum(1 for e in entries if e["outcome"] == "followed_through")
        recent = entries[:50]
        recent_n = len(recent)
        recent_wins = sum(1 for e in recent if e["outcome"] == "followed_through")
        med = SignalOutcomeStore._med
        return {
            "state": state,
            "direction": direction,
            "label": label,
            "sample_size": n,
            "win_rate": round(wins / n, 4),
            "recent_win_rate": round(recent_wins / recent_n, 4) if recent_n else None,
            "recent_sample": recent_n,
            "median_favorable_pct": med(entries, "max_favorable_pct"),
            "median_adverse_pct": med(entries, "max_adverse_pct"),
            "median_return": {
                "5m": med(entries, "return_5m"),
                "15m": med(entries, "return_15m"),
                "30m": med(entries, "return_30m"),
                "60m": med(entries, "return_60m"),
            },
            "oldest_ts": min((e["started_ts"] for e in entries), default=None),
            "newest_ts": max((e["started_ts"] for e in entries), default=None),
        }

    @staticmethod
    def _learning_card(
        state: str,
        direction: str,
        label: str,
        *,
        peer_market_periods: int = 0,
    ) -> dict[str, Any]:
        """A category the client can render without it carrying any claim.

        The taxonomy (state/direction/label) is not a performance statement, so
        it is safe to list.  Every number that could be read as evidence is
        None or zero, and the two tracks report progress separately because
        they fill at different rates.
        """
        return {
            "state": state,
            "direction": direction,
            "label": label,
            "sample_size": 0,
            "peer_status": "learning",
            "placebo_status": "learning",
            "peer_market_periods": peer_market_periods,
            # Placebo controls do not exist until Phase 2, so this track cannot
            # have made progress and must not imply that it has.
            "placebo_market_periods": 0,
            "required_market_periods": EVIDENCE_GATE_MARKET_PERIODS,
            "peer_coverage": None,
            "placebo_coverage": None,
            "peer_lift": None,
            "placebo_lift": None,
            "oldest_ts": None,
            "newest_ts": None,
            **{
                key: (dict(value) if isinstance(value, dict) else value)
                for key, value in _NULL_PERFORMANCE.items()
            },
        }

    def _cards_from_rows(
        self, rows: list[Any], min_samples: int, *, publishing: bool
    ) -> list[dict[str, Any]]:
        """Build category cards.

        Legacy rows contribute **taxonomy only** — the set of categories that
        exist, so a client can render progress for each. They never enter an
        aggregate. Mixing them in produced the reproducible contradiction of an
        overall rate of 0.0 sitting beside a category card reading 0.9.
        """
        taxonomy: list[tuple[str, str, str]] = []
        publishable_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        seen: set[tuple[str, str, str]] = set()
        for row in rows:
            key = (row["primary_state"], row["direction"], row["read_label"])
            if key not in seen:
                seen.add(key)
                taxonomy.append(key)
            if (
                publishing
                and row["methodology_version"] == self.publishable_methodology
            ):
                publishable_groups.setdefault(key, []).append(dict(row))

        cards: list[dict[str, Any]] = []
        for state, direction, label in taxonomy:
            entries = publishable_groups.get((state, direction, label), [])
            if (
                publishing
                and len(entries) >= min_samples
                and self._evidence_gate_met(entries)
            ):
                cards.append(
                    SignalOutcomeStore._build_signal_card(
                        state, direction, label, entries
                    )
                )
            else:
                cards.append(
                    SignalOutcomeStore._learning_card(
                        state,
                        direction,
                        label,
                        peer_market_periods=len(
                            {
                                int(e["started_ts"]) // MARKET_PERIOD_SECONDS
                                for e in entries
                            }
                        ),
                    )
                )
        cards.sort(
            key=lambda c: (-c["sample_size"], c["state"], c["direction"], c["label"])
        )
        return cards

    def scorecard(self, *, min_samples: int = 5) -> dict[str, Any]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT primary_state, direction, read_label, outcome,
                       return_5m, return_15m, return_30m, return_60m,
                       max_favorable_pct, max_adverse_pct, started_ts,
                       methodology_version
                FROM signal_outcomes
                WHERE complete = 1
                ORDER BY started_ts DESC
                """
            ).fetchall()
        finally:
            conn.close()

        publishing = self.publication_enabled()
        publishable = [
            r
            for r in rows
            if publishing and r["methodology_version"] == self.publishable_methodology
        ]
        total = len(publishable)
        total_wins = sum(1 for r in publishable if r["outcome"] == "followed_through")
        periods = len(
            {int(r["started_ts"]) // MARKET_PERIOD_SECONDS for r in publishable}
        )
        gate_met = self._evidence_gate_met(publishable)

        return {
            "measurement_status": "measured" if (total and gate_met) else "learning",
            "total_graded": total,
            # The overall rate was the "21% average" every category was judged
            # against.  It stays None until it comes from controlled rows.
            "overall_win_rate": (
                round(total_wins / total, 4) if (total and gate_met) else None
            ),
            "target_pct": self.target_pct,
            "adverse_pct": self.adverse_pct,
            "horizon_minutes": int(self.horizon_seconds / 60),
            "publishable_methodology": self.publishable_methodology,
            "research_only_rows_excluded": len(rows) - total,
            "market_periods": periods,
            "required_market_periods": EVIDENCE_GATE_MARKET_PERIODS,
            "required_span_days": EVIDENCE_GATE_SPAN_DAYS,
            "signal_types": self._cards_from_rows(
                rows, min_samples, publishing=publishing
            ),
        }

    def coin_scorecard(
        self, product_id: str, *, min_samples: int = 5
    ) -> dict[str, Any]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT primary_state, direction, read_label, outcome,
                       return_5m, return_15m, return_30m, return_60m,
                       max_favorable_pct, max_adverse_pct, started_ts,
                       methodology_version
                FROM signal_outcomes
                WHERE complete = 1 AND product_id = ?
                ORDER BY started_ts DESC
                """,
                (product_id,),
            ).fetchall()
        finally:
            conn.close()

        publishing = self.publication_enabled()
        publishable = [
            r
            for r in rows
            if publishing and r["methodology_version"] == self.publishable_methodology
        ]

        return {
            "product_id": product_id,
            # Counts publishable outcomes only.  The popup prints this as
            # "N comparable outcomes", which reads as evidence, so it must not
            # include rows that can never back a rate.
            "total_outcomes": len(publishable),
            "target_pct": self.target_pct,
            "adverse_pct": self.adverse_pct,
            "horizon_minutes": int(self.horizon_seconds / 60),
            "measurement_status": (
                "measured"
                if (publishable and self._evidence_gate_met(publishable))
                else "learning"
            ),
            "publishable_methodology": self.publishable_methodology,
            "research_only_rows_excluded": len(rows) - len(publishable),
            "required_market_periods": EVIDENCE_GATE_MARKET_PERIODS,
            "signal_types": self._cards_from_rows(
                rows, min_samples, publishing=publishing
            ),
        }


store = SignalOutcomeStore()
