"""Tests for the point-in-time log and the Coinbase watcher. No network."""

import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pit_log  # noqa: E402
import pit_watch  # noqa: E402


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.delenv("MW_PIT_LOG_DISABLED", raising=False)
    path = tmp_path / "pit.sqlite"
    monkeypatch.setenv("MW_PIT_LOG_DB", str(path))
    pit_log._LAST_WRITE.clear()
    return path


def product(pid, status="online", **kw):
    base, quote = pid.split("-")
    return {"id": pid, "base_currency": base, "quote_currency": quote, "status": status,
            "trading_disabled": False, "cancel_only": False, "limit_only": False, "post_only": False,
            "auction_mode": False, "status_message": "", **kw}


def events(path):
    conn = pit_log.connect(path)
    rows = [dict(r) for r in conn.execute("SELECT * FROM pit_context_log ORDER BY record_id")]
    conn.close()
    return rows


def test_first_pass_is_baseline_not_listings(db):
    conn = pit_log.connect(db)
    out = pit_watch.poll_products(conn, fetch=lambda url: [product("RENDER-USD"), product("RNDR-USD", "delisted")])
    assert out == {"baseline": 2, "listed": 0, "changed": 0, "removed": 0}
    assert {e["event_type"] for e in events(db)} == {"BASELINE"}
    # a second identical pass records nothing
    assert pit_watch.poll_products(conn, fetch=lambda url: [product("RENDER-USD"), product("RNDR-USD", "delisted")])["baseline"] == 0
    assert len(events(db)) == 2


def test_listing_status_change_and_removal_are_logged_with_revision_links(db):
    conn = pit_log.connect(db)
    pit_watch.poll_products(conn, fetch=lambda url: [product("AAA-USD"), product("BBB-USD")])
    out = pit_watch.poll_products(conn, fetch=lambda url: [product("AAA-USD", "online", cancel_only=True), product("CCC-USD")])
    assert out == {"baseline": 0, "listed": 1, "changed": 1, "removed": 1}
    ev = {e["event_type"]: e for e in events(db) if e["event_type"] != "BASELINE"}
    assert set(ev) == {"PRODUCT_LISTED", "PRODUCT_STATUS_CHANGE", "PRODUCT_REMOVED"}
    change = ev["PRODUCT_STATUS_CHANGE"]
    payload = json.loads(change["payload_json"])
    assert payload["before"]["cancel_only"] is False and payload["after"]["cancel_only"] is True
    assert change["revision_of"] is not None
    conn2 = pit_log.connect(db)
    removed = conn2.execute("SELECT removed_seen_utc FROM symbol_registry WHERE product_id='BBB-USD'").fetchone()[0]
    assert removed is not None
    # removal is logged once, not on every later pass
    pit_watch.poll_products(conn, fetch=lambda url: [product("AAA-USD", "online", cancel_only=True), product("CCC-USD")])
    assert sum(e["event_type"] == "PRODUCT_REMOVED" for e in events(db)) == 1


def test_fetch_failure_marks_health_and_logs_nothing(db):
    conn = pit_log.connect(db)

    def boom(url):
        raise pit_watch.FetchError("HTTP 451", 451)

    with pytest.raises(pit_watch.FetchError):
        pit_watch.poll_products(conn, fetch=boom)
    h = conn.execute("SELECT data_status, http_status FROM source_health WHERE source_id='coinbase_products'").fetchone()
    assert (h[0], h[1]) == ("blocked", 451)
    assert events(db) == []


def test_incidents_new_then_update_keeps_both_rows(db):
    conn = pit_log.connect(db)
    inc = {"id": "x1", "name": "Delayed withdrawals", "status": "investigating", "impact": "minor",
           "created_at": "2026-10-10T10:00:00Z", "updated_at": "2026-10-10T10:00:00Z", "incident_updates": [{}]}
    assert pit_watch.poll_incidents(conn, fetch=lambda url: {"incidents": [inc]}) == {"new": 1, "updated": 0}
    later = {**inc, "status": "resolved", "updated_at": "2026-10-10T12:00:00Z", "incident_updates": [{}, {}]}
    assert pit_watch.poll_incidents(conn, fetch=lambda url: {"incidents": [later]}) == {"new": 0, "updated": 1}
    rows = events(db)
    assert [r["event_type"] for r in rows] == ["STATUS_INCIDENT", "STATUS_INCIDENT_UPDATE"]
    assert rows[0]["source_published_utc"] == "2026-10-10T10:00:00.000000Z"
    assert rows[1]["revision_of"] == rows[0]["record_id"]


