"""Outcome-blind feasibility instrument for the matched-peer control.

Answers three questions, prospectively, before any control is built:

1. Are the matching inputs actually present, on signalled coins and on the
   candidate universe?
2. What share of signals could find a credible peer basket, per caliper
   variant?
3. After matching, are the peers *balanced* against the signals they stand in
   for?

Coverage alone does not make a control credible — a basket that is easy to fill
but systematically more liquid or more volatile than the coin it benchmarks
would understate or overstate lift without ever failing a coverage check. So
balance is measured here too, and both feed the liquidity-rung decision.

**This module must never read outcomes.** It records what was knowable at
signal time and nothing about what happened afterwards. That is what makes the
rung selection honest: a variant cannot be preferred because it flatters the
result, since the result is not available to compare against. The prohibition
is enforced by `test_control_dry_run.py`, which fails if this file references
the outcome columns at all.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import json
import logging
import math
import os
import sqlite3
import threading
import time

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "control_dry_run.sqlite"

# Frozen dry-run configuration. Recorded with every observation so a later
# reading cannot be attributed to the wrong settings, and so changing a caliper
# is visible as a version change rather than a silent drift.
DRY_RUN_CONFIG_VERSION = "dryrun-2026-08-17.1"

# Caliper variants evaluated side by side. These are matching tolerances, not
# headline thresholds: none of them decides whether a claim is published.
MOVE_RELATIVE_TOLERANCE = 0.25
MOVE_ABSOLUTE_FLOOR_PP = 0.15
VOLATILITY_RELATIVE_TOLERANCE = 0.25
TARGET_BASKET_SIZE = 5
MINIMUM_BASKET_SIZE = 3
VOLATILITY_MAX_STALENESS_SECONDS = 120

# All three move horizons are evaluated separately. Coverage differs by
# horizon, and picking one would hide that.
MOVE_HORIZONS = ("1m", "3m", "1h")

# Liquidity rungs, in the pre-registered order of preference. The dry-run
# reports all three; it does not choose between them.
LIQUIDITY_RUNGS = ("quote_volume_decile", "categorical_bucket", "omitted")

_STABLECOINS = {"USDC", "USDT", "DAI", "PYUSD", "GUSD", "USDS", "EURC"}


def _symbol_of(event: dict[str, Any]) -> str:
    raw = str(event.get("product_id") or event.get("symbol") or "").strip().upper()
    return raw.split("-")[0] if raw else ""


def _number(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except Exception:
        return None


class ControlDryRunStore:
    def __init__(self, db_path: str | Path | None = None):
        configured = os.getenv("MW_CONTROL_DRY_RUN_DB")
        self.db_path = Path(db_path or configured or DEFAULT_DB_PATH)
        self._init_lock = threading.Lock()
        self.ensure_db()

    def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # Columns the current instrument writes. Compared explicitly on startup:
    # `CREATE TABLE IF NOT EXISTS` silently leaves an older, incompatible table
    # in place, and every insert against it then fails at runtime rather than
    # at migration time.
    _EXPECTED_COLUMNS = frozenset(
        {
            "signal_id",
            "observed_ts",
            "config_version",
            "product_id",
            "primary_state",
            "direction",
            "read_label",
            "has_volatility",
            "has_move",
            "has_quote_volume",
            "has_categorical_liquidity",
            "unmatchable_reason",
            "universe_size",
            "universe_with_volatility",
            "universe_with_quote_volume",
            "horizon",
            "rung",
            "basket_size",
            "basket_met_minimum",
            "signal_move_pct",
            "signal_volatility",
            "signal_quote_volume",
            "basket_mean_move_pct",
            "basket_mean_volatility",
            "basket_mean_quote_volume",
        }
    )

    # Ordered primary key the current instrument depends on. Column names alone
    # are not enough: a table can carry every expected column while still
    # keying on an older tuple, and the wrong key changes what INSERT OR IGNORE
    # considers a duplicate — silently, with no error to notice.
    _EXPECTED_PRIMARY_KEY = ("signal_id", "config_version", "horizon", "rung")

    _INDEX_NAME = "ix_dry_run_rung"

    @staticmethod
    def _primary_key_of(conn, table: str) -> tuple[str, ...]:
        """Ordered primary key columns, by their declared key position."""
        members = [
            (int(row[5]), str(row[1]))
            for row in conn.execute(f"PRAGMA table_info({table})")
            if int(row[5]) > 0
        ]
        return tuple(name for _, name in sorted(members))

    def _next_archive_name(self, conn) -> str:
        """A never-reused archive name.

        Archives are the only record of what a superseded instrument measured.
        Overwriting one on a second migration would destroy that history for a
        gain of nothing.
        """
        taken = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE 'dry_run_observations_archived%'"
            )
        }
        index = 1
        while f"dry_run_observations_archived_{index:03d}" in taken:
            index += 1
        return f"dry_run_observations_archived_{index:03d}"

    def _migrate_incompatible_table(self, conn) -> str | None:
        """Set aside a pre-existing table whose shape no longer matches.

        Rows written by an earlier instrument are archived rather than dropped
        — they are wrong about the population they measured, not worthless as a
        record of what that instrument did — but they must not sit in the live
        table, where a report would mix two incompatible definitions.

        Returns the archive table name when a migration happened.
        """
        existing = [
            row[1] for row in conn.execute("PRAGMA table_info(dry_run_observations)")
        ]
        if not existing:
            return None

        columns_match = set(existing) == self._EXPECTED_COLUMNS
        key_matches = (
            self._primary_key_of(conn, "dry_run_observations")
            == self._EXPECTED_PRIMARY_KEY
        )
        if columns_match and key_matches:
            return None

        archive = self._next_archive_name(conn)
        conn.execute(f"ALTER TABLE dry_run_observations RENAME TO {archive}")
        # RENAME carries the table's indexes with it, and index names are
        # database-wide, so the CREATE INDEX IF NOT EXISTS that follows would
        # find the name already taken and quietly do nothing — leaving the live
        # table unindexed. Drop it here so it is rebuilt against the new table.
        conn.execute(f"DROP INDEX IF EXISTS {self._INDEX_NAME}")
        return archive

    def ensure_db(self):
        with self._init_lock:
            conn = self._connect()
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                archived = self._migrate_incompatible_table(conn)
                if archived:
                    logging.warning(
                        "control_dry_run: incompatible dry_run_observations "
                        "schema found; archived to %s and recreated. Prior "
                        "observations do not carry over.",
                        archived,
                    )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dry_run_observations (
                        signal_id TEXT NOT NULL,
                        observed_ts INTEGER NOT NULL,
                        config_version TEXT NOT NULL,
                        product_id TEXT NOT NULL,
                        primary_state TEXT,
                        direction TEXT,
                        read_label TEXT,
                        has_volatility INTEGER NOT NULL,
                        has_move INTEGER NOT NULL,
                        has_quote_volume INTEGER NOT NULL,
                        has_categorical_liquidity INTEGER NOT NULL,
                        unmatchable_reason TEXT,
                        universe_size INTEGER NOT NULL,
                        universe_with_volatility INTEGER NOT NULL,
                        universe_with_quote_volume INTEGER NOT NULL,
                        horizon TEXT NOT NULL,
                        rung TEXT NOT NULL,
                        basket_size INTEGER NOT NULL,
                        basket_met_minimum INTEGER NOT NULL,
                        signal_move_pct REAL,
                        signal_volatility REAL,
                        signal_quote_volume REAL,
                        basket_mean_move_pct REAL,
                        basket_mean_volatility REAL,
                        basket_mean_quote_volume REAL,
                        -- config_version is part of the key: a caliper change
                        -- produces a genuinely different observation of the
                        -- same signal, not a correction of the old one.
                        PRIMARY KEY (signal_id, config_version, horizon, rung)
                    )
                    """
                )
                # Asserted against the live table rather than trusted: a stale
                # index owned by an archive satisfies IF NOT EXISTS while
                # leaving the table it is supposed to serve unindexed.
                owner = conn.execute(
                    "SELECT tbl_name FROM sqlite_master WHERE type='index' AND name = ?",
                    (self._INDEX_NAME,),
                ).fetchone()
                if owner and str(owner[0]) != "dry_run_observations":
                    conn.execute(f"DROP INDEX IF EXISTS {self._INDEX_NAME}")
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS {self._INDEX_NAME} "
                    "ON dry_run_observations(rung, config_version)"
                )
                conn.commit()
            finally:
                conn.close()

    # -- matching ---------------------------------------------------------

    @staticmethod
    def _within_move(candidate: float, target: float) -> bool:
        tolerance = max(abs(target) * MOVE_RELATIVE_TOLERANCE, MOVE_ABSOLUTE_FLOOR_PP)
        return abs(candidate - target) <= tolerance

    @staticmethod
    def _within_volatility(candidate: float, target: float) -> bool:
        if target <= 0:
            return False
        return abs(candidate - target) <= abs(target) * VOLATILITY_RELATIVE_TOLERANCE

    @staticmethod
    def _deciles(values: list[float]) -> list[float]:
        if not values:
            return []
        ordered = sorted(values)
        return [
            ordered[min(len(ordered) - 1, int(len(ordered) * q / 10))]
            for q in range(1, 10)
        ]

    @staticmethod
    def _decile_of(value: float, cuts: list[float]) -> int:
        rank = 0
        for cut in cuts:
            if value > cut:
                rank += 1
        return rank

    def _select_basket(
        self,
        *,
        signal: dict[str, Any],
        candidates: list[dict[str, Any]],
        rung: str,
        horizon: str,
        excluded_symbols: set[str],
    ) -> list[dict[str, Any]]:
        """Deterministic top-K peers under one liquidity rung and horizon.

        Ordering is by normalised distance then symbol, so the basket does not
        depend on the order candidates were supplied in.
        """
        target_move = signal["move"]
        target_vol = signal["volatility"]
        target_decile = signal.get("decile")
        target_bucket = signal.get("liquidity_bucket")

        scored: list[tuple[float, str, dict[str, Any]]] = []
        for row in candidates:
            if row["symbol"] == signal["symbol"]:
                continue
            # A coin signalling right now cannot serve as a control for what
            # happens without a signal.
            if row["symbol"] in excluded_symbols:
                continue
            move = row["moves"].get(horizon)
            vol = row["volatility"]
            if move is None or vol is None:
                continue
            if (target_move >= 0) != (move >= 0):
                continue
            if not self._within_move(move, target_move):
                continue
            if not self._within_volatility(vol, target_vol):
                continue
            if rung == "quote_volume_decile":
                if row.get("decile") is None or target_decile is None:
                    continue
                if row["decile"] != target_decile:
                    continue
            elif rung == "categorical_bucket":
                if not target_bucket or row.get("liquidity_bucket") != target_bucket:
                    continue
            move_term = abs(move - target_move) / max(abs(target_move), 1e-9)
            vol_term = abs(vol - target_vol) / max(abs(target_vol), 1e-9)
            scored.append((move_term + vol_term, row["symbol"], row))

        scored.sort(key=lambda item: (item[0], item[1]))
        return [row for _, _, row in scored[:TARGET_BASKET_SIZE]]

    # -- recording --------------------------------------------------------

    def record(
        self,
        ranking_snapshot: dict[str, dict[str, Any]],
        captured_ts: int,
        signal_events: Iterable[dict[str, Any]],
    ) -> int:
        """Record one observation per real signal, per horizon, per rung.

        ``signal_events`` are the actual Event Evolution transitions being
        written this scan — never a stand-in. There is deliberately no default:
        an earlier version fell back to "the whole universe is signalled",
        which measured a population that does not exist and would have written
        a row for every eligible coin on every scan.

        Signals missing volatility, a move, or liquidity are recorded as failed
        observations with a reason rather than dropped, because feature
        unavailability is the primary thing this instrument exists to measure —
        discarding it would report coverage over exactly the signals that had
        coverage.

        Re-observing the same signal on a later scan is a no-op: the first
        observation is the one that describes conditions when the signal fired,
        and it is never revised.

        Nothing here consults an outcome store, and no argument carries a result.
        """
        events = [e for e in (signal_events or []) if isinstance(e, dict)]
        if not events:
            return 0

        universe: list[dict[str, Any]] = []
        for symbol, row in (ranking_snapshot or {}).items():
            sym = str(symbol or "").upper()
            if not sym or sym in _STABLECOINS:
                continue
            raw = row.get("raw_inputs") if isinstance(row, dict) else None
            if not isinstance(raw, dict):
                continue
            staleness = _number(raw.get("realized_volatility_staleness_seconds"))
            fresh = (
                staleness is not None and staleness <= VOLATILITY_MAX_STALENESS_SECONDS
            )
            universe.append(
                {
                    "symbol": sym,
                    "product_id": f"{sym}-USD",
                    "moves": {
                        horizon: _number(raw.get(f"pct_{horizon}"))
                        for horizon in MOVE_HORIZONS
                    },
                    "volatility": (
                        _number(raw.get("realized_volatility_pct_hour"))
                        if fresh
                        else None
                    ),
                    "quote_volume": _number(raw.get("quote_volume_usd")),
                    "liquidity_bucket": raw.get("liquidity"),
                }
            )

        universe_size = len(universe)
        with_vol = sum(1 for r in universe if r["volatility"] is not None)
        with_qv = sum(1 for r in universe if r["quote_volume"] is not None)
        decile_cuts = self._deciles(
            [r["quote_volume"] for r in universe if r["quote_volume"] is not None]
        )
        for row in universe:
            row["decile"] = (
                self._decile_of(row["quote_volume"], decile_cuts)
                if row["quote_volume"] is not None and decile_cuts
                else None
            )
        by_symbol = {row["symbol"]: row for row in universe}

        # Every coin signalling on this scan is barred from being anyone's
        # control. A coin we are calling right now is not an example of what
        # happens when we say nothing.
        signalled_symbols = {_symbol_of(event) for event in events if _symbol_of(event)}

        written = 0
        conn = self._connect()
        try:
            for event in events:
                symbol = _symbol_of(event)
                if not symbol:
                    continue
                signal_id = str(event.get("id") or event.get("event_id") or "")
                if not signal_id:
                    continue
                read = (
                    event.get("the_read")
                    if isinstance(event.get("the_read"), dict)
                    else {}
                )
                features = by_symbol.get(symbol)

                base_reason = None
                if features is None:
                    base_reason = "no_ranking_row"
                elif features["volatility"] is None:
                    base_reason = "volatility_unavailable"

                for horizon in MOVE_HORIZONS:
                    move = features["moves"].get(horizon) if features else None
                    reason = base_reason or (
                        "move_unavailable" if move is None else None
                    )
                    for rung in LIQUIDITY_RUNGS:
                        if reason is not None:
                            basket: list[dict[str, Any]] = []
                        else:
                            basket = self._select_basket(
                                signal={**features, "move": move},
                                candidates=universe,
                                rung=rung,
                                horizon=horizon,
                                excluded_symbols=signalled_symbols,
                            )
                        size = len(basket)

                        def mean(key: str) -> float | None:
                            values = [
                                (r["moves"][horizon] if key == "move" else r[key])
                                for r in basket
                            ]
                            values = [v for v in values if v is not None]
                            return sum(values) / len(values) if values else None

                        # IGNORE, never REPLACE. The question is what was
                        # available *at signal time*; a later scan that finds
                        # volatility now would overwrite a real availability
                        # failure with a success the signal never had, and
                        # coverage would drift upward the longer a signal
                        # stayed live.
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO dry_run_observations (
                                signal_id, observed_ts, config_version, product_id,
                                primary_state, direction, read_label,
                                has_volatility, has_move, has_quote_volume,
                                has_categorical_liquidity, unmatchable_reason,
                                universe_size, universe_with_volatility,
                                universe_with_quote_volume, horizon, rung,
                                basket_size, basket_met_minimum,
                                signal_move_pct, signal_volatility,
                                signal_quote_volume, basket_mean_move_pct,
                                basket_mean_volatility, basket_mean_quote_volume
                            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                signal_id,
                                int(captured_ts),
                                DRY_RUN_CONFIG_VERSION,
                                f"{symbol}-USD",
                                # Real event metadata, not a stand-in: coverage
                                # has to be reportable per actual category.
                                str(event.get("primary_state") or "Building"),
                                str(event.get("direction") or "neutral"),
                                str(read.get("label") or "UNCLASSIFIED"),
                                (
                                    1
                                    if features and features["volatility"] is not None
                                    else 0
                                ),
                                1 if move is not None else 0,
                                (
                                    1
                                    if features and features["quote_volume"] is not None
                                    else 0
                                ),
                                (
                                    1
                                    if features and features.get("liquidity_bucket")
                                    else 0
                                ),
                                reason,
                                universe_size,
                                with_vol,
                                with_qv,
                                horizon,
                                rung,
                                size,
                                1 if size >= MINIMUM_BASKET_SIZE else 0,
                                move,
                                features["volatility"] if features else None,
                                features["quote_volume"] if features else None,
                                mean("move"),
                                mean("volatility"),
                                mean("quote_volume"),
                            ),
                        )
                        written += 1
            conn.commit()
        finally:
            conn.close()
        return written

    # -- reporting --------------------------------------------------------

    @staticmethod
    def _standardised_difference(
        signal_values: list[float], control_values: list[float]
    ) -> float | None:
        """Standardised mean difference — the balance diagnostic.

        Convention: |SMD| <= 0.1 is treated as balanced. Reported, not enforced;
        the rung decision reads it but this module does not make that decision.
        """
        pairs = [
            (s, c)
            for s, c in zip(signal_values, control_values)
            if s is not None and c is not None
        ]
        if len(pairs) < 2:
            return None
        sig = [p[0] for p in pairs]
        ctl = [p[1] for p in pairs]
        mean_s = sum(sig) / len(sig)
        mean_c = sum(ctl) / len(ctl)
        var_s = sum((v - mean_s) ** 2 for v in sig) / max(1, len(sig) - 1)
        var_c = sum((v - mean_c) ** 2 for v in ctl) / max(1, len(ctl) - 1)
        pooled = math.sqrt((var_s + var_c) / 2.0)
        if pooled <= 0:
            return 0.0
        return round((mean_s - mean_c) / pooled, 4)

    def report(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            rows = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM dry_run_observations WHERE config_version = ?",
                    (DRY_RUN_CONFIG_VERSION,),
                ).fetchall()
            ]
        finally:
            conn.close()

        signals = {r["signal_id"] for r in rows}
        distinct_ts = sorted({r["observed_ts"] for r in rows})
        span_hours = (
            round((distinct_ts[-1] - distinct_ts[0]) / 3600.0, 2)
            if len(distinct_ts) > 1
            else 0.0
        )

        def summarise(subset: list[dict[str, Any]]) -> dict[str, Any]:
            if not subset:
                return {"observations": 0, "coverage": None, "balance": {}}
            met = sum(1 for r in subset if r["basket_met_minimum"])
            matched = [r for r in subset if r["basket_met_minimum"]]
            return {
                "observations": len(subset),
                # Denominator is every signal seen, including those that could
                # not be matched at all. Coverage over only matchable signals
                # would report close to 100% by construction.
                "coverage": round(met / len(subset), 4),
                "median_basket_size": (
                    sorted(r["basket_size"] for r in subset)[len(subset) // 2]
                ),
                "balance": {
                    "move_pct": self._standardised_difference(
                        [r["signal_move_pct"] for r in matched],
                        [r["basket_mean_move_pct"] for r in matched],
                    ),
                    "volatility": self._standardised_difference(
                        [r["signal_volatility"] for r in matched],
                        [r["basket_mean_volatility"] for r in matched],
                    ),
                    "quote_volume": self._standardised_difference(
                        [r["signal_quote_volume"] for r in matched],
                        [r["basket_mean_quote_volume"] for r in matched],
                    ),
                },
            }

        rungs = {
            rung: {
                horizon: summarise(
                    [r for r in rows if r["rung"] == rung and r["horizon"] == horizon]
                )
                for horizon in MOVE_HORIZONS
            }
            for rung in LIQUIDITY_RUNGS
        }

        # Coverage and balance across the full cross-product. Reporting only
        # one rung at one horizon hid exactly the comparison the dry-run
        # exists to make: whether a rung that looks adequate in aggregate is
        # adequate for the categories that actually need it, and whether that
        # holds at the horizons the matcher will use.
        categories = sorted(
            {f"{r['primary_state']}|{r['direction']}|{r['read_label']}" for r in rows}
        )
        by_category: dict[str, Any] = {}
        for category in categories:
            by_category[category] = {
                rung: {
                    horizon: summarise(
                        [
                            r
                            for r in rows
                            if r["rung"] == rung
                            and r["horizon"] == horizon
                            and f"{r['primary_state']}|{r['direction']}|{r['read_label']}"
                            == category
                        ]
                    )
                    for horizon in MOVE_HORIZONS
                }
                for rung in LIQUIDITY_RUNGS
            }

        # Failed observations are first-class output: they are the availability
        # measurement, not noise to be filtered away. Keyed by horizon because
        # move availability differs between 1m, 3m and 1h; the rung is fixed
        # only to avoid counting the same signal once per rung, since the
        # reason never depends on the rung.
        unmatchable: dict[str, dict[str, int]] = {}
        for horizon in MOVE_HORIZONS:
            counts: dict[str, int] = {}
            for r in rows:
                if r["rung"] != LIQUIDITY_RUNGS[0] or r["horizon"] != horizon:
                    continue
                if r["unmatchable_reason"]:
                    counts[r["unmatchable_reason"]] = (
                        counts.get(r["unmatchable_reason"], 0) + 1
                    )
            unmatchable[horizon] = counts

        # One row per signal, taken at a fixed rung and horizon purely to
        # deduplicate: volatility and liquidity availability do not vary across
        # either. Move availability does, so it is reported per horizon.
        feature_rows = [
            r
            for r in rows
            if r["rung"] == LIQUIDITY_RUNGS[0] and r["horizon"] == MOVE_HORIZONS[-1]
        ]
        availability: dict[str, Any] = {}
        if feature_rows:
            latest = max(r["observed_ts"] for r in feature_rows)
            sample = next(r for r in feature_rows if r["observed_ts"] == latest)
            total = len(feature_rows)
            availability = {
                "universe_size": sample["universe_size"],
                "universe_with_volatility": sample["universe_with_volatility"],
                "universe_with_quote_volume": sample["universe_with_quote_volume"],
                "signalled_with_volatility": round(
                    sum(1 for r in feature_rows if r["has_volatility"]) / total, 4
                ),
                "signalled_with_quote_volume": round(
                    sum(1 for r in feature_rows if r["has_quote_volume"]) / total, 4
                ),
                "signalled_with_categorical_liquidity": round(
                    sum(1 for r in feature_rows if r["has_categorical_liquidity"])
                    / total,
                    4,
                ),
                "signalled_with_move": {
                    horizon: round(
                        sum(
                            1
                            for r in rows
                            if r["rung"] == LIQUIDITY_RUNGS[0]
                            and r["horizon"] == horizon
                            and r["has_move"]
                        )
                        / total,
                        4,
                    )
                    for horizon in MOVE_HORIZONS
                },
            }

        return {
            "config_version": DRY_RUN_CONFIG_VERSION,
            "outcome_blind": True,
            "signals_observed": len(signals),
            "observations": len(rows),
            "distinct_observation_times": len(distinct_ts),
            "span_hours": span_hours,
            "balance_threshold_abs_smd": 0.1,
            "minimum_basket_size": MINIMUM_BASKET_SIZE,
            "target_basket_size": TARGET_BASKET_SIZE,
            "move_horizons": list(MOVE_HORIZONS),
            "feature_availability": availability,
            "unmatchable_reasons": unmatchable,
            "rungs": rungs,
            "by_category": by_category,
            # Deliberately absent: any selection of a rung. Coverage and balance
            # are reported; the choice is made once collection is adequate, and
            # never from this process.
            "selected_rung": None,
        }


store = ControlDryRunStore()


def record_dry_run_observation(
    ranking_snapshot: dict[str, dict[str, Any]],
    captured_ts: int,
    signal_events: Iterable[dict[str, Any]],
) -> int:
    """``signal_events`` is required — there is no universe-wide fallback."""
    return store.record(ranking_snapshot, captured_ts, signal_events)


def dry_run_report() -> dict[str, Any]:
    return store.report()


if __name__ == "__main__":  # pragma: no cover - operator entry point
    print(json.dumps(dry_run_report(), indent=2))
