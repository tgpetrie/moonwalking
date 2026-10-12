from agents.audit_triage import analyze_audit_markdown


AUDIT = """
# Portfolio Risk Board audit

## B. Ranked UX problems

### P0 — misleading
1. Broken-support card reverses level direction and misstates why R/R is absent.
2. Chart/popup hide the entry invalidation boundary.

### P1 — confusing
6. Protection and entry R/R use different denominators without labels explaining them.

### P2 — polish
12. No honest entry band here is awkward trader-facing language.

## C. Exact recommended changes

| Files/components | Problem -> proposed behavior and copy | Backend contract impact |
|---|---|---|
| PortfolioRiskBoard.jsx | Make invalidation dominant. | None. |
| RiskLevelsChart.jsx | Pass and consume entry alongside plan. | None. |

## E. Smallest coherent implementation sequence

1. fix: make risk validity and level direction explicit - signed invalidation distances.
2. feat: explain risk references and supporting evidence - shared stop labels.
"""


def test_audit_triage_extracts_ranked_problems_and_steps():
    observations = analyze_audit_markdown(AUDIT, source_path="AUDIT.md")

    problems = [item for item in observations if item.kind == "audit_problem"]
    changes = [item for item in observations if item.kind == "audit_recommended_change"]
    steps = [item for item in observations if item.kind == "audit_implementation_step"]

    assert len(problems) == 4
    assert problems[0].severity == "critical"
    assert any("Broken-support" in item.summary for item in problems)
    assert len(changes) == 2
    assert changes[0].evidence["files"] == "PortfolioRiskBoard.jsx"
    assert len(steps) == 2
    assert steps[0].severity == "watch"
