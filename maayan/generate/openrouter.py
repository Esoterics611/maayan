"""OpenRouter generation backend (OpenAI-compatible API).

The API key comes from config (env), never hardcoded or logged. The OpenAI client
is pointed at OPENROUTER_BASE_URL. This is the only component that talks to the
cloud; everything else runs locally.
"""

from __future__ import annotations

from collections.abc import Sequence

from maayan.generate.base import Message


class OpenRouterBackend:
    """Calls an open model via OpenRouter's OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "qwen/qwen-2.5-72b-instruct",
        temperature: float = 0.2,
        timeout: float = 60.0,
    ) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self._model = model
        self._temperature = temperature

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        chat: list[dict[str, str]] = [{"role": "system", "content": system}]
        chat.extend({"role": m.role, "content": m.content} for m in messages)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=chat,  # type: ignore[arg-type]
            temperature=self._temperature,
        )
        return response.choices[0].message.content or ""
