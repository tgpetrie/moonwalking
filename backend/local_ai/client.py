from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any
from urllib.parse import urlparse

import requests


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class LocalLLMConfig:
    enabled: bool = False
    provider: str = "ollama"
    base_url: str = "http://127.0.0.1:11434/v1"
    model: str = ""
    timeout_seconds: float = 20.0
    allow_remote: bool = False

    @classmethod
    def from_env(cls) -> "LocalLLMConfig":
        return cls(
            enabled=os.environ.get("BHABIT_LLM_ENABLED", "0") == "1",
            provider=os.environ.get("BHABIT_LLM_PROVIDER", "ollama"),
            base_url=os.environ.get(
                "BHABIT_LLM_BASE_URL", "http://127.0.0.1:11434/v1"
            ),
            model=os.environ.get("BHABIT_LLM_MODEL", ""),
            timeout_seconds=float(os.environ.get("BHABIT_LLM_TIMEOUT_SECONDS", "20")),
            allow_remote=os.environ.get("BHABIT_LLM_ALLOW_REMOTE", "0") == "1",
        )

    def validate(self) -> None:
        if not self.enabled:
            return
        if not self.model.strip():
            raise ValueError("BHABIT_LLM_MODEL is required when local LLM is enabled")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("BHABIT_LLM_BASE_URL must be an HTTP URL")
        if not self.allow_remote and parsed.hostname not in LOCAL_HOSTS:
            raise ValueError(
                "Local LLM base URL must point at localhost unless "
                "BHABIT_LLM_ALLOW_REMOTE=1 is set"
            )


class LocalLLMClient:
    """Small OpenAI-compatible client for Ollama or LM Studio local servers."""

    def __init__(self, config: LocalLLMConfig | None = None):
        self.config = config or LocalLLMConfig.from_env()
        self.config.validate()

    def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.1) -> str:
        if not self.config.enabled:
            raise RuntimeError("local LLM is disabled")
        endpoint = self.config.base_url.rstrip("/") + "/chat/completions"
        response = requests.post(
            endpoint,
            json={
                "model": self.config.model,
                "messages": messages,
                "temperature": temperature,
            },
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise ValueError("local LLM returned no choices")
        content = choices[0].get("message", {}).get("content")
        text = str(content or "").strip()
        if not text:
            raise ValueError("local LLM returned an empty message")
        return text


def summarize_observations(
    observations: list[dict[str, Any]], *, client: LocalLLMClient | None = None
) -> dict:
    config = (client.config if client else LocalLLMConfig.from_env())
    if not config.enabled:
        return {
            "status": "disabled",
            "summary": None,
            "reason": "Set BHABIT_LLM_ENABLED=1 and BHABIT_LLM_MODEL to use a local model.",
        }
    client = client or LocalLLMClient(config)
    compact = [
        {
            "agent": item.get("agent"),
            "kind": item.get("kind"),
            "severity": item.get("severity"),
            "symbol": item.get("symbol"),
            "summary": item.get("summary"),
            "evidence": item.get("evidence"),
        }
        for item in observations[:30]
    ]
    text = client.chat(
        [
            {
                "role": "system",
                "content": (
                    "You summarize Moonwalking local-agent observations. "
                    "Use only the supplied observations. Do not add trading advice. "
                    "If data is missing, say it is missing."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Write a short operator briefing from these observations:\n"
                    f"{compact}"
                ),
            },
        ]
    )
    return {"status": "ok", "summary": text, "model": config.model}
