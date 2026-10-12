from __future__ import annotations

from typing import Any

from .contracts import AgentObservation


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value == value else None


def _symbol(row: dict) -> str | None:
    value = row.get("symbol") or row.get("product_id") or row.get("productId")
    return str(value).upper().split("-")[0] if value else None


class PortfolioWatchAgent:
    """Reads portfolio risk-board rows and surfaces evidence-backed watch items."""

    name = "portfolio_watch"
    model_version = "portfolio-watch-rule-v1"

    def run(self, context: dict | None) -> list[AgentObservation]:
        payload = (context or {}).get("risk_board")
        if not isinstance(payload, dict):
            return []
        rows = payload.get("rows")
        if not isinstance(rows, list):
            return [
                AgentObservation(
                    agent=self.name,
                    kind="risk_board_unavailable",
                    severity="warning",
                    summary="Portfolio risk board payload has no rows for the portfolio agent to inspect.",
                    evidence={"status": payload.get("status")},
                    source={"surface": "portfolio_risk_board"},
                )
            ]

        observations: list[AgentObservation] = []
        source = payload.get("source")
        if source and source != "portfolio":
            observations.append(
                AgentObservation(
                    agent=self.name,
                    kind="portfolio_fallback_source",
                    severity="info",
                    summary="Portfolio watch is using watchlist data, so position-size observations are unavailable.",
                    evidence={
                        "source": source,
                        "fallback_reason": payload.get("fallback_reason"),
                    },
                    source={"surface": "portfolio_risk_board"},
                )
            )

        unavailable = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = _symbol(row)
            plan = row.get("plan") if isinstance(row.get("plan"), dict) else {}
            entry = row.get("entry") if isinstance(row.get("entry"), dict) else {}
            status = (
                row.get("status")
                or plan.get("top_signal", {}).get("status")
                if isinstance(plan.get("top_signal"), dict)
                else None
            )
            available = bool(plan.get("available"))
            if not available:
                unavailable.append(symbol or "unknown")
                continue
            if status in {"high", "protect_now"}:
                observations.append(
                    AgentObservation(
                        agent=self.name,
                        kind="holding_protection_watch",
                        severity="critical",
                        symbol=symbol,
                        summary=f"{symbol} is in the highest protection bucket on the risk board.",
                        evidence={
                            "status": status,
                            "current_price": plan.get("current_price"),
                            "stop_trigger": plan.get("stop_trigger"),
                            "top_signal": plan.get("top_signal"),
                            "position_value_usd": row.get("position_value_usd"),
                        },
                        source={"surface": "portfolio_risk_board"},
                    )
                )
            elif status in {"watch", "medium"}:
                observations.append(
                    AgentObservation(
                        agent=self.name,
                        kind="holding_watch",
                        severity="watch",
                        symbol=symbol,
                        summary=f"{symbol} is in a portfolio watch bucket.",
                        evidence={
                            "status": status,
                            "top_signal": plan.get("top_signal"),
                            "position_value_usd": row.get("position_value_usd"),
                        },
                        source={"surface": "portfolio_risk_board"},
                    )
                )

            entry_status = entry.get("status") or row.get("entry_status")
            if entry_status in {"Breakout watch", "Support reclaim", "Pullback watch"}:
                observations.append(
                    AgentObservation(
                        agent=self.name,
                        kind="entry_watch",
                        severity="watch",
                        symbol=symbol,
                        summary=f"{symbol} has an entry-side watch state: {entry_status}.",
                        evidence={
                            "entry_status": entry_status,
                            "entry_zone": entry.get("entry_zone"),
                            "invalidation": entry.get("invalidation"),
                            "reward_to_risk": _num(entry.get("reward_to_risk")),
                            "evidence_score": entry.get("evidence_score"),
                        },
                        source={"surface": "portfolio_risk_board"},
                    )
                )

        if unavailable:
            observations.append(
                AgentObservation(
                    agent=self.name,
                    kind="risk_plan_unavailable",
                    severity="info",
                    summary="Some portfolio/watchlist symbols do not have enough data for a risk plan yet.",
                    evidence={"symbols": unavailable[:40], "count": len(unavailable)},
                    source={"surface": "portfolio_risk_board"},
                )
            )
        return observations
