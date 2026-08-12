"""Tests for the observability-only point-in-time feature snapshot layer.

The layer must be invisible to everything except the two outcome tables.  These
tests are grouped by the property they defend:

- TestPublicPayloadCompatibility: enabling feature collection cannot change the
  payload the frontend receives.
- TestBuildFeatureSnapshot: serialization is deterministic and fail-closed.
- TestPeekPurity: the early observability read mutates no runtime state.
- TestScannerCallOrder: the published alert/ranking sample stays at its
  original call site, and the early sample is never reused for it.
- TestSampleDivergence: an alert expiring between the two samples moves the
  snapshot only, never the published ranking.
- TestSignalOutcomeSnapshot / TestBoardOutcomeSnapshot: correct provenance and
  immutability at the storage boundary.
- TestSchemaMigration: safe on fresh and pre-existing databases.
"""

from __future__ import annotations

import ast
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app  # noqa: E402
from live_ranking import (  # noqa: E402
    INTERNAL_RANKING_FIELDS,
    LIVE_RANKING_MODEL_VERSION,
    LIVE_RANKING_SNAPSHOT_VERSION,
    build_feature_snapshot,
    build_live_rankings,
    public_ranking_rows,
)
from signal_outcomes import SignalOutcomeStore  # noqa: E402
from board_outcomes import BoardOutcomeStore, TABLE_NAME as BOARD_TABLE  # noqa: E402


APP_PATH = Path(app.__file__)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _tmp_db() -> Path:
    handle = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    handle.close()
    return Path(handle.name)


def _prices(symbol: str = "BTC") -> dict:
    return {
        symbol: {
            "price": 65000.0,
            "pct_1m": 0.70,
            "pct_3m": 1.80,
            "pct_1h": 0.74,
            "trend_streak": 3,
        }
    }


def _volumes(symbol: str = "BTC") -> dict:
    return {symbol: {"volume_change_1h_pct": 42.0}}


def _ranking_row(symbol: str = "BTC", **overrides) -> dict:
    """A real build_live_rankings row, so tests track the true shape."""
    rows = build_live_rankings(
        price_snapshot=_prices(symbol),
        volume_snapshot=_volumes(symbol),
        alerts=[{"symbol": f"{symbol}-USD", "type": "breakout"}],
        include_internal_features=True,
    )
    row = rows[0]
    row.update(overrides)
    return row


def _event(symbol: str = "BTC", event_id: str = "ev_001") -> dict:
    return {
        "id": event_id,
        "event_id": event_id,
        "product_id": f"{symbol}-USD",
        "primary_state": "Building",
        "the_read": {"label": "BUY_WATCH"},
        "direction": "up",
        "confidence": 75,
        "latest_transition_ts_ms": int(time.time() * 1000),
        "evidence": {"price": 65000.0},
    }


def _board_row(symbol: str = "BTC", change: float = 1.13) -> dict:
    return {
        "product_id": f"{symbol}-USD",
        "symbol": symbol,
        "change_3m": change,
        "change_1m": change,
        "price": 65000.0,
    }


def _boards(rows: list | None, board: str = "confirmation_3m_up") -> dict:
    payload = {
        "ignition_1m": None,
        "confirmation_3m_up": None,
        "confirmation_3m_down": None,
    }
    payload[board] = rows
    return payload


# ---------------------------------------------------------------------------
# Public payload must not change shape
# ---------------------------------------------------------------------------


