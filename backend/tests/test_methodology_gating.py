"""Legacy, uncontrolled outcomes must never reach a public surface.

The 43,100 rows already on disk were graded with no control group, and no
later work can repair them: the matched-peer behaviour they would need was
never recorded, and the price tape that held it is pruned at 24 hours. They are
kept for research and excluded from every published figure.

These tests exist because the failure mode is silent. A regression here does
not raise — it prints a plausible percentage.
"""

from __future__ import annotations

import json
import pathlib

import pytest

try:
    from signal_outcomes import LEGACY_METHODOLOGY_VERSION, SignalOutcomeStore
except Exception:  # pragma: no cover
    from backend.signal_outcomes import (  # type: ignore
        LEGACY_METHODOLOGY_VERSION,
        SignalOutcomeStore,
    )


def _legacy_store(tmp_path, rows=40):
    """A store holding only uncontrolled history, configured as Phase 0 is."""
    store = SignalOutcomeStore(
        tmp_path / "legacy.sqlite",
        collection_methodology=LEGACY_METHODOLOGY_VERSION,
        publishable_methodology=None,
    )
    conn = store._connect()
    try:
        for i in range(rows):
            conn.execute(
                """
                INSERT INTO signal_outcomes (
                    signal_id, event_id, product_id, primary_state, read_label,
                    direction, confidence, started_ts, start_price, last_ts,
                    last_price, max_favorable_pct, max_adverse_pct, outcome,
                    complete, methodology_version
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)
                """,
                (
                    f"legacy-{i}",
                    f"evt-{i}",
                    "BTC-USD",
                    "Reversal Risk",
                    "REVERSAL RISK RISING",
                    "up",
                    80,
                    1_700_000_000 + i * 7200,
                    100.0,
                    1_700_000_000 + i * 7200 + 3600,
                    102.0,
                    2.5,
                    -0.4,
                    # 37 of 40 wins = 0.925, a rate that collides with no
                    # config value in the payload, so a scan for it cannot be
                    # confused by barrier percentages or gate denominators.
                    "followed_through" if i < 37 else "did_not_follow_through",
                    LEGACY_METHODOLOGY_VERSION,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return store


def _numbers(payload):
    """Every finite number anywhere in a payload."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)
        elif isinstance(node, bool):
            return
        elif isinstance(node, (int, float)):
            found.append(node)

    walk(payload)
    return found


def test_legacy_rows_are_preserved_not_deleted(tmp_path):
    store = _legacy_store(tmp_path)
    conn = store._connect()
    try:
        total = conn.execute("SELECT COUNT(*) FROM signal_outcomes").fetchone()[0]
    finally:
        conn.close()
    assert total == 40, "legacy history is research data and must be kept"


def test_scorecard_publishes_no_rate_from_legacy_rows(tmp_path):
    store = _legacy_store(tmp_path)
    result = store.scorecard()

    assert result["measurement_status"] == "learning"
    assert result["overall_win_rate"] is None
    assert result["total_graded"] == 0
    assert result["research_only_rows_excluded"] == 40

    # The category is still listed, so the client can show progress...
    assert len(result["signal_types"]) == 1
    card = result["signal_types"][0]
    # ...but nothing on it reads as performance.
    assert card["win_rate"] is None
    assert card["recent_win_rate"] is None
    assert card["median_favorable_pct"] is None
    assert card["median_adverse_pct"] is None
    assert card["sample_size"] == 0
    assert all(v is None for v in card["median_return"].values())


def test_coin_scorecard_publishes_no_rate_from_legacy_rows(tmp_path):
    store = _legacy_store(tmp_path)
    result = store.coin_scorecard("BTC-USD")

    assert result["measurement_status"] == "learning"
    assert result["total_outcomes"] == 0
    assert result["research_only_rows_excluded"] == 40
    assert all(c["win_rate"] is None for c in result["signal_types"])


def test_history_for_returns_no_rate_from_legacy_rows(tmp_path):
    """The single chokepoint feeding popup, portfolio, alerts and enrichment."""
    store = _legacy_store(tmp_path)
    history = store.history_for(
        {
            "primary_state": "Reversal Risk",
            "direction": "up",
            "the_read": {"label": "REVERSAL RISK RISING"},
        }
    )

    assert history["measurement_status"] == "learning"
    assert history["follow_through_rate"] is None
    assert history["median_favorable_pct"] is None
    # Not 40: a large sample count beside a missing rate still reads as
    # accumulated evidence, and none of those rows can back a rate.
    assert history["sample_size"] == 0


@pytest.mark.parametrize(
    "surface",
    ["scorecard", "coin_scorecard", "history_for", "status"],
)
def test_no_public_surface_emits_the_legacy_win_rate(tmp_path, surface):
    """No published number may equal the legacy rate, in any encoding.

    Scanning every number in the payload rather than a list of named keys means
    a newly added field cannot quietly reintroduce the leak: a future
    `overall_rate_pct` would be caught without anyone remembering to extend
    this test.
    """
    store = _legacy_store(tmp_path)
    payload = {
        "scorecard": lambda: store.scorecard(),
        "coin_scorecard": lambda: store.coin_scorecard("BTC-USD"),
        "history_for": lambda: store.history_for(
            {
                "primary_state": "Reversal Risk",
                "direction": "up",
                "the_read": {"label": "REVERSAL RISK RISING"},
            }
        ),
        "status": lambda: store.status(),
    }[surface]()

    # 37/40 seeded wins, in the encodings a rate could plausibly take.
    leaked = [n for n in _numbers(payload) if n in (0.925, 92.5, 0.93, 92.0)]
    assert (
        leaked == []
    ), f"{surface} emitted a value matching the uncontrolled rate: {payload}"


def test_measured_mode_still_works_when_a_controlled_version_exists(tmp_path):
    """The gate withholds unbacked rates; it does not disable measurement.

    Requires control tables *and* enough market periods over enough days —
    the same bar Phase 1 will have to clear.
    """
    store = _controlled_store(tmp_path, "measured.sqlite")
    conn = store._connect()
    try:
        for i in range(200):
            conn.execute(
                """
                INSERT INTO signal_outcomes (
                    signal_id, event_id, product_id, primary_state, read_label,
                    direction, confidence, started_ts, start_price, last_ts,
                    last_price, max_favorable_pct, max_adverse_pct, outcome,
                    complete, methodology_version
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)
                """,
                (
                    f"m-{i}",
                    f"evt-{i}",
                    "BTC-USD",
                    "Breakout",
                    "CONTINUATION FAVORED",
                    "up",
                    80,
                    1_700_000_000 + i * 7200,
                    100.0,
                    1_700_000_000 + i * 7200 + 3600,
                    102.0,
                    2.5,
                    -0.4,
                    "followed_through" if i < 120 else "did_not_follow_through",
                    "v_test_measured",
                ),
            )
        conn.commit()
    finally:
        conn.close()

    result = store.scorecard(min_samples=5)
    assert result["measurement_status"] == "measured"
    assert result["total_graded"] == 200
    assert result["overall_win_rate"] == 0.6
    assert result["signal_types"][0]["win_rate"] == 0.6


def test_legacy_and_controlled_rows_do_not_mix(tmp_path):
    """A controlled rate must not absorb uncontrolled rows sitting beside it."""
    store = _controlled_store(tmp_path, "mix.sqlite")
    _seed(store, "v_test_measured", "did_not_follow_through", 200)
    _seed(store, LEGACY_METHODOLOGY_VERSION, "followed_through", 900, offset=5000)

    result = store.scorecard(min_samples=5)
    # 200 controlled losses beside 900 uncontrolled wins: the honest answer is
    # 0.0, and any bleed-through would pull it upward.
    assert result["total_graded"] == 200
    assert result["overall_win_rate"] == 0.0
    assert result["research_only_rows_excluded"] == 900
    assert all(c["win_rate"] in (None, 0.0) for c in result["signal_types"])


def test_dry_run_module_never_reads_outcomes():
    """Rung selection must be blind to results, enforced at the source.

    A dry-run that could see outcomes could prefer whichever caliper flattered
    them, which is precisely the bias the control exists to remove.
    """
    source = (
        pathlib.Path(__file__).resolve().parent.parent / "control_dry_run.py"
    ).read_text()
    forbidden = [
        "followed_through",
        "did_not_follow_through",
        "max_favorable_pct",
        "max_adverse_pct",
        "win_rate",
        "signal_outcomes",
        "return_60m",
    ]
    hits = [token for token in forbidden if token in source]
    assert hits == [], f"dry-run must not reference outcome data: {hits}"


# ---------------------------------------------------------------------------
# Regressions from review round 5. Each of these shipped as a real defect.
# ---------------------------------------------------------------------------


def _controlled_store(tmp_path, name="fixed.sqlite"):
    """A store with the control table present, simulating Phase 1 structure."""
    store = SignalOutcomeStore(
        tmp_path / name,
        collection_methodology="v_test_measured",
        publishable_methodology="v_test_measured",
    )
    conn = store._connect()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS signal_controls (signal_id TEXT)")
        conn.commit()
    finally:
        conn.close()
    return store


def _seed(store, version, outcome, count, start=1_700_000_000, step=7200, offset=0):
    conn = store._connect()
    try:
        for i in range(count):
            n = offset + i
            conn.execute(
                """
                INSERT INTO signal_outcomes (
                    signal_id, event_id, product_id, primary_state, read_label,
                    direction, confidence, started_ts, start_price, last_ts,
                    last_price, max_favorable_pct, max_adverse_pct, outcome,
                    complete, methodology_version
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)
                """,
                (
                    f"seed-{version}-{n}",
                    f"evt-{n}",
                    "BTC-USD",
                    "Breakout",
                    "CONTINUATION FAVORED",
                    "up",
                    80,
                    start + n * step,
                    100.0,
                    start + n * step + 3600,
                    102.0,
                    2.5,
                    -0.4,
                    outcome,
                    version,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def test_category_cards_never_aggregate_legacy_rows(tmp_path):
    """The reproduced contradiction: overall 0.0 beside a 0.9 category card.

    `_cards_from_rows` received every methodology, so a category card averaged
    10 controlled losses together with 90 legacy wins while the overall rate
    correctly saw only the 10.
    """
    store = _controlled_store(tmp_path, "mixed.sqlite")
    _seed(store, "v_test_measured", "did_not_follow_through", 10)
    _seed(store, LEGACY_METHODOLOGY_VERSION, "followed_through", 90, offset=1000)

    result = store.scorecard(min_samples=5)

    assert result["overall_win_rate"] in (None, 0.0)
    for card in result["signal_types"]:
        assert card["win_rate"] != 0.9
        assert card["sample_size"] != 100
        # Whatever the card reports, it may never disagree with the overall
        # figure by drawing on rows the overall figure excluded.
        if card["win_rate"] is not None:
            assert card["win_rate"] == 0.0


def test_legacy_version_is_rejected_as_publishable(tmp_path):
    """`MW_PUBLISHABLE_METHODOLOGY=v1_uncontrolled` must be impossible."""
    with pytest.raises(ValueError):
        SignalOutcomeStore(
            tmp_path / "reject.sqlite",
            publishable_methodology=LEGACY_METHODOLOGY_VERSION,
        )


def test_publication_requires_control_tables_to_exist(tmp_path):
    """A configuration string alone must not open a publishing path."""
    store = SignalOutcomeStore(
        tmp_path / "nocontrols.sqlite",
        collection_methodology="v_test_measured",
        publishable_methodology="v_test_measured",
    )
    _seed(store, "v_test_measured", "followed_through", 40)

    assert store.publication_enabled() is False
    result = store.scorecard(min_samples=5)
    assert result["measurement_status"] == "learning"
    assert result["overall_win_rate"] is None
    assert all(c["win_rate"] is None for c in result["signal_types"])


def test_one_row_cannot_publish_through_history_for(tmp_path):
    store = _controlled_store(tmp_path, "onerow.sqlite")
    _seed(store, "v_test_measured", "followed_through", 1)

    history = store.history_for(
        {
            "primary_state": "Breakout",
            "direction": "up",
            "the_read": {"label": "CONTINUATION FAVORED"},
        }
    )
    assert history["measurement_status"] == "learning"
    assert history["follow_through_rate"] is None


def test_evidence_gate_requires_market_periods_and_span(tmp_path):
    """Rows crammed into a few hours must not clear the gate."""
    store = _controlled_store(tmp_path, "gate.sqlite")
    # 500 rows, but only 5 distinct 2h periods and under a day of span.
    _seed(store, "v_test_measured", "followed_through", 500, step=60)

    result = store.scorecard(min_samples=5)
    assert result["measurement_status"] == "learning"
    assert result["overall_win_rate"] is None
    assert all(c["win_rate"] is None for c in result["signal_types"])
