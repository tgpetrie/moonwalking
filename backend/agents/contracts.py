from __future__ import annotations

from dataclasses import dataclass, field
import math
import time
from typing import Any, Mapping


VALID_SEVERITIES = {"info", "watch", "warning", "critical"}


def utc_ts() -> int:
    return int(time.time())


def json_safe(value: Any) -> Any:
    """Return a JSON-safe value without inventing replacement market data."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return str(value)


@dataclass(frozen=True)
class AgentObservation:
    agent: str
    kind: str
    summary: str
    severity: str = "info"
    product_id: str | None = None
    symbol: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)
    source: Mapping[str, Any] = field(default_factory=dict)
    created_ts: int = field(default_factory=utc_ts)
    expires_ts: int | None = None

    def __post_init__(self) -> None:
        if not self.agent.strip():
            raise ValueError("agent is required")
        if not self.kind.strip():
            raise ValueError("kind is required")
        if not self.summary.strip():
            raise ValueError("summary is required")
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"invalid severity: {self.severity}")

    def to_record(self) -> dict[str, Any]:
        symbol = self.symbol.upper() if self.symbol else None
        product_id = self.product_id.upper() if self.product_id else None
        if symbol and not product_id:
            product_id = f"{symbol}-USD"
        if product_id and not symbol:
            symbol = product_id.split("-")[0]
        return {
            "agent": self.agent,
            "kind": self.kind,
            "summary": self.summary,
            "severity": self.severity,
            "product_id": product_id,
            "symbol": symbol,
            "evidence": json_safe(dict(self.evidence)),
            "source": json_safe(dict(self.source)),
            "created_ts": int(self.created_ts),
            "expires_ts": int(self.expires_ts) if self.expires_ts is not None else None,
        }
