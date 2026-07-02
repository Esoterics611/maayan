"""Generation backend factory — selects OpenRouter/Ollama from config (DI seam).

The `GENERATION_BACKEND` config switch decides which backend is injected; no other
code changes when swapping cloud ↔ local. (Ollama lands in Prompt 8.)
"""

from __future__ import annotations

from maayan.config import Settings
from maayan.generate.base import GenerationBackend


def build_generation_backend(settings: Settings) -> GenerationBackend:
    backend = settings.generation_backend
    if backend == "openrouter":
        from maayan.generate.openrouter import OpenRouterBackend

        api_key = settings.openrouter_api_key.get_secret_value()
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is not set. Add it to .env (see .env.example)."
            )
        return OpenRouterBackend(
            api_key,
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_model,
            max_tokens=settings.generation_max_tokens,
            timeout=settings.generation_timeout,
            max_retries=settings.generation_max_retries,
        )
    if backend == "ollama":
        from maayan.generate.ollama import OllamaBackend

        return OllamaBackend(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    raise ValueError(f"Unknown or unsupported generation_backend: {backend!r}")