class TestPublicPayloadCompatibility:
    def test_default_output_omits_internal_fields(self):
        rows = build_live_rankings(price_snapshot=_prices(), volume_snapshot=_volumes())
        assert rows
        for field in INTERNAL_RANKING_FIELDS:
            assert field not in rows[0]

    def test_opt_in_adds_internal_fields(self):
        rows = build_live_rankings(
            price_snapshot=_prices(),
            volume_snapshot=_volumes(),
            include_internal_features=True,
        )
        for field in INTERNAL_RANKING_FIELDS:
            assert field in rows[0]

    def test_public_rows_equal_default_output_exactly(self):
        """The core backward-compatibility guarantee.

        Collecting internal features and then stripping them must reproduce the
        default payload byte-for-byte, so turning collection on cannot alter
        what the frontend receives.
        """
        kwargs = dict(
            price_snapshot={
                "AAA": {
                    "price": 2,
                    "pct_1m": 0.8,
                    "pct_3m": 1.6,
                    "pct_1h": 3.0,
                    "trend_streak": 3,
                },
                "BBB": {"price": 3, "pct_1m": -0.4, "pct_3m": -1.1, "pct_1h": -2.0},
                "CCC": {"price": 9, "pct_1m": None, "pct_3m": None, "pct_1h": None},
            },
            volume_snapshot={"AAA": {"volume_change_1h_pct": 120}},
            context_snapshot={"AAA": {"spot_pressure": "buying", "liquidity": "thin"}},
            alerts=[{"symbol": "AAA-USD", "type": "breakout"}],
        )
        plain = build_live_rankings(**kwargs)
        enriched = build_live_rankings(**kwargs, include_internal_features=True)

        assert public_ranking_rows(enriched) == plain
        assert json.dumps(public_ranking_rows(enriched), sort_keys=True) == json.dumps(
            plain, sort_keys=True
        )

    def test_public_rows_do_not_mutate_the_originals(self):
        enriched = build_live_rankings(
            price_snapshot=_prices(),
            volume_snapshot=_volumes(),
            include_internal_features=True,
        )
        public_ranking_rows(enriched)
        for field in INTERNAL_RANKING_FIELDS:
            assert field in enriched[0], "stripping must copy, not delete in place"

    def test_scores_identical_with_and_without_collection(self):
        kwargs = dict(
            price_snapshot={
                "AAA": {
                    "price": 2,
                    "pct_1m": 0.8,
                    "pct_3m": 1.6,
                    "pct_1h": 3.0,
                    "trend_streak": 3,
                },
                "BBB": {"price": 3, "pct_1m": -0.4, "pct_3m": -1.1, "pct_1h": -2.0},
            },
            volume_snapshot={"AAA": {"volume_change_1h_pct": 120}},
        )
        plain = build_live_rankings(**kwargs)
        enriched = build_live_rankings(**kwargs, include_internal_features=True)
        for left, right in zip(plain, enriched):
            assert left["live_score"] == right["live_score"]
            assert left["live_rank"] == right["live_rank"]
            assert left["live_components"] == right["live_components"]
            assert left["data_quality"] == right["data_quality"]
            assert left["live_risks"] == right["live_risks"]


# ---------------------------------------------------------------------------
# Snapshot serialization
# ---------------------------------------------------------------------------


class TestBuildFeatureSnapshot:
    def test_schema_version_is_v2(self):
        assert LIVE_RANKING_SNAPSHOT_VERSION.endswith("-v2")
        version, _ = build_feature_snapshot(_ranking_row(), captured_ts=1000)
        assert version == LIVE_RANKING_SNAPSHOT_VERSION

    def test_refuses_rows_without_internal_features(self):
        plain = build_live_rankings(
            price_snapshot=_prices(), volume_snapshot=_volumes()
        )[0]
        assert build_feature_snapshot(plain, captured_ts=1000) == (None, None)

    def test_json_is_deterministic_and_sorted(self):
        row = _ranking_row()
        _, first = build_feature_snapshot(row, captured_ts=1000)
        _, second = build_feature_snapshot(row, captured_ts=1000)
        assert first == second
        parsed = json.loads(first)
        assert list(parsed.keys()) == sorted(parsed.keys())

    def test_captured_ts_is_recorded_verbatim(self):
        _, text = build_feature_snapshot(_ranking_row(), captured_ts=9999)
        assert json.loads(text)["captured_ts"] == 9999

    def test_null_inputs_remain_null(self):
        rows = build_live_rankings(
            price_snapshot={"ETH": {"price": 3000, "pct_1m": 0.5}},
            include_internal_features=True,
        )
        _, text = build_feature_snapshot(rows[0], captured_ts=1)
        raw = json.loads(text)["raw_inputs"]
        assert raw["pct_3m"] is None
        assert raw["pct_1h"] is None
        assert raw["volume_change_1h_pct"] is None
        assert raw["trend_streak"] is None

    def test_carries_full_feature_state(self):
        _, text = build_feature_snapshot(_ranking_row(), captured_ts=1)
        parsed = json.loads(text)
        assert parsed["model_version"] == LIVE_RANKING_MODEL_VERSION
        assert set(parsed["components"]) == {
            "momentum_1m",
            "momentum_3m",
            "trend_1h",
            "volume",
            "confirmation",
            "persistence",
        }
        assert set(parsed["scoring_detail"]) == {
            "weighted_before_penalty",
            "chase_penalty",
            "raw_score",
            "reliability",
        }
        for key in (
            "live_score",
            "live_label",
            "live_rank",
            "universe_size",
            "data_quality",
            "observed_inputs",
            "expected_inputs",
            "live_risks",
        ):
            assert key in parsed


