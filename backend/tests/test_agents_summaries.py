import time

import pytest

from agents.catalog import AGENT_CATALOG, describe
from agents.contracts import AgentObservation
from agents.runner import DEFAULT_AGENT_FACTORIES
from agents.store import AgentStore


def _obs(agent, severity, summary="x"):
    return AgentObservation(agent=agent, kind="k", severity=severity, summary=summary)


def _by_agent(summaries):
    return {row["agent"]: row for row in summaries}


def test_known_agent_with_no_runs_is_listed_as_never_run(tmp_path):
    store = AgentStore(tmp_path / "a.sqlite")
    rows = _by_agent(store.agent_summaries(["tape_scout"]))
    assert rows["tape_scout"]["state"] == "never_run"
    assert rows["tape_scout"]["latest_run"] is None
    assert rows["tape_scout"]["run_count"] == 0


def test_finished_ok_run_is_idle_with_its_findings_by_severity(tmp_path):
    store = AgentStore(tmp_path / "a.sqlite")
    run_id = store.begin_run("data_quality")
    n = store.record_observations(
        run_id,
        [_obs("data_quality", "warning"), _obs("data_quality", "warning"), _obs("data_quality", "info")],
    )
    store.finish_run(run_id, status="ok", observation_count=n)

    row = _by_agent(store.agent_summaries())["data_quality"]
    assert row["state"] == "idle"
    assert row["latest_findings_by_severity"] == {"warning": 2, "info": 1}
    assert row["last_activity_ts"] == row["latest_run"]["finished_ts"]


def test_error_run_is_failed_and_keeps_the_error(tmp_path):
    store = AgentStore(tmp_path / "a.sqlite")
    run_id = store.begin_run("portfolio_watch")
    store.finish_run(run_id, status="error", error="risk board unreachable")

    row = _by_agent(store.agent_summaries())["portfolio_watch"]
    assert row["state"] == "failed"
    assert row["latest_run"]["error"] == "risk board unreachable"


def test_unfinished_run_is_running_until_stale_then_interrupted(tmp_path):
    store = AgentStore(tmp_path / "a.sqlite")
    store.begin_run("tape_scout")
    started = _by_agent(store.agent_summaries())["tape_scout"]["latest_run"]["started_ts"]

    fresh = _by_agent(store.agent_summaries(now=started + 30))["tape_scout"]
    assert fresh["state"] == "running"

    stale = _by_agent(
        store.agent_summaries(now=started + AgentStore.STALE_RUN_SECONDS)
    )["tape_scout"]
    assert stale["state"] == "interrupted"


def test_state_follows_the_latest_run_not_an_older_one(tmp_path):
    store = AgentStore(tmp_path / "a.sqlite")
    old = store.begin_run("audit_triage")
    store.finish_run(old, status="error", error="old failure")
    # begin_run timestamps in whole seconds; make the second run strictly later.
    time.sleep(1.05)
    new = store.begin_run("audit_triage")
    store.finish_run(new, status="ok", observation_count=0)

    row = _by_agent(store.agent_summaries())["audit_triage"]
    assert row["state"] == "idle"
    assert row["run_count"] == 2
    assert row["latest_findings_by_severity"] == {}


def test_every_default_agent_has_a_catalog_entry():
    names = {factory.name for factory in DEFAULT_AGENT_FACTORIES}
    assert names <= set(AGENT_CATALOG), names - set(AGENT_CATALOG)
    for name in names:
        assert describe(name)["purpose"], name


def test_unknown_agent_gets_a_readable_label():
    assert describe("baseline_builder") == {"label": "Baseline Builder", "purpose": ""}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("MW_AGENT_OBSERVATIONS_DB", str(tmp_path / "ledger.sqlite"))
    import app as backend_app

    monkeypatch.setattr(backend_app, "_mw_ensure_background_started", lambda: None)
    return backend_app.app.test_client()


def test_status_route_lists_every_known_agent_with_label_and_state(api):
    payload = api.get("/api/agents/status").get_json()
    assert payload["status"] == "live"
    rows = _by_agent(payload["agent_summaries"])
    assert set(rows) >= {factory.name for factory in DEFAULT_AGENT_FACTORIES}
    assert rows["data_quality"]["label"] == "Data Quality"
    assert rows["data_quality"]["state"] == "never_run"
    assert isinstance(payload["generated_ts"], int)
