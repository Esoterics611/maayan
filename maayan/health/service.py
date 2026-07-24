"""Health probes: is each dependency actually reachable, right now?

Each probe is a small injected object satisfying `HealthProbe`, so the service is
testable without Qdrant, without a model, and without spending money on a provider
call. Every probe is responsible for never raising — a health check that throws is
worse than useless, because the thing it was meant to report on is exactly what has
gone wrong.

Cost discipline: the generation probe must NEVER hit a completion endpoint. Asking
"are you alive?" should not bill tokens, so it lists models (free on OpenRouter,
local on Ollama) or, failing that, reports whether it is configured at all.
"""

from __future__ import annotations

import time
from typing import Protocol

import httpx

from maayan.clock import Clock
from maayan.config import Settings
from maayan.embed.base import Embedder
from maayan.health.models import ComponentHealth, HealthReport
from maayan.index.qdrant import QdrantIndex


class HealthProbe(Protocol):
    """One dependency's check (DI seam). Must not raise."""

    def check(self) -> ComponentHealth: ...


class QdrantProbe:
    """Reachable? Does the collection exist, and does it hold anything?

    An empty or missing collection is `degraded`, not `ok`: retrieval against it
    succeeds and returns nothing, which downstream looks exactly like "the corpus
    doesn't cover that" — the failure mode that started the retrieval audit.
    """

    name = "qdrant"

    def __init__(self, index: QdrantIndex, *, collection: str) -> None:
        self._index = index
        self._collection = collection

    def check(self) -> ComponentHealth:
        started = time.monotonic()
        try:
            points = self._index.count()
        except Exception as exc:  # noqa: BLE001 - a probe reports failures, never raises
            return ComponentHealth(
                name=self.name, status="down",
                detail=f"{type(exc).__name__}: {exc}"[:200],
                latency_ms=(time.monotonic() - started) * 1000,
            )
        elapsed = (time.monotonic() - started) * 1000
        if points == 0:
            return ComponentHealth(
                name=self.name, status="degraded", latency_ms=elapsed,
                detail=f"collection {self._collection!r} is empty — run `maayan index`",
            )
        return ComponentHealth(
            name=self.name, status="ok", latency_ms=elapsed,
            detail=f"{points} points in {self._collection!r}",
        )


class EmbedderProbe:
    """Can the embedder actually embed? Reports the dense dim and sparse-term count.

    Takes an ALREADY-CONSTRUCTED embedder: loading bge-m3 costs ~15s and several GB,
    so a health check must never trigger it. When the process has no embedder (the
    UI can run without one), this reports `skipped` rather than pretending.
    """

    name = "embedder"

    def __init__(self, embedder: Embedder | None, *, model: str, probe_text: str) -> None:
        self._embedder = embedder
        self._model = model
        self._probe_text = probe_text

    def check(self) -> ComponentHealth:
        if self._embedder is None:
            return ComponentHealth(
                name=self.name, status="skipped", detail="not loaded in this process"
            )
        started = time.monotonic()
        try:
            emb = self._embedder.embed_query(self._probe_text)
        except Exception as exc:  # noqa: BLE001
            return ComponentHealth(
                name=self.name, status="down",
                detail=f"{type(exc).__name__}: {exc}"[:200],
                latency_ms=(time.monotonic() - started) * 1000,
            )
        elapsed = (time.monotonic() - started) * 1000
        if not emb.dense:
            return ComponentHealth(
                name=self.name, status="degraded", latency_ms=elapsed,
                detail=f"{self._model} returned an empty dense vector",
            )
        return ComponentHealth(
            name=self.name, status="ok", latency_ms=elapsed,
            detail=f"{self._model} · dim {len(emb.dense)} · {len(emb.sparse_indices)} sparse terms",
        )


class GenerationProbe:
    """Is the configured generation backend reachable — without spending a token.

    Lists models rather than completing anything. For OpenRouter a missing API key is
    `down` on its own: no key means every grounded answer will fail at the last step,
    and finding that out when a scholar asks is too late.
    """

    name = "generation"

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client

    def check(self) -> ComponentHealth:
        s = self._settings
        if s.generation_backend == "ollama":
            return self._probe(f"{s.ollama_base_url.rstrip('/')}/api/tags", {}, s.ollama_model)
        key = s.openrouter_api_key.get_secret_value()
        if not key:
            return ComponentHealth(
                name=self.name, status="down",
                detail="OPENROUTER_API_KEY is not set — every answer will fail to generate",
            )
        return self._probe(
            f"{s.openrouter_base_url.rstrip('/')}/models",
            {"Authorization": f"Bearer {key}"},   # never logged; only sent
            s.openrouter_model,
        )

    def _probe(self, url: str, headers: dict[str, str], model: str) -> ComponentHealth:
        started = time.monotonic()
        try:
            client = self._client or httpx.Client(timeout=self._settings.health_timeout)
            response = client.get(url, headers=headers)
            elapsed = (time.monotonic() - started) * 1000
            if response.status_code >= 400:
                return ComponentHealth(
                    name=self.name, status="down", latency_ms=elapsed,
                    detail=f"{self._settings.generation_backend} returned HTTP "
                           f"{response.status_code}",
                )
        except Exception as exc:  # noqa: BLE001
            return ComponentHealth(
                name=self.name, status="down",
                detail=f"{type(exc).__name__}: {exc}"[:200],
                latency_ms=(time.monotonic() - started) * 1000,
            )
        return ComponentHealth(
            name=self.name, status="ok", latency_ms=elapsed,
            detail=f"{self._settings.generation_backend} · {model}",
        )


class HealthService:
    """Runs every injected probe and assembles the report."""

    def __init__(self, probes: list[HealthProbe], clock: Clock | None = None) -> None:
        self._probes = probes
        self._clock = clock

    def check(self) -> HealthReport:
        return HealthReport(components=[p.check() for p in self._probes])