# ---------------------------------------------------------------------------
# The early read must mutate nothing
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_alert_state():
    """Isolate the module-global alert stream and sticky cache per test."""
    saved_stream = list(app.alerts_log_main)
    saved_good = app._MW_LAST_GOOD_ALERTS
    saved_ts = app._MW_LAST_GOOD_ALERTS_TS
    app.alerts_log_main.clear()
    yield
    app.alerts_log_main.clear()
    app.alerts_log_main.extend(saved_stream)
    app._MW_LAST_GOOD_ALERTS = saved_good
    app._MW_LAST_GOOD_ALERTS_TS = saved_ts


def _live_alert(symbol="BTC-USD", type_key="breakout", ttl_s=300, evidence=None):
    now = app.datetime.now(app.timezone.utc)
    return {
        "id": f"{type_key}|{symbol}|{int(now.timestamp() * 1000)}",
        "ts": now.isoformat(),
        "symbol": symbol,
        "type": type_key,
        "type_key": type_key,
        "severity": "info",
        "title": "t",
        "message": "m",
        "expires_at": (now + app.timedelta(seconds=ttl_s)).isoformat(),
        "evidence": {} if evidence is None else evidence,
    }


class TestPeekPurity:
    def test_peek_does_not_touch_sticky_globals(self, clean_alert_state):
        app.alerts_log_main.append(_live_alert())
        app._MW_LAST_GOOD_ALERTS = ["sentinel"]
        app._MW_LAST_GOOD_ALERTS_TS = 12345.0

        result = app._mw_peek_alerts_normalized_with_sticky()

        assert result, "peek should surface the live alert"
        assert app._MW_LAST_GOOD_ALERTS == ["sentinel"]
        assert app._MW_LAST_GOOD_ALERTS_TS == 12345.0

    def test_getter_does_touch_sticky_globals(self, clean_alert_state):
        """Control for the test above: proves the assertion is meaningful."""
        app.alerts_log_main.append(_live_alert())
        app._MW_LAST_GOOD_ALERTS = ["sentinel"]
        app._MW_LAST_GOOD_ALERTS_TS = 12345.0

        app._mw_get_alerts_normalized_with_sticky()

        assert app._MW_LAST_GOOD_ALERTS != ["sentinel"]
        assert app._MW_LAST_GOOD_ALERTS_TS != 12345.0

    def test_peek_does_not_mutate_alert_evidence(self, clean_alert_state):
        """_normalize_alert() writes 'mood' into market-mood evidence in place."""
        evidence: dict = {}
        app.alerts_log_main.append(_live_alert(type_key="fomo", evidence=evidence))

        app._mw_peek_alerts_normalized_with_sticky()

        assert evidence == {}, "peek must not write into the stored alert"

    def test_getter_does_mutate_alert_evidence(self, clean_alert_state):
        """Control: the published path does mutate, which is why peek copies."""
        evidence: dict = {}
        app.alerts_log_main.append(_live_alert(type_key="fomo", evidence=evidence))

        app._mw_get_alerts_normalized_with_sticky()

        assert "mood" in evidence

    def test_peek_does_not_mutate_the_stream(self, clean_alert_state):
        original = _live_alert()
        app.alerts_log_main.append(original)

        app._mw_peek_alerts_normalized_with_sticky()

        assert len(app.alerts_log_main) == 1
        assert app.alerts_log_main[0] is original

    def test_peek_reproduces_sticky_fallback_inside_window(self, clean_alert_state):
        app._MW_LAST_GOOD_ALERTS = [{"id": "sticky-1", "symbol": "BTC-USD"}]
        app._MW_LAST_GOOD_ALERTS_TS = time.time()

        assert app._mw_peek_alerts_normalized_with_sticky() == [
            {"id": "sticky-1", "symbol": "BTC-USD"}
        ]

    def test_peek_reproduces_sticky_expiry_outside_window(self, clean_alert_state):
        window = int(app.CONFIG.get("ALERTS_STICKY_SECONDS", 60) or 60)
        app._MW_LAST_GOOD_ALERTS = [{"id": "sticky-1", "symbol": "BTC-USD"}]
        app._MW_LAST_GOOD_ALERTS_TS = time.time() - (window + 10)

        assert app._mw_peek_alerts_normalized_with_sticky() == []

    def test_peek_and_getter_agree_on_zero_alerts(self, clean_alert_state):
        """Zero alerts must not make the two paths disagree."""
        app._MW_LAST_GOOD_ALERTS = []
        app._MW_LAST_GOOD_ALERTS_TS = None

        peeked = app._mw_peek_alerts_normalized_with_sticky()
        fetched, _ = app._mw_get_alerts_normalized_with_sticky()

        assert peeked == fetched == []
        assert build_live_rankings(
            price_snapshot=_prices(), alerts=peeked
        ) == build_live_rankings(price_snapshot=_prices(), alerts=fetched)


