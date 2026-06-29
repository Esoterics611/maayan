"""Capture service factory (DI at the edge)."""

from __future__ import annotations

from maayan.capture.populate import ConnectionDrafter, ConnectionPopulator
from maayan.capture.service import CaptureService
from maayan.capture.store import CaptureStore
from maayan.capture.suggestions import ConnectionSuggestionStore
from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.embed.base import Embedder
from maayan.embed.factory import build_embedder
from maayan.generate.base import GenerationBackend
from maayan.generate.factory import build_generation_backend
from maayan.index.qdrant import QdrantIndex, build_qdrant_client


def build_capture_service(
    settings: Settings, *, embedder: Embedder | None = None
) -> CaptureService:
    """Assemble a CaptureService wired to the same stores + collection as the rest."""
    embedder = embedder or build_embedder(settings)
    index = QdrantIndex(
        build_qdrant_client(settings), settings.collection_name, embedder.dim
    )
    return CaptureService(
        CaptureStore(settings.db_path),
        ChunkStore(settings.db_path),
        embedder,
        index,
        SystemClock(),
        allowed_kinds=settings.annotation_kinds,
    )


def build_connection_populator(
    settings: Settings,
    *,
    embedder: Embedder | None = None,
    backend: GenerationBackend | None = None,
) -> ConnectionPopulator:
    """Assemble the cross-text connection auto-populator (drafter + queue + capture).

    The drafting model is swapped here (the same `lexicon_draft_model` knob) so Claude
    drafts the connection while maayan's own answers stay on its generation model. Drafts
    are grounded in both ends, cited, and queued for approval before indexing.
    """
    embedder = embedder or build_embedder(settings)
    draft_settings = settings
    if settings.lexicon_draft_model:
        field = "ollama_model" if settings.generation_backend == "ollama" else "openrouter_model"
        draft_settings = settings.model_copy(update={field: settings.lexicon_draft_model})
    backend = backend or build_generation_backend(draft_settings)
    drafter = ConnectionDrafter(
        backend,
        SystemClock(),
        model=draft_settings.generation_model,
        verify=settings.lexicon_draft_verify,
    )
    return ConnectionPopulator(
        drafter,
        ConnectionSuggestionStore(settings.db_path),
        build_capture_service(settings, embedder=embedder),
    )
