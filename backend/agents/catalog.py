"""Human-facing names and purposes for the local agents.

The Agents page lists every agent the runner knows about, including ones that
have never run on this machine, so it needs a label and a one-line purpose for
each. Keep this in step with ``runner.DEFAULT_AGENT_FACTORIES``; a test fails if
a default agent has no entry here.
"""

from __future__ import annotations

AGENT_CATALOG: dict[str, dict[str, str]] = {
    "data_quality": {
        "label": "Data Quality",
        "purpose": (
            "Catches stale board snapshots, duplicate rows and missing prices "
            "that would make the app look wrong."
        ),
    },
    "audit_triage": {
        "label": "Audit Triage",
        "purpose": (
            "Turns a saved AUDIT.md into ranked problems, recommended changes "
            "and implementation steps. It identifies work; it does not fix it."
        ),
    },
    "tape_scout": {
        "label": "Tape Scout",
        "purpose": (
            "Flags fast 1-minute (2%+) and 3-minute (4%+) moves as watch items. "
            "A description of what moved, not a forecast."
        ),
    },
    "portfolio_watch": {
        "label": "Portfolio Watch",
        "purpose": (
            "Reads the Portfolio Risk Board and surfaces protection, watch and "
            "unavailable-plan states for coins you hold."
        ),
    },
    "development_efficiency": {
        "label": "Development Efficiency",
        "purpose": (
            "Flags uncommitted work, missing handoff docs and failing tests so "
            "handoffs between models and people stay clean."
        ),
    },
}


def describe(name: str) -> dict[str, str]:
    """Label and purpose for an agent, with a plain fallback for unknown names."""
    entry = AGENT_CATALOG.get(name)
    if entry:
        return dict(entry)
    return {"label": name.replace("_", " ").title(), "purpose": ""}