# ---------------------------------------------------------------------------
# The published sample must stay at its original call site
# ---------------------------------------------------------------------------


def _scanner_calls() -> list[tuple[int, str]]:
    """(lineno, callee) for every call inside _compute_snapshots_from_cache."""
    tree = ast.parse(APP_PATH.read_text())
    fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_compute_snapshots_from_cache"
    )
    calls = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.append((node.lineno, func.id))
            elif isinstance(func, ast.Attribute):
                calls.append((node.lineno, func.attr))
    return sorted(calls)


class TestScannerCallOrder:
    def test_published_getter_is_called_exactly_once(self):
        names = [name for _, name in _scanner_calls()]
        assert names.count("_mw_get_alerts_normalized_with_sticky") == 1, (
            "the published alert list must be sampled once per cycle; a second "
            "call would let the alerts payload and the rankings disagree"
        )

    def test_peek_is_called_exactly_once(self):
        names = [name for _, name in _scanner_calls()]
        assert names.count("_mw_peek_alerts_normalized_with_sticky") == 1

    def test_early_snapshot_precedes_signal_observe(self):
        calls = _scanner_calls()
        peek = next(
            ln for ln, n in calls if n == "_mw_peek_alerts_normalized_with_sticky"
        )
        observe = next(ln for ln, n in calls if n == "observe")
        assert peek < observe

    def test_published_sample_comes_after_signal_observe(self):
        """The published path keeps its original, later position in the cycle."""
        calls = _scanner_calls()
        getter = next(
            ln for ln, n in calls if n == "_mw_get_alerts_normalized_with_sticky"
        )
        first_observe = min(ln for ln, n in calls if n == "observe")
        assert getter > first_observe

    def test_published_ranking_is_stripped(self):
        names = [name for _, name in _scanner_calls()]
        assert (
            "public_ranking_rows" in names
        ), "the published ranking payload must be stripped of retention fields"

    def test_ranking_is_computed_twice_deliberately(self):
        """One private early calculation, one canonical published calculation."""
        names = [name for _, name in _scanner_calls()]
        assert names.count("build_live_rankings") == 2


# ---------------------------------------------------------------------------
# Divergence between the two samples is contained
# ---------------------------------------------------------------------------