def test_positioning_snapshot_maps_only_known_products_and_throttles(db):
    conn = pit_log.connect(db)
    pit_watch.poll_products(conn, fetch=lambda url: [product("RENDER-USD")])
    conn.close()
    item = {"exchange": "hyperliquid", "symbol": "RENDER", "base_asset": "RENDER", "funding_rate": 0.0000427,
            "funding_interval_hours": 1.0, "open_interest": 1000.0, "open_interest_usd": None}
    other = {"exchange": "hyperliquid", "symbol": "HYPE", "base_asset": "HYPE", "funding_rate": None, "open_interest": None}
    assert pit_log.safe_record_positioning([item, other], scope="coin") == 2
    assert pit_log.safe_record_positioning([item], scope="coin") == 0  # throttled
    snaps = [e for e in events(db) if e["event_type"] == "POSITIONING_SNAPSHOT"]
    by_sym = {e["venue_symbol"]: e for e in snaps}
    assert by_sym["RENDER"]["product_id"] == "RENDER-USD"
    assert by_sym["HYPE"]["product_id"] is None            # no Coinbase product: not guessed
    assert by_sym["HYPE"]["metric_primary"] is None         # missing stays NULL
    assert by_sym["RENDER"]["metric_secondary"] is None     # USD OI unknown: not replaced by base OI


def test_errors_mark_venue_blocked(db):
    pit_log.safe_record_positioning([], [{"exchange": "binance", "status": "blocked", "status_code": 451, "message": "451"}], scope="market")
    conn = pit_log.connect(db)
    assert conn.execute("SELECT data_status FROM source_health WHERE source_id='binance_perp'").fetchone()[0] == "blocked"


def test_disabled_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("MW_PIT_LOG_DISABLED", "1")
    monkeypatch.setenv("MW_PIT_LOG_DB", str(tmp_path / "x.sqlite"))
    assert pit_log.safe_record_positioning([{"exchange": "okx", "symbol": "BTC-USDT-SWAP"}], scope="market") == 0
    assert not (tmp_path / "x.sqlite").exists()


def test_writer_never_raises_on_a_bad_path(monkeypatch, tmp_path):
    monkeypatch.delenv("MW_PIT_LOG_DISABLED", raising=False)
    bad = tmp_path / "file"
    bad.write_text("not a directory")
    monkeypatch.setenv("MW_PIT_LOG_DB", str(bad / "pit.sqlite"))
    assert pit_log.safe_record_positioning([{"exchange": "okx", "symbol": "S"}], scope="market") == 0


def test_symbol_positioning_hook_writes_one_snapshot(db, monkeypatch):
    import derivatives_positioning as dp
    conn = pit_log.connect(db)
    pit_watch.poll_products(conn, fetch=lambda url: [product("RENDER-USD")])
    conn.close()

    async def fake_ctxs():
        return {"RENDER": {"funding": "0.00001", "openInterest": "100", "markPx": "2.0", "oraclePx": "2.01"}}

    monkeypatch.setattr(dp, "_fetch_hyperliquid_ctxs", fake_ctxs)
    out = asyncio.run(dp.get_symbol_positioning("RENDER"))
    assert out["available"] is True
    snaps = [e for e in events(db) if e["event_type"] == "POSITIONING_SNAPSHOT"]
    assert len(snaps) == 1 and snaps[0]["product_id"] == "RENDER-USD" and snaps[0]["metric_secondary"] == 200.0


def test_to_utc_normalises_offsets_and_keeps_unknowns():
    assert pit_log.to_utc("2026-10-12T15:24:34.523-07:00") == "2026-10-12T22:24:34.523000Z"
    assert pit_log.to_utc(None) is None
    assert pit_log.to_utc("not a date") == "not a date"
