from __future__ import annotations

import re
from typing import Iterable

from .contracts import AgentObservation


PRIORITY_SEVERITY = {"P0": "critical", "P1": "warning", "P2": "info"}


def _section(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)",
        re.MULTILINE,
    )
    match = pattern.search(markdown)
    return match.group(1).strip() if match else ""


def _priority_sections(markdown: str) -> Iterable[tuple[str, str]]:
    ranked = _section(markdown, "B. Ranked UX problems")
    for priority in ("P0", "P1", "P2"):
        pattern = re.compile(
            rf"^###\s+{priority}\b[^\n]*\n([\s\S]*?)(?=^###\s+P[0-9]\b|^##\s+|\Z)",
            re.MULTILINE,
        )
        match = pattern.search(ranked)
        if match:
            yield priority, match.group(1).strip()


def _numbered_items(text: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if re.match(r"^\d+\.\s+", line):
            if current:
                items.append(" ".join(current).strip())
            current = [re.sub(r"^\d+\.\s+", "", line).strip()]
        elif current and line.strip():
            current.append(line.strip())
    if current:
        items.append(" ".join(current).strip())
    return items


def _implementation_steps(markdown: str) -> list[str]:
    return _numbered_items(_section(markdown, "E. Smallest coherent implementation sequence"))


def _recommended_change_rows(markdown: str) -> list[dict[str, str]]:
    section = _section(markdown, "C. Exact recommended changes")
    rows: list[dict[str, str]] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line or "Files/components" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        rows.append(
            {
                "files": cells[0],
                "change": cells[1],
                "backend_contract": cells[2],
            }
        )
    return rows


def analyze_audit_markdown(markdown: str, *, source_path: str | None = None) -> list[AgentObservation]:
    observations: list[AgentObservation] = []
    source = {"surface": "audit", "path": source_path} if source_path else {"surface": "audit"}

    for priority, section_text in _priority_sections(markdown):
        for item in _numbered_items(section_text):
            observations.append(
                AgentObservation(
                    agent="audit_triage",
                    kind="audit_problem",
                    severity=PRIORITY_SEVERITY.get(priority, "info"),
                    summary=f"{priority}: {item.split('. ', 1)[0].strip()}",
                    evidence={"priority": priority, "text": item},
                    source=source,
                )
            )

    for row in _recommended_change_rows(markdown):
        observations.append(
            AgentObservation(
                agent="audit_triage",
                kind="audit_recommended_change",
                severity="watch",
                summary=f"Audit recommends changes in {row['files']}.",
                evidence=row,
                source=source,
            )
        )

    for index, step in enumerate(_implementation_steps(markdown), start=1):
        observations.append(
            AgentObservation(
                agent="audit_triage",
                kind="audit_implementation_step",
                severity="watch" if index == 1 else "info",
                summary=f"Audit implementation step {index}: {step.split(' - ', 1)[0]}",
                evidence={"step": index, "text": step},
                source=source,
            )
        )

    if not observations and markdown.strip():
        observations.append(
            AgentObservation(
                agent="audit_triage",
                kind="audit_unparsed",
                severity="warning",
                summary="Audit text was provided, but no ranked problems or work items were parsed.",
                evidence={"characters": len(markdown)},
                source=source,
            )
        )
    return observations


class AuditTriageAgent:
    """Turns saved audits into structured local-agent observations."""

    name = "audit_triage"
    model_version = "audit-triage-v1"

    def run(self, context: dict | None) -> list[AgentObservation]:
        context = context or {}
        markdown = context.get("audit_markdown")
        if not isinstance(markdown, str) or not markdown.strip():
            return []
        return analyze_audit_markdown(markdown, source_path=context.get("audit_source_path"))