class TestSampleDivergence:
    def test_expiring_alert_moves_snapshot_only(self):
        """An alert that expires between the early and late sample.

        The early (snapshot) sample still counts it; the late (published)
        sample does not. The published ranking must match the late sample
        exactly, and the snapshot must record the early one — so the divergence
        is recorded rather than leaking into what the frontend sees.
        """
        early_alerts = [{"symbol": "BTC-USD", "type": "breakout"}]
        late_alerts: list = []  # the alert expired in between

        early = build_live_rankings(
            price_snapshot=_prices(),
            volume_snapshot=_volumes(),
            alerts=early_alerts,
            include_internal_features=True,
        )
        late = build_live_rankings(
            price_snapshot=_prices(),
            volume_snapshot=_volumes(),
            alerts=late_alerts,
            include_internal_features=True,
        )

        # The hazard is real: the two samples genuinely disagree.
        assert early[0]["live_score"] != late[0]["live_score"]
        assert early[0]["raw_inputs"]["bullish_alerts"] == 1
        assert late[0]["raw_inputs"]["bullish_alerts"] == 0

        # The published payload reflects the late sample only.
        published = public_ranking_rows(late)
        assert published == build_live_rankings(
            price_snapshot=_prices(), volume_snapshot=_volumes(), alerts=late_alerts
        )

        # The snapshot records the early sample, and says so honestly.
        _, text = build_feature_snapshot(early[0], captured_ts=1000)
        assert json.loads(text)["live_score"] == early[0]["live_score"]

    def test_board_snapshot_matches_published_ranking(self):
        """Board snapshots come from the same calculation the frontend saw."""
        alerts = [{"symbol": "BTC-USD", "type": "breakout"}]
        rankings = build_live_rankings(
            price_snapshot=_prices(),
            volume_snapshot=_volumes(),
            alerts=alerts,
            include_internal_features=True,
        )
        published = public_ranking_rows(rankings)
        _, text = build_feature_snapshot(rankings[0], captured_ts=1000)
        snapshot = json.loads(text)

        assert snapshot["live_score"] == published[0]["live_score"]
        assert snapshot["live_rank"] == published[0]["live_rank"]
        assert snapshot["components"] == published[0]["live_components"]


# ---------------------------------------------------------------------------
# Signal outcome storage
# ---------------------------------------------------------------------------


def _signal_row(store, signal_id):
    conn = sqlite3.connect(store.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM signal_outcomes WHERE signal_id = ?", (signal_id,)
        ).fetchone()
    finally:
        conn.close()


class TestSignalOutcomeSnapshot:
    def test_new_row_receives_snapshot(self):
        store = SignalOutcomeStore(db_path=_tmp_db())
        event = _event()
        store.observe(
            [event],
            {"BTC-USD": 65000.0},
            ranking_snapshot={"BTC": _ranking_row()},
            ranking_captured_ts=1700000000,
        )
        row = _signal_row(store, event["id"])
        assert row["feature_schema_version"] == LIVE_RANKING_SNAPSHOT_VERSION
        parsed = json.loads(row["feature_snapshot_json"])
        assert parsed["raw_inputs"]["pct_1m"] == pytest.approx(0.70)
        assert parsed["components"]["momentum_1m"] > 50

    def test_captured_ts_is_the_ranking_time_not_the_observer_time(self):
        """Provenance: the snapshot must not be dated by the observer's clock."""
        store = SignalOutcomeStore(db_path=_tmp_db())
        event = _event(event_id="ev_ts")
        ranking_ts, observe_ts = 1700000000, 1700009999
        store.observe(
            [event],
            {"BTC-USD": 65000.0},
            now_ts=observe_ts,
            ranking_snapshot={"BTC": _ranking_row()},
            ranking_captured_ts=ranking_ts,
        )
        parsed = json.loads(_signal_row(store, event["id"])["feature_snapshot_json"])
        assert parsed["captured_ts"] == ranking_ts
        assert parsed["captured_ts"] != observe_ts

    def test_missing_captured_ts_writes_no_snapshot(self):
        """Fail closed rather than store a misdated record."""
        store = SignalOutcomeStore(db_path=_tmp_db())
        event = _event(event_id="ev_no_ts")
        store.observe(
            [event],
            {"BTC-USD": 65000.0},
            ranking_snapshot={"BTC": _ranking_row()},
            ranking_captured_ts=None,
        )
        row = _signal_row(store, event["id"])
        assert row["feature_schema_version"] is None
        assert row["feature_snapshot_json"] is None

    def test_symbol_absent_from_ranking_writes_null(self):
        store = SignalOutcomeStore(db_path=_tmp_db())
        event = _event(event_id="ev_absent")
        store.observe(
            [event],
            {"BTC-USD": 65000.0},
            ranking_snapshot={},
            ranking_captured_ts=1700000000,
        )
        assert _signal_row(store, event["id"])["feature_snapshot_json"] is None

    def test_repeated_observation_does_not_overwrite(self):
        store = SignalOutcomeStore(db_path=_tmp_db())
        event = _event(event_id="ev_repeat")
        first = _ranking_row(live_score=70)
        second = _ranking_row(live_score=95)

        store.observe(
            [event],
            {"BTC-USD": 65000.0},
            ranking_snapshot={"BTC": first},
            ranking_captured_ts=1700000000,
        )
        store.observe(
            [event],
            {"BTC-USD": 65500.0},
            ranking_snapshot={"BTC": second},
            ranking_captured_ts=1700000060,
        )

        parsed = json.loads(_signal_row(store, event["id"])["feature_snapshot_json"])
        assert parsed["live_score"] == 70
        assert parsed["captured_ts"] == 1700000000

    def test_grading_still_completes(self):
        store = SignalOutcomeStore(db_path=_tmp_db())
        started = int(time.time()) - 7200
        event = {
            **_event(symbol="ETH", event_id="ev_grade"),
            "product_id": "ETH-USD",
            "latest_transition_ts_ms": started * 1000,
            "evidence": {"price": 3000.0},
        }
        store.observe([event], {"ETH-USD": 3000.0}, now_ts=started)
        store.observe([], {"ETH-USD": 3200.0}, now_ts=int(time.time()))
        row = _signal_row(store, event["id"])
        assert row["complete"] == 1
        assert row["outcome"] in ("followed_through", "did_not_follow_through")

    def test_legacy_call_without_snapshot_args_still_works(self):
        store = SignalOutcomeStore(db_path=_tmp_db())
        event = _event(event_id="ev_legacy")
        store.observe([event], {"BTC-USD": 65000.0})
        assert _signal_row(store, event["id"]) is not None


