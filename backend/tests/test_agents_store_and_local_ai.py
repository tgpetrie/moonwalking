import pytest

from agents.contracts import AgentObservation
from agents.runner import run_once
from agents.store import AgentStore
from local_ai.client import LocalLLMClient, LocalLLMConfig, summarize_observations


def test_agent_store_records_latest_observations(tmp_path):
    store = AgentStore(tmp_path / "agents.sqlite")
    run_id = store.begin_run("data_quality", model_version="test")
    count = store.record_observations(
        run_id,
        [
            AgentObservation(
                agent="data_quality",
                kind="missing_or_invalid_price",
                severity="warning",
                symbol="BTC",
                summary="BTC is missing price.",
                evidence={"field": "price_now"},
            )
        ],
    )
    store.finish_run(run_id, status="ok", observation_count=count)

    latest = store.latest(symbol="BTC")
    assert latest[0]["symbol"] == "BTC"
    assert latest[0]["evidence"] == {"field": "price_now"}
    assert store.status()["total_observations"] == 1


def test_runner_records_agent_output(tmp_path):
    store = AgentStore(tmp_path / "agents.sqlite")

    result = run_once(
        {"board_snapshot": {"timestamp": 1_000, "gainers_1m": []}},
        store=store,
    )

    assert result["status"] == "ok"
    assert result["observation_count"] >= 1
    assert store.status()["last_run"]["status"] == "ok"


def test_local_llm_summary_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("BHABIT_LLM_ENABLED", raising=False)

    result = summarize_observations([])

    assert result["status"] == "disabled"


def test_local_llm_rejects_remote_base_url():
    config = LocalLLMConfig(
        enabled=True,
        model="qwen",
        base_url="https://example.com/v1",
    )

    with pytest.raises(ValueError, match="localhost"):
        LocalLLMClient(config)
