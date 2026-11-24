import json
import sys
import time

import pytest

from scripts import run_local_agents


def test_local_cli_uses_db_overrides_and_requests_held_symbols_first(tmp_path, monkeypatch):
    agent_db = tmp_path / "shared-agents.sqlite"
    alerts_db = tmp_path / "shared-alerts.sqlite"
    (tmp_path / ".env").write_text(
        f'MW_AGENT_OBSERVATIONS_DB="{agent_db.as_posix()}"\n'
        f'MW_SMART_ALERTS_DB="{alerts_db.as_posix()}"\n'
        "MW_NTFY_URL=https://example.test/not-enabled\n",
        encoding="utf-8",
    )
    for name in ("MW_AGENT_OBSERVATIONS_DB", "MW_SMART_ALERTS_DB", "MW_NTFY_URL"):
        monkeypatch.setenv(name, "test-placeholder")
        monkeypatch.delenv(name)
    monkeypatch.setattr(run_local_agents, "BACKEND", tmp_path)
    positions = tmp_path / "positions.json"
    positions.write_text(json.dumps([{"symbol": "sol", "quantity": 3}]), encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv",
        ["run_local_agents", "--api-base", "http://unused.invalid",
         "--watchlist", "avax-usd,SOL,bad symbol", "--positions-file", str(positions),
         "--no-smart-alerts"],
    )
    requests = []
    now = time.time()
    scan = {
        "status": "ready", "computed_at": now, "ttl_seconds": 1800,
        "coins": [{"symbol": "SOL", "available": True, "price": 100}],
    }

    def fetch(url, *, timeout=12.0, params=None):
        requests.append((url, params))
        return scan if url.endswith("/api/macro-cycle-scan") else {}

    runs = []

    def run(context, *, store, smart_alert_engine):
        runs.append((context, store.db_path, smart_alert_engine))
        return {"status": "ok", "runs": []}

    monkeypatch.setattr(run_local_agents, "fetch_json", fetch)
    monkeypatch.setattr(run_local_agents, "repo_status", lambda: {})
    monkeypatch.setattr(run_local_agents, "run_once", run)
    assert run_local_agents.main() == 0
    assert requests[-1] == (
        "http://unused.invalid/api/macro-cycle-scan", {"symbols": "SOL,AVAX"}
    )
    context, db, engine = runs[-1]
    assert context["cycle_scan"] is not None
    assert context["positions"] == [{"symbol": "SOL", "product_id": "SOL-USD", "quantity": 3}]
    assert context["watchlist"] == ["AVAX", "SOL"]
    assert db == agent_db and engine is None
    assert run_local_agents.os.environ["MW_SMART_ALERTS_DB"] == alerts_db.as_posix()
    assert "MW_NTFY_URL" not in run_local_agents.os.environ

    scan["computed_at"] = now - 1801
    assert run_local_agents.main() == 0
    assert runs[-1][0]["cycle_scan"] is None


def _run_cli(tmp_path, monkeypatch, *flags):
    """Run main() offline; return the context handed to run_once and the scan request."""
    monkeypatch.setattr(run_local_agents, "BACKEND", tmp_path)
    monkeypatch.setattr(
        sys, "argv",
        ["run_local_agents", "--api-base", "http://unused.invalid",
         "--db-path", str(tmp_path / "agents.sqlite"), "--no-smart-alerts", *flags],
    )
    requests, runs = [], []
    scan = {
        "status": "ready", "computed_at": time.time(), "ttl_seconds": 1800,
        "coins": [{"symbol": "SOL", "available": True, "price": 100}],
    }

    def fetch(url, *, timeout=12.0, params=None):
        requests.append((url, params))
        return scan if url.endswith("/api/macro-cycle-scan") else {}

    def run(context, *, store, smart_alert_engine):
        runs.append(context)
        return {"status": "ok", "runs": []}

    monkeypatch.setattr(run_local_agents, "fetch_json", fetch)
    monkeypatch.setattr(run_local_agents, "repo_status", lambda: {})
    monkeypatch.setattr(run_local_agents, "run_once", run)
    assert run_local_agents.main() == 0
    return runs[-1], requests[-1]


def test_local_cli_wires_the_live_quote_feed_unless_told_not_to(tmp_path, monkeypatch):
    context, _ = _run_cli(tmp_path, monkeypatch, "--watchlist", "SOL")
    assert context["quote_fetcher"] is run_local_agents.fetch_live_quotes
    assert "quotes" not in context  # fetched by the strategist, only for Mode B exits
    assert not {"portfolio_equity_usd", "base_risk_pct", "max_open_risk_pct"} & set(context)

    context, _ = _run_cli(tmp_path, monkeypatch, "--watchlist", "SOL", "--no-live-quotes")
    assert "quote_fetcher" not in context


def test_local_cli_passes_risk_settings_and_rejects_bad_ones(tmp_path, monkeypatch):
    context, _ = _run_cli(
        tmp_path, monkeypatch, "--equity-usd", "25000", "--base-risk-pct", "0.5",
        "--max-open-risk-pct", "4",
    )
    assert context["portfolio_equity_usd"] == 25_000.0
    assert context["base_risk_pct"] == 0.5 and context["max_open_risk_pct"] == 4.0

    for flags in (("--equity-usd", "0"), ("--equity-usd", "nan"), ("--base-risk-pct", "0"),
                  ("--max-open-risk-pct", "101")):
        with pytest.raises(SystemExit):
            _run_cli(tmp_path, monkeypatch, *flags)


def test_local_cli_scans_coins_with_an_open_reload_ladder(tmp_path, monkeypatch):
    from agents.cycle_strategist import CycleStrategistAgent
    from agents.store import AgentStore

    store = AgentStore(tmp_path / "agents.sqlite")
    agent = CycleStrategistAgent(store)
    agent.run({
        "cycle_scan": {
            "industry": {"available": True, "liquidity_rotation_stage": "stage_1_macro_compression"},
            "coins": [{
                "symbol": "RENDER", "available": True, "price": 9.0,
                "rollover_target_box": {"low": 8.0, "high": 10.0},
                "support_levels": {"0.618": 6.0, "0.702": 5.0, "0.786": 4.0}, "cycle_low": 2.0,
            }],
        },
        "positions": [{"symbol": "RENDER", "quantity": 100}],
    })
    store.decide_proposal(agent.last_proposals[0]["proposal_id"], "approve")

    # RENDER is neither held nor watched now, but its ladder keeps it in the scan.
    _, request = _run_cli(tmp_path, monkeypatch, "--watchlist", "AVAX")
    assert request == ("http://unused.invalid/api/macro-cycle-scan", {"symbols": "RENDER,AVAX"})
