"""Development service factory (DI at the edge)."""

from __future__ import annotations

from maayan.clock import SystemClock
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.develop.service import DevelopmentService
from maayan.develop.store import DevelopmentStore
from maayan.embed.base import Embedder
from maayan.embed.factory import build_embedder
from maayan.generate.factory import build_generation_backend
from maayan.index.qdrant import QdrantIndex, build_qdrant_client
from maayan.retrieve.factory import build_retriever
from maayan.threads.factory import build_thread_service


def build_development_service(
    settings: Settings, *, embedder: Embedder | None = None
) -> DevelopmentService:
    """Assemble a DevelopmentService wired to the same stores + collection as the rest."""
    embedder = embedder or build_embedder(settings)  # shared with the retriever + indexing
    retriever = build_retriever(settings, embedder=embedder)
    backend = build_generation_backend(settings)
    index = QdrantIndex(
        build_qdrant_client(settings), settings.collection_name, embedder.dim
    )
    return DevelopmentService(
        retriever,
        backend,
        DevelopmentStore(settings.db_path),
        build_thread_service(settings),
        SystemClock(),
        settings,
        embedder,
        ChunkStore(settings.db_path),
        index,
    )
