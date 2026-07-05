"""Summary service factory (DI at the edge).

The drafting model is swapped here (mirrors lexicon_draft_model): set
`summary_draft_model` to draft summaries with a stronger model while maayan's answers
stay on the configured generation model.
"""

from __future__ import annotations

from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.embed.base import Embedder
from maayan.embed.factory import build_embedder
from maayan.generate.base import GenerationBackend
from maayan.generate.factory import build_generation_backend
from maayan.index.qdrant import QdrantIndex, build_qdrant_client
from maayan.summarize.draft import SummaryDrafter
from maayan.summarize.service import SummaryService
from maayan.summarize.store import SummaryStore


def build_summary_service(
    settings: Settings,
    *,
    embedder: Embedder | None = None,
    backend: GenerationBackend | None = None,
) -> SummaryService:
    """Assemble the summary service wired to the shared stores + collection."""
    embedder = embedder or build_embedder(settings)
    draft_settings = settings
    if settings.summary_draft_model:
        field = "ollama_model" if settings.generation_backend == "ollama" else "openrouter_model"
        draft_settings = settings.model_copy(update={field: settings.summary_draft_model})
    backend = backend or build_generation_backend(draft_settings)
    index = QdrantIndex(
        build_qdrant_client(settings), settings.collection_name, embedder.dim
    )
    drafter = SummaryDrafter(
        backend,
        SystemClock(),
        model=draft_settings.generation_model,
        verify=settings.summary_draft_verify,
    )
    return SummaryService(
        drafter,
        ChunkStore(settings.db_path),
        SummaryStore(settings.db_path),
        embedder,
        index,
        SystemClock(),
        pace=settings.summary_pace_seconds,
        max_retries=settings.populate_max_retries,
        backoff=settings.populate_backoff_seconds,
    )
