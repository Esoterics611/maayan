"""Health service factory — DI at the edge (CLI / UI wiring)."""

from __future__ import annotations

from maayan.config import Settings
from maayan.embed.base import Embedder
from maayan.health.service import (
    EmbedderProbe,
    GenerationProbe,
    HealthProbe,
    HealthService,
    QdrantProbe,
)
from maayan.index.qdrant import QdrantIndex, build_qdrant_client


def build_health_service(
    settings: Settings, *, embedder: Embedder | None = None
) -> HealthService:
    """Assemble the standard probe set.

    `embedder` is passed in rather than built: loading bge-m3 costs ~15s and several
    GB, so a health check must never trigger it. Callers that already have one (the
    UI, `maayan ask`) hand it over; the rest get an honest `skipped`.
    """
    index = QdrantIndex(
        build_qdrant_client(settings), settings.collection_name, settings.embed_dim
    )
    probes: list[HealthProbe] = [
        QdrantProbe(index, collection=settings.collection_name),
        EmbedderProbe(
            embedder, model=settings.embed_model, probe_text=settings.health_probe_text
        ),
    ]
    if settings.health_check_generation:
        probes.append(GenerationProbe(settings))
    return HealthService(probes)
