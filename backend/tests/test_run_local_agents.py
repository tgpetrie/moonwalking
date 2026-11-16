import json
import sys
import time

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
