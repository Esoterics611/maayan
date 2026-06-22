"""Local Ollama generation backend (Prompt 8) — the offline/private *backup*.

Implements the same `GenerationBackend` protocol as `OpenRouterBackend`, so it is
selected by `GENERATION_BACKEND=ollama` with no other code change. OpenRouter stays
the default; this exists so the loop can run fully local when needed. Talks to
Ollama's native non-streaming chat endpoint (`POST {base_url}/api/chat`) over an
injected/owned `httpx.Client`, so the unit test mocks it with respx (no real model).

Tradeoff (see CLAUDE.md): offline + private + free, but small local models are weaker,
especially on Hebrew. RAG + default-deny + citations stay the backbone regardless.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from maayan.generate.base import Message


class OllamaBackend:
    """Calls a local Ollama model via its native /api/chat endpoint (stream=false)."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b-instruct",
        temperature: float = 0.2,
        timeout: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._client = client or httpx.Client(timeout=timeout)

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        chat: list[dict[str, str]] = [{"role": "system", "content": system}]
        chat.extend({"role": m.role, "content": m.content} for m in messages)
        resp = self._client.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": chat,
                "stream": False,
                "options": {"temperature": self._temperature},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        message = data.get("message") if isinstance(data, dict) else None
        if not isinstance(message, dict):
            return ""
        content = message.get("content")
        return content if isinstance(content, str) else ""