# ---------------------------------------------------------------------------
# Board outcome storage
# ---------------------------------------------------------------------------


def _board_rows(store, symbol):
    conn = sqlite3.connect(store.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            f"SELECT * FROM {BOARD_TABLE} WHERE symbol = ? ORDER BY entered_ts",
            (symbol,),
        ).fetchall()
    finally:
        conn.close()


class TestBoardOutcomeSnapshot:
    def test_new_entry_receives_snapshot(self):
        store = BoardOutcomeStore(db_path=_tmp_db())
        store.observe(
            _boards([_board_row("BTC")]),
            {"BTC-USD": {"price": 65000.0}},
            ranking_snapshot={"BTC": _ranking_row()},
            ranking_captured_ts=1700000000,
        )
        rows = _board_rows(store, "BTC")
        assert rows[0]["feature_schema_version"] == LIVE_RANKING_SNAPSHOT_VERSION
        assert json.loads(rows[0]["feature_snapshot_json"])["captured_ts"] == 1700000000

    def test_captured_ts_is_the_ranking_time_not_the_observer_time(self):
        store = BoardOutcomeStore(db_path=_tmp_db())
        store.observe(
            _boards([_board_row("BTC")]),
            {"BTC-USD": {"price": 65000.0}},
            now_ts=1700009999,
            ranking_snapshot={"BTC": _ranking_row()},
            ranking_captured_ts=1700000000,
        )
        parsed = json.loads(_board_rows(store, "BTC")[0]["feature_snapshot_json"])
        assert parsed["captured_ts"] == 1700000000

    def test_missing_captured_ts_writes_no_snapshot(self):
        store = BoardOutcomeStore(db_path=_tmp_db())
        store.observe(
            _boards([_board_row("BTC")]),
            {"BTC-USD": {"price": 65000.0}},
            ranking_snapshot={"BTC": _ranking_row()},
            ranking_captured_ts=None,
        )
        assert _board_rows(store, "BTC")[0]["feature_snapshot_json"] is None

    def test_symbol_absent_from_ranking_writes_null(self):
        store = BoardOutcomeStore(db_path=_tmp_db())
        store.observe(
            _boards([_board_row("ETH")]),
            {"ETH-USD": {"price": 3000.0}},
            ranking_snapshot={},
            ranking_captured_ts=1700000000,
        )
        assert _board_rows(store, "ETH")[0]["feature_snapshot_json"] is None

    def test_existing_entry_is_never_backfilled(self):
        """A coin still on the board must keep its original snapshot."""
        store = BoardOutcomeStore(db_path=_tmp_db())
        t0 = int(time.time())
        store.observe(
            _boards([_board_row("SOL")]),
            {"SOL-USD": {"price": 100.0}},
            now_ts=t0,
            ranking_snapshot={"SOL": _ranking_row("SOL", live_score=70)},
            ranking_captured_ts=t0,
        )
        store.observe(
            _boards([_board_row("SOL")]),
            {"SOL-USD": {"price": 101.0}},
            now_ts=t0 + 30,
            ranking_snapshot={"SOL": _ranking_row("SOL", live_score=95)},
            ranking_captured_ts=t0 + 30,
        )
        rows = _board_rows(store, "SOL")
        assert len(rows) == 1
        parsed = json.loads(rows[0]["feature_snapshot_json"])
        assert parsed["live_score"] == 70
        assert parsed["captured_ts"] == t0

    def test_legacy_call_without_snapshot_args_still_works(self):
        store = BoardOutcomeStore(db_path=_tmp_db())
        store.observe(_boards([_board_row("BTC")]), {"BTC-USD": {"price": 65000.0}})
        assert len(_board_rows(store, "BTC")) == 1


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

