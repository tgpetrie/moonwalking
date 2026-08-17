"""The dry-run must measure the real signal population, and measure its failures.

Every test here corresponds to a defect that shipped: the instrument treated
the whole universe as signalled, dropped exactly the signals whose feature
availability it existed to measure, and would have written a row per eligible
coin per scan.
"""

from __future__ import annotations

import pytest

try:
    from control_dry_run import ControlDryRunStore, MOVE_HORIZONS
except Exception:  # pragma: no cover
    from backend.control_dry_run import ControlDryRunStore, MOVE_HORIZONS  # type: ignore


def _row(symbol, *, move=1.0, vol=1.0, staleness=0, qv=1_000_000.0, liquidity="normal"):
    return {
        "symbol": symbol,
        "live_label": "Breakout",
        "raw_inputs": {
            "pct_1m": move / 10.0,
            "pct_3m": move / 3.0,
            "pct_1h": move,
            "realized_volatility_pct_hour": vol,
            "realized_volatility_staleness_seconds": staleness,
            "quote_volume_usd": qv,
            "liquidity": liquidity,
        },
    }


def _universe(n=12, **kw):
    # Moves close enough to sit inside the caliper of one another.
    return {
        f"C{i}": _row(f"C{i}", move=1.0 + i * 0.02, vol=1.0 + i * 0.005, **kw)
        for i in range(n)
    }


def _event(
    symbol,
    signal_id=None,
    state="Breakout",
    direction="up",
    label="CONTINUATION FAVORED",
):
    return {
        "id": signal_id or f"sig-{symbol}",
        "product_id": f"{symbol}-USD",
        "primary_state": state,
        "direction": direction,
        "the_read": {"label": label},
    }


def _store(tmp_path, name="dry.sqlite"):
    return ControlDryRunStore(tmp_path / name)


def test_records_nothing_without_signal_events(tmp_path):
    """No universe-wide fallback: an empty signal list means nothing happened."""
    store = _store(tmp_path)
    assert store.record(_universe(), 1_700_000_000, []) == 0
    assert store.report()["signals_observed"] == 0


def test_only_signalled_coins_are_observed(tmp_path):
    """12 coins in the universe, 2 signalling — 2 signals observed, not 12."""
    store = _store(tmp_path)
    store.record(_universe(), 1_700_000_000, [_event("C0"), _event("C1")])

    report = store.report()
    assert report["signals_observed"] == 2


def test_signal_ids_deduplicate_across_scans(tmp_path):
    """Re-observing the same signal is a no-op, not an extra row nor a revision."""
    store = _store(tmp_path)
    universe = _universe()
    store.record(universe, 1_700_000_000, [_event("C0")])
    store.record(universe, 1_700_000_060, [_event("C0")])
    store.record(universe, 1_700_000_120, [_event("C0")])

    report = store.report()
    assert report["signals_observed"] == 1
    # One row per horizon per rung, regardless of how many scans saw it.
    assert report["observations"] == len(MOVE_HORIZONS) * 3


def test_real_event_metadata_is_preserved(tmp_path):
    """Category coverage is only meaningful against the real category."""
    store = _store(tmp_path)
    store.record(
        _universe(),
        1_700_000_000,
        [
            _event(
                "C0",
                state="Reversal Risk",
                direction="down",
                label="BREAKDOWN CONFIRMED",
            )
        ],
    )

    report = store.report()
    assert "Reversal Risk|down|BREAKDOWN CONFIRMED" in report["by_category"]


def test_missing_volatility_is_recorded_not_dropped(tmp_path):
    """Feature unavailability is the measurement, not something to filter out."""
    store = _store(tmp_path)
    universe = _universe()
    universe["C0"]["raw_inputs"]["realized_volatility_pct_hour"] = None

    store.record(universe, 1_700_000_000, [_event("C0")])

    report = store.report()
    assert report["signals_observed"] == 1
    assert report["unmatchable_reasons"]["1h"].get("volatility_unavailable") == 1
    # Counted in the denominator, so coverage reflects the real failure rate.
    assert report["rungs"]["categorical_bucket"]["1h"]["coverage"] == 0.0


def test_stale_volatility_counts_as_unavailable(tmp_path):
    store = _store(tmp_path)
    universe = _universe()
    universe["C0"]["raw_inputs"]["realized_volatility_staleness_seconds"] = 9999

    store.record(universe, 1_700_000_000, [_event("C0")])
    assert (
        store.report()["unmatchable_reasons"]["1h"].get("volatility_unavailable") == 1
    )


