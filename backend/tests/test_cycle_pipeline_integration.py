"""Exercise the scan-to-ledger path with closed Coinbase-shaped daily candles."""

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as backend_app
import chart_reader
import watchlist
from agents.cycle_context import build_cycle_context
from agents.runner import run_once
from agents.store import AgentStore
from smart_alerts import SmartAlertEngine


def test_real_macro_response_drives_proposals_and_smart_alerts(
    monkeypatch, tmp_path, daily_series, cycle_fixture, macro_scan_state
):
    for key in ("AGENT_OBSERVATIONS", "SMART_ALERTS", "CYCLE_HISTORY"):
        monkeypatch.setenv(f"MW_{key}_DB", str(tmp_path / f"{key}.sqlite"))
    monkeypatch.delenv("COINBASE_PORTFOLIO_OWNER_EMAIL", raising=False)
    monkeypatch.delenv("MW_NTFY_URL", raising=False)
    monkeypatch.setenv("MW_ALERT_NOTIFY_ENABLED", "0")
    monkeypatch.setenv("MW_MACRO_SCAN_SYNC", "1")
    # Pin the upstream cache's time to the closed daily fixture window.
    monkeypatch.setattr(chart_reader, "time", SimpleNamespace(time=lambda: 1794787200))
    monkeypatch.setattr(backend_app.time, "time", lambda: 1794787200)
    monkeypatch.setattr(watchlist, "_WATCHLIST_DB_PATH", tmp_path / "watchlist.sqlite")
    watchlist._ensure_watchlist_schema()
    monkeypatch.setattr(backend_app, "_mw_ensure_background_started", lambda: None)
    monkeypatch.setitem(backend_app.app.config, "TESTING", True)

    down = daily_series(60, [(200, 80), (1261, 8)])
    histories = dict.fromkeys(("BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "XRP-USD"), down)
    histories.update(
        {
            "RENDER-USD": cycle_fixture("render_cycle_fixture"),
            "LTC-USD": daily_series(11, [(1461, 10)]),
            "AVAX-USD": daily_series(
                30, [(120, 40), (1200, 4.2), (25, 5.0), (40, 3.5), (76, 5.4)]
            ),
        }
    )
    monkeypatch.setattr(backend_app, "_macro_scan_universe", lambda *a, **kw: sorted(histories))
    class Response:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            pass

        def json(self):
            return self.rows

    def candles(url, *, params, timeout):
        assert url.startswith("https://api.exchange.coinbase.com/products/")
        assert params["granularity"] == 86400 and timeout > 0
        product = url.split("/")[-2]
        start = datetime.fromisoformat(params["start"]).timestamp()
        end = datetime.fromisoformat(params["end"]).timestamp()
        return Response([r for r in reversed(histories[product]) if start <= r[0] <= end])

    monkeypatch.setattr(chart_reader.requests, "get", candles)
    client = backend_app.app.test_client()
    owner = "cycle-owner@example.test"
    assert client.post(
        "/api/auth/signup",
        json={"name": "Cycle Owner", "email": owner, "password": "test-only-password"},
    ).status_code == 201
    monkeypatch.setenv("COINBASE_PORTFOLIO_OWNER_EMAIL", owner)

    # The pre-audit fallback let a client re-sign a valid owner claim.
    with client.session_transaction() as session:
        claims = dict(session)
    unsigned_app = Flask("legacy-session-forgery")
    unsigned_app.secret_key = "dev-only-insecure-secret"  # pragma: allowlist secret
    serializer = unsigned_app.session_interface.get_signing_serializer(unsigned_app)
    anonymous = backend_app.app.test_client()
    anonymous.set_cookie(backend_app.app.config["SESSION_COOKIE_NAME"], serializer.dumps(claims))
    assert anonymous.get("/api/agents/proposals").status_code == 401

    created = client.post(
        "/api/smart-alerts/rules",
        json={
            "name": "Closed monthly RSI",
            "scope": "watchlist",
            "urgency": "watch",
            "conditions": [
                {"predicate": "rsi_regime", "value": {"timeframe": "1m", "regime": "oversold_compression"}},
                {"predicate": "daily_macd_kiss", "value": True},
            ],
        },
    )
    assert created.status_code in (200, 201)
    scan_response = client.get("/api/macro-cycle-scan?symbols=RENDER,AVAX,LTC")
    assert scan_response.status_code == 200
    scan = scan_response.json
    assert scan["status"] == "ready"
    assert scan["industry"]["stage_number"] == 1
    assert scan["market_snapshot"]["as_of_ts"] == 1794787200
    ltc = next(row for row in scan["coins"] if row["symbol"] == "LTC")
    assert ltc["rollover_target_box"] is None  # the SMA is the only trim trigger
    assert ltc["multi_year_context"]["weekly_sma_ladder"]["sma_50w"] > ltc["price"]

    context = build_cycle_context(
        scan,
        positions=[{"symbol": "LTC", "quantity": 2}],
        watchlist=["RENDER", "AVAX"],
    )
    context["now_ts"] = scan["computed_at"]
    result = run_once(context, store=AgentStore(), smart_alert_engine=SmartAlertEngine())
    assert next(r for r in result["runs"] if r["agent"] == "cycle_strategist")["status"] == "ok"
    assert result["smart_alerts"]["status"] == "ok"
    proposals = client.get("/api/agents/proposals").json["proposals"]
    by_action = {(p["action"], p["symbol"]): p for p in proposals}
    trim = by_action["TRIM_TO_USDC", "LTC"]
    assert trim["evidence"]["overhead_sma"]["key"] == "sma_50w"
    entry = by_action["BREAKOUT_ENTRY", "AVAX"]
    assert trim["status"] == entry["status"] == "pending_approval"

    history = client.get("/api/smart-alerts/history").json["history"]
    assert [(row["rule_name"], row["symbol"]) for row in history] == [
        ("Closed monthly RSI", "RENDER")
    ]
    for proposal in (entry, trim):
        assert proposal["market_snapshot"]["snapshot_id"] == scan["market_snapshot"]["snapshot_id"]
        path = f"/api/agents/proposals/{proposal['proposal_id']}/approve"
        approved = client.post(path, json={})
        assert approved.status_code == 200
        record = approved.json["proposal"]
        assert record["status"] == "approved" and record["execution"] is None
        assert client.post(path, json={}).json["proposal"] == record
    assert history[0]["evidence"]["market_snapshot"]["snapshot_id"] == scan["market_snapshot"]["snapshot_id"]
