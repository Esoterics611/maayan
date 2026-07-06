"""OpenRouter generation backend (OpenAI-compatible API).

The API key comes from config (env), never hardcoded or logged. The OpenAI client
is pointed at OPENROUTER_BASE_URL. This is the only component that talks to the
cloud; everything else runs locally.
"""

from __future__ import annotations

from collections.abc import Sequence

from maayan.generate.base import GenerationError, Message


def _error_detail(response: object) -> str:
    """Pull a human message out of an OpenRouter error-in-200 body, if present.

    OpenRouter signals a transient upstream failure by returning HTTP 200 with
    ``choices: null`` and an ``error`` object; the OpenAI SDK parses the latter
    into ``response.error``. Best-effort — returns "" when there's nothing useful.
    """
    err = getattr(response, "error", None)
    if isinstance(err, dict):
        msg = err.get("message")
        if isinstance(msg, str) and msg:
            return msg
    return ""


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
        max_tokens: int | None = None,
        max_retries: int = 2,
    ) -> None:
        from openai import OpenAI

        self._client = OpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout, max_retries=max_retries
        )
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        from openai import OpenAIError

        chat: list[dict[str, str]] = [{"role": "system", "content": system}]
        chat.extend({"role": m.role, "content": m.content} for m in messages)

        # OpenRouter occasionally returns HTTP 200 with choices=null on a transient
        # upstream/provider hiccup — the SDK doesn't treat that as an error, so its own
        # retries never fire and blindly indexing choices[0] crashes the whole request.
        # Re-issue once immediately (no backoff, so no clock needed) before giving up;
        # a hand-rerun is exactly what recovers this in practice.
        last_detail = ""
        for _ in range(2):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=chat,  # type: ignore[arg-type]
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                )
            except OpenAIError as exc:
                raise GenerationError(f"The model provider errored: {exc}") from exc
            if response.choices:
                return response.choices[0].message.content or ""
            last_detail = _error_detail(response)

        suffix = f" ({last_detail})" if last_detail else ""
        raise GenerationError(
            f"The model provider returned an empty response{suffix}. Please try again."
        )