def test_signal_absent_from_ranking_is_recorded(tmp_path):
    store = _store(tmp_path)
    store.record(_universe(), 1_700_000_000, [_event("MISSING")])
    assert store.report()["unmatchable_reasons"]["1h"].get("no_ranking_row") == 1


def test_concurrently_signalled_coins_are_excluded_from_peers(tmp_path):
    """A coin we are calling right now is not an example of saying nothing."""
    universe = _universe(n=6)
    all_symbols = [f"C{i}" for i in range(6)]

    lone = _store(tmp_path, "lone.sqlite")
    lone.record(universe, 1_700_000_000, [_event("C0")])
    lone_size = lone.report()["rungs"]["omitted"]["1h"]["median_basket_size"]

    crowded = _store(tmp_path, "crowded.sqlite")
    crowded.record(universe, 1_700_000_000, [_event(s) for s in all_symbols])
    crowded_size = crowded.report()["rungs"]["omitted"]["1h"]["median_basket_size"]

    # With every coin signalling, no candidate remains to serve as a control.
    assert lone_size > 0
    assert crowded_size == 0


def test_all_three_move_horizons_are_evaluated(tmp_path):
    store = _store(tmp_path)
    store.record(_universe(), 1_700_000_000, [_event("C0")])

    rungs = store.report()["rungs"]
    for rung in rungs.values():
        assert set(rung.keys()) == set(MOVE_HORIZONS)
        assert all(v["observations"] > 0 for v in rung.values())


def test_report_never_selects_a_rung(tmp_path):
    """Selection stays a human decision made from coverage and balance."""
    store = _store(tmp_path)
    store.record(_universe(), 1_700_000_000, [_event("C0")])
    assert store.report()["selected_rung"] is None
    assert store.report()["outcome_blind"] is True


# ---------------------------------------------------------------------------
# Schema migration, first-observation immutability, full cross-product report
# ---------------------------------------------------------------------------


OLD_SCHEMA = """
CREATE TABLE dry_run_observations (
    observed_ts INTEGER NOT NULL,
    config_version TEXT NOT NULL,
    product_id TEXT NOT NULL,
    primary_state TEXT,
    direction TEXT,
    read_label TEXT,
    has_volatility INTEGER NOT NULL,
    has_quote_volume INTEGER NOT NULL,
    has_categorical_liquidity INTEGER NOT NULL,
    universe_size INTEGER NOT NULL,
    universe_with_volatility INTEGER NOT NULL,
    universe_with_quote_volume INTEGER NOT NULL,
    rung TEXT NOT NULL,
    basket_size INTEGER NOT NULL,
    basket_met_minimum INTEGER NOT NULL,
    signal_move_pct REAL,
    signal_volatility REAL,
    signal_quote_volume REAL,
    basket_mean_move_pct REAL,
    basket_mean_volatility REAL,
    basket_mean_quote_volume REAL,
    PRIMARY KEY (observed_ts, product_id, rung)
)
"""


def test_incompatible_existing_table_is_archived_and_recreated(tmp_path):
    """A pre-existing older table must be detected, not silently kept.

    `CREATE TABLE IF NOT EXISTS` leaves the old shape in place, and every
    insert then fails at runtime instead of at migration time.
    """
    import sqlite3

    db = tmp_path / "old.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(OLD_SCHEMA)
    conn.execute(
        "INSERT INTO dry_run_observations (observed_ts, config_version, product_id,"
        " has_volatility, has_quote_volume, has_categorical_liquidity, universe_size,"
        " universe_with_volatility, universe_with_quote_volume, rung, basket_size,"
        " basket_met_minimum) VALUES (1,'old','BTC-USD',1,1,1,10,10,10,'omitted',3,1)"
    )
    conn.commit()
    conn.close()

    store = ControlDryRunStore(db)

    conn = sqlite3.connect(db)
    try:
        columns = {
            r[1] for r in conn.execute("PRAGMA table_info(dry_run_observations)")
        }
        assert "signal_id" in columns and "horizon" in columns
        # Old rows are set aside, not destroyed.
        archives = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE 'dry_run_observations_archived%'"
            )
        ]
        assert len(archives) == 1
        archived = conn.execute(f"SELECT COUNT(*) FROM {archives[0]}").fetchone()[0]
        assert archived == 1
    finally:
        conn.close()

    # And the recreated table accepts writes.
    assert store.record(_universe(), 1_700_000_000, [_event("C0")]) > 0


