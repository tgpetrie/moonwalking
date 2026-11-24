from __future__ import annotations

from .contracts import AgentObservation


class DevelopmentEfficiencyAgent:
    """Turns local development state into handoff and efficiency observations."""

    name = "development_efficiency"
    model_version = "development-efficiency-v1"

    def run(self, context: dict | None) -> list[AgentObservation]:
        repo = (context or {}).get("repo_status")
        tests = (context or {}).get("test_status")
        observations: list[AgentObservation] = []

        if isinstance(repo, dict):
            modified = list(repo.get("modified_files") or [])
            untracked = list(repo.get("untracked_files") or [])
            branch = repo.get("branch")
            if modified or untracked:
                observations.append(
                    AgentObservation(
                        agent=self.name,
                        kind="uncommitted_work",
                        severity="watch",
                        summary="There is local work that needs a clean handoff note before another agent edits nearby files.",
                        evidence={
                            "branch": branch,
                            "modified_files": modified[:40],
                            "untracked_files": untracked[:40],
                            "modified_count": len(modified),
                            "untracked_count": len(untracked),
                        },
                        source={"surface": "repo"},
                    )
                )
            touched_docs = any(str(path).startswith("docs/") for path in modified + untracked)
            touched_backend = any(str(path).startswith("backend/") for path in modified + untracked)
            touched_frontend = any(str(path).startswith("frontend/") for path in modified + untracked)
            if (touched_backend or touched_frontend) and not touched_docs:
                observations.append(
                    AgentObservation(
                        agent=self.name,
                        kind="handoff_docs_needed",
                        severity="info",
                        summary="Code changed without a docs change, so the dev handoff may need a short update.",
                        evidence={
                            "backend_changed": touched_backend,
                            "frontend_changed": touched_frontend,
                            "docs_changed": touched_docs,
                        },
                        source={"surface": "repo"},
                    )
                )

        if isinstance(tests, dict):
            failed = int(tests.get("failed", 0) or 0)
            errors = int(tests.get("errors", 0) or 0)
            skipped = int(tests.get("skipped", 0) or 0)
            if failed or errors:
                observations.append(
                    AgentObservation(
                        agent=self.name,
                        kind="test_failures",
                        severity="critical",
                        summary="Local checks have failures that should be fixed before handoff.",
                        evidence={"failed": failed, "errors": errors, "skipped": skipped},
                        source={"surface": "tests"},
                    )
                )
        return observations
