"""Provider interface for pluggable sentiment data sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

_PROVIDER_REGISTRY: Dict[str, "SentimentProvider"] = {}


class SentimentProvider(ABC):
    """Contract for concrete sentiment data providers."""

    name: str = "base"

    @abstractmethod
    async def fetch_latest(self) -> Dict[str, Any]:
        """Return a mapping compatible with ``SentimentResponse``."""


def register_provider(provider: "SentimentProvider") -> None:
    """Register a provider instance that can be fetched by name."""

    _PROVIDER_REGISTRY[provider.name] = provider


def get_provider(name: Optional[str] = None) -> Optional["SentimentProvider"]:
    """Return a provider by name or the first available fallback."""

    if name:
        return _PROVIDER_REGISTRY.get(name)
    return next(iter(_PROVIDER_REGISTRY.values()), None)


__all__ = ["SentimentProvider", "register_provider", "get_provider"]
