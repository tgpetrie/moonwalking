from __future__ import annotations

import time
from typing import Any

from .contracts import AgentObservation


TABLES = ("gainers_1m", "gainers_3m", "losers_3m")


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


class TapeScoutAgent:
    """Rule baseline that spots fast moves without calling them predictive."""

    name = "tape_scout"
    model_version = "tape-scout-rule-v1"

    def __init__(self, *, one_min_threshold: float = 2.0, three_min_threshold: float = 4.0):
        self.one_min_threshold = one_min_threshold
        self.three_min_threshold = three_min_threshold

    def run(self, context: dict | None) -> list[AgentObservation]:
        snapshot = (context or {}).get("board_snapshot")
        if not isinstance(snapshot, dict):
            return []
        created_ts = int(time.time())
        observations: list[AgentObservation] = []
        seen: set[tuple[str, str]] = set()
        for table in TABLES:
            rows = snapshot.get(table)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                symbol = _symbol(row)
                if not symbol:
                    continue
                pct_1m = _num(row.get("pct_1m"))
                pct_3m = _num(row.get("pct_3m"))
                reasons = []
                if pct_1m is not None and abs(pct_1m) >= self.one_min_threshold:
                    reasons.append("1m")
                if pct_3m is not None and abs(pct_3m) >= self.three_min_threshold:
                    reasons.append("3m")
                if not reasons:
                    continue
                key = (symbol, ",".join(reasons))
                if key in seen:
                    continue
                seen.add(key)
                direction = "up" if (pct_3m or pct_1m or 0) >= 0 else "down"
                observations.append(
                    AgentObservation(
                        agent=self.name,
                        kind="fast_price_move",
                        severity="watch",
                        symbol=symbol,
                        summary=(
                            f"{symbol} has a fast {direction} move on "
                            f"{'/'.join(reasons)} tape. Treat this as a watch item, not a forecast."
                        ),
                        evidence={
                            "table": table,
                            "pct_1m": pct_1m,
                            "pct_3m": pct_3m,
                            "thresholds": {
                                "pct_1m_abs": self.one_min_threshold,
                                "pct_3m_abs": self.three_min_threshold,
                            },
                        },
                        source={"surface": "board", "table": table},
                        created_ts=created_ts,
                        expires_ts=created_ts + 300,
                    )
                )
        return observations