def test_migration_is_idempotent(tmp_path):
    db = tmp_path / "idem.sqlite"
    first = ControlDryRunStore(db)
    first.record(_universe(), 1_700_000_000, [_event("C0")])
    before = first.report()["observations"]

    # Re-opening a current-shape database must not archive or clear anything.
    second = ControlDryRunStore(db)
    assert second.report()["observations"] == before


def test_rescan_cannot_alter_the_first_observation(tmp_path):
    """The first observation describes conditions when the signal fired.

    A later scan that finds features now must not overwrite an availability
    failure the signal actually had, or coverage drifts upward the longer a
    signal stays live.
    """
    import sqlite3

    store = _store(tmp_path, "immutable.sqlite")
    universe = _universe()
    universe["C0"]["raw_inputs"]["realized_volatility_pct_hour"] = None

    store.record(universe, 1_700_000_000, [_event("C0")])

    def snapshot():
        conn = sqlite3.connect(store.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM dry_run_observations ORDER BY horizon, rung"
                )
            ]
        finally:
            conn.close()

    original = snapshot()
    assert original, "first observation should have been written"
    assert all(r["unmatchable_reason"] == "volatility_unavailable" for r in original)

    # Same signal id, later scan, features now fully available.
    store.record(_universe(), 1_700_009_999, [_event("C0")])

    after = snapshot()
    assert after == original, "a rescan must not revise the original observation"
    # Specifically: timestamp, availability failure, features and basket.
    assert all(r["observed_ts"] == 1_700_000_000 for r in after)
    assert all(r["unmatchable_reason"] == "volatility_unavailable" for r in after)
    assert all(r["signal_volatility"] is None for r in after)
    assert all(r["basket_size"] == 0 for r in after)
    assert store.report()["unmatchable_reasons"]["1h"]["volatility_unavailable"] == 1


def test_config_version_change_creates_a_new_observation(tmp_path):
    """A caliper change is a different observation, not a correction."""
    import control_dry_run as module

    store = _store(tmp_path, "cfg.sqlite")
    store.record(_universe(), 1_700_000_000, [_event("C0")])
    baseline = store.report()["observations"]

    original = module.DRY_RUN_CONFIG_VERSION
    try:
        module.DRY_RUN_CONFIG_VERSION = "dryrun-test.2"
        store.record(_universe(), 1_700_000_600, [_event("C0")])
        # The new config's rows are separate; the report scopes to one version.
        assert store.report()["observations"] == baseline
    finally:
        module.DRY_RUN_CONFIG_VERSION = original

    assert store.report()["observations"] == baseline


def test_report_breaks_out_category_by_rung_and_horizon(tmp_path):
    """Aggregate adequacy can hide a starved category at a needed horizon."""
    store = _store(tmp_path, "xprod.sqlite")
    store.record(
        _universe(),
        1_700_000_000,
        [
            _event(
                "C0", state="Breakout", direction="up", label="CONTINUATION FAVORED"
            ),
            _event(
                "C1",
                state="Reversal Risk",
                direction="down",
                label="BREAKDOWN CONFIRMED",
            ),
        ],
    )

    report = store.report()
    from control_dry_run import LIQUIDITY_RUNGS

    assert set(report["by_category"]) == {
        "Breakout|up|CONTINUATION FAVORED",
        "Reversal Risk|down|BREAKDOWN CONFIRMED",
    }
    for category, rungs in report["by_category"].items():
        assert set(rungs) == set(LIQUIDITY_RUNGS)
        for rung, horizons in rungs.items():
            assert set(horizons) == set(MOVE_HORIZONS)
            for horizon, cell in horizons.items():
                assert "coverage" in cell and "balance" in cell
                assert cell["observations"] == 1


def test_move_availability_is_reported_per_horizon(tmp_path):
    store = _store(tmp_path, "moves.sqlite")
    universe = _universe()
    universe["C0"]["raw_inputs"]["pct_1m"] = None

    store.record(universe, 1_700_000_000, [_event("C0")])

    report = store.report()
    assert report["feature_availability"]["signalled_with_move"]["1m"] == 0.0
    assert report["feature_availability"]["signalled_with_move"]["1h"] == 1.0
    assert report["unmatchable_reasons"]["1m"].get("move_unavailable") == 1
    assert report["unmatchable_reasons"]["1h"] == {}


def _sqlite(db):
    import sqlite3

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


CURRENT_COLUMNS_WRONG_KEY = """
CREATE TABLE dry_run_observations (
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
    PRIMARY KEY (signal_id, horizon, rung)
)
"""