_LEGACY_SIGNAL_SCHEMA = """
CREATE TABLE signal_outcomes (
    signal_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, product_id TEXT NOT NULL,
    primary_state TEXT NOT NULL, read_label TEXT NOT NULL, direction TEXT NOT NULL,
    confidence INTEGER NOT NULL, started_ts INTEGER NOT NULL, start_price REAL NOT NULL,
    last_ts INTEGER NOT NULL, last_price REAL NOT NULL,
    return_5m REAL, return_15m REAL, return_30m REAL, return_60m REAL,
    max_favorable_pct REAL NOT NULL DEFAULT 0, max_adverse_pct REAL NOT NULL DEFAULT 0,
    target_hit_ts INTEGER, adverse_hit_ts INTEGER, outcome TEXT,
    complete INTEGER NOT NULL DEFAULT 0
)
"""


class TestSchemaMigration:
    def test_fresh_signal_db_has_columns(self):
        store = SignalOutcomeStore(db_path=_tmp_db())
        conn = sqlite3.connect(store.db_path)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(signal_outcomes)")}
        conn.close()
        assert {"feature_schema_version", "feature_snapshot_json"} <= cols

    def test_fresh_board_db_has_columns(self):
        store = BoardOutcomeStore(db_path=_tmp_db())
        conn = sqlite3.connect(store.db_path)
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({BOARD_TABLE})")}
        conn.close()
        assert {"feature_schema_version", "feature_snapshot_json"} <= cols

    def test_pre_existing_signal_rows_survive(self):
        db = _tmp_db()
        conn = sqlite3.connect(db)
        conn.execute(_LEGACY_SIGNAL_SCHEMA)
        conn.execute(
            "INSERT INTO signal_outcomes (signal_id, event_id, product_id, "
            "primary_state, read_label, direction, confidence, started_ts, "
            "start_price, last_ts, last_price) VALUES "
            "('old', 'oldev', 'BTC-USD', 'Building', 'BUY_WATCH', 'up', 75, "
            "1700000000, 40000.0, 1700000001, 40000.0)"
        )
        conn.commit()
        conn.close()

        store = SignalOutcomeStore(db_path=db)
        row = _signal_row(store, "old")
        assert row["product_id"] == "BTC-USD"
        assert row["feature_schema_version"] is None

    def test_legacy_row_still_grades_after_migration(self):
        """A null-snapshot row must remain a fully working outcome record."""
        db = _tmp_db()
        started = int(time.time()) - 7200
        conn = sqlite3.connect(db)
        conn.execute(_LEGACY_SIGNAL_SCHEMA)
        conn.execute(
            "INSERT INTO signal_outcomes (signal_id, event_id, product_id, "
            "primary_state, read_label, direction, confidence, started_ts, "
            "start_price, last_ts, last_price) VALUES "
            f"('old', 'oldev', 'ETH-USD', 'Building', 'BUY_WATCH', 'up', 75, "
            f"{started}, 3000.0, {started}, 3000.0)"
        )
        conn.commit()
        conn.close()

        store = SignalOutcomeStore(db_path=db)
        store.observe([], {"ETH-USD": 3200.0}, now_ts=int(time.time()))
        row = _signal_row(store, "old")
        assert row["complete"] == 1
        assert row["feature_snapshot_json"] is None

    def test_ensure_db_is_idempotent(self):
        db = _tmp_db()
        SignalOutcomeStore(db_path=db)
        SignalOutcomeStore(db_path=db)
        BoardOutcomeStore(db_path=db)
        BoardOutcomeStore(db_path=db)
        conn = sqlite3.connect(db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(signal_outcomes)")}
        conn.close()
        assert "feature_snapshot_json" in cols
