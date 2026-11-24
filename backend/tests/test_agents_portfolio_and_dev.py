from agents.development_efficiency import DevelopmentEfficiencyAgent
from agents.portfolio_watch import PortfolioWatchAgent


def test_portfolio_watch_flags_high_risk_holding():
    agent = PortfolioWatchAgent()

    observations = agent.run(
        {
            "risk_board": {
                "source": "portfolio",
                "rows": [
                    {
                        "symbol": "ETH",
                        "position_value_usd": 1000,
                        "plan": {
                            "available": True,
                            "current_price": 2500,
                            "stop_trigger": 2400,
                            "top_signal": {"status": "high", "label": "Protect now"},
                        },
                    }
                ],
            }
        }
    )

    assert observations[0].kind == "holding_protection_watch"
    assert observations[0].severity == "critical"


def test_portfolio_watch_marks_watchlist_fallback():
    agent = PortfolioWatchAgent()

    observations = agent.run(
        {
            "risk_board": {
                "source": "watchlist",
                "fallback_reason": "Showing your watchlist.",
                "rows": [],
            }
        }
    )

    assert observations[0].kind == "portfolio_fallback_source"


def test_development_efficiency_flags_uncommitted_code_without_docs():
    agent = DevelopmentEfficiencyAgent()

    observations = agent.run(
        {
            "repo_status": {
                "branch": "codex/example",
                "modified_files": ["backend/app.py"],
                "untracked_files": [],
            }
        }
    )

    kinds = {item.kind for item in observations}
    assert "uncommitted_work" in kinds
    assert "handoff_docs_needed" in kinds