def test_correct_columns_but_wrong_primary_key_is_migrated(tmp_path):
    """Column names alone do not make a schema compatible.

    This table has every expected column but keys on the pre-fix tuple, so
    INSERT OR IGNORE would treat two different config versions as duplicates
    and silently discard the second — no error, just a missing observation.
    """
    from control_dry_run import ControlDryRunStore as Store

    db = tmp_path / "wrongkey.sqlite"
    conn = _sqlite(db)
    conn.execute(CURRENT_COLUMNS_WRONG_KEY)
    conn.execute(
        "INSERT INTO dry_run_observations (signal_id, observed_ts, config_version,"
        " product_id, has_volatility, has_move, has_quote_volume,"
        " has_categorical_liquidity, universe_size, universe_with_volatility,"
        " universe_with_quote_volume, horizon, rung, basket_size, basket_met_minimum)"
        " VALUES ('s1',1,'old','BTC-USD',1,1,1,1,10,10,10,'1h','omitted',3,1)"
    )
    conn.commit()
    conn.close()

    Store(db)

    conn = _sqlite(db)
    try:
        pk = [
            r["name"]
            for r in sorted(
                (
                    r
                    for r in conn.execute("PRAGMA table_info(dry_run_observations)")
                    if r["pk"] > 0
                ),
                key=lambda r: r["pk"],
            )
        ]
        assert pk == ["signal_id", "config_version", "horizon", "rung"]
        archives = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE 'dry_run_observations_archived%'"
            )
        ]
        assert len(archives) == 1
        assert conn.execute(f"SELECT COUNT(*) FROM {archives[0]}").fetchone()[0] == 1
    finally:
        conn.close()


def test_reporting_index_belongs_to_the_live_table_after_migration(tmp_path):
    """RENAME carries indexes with the table, and index names are global.

    The follow-up CREATE INDEX IF NOT EXISTS then finds the name taken and does
    nothing, leaving the live table unindexed while the archive keeps the index.
    """
    from control_dry_run import ControlDryRunStore as Store

    db = tmp_path / "index.sqlite"
    conn = _sqlite(db)
    conn.execute(OLD_SCHEMA)
    conn.execute(
        "CREATE INDEX ix_dry_run_rung ON dry_run_observations(rung, config_version)"
    )
    conn.commit()
    conn.close()

    Store(db)

    conn = _sqlite(db)
    try:
        row = conn.execute(
            "SELECT tbl_name FROM sqlite_master WHERE type='index' AND name = 'ix_dry_run_rung'"
        ).fetchone()
        assert row is not None, "reporting index must exist after migration"
        assert row["tbl_name"] == "dry_run_observations"
    finally:
        conn.close()


def test_repeated_migrations_never_destroy_an_earlier_archive(tmp_path):
    """Archives are the only record of what a superseded instrument measured."""
    from control_dry_run import ControlDryRunStore as Store

    db = tmp_path / "archives.sqlite"

    conn = _sqlite(db)
    conn.execute(OLD_SCHEMA)
    conn.execute(
        "INSERT INTO dry_run_observations (observed_ts, config_version, product_id,"
        " has_volatility, has_quote_volume, has_categorical_liquidity, universe_size,"
        " universe_with_volatility, universe_with_quote_volume, rung, basket_size,"
        " basket_met_minimum) VALUES (1,'first','BTC-USD',1,1,1,10,10,10,'omitted',3,1)"
    )
    conn.commit()
    conn.close()

    Store(db)  # first migration

    # A second superseded shape appears later.
    conn = _sqlite(db)
    conn.execute("DROP TABLE dry_run_observations")
    conn.execute(CURRENT_COLUMNS_WRONG_KEY)
    conn.execute(
        "INSERT INTO dry_run_observations (signal_id, observed_ts, config_version,"
        " product_id, has_volatility, has_move, has_quote_volume,"
        " has_categorical_liquidity, universe_size, universe_with_volatility,"
        " universe_with_quote_volume, horizon, rung, basket_size, basket_met_minimum)"
        " VALUES ('s2',2,'second','ETH-USD',1,1,1,1,10,10,10,'1h','omitted',3,1)"
    )
    conn.commit()
    conn.close()

    Store(db)  # second migration

    conn = _sqlite(db)
    try:
        archives = sorted(
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE 'dry_run_observations_archived%'"
            )
        )
        assert len(archives) == 2, f"both archives must survive, got {archives}"
        preserved = {
            conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            for name in archives
        }
        assert preserved == {1}
    finally:
        conn.close()
