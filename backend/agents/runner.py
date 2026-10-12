from __future__ import annotations

from typing import Iterable

from .audit_triage import AuditTriageAgent
from .data_quality import DataQualityAgent
from .development_efficiency import DevelopmentEfficiencyAgent
from .portfolio_watch import PortfolioWatchAgent
from .store import AgentStore
from .tape_scout import TapeScoutAgent


DEFAULT_AGENT_FACTORIES = (
    DataQualityAgent,
    AuditTriageAgent,
    TapeScoutAgent,
    PortfolioWatchAgent,
    DevelopmentEfficiencyAgent,
)


def run_once(
    context: dict | None,
    *,
    store: AgentStore | None = None,
    agents: Iterable[object] | None = None,
) -> dict:
    store = store or AgentStore()
    active_agents = list(agents or [factory() for factory in DEFAULT_AGENT_FACTORIES])
    runs = []
    total_observations = 0
    for agent in active_agents:
        name = getattr(agent, "name", agent.__class__.__name__)
        run_id = store.begin_run(name, model_version=getattr(agent, "model_version", None))
        try:
            observations = list(agent.run(context or {}))
            recorded = store.record_observations(run_id, observations)
            store.finish_run(run_id, status="ok", observation_count=recorded)
            total_observations += recorded
            runs.append({"agent": name, "status": "ok", "observations": recorded})
        except Exception as exc:
            store.finish_run(run_id, status="error", error=str(exc), observation_count=0)
            runs.append({"agent": name, "status": "error", "error": str(exc)[:300]})
    return {"status": "ok", "runs": runs, "observation_count": total_observations}
