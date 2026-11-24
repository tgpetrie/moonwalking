"""Local LLM adapter for optional Moonwalking summaries."""

from .client import LocalLLMClient, LocalLLMConfig, summarize_observations

__all__ = ["LocalLLMClient", "LocalLLMConfig", "summarize_observations"]
